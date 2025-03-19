from datetime import timezone
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import WeatherAlert, WeatherStation, ClimateData, DataExport, Country, WeatherDataType

class WeatherStationSerializer(GeoFeatureModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    country_name = serializers.CharField(source='country.name', read_only=True)
    
    class Meta:
        model = WeatherStation
        geo_field = 'location'
        fields = (
            'id', 'name', 'description', 'location', 'latitude', 'longitude',
            'altitude', 'is_active', 'date_installed', 'country_name'
        )
        
    def get_latitude(self, obj):
        return obj.location.y
    
    def get_longitude(self, obj):
        return obj.location.x
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['geometry'] = {
            'type': 'Point',
            'coordinates': [instance.longitude, instance.latitude]
        }
        print(f"Serialized station: {instance.name}, GeoJSON: {representation}")
        return representation
    
class ClimateDataSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_location = serializers.SerializerMethodField()
    
    class Meta:
        model = ClimateData
        fields = (
            'id', 'station', 'station_name', 'station_location', 'timestamp', 
            'temperature', 'humidity', 'precipitation', 'air_quality_index', 
            'wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover', 
            'soil_moisture', 'water_level', 'data_quality', 'uv_index'
        )
    
    def get_station_location(self, obj):
        if obj.station and obj.station.location:
            return {
                'type': 'Point',
                'coordinates': [obj.station.longitude, obj.station.latitude]
            }
        return None


class GeoJSONClimateDataSerializer(GeoFeatureModelSerializer):
    """Serializer for returning climate data with station location as GeoJSON"""
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id = serializers.IntegerField(source='station.id', read_only=True)
    
    class Meta:
        model = ClimateData
        geo_field = 'station__location'  # Use dot notation to access station's location
        fields = (
            'id', 'station_id', 'station_name', 'timestamp', 'temperature', 
            'humidity', 'precipitation', 'air_quality_index', 'wind_speed', 
            'wind_direction', 'barometric_pressure', 'cloud_cover', 'soil_moisture', 
            'water_level', 'data_quality', 'uv_index'
        )
    
    def get_location(self, obj):
        # Return the actual Point object from the station
        if obj.station and obj.station.location:
            return obj.station.location
        return None


class DataExportSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    station_names = serializers.SerializerMethodField()
    country_name = serializers.CharField(source='country.name', read_only=True)
    
    class Meta:
        model = DataExport
        fields = (
            'id', 'user', 'user_email', 'stations', 'station_names', 'country', 'country_name', 
            'export_format', 'date_from', 'date_to', 'created_at', 'status'
        )
    
    def get_station_names(self, obj):
        return [station.name for station in obj.stations.all()]

class WeatherAlertSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    data_type_name = serializers.CharField(source='data_type.name', read_only=True)

    class Meta:
        model = WeatherAlert
        fields = (
            'id', 'station', 'station_name', 'country', 'country_name', 'title', 'description', 
            'data_type', 'data_type_name', 'parameter', 'threshold_value', 'severity', 'status', 
            'created_at', 'updated_at', 'resolved_at', 'notify_email', 'notify_sms', 'notify_push'
        )

