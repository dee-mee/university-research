# serializers.py
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import WeatherStation, ClimateData

class WeatherStationSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = WeatherStation
        geo_field = 'location'
        fields = ('id', 'name', 'description', 'location', 'altitude', 'is_active', 'date_installed')


class ClimateDataSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    
    class Meta:
        model = ClimateData
        fields = (
            'id', 'station', 'station_name', 'timestamp', 'temperature', 'humidity',
            'precipitation', 'air_quality_index', 'wind_speed', 'wind_direction',
            'barometric_pressure', 'cloud_cover', 'soil_moisture', 'water_level',
            'data_quality', 'uv_index'
        )


class GeoJSONClimateDataSerializer(GeoFeatureModelSerializer):
    """Serializer for returning climate data with station location as GeoJSON"""
    station_name = serializers.CharField(source='station.name', read_only=True)
    location = serializers.SerializerMethodField()
    
    class Meta:
        model = ClimateData
        geo_field = 'location'
        fields = (
            'id', 'station', 'station_name', 'location', 'timestamp', 'temperature', 'humidity',
            'precipitation', 'air_quality_index', 'wind_speed', 'wind_direction',
            'barometric_pressure', 'cloud_cover', 'soil_moisture', 'water_level',
            'data_quality', 'uv_index'
        )
    
    def get_location(self, obj):
        return obj.station.location

