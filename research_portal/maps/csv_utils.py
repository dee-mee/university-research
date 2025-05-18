import csv
import io
import logging
import chardet
import codecs
import time
from typing import Dict, List, Any, Tuple, Optional, Callable, Iterator, Union
from django.db import transaction, DatabaseError
from django.core.files.uploadedfile import UploadedFile
from datetime import datetime, date
from dateutil import parser

logger = logging.getLogger(__name__)

class CSVImportError(Exception):
    """Custom exception for CSV import errors with detailed context"""
    def __init__(self, message, row=None, line_num=None, field=None):
        self.message = message
        self.row = row
        self.line_num = line_num
        self.field = field
        
        # Format detailed error message
        detail = ""
        if line_num is not None:
            detail += f" at line {line_num}"
        if field is not None:
            detail += f" in field '{field}'"
        
        super().__init__(f"{message}{detail}")


class CSVImportProgress:
    """Track progress of CSV import operations"""
    def __init__(self, total_rows=0, callback=None):
        self.total_rows = total_rows
        self.processed_rows = 0
        self.success_count = 0
        self.error_count = 0
        self.errors = []
        self.warnings = []
        self.start_time = time.time()
        self.callback = callback
        
    def success(self):
        """Record a successful row import"""
        self.processed_rows += 1
        self.success_count += 1
        self._update_progress()
        
    def error(self, error_message, row=None, line_num=None, field=None):
        """Record an error during row import"""
        self.processed_rows += 1
        self.error_count += 1
        
        error_detail = {
            "message": error_message,
            "line": line_num,
            "field": field
        }
        if row:
            # Limit row data to avoid overwhelming memory
            error_detail["row_data"] = str(row)[:500] 
            
        self.errors.append(error_detail)
        self._update_progress()
        
    def warning(self, warning_message, row=None, line_num=None, field=None):
        """Record a warning during row import"""
        warning_detail = {
            "message": warning_message,
            "line": line_num,
            "field": field
        }
        if row:
            # Limit row data to avoid overwhelming memory
            warning_detail["row_data"] = str(row)[:500]
            
        self.warnings.append(warning_detail)
        self._update_progress()
        
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the import operation"""
        duration = time.time() - self.start_time
        return {
            "success": self.success_count,
            "error": self.error_count, 
            "errors": self.errors[:100],  # Limit number of errors returned
            "warnings": self.warnings[:100],  # Limit number of warnings returned
            "total_processed": self.processed_rows,
            "total_rows": self.total_rows,
            "duration_seconds": round(duration, 2),
            "complete": self.total_rows > 0 and self.processed_rows >= self.total_rows
        }
    
    def _update_progress(self):
        """Update progress and call the callback if provided"""
        if self.callback and callable(self.callback):
            try:
                self.callback(self.get_summary())
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")


def detect_encoding(file_content: bytes) -> str:
    """
    Detect file encoding using chardet with fallback options
    
    Args:
        file_content: Raw bytes from the file
        
    Returns:
        String representing the detected encoding
    """
    # First try chardet to detect encoding
    result = chardet.detect(file_content)
    encoding = result.get('encoding', 'utf-8')
    confidence = result.get('confidence', 0)
    
    logger.debug(f"Detected encoding: {encoding} with confidence {confidence}")
    
    # If low confidence or encoding is None, try common encodings
    if confidence < 0.7 or not encoding:
        for enc in ['utf-8', 'latin-1', 'iso-8859-1', 'windows-1252', 'utf-16']:
            try:
                # Try to decode a sample with this encoding
                sample = file_content[:1000]
                sample.decode(enc)
                logger.debug(f"Using fallback encoding: {enc}")
                return enc
            except UnicodeDecodeError:
                continue
    
    return encoding or 'utf-8'  # Default to utf-8 if all else fails


def read_csv_file(csv_file: UploadedFile) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Read CSV file with automatic encoding detection
    
    Args:
        csv_file: Django UploadedFile object
        
    Returns:
        Tuple of (rows as list of dicts, field names)
    """
    # Read file content for encoding detection
    csv_file.seek(0)
    file_content = csv_file.read()
    
    if not file_content:
        raise CSVImportError("File is empty")
    
    # Detect encoding and decode file
    encoding = detect_encoding(file_content)
    
    try:
        decoded_content = file_content.decode(encoding)
    except UnicodeDecodeError:
        # If specific encoding fails, try with a more permissive one
        try:
            decoded_content = file_content.decode('latin-1', errors='replace')
            logger.warning("File encoding detection failed, using latin-1 with replacement")
        except Exception as e:
            raise CSVImportError(f"Failed to decode file with detected encoding ({encoding}): {e}")
    
    # Parse CSV content
    csv_file_obj = io.StringIO(decoded_content)
    
    # Try to determine dialect
    try:
        dialect = csv.Sniffer().sniff(decoded_content[:1024])
        reader = csv.DictReader(csv_file_obj, dialect=dialect)
    except csv.Error:
        # Fall back to default dialect
        csv_file_obj.seek(0)
        reader = csv.DictReader(csv_file_obj)
    
    # Check if file has headers
    if not reader.fieldnames:
        raise CSVImportError("CSV file has no headers")
    
    # Read all rows now to catch any issues early
    try:
        rows = list(reader)
    except csv.Error as e:
        raise CSVImportError(f"Error parsing CSV content: {e}")
    
    return rows, reader.fieldnames


def count_csv_rows(file_content: str) -> int:
    """
    Count the number of rows in a CSV file
    
    Args:
        file_content: String content of CSV file
        
    Returns:
        Number of rows in the file (excluding header)
    """
    return file_content.count('\n') - 1  # Subtract header row


def process_csv_in_batches(
    csv_file: UploadedFile,
    row_processor: Callable[[Dict[str, str], int, CSVImportProgress], None],
    batch_size: int = 100,
    progress_callback: Optional[Callable] = None,
    required_fields: List[str] = None
) -> Dict[str, Any]:
    """
    Process CSV file in batches with transaction support
    
    Args:
        csv_file: Django UploadedFile object
        row_processor: Function that processes each row
        batch_size: Number of rows to process in each transaction
        progress_callback: Function to call with progress updates
        required_fields: List of field names that must be present in the CSV
        
    Returns:
        Dictionary with import summary
    """
    # Read file with encoding detection
    csv_file.seek(0)
    file_content = csv_file.read()
    encoding = detect_encoding(file_content)
    
    try:
        decoded_content = file_content.decode(encoding)
    except UnicodeDecodeError:
        try:
            decoded_content = file_content.decode('latin-1', errors='replace')
        except Exception as e:
            return {
                "success": 0,
                "error": 1,
                "errors": [f"Failed to decode file: {str(e)}"],
                "warnings": []
            }
    
    # Count rows for progress tracking
    total_rows = count_csv_rows(decoded_content)
    progress = CSVImportProgress(total_rows=total_rows, callback=progress_callback)
    
    # Parse CSV
    csv_file_obj = io.StringIO(decoded_content)
    
    try:
        # Determine dialect for more accurate parsing
        dialect = csv.Sniffer().sniff(decoded_content[:1024])
        reader = csv.DictReader(csv_file_obj, dialect=dialect)
    except csv.Error:
        # Fall back to default dialect
        csv_file_obj.seek(0)
        reader = csv.DictReader(csv_file_obj)
    
    if not reader.fieldnames:
        return {
            "success": 0,
            "error": 1,
            "errors": ["CSV file has no headers"],
            "warnings": []
        }
    
    # Validate required fields
    if required_fields:
        missing_fields = validate_csv_headers(reader.fieldnames, required_fields)
        if missing_fields:
            return {
                "success": 0,
                "error": 1,
                "errors": [f"Missing required fields: {', '.join(missing_fields)}"],
                "warnings": []
            }
    
    # Clean field names (strip whitespace and handle case variations)
    cleaned_fieldnames = {field.strip().lower(): field for field in reader.fieldnames}
    
    # Process in batches with transactions
    batch = []
    batch_num = 0
    
    for i, row in enumerate(reader, start=1):
        # Normalize field names in the row
        normalized_row = {}
        for key, value in row.items():
            # Keep original field name but clean the value
            normalized_row[key] = value.strip() if isinstance(value, str) else value
        
        # Handle common variations of field names
        for clean_key, orig_key in cleaned_fieldnames.items():
            # For example, map "station_name", "stationname", "station name" to the same field
            key_variations = [
                clean_key.replace('_', ''),  # Remove underscores
                clean_key.replace('_', ' ')   # Underscores to spaces
            ]
            for alt_key in key_variations:
                if alt_key in normalized_row and orig_key not in normalized_row:
                    normalized_row[orig_key] = normalized_row.pop(alt_key)
        
        batch.append((normalized_row, i))
        
        # When batch is full or at end of file, process the batch
        if len(batch) >= batch_size:
            _process_batch(batch, row_processor, progress)
            batch = []
            batch_num += 1
            
            # Update progress after each batch
            logger.info(f"Processed batch {batch_num}: {progress.success_count} success, {progress.error_count} errors")
    
    # Process any remaining rows
    if batch:
        _process_batch(batch, row_processor, progress)
    
    # Return the final summary
    return progress.get_summary()


def _process_batch(batch: List[Tuple[Dict[str, str], int]], row_processor: Callable, progress: CSVImportProgress):
    """
    Process a batch of rows with transaction support
    
    Args:
        batch: List of (row dict, line number) tuples
        row_processor: Function to process each row
        progress: Progress tracker object
    """
    try:
        with transaction.atomic():
            for row, line_num in batch:
                try:
                    # Process the row and update progress
                    row_processor(row, line_num, progress)
                except CSVImportError as e:
                    # Specific CSV import errors
                    progress.error(e.message, row=e.row, line_num=e.line_num, field=e.field)
                except Exception as e:
                    # Unexpected errors
                    logger.exception(f"Error processing row at line {line_num}: {e}")
                    progress.error(str(e), row=row, line_num=line_num)
    except DatabaseError as e:
        # If the entire transaction fails
        for row, line_num in batch:
            progress.error(f"Database error: {str(e)}", row=row, line_num=line_num)


def validate_csv_headers(fieldnames: List[str], required_fields: List[str]) -> List[str]:
    """
    Validate that CSV headers contain required fields
    
    Args:
        fieldnames: List of header field names
        required_fields: List of required field names
        
    Returns:
        List of missing field names (empty if all present)
    """
    if not fieldnames:
        return ["No headers found in file"]
    
    # Clean and normalize field names for comparison
    clean_fieldnames = set(f.strip().lower() for f in fieldnames)
    
    # Handle special case for station fields - need one of the station identifier fields
    station_fields = ['station_id', 'station_name', 'station']
    if all(field in required_fields for field in station_fields):
        # If all station fields are listed as required, we only need one
        if any(field.lower() in clean_fieldnames for field in station_fields):
            # Remove station fields from required list for normal checking
            required_check = [f for f in required_fields if f not in station_fields]
        else:
            # Missing all station fields
            return [f"One of: {', '.join(station_fields)}"]
    else:
        required_check = required_fields
    
    # Check each required field
    missing_fields = []
    for field in required_check:
        # Try variations of the field name
        field_lower = field.lower()
        field_no_underscore = field_lower.replace('_', '')
        field_spaced = field_lower.replace('_', ' ')
        
        if (field_lower not in clean_fieldnames and 
            field_no_underscore not in clean_fieldnames and
            field_spaced not in clean_fieldnames):
            missing_fields.append(field)
    
    return missing_fields


def parse_numeric(value: Union[str, float, int], field_name: str, line_num: int, 
                 allow_none: bool = True, min_value: float = None, 
                 max_value: float = None) -> Optional[float]:
    """
    Parse numeric value with proper error handling and validation
    
    Args:
        value: Value to parse
        field_name: Name of the field (for error reporting)
        line_num: Line number (for error reporting)
        allow_none: Whether None is allowed for empty values
        min_value: Minimum allowed value (None for no minimum)
        max_value: Maximum allowed value (None for no maximum)
        
    Returns:
        Parsed float value or None if empty and allow_none is True
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if allow_none:
            return None
        raise CSVImportError(
            f"Missing required numeric value", 
            field=field_name, 
            line_num=line_num
        )
    
    # Handle numeric types directly
    if isinstance(value, (int, float)):
        numeric_value = float(value)
    else:
        try:
            # Handle string representation
            value_str = str(value).strip()
            # Handle special case with commas as decimal separator
            if ',' in value_str and '.' not in value_str:
                value_str = value_str.replace(',', '.')
            numeric_value = float(value_str)
        except (ValueError, TypeError):
            raise CSVImportError(
                f"Invalid numeric value '{value}'", 
                field=field_name, 
                line_num=line_num
            )
    
    # Validate range
    if min_value is not None and numeric_value < min_value:
        raise CSVImportError(
            f"Value {numeric_value} is below minimum {min_value}", 
            field=field_name, 
            line_num=line_num
        )
    
    if max_value is not None and numeric_value > max_value:
        raise CSVImportError(
            f"Value {numeric_value} is above maximum {max_value}", 
            field=field_name, 
            line_num=line_num
        )
    
    return numeric_value


def parse_date(value: Union[str, datetime, date], field_name: str, line_num: int, 
               formats: List[str] = None, allow_none: bool = True) -> Optional[datetime]:
    """
    Parse date value with multiple format attempts
    
    Args:
        value: Value to parse
        field_name: Name of the field (for error reporting)
        line_num: Line number (for error reporting)
        formats: List of date formats to try
        allow_none: Whether None is allowed for empty values
        
    Returns:
        Parsed datetime object or None if empty and allow_none is True
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if allow_none:
            return None
        raise CSVImportError(
            f"Missing required date value", 
            field=field_name, 
            line_num=line_num
        )
    
    # Handle case where value is already a datetime or date
    if isinstance(value, datetime):
        return value
    elif isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    
    # Handle string value
    formats = formats or [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y',
        '%Y%m%d',
    ]
    
    # First try dateutil parser which handles many formats
    try:
        return parser.parse(value)
    except (ValueError, TypeError):
        # Fall back to explicit formats
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    
    raise CSVImportError(
        f"Invalid date format '{value}'", 
        field=field_name,
        line_num=line_num
    )


def parse_boolean(value: Union[str, bool, int], field_name: str, line_num: int, 
                 default: bool = None) -> Optional[bool]:
    """
    Parse boolean value with proper error handling
    
    Args:
        value: Value to parse
        field_name: Name of the field (for error reporting)
        line_num: Line number (for error reporting)
        default: Default value if parsing fails
        
    Returns:
        Parsed boolean value or default
    """
    if isinstance(value, bool):
        return value
    
    if value is None or (isinstance(value, str) and not value.strip()):
        if default is not None:
            return default
        raise CSVImportError(
            f"Missing boolean value", 
            field=field_name, 
            line_num=line_num
        )
    
    if isinstance(value, int):
        return bool(value)
    
    # Handle string representations
    true_values = ['true', 'yes', 'y', 't', '1', 'on']
    false_values = ['false', 'no', 'n', 'f', '0', 'off']
    
    value_lower = str(value).lower().strip()
    
    if value_lower in true_values:
        return True
    elif value_lower in false_values:
        return False
    else:
        if default is not None:
            return default
        raise CSVImportError(
            f"Invalid boolean value '{value}'", 
            field=field_name, 
            line_num=line_num
        )


def find_station_by_identifier(identifier: str, field_name: str, line_num: int):
    """
    Find a weather station by various identifiers
    
    Args:
        identifier: Station identifier (name, id, or pk)
        field_name: Name of the field (for error reporting)
        line_num: Line number (for error reporting)
        
    Returns:
        WeatherStation object
    """
    from .models import WeatherStation
    
    if not identifier:
        raise CSVImportError(
            "Missing station identifier", 
            field=field_name, 
            line_num=line_num
        )
    
    # First try by station_id
    station = WeatherStation.objects.filter(station_id=identifier).first()
    
    if not station:
        # Then try by name
        station = WeatherStation.objects.filter(name=identifier).first()
        
    if not station and identifier.isdigit():
        # Finally try by ID if numeric
        station = WeatherStation.objects.filter(id=int(identifier)).first()
    
    if not station:
        raise CSVImportError(
            f"Station not found: {identifier}", 
            field=field_name, 
            line_num=line_num
        )
    
    return station


def get_station_from_row(row: Dict[str, str], line_num: int) -> Any:
    """
    Extract a station object from a CSV row
    
    Args:
        row: CSV row as dict
        line_num: Line number (for error reporting)
        
    Returns:
        WeatherStation object
    """
    # Find the station based on available identifiers
    station_id_fields = ['station_name', 'station_id', 'station']
    
    for field in station_id_fields:
        if field in row and row[field]:
            return find_station_by_identifier(row[field], field, line_num)
    
    raise CSVImportError(
        f"Missing station identifier (one of {', '.join(station_id_fields)} is required)",
        line_num=line_num
    )


def validate_column_values(row: Dict[str, str], validations: Dict[str, Dict], line_num: int, progress: CSVImportProgress):
    """
    Validate column values against specified criteria
    
    Args:
        row: CSV row as dict
        validations: Dictionary mapping field names to validation criteria
        line_num: Line number for error reporting
        progress: Progress tracker
    
    Returns:
        Dictionary of validated and transformed values
    """
    result = {}
    
    for field, criteria in validations.items():
        field_type = criteria.get('type', 'str')
        required = criteria.get('required', False)
        
        # Skip if field not present and not required
        if field not in row:
            if required:
                progress.error(f"Missing required field: {field}", row=row, line_num=line_num)
            continue
        
        value = row[field]
        
        # Skip empty values for optional fields
        if (value is None or (isinstance(value, str) and not value.strip())) and not required:
            continue
            
        try:
            if field_type == 'numeric':
                min_val = criteria.get('min')
                max_val = criteria.get('max')
                result[field] = parse_numeric(value, field, line_num, min_value=min_val, max_value=max_val)
            elif field_type == 'date':
                formats = criteria.get('formats')
                result[field] = parse_date(value, field, line_num, formats=formats)
            elif field_type == 'boolean':
                default = criteria.get('default')
                result[field] = parse_boolean(value, field, line_num, default=default)
            elif field_type == 'station':
                result[field] = find_station_by_identifier(value, field, line_num)
            else:
                # Default to string
                result[field] = value.strip() if isinstance(value, str) else value
        except CSVImportError as e:
            if required:
                # Re-raise for required fields
                raise
            else:
                # Just warn for optional fields
                progress.warning(e.message, row=row, line_num=line_num, field=field)
    
    return result
