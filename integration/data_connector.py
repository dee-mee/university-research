"""
Data Connector Module for Research Portal

This module provides utilities to connect the data_repository and maps applications,
allowing for seamless data transfer, format conversion, and enhanced import/export capabilities.
"""
from django.db import transaction
from django.core.files.base import ContentFile
import json
import csv
import io
import logging
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional, Union

# Configure logger
logger = logging.getLogger(__name__)

class DataConnector:
    """Class that facilitates data transfer between apps"""
    
    @staticmethod
    def import_data(file_obj, file_format, target_app, model_name, id_field=None, 
                    mapping=None, convert=False, validate=True):
        """
        Import data from a file into a specific app's models
        
        Args:
            file_obj: File object to import
            file_format: 'csv' or 'json'
            target_app: 'maps' or 'data_repository'
            model_name: Name of the model to import data into
            id_field: Field to use for identifying existing records
            mapping: Optional dict mapping file fields to model fields
            convert: Whether to convert between formats if needed
            validate: Whether to validate data before import
            
        Returns:
            Dict with import results
        """
        result = {
            'success': 0,
            'error': 0,
            'errors': [],
            'warnings': []
        }
        
        # Save position to restore later
        original_position = file_obj.tell()
        
        try:
            # Convert format if needed
            if convert and file_format not in ('csv', 'json'):
                if file_format.lower() in ('xlsx', 'xls'):
                    # Convert Excel to CSV
                    file_obj, file_format = DataConnector._excel_to_csv(file_obj)
                else:
                    result['error'] += 1
                    result['errors'].append(f"Unsupported file format: {file_format}") 
                    return result
                    
            # Handle import based on target app
            if target_app == 'maps':
                return DataConnector._import_to_maps(
                    file_obj, file_format, model_name, id_field, mapping, validate)
            elif target_app == 'data_repository':
                return DataConnector._import_to_repository(
                    file_obj, file_format, model_name, id_field, mapping, validate)
            else:
                result['error'] += 1
                result['errors'].append(f"Unknown target app: {target_app}")
                return result
                
        except Exception as e:
            logger.exception(f"Error importing data: {str(e)}")
            result['error'] += 1
            result['errors'].append(f"Error importing data: {str(e)}")
            return result
        finally:
            # Restore original position
            file_obj.seek(original_position)
    
    @staticmethod
    def _import_to_maps(file_obj, file_format, model_name, id_field=None, mapping=None, validate=True):
        """Import data to maps app models"""
        # Import here to avoid circular imports
        from maps.models import WeatherStation, ClimateData, WeatherDataType, Country
        from maps.field_models import FieldDevice, DeviceType
        from maps.csv_utils import process_csv_in_batches
        
        # Map model names to actual models
        model_mapping = {
            'weather_station': WeatherStation,
            'climate_data': ClimateData,
            'weather_data_type': WeatherDataType,
            'country': Country,
            'field_device': FieldDevice,
            'device_type': DeviceType,
        }
        
        if model_name not in model_mapping:
            return {
                'success': 0,
                'error': 1,
                'errors': [f"Unknown model name for maps app: {model_name}"],
                'warnings': []
            }
        
        target_model = model_mapping[model_name]
        
        # Process based on file format
        if file_format == 'csv':
            # For CSV files, use the existing maps utilities
            if model_name == 'weather_station':
                from maps.utils import _process_station_row_enhanced
                
                def row_processor(row, line_num, progress):
                    return _process_station_row_enhanced(row, line_num, progress, 
                                                       update_existing=True, 
                                                       required_fields=['name'])
                
                return process_csv_in_batches(file_obj, row_processor, batch_size=100,
                                             required_fields=['name'])
                
            elif model_name == 'climate_data':
                from maps.utils import _process_climate_data_row_enhanced
                
                def row_processor(row, line_num, progress):
                    return _process_climate_data_row_enhanced(row, line_num, progress, 
                                                           update_existing=True, 
                                                           required_fields=['station', 'timestamp'])
                
                return process_csv_in_batches(file_obj, row_processor, batch_size=100,
                                             required_fields=['station', 'timestamp'])
            else:
                # Generic CSV processing for other models
                def row_processor(row, line_num, progress):
                    try:
                        # Apply field mapping if provided
                        if mapping:
                            mapped_row = {}
                            for file_field, model_field in mapping.items():
                                if file_field in row:
                                    mapped_row[model_field] = row[file_field]
                            row = mapped_row
                        
                        # Check for ID field to update existing
                        instance = None
                        if id_field and id_field in row:
                            try:
                                instance = target_model.objects.filter(**{id_field: row[id_field]}).first()
                            except:
                                pass
                        
                        if instance:
                            # Update existing
                            for key, value in row.items():
                                if hasattr(instance, key):
                                    setattr(instance, key, value)
                            instance.save()
                        else:
                            # Create new
                            instance = target_model.objects.create(**row)
                        
                        progress.success()
                        return instance
                    except Exception as e:
                        progress.error(str(e), row=row, line_num=line_num)
                        raise
                
                return process_csv_in_batches(file_obj, row_processor, batch_size=100)
                
        elif file_format == 'json':
            # Convert the JSON to CSV if needed for climate data or stations
            if model_name in ('climate_data', 'weather_station'):
                from data_repository.json_import import json_to_csv, extract_json_metadata
                
                # First extract metadata to determine structure
                metadata = extract_json_metadata(file_obj)
                
                # Reset position after metadata extraction
                file_obj.seek(0)
                
                # For these special cases, convert to CSV and process
                if metadata['structure_type']:
                    # Determine time field for CSV conversion
                    time_field = None
                    if metadata['time_fields']:
                        time_field = metadata['time_fields'][0]
                    
                    # Convert to CSV
                    csv_data = json_to_csv(file_obj, time_field, metadata['value_fields'])
                    if csv_data:
                        # Create a file-like object from the CSV string
                        csv_file = io.StringIO(csv_data)
                        csv_file.name = "converted.csv"  # Add a name attribute
                        
                        # Use the CSV processing function recursively
                        return DataConnector._import_to_maps(csv_file, 'csv', model_name, 
                                                           id_field, mapping, validate)
                
            # Generic JSON processing for other models
            file_obj.seek(0)  # Reset position
            try:
                # Read the file
                content = file_obj.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                
                # Parse the JSON
                data = json.loads(content)
                
                result = {
                    'success': 0,
                    'error': 0,
                    'errors': [],
                    'warnings': []
                }
                
                # Process based on structure
                if isinstance(data, list):
                    # Batch process with transactions for efficiency
                    for i in range(0, len(data), 100):
                        batch = data[i:i+100]
                        try:
                            with transaction.atomic():
                                for item in batch:
                                    # Apply field mapping if provided
                                    if mapping:
                                        mapped_item = {}
                                        for file_field, model_field in mapping.items():
                                            if file_field in item:
                                                mapped_item[model_field] = item[file_field]
                                        item = mapped_item
                                    
                                    # Check for ID field to update existing
                                    instance = None
                                    if id_field and id_field in item:
                                        try:
                                            instance = target_model.objects.filter(**{id_field: item[id_field]}).first()
                                        except:
                                            result['warnings'].append(f"Failed to look up existing record with {id_field}={item[id_field]}")
                                    
                                    if instance:
                                        # Update existing
                                        for key, value in item.items():
                                            if hasattr(instance, key):
                                                setattr(instance, key, value)
                                        instance.save()
                                    else:
                                        # Create new
                                        instance = target_model.objects.create(**item)
                                    
                                    result['success'] += 1
                        except Exception as e:
                            result['error'] += len(batch)
                            result['errors'].append(f"Error processing batch: {str(e)}")
                
                elif isinstance(data, dict):
                    # Process single object
                    try:
                        # Apply field mapping if provided
                        if mapping:
                            mapped_data = {}
                            for file_field, model_field in mapping.items():
                                if file_field in data:
                                    mapped_data[model_field] = data[file_field]
                            data = mapped_data
                        
                        # Check for ID field to update existing
                        instance = None
                        if id_field and id_field in data:
                            try:
                                instance = target_model.objects.filter(**{id_field: data[id_field]}).first()
                            except:
                                result['warnings'].append(f"Failed to look up existing record with {id_field}={data[id_field]}")
                        
                        if instance:
                            # Update existing
                            for key, value in data.items():
                                if hasattr(instance, key):
                                    setattr(instance, key, value)
                            instance.save()
                        else:
                            # Create new
                            instance = target_model.objects.create(**data)
                        
                        result['success'] += 1
                    except Exception as e:
                        result['error'] += 1
                        result['errors'].append(f"Error processing JSON object: {str(e)}")
                
                return result
                
            except json.JSONDecodeError as e:
                return {
                    'success': 0,
                    'error': 1,
                    'errors': [f"Invalid JSON format: {str(e)}"],
                    'warnings': []
                }
            except Exception as e:
                return {
                    'success': 0,
                    'error': 1,
                    'errors': [f"Error processing JSON file: {str(e)}"],
                    'warnings': []
                }
        
        else:
            return {
                'success': 0,
                'error': 1,
                'errors': [f"Unsupported file format for maps app: {file_format}"],
                'warnings': []
            }
    
    @staticmethod
    def _import_to_repository(file_obj, file_format, model_name, id_field=None, mapping=None, validate=True):
        """Import data to data_repository app models"""
        # Import here to avoid circular imports
        from data_repository.models import Dataset, DatasetVersion, DatasetCategory, StackedDataset
        
        # Map model names to actual models
        model_mapping = {
            'dataset': Dataset,
            'dataset_version': DatasetVersion,
            'dataset_category': DatasetCategory,
            'stacked_dataset': StackedDataset,
        }
        
        if model_name not in model_mapping:
            return {
                'success': 0,
                'error': 1,
                'errors': [f"Unknown model name for data_repository app: {model_name}"],
                'warnings': []
            }
        
        target_model = model_mapping[model_name]
        
        # Process based on file format
        if file_format == 'csv':
            from data_repository.csv_import import extract_csv_metadata
            
            # Extract metadata for better import handling
            metadata = None
            try:
                metadata = extract_csv_metadata(file_obj)
                file_obj.seek(0)  # Reset position after metadata extraction
            except Exception as e:
                logger.warning(f"Error extracting CSV metadata: {str(e)}")
            
            # Use a temporary file for clean processing
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_file:
                temp_path = temp_file.name
                # Copy the file content
                file_obj.seek(0)
                temp_file.write(file_obj.read())
            
            try:
                result = {
                    'success': 0,
                    'error': 0,
                    'errors': [],
                    'warnings': []
                }
                
                # Import based on model type
                if model_name == 'dataset':
                    # For datasets, we need to handle file paths and related fields
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            try:
                                # Apply field mapping if provided
                                if mapping:
                                    mapped_row = {}
                                    for file_field, model_field in mapping.items():
                                        if file_field in row:
                                            mapped_row[model_field] = row[file_field]
                                    row = mapped_row
                                
                                # Check for ID field to update existing
                                instance = None
                                if id_field and id_field in row:
                                    try:
                                        instance = target_model.objects.filter(**{id_field: row[id_field]}).first()
                                    except:
                                        result['warnings'].append(f"Failed to look up existing record with {id_field}={row[id_field]}")
                                
                                # Handle special fields
                                if 'category' in row and not isinstance(row['category'], DatasetCategory):
                                    # Try to find category by name or ID
                                    try:
                                        category_id = int(row['category'])
                                        row['category'] = DatasetCategory.objects.get(id=category_id)
                                    except (ValueError, DatasetCategory.DoesNotExist):
                                        # Try by name
                                        category = DatasetCategory.objects.filter(name=row['category']).first()
                                        if category:
                                            row['category'] = category
                                        else:
                                            # Create a new category
                                            from django.utils.text import slugify
                                            slug = slugify(row['category'])
                                            category = DatasetCategory.objects.create(
                                                name=row['category'],
                                                slug=slug
                                            )
                                            row['category'] = category
                                
                                # Handle metadata if it's a string
                                if 'metadata' in row and isinstance(row['metadata'], str):
                                    try:
                                        row['metadata'] = json.loads(row['metadata'])
                                    except:
                                        # Keep as string if not valid JSON
                                        pass
                                
                                if instance:
                                    # Update existing
                                    for key, value in row.items():
                                        if hasattr(instance, key):
                                            setattr(instance, key, value)
                                    instance.save()
                                else:
                                    # Create new
                                    instance = target_model.objects.create(**row)
                                
                                result['success'] += 1
                            except Exception as e:
                                result['error'] += 1
                                result['errors'].append(f"Error processing row: {str(e)}")
                
                else:
                    # Generic CSV processing for other models
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            try:
                                # Apply field mapping if provided
                                if mapping:
                                    mapped_row = {}
                                    for file_field, model_field in mapping.items():
                                        if file_field in row:
                                            mapped_row[model_field] = row[file_field]
                                    row = mapped_row
                                
                                # Check for ID field to update existing
                                instance = None
                                if id_field and id_field in row:
                                    try:
                                        instance = target_model.objects.filter(**{id_field: row[id_field]}).first()
                                    except:
                                        result['warnings'].append(f"Failed to look up existing record with {id_field}={row[id_field]}")
                                
                                if instance:
                                    # Update existing
                                    for key, value in row.items():
                                        if hasattr(instance, key):
                                            setattr(instance, key, value)
                                    instance.save()
                                else:
                                    # Create new
                                    instance = target_model.objects.create(**row)
                                
                                result['success'] += 1
                            except Exception as e:
                                result['error'] += 1
                                result['errors'].append(f"Error processing row: {str(e)}")
                
                return result
                
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        elif file_format == 'json':
            from data_repository.json_import import process_json_file, extract_json_metadata
            
            # Use the new json import utility for processing
            return process_json_file(file_obj, target_model, id_field)
            
        else:
            return {
                'success': 0,
                'error': 1,
                'errors': [f"Unsupported file format for data_repository app: {file_format}"],
                'warnings': []
            }
    
    @staticmethod
    def export_data(source_app, model_name, query_params=None, format='json', include_related=False):
        """
        Export data from a specific app's models
        
        Args:
            source_app: 'maps' or 'data_repository'
            model_name: Name of the model to export data from
            query_params: Optional dict of query parameters to filter data
            format: 'csv' or 'json'
            include_related: Whether to include related objects
            
        Returns:
            Tuple of (content, format, filename)
        """
        # Import here to avoid circular imports
        from django.core.serializers import serialize
        
        # Default values
        query_params = query_params or {}
        
        try:
            if source_app == 'maps':
                from maps.models import WeatherStation, ClimateData, WeatherDataType, Country
                from maps.field_models import FieldDevice, DeviceType
                
                # Map model names to actual models
                model_mapping = {
                    'weather_station': WeatherStation,
                    'climate_data': ClimateData,
                    'weather_data_type': WeatherDataType,
                    'country': Country,
                    'field_device': FieldDevice,
                    'device_type': DeviceType,
                }
                
                if model_name not in model_mapping:
                    return None, None, None
                
                model = model_mapping[model_name]
                queryset = model.objects.filter(**query_params)
                
                if model_name == 'weather_station' and format == 'geojson':
                    # Special handling for GeoJSON export of stations
                    features = []
                    for station in queryset:
                        features.append(station.to_representation())
                    
                    geojson = {
                        'type': 'FeatureCollection',
                        'features': features
                    }
                    
                    return json.dumps(geojson), 'json', f'stations_{datetime.now().strftime("%Y%m%d")}.geojson'
                
                elif model_name == 'climate_data' and format == 'csv':
                    # Special handling for CSV export of climate data
                    output = io.StringIO()
                    writer = csv.writer(output)
                    
                    # Write header
                    header = ['station', 'timestamp', 'year', 'month', 'season', 
                             'temperature', 'humidity', 'precipitation', 'air_quality_index', 
                             'wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover',
                             'soil_moisture', 'water_level', 'data_quality', 'uv_index']
                    writer.writerow(header)
                    
                    # Write data rows
                    for data in queryset:
                        row = [
                            data.station.name,
                            data.timestamp.isoformat(),
                            data.year,
                            data.month,
                            data.season,
                            data.temperature if data.temperature is not None else '',
                            data.humidity if data.humidity is not None else '',
                            data.precipitation if data.precipitation is not None else '',
                            data.air_quality_index if data.air_quality_index is not None else '',
                            data.wind_speed if data.wind_speed is not None else '',
                            data.wind_direction if data.wind_direction is not None else '',
                            data.barometric_pressure if data.barometric_pressure is not None else '',
                            data.cloud_cover if data.cloud_cover is not None else '',
                            data.soil_moisture if data.soil_moisture is not None else '',
                            data.water_level if data.water_level is not None else '',
                            data.data_quality,
                            data.uv_index if data.uv_index is not None else ''
                        ]
                        writer.writerow(row)
                    
                    return output.getvalue(), 'csv', f'climate_data_{datetime.now().strftime("%Y%m%d")}.csv'
                
                else:
                    # Default serialization
                    if format == 'csv':
                        # Convert to CSV
                        return DataConnector._queryset_to_csv(queryset), 'csv', f'{model_name}_{datetime.now().strftime("%Y%m%d")}.csv'
                    else:
                        # Use JSON serialization
                        fields = None  # All fields
                        if model_name == 'weather_station':
                            fields = ['id', 'name', 'station_id', 'description', 'latitude', 'longitude', 
                                     'altitude', 'country', 'region', 'is_active', 'date_installed', 
                                     'date_decommissioned', 'has_temperature', 'has_precipitation', 
                                     'has_humidity', 'has_wind', 'has_air_quality', 'has_soil_moisture', 
                                     'has_water_level']
                        
                        serialized = serialize('json', queryset, fields=fields, use_natural_foreign_keys=True)
                        return serialized, 'json', f'{model_name}_{datetime.now().strftime("%Y%m%d")}.json'
            
            elif source_app == 'data_repository':
                from data_repository.models import Dataset, DatasetVersion, DatasetCategory
                
                # Map model names to actual models
                model_mapping = {
                    'dataset': Dataset,
                    'dataset_version': DatasetVersion,
                    'dataset_category': DatasetCategory,
                }
                
                if model_name not in model_mapping:
                    return None, None, None
                
                model = model_mapping[model_name]
                queryset = model.objects.filter(**query_params)
                
                if format == 'csv':
                    # Convert to CSV
                    return DataConnector._queryset_to_csv(queryset), 'csv', f'{model_name}_{datetime.now().strftime("%Y%m%d")}.csv'
                else:
                    # Use JSON serialization
                    serialized = serialize('json', queryset, use_natural_foreign_keys=True)
                    return serialized, 'json', f'{model_name}_{datetime.now().strftime("%Y%m%d")}.json'
            
            else:
                return None, None, None
                
        except Exception as e:
            logger.exception(f"Error exporting data: {str(e)}")
            return None, None, None
    
    @staticmethod
    def sync_weather_data_to_repository(station_ids=None, time_range=None, include_field_data=True):
        """
        Synchronize weather data from maps app to data_repository
        
        Args:
            station_ids: Optional list of station IDs to sync
            time_range: Optional tuple of (start_date, end_date)
            include_field_data: Whether to include field device data
            
        Returns:
            Dict with sync results
        """
        result = {
            'datasets_created': 0,
            'datasets_updated': 0,
            'errors': []
        }
        
        try:
            # Import required models
            from maps.models import WeatherStation, ClimateData
            from data_repository.models import Dataset, DatasetVersion, DatasetCategory
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get a default admin user for attribution
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                result['errors'].append("No admin user found for dataset attribution")
                return result
            
            # Get or create Weather Data category
            category, _ = DatasetCategory.objects.get_or_create(
                name="Weather Data",
                defaults={
                    "description": "Weather and climate data from stations",
                    "slug": "weather-data"
                }
            )
            
            # Get stations to process
            stations_query = WeatherStation.objects.all()
            if station_ids:
                stations_query = stations_query.filter(id__in=station_ids)
            
            # Process each station
            for station in stations_query:
                try:
                    # Export station data to repository
                    dataset, created = station.export_to_repository(
                        title=f"Weather data from {station.name}",
                        description=f"Climate data collected from {station.name} weather station",
                        category_id=category.id,
                        creator_id=admin_user.id
                    )
                    
                    if created:
                        result['datasets_created'] += 1
                    else:
                        result['datasets_updated'] += 1
                        
                except Exception as e:
                    result['errors'].append(f"Error syncing station {station.id}: {str(e)}")
            
            return result
            
        except Exception as e:
            logger.exception(f"Error syncing weather data: {str(e)}")
            result['errors'].append(f"Error syncing weather data: {str(e)}")
            return result
    
    @staticmethod
    def _excel_to_csv(file_obj):
        """Convert Excel file to CSV format"""
        import pandas as pd
        
        # Save position to restore later
        original_position = file_obj.tell()
        
        try:
            # Read the Excel file
            df = pd.read_excel(file_obj)
            
            # Convert to CSV
            output = io.StringIO()
            df.to_csv(output, index=False)
            
            # Create a new file-like object from the CSV string
            csv_file = io.StringIO(output.getvalue())
            csv_file.name = file_obj.name.rsplit('.', 1)[0] + '.csv' if hasattr(file_obj, 'name') else 'converted.csv'
            
            return csv_file, 'csv'
            
        except Exception as e:
            logger.exception(f"Error converting Excel to CSV: {str(e)}")
            raise
        finally:
            # Restore original position
            file_obj.seek(original_position)
    
    @staticmethod
    def _queryset_to_csv(queryset):
        """Convert a queryset to CSV format"""
        if not queryset.exists():
            return ""
            
        # Get model fields
        model = queryset.model
        field_names = [field.name for field in model._meta.fields]
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(field_names)
        
        # Write data rows
        for obj in queryset:
            row = []
            for field in field_names:
                value = getattr(obj, field)
                # Handle special cases
                if isinstance(value, datetime):
                    value = value.isoformat()
                row.append(value)
            writer.writerow(row)
        
        return output.getvalue()


# Add standalone utility functions

def detect_file_format(file_obj):
    """
    Detect the format of a file based on content and extension
    
    Args:
        file_obj: File object to detect format for
        
    Returns:
        String with detected format ('csv', 'json', 'excel', etc.)
    """
    # Get file extension if available
    file_name = getattr(file_obj, 'name', '')
    extension = file_name.split('.')[-1].lower() if '.' in file_name else ''
    
    # Common extensions mapping
    if extension in ('csv', 'txt'):
        return 'csv'
    elif extension in ('json', 'geojson'):
        return 'json'
    elif extension in ('xlsx', 'xls'):
        return 'excel'
    
    # If no clear extension, try to detect from content
    # Save position to restore later
    original_position = file_obj.tell()
    
    try:
        # Read a sample of the file
        sample = file_obj.read(4096)
        file_obj.seek(original_position)
        
        # If it's bytes, try to decode
        if isinstance(sample, bytes):
            try:
                sample = sample.decode('utf-8')
            except UnicodeDecodeError:
                # Binary file - could be Excel
                import magic
                mime = magic.from_buffer(sample, mime=True)
                if 'excel' in mime or 'spreadsheet' in mime:
                    return 'excel'
                return 'binary'
        
        # Check for JSON format
        sample = sample.strip()
        if (sample.startswith('{') and sample.endswith('}')) or \
           (sample.startswith('[') and sample.endswith(']')):
            try:
                json.loads(sample)
                return 'json'
            except:
                pass
        
        # Check for CSV format
        if ',' in sample and '\n' in sample:
            lines = sample.split('\n')
            # CSV usually has similar number of commas per line
            comma_counts = [line.count(',') for line in lines[:5] if line]
            if comma_counts and all(c == comma_counts[0] for c in comma_counts):
                return 'csv'
        
        # If we can't determine, default to binary
        return 'unknown'
        
    except Exception as e:
        logger.exception(f"Error detecting file format: {str(e)}")
        return 'unknown'
    finally:
        # Restore original position
        file_obj.seek(original_position)


def convert_format(file_obj, source_format, target_format):
    """
    Convert a file from one format to another
    
    Args:
        file_obj: File object to convert
        source_format: Source format ('csv', 'json', 'excel')
        target_format: Target format ('csv', 'json')
        
    Returns:
        Tuple of (converted_file_obj, format)
    """
    if source_format == target_format:
        return file_obj, source_format
    
    # Different conversion paths
    if source_format == 'csv' and target_format == 'json':
        return _csv_to_json(file_obj), 'json'
    elif source_format == 'json' and target_format == 'csv':
        from data_repository.json_import import json_to_csv
        csv_content = json_to_csv(file_obj)
        csv_file = io.StringIO(csv_content)
        csv_file.name = file_obj.name.rsplit('.', 1)[0] + '.csv' if hasattr(file_obj, 'name') else 'converted.csv'
        return csv_file, 'csv'
    elif source_format == 'excel' and target_format in ('csv', 'json'):
        # Convert Excel to CSV first
        csv_file, _ = DataConnector._excel_to_csv(file_obj)
        
        # If target is JSON, convert CSV to JSON
        if target_format == 'json':
            return _csv_to_json(csv_file), 'json'
        else:
            return csv_file, 'csv'
    else:
        raise ValueError(f"Unsupported conversion from {source_format} to {target_format}")


def _csv_to_json(file_obj):
    """Convert CSV to JSON format"""
    # Save position to restore later
    original_position = file_obj.tell()
    
    try:
        # Read CSV content
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(content))
        data = list(reader)
        
        # Convert to JSON
        json_content = json.dumps(data, indent=2)
        
        # Create a new file-like object from the JSON string
        json_file = io.StringIO(json_content)
        json_file.name = file_obj.name.rsplit('.', 1)[0] + '.json' if hasattr(file_obj, 'name') else 'converted.json'
        
        return json_file
        
    except Exception as e:
        logger.exception(f"Error converting CSV to JSON: {str(e)}")
        raise
    finally:
        # Restore original position
        file_obj.seek(original_position)