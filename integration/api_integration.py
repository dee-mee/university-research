"""
API Integration Module for Maps and Data Repository

This module provides unified access to data across both the Maps and Data Repository
components of the research portal. It serves as a bridge to enable seamless
integration between geographical data visualization and dataset management.
"""
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

def fetch_integrated_data(station_id=None, dataset_id=None, time_range=None):
    """
    Fetch integrated data from both maps and repository sources
    
    Args:
        station_id (int): ID of a weather station to fetch data for
        dataset_id (int): ID of a dataset to fetch data for
        time_range (tuple): Optional (start_date, end_date) tuple to filter by time
        
    Returns:
        dict: Dictionary containing integrated data from both systems
    """
    result = {
        "station_data": None,
        "repository_datasets": [],
        "visualization_options": []
    }
    
    # Get station data if provided
    if station_id:
        from maps.models import WeatherStation, ClimateData
        try:
            station = WeatherStation.objects.get(id=station_id)
            
            # Prepare query for climate data
            climate_query = ClimateData.objects.filter(station=station)
            
            # Apply time range filter if provided
            if time_range and len(time_range) == 2:
                start_date, end_date = time_range
                climate_query = climate_query.filter(timestamp__range=(start_date, end_date))
            else:
                # Default to last 30 days
                end_date = timezone.now()
                start_date = end_date - timedelta(days=30)
                climate_query = climate_query.filter(timestamp__range=(start_date, end_date))
            
            # Get recent climate data, ordered by timestamp
            recent_data = climate_query.order_by('-timestamp')[:100]
            
            result["station_data"] = {
                "info": {
                    "id": station.id,
                    "name": station.name,
                    "station_id": station.station_id,
                    "location": {
                        "latitude": station.latitude,
                        "longitude": station.longitude,
                        "altitude": station.altitude
                    },
                    "country": station.country.name if station.country else None,
                    "region": station.region,
                    "is_active": station.is_active,
                    "date_installed": station.date_installed,
                    "available_data_types": station.available_data_types()
                },
                "recent_data": [{
                    "timestamp": data.timestamp,
                    "temperature": data.temperature,
                    "humidity": data.humidity,
                    "precipitation": data.precipitation,
                    "wind_speed": data.wind_speed,
                    "wind_direction": data.wind_direction,
                    "barometric_pressure": data.barometric_pressure,
                    "data_quality": data.data_quality
                } for data in recent_data]
            }
            
            # Get statistics for each available data type
            stats = {}
            for data_type in station.available_data_types():
                if hasattr(ClimateData, data_type):
                    # Skip if this data type doesn't exist in the model
                    continue
                    
                # Get aggregated statistics for this data type
                agg_data = climate_query.filter(**{f"{data_type}__isnull": False}).aggregate(
                    min=models.Min(data_type),
                    max=models.Max(data_type),
                    avg=models.Avg(data_type)
                )
                
                if agg_data['min'] is not None:
                    stats[data_type] = agg_data
            
            result["station_data"]["statistics"] = stats
            
        except WeatherStation.DoesNotExist:
            pass
    
    # Get repository data if provided
    if dataset_id:
        from data_repository.models import Dataset, DatasetVersion
        try:
            dataset = Dataset.objects.get(id=dataset_id)
            latest_version = DatasetVersion.objects.filter(
                dataset=dataset
            ).order_by('-version_number').first()
            
            result["repository_datasets"].append({
                "id": dataset.id,
                "title": dataset.title,
                "description": dataset.description,
                "category": dataset.category.name,
                "created_at": dataset.created_at,
                "status": dataset.status,
                "metadata": dataset.metadata,
                "latest_version": {
                    "version_number": latest_version.version_number if latest_version else None,
                    "created_at": latest_version.created_at if latest_version else None,
                    "file_url": latest_version.file_path.url if latest_version and latest_version.file_path else None,
                    "metadata": latest_version.metadata if latest_version else {}
                },
                "spatial_info": {
                    "has_location": dataset.location is not None,
                    "has_bounding_box": dataset.bounding_box is not None,
                    "location": {
                        "latitude": dataset.location.y if dataset.location else None,
                        "longitude": dataset.location.x if dataset.location else None
                    } if dataset.location else None
                },
                "url": dataset.get_absolute_url()
            })
        except Dataset.DoesNotExist:
            pass
    
    # Get all related datasets if station provided but no dataset
    if station_id and not dataset_id:
        from data_repository.models import Dataset
        try:
            station = WeatherStation.objects.get(id=station_id)
            datasets = list(station.datasets.all())
            
            for dataset in datasets:
                from data_repository.models import DatasetVersion
                latest_version = DatasetVersion.objects.filter(
                    dataset=dataset
                ).order_by('-version_number').first()
                
                result["repository_datasets"].append({
                    "id": dataset.id,
                    "title": dataset.title,
                    "description": dataset.description,
                    "category": dataset.category.name,
                    "created_at": dataset.created_at,
                    "status": dataset.status,
                    "metadata": dataset.metadata,
                    "latest_version": {
                        "version_number": latest_version.version_number if latest_version else None,
                        "created_at": latest_version.created_at if latest_version else None,
                        "file_url": latest_version.file_path.url if latest_version and latest_version.file_path else None,
                        "metadata": latest_version.metadata if latest_version else {}
                    },
                    "spatial_info": {
                        "has_location": dataset.location is not None,
                        "has_bounding_box": dataset.bounding_box is not None,
                        "location": {
                            "latitude": dataset.location.y if dataset.location else None,
                            "longitude": dataset.location.x if dataset.location else None
                        } if dataset.location else None
                    },
                    "url": dataset.get_absolute_url()
                })
        except WeatherStation.DoesNotExist:
            pass
    
    # Determine appropriate visualization options based on available data
    visualizations = []
    
    # If we have station data with geolocation, suggest map visualization
    if result["station_data"] and result["station_data"]["info"]["location"]["latitude"]:
        visualizations.append({
            "type": "map_markers",
            "title": "Map View",
            "description": "Display stations and data on a geographical map",
        })
    
    # If we have time series climate data, suggest line chart
    if result["station_data"] and result["station_data"]["recent_data"]:
        data_types = []
        for data_type in ["temperature", "humidity", "precipitation", "wind_speed"]:
            if any(data[data_type] is not None for data in result["station_data"]["recent_data"]):
                data_types.append(data_type)
        
        if data_types:
            visualizations.append({
                "type": "time_series_chart",
                "title": "Time Series Chart",
                "description": "Display data as a line chart over time",
                "available_data_types": data_types
            })
    
    # If we have repository datasets with time series data, suggest charts
    has_time_series_data = False
    for dataset in result["repository_datasets"]:
        if dataset["latest_version"]["metadata"].get("time_series"):
            has_time_series_data = True
            break
    
    if has_time_series_data:
        visualizations.append({
            "type": "dataset_time_series",
            "title": "Dataset Time Series",
            "description": "Display dataset values as a time series chart"
        })
    
    result["visualization_options"] = visualizations
    
    return result


def unified_search(query_string):
    """
    Search across both maps and repository components
    
    Args:
        query_string (str): Search query text
        
    Returns:
        dict: Search results from different components
    """
    results = {
        'stations': [],
        'devices': [],
        'datasets': [],
        'climate_data': []
    }
    
    # Search weather stations
    from maps.models import WeatherStation
    station_results = WeatherStation.objects.filter(
        Q(name__icontains=query_string) | 
        Q(description__icontains=query_string) |
        Q(station_id__icontains=query_string)
    ).values('id', 'name', 'station_id', 'is_active', 'country__name', 'region')
    
    results['stations'] = list(station_results)
    
    # Search field devices (if available)
    try:
        from maps.field_models import FieldDevice
        device_results = FieldDevice.objects.filter(
            Q(name__icontains=query_string) | 
            Q(device_id__icontains=query_string) |
            Q(notes__icontains=query_string)
        ).values('id', 'name', 'device_id', 'status', 'device_type__name')
        
        results['devices'] = list(device_results)
    except (ImportError, ModuleNotFoundError):
        # Field devices might not be available
        pass
    
    # Search repository datasets
    from data_repository.models import Dataset
    dataset_results = Dataset.objects.filter(
        Q(title__icontains=query_string) |
        Q(description__icontains=query_string) |
        Q(category__name__icontains=query_string)
    ).values('id', 'title', 'status', 'category__name', 'created_by__username', 'created_at')
    
    results['datasets'] = list(dataset_results)
    
    # Search climate data if we have specific measurements to find
    try:
        # Only search climate data if the query looks like a specific measurement value
        import re
        if re.match(r"^-?\d+(\.\d+)?$", query_string.strip()):
            # Might be a specific value (temperature, etc.)
            value = float(query_string.strip())
            
            from maps.models import ClimateData
            climate_results = ClimateData.objects.filter(
                Q(temperature=value) |
                Q(humidity=value) | 
                Q(precipitation=value) |
                Q(wind_speed=value) |
                Q(barometric_pressure=value)
            ).values(
                'id', 'station__name', 'timestamp', 'temperature', 
                'humidity', 'precipitation', 'wind_speed'
            )[:50]  # Limit results
            
            results['climate_data'] = list(climate_results)
    except (ValueError, TypeError):
        # Not a number, skip climate data search
        pass
    
    return results


def get_datasets_by_station(station_id):
    """
    Get all datasets associated with a specific weather station
    
    Args:
        station_id (int): ID of the weather station
        
    Returns:
        list: List of dictionaries containing dataset information
    """
    from maps.models import WeatherStation
    
    try:
        station = WeatherStation.objects.get(id=station_id)
        datasets = station.datasets.all().select_related('category', 'created_by')
        
        result = []
        for dataset in datasets:
            result.append({
                'id': dataset.id,
                'title': dataset.title,
                'description': dataset.description,
                'category': dataset.category.name,
                'created_by': dataset.created_by.username,
                'created_at': dataset.created_at,
                'status': dataset.status,
                'url': dataset.get_absolute_url(),
                'is_featured': dataset.is_featured
            })
        
        return result
    except WeatherStation.DoesNotExist:
        return []


def get_stations_by_dataset(dataset_id):
    """
    Get all weather stations associated with a specific dataset
    
    Args:
        dataset_id (int): ID of the dataset
        
    Returns:
        list: List of dictionaries containing station information
    """
    from data_repository.models import Dataset
    
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        stations = dataset.weather_stations.all().select_related('country')
        
        result = []
        for station in stations:
            result.append({
                'id': station.id,
                'name': station.name,
                'station_id': station.station_id,
                'description': station.description,
                'country': station.country.name if station.country else None,
                'region': station.region,
                'is_active': station.is_active,
                'data_types': station.available_data_types(),
                'location': {
                    'latitude': station.latitude,
                    'longitude': station.longitude,
                    'altitude': station.altitude
                }
            })
        
        return result
    except Dataset.DoesNotExist:
        return []


def process_station_data_to_repository(station_id, time_range=None, creator_id=None, title=None, description=None, category_id=None):
    """
    Process station data into repository dataset
    
    Args:
        station_id (int): ID of the weather station to process data from
        time_range (tuple): Optional (start_date, end_date) tuple to filter data
        creator_id (int): User ID of creator (uses current user if None)
        title (str): Title for the dataset (generates from station name if None)
        description (str): Description for the dataset (generates from station info if None)
        category_id (int): Category ID for the dataset
        
    Returns:
        tuple: (dataset, created) where created is True if a new dataset was created
    """
    from maps.models import WeatherStation
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        station = WeatherStation.objects.get(id=station_id)
        
        # Set default creator if not provided
        if not creator_id:
            creator = User.objects.filter(is_superuser=True).first()
            if not creator:
                return None, False, "No default creator found"
        else:
            try:
                creator = User.objects.get(id=creator_id)
            except User.DoesNotExist:
                return None, False, "Creator not found"
        
        # Set default title if not provided
        if not title:
            title = f"Weather data from {station.name}"
        
        # Set default description if not provided
        if not description:
            description = (f"Automatically processed climate data from station {station.name}. "
                        f"Contains data for {', '.join(station.available_data_types())}.")
        
        # Get or create category if not provided
        from data_repository.models import DatasetCategory
        if not category_id:
            category, _ = DatasetCategory.objects.get_or_create(
                name="Weather Data",
                defaults={
                    "description": "Weather and climate data from stations",
                    "slug": "weather-data"
                }
            )
        else:
            try:
                category = DatasetCategory.objects.get(id=category_id)
            except DatasetCategory.DoesNotExist:
                return None, False, "Category not found"
        
        # Export data to repository
        dataset, created = station.export_to_repository(
            title=title,
            description=description,
            category_id=category.id,
            creator_id=creator.id
        )
        
        if not dataset:
            return None, False, "Failed to create dataset"
        
        return dataset, created, "Success"
        
    except WeatherStation.DoesNotExist:
        return None, False, "Weather station not found"
    except Exception as e:
        import traceback
        return None, False, f"Error: {str(e)}\n{traceback.format_exc()}"