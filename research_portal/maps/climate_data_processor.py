"""
Climate data processing utilities for improved data importing
"""
import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from django.db import transaction
from django.utils import timezone

from .models import WeatherStation, ClimateData
from .csv_utils import (
    CSVImportError, 
    parse_numeric, 
    parse_date, 
    find_station_by_identifier, 
    get_station_from_row, 
    validate_column_values,
    CSVImportProgress
)

logger = logging.getLogger(__name__)

# Field validation specs
CLIMATE_DATA_VALIDATIONS = {
    'temperature': {
        'type': 'numeric',
        'min': -100,
        'max': 100,
        'required': False,
    },
    'humidity': {
        'type': 'numeric',
        'min': 0,
        'max': 100,
        'required': False,
    },
    'precipitation': {
        'type': 'numeric',
        'min': 0,
        'max': 10000,  # Allow for extreme values
        'required': False,
    },
    'air_quality_index': {
        'type': 'numeric',
        'min': 0,
        'max': 500,
        'required': False,
    },
    'wind_speed': {
        'type': 'numeric',
        'min': 0,
        'max': 200,  # Allow for extreme weather events
        'required': False,
    },
    'wind_direction': {
        'type': 'numeric',
        'min': 0,
        'max': 360,
        'required': False,
    },
    'barometric_pressure': {
        'type': 'numeric',
        'min': 800,
        'max': 1200,
        'required': False,
    },
    'cloud_cover': {
        'type': 'numeric',
        'min': 0,
        'max': 100,
        'required': False,
    },
    'soil_moisture': {
        'type': 'numeric',
        'min': 0,
        'max': 100,
        'required': False,
    },
    'water_level': {
        'type': 'numeric',
        'min': -50,  # Allow for values below sea level
        'max': 100,
        'required': False,
    },
    'uv_index': {
        'type': 'numeric',
        'min': 0,
        'max': 12,
        'required': False,
    },
    'timestamp': {
        'type': 'date',
        'formats': ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%d/%m/%Y'],
        'required': True,
    },
    'data_quality': {
        'type': 'str',
        'required': False,
    },
}

def process_climate_data_row(row: Dict[str, str], line_num: int, progress: CSVImportProgress) -> Optional[ClimateData]:
    """
    Process a single row of climate data with enhanced validation
    
    Args:
        row: CSV row as dict
        line_num: Line number for error reporting
        progress: Progress tracker
    
    Returns:
        ClimateData object or None if processing fails
    """
    try:
        # Find the station
        station = get_station_from_row(row, line_num)
        
        # Parse timestamp
        timestamp = None
        if 'timestamp' in row and row['timestamp']:
            timestamp = parse_date(row['timestamp'], 'timestamp', line_num, allow_none=False)
        else:
            raise CSVImportError("Missing required timestamp field", row=row, line_num=line_num)
        
        # Validate numeric fields
        validated_data = validate_column_values(row, CLIMATE_DATA_VALIDATIONS, line_num, progress)
        
        # Set default data quality if not provided
        data_quality = validated_data.get('data_quality', 'medium')
        if data_quality not in ['high', 'medium', 'low', 'uncertain']:
            data_quality = 'medium'
            progress.warning(
                f"Invalid data quality value '{row.get('data_quality')}', using 'medium'", 
                row=row, line_num=line_num, field='data_quality'
            )
        
        # Set defaults for all data fields - None values will be excluded
        climate_data = {
            'station': station,
            'timestamp': timestamp,
            'data_quality': data_quality
        }
        
        # Add numeric fields if present in validated data
        for field in [
            'temperature', 'humidity', 'precipitation', 'air_quality_index',
            'wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover',
            'soil_moisture', 'water_level', 'uv_index'
        ]:
            if field in validated_data:
                climate_data[field] = validated_data[field]
        
        # Check if at least one measurement field is present
        measurement_fields = [
            'temperature', 'humidity', 'precipitation', 'air_quality_index',
            'wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover',
            'soil_moisture', 'water_level', 'uv_index'
        ]
        
        has_measurement = any(climate_data.get(field) is not None for field in measurement_fields)
        
        if not has_measurement:
            progress.warning(
                "No measurement fields found in row", 
                row=row, line_num=line_num
            )
            # Continue anyway, we might want to record the timestamp even without measurements
        
        # Check if record already exists for this station and timestamp
        existing = ClimateData.objects.filter(
            station=station,
            timestamp=timestamp
        ).first()
        
        if existing:
            # Update existing record with new data
            for key, value in climate_data.items():
                if key not in ['station', 'timestamp'] and value is not None:
                    setattr(existing, key, value)
            existing.save()
            return existing
        else:
            # Create new climate data record
            obj = ClimateData.objects.create(**climate_data)
            return obj
            
    except CSVImportError as e:
        # Re-raise to be caught by the batch processor
        raise
    except Exception as e:
        logger.exception(f"Unexpected error processing climate data row at line {line_num}")
        raise CSVImportError(str(e), row=row, line_num=line_num)


def process_climate_data_to_stack(row: Dict[str, str], line_num: int, progress: CSVImportProgress) -> bool:
    """
    Process a row of climate data and push it to the station's data stack
    
    Args:
        row: CSV row as dict
        line_num: Line number for error reporting
        progress: Progress tracker
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Find the station
        station = get_station_from_row(row, line_num)
        
        # Create data dictionary for the stack
        data_dict = {}
        
        # Add timestamp if present, otherwise use current time
        if 'timestamp' in row and row['timestamp']:
            try:
                timestamp = parse_date(row['timestamp'], 'timestamp', line_num, allow_none=False)
                data_dict['timestamp'] = timestamp.isoformat()
            except CSVImportError as e:
                progress.warning(e.message, row=row, line_num=line_num, field='timestamp')
                data_dict['timestamp'] = datetime.now().isoformat()
        else:
            data_dict['timestamp'] = datetime.now().isoformat()
        
        # Parse numeric fields
        numeric_fields = [
            'temperature', 'humidity', 'precipitation', 'air_quality_index',
            'wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover',
            'soil_moisture', 'water_level', 'uv_index'
        ]
        
        # Validate and add numeric fields
        has_data = False
        for field in numeric_fields:
            if field in row and row[field]:
                try:
                    value = parse_numeric(row[field], field, line_num)
                    if value is not None:
                        data_dict[field] = value
                        has_data = True
                except CSVImportError as e:
                    # Just warn for data stack import
                    progress.warning(e.message, row=row, line_num=line_num, field=field)
        
        # Add data quality if present
        if 'data_quality' in row and row['data_quality']:
            data_dict['data_quality'] = row['data_quality']
        
        # Check if we have any data to push
        if not has_data:
            progress.warning(
                "No valid measurement data found in row", 
                row=row, line_num=line_num
            )
            return False
            
        # Push data to station's stack
        success = station.push_data(data_dict)
        if not success:
            progress.warning(
                f"Failed to add data to stack for station {station.name}: Stack is full", 
                row=row, line_num=line_num
            )
            return False
            
        return True
        
    except CSVImportError as e:
        # Re-raise to be caught by the batch processor
        raise
    except Exception as e:
        logger.exception(f"Unexpected error processing climate data to stack at line {line_num}")
        raise CSVImportError(str(e), row=row, line_num=line_num)


def bulk_process_stacks(stations=None):
    """
    Process data stacks for all stations or specified stations
    
    Args:
        stations: List of WeatherStation objects or None for all stations
        
    Returns:
        Dictionary with processing results
    """
    if stations is None:
        # Get all stations with non-empty stacks
        stations = WeatherStation.objects.all()
    
    results = {
        'stations_processed': 0,
        'records_processed': 0,
        'errors': []
    }
    
    for station in stations:
        try:
            records = station.process_data_stack()
            if records > 0:
                results['stations_processed'] += 1
                results['records_processed'] += records
        except Exception as e:
            logger.exception(f"Error processing data stack for station {station.id}")
            results['errors'].append(f"Station {station.name}: {str(e)}")
    
    return results