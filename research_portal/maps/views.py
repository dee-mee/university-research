
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

import csv
import json
import datetime
from django.core.serializers.json import DjangoJSONEncoder

from .models import LocationMarker, EnvironmentalData, UserMarkerAnnotation, AlertThreshold, DataSource
from .serializers import (
    LocationMarkerSerializer, LocationMarkerDetailSerializer,
    EnvironmentalDataSerializer, UserMarkerAnnotationSerializer,
    AlertThresholdSerializer
)

# View for rendering the main map page
def map_view(request):
    return render(request, 'maps/map.html')

# View for marker details
def marker_detail_view(request, marker_id):
    marker = get_object_or_404(LocationMarker, id=marker_id)
    return render(request, 'maps/marker_detail.html', {'marker': marker})

# API ViewSets
class LocationMarkerViewSet(viewsets.ModelViewSet):
    queryset = LocationMarker.objects.all()
    serializer_class = LocationMarkerSerializer
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LocationMarkerDetailSerializer
        return LocationMarkerSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context
    
    @action(detail=True, methods=['get'])
    def download_data(self, request, pk=None):
        marker = self.get_object()
        format_type = request.query_params.get('format', 'csv')
        
        # Get filtering parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Filter data
        data_queryset = marker.environmental_data.all()
        if start_date:
            data_queryset = data_queryset.filter(timestamp__gte=start_date)
        if end_date:
            data_queryset = data_queryset.filter(timestamp__lte=end_date)
            
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{marker.name}_data.csv"'
            
            writer = csv.writer(response)
            # Write header
            writer.writerow([
                'Timestamp', 'Temperature', 'Humidity', 'Precipitation', 'Air Quality',
                'Wind Speed', 'Wind Direction', 'Barometric Pressure', 'UV Index',
                'Visibility', 'Cloud Cover', 'Soil Moisture', 'Water Level',
                'Vegetation Index', 'Data Quality', 'Data Source'
            ])
            
            # Write data rows
            for data in data_queryset:
                writer.writerow([
                    data.timestamp, data.temperature, data.humidity, data.precipitation,
                    data.air_quality_index, data.wind_speed, data.wind_direction,
                    data.barometric_pressure, data.uv_index, data.visibility,
                    data.cloud_cover, data.soil_moisture, data.water_level,
                    data.vegetation_index, data.data_quality,
                    data.data_source.name if data.data_source else 'Unknown'
                ])
            
            return response
            
        elif format_type == 'json':
            data = []
            for item in data_queryset:
                data_dict = {
                    'timestamp': item.timestamp,
                    'temperature': item.temperature,
                    'humidity': item.humidity,
                    'precipitation': item.precipitation,
                    'air_quality_index': item.air_quality_index,
                    'wind_speed': item.wind_speed,
                    'wind_direction': item.wind_direction,
                    'barometric_pressure': item.barometric_pressure,
                    'uv_index': item.uv_index,
                    'visibility': item.visibility,
                    'cloud_cover': item.cloud_cover,
                    'soil_moisture': item.soil_moisture,
                    'water_level': item.water_level,
                    'vegetation_index': item.vegetation_index,
                    'data_quality': item.data_quality,
                    'data_source': item.data_source.name if item.data_source else 'Unknown'
                }
                data.append(data_dict)
                
            response = HttpResponse(
                json.dumps(data, cls=DjangoJSONEncoder),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="{marker.name}_data.json"'
            return response
            
        # Default to CSV if format is not specified or invalid
        return Response(
            {"detail": "Invalid format specified. Use 'csv' or 'json'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=['get'])
    def heatmap_data(self, request):
        """Returns data formatted for heatmap visualization"""
        metric = request.query_params.get('metric', 'temperature')
        
        # Ensure metric is valid
        valid_metrics = [
            'temperature', 'humidity', 'precipitation', 'air_quality_index',
            'wind_speed', 'barometric_pressure', 'uv_index', 'visibility',
            'cloud_cover', 'soil_moisture', 'water_level', 'vegetation_index'
        ]
        
        if metric not in valid_metrics:
            return Response(
                {"detail": f"Invalid metric. Choose from: {', '.join(valid_metrics)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the latest data for each marker
        heatmap_data = []
        for marker in LocationMarker.objects.all():
            latest_data = marker.environmental_data.first()
            if latest_data:
                # Get the value for the requested metric
                value = getattr(latest_data, metric, None)
                if value is not None:
                    heatmap_data.append({
                        'lat': marker.latitude,
                        'lng': marker.longitude,
                        'value': value
                    })
        
        return Response(heatmap_data)

class EnvironmentalDataViewSet(viewsets.ModelViewSet):
    queryset = EnvironmentalData.objects.all()
    serializer_class = EnvironmentalDataSerializer
    
    @action(detail=False, methods=['get'])
    def historical_trends(self, request):
        """Returns historical trends data for visualization"""
        marker_id = request.query_params.get('marker_id')
        metric = request.query_params.get('metric', 'temperature')
        days = int(request.query_params.get('days', 30))
        
        if not marker_id:
            return Response(
                {"detail": "marker_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate date range
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days)
        
        # Get data
        try:
            marker = LocationMarker.objects.get(id=marker_id)
            data = marker.environmental_data.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            # Format response
            result = {
                'marker_name': marker.name,
                'metric': metric,
                'data': []
            }
            
            for item in data:
                value = getattr(item, metric, None)
                if value is not None:
                    result['data'].append({
                        'timestamp': item.timestamp,
                        'value': value
                    })
            
            return Response(result)
        except LocationMarker.DoesNotExist:
            return Response(
                {"detail": "Marker not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class UserMarkerAnnotationViewSet(viewsets.ModelViewSet):
    queryset = UserMarkerAnnotation.objects.all()
    serializer_class = UserMarkerAnnotationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserMarkerAnnotation.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class AlertThresholdViewSet(viewsets.ModelViewSet):
    queryset = AlertThreshold.objects.all()
    serializer_class = AlertThresholdSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return AlertThreshold.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)