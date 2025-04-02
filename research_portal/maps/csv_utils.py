import csv
import io
import logging
import chardet
import codecs
import time
from typing import Dict, List, Any, Tuple, Optional, Callable, Iterator
from django.db import transaction, DatabaseError
from django.core.files.uploadedfile import UploadedFile

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
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Process CSV file in batches with transaction support
    
    Args:
        csv_file: Django UploadedFile object
        row_processor: Function that processes each row
        batch_size: Number of rows to process in each transaction
        progress_callback: Function to call with progress updates
        
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
    
    # Process in batches with transactions
    batch = []
    batch_num = 0
    
    for i, row in enumerate(reader, start=1):
        batch.append((row, i))
        
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
        
    missing_fields = [field for field in required_fields if field not in fieldnames]
    return missing_fields


def parse_numeric(value: str, field_name: str, line_num: int, allow_none: bool = True) -> Optional[float]:
    """
    Parse numeric value with proper error handling
    
    Args:
        value: String value to parse
        field_name: Name of the field (for error reporting)
        line_num: Line number (for error reporting)
        allow_none: Whether None is allowed for empty values
        
    Returns:
        Parsed float value or None if empty and allow_none is True
    """
    if not value and allow_none:
        return None
        
    try:
        return float(value)
    except (ValueError, TypeError):
        raise CSVImportError(
            f"Invalid numeric value '{value}'", 
            field=field_name, 
            line_num=line_num
        )


def parse_date(value: str, field_name: str, line_num: int, 
               formats: List[str] = None, allow_none: bool = True) -> Optional[datetime]:
    """
    Parse date value with multiple format attempts
    
    Args:
        value: String value to parse
        field_name: Name of the field (for error reporting)
        line_num: Line number (for error reporting)
        formats: List of date formats to try
        allow_none: Whether None is allowed for empty values
        
    Returns:
        Parsed datetime object or None if empty and allow_none is True
    """
    from datetime import datetime
    from dateutil import parser
    
    if not value and allow_none:
        return None
    
    formats = formats or ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d']
    
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


def get_bool_value(value: str) -> bool:
    """
    Convert various string representations to boolean
    
    Args:
        value: String value to convert
        
    Returns:
        Boolean representation of the value
    """
    if isinstance(value, bool):
        return value
    
    if not value:
        return False
        
    return value.lower() in ('true', 'yes', '1', 't', 'y')
