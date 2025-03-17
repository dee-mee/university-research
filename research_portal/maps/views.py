import os
import csv
import json
import pytz
import logging
import io
from datetime import datetime, timedelta
from pathlib import Path
from dateutil import parser
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import FormView, TemplateView
from django.db.models import Avg, Max, Min, Sum
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import WeatherAlert, WeatherStation, ClimateData
from .forms import CSVUploadForm, FlashDriveImportForm
from .serializers import (
    WeatherAlertSerializer,
    WeatherStationSerializer,
    ClimateDataSerializer,
    GeoJSONClimateDataSerializer
)
from .permissions import IsAdminOrReadOnly



def debug_stations(request):
    """Debug view to check GeoJSON output"""
    stations = WeatherStation.objects.all()
    serializer = WeatherStationSerializer(stations, many=True)
    return JsonResponse(serializer.data)

class MapView(TemplateView):
    template_name = 'maps/map.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get data for initial map rendering
        stations = WeatherStation.objects.all()
        active_stations = stations.filter(is_active=True).count()
        
        context.update({
            'stations_count': stations.count(),
            'active_stations': active_stations,
            'api_base_url': '/api',  # Adjust based on your URL configuration
            'map_title': 'Weather Stations Map',
        })
        
        return context

class WeatherStationViewSet(viewsets.ModelViewSet):
    queryset = WeatherStation.objects.all()
    serializer_class = WeatherStationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'date_installed']
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'type': 'FeatureCollection',
            'features': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Find weather stations near a specific point"""
        lat = request.query_params.get('lat', None)
        lng = request.query_params.get('lng', None)
        radius = request.query_params.get('radius', 10)  # Default 10 km
        
        if lat is None or lng is None:
            return Response({"error": "Latitude and longitude are required"}, status=400)
        
        try:
            point = Point(float(lng), float(lat), srid=4326)
            radius = float(radius)
        except ValueError:
            return Response({"error": "Invalid coordinates or radius"}, status=400)
        
        # Find stations within radius km
        stations = WeatherStation.objects.filter(
            location__distance_lte=(point, D(km=radius))
        ).annotate(
            distance=Distance('location', point)
        ).order_by('distance')
        
        serializer = self.get_serializer(stations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Get climate data for a specific station"""
        station = self.get_object()
        days = int(request.query_params.get('days', 7))  # Default to last 7 days
        
        start_date = timezone.now() - timedelta(days=days)
        climate_data = ClimateData.objects.filter(
            station=station,
            timestamp__gte=start_date
        ).order_by('-timestamp')
        
        # Use pagination from the viewset
        page = self.paginate_queryset(climate_data)
        if page is not None:
            serializer = ClimateDataSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ClimateDataSerializer(climate_data, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export climate data for a specific station"""
        station = self.get_object()
        days = int(request.query_params.get('days', 7))
        format_type = request.query_params.get('format', 'csv').lower()
        
        if format_type not in ['csv', 'json', 'geojson']:
            return Response({"error": "Format must be one of: csv, json, geojson"}, status=400)
        
        start_date = timezone.now() - timedelta(days=days)
        climate_data = ClimateData.objects.filter(
            station=station,
            timestamp__gte=start_date
        ).order_by('-timestamp')
        
        # Record the export
        if request.user.is_authenticated:
            DataExport.objects.create(
                user=request.user,
                station=station,
                export_format=format_type,
                date_from=start_date,
                date_to=timezone.now()
            )
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{station.name}_{timezone.now().strftime("%Y%m%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Station', 'Timestamp', 'Temperature', 'Humidity', 'Precipitation', 
                'Air Quality Index', 'Wind Speed', 'Wind Direction', 'Barometric Pressure',
                'Cloud Cover', 'Soil Moisture', 'Water Level', 'Data Quality', 'UV Index'
            ])
            
            for data in climate_data:
                writer.writerow([
                    station.name,
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
                    data.uv_index
                ])
            
            return response
            
        elif format_type == 'json':
            serializer = ClimateDataSerializer(climate_data, many=True)
            response = HttpResponse(json.dumps(serializer.data, default=str), content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{station.name}_{timezone.now().strftime("%Y%m%d")}.json"'
            return response
            
        elif format_type == 'geojson':
            serializer = GeoJSONClimateDataSerializer(climate_data, many=True)
            response = HttpResponse(json.dumps(serializer.data, default=str), content_type='application/geo+json')
            response['Content-Disposition'] = f'attachment; filename="{station.name}_{timezone.now().strftime("%Y%m%d")}.geojson"'
            return response
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get statistics for a specific weather station"""
        station = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        start_date = timezone.now() - timedelta(days=days)
        stats = ClimateData.objects.filter(
            station=station,
            timestamp__gte=start_date
        ).aggregate(
            avg_temp=Avg('temperature'),
            max_temp=Max('temperature'),
            min_temp=Min('temperature'),
            avg_humidity=Avg('humidity'),
            total_precipitation=Sum('precipitation', default=0),
            avg_wind_speed=Avg('wind_speed'),
            max_wind_speed=Max('wind_speed'),
            avg_pressure=Avg('barometric_pressure'),
            max_uv=Max('uv_index')
        )
        
        return Response({
            'station': station.name,
            'period': f"Last {days} days",
            'stats': stats
        })
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Manually create the GeoJSON feature collection
        features = []
        for station in queryset:
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [station.longitude, station.latitude]
                },
                'properties': {
                    'id': station.id,
                    'name': station.name,
                    'description': station.description,
                    'is_active': station.is_active,
                    'altitude': station.altitude,
                    'date_installed': station.date_installed.isoformat() if station.date_installed else None
                }
            }
            features.append(feature)
        
        feature_collection = {
            'type': 'FeatureCollection',
            'features': features
        }
        
        return Response(feature_collection)


class ClimateDataViewSet(viewsets.ModelViewSet):
    queryset = ClimateData.objects.all().select_related('station')
    serializer_class = ClimateDataSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['station', 'data_quality']
    ordering_fields = ['timestamp', 'temperature', 'precipitation']
    
    def get_serializer_class(self):
        if self.request.query_params.get('format') == 'geojson':
            return GeoJSONClimateDataSerializer
        return ClimateDataSerializer
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get the most recent climate data for all stations"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        # Subquery to get the latest reading for each station
        from django.db.models import OuterRef, Subquery
        latest_per_station = ClimateData.objects.filter(
            station=OuterRef('station'),
            timestamp__gte=since
        ).order_by('-timestamp').values('id')[:1]
        
        recent_data = ClimateData.objects.filter(
            id__in=Subquery(latest_per_station)
        ).select_related('station')
        
        serializer = self.get_serializer(recent_data, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """Override create to check for alerts when new data is added"""
        climate_data = serializer.save()
        
        # Check for potential alerts
        alerts = check_for_alerts(climate_data)
        
        # Create alerts and send notifications
        for alert_data in alerts:
            alert = create_alert_from_detection(climate_data.station, alert_data)
            send_alert_notifications(alert)
        
        return climate_data


class CSVUploadView(FormView):
    template_name = 'maps/csv_upload.html'
    form_class = CSVUploadForm
    success_url = '/upload/success/'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def form_valid(self, form):
        import_type = form.cleaned_data['import_type']
        csv_file = form.cleaned_data['csv_file']
        
        # Process the file
        if import_type == 'stations':
            result = self.process_stations_file(csv_file)
        else:  # climate_data
            result = self.process_climate_data_file(csv_file)
        
        # Store results in session for display
        self.request.session['import_results'] = result
        
        return super().form_valid(form)
    
    def process_stations_file(self, csv_file):
        """Process a CSV file containing weather station data"""
        result = {
            'success': 0,
            'error': 0,
            'errors': [],
            'type': 'Weather Stations'
        }
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
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
                            # If date parsing fails, leave as None
                            pass
                    
                    # Parse altitude if present
                    altitude = None
                    if 'altitude' in row and row['altitude']:
                        try:
                            altitude = float(row['altitude'])
                        except ValueError:
                            # If altitude parsing fails, leave as None
                            pass
                    
                    # Parse is_active if present
                    is_active = True
                    if 'is_active' in row and row['is_active']:
                        is_active = row['is_active'].lower() in ('true', 'yes', '1', 't', 'y')
                    
                    # Create or update the station
                    station, created = WeatherStation.objects.update_or_create(
                        name=row['name'],
                        defaults={
                            'location': location,
                            'description': row.get('description', ''),
                            'altitude': altitude,
                            'is_active': is_active,
                            'date_installed': date_installed,
                        }
                    )
                    
                    result['success'] += 1
                    
                except Exception as e:
                    result['error'] += 1
                    result['errors'].append(f"Error processing row: {row}. Error: {str(e)}")
            
        except Exception as e:
            result['errors'].append(f"Error processing file: {str(e)}")
        
        return result
    
    def process_climate_data_file(self, csv_file):
        """Process a CSV file containing climate data"""
        result = {
            'success': 0,
            'error': 0,
            'errors': [],
            'type': 'Climate Data'
        }
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            required_fields = ['station_name', 'timestamp']
            
            # Check if required fields exist
            for field in required_fields:
                if field not in reader.fieldnames:
                    result['errors'].append(f"Missing required field: {field}")
                    return result
            
            # Get timezone for timestamps
            timezone = pytz.timezone('UTC')  # Default to UTC, adjust if needed
            
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
                    
                    # Parse timestamp
                    try:
                        timestamp = parser.parse(row['timestamp'])
                        if timestamp.tzinfo is None:
                            timestamp = timezone.localize(timestamp)
                    except ValueError:
                        result['error'] += 1
                        result['errors'].append(f"Invalid timestamp in row: {row}")
                        continue
                    
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
                    data, created = ClimateData.objects.update_or_create(
                        station=station,
                        timestamp=timestamp,
                        defaults=climate_data
                    )
                    
                    result['success'] += 1
                    
                except Exception as e:
                    result['error'] += 1
                    result['errors'].append(f"Error processing row: {row}. Error: {str(e)}")
            
        except Exception as e:
            result['errors'].append(f"Error processing file: {str(e)}")
        
        return result


class ImportSuccessView(View):
    template_name = 'maps/import_success.html'
    
    def get(self, request):
        results = request.session.get('import_results', {})
        return render(request, self.template_name, {'results': results})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def api_import_csv(request):
    """API endpoint for importing CSV data"""
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)
    
    import_type = request.data.get('import_type', 'stations')
    csv_file = request.FILES['file']
    
    # Process the file
    if import_type == 'stations':
        result = CSVUploadView().process_stations_file(csv_file)
    else:  # climate_data
        result = CSVUploadView().process_climate_data_file(csv_file)
    
    return Response(result)


def is_safe_path(base_dir, path):
    """
    Validate that the provided path is within an acceptable base directory
    to prevent directory traversal attacks
    """
    # Convert to absolute paths
    base_dir_abs = os.path.abspath(base_dir)
    path_abs = os.path.abspath(path)
    
    # Check if path is within base directory
    return os.path.commonpath([base_dir_abs]) == os.path.commonpath([base_dir_abs, path_abs])


@login_required
def flash_drive_import_view(request):
    """View to import data from a flash drive with improved security and error handling"""
    if request.method == 'POST':
        form = FlashDriveImportForm(request.POST)
        if form.is_valid():
            import_type = form.cleaned_data['import_type']
            drive_path = form.cleaned_data['drive_path']
            
            # Security check: Validate the path is within acceptable boundaries
            if not is_safe_path('/media', drive_path):
                messages.error(request, "Invalid drive path. Path must be within the media directory.")
                return render(request, 'maps/flash_drive_import.html', {'form': form})
            
            # Verify the path exists
            if not os.path.exists(drive_path):
                messages.error(request, f"The specified path does not exist: {drive_path}")
                return render(request, 'maps/flash_drive_import.html', {'form': form})
            
            # Look for CSV files in the directory
            try:
                csv_files = [f for f in os.listdir(drive_path) if f.endswith('.csv')]
            except PermissionError:
                messages.error(request, f"Permission denied when trying to access: {drive_path}")
                return render(request, 'maps/flash_drive_import.html', {'form': form})
            except Exception as e:
                messages.error(request, f"Error accessing directory: {str(e)}")
                return render(request, 'maps/flash_drive_import.html', {'form': form})
            
            if not csv_files:
                messages.error(request, "No CSV files found in the specified directory.")
                return render(request, 'maps/flash_drive_import.html', {'form': form})
            
            # Process all CSV files
            results = {
                'success_total': 0,
                'error_total': 0,
                'file_results': []
            }
            
            for csv_file_name in csv_files:
                file_path = os.path.join(drive_path, csv_file_name)
                
                # Process the file with multiple encoding attempts
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        file_content = file.read()
                except UnicodeDecodeError:
                    try:
                        # Try another common encoding
                        with open(file_path, 'r', encoding='latin-1') as file:
                            file_content = file.read()
                    except UnicodeDecodeError:
                        # If both fail, report error and skip file
                        result = {
                            'file_name': csv_file_name,
                            'success': 0,
                            'error': 1,
                            'errors': ["Could not decode file encoding. Please ensure it's properly encoded (UTF-8 or Latin-1)."]
                        }
                        results['error_total'] += 1
                        results['file_results'].append(result)
                        continue
                except Exception as e:
                    # Handle other file access errors
                    result = {
                        'file_name': csv_file_name,
                        'success': 0,
                        'error': 1,
                        'errors': [f"Error reading file: {str(e)}"]
                    }
                    results['error_total'] += 1
                    results['file_results'].append(result)
                    continue
                
                # Create a file-like object
                file_object = io.StringIO(file_content)
                file_object.name = csv_file_name
                
                # Choose the appropriate processor based on import type
                from .views import CSVUploadView
                if import_type == 'stations':
                    processor = CSVUploadView().process_stations_file
                else:  # climate_data
                    processor = CSVUploadView().process_climate_data_file
                
                # Process the file
                result = processor(file_object)
                
                # Add file name to the result
                result['file_name'] = csv_file_name
                
                # Update totals
                results['success_total'] += result['success']
                results['error_total'] += result['error']
                
                # Add to file results
                results['file_results'].append(result)
                
                # Option to move or rename processed files to avoid reimporting
                try:
                    if result['success'] > 0:
                        processed_path = file_path + '.processed'
                        # Only move if we don't already have a processed file
                        if not os.path.exists(processed_path):
                            os.rename(file_path, processed_path)
                except Exception as e:
                    # Log but don't fail if we can't move the file
                    logging.warning(f"Could not mark file as processed: {str(e)}")
            
            # Store results in session for display
            request.session['import_results'] = results
            
            return redirect('maps:import_success')
    else:
        form = FlashDriveImportForm()
    
    return render(request, 'maps/flash_drive_import.html', {'form': form})


def setup_automated_imports(flash_drive_path=None, import_interval=3600):
    """
    Set up scheduled imports from a flash drive with improved configuration and error handling
    
    This function should be called from your app's AppConfig.ready() method
    to set up scheduled tasks when the application starts.
    
    Parameters:
    - flash_drive_path: Path to monitor for CSV files, defaults to environment variable or '/media/usb'
    - import_interval: How often to check for new files (in seconds), defaults to environment variable or 3600
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        import logging
        
        # Use environment variables if path not provided
        if flash_drive_path is None:
            flash_drive_path = os.environ.get('FLASH_DRIVE_PATH', '/media/usb')
        
        # Use environment variable for interval if not provided
        if import_interval is None:
            import_interval = int(os.environ.get('IMPORT_INTERVAL', '3600'))
        
        def import_task():
            """Task to import CSV files from the flash drive path"""
            logging.info(f"Running scheduled import from {flash_drive_path}")
            try:
                # Security check for the path
                if not is_safe_path('/media', flash_drive_path):
                    logging.error(f"Unsafe path detected: {flash_drive_path}")
                    return
                
                if os.path.exists(flash_drive_path):
                    # Look for CSV files
                    try:
                        csv_files = [f for f in os.listdir(flash_drive_path) if f.endswith('.csv')]
                    except PermissionError:
                        logging.error(f"Permission denied when accessing {flash_drive_path}")
                        return
                    except Exception as e:
                        logging.error(f"Error accessing directory {flash_drive_path}: {str(e)}")
                        return
                    
                    # Process files in appropriate order
                    process_files(flash_drive_path, 'station_', 'stations', csv_files)
                    process_files(flash_drive_path, 'climate_', 'climate_data', csv_files)
                else:
                    logging.warning(f"Flash drive path {flash_drive_path} does not exist")
            except Exception as e:
                logging.error(f"Error in import task: {str(e)}")
        
        def process_files(path, prefix, import_type, all_files):
            """Process specific types of CSV files"""
            from .views import CSVUploadView
            
            # Filter files by prefix
            filtered_files = [f for f in all_files if f.startswith(prefix)]
            
            for file_name in filtered_files:
                try:
                    file_path = os.path.join(path, file_name)
                    
                    # Try different encodings
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file:
                            file_content = file.read()
                    except UnicodeDecodeError:
                        try:
                            with open(file_path, 'r', encoding='latin-1') as file:
                                file_content = file.read()
                        except UnicodeDecodeError:
                            logging.error(f"Cannot decode file {file_name}: Encoding issues")
                            continue
                    
                    # Create a file-like object
                    file_object = io.StringIO(file_content)
                    file_object.name = file_name
                    
                    # Choose processor based on import type
                    if import_type == 'stations':
                        processor = CSVUploadView().process_stations_file
                    else:  # climate_data
                        processor = CSVUploadView().process_climate_data_file
                    
                    # Process the file
                    result = processor(file_object)
                    
                    # Log the result
                    logging.info(f"Imported {file_name}: {result['success']} success, {result['error']} errors")
                    
                    # Move processed file to avoid reimporting
                    processed_path = file_path + '.processed'
                    if result['success'] > 0 and not os.path.exists(processed_path):
                        os.rename(file_path, processed_path)
                except Exception as e:
                    logging.error(f"Error processing {file_name}: {str(e)}")
        
        # Create and start the scheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            import_task,
            trigger=IntervalTrigger(seconds=import_interval),
            id='csv_import_job',
            replace_existing=True
        )
        scheduler.start()
        logging.info(f"Scheduled automated CSV imports from {flash_drive_path} every {import_interval} seconds")
        
    except ImportError:
        logging.warning("APScheduler not installed. Automated imports will not run.")
    except Exception as e:
        logging.error(f"Error setting up automated imports: {str(e)}")


class WeatherAlertViewSet(viewsets.ModelViewSet):
    queryset = WeatherAlert.objects.all()
    serializer_class = WeatherAlertSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['station', 'severity', 'status']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at']
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark an alert as resolved"""
        alert = self.get_object()
        alert.status = 'resolved'
        alert.resolved_at = timezone.now()
        alert.save()
        
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active alerts"""
        alerts = WeatherAlert.objects.filter(status='active')
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)