import os
import csv
import json
import pytz
import logging
import io
import random
import pandas as pd
import xlsxwriter
from datetime import datetime, timedelta
from pathlib import Path
from dateutil import parser
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.contrib import messages
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import FormView, TemplateView
from django.db.models import Avg, Max, Min, Sum, OuterRef, Subquery
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.db.models.functions import TruncDay, TruncHour
from django.db import models
import operator
from functools import reduce
from django.core.signing import Signer, BadSignature
from .utils import check_for_alerts, create_alert_from_detection, send_alert_notifications
from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .utils import fetch_environmental_data, calculate_statistics
from .models import DataExport, WeatherAlert, WeatherStation, ClimateData, Country, WeatherDataType
from .field_models import DeviceType, FieldDevice, DeviceCalibration, FieldDataUpload
from .forms import CSVUploadForm, FlashDriveImportForm
from .serializers import (
    WeatherAlertSerializer,
    WeatherStationSerializer,
    ClimateDataSerializer,
    GeoJSONClimateDataSerializer,
    StackedDataSerializer,
    StackInfoSerializer,
    StackedDataSerializer,
    StackInfoSerializer
)
from .permissions import IsAdminOrReadOnly
from django.urls import reverse_lazy, reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .field_models import FieldDataUpload, FieldDataRecord, FieldDevice, DeviceType


# views.py (improved debug_stations)
def debug_stations(request):
    """Debug view to check GeoJSON output"""
    stations = WeatherStation.objects.all().select_related('country')
    features = [station.to_representation() for station in stations]
    stations = WeatherStation.objects.all().select_related('country')
    features = [station.to_representation() for station in stations]
    
    return JsonResponse({
        'type': 'FeatureCollection',
        'count': len(features),
        'features': features,
        'count': len(features),
        'features': features,
        'debug_info': {
            'fields_available': [field.name for field in WeatherStation._meta.fields],
            'data_types': list(WeatherDataType.objects.values_list('name', flat=True)),
            'data_types': list(WeatherDataType.objects.values_list('name', flat=True))
        }
    })

# views.py (improved MapView)
@api_view(['POST'])
def field_data_upload(request):
    """
    Endpoint for field devices to upload data
    """
    try:
        device_id = request.data.get('device_id')
        timestamp = request.data.get('timestamp')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        data = request.data.get('data')

        if not all([device_id, timestamp, latitude, longitude, data]):
            return Response(
                {'error': 'Missing required fields', 'received_data': request.data},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create device
        device = FieldDevice.objects.filter(device_id=device_id).first()
        if not device:
            # Create new device if it doesn't exist
            device_type = DeviceType.objects.first()  # Use default device type
            if not device_type:
                return Response(
                    {
                        'error': 'No device type configured',
                        'device_id': device_id,
                        'available_device_types': list(DeviceType.objects.values_list('name', flat=True))
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            device = FieldDevice.objects.create(
                device_id=device_id,
                device_type=device_type,
                name=f"Device {device_id}",
                location=Point(longitude, latitude)
            )

        # Update device location and last communication
        device.location = Point(longitude, latitude)
        device.last_communication = timezone.now()
        device.save()

        # Create or get data upload
        upload, created = FieldDataUpload.objects.get_or_create(
            title=f"Data Upload for {device_id}",
            defaults={
                'description': f"Automatic upload from device {device_id}",
                'status': 'completed'
            }
        )

        # Create data record
        try:
            record = FieldDataRecord.objects.create(
                upload=upload,
                device=device,
                timestamp=timezone.make_aware(datetime.fromisoformat(timestamp)),
                latitude=latitude,
                longitude=longitude,
                data=data
            )
            
            return Response(
                {
                    'status': 'success',
                    'message': 'Data uploaded successfully',
                    'device_status': device.status,
                    'record_id': record.id
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {
                    'error': f'Failed to create data record: {str(e)}',
                    'device_id': device_id,
                    'timestamp': timestamp
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class MapView(TemplateView):
    template_name = 'maps/map.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get data for initial map rendering with optimized queries
        stations = WeatherStation.objects.select_related('country').all()
        active_stations = stations.filter(is_active=True)
        
        
        # Get recent climate data with related station info
        recent_data = ClimateData.objects.select_related('station').filter(
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).order_by('-timestamp')[:100]
        
        # Get active alerts with related station and country info
        active_alerts = WeatherAlert.objects.select_related('station', 'country', 'data_type').filter(
            status='active'
        ).order_by('-created_at')[:5]
        
        
        context.update({
            'stations_count': stations.count(),
            'active_stations': active_stations.count(),
            'stations_list': stations,
            'recent_data_count': recent_data.count(),
            'has_alerts': active_alerts.exists(),
            'alerts_count': active_alerts.count(),
            'data_types': WeatherDataType.objects.all(),
            'api_base_url': '/maps',  # Update API base URL to include maps prefix
            'map_title': 'Weather Stations Map',
            'map_description': 'Interactive map of all weather stations and their data',
            'geojson_url': '/maps/api/weather-stations/',  # Updated path
        })
        
        return context

# views.py (fixed WeatherStationViewSet)
class WeatherStationViewSet(viewsets.ModelViewSet):
    queryset = WeatherStation.objects.all()
    serializer_class = WeatherStationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'country']
    search_fields = ['name', 'description', 'country__name']
    ordering_fields = ['name', 'date_installed']
    
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
                    'date_installed': station.date_installed.isoformat() if station.date_installed else None,
                    'country': station.country.name if station.country else None
                }
            }
            features.append(feature)
        
        feature_collection = {
            'type': 'FeatureCollection',
            'features': features
        }
        
        return Response(feature_collection)
    
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
        return Response({
            'type': 'FeatureCollection',
            'features': serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Get climate data for a specific station"""
        station = self.get_object()
        days = int(request.query_params.get('days', 7))
        data_types = request.query_params.getlist('data_types', [])
        
        start_date = timezone.now() - timedelta(days=days)
        query = ClimateData.objects.filter(
            station=station,
            timestamp__gte=start_date
        ).order_by('-timestamp')
        
        # Filter by data types if specified
        if data_types:
            conditions = []
            for data_type in data_types:
                if hasattr(ClimateData, data_type):
                    conditions.append(~models.Q(**{data_type: None}))
            if conditions:
                query = query.filter(reduce(operator.or_, conditions))
        
        page = self.paginate_queryset(query)
        if page is not None:
            serializer = ClimateDataSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ClimateDataSerializer(query, many=True)
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
                stations=[station],
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
                    data.timestamp.isoformat(),
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
    
    @action(detail=True, methods=['post'])
    def push_data(self, request, pk=None):
        """Push weather data onto the station's stack"""
        station = self.get_object()
        serializer = StackedDataSerializer(data=request.data)
        
        if serializer.is_valid():
            success = station.push_data(serializer.validated_data)
            if success:
                return Response({
                    'success': True,
                    'message': 'Data successfully added to stack',
                    'stack_size': station.stack_size()
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Failed to add data to stack. The stack may be full.'
                }, status=400)
        else:
            return Response(serializer.errors, status=400)
    
    @action(detail=True, methods=['post'])
    def process_stack(self, request, pk=None):
        """Process all data in the station's stack"""
        station = self.get_object()
        records_processed = station.process_data_stack()
        
        return Response({
            'success': True,
            'records_processed': records_processed,
            'message': f'Successfully processed {records_processed} records'
        })
    
    @action(detail=True, methods=['get'])
    def stack_info(self, request, pk=None):
        """Get information about the station's data stack"""
        station = self.get_object()
        latest_data = station.peek_data()
        
        data = {
            'station_id': station.id,
            'station_name': station.name,
            'stack_size': station.stack_size(),
            'max_stack_size': station.max_stack_size,
            'last_data_feed': station.last_data_feed,
            'auto_process': station.auto_process,
            'process_threshold': station.process_threshold,
            'latest_data': latest_data
        }
        
        return Response(data)


    def perform_create(self, serializer):
        """Override create to check for alerts when new data is added"""
        climate_data = serializer.save()
        
        # Check for potential alerts
        alerts = check_for_alerts(climate_data)
        
        # Create alerts and send notifications
        for alert_data in alerts:
            create_alert_from_detection(climate_data.station, alert_data)
        
        return climate_data

class WeatherAlertViewSet(viewsets.ModelViewSet):
    queryset = WeatherAlert.objects.all().select_related('station', 'country', 'data_type')
    serializer_class = WeatherAlertSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['station', 'severity', 'status', 'country', 'data_type']
    search_fields = ['title', 'description', 'station__name', 'country__name']
    ordering_fields = ['created_at', 'updated_at', 'severity']
    
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
        queryset = self.queryset.filter(status='active')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminOrReadOnly])
def climate_data_station(request, station_id=None):
    """
    Get climate data for a specific station with options for filtering by time period
    """
    try:
        # Get parameters
        hours = int(request.query_params.get('hours', 72))
        days = int(request.query_params.get('days', 0))
        
        # Calculate time period
        time_delta = timedelta(hours=hours, days=days)
        since = timezone.now() - time_delta
        
        # Get station
        station = WeatherStation.objects.get(id=station_id)
        
        # Get climate data for this station within the time period
        climate_data = ClimateData.objects.filter(
            station=station,
            timestamp__gte=since
        ).order_by('timestamp')
        
        # Serialize the data
        serializer = ClimateDataSerializer(climate_data, many=True)
        
        return Response(serializer.data)
    
    except WeatherStation.DoesNotExist:
        return Response(
            {"error": f"Weather station with ID {station_id} not found"},
            status=404
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=500
        )
    
# views.py (new map_data endpoint)
@api_view(['GET'])
def map_data(request):
    """API endpoint to get consolidated data for map display"""
    try:
        # Get stations with related data - use only fields we know exist
        # Avoid using defer() or only() with Country as it might try to load the missing field
        stations = WeatherStation.objects.all()
        
        # Get recent climate data for active stations
        recent_data = []
        active_stations = stations.filter(is_active=True)
        
        for station in active_stations:
            try:
                # Use values() to explicitly select only existing fields
                latest_reading = ClimateData.objects.filter(
                    station=station
                ).order_by('-timestamp').values(
                    'id', 'timestamp', 'temperature', 'humidity', 'precipitation',
                    'air_quality_index', 'wind_speed', 'wind_direction', 'barometric_pressure',
                    'cloud_cover', 'soil_moisture', 'water_level', 'data_quality', 'uv_index',
                    'year', 'month'
                ).first()
                
                if latest_reading:
                    data = {
                        'station_id': station.id,
                        'station_name': station.name,
                        'timestamp': latest_reading['timestamp'],
                        'data': {}
                    }
                    
                    # Add available measurements
                    for data_type in station.available_data_types():
                        if data_type in latest_reading and latest_reading[data_type] is not None:
                            data['data'][data_type] = latest_reading[data_type]
                    
                    data['is_recent'] = latest_reading['timestamp'] > (timezone.now() - timedelta(days=1))
                    recent_data.append(data)
            except Exception as e:
                # Log the error but continue processing other stations
                print(f"Error getting data for station {station.id}: {str(e)}")
                continue
        
        # Get active alerts with related info - avoid using select_related with Country
        active_alerts = WeatherAlert.objects.filter(status='active')
        
        # Safe feature collection creation - use a more direct approach to avoid model field access issues
        features = []
        for station in stations:
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [station.longitude, station.latitude]
                },
                'properties': {
                    'id': station.id,
                    'name': station.name,
                    'is_active': station.is_active,
                    'country': station.country.name if station.country else None,
                }
            }
            features.append(feature)
        
        # Return the consolidated data
        return Response({
            'stations': {
                'type': 'FeatureCollection',
                'features': features
            },
            'recent_data': recent_data,
            'alerts': WeatherAlertSerializer(active_alerts, many=True).data,
            'stats': {
                'total_stations': stations.count(),
                'active_stations': active_stations.count(),
                'stations_with_recent_data': len([d for d in recent_data if d['is_recent']]),
                'active_alerts': active_alerts.count(),
                'available_data_types': list(WeatherDataType.objects.values('name', 'display_name', 'unit'))
            }
        })
    except Exception as e:
        # Return a meaningful error that won't expose sensitive information
        return Response({
            'error': f"Failed to load map data: {str(e)}",
            'stations': {'type': 'FeatureCollection', 'features': []}
        }, status=500)

class CSVUploadView(FormView):
    template_name = 'maps/csv_upload.html'
    form_class = CSVUploadForm
    success_url = reverse_lazy('maps:import_success')

    # @method_decorator(login_required)
    success_url = reverse_lazy('maps:import_success')

    # @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_datetime'] = timezone.now()
        return context


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_datetime'] = timezone.now()
        return context

    def form_valid(self, form):
        try:
            import_type = form.cleaned_data['import_type']
            csv_file = form.cleaned_data['csv_file']
            processing_mode = form.cleaned_data.get('processing_mode', 'direct')

            # Enhanced logging
            logging.info(f"Processing CSV import of type: {import_type}, file: {csv_file.name}, size: {csv_file.size} bytes, mode: {processing_mode}")
            
            # Check if file is empty
            if csv_file.size == 0:
                result = {
                    'success': 0, 
                    'error': 1, 
                    'errors': ['The uploaded file is empty.'], 
                    'type': import_type
                }
                self.request.session['import_results'] = result
                messages.error(self.request, "The uploaded file is empty.")
                return redirect(self.get_success_url())

            # Process the file with the appropriate method based on import_type
            if import_type == 'stations':
                result = self.process_stations_file(csv_file)
            elif import_type == 'climate_data':
                result = self.process_climate_data_file(csv_file, processing_mode)
            elif import_type == 'weather_data_types':
                result = self.process_weather_data_types_file(csv_file)
            elif import_type == 'countries':
                result = self.process_countries_file(csv_file)
            else:
                # Default to the generic processor
                result = self.process_csv_file(csv_file, import_type, processing_mode)

            # Enhanced logging
            logging.info(f"CSV import result: {result['success']} success, {result['error']} errors")
            
            # Store results in session
            self.request.session['import_results'] = result

            # Add message for regular form submission
            if result['success'] > 0:
                messages.success(
                    self.request,
                    f"Successfully processed {result['success']} records. "
                    f"Encountered {result['error']} errors."
                )
            else:
                messages.error(
                    self.request,
                    f"Import failed. Encountered {result['error']} errors."
                )

            # Always redirect to success page for consistent behavior
            return redirect(self.get_success_url())

        except Exception as e:
            # Enhanced error logging
            logging.error(f"CSV import error: {str(e)}", exc_info=True)
            
            error_msg = f"An error occurred: {str(e)}"
            messages.error(self.request, error_msg)
            
            # Store minimal results in session to show on import_success page
            self.request.session['import_results'] = {
                'success': 0,
                'error': 1,
                'errors': [error_msg],
                'type': form.cleaned_data.get('import_type', 'Unknown')
            }
            
            # Always redirect to success page even on errors
            return redirect(self.get_success_url())

    # Add these new specific file processors
    def process_stations_file(self, csv_file):
        """Process a CSV file containing weather station data"""
        from .utils import _process_station_row_enhanced
        from .csv_utils import process_csv_in_batches

        def row_processor(row, line_num, progress):
            return _process_station_row_enhanced(
                row, line_num, progress, update_existing=True,
                required_fields=['name', 'latitude', 'longitude']
            )
            
        result = process_csv_in_batches(csv_file, row_processor, batch_size=100)
        result['type'] = 'Weather Stations'
        
        return result

    def process_climate_data_file(self, csv_file, processing_mode='direct'):
        """Process a CSV file containing climate data"""
        from .utils import _process_climate_data_row_enhanced
        from .csv_utils import process_csv_in_batches

        if processing_mode == 'stack':
            def row_processor(row, line_num, progress):
                return self._process_climate_data_to_stack(row, line_num, progress)
        else:
            def row_processor(row, line_num, progress):
                return _process_climate_data_row_enhanced(
                    row, line_num, progress, update_existing=True,
                    required_fields=['station_name', 'timestamp']
                )
                
        result = process_csv_in_batches(csv_file, row_processor, batch_size=100)
        result['type'] = 'Climate Data'
        
        return result

    def process_weather_data_types_file(self, csv_file):
        """Process a CSV file containing weather data types"""
        from .csv_utils import process_csv_in_batches

        def row_processor(row, line_num, progress):
            return self._process_weather_data_type_row(row, line_num, progress)
                
        result = process_csv_in_batches(csv_file, row_processor, batch_size=100)
        result['type'] = 'Weather Data Types'
        
        return result

    def process_countries_file(self, csv_file):
        """Process a CSV file containing country data"""
        from .csv_utils import process_csv_in_batches

        def row_processor(row, line_num, progress):
            return self._process_country_row(row, line_num, progress)
                
        result = process_csv_in_batches(csv_file, row_processor, batch_size=100)
        result['type'] = 'Countries'
        
        return result

    # Keep existing process_csv_file and other methods
    def process_csv_file(self, csv_file, import_type, processing_mode):
        """
        Process a CSV file using our improved CSV handling utilities
        
        Args:
            csv_file: The uploaded file object
            import_type: Type of data being imported
            processing_mode: 'direct' or 'stack'
            
        Returns:
            Dictionary with processing results
        """
        from .csv_utils import process_csv_in_batches, CSVImportError
        from .utils import (_process_station_row_enhanced, 
                           _process_climate_data_row_enhanced)
        
        # Set up the appropriate row processor based on import type
        if import_type == 'stations':
            def row_processor(row, line_num, progress):
                return _process_station_row_enhanced(
                    row, line_num, progress, update_existing=True,
                    required_fields=['name', 'latitude', 'longitude']
                )
            data_type = 'Weather Stations'
            
        elif import_type == 'climate_data':
            # If stack mode is selected, use different processing
            if processing_mode == 'stack':
                def row_processor(row, line_num, progress):
                    return self._process_climate_data_to_stack(row, line_num, progress)
            else:
                def row_processor(row, line_num, progress):
                    return _process_climate_data_row_enhanced(
                        row, line_num, progress, update_existing=True,
                        required_fields=['station_name', 'timestamp']
                    )
            data_type = 'Climate Data'
                
        elif import_type == 'weather_data_types':
            def row_processor(row, line_num, progress):
                return self._process_weather_data_type_row(row, line_num, progress)
            data_type = 'Weather Data Types'
                
        elif import_type == 'countries':
            def row_processor(row, line_num, progress):
                return self._process_country_row(row, line_num, progress)
            data_type = 'Countries'
                
        else:
            return {
                'success': 0,
                'error': 1,
                'errors': [f"Invalid import type: {import_type}"],
                'type': 'Unknown'
            }
            
        # Process the file with our enhanced batched processor
        result = process_csv_in_batches(csv_file, row_processor, batch_size=100)
        
        # Add import type to the result
        result['type'] = data_type
        
        return result
        
    def _process_climate_data_to_stack(self, row, line_num, progress):
        """Process climate data into a station's data stack"""
        from .csv_utils import CSVImportError, parse_numeric, parse_date
        from .models import WeatherStation
        
        # Find the station
        station_identifier = None
        station_id_fields = ['station_name', 'station_id', 'station']
        
        for field in station_id_fields:
            if field in row and row[field]:
                station_identifier = row[field]
                break
                
        if not station_identifier:
            raise CSVImportError(
                f"Missing station identifier (one of {', '.join(station_id_fields)} is required)",
                row=row, line_num=line_num
            )
        
        # Find the station using multiple methods
        try:
            try:
                # First try by station_id
                station = WeatherStation.objects.get(station_id=station_identifier)
            except WeatherStation.DoesNotExist:
                try:
                    # Then try by name
                    station = WeatherStation.objects.get(name=station_identifier)
                except WeatherStation.DoesNotExist:
                    try:
                        # Finally try by ID if numeric
                        if station_identifier.isdigit():
                            station = WeatherStation.objects.get(id=int(station_identifier))
                        else:
                            raise WeatherStation.DoesNotExist()
                    except (WeatherStation.DoesNotExist, ValueError):
                        raise CSVImportError(f"Station not found: {station_identifier}", 
                                          row=row, line_num=line_num, field='station_name')
        except Exception as e:
            raise CSVImportError(f"Error finding station: {str(e)}", 
                              row=row, line_num=line_num)
        
        # Create data dictionary for the stack
        data_dict = {}
        
        # Add timestamp if present
        if 'timestamp' in row and row['timestamp']:
            try:
                timestamp = parse_date(row['timestamp'], 'timestamp', line_num, allow_none=False)
                data_dict['timestamp'] = timestamp.isoformat()
            except Exception as e:
                raise CSVImportError(f"Invalid timestamp: {str(e)}", 
                                  row=row, line_num=line_num, field='timestamp')
        else:
            # Use current time if no timestamp provided
            data_dict['timestamp'] = datetime.now().isoformat()
        
        # Parse numeric fields
        numeric_fields = [
            'temperature', 'humidity', 'precipitation', 'air_quality_index',
            'wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover',
            'soil_moisture', 'water_level', 'uv_index'
        ]
        
        for field in numeric_fields:
            if field in row and row[field]:
                try:
                    data_dict[field] = parse_numeric(row[field], field, line_num)
                except CSVImportError as e:
                    # Log warning but continue
                    progress.warning(e.message, row=row, line_num=line_num, field=field)
        
        # Push data to station's stack
        try:
            success = station.push_data(data_dict)
            if success:
                progress.success()
            else:
                progress.error(
                    f"Failed to add data to stack for station {station.name}: Stack is full", 
                    row=row, line_num=line_num
                )
        except Exception as e:
            raise CSVImportError(f"Error adding data to stack: {str(e)}", 
                              row=row, line_num=line_num)
    
    def _process_weather_data_type_row(self, row, line_num, progress):
        """Process weather data type row with enhanced error handling"""
        from .csv_utils import CSVImportError, parse_numeric
        from .models import WeatherDataType
        
        # Check required fields
        if not row.get('name'):
            raise CSVImportError("Missing required field: 'name'", 
                              row=row, line_num=line_num, field='name')
        
        # Parse numeric fields with validation
        min_value = None
        if 'min_value' in row and row['min_value']:
            try:
                min_value = parse_numeric(row['min_value'], 'min_value', line_num)
            except CSVImportError as e:
                progress.warning(e.message, row=row, line_num=line_num, field='min_value')
        
        max_value = None
        if 'max_value' in row and row['max_value']:
            try:
                max_value = parse_numeric(row['max_value'], 'max_value', line_num)
            except CSVImportError as e:
                progress.warning(e.message, row=row, line_num=line_num, field='max_value')
        
        # Create or update data type record
        try:
            data_type, created = WeatherDataType.objects.update_or_create(
                name=row['name'],
                defaults={
                    'display_name': row.get('display_name', row['name']),
                    'description': row.get('description', ''),
                    'unit': row.get('unit', ''),
                    'min_value': min_value,
                    'max_value': max_value,
                    'icon': row.get('icon', '')
                }
            )
            progress.success()
        except Exception as e:
            raise CSVImportError(f"Error creating weather data type: {str(e)}", 
                              row=row, line_num=line_num)
    
    def _process_country_row(self, row, line_num, progress):
        """Process country row with enhanced error handling"""
        from .csv_utils import CSVImportError, get_bool_value
        from .models import Country
        
        # Check required fields
        if not row.get('name'):
            raise CSVImportError("Missing required field: 'name'", 
                              row=row, line_num=line_num, field='name')
        if not row.get('code'):
            raise CSVImportError("Missing required field: 'code'", 
                              row=row, line_num=line_num, field='code')
        
        # Validate country code format (assume 2 or 3-letter code)
        code = row['code'].strip()
        if not (len(code) == 2 or len(code) == 3):
            progress.warning(f"Country code '{code}' should be 2 or 3 letters", 
                          row=row, line_num=line_num, field='code')
        
        # Parse hemisphere flag if present
        is_southern = False
        if 'is_southern_hemisphere' in row:
            is_southern = get_bool_value(row['is_southern_hemisphere'])
        
        # Create or update country record
        try:
            country, created = Country.objects.update_or_create(
                code=code.upper(),
                defaults={
                    'name': row['name'].strip(),
                    'is_southern_hemisphere': is_southern
                }
            )
            progress.success()
        except Exception as e:
            raise CSVImportError(f"Error creating country: {str(e)}", 
                              row=row, line_num=line_num)

# ... existing code ...

@api_view(['POST'])
# @permission_classes([IsAdminUser])
# @permission_classes([IsAdminUser])
def api_import_csv(request):
    """API endpoint for importing CSV data with enhanced processing"""
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)


    import_type = request.data.get('import_type', 'stations')
    processing_mode = request.data.get('processing_mode', 'direct')
    csv_file = request.FILES['file']

    # Process the file with our improved functions
    view = CSVUploadView()
    result = view.process_csv_file(csv_file, import_type, processing_mode)

    return Response(result)

# ... existing code ...

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


# @login_required
# @login_required
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
                            'errors': [
                                "Could not decode file encoding. Please ensure it's properly encoded (UTF-8 or Latin-1)."]
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

                # Process the file based on import type or filename prefix
                csv_view = CSVUploadView()

                if import_type != 'auto':
                    # Use the specified import type
                    if import_type == 'stations':
                        result = csv_view.process_stations_file(file_object)
                    elif import_type == 'climate_data':
                        driveresult = csv_view.process_climate_data_file(file_object)
                    elif import_type == 'weather_data_types':
                        result = csv_view.process_weather_data_types_file(file_object)
                    elif import_type == 'countries':
                        result = csv_view.process_countries_file(file_object)
                else:
                    # Auto-detect based on filename prefix
                    if csv_file_name.startswith('station_'):
                        result = csv_view.process_stations_file(file_object)
                    elif csv_file_name.startswith('climate_'):
                        result = csv_view.process_climate_data_file(file_object)
                    elif csv_file_name.startswith('datatype_'):
                        result = csv_view.process_weather_data_types_file(file_object)
                    elif csv_file_name.startswith('country_'):
                        result = csv_view.process_countries_file(file_object)
                    else:
                        # Default to climate data
                        result = csv_view.process_climate_data_file(file_object)


                # Process the file based on import type or filename prefix
                csv_view = CSVUploadView()

                if import_type != 'auto':
                    # Use the specified import type
                    if import_type == 'stations':
                        result = csv_view.process_stations_file(file_object)
                    elif import_type == 'climate_data':
                        driveresult = csv_view.process_climate_data_file(file_object)
                    elif import_type == 'weather_data_types':
                        result = csv_view.process_weather_data_types_file(file_object)
                    elif import_type == 'countries':
                        result = csv_view.process_countries_file(file_object)
                else:
                    # Auto-detect based on filename prefix
                    if csv_file_name.startswith('station_'):
                        result = csv_view.process_stations_file(file_object)
                    elif csv_file_name.startswith('climate_'):
                        result = csv_view.process_climate_data_file(file_object)
                    elif csv_file_name.startswith('datatype_'):
                        result = csv_view.process_weather_data_types_file(file_object)
                    elif csv_file_name.startswith('country_'):
                        result = csv_view.process_countries_file(file_object)
                    else:
                        # Default to climate data
                        result = csv_view.process_climate_data_file(file_object)

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
    Sets up an automated background job to import CSV files from a flash drive.
    
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
                    process_files(flash_drive_path, 'country_', 'countries', csv_files)
                    process_files(flash_drive_path, 'datatype_', 'weather_data_types', csv_files)
                    process_files(flash_drive_path, 'country_', 'countries', csv_files)
                    process_files(flash_drive_path, 'datatype_', 'weather_data_types', csv_files)
                    process_files(flash_drive_path, 'station_', 'stations', csv_files)
                    process_files(flash_drive_path, 'climate_', 'climate_data', csv_files)
                else:
                    logging.warning(f"Flash drive path {flash_drive_path} does not exist")
            except Exception as e:
                logging.error(f"Error in import task: {str(e)}")


        def process_files(path, prefix, import_type, all_files):
            """Process specific types of CSV files"""
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

                    # Process the file based on import type
                    csv_view = CSVUploadView()

                    # Process the file based on import type
                    csv_view = CSVUploadView()
                    if import_type == 'stations':
                        result = csv_view.process_stations_file(file_object)
                    elif import_type == 'climate_data':
                        result = csv_view.process_climate_data_file(file_object)
                    elif import_type == 'weather_data_types':
                        result = csv_view.process_weather_data_types_file(file_object)
                    elif import_type == 'countries':
                        result = csv_view.process_countries_file(file_object)
                    else:
                        logging.error(f"Unknown import type: {import_type}")
                        continue
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
        print("APScheduler not installed. Automated imports will not run.")
    except Exception as e:
        print(f"Error setting up automated imports: {str(e)}")


def station_statistics_view(request, station_id):
    """View for displaying station statistics in a template"""
    try:
        station = WeatherStation.objects.get(pk=station_id)
    except WeatherStation.DoesNotExist:
        messages.error(request, f"Weather station with ID {station_id} does not exist.")
        return redirect('maps:map')
    
    # Calculate days for different time periods
    days_30 = timezone.now() - timedelta(days=30)
    days_90 = timezone.now() - timedelta(days=90)
    days_365 = timezone.now() - timedelta(days=365)
    
    # Get statistics for different time periods
    stats_30 = ClimateData.objects.filter(
        station=station,
        timestamp__gte=days_30
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
    
    stats_90 = ClimateData.objects.filter(
        station=station,
        timestamp__gte=days_90
    ).aggregate(
        avg_temp=Avg('temperature'),
        max_temp=Max('temperature'),
        min_temp=Min('temperature'),
        avg_humidity=Avg('humidity'),
        total_precipitation=Sum('precipitation', default=0)
    )
    
    stats_365 = ClimateData.objects.filter(
        station=station,
        timestamp__gte=days_365
    ).aggregate(
        avg_temp=Avg('temperature'),
        total_precipitation=Sum('precipitation', default=0)
    )
    
    # Get recent climate data points for this station
    recent_data = ClimateData.objects.filter(
        station=station
    ).order_by('-timestamp')[:100]
    
    # Get available data types for this station
    available_data_types = []
    data_type_fields = [
        'temperature', 'humidity', 'precipitation', 'wind_speed', 
        'barometric_pressure', 'air_quality_index', 'uv_index'
    ]
    
    for field in data_type_fields:
        if ClimateData.objects.filter(station=station).exclude(**{field: None}).exists():
            # Get the display name
            try:
                data_type_obj = WeatherDataType.objects.get(name=field)
                display_name = data_type_obj.display_name
                unit = data_type_obj.unit or ""
            except WeatherDataType.DoesNotExist:
                display_name = field.replace('_', ' ').title()
                
                # Default units
                unit = ""
                if field == 'temperature':
                    unit = '°C'
                elif field == 'humidity':
                    unit = '%'
                elif field == 'precipitation':
                    unit = 'mm'
                elif field == 'wind_speed':
                    unit = 'm/s'
                elif field == 'barometric_pressure':
                    unit = 'hPa'
            
            available_data_types.append({
                'field': field,
                'display_name': display_name,
                'unit': unit
            })
    
    context = {
        'station': station,
        'stats_30': stats_30,
        'stats_90': stats_90,
        'stats_365': stats_365,
        'recent_data': recent_data,
        'current_year': timezone.now().year,
        'available_data_types': available_data_types,
        'api_base_url': '/maps',
    }
    
    return render(request, 'maps/station_statistics.html', context)

def station_data_export_view(request, station_id):
    """View for station data export options"""
    try:
        station = WeatherStation.objects.get(pk=station_id)
    except WeatherStation.DoesNotExist:
        messages.error(request, f"Weather station with ID {station_id} does not exist.")
        return redirect('maps:map')
    
    # Calculate data availability
    earliest_record = ClimateData.objects.filter(station=station).order_by('timestamp').first()
    latest_record = ClimateData.objects.filter(station=station).order_by('-timestamp').first()
    record_count = ClimateData.objects.filter(station=station).count()
    
    # Get data types that are actually available for this station
    data_types = []
    data_type_fields = [
        'temperature', 'humidity', 'precipitation', 'wind_speed', 
        'wind_direction', 'barometric_pressure', 'air_quality_index',
        'cloud_cover', 'soil_moisture', 'water_level', 'uv_index'
    ]
    
    for field in data_type_fields:
        # Check if field exists in data and is not all null
        if ClimateData.objects.filter(station=station).exclude(**{field: None}).exists():
            # Get the display name if available, otherwise use the field name
            try:
                data_type = WeatherDataType.objects.get(name=field)
                display_name = data_type.display_name
                unit = data_type.unit
            except WeatherDataType.DoesNotExist:
                display_name = field.replace('_', ' ').title()
                unit = ''
                
            data_types.append({
                'field': field,
                'display_name': display_name,
                'unit': unit
            })
    
    context = {
        'station': station,
        'earliest_record': earliest_record,
        'latest_record': latest_record,
        'record_count': record_count,
        'data_types': data_types,
    }
    
    return render(request, 'maps/station_data_export.html', context)

def download_station_data(request, station_id):
    """Download station data in the specified format"""
    try:
        station = WeatherStation.objects.get(pk=station_id)
    except WeatherStation.DoesNotExist:
        messages.error(request, f"Weather station with ID {station_id} does not exist.")
        return redirect('maps:map')
    
    # Get parameters from query
    format_type = request.GET.get('format', 'csv').lower()
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    selected_fields = request.GET.getlist('fields')
    
    # Default fields if none selected
    if not selected_fields:
        selected_fields = ['timestamp', 'temperature', 'humidity', 'precipitation']
    
    # Always include timestamp
    if 'timestamp' not in selected_fields:
        selected_fields = ['timestamp'] + selected_fields
    
    # Parse dates if provided
    filters = {'station': station}
    
    # Default date range - last 30 days if not specified
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    if date_from_str:
        try:
            start_date = parser.parse(date_from_str)
            if timezone.is_naive(start_date):
                start_date = timezone.make_aware(start_date)
            filters['timestamp__gte'] = start_date
        except ValueError:
            messages.warning(request, f"Invalid from date format: {date_from_str}. Using default.")
    
    if date_to_str:
        try:
            end_date = parser.parse(date_to_str)
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)
            filters['timestamp__lte'] = end_date
        except ValueError:
            messages.warning(request, f"Invalid to date format: {date_to_str}. Using default.")
    
    # Always add date filters even if not provided in request
    filters['timestamp__gte'] = filters.get('timestamp__gte', start_date)
    filters['timestamp__lte'] = filters.get('timestamp__lte', end_date)
    
    # Query the data
    data = ClimateData.objects.filter(**filters).order_by('-timestamp')
    
    # Create filename with date info
    date_str = timezone.now().strftime("%Y%m%d")
    filename = f"{station.name.replace(' ', '_')}_{date_str}"
    
    # Record the export if user is authenticated
    if request.user.is_authenticated:
        # Create the DataExport object with proper date_from and date_to values
        data_export = DataExport.objects.create(
            user=request.user,
            export_format=format_type,
            date_from=filters['timestamp__gte'],
            date_to=filters['timestamp__lte'],
            status='completed'
        )
        # Now add the station to the many-to-many relationship
        data_export.stations.add(station)
    
    if format_type == 'csv':
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        
        writer = csv.writer(response)
        
        # Write headers
        headers = ['Station Name', 'Station ID'] + [field for field in selected_fields]
        writer.writerow(headers)
        
        # Write data rows
        for record in data:
            row = [
                station.name,
                station.station_id or station.id,
            ]
            
            for field in selected_fields:
                if field == 'timestamp':
                    value = record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    value = getattr(record, field, '')
                row.append(value)
                
            writer.writerow(row)
            
        return response
        
    elif format_type == 'excel':
        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Station Data')
        
        # Add bold format for headers
        bold = workbook.add_format({'bold': True})
        
        # Write headers
        headers = ['Station Name', 'Station ID'] + [field for field in selected_fields]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold)
        
        # Write data rows
        for row_idx, record in enumerate(data, start=1):
            worksheet.write(row_idx, 0, station.name)
            worksheet.write(row_idx, 1, station.station_id or str(station.id))
            
            for col_idx, field in enumerate(selected_fields, start=2):
                if field == 'timestamp':
                    value = record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    value = getattr(record, field, '')
                worksheet.write(row_idx, col_idx, value)
        
        workbook.close()
        
        # Prepare the response
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response
        
    elif format_type == 'json':
        # Create list of dictionaries
        result = []
        for record in data:
            item = {
                'station_name': station.name,
                'station_id': station.station_id or station.id
            }
            
            for field in selected_fields:
                if field == 'timestamp':
                    item[field] = record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    item[field] = getattr(record, field, None)
                    
            result.append(item)
            
        # Create JSON response
        response = HttpResponse(json.dumps(result, default=str), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
        return response
    
    else:
        messages.error(request, f"Unsupported format: {format_type}")
        return redirect('maps:station_data_export', station_id=station_id)

class ClimateDataViewSet(viewsets.ModelViewSet):
    queryset = ClimateData.objects.all().select_related('station')
    serializer_class = ClimateDataSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['station', 'data_quality', 'year', 'month']
    ordering_fields = ['timestamp', 'temperature', 'precipitation']
    
    def get_serializer_class(self):
        if self.request.query_params.get('format') == 'geojson':
            return GeoJSONClimateDataSerializer
        return ClimateDataSerializer
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        # If GeoJSON format is requested, wrap in a FeatureCollection
        if request.query_params.get('format') == 'geojson':
            return Response({
                'type': 'FeatureCollection',
                'features': serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        
        # If GeoJSON format is requested, wrap in a FeatureCollection
        if request.query_params.get('format') == 'geojson':
            return Response({
                'type': 'FeatureCollection',
                'features': serializer.data
            })
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get the most recent climate data for all stations"""
        hours = int(request.query_params.get('hours', 24))
        data_types = request.query_params.getlist('data_types', [])
        since = timezone.now() - timedelta(hours=hours)
        
        # Get latest reading for each station
        subquery = ClimateData.objects.filter(
            station=OuterRef('station'),
            timestamp__gte=since
        ).order_by('-timestamp').values('id')[:1]
        
        query = ClimateData.objects.filter(
            id__in=Subquery(subquery)
        ).select_related('station')
        
        # Filter by data types if specified
        if data_types:
            conditions = []
            for data_type in data_types:
                if hasattr(ClimateData, data_type):
                    conditions.append(~models.Q(**{data_type: None}))
            if conditions:
                query = query.filter(reduce(operator.or_, conditions))
        
        serializer = self.get_serializer(query, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """Override create to check for alerts when new data is added"""
        climate_data = serializer.save()
        
        # Check for potential alerts
        alerts = check_for_alerts(climate_data)
        
        # Create alerts and send notifications
        for alert_data in alerts:
            create_alert_from_detection(climate_data.station, alert_data)
        
        return climate_data

@api_view(['POST'])
def push_station_data(request, station_id):
    """API endpoint for pushing data to a station's stack"""
    try:
        station = get_object_or_404(WeatherStation, pk=station_id)
        serializer = StackedDataSerializer(data=request.data)
        
        if serializer.is_valid():
            success = station.push_data(serializer.validated_data)
            if success:
                return Response({
                    'success': True, 
                    'stack_size': station.stack_size(),
                    'message': 'Data added to stack successfully'
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Stack is full'
                }, status=400)
        else:
            return Response(serializer.errors, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def process_station_stack(request, station_id):
    """API endpoint for processing a station's data stack"""
    try:
        station = get_object_or_404(WeatherStation, pk=station_id)
        records_processed = station.process_data_stack()
        
        return Response({
            'success': True,
            'records_processed': records_processed,
            'message': f'Successfully processed {records_processed} records'
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_stack_info(request, station_id):
    """API endpoint for getting information about a station's data stack"""
    try:
        station = get_object_or_404(WeatherStation, pk=station_id)
        latest_data = station.peek_data()
        
        data = {
            'station_id': station.id,
            'station_name': station.name,
            'stack_size': station.stack_size(),
            'max_stack_size': station.max_stack_size,
            'last_data_feed': station.last_data_feed,
            'auto_process': station.auto_process,
            'process_threshold': station.process_threshold,
            'latest_data': latest_data
        }
        
        serializer = StackInfoSerializer(data)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def clear_station_stack(request, station_id):
    """API endpoint for clearing a station's data stack"""
    try:
        station = get_object_or_404(WeatherStation, pk=station_id)
        import json
        
        # Get current stack size for reporting
        stack_size = station.stack_size()
        
        # Clear the stack
        station.data_stack = json.dumps([])
        station.save(update_fields=['data_stack'])
        
        return Response({
            'success': True,
            'cleared_items': stack_size,
            'message': f'Successfully cleared {stack_size} items from the stack'
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)

def station_data_stack_view(request, station_id):
    """View for managing a station's data stack in a template"""
    try:
        station = get_object_or_404(WeatherStation, pk=station_id)
        
        # Handle stack configuration updates if form submitted
        if request.method == 'POST':
            from .forms import DataStackSettingsForm
            form = DataStackSettingsForm(request.POST, instance=station)
            if form.is_valid():
                form.save()
                messages.success(request, "Data stack settings updated successfully")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            from .forms import DataStackSettingsForm
            form = DataStackSettingsForm(instance=station)
        
        # Get stack data for display
        try:
            import json
            stack_data = json.loads(station.data_stack) if station.data_stack else []
            # Limit to last 50 items to prevent overwhelming the page
            stack_preview = stack_data[-50:] if len(stack_data) > 50 else stack_data
        except:
            stack_preview = []
        
        context = {
            'station': station,
            'stack_size': station.stack_size(),
            'max_stack_size': station.max_stack_size,
            'form': form,
            'stack_preview': stack_preview,
            'has_data': len(stack_preview) > 0,
            'last_data_feed': station.last_data_feed,
        }
        
        return render(request, 'maps/station_data_stack.html', context)
        
    except WeatherStation.DoesNotExist:
        messages.error(request, f"Weather station with ID {station_id} does not exist.")
        return redirect('maps:map')

@api_view(['GET'])
def climate_data_recent(request):
    """Get recent climate data for all stations"""
    hours = int(request.query_params.get('hours', 24))
    since = timezone.now() - timedelta(hours=hours)
    
    # Get latest reading for each station
    climate_data = []
    stations = WeatherStation.objects.filter(is_active=True)
    
    for station in stations:
        latest = ClimateData.objects.filter(
            station=station,
            timestamp__gte=since
        ).order_by('-timestamp').first()
        
        if latest:
            climate_data.append(latest)
    
    serializer = ClimateDataSerializer(climate_data, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def station_climate_data(request, station_id):
    """Get climate data for a specific station - fallback endpoint for the map JS"""
    try:
        station = get_object_or_404(WeatherStation, pk=station_id)
        days = int(request.query_params.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        data = ClimateData.objects.filter(
            station=station,
            timestamp__gte=start_date
        ).order_by('-timestamp')
        
        serializer = ClimateDataSerializer(data, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

def secure_export_download(request, export_id, signature):
    """
    Securely serve export files with signature verification
    """
    try:
        # Verify the signature
        signer = Signer()
        expected_signature = signer.sign(str(export_id)).split(':')[1]
        
        if signature != expected_signature:
            raise BadSignature("Invalid signature")
        
        # Get the export object
        export = get_object_or_404(DataExport, pk=export_id)
        
        # Check if file exists
        if not export.file or not os.path.exists(export.file.path):
            raise Http404("Export file does not exist")
        
        # Check if user has permission to download this export
        if request.user != export.user and not request.user.is_staff:
            return HttpResponse("Permission denied", status=403)
        
        # Update download count
        export.download_count += 1
        export.last_downloaded = timezone.now()
        export.save(update_fields=['download_count', 'last_downloaded'])
        
        # Serve the file
        response = FileResponse(open(export.file.path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(export.file.name)}"'
        
        # Set Content-Type based on file extension
        file_ext = os.path.splitext(export.file.name)[1].lower()
        if file_ext == '.csv':
            response['Content-Type'] = 'text/csv'
        elif file_ext == '.xlsx':
            response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif file_ext == '.json':
            response['Content-Type'] = 'application/json'
        elif file_ext == '.geojson':
            response['Content-Type'] = 'application/geo+json'
        
        return response
        
    except BadSignature:
        return HttpResponse("Invalid or expired download link", status=403)
    except Exception as e:
        logging.error(f"Error serving export file: {str(e)}")
        return HttpResponse("Error serving file", status=500)

class ImportSuccessView(TemplateView):
    """View to display results of successful data imports"""
    template_name = 'maps/import_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get import results from session
        import_results = self.request.session.get('import_results', {})
        
        context.update({
            'import_results': import_results,
            'success_count': import_results.get('success', 0),
            'error_count': import_results.get('error', 0),
            'import_type': import_results.get('type', 'Data'),
            'has_errors': import_results.get('error', 0) > 0,
            'errors': import_results.get('errors', [])[:10],  # Limit displayed errors
            'has_more_errors': len(import_results.get('errors', [])) > 10,
            'timestamp': timezone.now()
        })
        
        return context

# ...existing code...

@api_view(['GET'])
def station_graph_data(request, station_id):
    """API endpoint for fetching station graph data in continuous time series format"""
    try:
        station = WeatherStation.objects.get(pk=station_id)
    except WeatherStation.DoesNotExist:
        return JsonResponse({'error': 'Station not found'}, status=404)
    
    # Get query parameters
    period = request.GET.get('period', 'week')  # day, week, month, year
    data_type = request.GET.get('data_type', 'temperature')  # temperature, humidity, precipitation, etc.
    resolution = request.GET.get('resolution', 'auto')  # hourly, daily, auto
    
    # Determine time range based on period
    now = datetime.now()
    if period == 'day':
        start_date = now - timedelta(days=1)
        date_trunc = TruncHour
        date_format = '%H:%M'
        if resolution == 'auto':
            resolution = 'hourly'
    elif period == 'week':
        start_date = now - timedelta(days=7)
        date_trunc = TruncDay if resolution in ['daily', 'auto'] else TruncHour
        date_format = '%a %d' if resolution in ['daily', 'auto'] else '%m-%d %H:%M'
    elif period == 'month':
        start_date = now - timedelta(days=30)
        date_trunc = TruncDay if resolution in ['daily', 'auto'] else TruncHour
        date_format = '%b %d' if resolution in ['daily', 'auto'] else '%m-%d %H:%M'
    elif period == 'year':
        start_date = now - timedelta(days=365)
        date_trunc = TruncDay
        date_format = '%b %Y'
    else:
        start_date = now - timedelta(days=7)  # Default to week
        date_trunc = TruncDay
        date_format = '%a %d'
    
    # Query data with appropriate time grouping
    queryset = ClimateData.objects.filter(
        station=station,
        timestamp__gte=start_date,
        timestamp__lte=now
    ).annotate(
        date=date_trunc('timestamp')
    ).values('date')
    
    # Build aggregation based on data type
    aggregation = {}
    if data_type == 'temperature' or data_type == 'all':
        aggregation.update({
            'avg_temp': Avg('temperature'),
            'min_temp': Min('temperature'),
            'max_temp': Max('temperature'),
        })
    if data_type == 'humidity' or data_type == 'all':
        aggregation.update({
            'avg_humidity': Avg('humidity'),
        })
    if data_type == 'precipitation' or data_type == 'all':
        aggregation.update({
            'total_precipitation': Sum('precipitation'),
        })
    if data_type == 'wind' or data_type == 'all':
        aggregation.update({
            'avg_wind_speed': Avg('wind_speed'),
            'max_wind_speed': Max('wind_speed'),
        })
    if data_type == 'pressure' or data_type == 'all':
        aggregation.update({
            'avg_pressure': Avg('barometric_pressure'),
        })
    
    # If no specific data type is requested or invalid, return all
    if not aggregation:
        aggregation = {
            'avg_temp': Avg('temperature'),
            'avg_humidity': Avg('humidity'),
            'total_precipitation': Sum('precipitation'),
            'avg_wind_speed': Avg('wind_speed'),
        }
    
    data = queryset.order_by('date').annotate(**aggregation)
    
    # Format results for continuous time series
    formatted_data = {
        'station_name': station.name,
        'station_id': station.id,
        'period': period,
        'resolution': resolution,
        'timestamps': [],
        'datasets': {}
    }
    
    # Initialize datasets based on aggregation keys
    for key in aggregation.keys():
        formatted_data['datasets'][key] = []
    
    # Populate datasets ensuring continuous time series
    last_date = None
    
    for entry in data:
        # Format the date
        date_obj = entry['date']
        if isinstance(date_obj, datetime):
            date_str = date_obj.strftime(date_format)
            timestamp = int(date_obj.timestamp() * 1000)  # Convert to milliseconds for JS
        else:
            date_str = str(date_obj)
            timestamp = None
        
        formatted_data['timestamps'].append({
            'display': date_str,
            'timestamp': timestamp
        })
        
        # Add values for each dataset
        for key in aggregation.keys():
            value = entry.get(key)
            # Handle null values to maintain continuous graph
            formatted_data['datasets'][key].append(
                round(float(value), 2) if value is not None else None
            )
    
    return JsonResponse(formatted_data)

# ...existing code...

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from .forms import StackDataEntryForm
from .models import WeatherStation

# ...existing code...

class ImportSuccessView(TemplateView):
    template_name = "maps/import_success.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['import_count'] = self.request.session.get('import_count', 0)
        context['import_type'] = self.request.session.get('import_type', 'data')
        return context


def station_data_view(request):
    """
    View for displaying detailed station data with download options
    """
    station_id = request.GET.get('id')
    
    # For custom stations, we'll handle the data in JavaScript
    # This view just renders the template
    
    context = {
        'title': 'Weather Station Data',
        'station_id': station_id
    }
    
    return render(request, 'maps/station_data.html', context)


def station_statistics_view(request, station_id):
    """
    View for displaying station statistics
    Can handle both numeric IDs (database stations) and string IDs (custom stations)
    """
    # Handle both numeric and string IDs
    try:
        # First try to convert to int if it looks like a number
        if isinstance(station_id, str) and station_id.isdigit():
            numeric_id = int(station_id)
            station = get_object_or_404(WeatherStation, id=numeric_id)
        else:
            # If it's already a number or a non-numeric string ID
            if isinstance(station_id, str) and station_id.startswith('ws_'):
                # Handle 'ws_X' format by extracting the number
                numeric_part = station_id.split('_')[1]
                if numeric_part.isdigit():
                    station = get_object_or_404(WeatherStation, id=int(numeric_part))
                else:
                    # This is a custom station ID
                    return redirect(f'/maps/station-data/?id={station_id}')
            else:
                # Regular numeric ID
                station = get_object_or_404(WeatherStation, id=station_id)
        
        # Get climate data for this station
        recent_data = ClimateData.objects.filter(
            station=station,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).order_by('-timestamp')
        
        # Calculate statistics
        stats = {
            'readings_count': recent_data.count(),
            'temperature': {
                'avg': recent_data.aggregate(Avg('temperature'))['temperature__avg'],
                'max': recent_data.aggregate(Max('temperature'))['temperature__max'],
                'min': recent_data.aggregate(Min('temperature'))['temperature__min'],
            },
            'precipitation': {
                'avg': recent_data.aggregate(Avg('precipitation'))['precipitation__avg'],
                'max': recent_data.aggregate(Max('precipitation'))['precipitation__max'],
                'min': recent_data.aggregate(Min('precipitation'))['precipitation__min'],
                'total': recent_data.aggregate(Sum('precipitation'))['precipitation__sum'],
            },
            'humidity': {
                'avg': recent_data.aggregate(Avg('humidity'))['humidity__avg'],
                'max': recent_data.aggregate(Max('humidity'))['humidity__max'],
                'min': recent_data.aggregate(Min('humidity'))['humidity__min'],
            },
        }
        
        context = {
            'station': station,
            'recent_data': recent_data[:10],  # Show only the 10 most recent readings
            'stats': stats,
            'title': f'{station.name} Statistics',
        }
        
        return render(request, 'maps/station_statistics.html', context)
        
    except Exception as e:
        messages.error(request, f"Error retrieving station statistics: {str(e)}")
        return redirect('maps:map')  # Make sure 'maps:map' is the correct namespace

# ...existing code...

@login_required
@permission_required('maps.add_climatedata')
def stack_data_entry(request):
    """View for adding climate data to a station's stack"""    
    stations = WeatherStation.objects.filter(is_active=True)
    
    if request.method == 'POST':
        form = StackDataEntryForm(request.POST)
        if form.is_valid():
            success, message = form.add_to_stack()
            if success:
                messages.success(request, message)
                # Redirect to the same page to clear the form
                return redirect(reverse('maps:stack_data_entry'))
            else:
                messages.error(request, message)
    else:
        # Pre-select station if provided in query params
        station_id = request.GET.get('station')
        if station_id:
            try:
                station = stations.get(id=station_id)
                form = StackDataEntryForm(initial={'station': station})
            except WeatherStation.DoesNotExist:
                form = StackDataEntryForm()
        else:
            form = StackDataEntryForm()
    
    # Get stack information for all stations
    station_stacks = []
    for station in stations:
        stack_size = station.stack_size()
        station_stacks.append({
            'id': station.id,
            'name': station.name,
            'stack_size': stack_size,
            'max_size': station.max_stack_size,
            'auto_process': station.auto_process,
            'threshold': station.process_threshold,
            'percentage': (stack_size / station.max_stack_size * 100) if station.max_stack_size > 0 else 0,
        })
    
    context = {
        'form': form,
        'stations': station_stacks,
        'title': 'Daily Data Entry',
    }
    
    return render(request, 'maps/stack_data_entry.html', context)

@login_required
@permission_required('maps.add_climatedata')
def process_station_stack(request, station_id):
    """Process the data stack for a specific station"""
    station = get_object_or_404(WeatherStation, id=station_id)
    
    if request.method == 'POST':
        records_processed = station.process_data_stack()
        if records_processed > 0:
            messages.success(request, f"Successfully processed {records_processed} readings from {station.name}.")
        else:
            messages.info(request, f"No data found to process for {station.name}.")
    
    # Redirect back to the data entry page
    return redirect(reverse('maps:stack_data_entry'))