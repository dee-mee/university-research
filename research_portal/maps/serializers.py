from datetime import timezone
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import WeatherAlert, WeatherStation, ClimateData, DataExport, Country, WeatherDataType

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ('id', 'name', 'code')

class WeatherDataTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherDataType
        fields = ('id', 'name', 'display_name', 'description', 'unit', 'min_value', 'max_value', 'icon')

class WeatherStationSerializer(GeoFeatureModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    data_types = serializers.SerializerMethodField()
    stack_size = serializers.SerializerMethodField()
    last_data_feed = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = WeatherStation
        geo_field = 'location'
        fields = (
            'id', 'name', 'station_id', 'description', 'location', 
            'altitude', 'is_active', 'date_installed', 'date_decommissioned',
            'country', 'country_name', 'region', 'data_types', 
            'stack_size', 'last_data_feed', 'auto_process', 'process_threshold', 'max_stack_size'
        )
    
    def get_data_types(self, obj):
        return obj.available_data_types()
    
    def get_stack_size(self, obj):
        return obj.stack_size()

class ClimateDataSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_location = serializers.SerializerMethodField()
    
    class Meta:
        model = ClimateData
        fields = (
            'id', 'station', 'station_name', 'station_location', 
            'timestamp', 'year', 'month', 'data_quality',
            'temperature', 'humidity', 'precipitation', 
            'air_quality_index', 'wind_speed', 'wind_direction', 
            'barometric_pressure', 'cloud_cover', 'soil_moisture', 
            'water_level', 'uv_index'
        )
    
    def get_station_location(self, obj):
        if obj.station and obj.station.location:
            return {
                'type': 'Point',
                'coordinates': [obj.station.longitude, obj.station.latitude]
            }
        return None

class GeoJSONClimateDataSerializer(GeoFeatureModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    station_id = serializers.CharField(source='station.station_id', read_only=True)
    data_quality = serializers.CharField()
    
    class Meta:
        model = ClimateData
        geo_field = 'station__location'
        fields = (
            'id', 'station_id', 'station_name', 'timestamp', 
            'year', 'month', 'data_quality',
            'temperature', 'humidity', 'precipitation', 
            'air_quality_index', 'wind_speed', 'wind_direction', 
            'barometric_pressure', 'cloud_cover', 'soil_moisture', 
            'water_level', 'uv_index'
        )

class DataExportSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    station_names = serializers.SerializerMethodField()
    country_name = serializers.CharField(source='country.name', read_only=True)
    data_type_names = serializers.SerializerMethodField()
    
    class Meta:
        model = DataExport
        fields = (
            'id', 'user', 'user_email', 'stations', 'station_names',
            'country', 'country_name', 'data_types', 'data_type_names',
            'bounding_box', 'date_from', 'date_to', 'years',
            'min_data_quality', 'export_format', 'include_metadata',
            'file_url', 'status', 'error_message', 'created_at',
            'completed_at'
        )
    
    def get_station_names(self, obj):
        return [station.name for station in obj.stations.all()]
    
    def get_data_type_names(self, obj):
        return [dt.display_name for dt in obj.data_types.all()]

class WeatherAlertSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    data_type_info = WeatherDataTypeSerializer(source='data_type', read_only=True)

    class Meta:
        model = WeatherAlert
        fields = (
            'id', 'station', 'station_name', 'country', 'country_name',
            'title', 'description', 'data_type', 'data_type_info',
            'threshold_value', 'severity', 'status', 'affected_area',
            'created_at', 'updated_at', 'resolved_at',
            'notify_email', 'notify_sms', 'notify_push'
        )

class StackedDataSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField(required=False)
    temperature = serializers.FloatField(required=False)
    humidity = serializers.FloatField(required=False)
    precipitation = serializers.FloatField(required=False)
    air_quality_index = serializers.IntegerField(required=False)
    wind_speed = serializers.FloatField(required=False)
    wind_direction = serializers.FloatField(required=False)
    barometric_pressure = serializers.FloatField(required=False)
    cloud_cover = serializers.FloatField(required=False)
    soil_moisture = serializers.FloatField(required=False)
    water_level = serializers.FloatField(required=False)
    uv_index = serializers.FloatField(required=False)
    data_quality = serializers.ChoiceField(choices=ClimateData.QUALITY_CHOICES, default='medium', required=False)

class StackInfoSerializer(serializers.Serializer):
    station_id = serializers.IntegerField(read_only=True)
    station_name = serializers.CharField(read_only=True)
    stack_size = serializers.IntegerField(read_only=True)
    max_stack_size = serializers.IntegerField(read_only=True)
    last_data_feed = serializers.DateTimeField(read_only=True)
    auto_process = serializers.BooleanField(read_only=True)
    process_threshold = serializers.IntegerField(read_only=True)
    latest_data = StackedDataSerializer(read_only=True)

