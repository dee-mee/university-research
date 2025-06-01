"""
JSON Import utility for the Data Repository app

This module provides functions for handling JSON files in the data repository,
including metadata extraction, validation, and conversion to other formats.
"""
import json
import logging
import io
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)


class JSONImportError(Exception):
    """Custom exception for JSON import errors with detailed context"""
    def __init__(self, message, json_data=None, path=None, field=None):
        self.message = message
        self.json_data = json_data
        self.path = path
        self.field = field
        super().__init__(message)


def extract_json_metadata(file_obj, max_size=100000):
    """
    Extract metadata from a JSON file including:
    - Data structure type (object, array)
    - Keys in the root object
    - Value types
    - Time fields
    - Value fields (potential variables)
    - Sample data
    
    Args:
        file_obj: The file object to read
        max_size: Maximum bytes to read for large files
        
    Returns:
        Dict with extracted metadata
    """
    metadata = {
        'structure_type': None,
        'keys': [],
        'nested_objects': [],
        'time_fields': [],
        'value_fields': [],
        'data_types': {},
        'sample_data': None,
        'row_count': 0,
        'format': 'json'
    }
    
    # Remember current position
    current_position = file_obj.tell()
    
    try:
        # Read file content
        file_content = file_obj.read(max_size)
        file_obj.seek(current_position)  # Reset file pointer
        
        # Handle bytes vs string
        if isinstance(file_content, bytes):
            data_str = file_content.decode('utf-8', errors='replace')
        else:
            data_str = file_content
        
        # Parse JSON
        data = json.loads(data_str)
        metadata['sample_data'] = data
        
        # Determine structure type
        if isinstance(data, dict):
            metadata['structure_type'] = 'object'
            metadata['keys'] = list(data.keys())
            metadata['row_count'] = 1
            
            # Analyze each key
            for key, value in data.items():
                metadata['data_types'][key] = _determine_data_type(value)
                
                # Check if this is a time field
                if _is_likely_time_field(key, value):
                    metadata['time_fields'].append(key)
                
                # Check if this is a value field
                elif _is_likely_value_field(key, value):
                    metadata['value_fields'].append(key)
                
                # Check for nested objects
                if isinstance(value, dict):
                    metadata['nested_objects'].append(key)
                    
                # Check for arrays of data
                elif isinstance(value, list) and len(value) > 0:
                    if all(isinstance(item, (int, float)) for item in value):
                        metadata['value_fields'].append(key)
                    elif all(isinstance(item, dict) for item in value):
                        metadata['nested_objects'].append(key)
                        metadata['row_count'] = len(value)
                    
        elif isinstance(data, list):
            metadata['structure_type'] = 'array'
            metadata['row_count'] = len(data)
            
            # If we have array of objects, analyze the first few
            if data and all(isinstance(item, dict) for item in data[:10]):
                # Get keys from the first item
                if data[0]:
                    metadata['keys'] = list(data[0].keys())
                    
                    # Analyze each key based on the first few items
                    sample_size = min(len(data), 10)
                    for key in metadata['keys']:
                        # Get sample values for this key
                        values = [item.get(key) for item in data[:sample_size] if key in item]
                        
                        # Determine predominant data type
                        if values:
                            metadata['data_types'][key] = _determine_data_type(values[0])
                            
                            # Check if this is a time field
                            if any(_is_likely_time_field(key, value) for value in values):
                                metadata['time_fields'].append(key)
                            
                            # Check if this is a value field
                            elif any(_is_likely_value_field(key, value) for value in values):
                                metadata['value_fields'].append(key)
                            
                            # Check for nested objects
                            if any(isinstance(value, dict) for value in values):
                                metadata['nested_objects'].append(key)
        
        # Detect time series data structure
        if 'data' in metadata['keys'] and isinstance(data.get('data', {}), dict):
            data_obj = data.get('data', {})
            # Common time series pattern: {"data": {"variable1": {"times": [...], "values": [...]}, ...}}
            for var, contents in data_obj.items():
                if isinstance(contents, dict) and 'times' in contents and 'values' in contents:
                    if var not in metadata['value_fields']:
                        metadata['value_fields'].append(var)
                    metadata['time_fields'].append(f"data.{var}.times")
    
    except Exception as e:
        logger.error(f"Error extracting JSON metadata: {str(e)}")
        metadata['error'] = str(e)
    
    finally:
        # Reset file pointer to where it was
        file_obj.seek(current_position)
    
    return metadata


def json_to_csv(file_obj, time_field=None, value_fields=None):
    """
    Convert JSON data to CSV format
    
    Args:
        file_obj: The file object containing JSON data
        time_field: Key for the time field
        value_fields: List of keys for value fields
        
    Returns:
        String containing CSV data
    """
    # Remember current position
    current_position = file_obj.tell()
    
    try:
        content = file_obj.read()
        
        # Handle bytes vs string
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='replace')
        else:
            content_str = content
        
        # Parse JSON
        data = json.loads(content_str)
        
        # Extract metadata to determine structure
        metadata = extract_json_metadata(io.StringIO(content_str))
        
        # Initialize CSV output
        output = io.StringIO()
        import csv
        
        if metadata['structure_type'] == 'array' and metadata['keys']:
            # Handle array of objects - straightforward CSV conversion
            # Determine fields to include
            if not value_fields:
                value_fields = [k for k in metadata['keys'] if k != time_field]
            
            # Create CSV writer and write header
            writer = csv.writer(output)
            header = [time_field] if time_field else []
            header.extend(value_fields)
            writer.writerow(header)
            
            # Write rows
            for item in data:
                row = []
                if time_field:
                    row.append(item.get(time_field, ''))
                for field in value_fields:
                    row.append(item.get(field, ''))
                writer.writerow(row)
                
        elif metadata['structure_type'] == 'object' and 'data' in data:
            # Handle time series format: {"data": {"var1": {"times": [...], "values": [...]}, ...}}
            data_obj = data.get('data', {})
            
            # Determine structure and fields
            if isinstance(data_obj, dict):
                # Check if we have the time-series structure we expect
                has_time_series_structure = False
                time_values = []
                variables = {}
                
                for var, contents in data_obj.items():
                    if isinstance(contents, dict) and 'times' in contents and 'values' in contents:
                        has_time_series_structure = True
                        times = contents.get('times', [])
                        values = contents.get('values', [])
                        
                        if len(times) == len(values):
                            variables[var] = dict(zip(times, values))
                            # Keep track of all time points
                            time_values.extend(times)
                
                if has_time_series_structure:
                    # Get unique sorted time values
                    time_values = sorted(set(time_values))
                    
                    # Create CSV with time as first column and variables as additional columns
                    writer = csv.writer(output)
                    
                    # Write header
                    header = ['timestamp']
                    header.extend(sorted(variables.keys()))
                    writer.writerow(header)
                    
                    # Write data rows
                    for timestamp in time_values:
                        row = [timestamp]
                        for var in sorted(variables.keys()):
                            row.append(variables[var].get(timestamp, ''))
                        writer.writerow(row)
        
        return output.getvalue()
    
    except Exception as e:
        logger.error(f"Error converting JSON to CSV: {str(e)}")
        return ""
        
    finally:
        # Reset file pointer to where it was
        file_obj.seek(current_position)


def _determine_data_type(value):
    """Determine the data type of a value"""
    if value is None:
        return 'null'
    elif isinstance(value, bool):
        return 'boolean'
    elif isinstance(value, int):
        return 'integer'
    elif isinstance(value, float):
        return 'float'
    elif isinstance(value, str):
        # Check if string might be a date/time
        if _is_likely_date_string(value):
            return 'datetime'
        return 'string'
    elif isinstance(value, dict):
        return 'object'
    elif isinstance(value, list):
        if value and all(isinstance(item, (int, float)) for item in value):
            return 'numeric_array'
        elif value and all(isinstance(item, dict) for item in value):
            return 'object_array'
        else:
            return 'array'
    else:
        return 'unknown'


def _is_likely_time_field(key, value):
    """Check if a field is likely to contain time data"""
    time_keywords = ['time', 'date', 'timestamp', 'datetime', 'created', 'updated', 'period', 'year', 'month']
    
    # Check the key name first
    key_lower = key.lower()
    if any(keyword in key_lower for keyword in time_keywords):
        return True
    
    # Check if the value looks like a date string
    if isinstance(value, str) and _is_likely_date_string(value):
        return True
    
    return False


def _is_likely_date_string(value):
    """Check if a string is likely to be a date"""
    # Common date formats to check
    import re
    
    if not isinstance(value, str):
        return False
    
    # ISO-8601 date formats (YYYY-MM-DD, with or without time)
    iso_pattern = r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?'
    if re.match(iso_pattern, value):
        return True
    
    # Date with slashes (MM/DD/YYYY or DD/MM/YYYY)
    slash_pattern = r'\d{1,2}/\d{1,2}/\d{4}'
    if re.match(slash_pattern, value):
        return True
    
    # Try parsing with datetime
    try:
        from dateutil import parser
        parser.parse(value)
        return True
    except:
        return False
    
    return False


def _is_likely_value_field(key, value):
    """Check if a field is likely to contain numeric values of interest"""
    # These keywords often indicate measurement values
    value_keywords = ['temp', 'temperature', 'humidity', 'pressure', 'precipitation',
                     'wind', 'speed', 'value', 'measurement', 'reading', 'level',
                     'concentration', 'rate', 'amount', 'count', 'total']
    
    # Check the key name
    key_lower = key.lower()
    key_matches = any(keyword in key_lower for keyword in value_keywords)
    
    # Check the value type
    value_is_numeric = isinstance(value, (int, float))
    
    return key_matches or value_is_numeric


def process_json_file(json_file: UploadedFile, target_model, id_field=None):
    """
    Process JSON file and create or update model instances
    
    Args:
        json_file: The uploaded JSON file
        target_model: The Django model to create instances of
        id_field: Optional field to use for updating existing instances
        
    Returns:
        Dict with processing results
    """
    result = {
        'success': 0,
        'error': 0,
        'errors': [],
        'warnings': []
    }
    
    try:
        # Read and parse JSON
        content = json_file.read()
        
        # Handle bytes vs string
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='replace')
        else:
            content_str = content
        
        data = json.loads(content_str)
        
        # Detect structure
        if isinstance(data, list):
            # Process list of objects
            for index, item in enumerate(data):
                try:
                    if not isinstance(item, dict):
                        result['warnings'].append(f"Item {index} is not an object, skipping")
                        continue
                    
                    # If we have an ID field, check for existing instance
                    instance = None
                    if id_field and id_field in item:
                        try:
                            instance = target_model.objects.filter(**{id_field: item[id_field]}).first()
                        except:
                            result['warnings'].append(f"Failed to look up existing record with {id_field}={item[id_field]}")
                    
                    if instance:
                        # Update existing instance
                        for key, value in item.items():
                            setattr(instance, key, value)
                        instance.save()
                    else:
                        # Create new instance
                        instance = target_model.objects.create(**item)
                    
                    result['success'] += 1
                    
                except Exception as e:
                    result['error'] += 1
                    result['errors'].append(f"Error processing item {index}: {str(e)}")
        
        elif isinstance(data, dict):
            # Single object, create or update one instance
            try:
                # If we have an ID field, check for existing instance
                instance = None
                if id_field and id_field in data:
                    try:
                        instance = target_model.objects.filter(**{id_field: data[id_field]}).first()
                    except:
                        result['warnings'].append(f"Failed to look up existing record with {id_field}={data[id_field]}")
                
                if instance:
                    # Update existing instance
                    for key, value in data.items():
                        setattr(instance, key, value)
                    instance.save()
                else:
                    # Create new instance
                    instance = target_model.objects.create(**data)
                
                result['success'] += 1
                
            except Exception as e:
                result['error'] += 1
                result['errors'].append(f"Error processing JSON object: {str(e)}")
        
        else:
            result['error'] += 1
            result['errors'].append("Unsupported JSON format. Expected object or array of objects.")
    
    except json.JSONDecodeError as e:
        result['error'] += 1
        result['errors'].append(f"Invalid JSON format: {str(e)}")
    except Exception as e:
        result['error'] += 1
        result['errors'].append(f"Error processing JSON file: {str(e)}")
    
    return result