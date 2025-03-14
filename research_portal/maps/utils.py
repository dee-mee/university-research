# utils.py
import os
import logging
import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.utils import timezone
from django.db.models import Avg, Max, Min, Sum, Count, Q
from dateutil import parser
import pytz
import csv
import io
from typing import Dict, List, Union, Optional, Tuple, Any

from .models import WeatherStation, ClimateData, DataExport

# Configure logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_WEATHER_API_KEY = getattr(settings, 'WEATHER_API_KEY', None)
DEFAULT_EMAIL_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@weatherstations.example.com')
CSV_DATETIME_FORMATS = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M:%S']


class WeatherDataException(Exception):
    """Custom exception for weather data operations"""
    pass


class AlertThresholdException(Exception):
    """Custom exception for alert threshold operations"""
    pass


# API Data Fetching Functions
def fetch_environmental_data(api_key: str = None) -> Dict[str, int]:
    """
    Fetches environmental data from external API for all active weather stations.
    
    Args:
        api_key: API key for weather service (defaults to settings.WEATHER_API_KEY)
    
    Returns:
        Dict with success and error counts
    """
    if not api_key:
        api_key = DEFAULT_WEATHER_API_KEY
        
    if not api_key:
        logger.error("No API key provided for weather data retrieval")
        raise WeatherDataException("API key is required")
    
    # Get all active weather stations
    stations = WeatherStation.objects.filter(is_active=True)
    
    if not stations.exists():
        logger.info("No active weather stations found")
        return {"success": 0, "error": 0}
    
    results = {"success": 0, "error": 0}
    
    for station in stations:
        try:
            # Construct API URL for OpenWeatherMap (can be replaced with any weather API)
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={station.latitude}&lon={station.longitude}&units=metric&appid={api_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch data for station {station.name}. Status code: {response.status_code}")
                results["error"] += 1
                continue
            
            data = response.json()
            
            # Map API response to ClimateData model fields
            climate_data = {
                'station': station,
                'timestamp': timezone.now(),
                'temperature': data.get('main', {}).get('temp'),
                'humidity': data.get('main', {}).get('humidity'),
                'wind_speed': data.get('wind', {}).get('speed'),
                'wind_direction': data.get('wind', {}).get('deg'),
                'barometric_pressure': data.get('main', {}).get('pressure'),
                'cloud_cover': data.get('clouds', {}).get('all'),
                'data_quality': 'high'  # Assuming API data is high quality
            }
            
            # Add precipitation if available
            if 'rain' in data and '1h' in data['rain']:
                climate_data['precipitation'] = data['rain']['1h']
            
            # Create new climate data entry
            ClimateData.objects.create(**climate_data)
            logger.info(f"Successfully fetched data for station {station.name}")
            results["success"] += 1
            
        except Exception as e:
            logger.error(f"Error fetching data for station {station.name}: {str(e)}")
            results["error"] += 1
    
    return results


def batch_fetch_environmental_data(api_key: str = None, batch_size: int = 10) -> Dict[str, int]:
    """
    Fetches environmental data in batches to avoid rate limiting
    
    Args:
        api_key: API key for weather service
        batch_size: Number of stations to process in each batch
        
    Returns:
        Dict with success and error counts
    """
    stations = WeatherStation.objects.filter(is_active=True)
    total_results = {"success": 0, "error": 0}
    
    # Process in batches
    for i in range(0, stations.count(), batch_size):
        batch = stations[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}")
        
        # Process each station in the batch
        for station in batch:
            try:
                # Call a single station fetch function
                result = fetch_station_data(station, api_key)
                if result:
                    total_results["success"] += 1
                else:
                    total_results["error"] += 1
            except Exception as e:
                logger.error(f"Error in batch processing for station {station.name}: {str(e)}")
                total_results["error"] += 1
        
        # Add a delay between batches to avoid rate limiting
        if i + batch_size < stations.count():
            import time
            time.sleep(1)  # 1 second delay between batches
    
    return total_results


def fetch_station_data(station: WeatherStation, api_key: str = None) -> bool:
    """
    Fetches data for a single weather station
    
    Args:
        station: WeatherStation object
        api_key: API key for weather service
        
    Returns:
        True if successful, False otherwise
    """
    if not api_key:
        api_key = DEFAULT_WEATHER_API_KEY
        
    try:
        # Construct API URL
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={station.latitude}&lon={station.longitude}&units=metric&appid={api_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch data for station {station.name}. Status code: {response.status_code}")
            return False
        
        data = response.json()
        
        # Map API response to ClimateData model fields
        climate_data = {
            'station': station,
            'timestamp': timezone.now(),
            'temperature': data.get('main', {}).get('temp'),
            'humidity': data.get('main', {}).get('humidity'),
            'wind_speed': data.get('wind', {}).get('speed'),
            'wind_direction': data.get('wind', {}).get('deg'),
            'barometric_pressure': data.get('main', {}).get('pressure'),
            'cloud_cover': data.get('clouds', {}).get('all'),
            'data_quality': 'high'
        }
        
        # Add precipitation if available
        if 'rain' in data and '1h' in data['rain']:
            climate_data['precipitation'] = data['rain']['1h']
        
        # Create new climate data entry
        ClimateData.objects.create(**climate_data)
        return True
        
    except Exception as e:
        logger.error(f"Error fetching data for station {station.name}: {str(e)}")
        return False


# Alert Functions
def check_alert_thresholds(alert_config: Dict = None, send_notifications: bool = True) -> Dict[str, int]:
    """
    Checks if the latest climate data exceeds alert thresholds
    
    Args:
        alert_config: Dictionary mapping field names to threshold values
        send_notifications: Whether to send email notifications
        
    Returns:
        Dict with counts of alerts triggered
    """
    if alert_config is None:
        # Default alert thresholds if none provided
        alert_config = {
            'temperature': {'max': 35.0, 'min': -10.0},
            'precipitation': {'max': 50.0},
            'wind_speed': {'max': 20.0},
            'air_quality_index': {'max': 150}
        }
    
    # Get the latest reading for each active station
    latest_data = []
    for station in WeatherStation.objects.filter(is_active=True):
        data = ClimateData.objects.filter(station=station).order_by('-timestamp').first()
        if data:
            latest_data.append(data)
    
    alerts_triggered = {"total": 0}
    
    for data in latest_data:
        station_alerts = []
        
        # Check each field against its threshold
        for field, thresholds in alert_config.items():
            value = getattr(data, field, None)
            if value is None:
                continue
            
            if 'max' in thresholds and value > thresholds['max']:
                alert = f"{field.replace('_', ' ').title()} is too high: {value}"
                station_alerts.append(alert)
                alerts_triggered[field + "_high"] = alerts_triggered.get(field + "_high", 0) + 1
            
            if 'min' in thresholds and value < thresholds['min']:
                alert = f"{field.replace('_', ' ').title()} is too low: {value}"
                station_alerts.append(alert)
                alerts_triggered[field + "_low"] = alerts_triggered.get(field + "_low", 0) + 1
        
        if station_alerts and send_notifications:
            try:
                # In a real app, you'd get this from a user preferences model
                recipient_email = "admin@example.com"
                subject = f"Weather Alert for {data.station.name}"
                message = (
                    f"The following alerts have been triggered for {data.station.name} "
                    f"at {data.timestamp.strftime('%Y-%m-%d %H:%M')}:\n\n"
                    f"{chr(10).join(station_alerts)}\n\n"
                    f"Please check the system for more details."
                )
                
                send_mail(
                    subject,
                    message,
                    DEFAULT_EMAIL_FROM,
                    [recipient_email],
                    fail_silently=False,
                )
                
                logger.info(f"Alert notification sent for station {data.station.name}")
            except Exception as e:
                logger.error(f"Failed to send alert notification: {str(e)}")
        
        alerts_triggered["total"] += len(station_alerts)
    
    return alerts_triggered


# Data Analysis Functions
def calculate_statistics(station_id: int = None, days: int = 30) -> Dict[str, Any]:
    """
    Calculate statistics for climate data
    
    Args:
        station_id: Optional filter for a specific station
        days: Number of days to include in statistics
        
    Returns:
        Dictionary of statistics
    """
    start_date = timezone.now() - timedelta(days=days)
    
    # Filter query based on parameters
    query = ClimateData.objects.filter(timestamp__gte=start_date)
    if station_id:
        query = query.filter(station_id=station_id)
    
    # Calculate overall statistics
    stats = query.aggregate(
        avg_temp=Avg('temperature'),
        max_temp=Max('temperature'),
        min_temp=Min('temperature'),
        avg_humidity=Avg('humidity'),
        total_precipitation=Sum('precipitation', default=0),
        avg_wind_speed=Avg('wind_speed'),
        max_wind_speed=Max('wind_speed'),
        avg_pressure=Avg('barometric_pressure'),
        max_uv=Max('uv_index'),
        data_count=Count('id')
    )
    
    # Add station count if no specific station was requested
    if not station_id:
        stats['station_count'] = query.values('station').distinct().count()
    
    # Calculate daily averages
    daily_data = query.extra({
        'date': "date(timestamp)"
    }).values('date').annotate(
        avg_temp=Avg('temperature'),
        total_precip=Sum('precipitation', default=0),
        avg_humidity=Avg('humidity')
    ).order_by('date')
    
    # Convert to list for serialization
    stats['daily_averages'] = list(daily_data)
    
    return stats


def detect_anomalies(station_id: int = None, days: int = 30, std_dev_threshold: float = 2.0) -> List[Dict]:
    """
    Detect anomalies in climate data using standard deviation
    
    Args:
        station_id: Optional filter for a specific station
        days: Number of days to analyze
        std_dev_threshold: Number of standard deviations to consider an anomaly
        
    Returns:
        List of anomalies detected
    """
    start_date = timezone.now() - timedelta(days=days)
    
    # Filter query based on parameters
    query = ClimateData.objects.filter(timestamp__gte=start_date)
    if station_id:
        query = query.filter(station_id=station_id)
    
    # Convert to pandas DataFrame for easier analysis
    data = list(query.values(
        'id', 'station__name', 'timestamp', 'temperature', 
        'humidity', 'precipitation', 'wind_speed'
    ))
    
    if not data:
        return []
    
    df = pd.DataFrame(data)
    anomalies = []
    
    # Analyze each numerical column
    for column in ['temperature', 'humidity', 'precipitation', 'wind_speed']:
        if column in df.columns:
            # Calculate mean and standard deviation
            mean = df[column].mean()
            std = df[column].std()
            
            if pd.isna(mean) or pd.isna(std) or std == 0:
                continue
            
            # Find values outside threshold
            outliers = df[abs(df[column] - mean) > std_dev_threshold * std]
            
            for _, row in outliers.iterrows():
                anomalies.append({
                    'id': row['id'],
                    'station': row['station__name'],
                    'timestamp': row['timestamp'],
                    'field': column,
                    'value': row[column],
                    'mean': mean,
                    'deviation': abs(row[column] - mean) / std
                })
    
    return sorted(anomalies, key=lambda x: x['deviation'], reverse=True)


# Data Import/Export Functions
def validate_csv_data(file_path: str, import_type: str) -> Dict[str, Any]:
    """
    Validates a CSV file before import
    
    Args:
        file_path: Path to CSV file
        import_type: 'stations' or 'climate_data'
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'row_count': 0,
        'fields': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # Check if file is empty
            first_line = file.readline().strip()
            if not first_line:
                results['errors'].append("File is empty")
                return results
            
            file.seek(0)  # Reset file pointer
            reader = csv.reader(file)
            header = next(reader)
            
            # Store fields found
            results['fields'] = header
            
            # Check required fields
            if import_type == 'stations':
                required_fields = ['name', 'latitude', 'longitude']
            else:  # climate_data
                required_fields = ['station_name', 'timestamp']
            
            for field in required_fields:
                if field not in header:
                    results['errors'].append(f"Missing required field: {field}")
            
            # Check for duplicate fields
            duplicates = set([x for x in header if header.count(x) > 1])
            if duplicates:
                results['errors'].append(f"Duplicate fields found: {', '.join(duplicates)}")
            
            # Count rows and check sample data
            row_count = 0
            for row in reader:
                row_count += 1
                
                # Check first few rows for obvious issues
                if row_count <= 5:
                    # Check row length
                    if len(row) != len(header):
                        results['warnings'].append(f"Row {row_count} has {len(row)} fields, expected {len(header)}")
                    
                    # For stations, check lat/lng validity
                    if import_type == 'stations' and 'latitude' in header and 'longitude' in header:
                        lat_idx = header.index('latitude')
                        lng_idx = header.index('longitude')
                        
                        if lat_idx < len(row) and lng_idx < len(row):
                            try:
                                lat = float(row[lat_idx])
                                lng = float(row[lng_idx])
                                
                                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                                    results['warnings'].append(
                                        f"Row {row_count} has invalid coordinates: {lat}, {lng}"
                                    )
                            except ValueError:
                                results['warnings'].append(
                                    f"Row {row_count} has non-numeric coordinates"
                                )
            
            results['row_count'] = row_count
            
            # Set validity based on errors
            results['valid'] = len(results['errors']) == 0
            
    except Exception as e:
        results['errors'].append(f"Error validating file: {str(e)}")
        results['valid'] = False
    
    return results


def process_csv_data(file_path: str, import_type: str, update_existing: bool = True) -> Dict[str, Any]:
    """
    Process a CSV file for import
    
    Args:
        file_path: Path to CSV file
        import_type: 'stations' or 'climate_data'
        update_existing: Whether to update existing records
        
    Returns:
        Dictionary with processing results
    """
    # First validate the file
    validation = validate_csv_data(file_path, import_type)
    
    if not validation['valid']:
        return {
            'success': 0,
            'error': 0,
            'errors': validation['errors'],
            'type': 'Weather Stations' if import_type == 'stations' else 'Climate Data'
        }
    
    # Process the file based on type
    if import_type == 'stations':
        processor = process_stations_csv
    else:  # climate_data
        processor = process_climate_data_csv
    
    # Create a file object
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    file_object = io.StringIO(file_content)
    file_object.name = os.path.basename(file_path)
    
    # Process the file
    return processor(file_object, update_existing)


def process_stations_csv(csv_file, update_existing: bool = True) -> Dict[str, Any]:
    """
    Process a CSV file containing weather station data
    
    Args:
        csv_file: File-like object containing CSV data
        update_existing: Whether to update existing records
        
    Returns:
        Dictionary with processing results
    """
    result = {
        'success': 0,
        'error': 0,
        'errors': [],
        'type': 'Weather Stations'
    }
    
    try:
        decoded_file = csv_file.read().decode('utf-8') if hasattr(csv_file, 'read') and not isinstance(csv_file.read(), str) else csv_file.read()
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        required_fields = ['name', 'latitude', 'longitude']
        
        # Check if required fields exist
        for field in required_fields:
            if field not in reader.fieldnames:
                result['errors'].append(f"Missing required field: {field}")
                return result
        
        for row in reader:
            try:
                # Check for required fields
                if not row['name'] or not row['latitude'] or not row['longitude']:
                    result['error'] += 1
                    result['errors'].append(f"Missing required data in row: {row}")
                    continue
                
                # Parse location
                try:
                    latitude = float(row['latitude'])
                    longitude = float(row['longitude'])
                    
                    # Validate coordinate range
                    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                        result['error'] += 1
                        result['errors'].append(f"Invalid coordinate range in row: {row}")
                        continue
                        
                    location = Point(longitude, latitude, srid=4326)
                except (ValueError, TypeError):
                    result['error'] += 1
                    result['errors'].append(f"Invalid coordinates in row: {row}")
                    continue
                
                # Parse date if present
                date_installed = None
                if 'date_installed' in row and row['date_installed']:
                    try:
                        date_installed = parser.parse(row['date_installed']).date()
                    except ValueError:
                        # Try common date formats
                        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                            try:
                                date_installed = datetime.strptime(row['date_installed'], fmt).date()
                                break
                            except ValueError:
                                continue
                
                # Parse altitude if present
                altitude = None
                if 'altitude' in row and row['altitude']:
                    try:
                        altitude = float(row['altitude'])
                    except ValueError:
                        # Skip invalid altitude
                        pass
                
                # Parse is_active if present
                is_active = True
                if 'is_active' in row and row['is_active']:
                    is_active = row['is_active'].lower() in ('true', 'yes', '1', 't', 'y')
                
                # Create or update the station
                defaults = {
                    'location': location,
                    'description': row.get('description', ''),
                    'altitude': altitude,
                    'is_active': is_active,
                }
                
                if date_installed:
                    defaults['date_installed'] = date_installed
                
                if update_existing:
                    station, created = WeatherStation.objects.update_or_create(
                        name=row['name'],
                        defaults=defaults
                    )
                else:
                    # Only create if doesn't exist
                    if not WeatherStation.objects.filter(name=row['name']).exists():
                        station = WeatherStation.objects.create(
                            name=row['name'],
                            **defaults
                        )
                        created = True
                    else:
                        result['error'] += 1
                        result['errors'].append(f"Station already exists: {row['name']}")
                        continue
                
                result['success'] += 1
                
            except Exception as e:
                result['error'] += 1
                result['errors'].append(f"Error processing row: {row}. Error: {str(e)}")
        
    except Exception as e:
        result['errors'].append(f"Error processing file: {str(e)}")
    
    return result


def process_climate_data_csv(csv_file, update_existing: bool = True) -> Dict[str, Any]:
    """
    Process a CSV file containing climate data
    
    Args:
        csv_file: File-like object containing CSV data
        update_existing: Whether to update existing records
        
    Returns:
        Dictionary with processing results
    """
    result = {
        'success': 0,
        'error': 0,
        'errors': [],
        'type': 'Climate Data'
    }
    
    try:
        decoded_file = csv_file.read().decode('utf-8') if hasattr(csv_file, 'read') and not isinstance(csv_file.read(), str) else csv_file.read()
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        required_fields = ['station_name', 'timestamp']
        
        # Check if required fields exist
        for field in required_fields:
            if field not in reader.fieldnames:
                result['errors'].append(f"Missing required field: {field}")
                return result
        
        # Get timezone for timestamps
        timezone_name = getattr(settings, 'TIME_ZONE', 'UTC')
        timezone_obj = pytz.timezone(timezone_name)
        
        for row in reader:
            try:
                # Check for required fields
                if not row['station_name'] or not row['timestamp']:
                    result['error'] += 1
                    result['errors'].append(f"Missing required data in row: {row}")
                    continue
                
                # Find the station
                try:
                    station = WeatherStation.objects.get(name=row['station_name'])
                except WeatherStation.DoesNotExist:
                    result['error'] += 1
                    result['errors'].append(f"Station not found: {row['station_name']}")
                    continue
                
                # Parse timestamp with multiple formats
                timestamp = None
                try:
                    # Try dateutil parser first
                    timestamp = parser.parse(row['timestamp'])
                except ValueError:
                    # Try common formats
                    for fmt in CSV_DATETIME_FORMATS:
                        try:
                            timestamp = datetime.strptime(row['timestamp'], fmt)
                            break
                        except ValueError:
                            continue
                
                if timestamp is None:
                    result['error'] += 1
                    result['errors'].append(f"Invalid timestamp format in row: {row}")
                    continue
                
                # Add timezone if missing
                if timestamp.tzinfo is None:
                    timestamp = timezone_obj.localize(timestamp)
                
                # Create climate data dictionary with defaults
                climate_data = {
                    'station': station,
                    'timestamp': timestamp,
                    'data_quality': row.get('data_quality', 'medium'),
                }
                
                # Map numeric fields with proper conversion
                numeric_fields = [
                    'temperature', 'humidity', 'precipitation', 'air_quality_index',
                    'wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover',
                    'soil_moisture', 'water_level', 'uv_index'
                ]
                
                for field in numeric_fields:
                    if field in row and row[field]:
                        try:
                            climate_data[field] = float(row[field])
                        except ValueError:
                            # Skip this field if conversion fails
                            pass
                
                # Create or update the climate data
                if update_existing:
                    data, created = ClimateData.objects.update_or_create(
                        station=station,
                        timestamp=timestamp,
                        defaults=climate_data
                    )
                else:
                    # Check if data already exists
                    if not ClimateData.objects.filter(station=station, timestamp=timestamp).exists():
                        data = ClimateData.objects.create(**climate_data)
                    else:
                        result['error'] += 1
                        result['errors'].append(f"Data already exists for {station.name} at {timestamp}")
                        continue
                
                result['success'] += 1
                
            except Exception as e:
                result['error'] += 1
                result['errors'].append(f"Error processing row: {row}. Error: {str(e)}")
        
    except Exception as e:
        result['errors'].append(f"Error processing file: {str(e)}")
    
    return result


def export_data_to_csv(station_id: Optional[int] = None, 
                       start_date: Optional[datetime] = None, 
                       end_date: Optional[datetime] = None,
                       user=None) -> Tuple[str, io.StringIO]:
    """
    Export climate data to CSV
    
    Args:
        station_id: Optional filter for specific station
        start_date: Start date for data range
        end_date: End date for data range
        user: User performing the export (for logging)
        
    Returns:
        Tuple of (filename, csv_file_object)
    """
    # Set default dates if not provided
    if end_date is None:
        end_date = timezone.now()
    if start_date is None:
        start_date = end_date - timedelta(days=7)
    
    # Build query
    query = ClimateData.objects.filter(timestamp__gte=start_date, timestamp__lte=end_date)
    if station_id:
        query = query.filter(station_id=station_id)
    
    query = query.select_related('station').order_by('-timestamp')
    
    # Create CSV file
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerow([
        'Station', 'Timestamp', 'Temperature', 'Humidity', 'Precipitation', 
        'Air Quality Index', 'Wind Speed', 'Wind Direction', 'Barometric Pressure',
        'Cloud Cover', 'Soil Moisture', 'Water Level', 'Data Quality', 'UV Index',
        'Station Latitude', 'Station Longitude'
    ])
    
    for data in query:
        writer.writerow([
            data.station.name,
            data.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            data.temperature,
            data.humidity,
            data.precipitation,
            data.air_quality_index,
            data.wind_speed,
            data.wind_direction,
            data.barometric_pressure,
            data.cloud_cover,
            data.soil_moisture,
            data.water_level,
            data.data_quality,
            data.uv_index,
            data.station.latitude,
            data.station.longitude
        ])
    
    # Log the export if user is provided
    if user and user.is_authenticated:
        station = WeatherStation.objects.get(id=station_id) if station_id else None
        DataExport.objects.create(
            user=user,
            station=station,
            export_format='csv',
            date_from=start_date,
            date_to=end_date
        )
    
    # Generate filename
    if station_id:
        station = WeatherStation.objects.get(id=station_id)
        filename = f"{station.name.replace(' ', '_')}_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
    else:
        filename = f"all_stations_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
    
    # Reset file pointer to beginning
    csv_file.seek(0)
    
    return filename, csv_file


# Geospatial Functions
def find_nearest_stations(latitude: float, longitude: float, radius_km: float = 10.0, 
                         limit: int = 5, only_active: bool = True) -> List[Dict]:
    """
    Find weather stations near a given point
    
    Args:
        latitude: Latitude of the point
        longitude: Longitude"""

def check_alert_thresholds():
    """
    Utility function to check all active alert thresholds
    and notify users if thresholds are exceeded.
    This could be run as a scheduled task.
    """
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from .models import AlertThreshold
    
    # Get all active alert thresholds
    thresholds = AlertThreshold.objects.filter(active=True)
    
    for threshold in thresholds:
        # Get the latest environmental data for this marker
        try:
            latest_data = threshold.marker.environmental_data.latest()
            
            # Get the value to check
            metric_value = getattr(latest_data, threshold.metric, None)
            
            if metric_value is not None:
                # Check if threshold is exceeded
                threshold_exceeded = False
                
                if threshold.condition == 'gt' and metric_value > threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'lt' and metric_value < threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'eq' and metric_value == threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'gte' and metric_value >= threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'lte' and metric_value <= threshold.value:
                    threshold_exceeded = True
                
                if threshold_exceeded:
                    # Notify the user (here we'll just email)
                    user_email = threshold.user.email
                    condition_display = threshold.get_condition_display()
                    metric_display = threshold.get_metric_display()
                    
                    if user_email:
                        message = f"""
                        Alert Notification
                        
                        Your alert threshold for {threshold.marker.name} has been triggered.
                        
                        {metric_display} is now {metric_value}, which is {condition_display} your threshold of {threshold.value}.
                        
                        Timestamp: {latest_data.timestamp}
                        
                        You can view more details on the map at {settings.BASE_URL}/markers/{threshold.marker.id}/
                        """
                        
                        send_mail(
                            f'Environmental Alert: {threshold.marker.name}',
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [user_email],
                            fail_silently=True,
                        )
                        
                        logger.info(f"Alert sent to {threshold.user.username} for {threshold.marker.name}")
        
        except Exception as e:
            logger.error(f"Error checking threshold {threshold.id}: {str(e)}")
    
    logger.info("Alert threshold check complete")