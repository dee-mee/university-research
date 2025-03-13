# views.py
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Avg, Max, Min
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
import csv
import json
from datetime import datetime, timedelta
import io

from .models import WeatherStation, ClimateData
from .serializers import (
    WeatherStationSerializer,
    ClimateDataSerializer,
    GeoJSONClimateDataSerializer
)
from .permissions import IsAdminOrReadOnly
from django.views.generic import TemplateView

class MapView(TemplateView):
    template_name = 'maps/map.html'

class WeatherStationViewSet(viewsets.ModelViewSet):
    queryset = WeatherStation.objects.all()
    serializer_class = WeatherStationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'date_installed']
    
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