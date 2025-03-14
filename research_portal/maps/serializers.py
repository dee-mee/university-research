from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import WeatherStation, ClimateData, DataExport

class WeatherStationSerializer(GeoFeatureModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = WeatherStation
        geo_field = 'location'
        fields = (
            'id', 'name', 'description', 'location', 'latitude', 'longitude',
            'altitude', 'is_active', 'date_installed'
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
    location = serializers.SerializerMethodField()
    
    class Meta:
        model = ClimateData
        geo_field = 'location'
        fields = (
            'id', 'station', 'station_name', 'location', 'timestamp', 'temperature', 
            'humidity', 'precipitation', 'air_quality_index', 'wind_speed', 
            'wind_direction', 'barometric_pressure', 'cloud_cover', 'soil_moisture', 
            'water_level', 'data_quality', 'uv_index'
        )
    
    def get_location(self, obj):
        return obj.station.location


class DataExportSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    station_name = serializers.CharField(source='station.name', read_only=True)
    
    class Meta:
        model = DataExport
        fields = (
            'id', 'user', 'user_email', 'station', 'station_name', 
            'export_format', 'date_from', 'date_to', 'created_at'
        )