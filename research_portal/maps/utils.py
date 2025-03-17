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
from django.utils import timezone
from django.db.models import Avg, Max, Min, Sum, Count, Q
from dateutil import parser
import pytz
import csv
import io
import time
from typing import Dict, List, Union, Optional, Tuple, Any

from .models import WeatherStation, ClimateData, DataExport, WeatherAlert, AlertThreshold

# Configure logger
logger = logging.getLogger(__name__)

# ----------------------
# Constants
# ----------------------
DEFAULT_WEATHER_API_KEY = getattr(settings, 'WEATHER_API_KEY', None)
DEFAULT_EMAIL_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@weatherstations.example.com')
CSV_DATETIME_FORMATS = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M:%S']
BASE_URL = getattr(settings, 'BASE_URL', 'http://localhost:8000')

# Default alert thresholds
DEFAULT_ALERT_THRESHOLDS = {
    'temperature': {'max': 35.0, 'min': -10.0},
    'precipitation': {'max': 50.0},
    'wind_speed': {'max': 20.0},
    'air_quality_index': {'max': 150}
}

# Alert severity thresholds
ALERT_SEVERITY_THRESHOLDS = {
    'temperature': {
        'danger_high': 40.0,  # °C
        'warning_high': 35.0,
        'warning_low': 0.0,
        'danger_low': -10.0,
    },
    'precipitation': {
        'warning': 25.0,  # mm in an hour
        'danger': 50.0,
    },
    'wind_speed': {
        'warning': 20.0,  # m/s
        'danger': 30.0,
    },
    'air_quality_index': {
        'warning': 150,
        'danger': 300,
    }
}

# ----------------------
# Custom Exceptions
# ----------------------
class WeatherDataException(Exception):
    """Custom exception for weather data operations"""
    pass


class AlertThresholdException(Exception):
    """Custom exception for alert threshold operations"""
    pass


# ----------------------
# API Data Fetching Functions
# ----------------------
def fetch_environmental_data(api_key: str = None) -> Dict[str, int]:
    """
    Fetches environmental data from external API for all active weather stations.
    
    Args:
        api_key: API key for weather service (defaults to settings.WEATHER_API_KEY)
    
    Returns:
        Dict with success and error counts
    """
    api_key = api_key or DEFAULT_WEATHER_API_KEY
    if not api_key:
        logger.error("No API key provided for weather data retrieval")
        raise WeatherDataException("API key is required")
    
    stations = WeatherStation.objects.filter(is_active=True)
    if not stations.exists():
        logger.info("No active weather stations found")
        return {"success": 0, "error": 0}
    
    return _process_stations_data(stations, api_key)


def batch_fetch_environmental_data(api_key: str = None, batch_size: int = 10, delay: int = 1) -> Dict[str, int]:
    """
    Fetches environmental data in batches to avoid rate limiting
    
    Args:
        api_key: API key for weather service
        batch_size: Number of stations to process in each batch
        delay: Delay between batches in seconds
        
    Returns:
        Dict with success and error counts
    """
    stations = WeatherStation.objects.filter(is_active=True)
    return _process_stations_data_in_batches(stations, api_key, batch_size, delay)


def fetch_station_data(station: WeatherStation, api_key: str = None) -> bool:
    """
    Fetches data for a single weather station
    
    Args:
        station: WeatherStation object
        api_key: API key for weather service
        
    Returns:
        True if successful, False otherwise
    """
    api_key = api_key or DEFAULT_WEATHER_API_KEY
    if not api_key:
        logger.error("No API key provided for weather data retrieval")
        return False
    
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={station.latitude}&lon={station.longitude}&units=metric&appid={api_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch data for station {station.name}. Status code: {response.status_code}")
            return False
        
        data = response.json()
        climate_data = _map_api_response_to_climate_data(station, data)
        
        climate_data_obj = ClimateData.objects.create(**climate_data)
        process_alerts_for_data(climate_data_obj)
        
        logger.info(f"Successfully fetched data for station {station.name}")
        return True
    
    except Exception as e:
        logger.error(f"Error fetching data for station {station.name}: {str(e)}")
        return False


def _process_stations_data(stations, api_key):
    results = {"success": 0, "error": 0}
    for station in stations:
        if fetch_station_data(station, api_key):
            results["success"] += 1
        else:
            results["error"] += 1
    return results


def _process_stations_data_in_batches(stations, api_key, batch_size, delay):
    total_results = {"success": 0, "error": 0}
    for i in range(0, stations.count(), batch_size):
        batch = stations[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}")
        
        for station in batch:
            try:
                if fetch_station_data(station, api_key):
                    total_results["success"] += 1
                else:
                    total_results["error"] += 1
            except Exception as e:
                logger.error(f"Error in batch processing for station {station.name}: {str(e)}")
                total_results["error"] += 1
        
        if i + batch_size < stations.count():
            time.sleep(delay)
    
    return total_results


def _map_api_response_to_climate_data(station, data):
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
    
    if 'rain' in data and '1h' in data['rain']:
        climate_data['precipitation'] = data['rain']['1h']
    
    return climate_data


# ----------------------
# Alert Functions
# ----------------------
def check_alert_thresholds(alert_config: Dict = None, send_notifications: bool = True) -> Dict[str, int]:
    """
    Checks if the latest climate data exceeds alert thresholds
    
    Args:
        alert_config: Dictionary mapping field names to threshold values
        send_notifications: Whether to send email notifications
        
    Returns:
        Dict with counts of alerts triggered
    """
    alert_config = alert_config or DEFAULT_ALERT_THRESHOLDS
    latest_data = ClimateData.objects.filter(
        station__in=WeatherStation.objects.filter(is_active=True)
    ).order_by('station', '-timestamp').distinct('station')
    
    alerts_triggered = {"total": 0}
    for data in latest_data:
        station_alerts = _evaluate_alerts(data, alert_config)
        if station_alerts and send_notifications:
            send_alert_email(data.station, station_alerts, data.timestamp)
        alerts_triggered["total"] += len(station_alerts)
    
    return alerts_triggered


def check_for_alerts(climate_data: ClimateData) -> List[Dict]:
    """
    Check a climate data point against alert thresholds
    
    Args:
        climate_data: ClimateData object to check
        
    Returns:
        List of alert dictionaries
    """
    alerts = []
    for parameter, thresholds in ALERT_SEVERITY_THRESHOLDS.items():
        value = getattr(climate_data, parameter, None)
        if value is not None:
            alerts.extend(_evaluate_parameter_alerts(parameter, value, thresholds))
    
    return alerts


def create_alert_from_detection(station: WeatherStation, alert_data: Dict) -> WeatherAlert:
    """
    Create an alert record from detection data
    
    Args:
        station: Weather station object
        alert_data: Alert data dictionary
        
    Returns:
        Created WeatherAlert object
    """
    alert = WeatherAlert(
        station=station,
        title=alert_data['title'],
        description=alert_data['description'],
        parameter=alert_data['parameter'],
        threshold_value=alert_data['threshold'],
        current_value=alert_data['value'],
        severity=alert_data['severity']
    )
    alert.save()
    
    return alert


def _evaluate_alerts(data, alert_config):
    alerts = []
    for field, thresholds in alert_config.items():
        value = getattr(data, field, None)
        if value is not None:
            if 'max' in thresholds and value > thresholds['max']:
                alerts.append(f"{field.replace('_', ' ').title()} is too high: {value}")
            if 'min' in thresholds and value < thresholds['min']:
                alerts.append(f"{field.replace('_', ' ').title()} is too low: {value}")
    return alerts


def _evaluate_parameter_alerts(parameter, value, thresholds):
    alerts = []
    if 'danger_high' in thresholds and value >= thresholds['danger_high']:
        alerts.append(_create_alert_dict(parameter, value, thresholds['danger_high'], 'danger', 'Extreme High'))
    elif 'warning_high' in thresholds and value >= thresholds['warning_high']:
        alerts.append(_create_alert_dict(parameter, value, thresholds['warning_high'], 'warning', 'High'))
    elif 'danger_low' in thresholds and value <= thresholds['danger_low']:
        alerts.append(_create_alert_dict(parameter, value, thresholds['danger_low'], 'danger', 'Extreme Low'))
    elif 'warning_low' in thresholds and value <= thresholds['warning_low']:
        alerts.append(_create_alert_dict(parameter, value, thresholds['warning_low'], 'warning', 'Low'))
    return alerts


def _create_alert_dict(parameter, value, threshold, severity, level):
    return {
        'parameter': parameter,
        'value': value,
        'threshold': threshold,
        'severity': severity,
        'title': f'{level} {parameter.replace("_", " ").title()}',
        'description': f'{parameter.replace("_", " ").title()} of {value} exceeds {level.lower()} threshold of {threshold}.'
    }


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
    query = ClimateData.objects.filter(timestamp__gte=start_date)
    if station_id:
        query = query.filter(station_id=station_id)
    
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
    
    if not station_id:
        stats['station_count'] = query.values('station').distinct().count()
    
    daily_data = query.extra({
        'date': "date(timestamp)"
    }).values('date').annotate(
        avg_temp=Avg('temperature'),
        total_precip=Sum('precipitation', default=0),
        avg_humidity=Avg('humidity')
    ).order_by('date')
    
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
    query = ClimateData.objects.filter(timestamp__gte=start_date)
    if station_id:
        query = query.filter(station_id=station_id)
    
    data = list(query.values(
        'id', 'station__name', 'timestamp', 'temperature', 
        'humidity', 'precipitation', 'wind_speed'
    ))
    
    if not data:
        return []
    
    df = pd.DataFrame(data)
    anomalies = []
    
    for column in ['temperature', 'humidity', 'precipitation', 'wind_speed']:
        if column in df.columns:
            mean = df[column].mean()
            std = df[column].std()
            
            if pd.isna(mean) or pd.isna(std) or std == 0:
                continue
            
            outliers = df[abs(df[column] - mean) > std_dev_threshold * std]
            anomalies.extend(_create_anomaly_dicts(outliers, column, mean, std))
    
    return sorted(anomalies, key=lambda x: x['deviation'], reverse=True)


def _create_anomaly_dicts(outliers, column, mean, std):
    anomalies = []
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
    return anomalies


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
            first_line = file.readline().strip()
            if not first_line:
                results['errors'].append("File is empty")
                return results
            
            file.seek(0)
            reader = csv.reader(file)
            header = next(reader)
            results['fields'] = header
            
            required_fields = ['name', 'latitude', 'longitude'] if import_type == 'stations' else ['station_name', 'timestamp']
            results = _validate_csv_headers(header, required_fields, results)
            
            row_count, warnings = _validate_csv_rows(reader, header, import_type)
            results['row_count'] = row_count
            results['warnings'].extend(warnings)
            results['valid'] = len(results['errors']) == 0
            
    except Exception as e:
        results['errors'].append(f"Error validating file: {str(e)}")
    
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
    validation = validate_csv_data(file_path, import_type)
    if not validation['valid']:
        return {
            'success': 0,
            'error': 0,
            'errors': validation['errors'],
            'type': 'Weather Stations' if import_type == 'stations' else 'Climate Data'
        }
    
    processor = process_stations_csv if import_type == 'stations' else process_climate_data_csv
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    file_object = io.StringIO(file_content)
    file_object.name = os.path.basename(file_path)
    
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
    return _process_csv(csv_file, update_existing, _process_station_row, 'Weather Stations', ['name', 'latitude', 'longitude'])


def process_climate_data_csv(csv_file, update_existing: bool = True) -> Dict[str, Any]:
    """
    Process a CSV file containing climate data
    
    Args:
        csv_file: File-like object containing CSV data
        update_existing: Whether to update existing records
        
    Returns:
        Dictionary with processing results
    """
    return _process_csv(csv_file, update_existing, _process_climate_data_row, 'Climate Data', ['station_name', 'timestamp'])


def _process_csv(csv_file, update_existing, row_processor, data_type, required_fields):
    result = {
        'success': 0,
        'error': 0,
        'errors': [],
        'type': data_type
    }
    
      
    try:
        decoded_file = csv_file.read().decode('utf-8') if hasattr(csv_file, 'read') and not isinstance(csv_file.read(), str) else csv_file.read()
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        for row in reader:
            try:
                row_processor(row, result, update_existing, required_fields)
            except Exception as e:
                result['error'] += 1
                result['errors'].append(f"Error processing row: {row}. Error: {str(e)}")
        
    except Exception as e:
        result['errors'].append(f"Error processing file: {str(e)}")
    
    return result


def _validate_csv_headers(header, required_fields, results):
    for field in required_fields:
        if field not in header:
            results['errors'].append(f"Missing required field: {field}")
    
    duplicates = set([x for x in header if header.count(x) > 1])
    if duplicates:
        results['errors'].append(f"Duplicate fields found: {', '.join(duplicates)}")
    
    return results


def _validate_csv_rows(reader, header, import_type):
    row_count = 0
    warnings = []
    for row in reader:
        row_count += 1
        
        if row_count <= 5 and len(row) != len(header):
            warnings.append(f"Row {row_count} has {len(row)} fields, expected {len(header)}")
        
        if import_type == 'stations' and 'latitude' in header and 'longitude' in header:
            lat_idx = header.index('latitude')
            lng_idx = header.index('longitude')
            
            if lat_idx < len(row) and lng_idx < len(row):
                try:
                    lat = float(row[lat_idx])
                    lng = float(row[lng_idx])
                    
                    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                        warnings.append(f"Row {row_count} has invalid coordinates: {lat}, {lng}")
                except ValueError:
                    warnings.append(f"Row {row_count} has non-numeric coordinates")
    
    return row_count, warnings


def _process_station_row(row, result, update_existing, required_fields):
    if any(not row[field] for field in required_fields):
        result['error'] += 1
        result['errors'].append(f"Missing required data in row: {row}")
        return
    
    location = _parse_location(row, result)
    if not location:
        return
    
    date_installed = _parse_date_installed(row)
    altitude = _parse_altitude(row)
    is_active = _parse_is_active(row)
    
    defaults = {
        'location': location,
        'description': row.get('description', ''),
        'altitude': altitude,
        'is_active': is_active,
    }
    
    if date_installed:
        defaults['date_installed'] = date_installed
    
    if update_existing:
        WeatherStation.objects.update_or_create(
            name=row['name'],
            defaults=defaults
        )
    else:
        if not WeatherStation.objects.filter(name=row['name']).exists():
            WeatherStation.objects.create(name=row['name'], **defaults)
        else:
            result['error'] += 1
            result['errors'].append(f"Station already exists: {row['name']}")
            return
    
    result['success'] += 1


def _parse_location(row, result):
    try:
        latitude = float(row['latitude'])
        longitude = float(row['longitude'])
        
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            result['error'] += 1
            result['errors'].append(f"Invalid coordinate range in row: {row}")
            return None
        
        return Point(longitude, latitude, srid=4326)
    except (ValueError, TypeError):
        result['error'] += 1
        result['errors'].append(f"Invalid coordinates in row: {row}")
        return None


def _parse_date_installed(row):
    if 'date_installed' in row and row['date_installed']:
        try:
            return parser.parse(row['date_installed']).date()
        except ValueError:
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                try:
                    return datetime.strptime(row['date_installed'], fmt).date()
                except ValueError:
                    continue
    return None


def _parse_altitude(row):
    if 'altitude' in row and row['altitude']:
        try:
            return float(row['altitude'])
        except ValueError:
            pass
    return None


def _parse_is_active(row):
    if 'is_active' in row and row['is_active']:
        return row['is_active'].lower() in ('true', 'yes', '1', 't', 'y')
    return True


def _process_climate_data_row(row, result, update_existing, required_fields):
    if any(not row[field] for field in required_fields):
        result['error'] += 1
        result['errors'].append(f"Missing required data in row: {row}")
        return
    
    try:
        station = WeatherStation.objects.get(name=row['station_name'])
    except WeatherStation.DoesNotExist:
        result['error'] += 1
        result['errors'].append(f"Station not found: {row['station_name']}")
        return
    
    timestamp = _parse_timestamp(row, result)
    if not timestamp:
        return
    
    climate_data = {
        'station': station,
        'timestamp': timestamp,
        'data_quality': row.get('data_quality', 'medium'),
    }
    
    _map_numeric_fields(row, climate_data)
    
    if update_existing:
        ClimateData.objects.update_or_create(
            station=station,
            timestamp=timestamp,
            defaults=climate_data
        )
    else:
        if not ClimateData.objects.filter(station=station, timestamp=timestamp).exists():
            ClimateData.objects.create(**climate_data)
        else:
            result['error'] += 1
            result['errors'].append(f"Data already exists for {station.name} at {timestamp}")
            return
    
    result['success'] += 1


def _parse_timestamp(row, result):
    for fmt in CSV_DATETIME_FORMATS:
        try:
            timestamp = datetime.strptime(row['timestamp'], fmt)
            if timestamp.tzinfo is None:
                timezone_name = getattr(settings, 'TIME_ZONE', 'UTC')
                timezone_obj = pytz.timezone(timezone_name)
                timestamp = timezone_obj.localize(timestamp)
            return timestamp
        except ValueError:
            continue
    
    result['error'] += 1
    result['errors'].append(f"Invalid timestamp format in row: {row}")
    return None


def _map_numeric_fields(row, climate_data):
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
                pass


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
    start_date = start_date or timezone.now() - timedelta(days=7)
    end_date = end_date or timezone.now()
    
    query = ClimateData.objects.filter(timestamp__gte=start_date, timestamp__lte=end_date)
    if station_id:
        query = query.filter(station_id=station_id)
    
    query = query.select_related('station').order_by('-timestamp')
    
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
    
    if user and user.is_authenticated:
        station = WeatherStation.objects.get(id=station_id) if station_id else None
        DataExport.objects.create(
            user=user,
            station=station,
            export_format='csv',
            date_from=start_date,
            date_to=end_date
        )
    
    filename = f"{station.name.replace(' ', '_')}_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv" if station_id else f"all_stations_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
    csv_file.seek(0)
    
    return filename, csv_file


# Geospatial Functions
def find_nearest_stations(latitude: float, longitude: float, radius_km: float = 10.0, 
                         limit: int = 5, only_active: bool = True) -> List[Dict]:
    """
    Find weather stations near a given point
    
    Args:
        latitude: Latitude of the point
        longitude: Longitude of the point
        radius_km: Search radius in kilometers
        limit: Maximum number of stations to return
        only_active: Whether to include only active stations
        
    Returns:
        List of dictionaries containing station information
    """
    point = Point(longitude, latitude, srid=4326)
    stations = WeatherStation.objects.filter(
        location__distance_lte=(point, D(km=radius_km))
    ).annotate(distance=Distance('location', point)).order_by('distance')
    
    if only_active:
        stations = stations.filter(is_active=True)
    
    return stations[:limit].values('id', 'name', 'latitude', 'longitude', 'distance')


# Alert Notification Functions
def send_alert_notifications(alert: WeatherAlert):
    """Send notifications for an alert based on its settings"""
    if alert.notify_email:
        send_email_notification(alert)
    
    if alert.notify_sms:
        send_sms_notification(alert)
    
    if alert.notify_push:
        send_push_notification(alert)


def send_email_notification(alert: WeatherAlert):
    """Send email notification about an alert"""
    subject = f"Weather Alert: {alert.title} at {alert.station.name}"
    message = f"""
    {alert.description}
    
    Station: {alert.station.name}
    Parameter: {alert.parameter}
    Current Value: {alert.threshold_value}
    Severity: {alert.get_severity_display()}
    Timestamp: {alert.created_at}
    
    View more details in the weather monitoring system.
    """
    
    recipient_list = settings.ALERT_EMAIL_RECIPIENTS
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)


def send_sms_notification(alert: WeatherAlert):
    """Send SMS notification about an alert"""
    # Implement SMS sending logic here
    pass


def send_push_notification(alert: WeatherAlert):
    """Send push notification about an alert"""
    # Implement push notification logic here
    pass


def setup_alert_checks(check_interval=300):
    """Set up scheduled checks for alert conditions"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        
        def check_task():
            stations = WeatherStation.objects.filter(is_active=True)
            for station in stations:
                latest = ClimateData.objects.filter(station=station).order_by('-timestamp').first()
                if latest:
                    alerts = check_for_alerts(latest)
                    for alert_data in alerts:
                        alert = create_alert_from_detection(station, alert_data)
                        send_alert_notifications(alert)
        
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            check_task,
            trigger=IntervalTrigger(seconds=check_interval),
            id='alert_check_job',
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Scheduled alert checks every {check_interval} seconds")
        
    except ImportError:
        logger.warning("APScheduler not installed. Automated alert checks will not run.")