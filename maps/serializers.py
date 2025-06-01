from datetime import timezone
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import WeatherAlert, WeatherStation, ClimateData, DataExport, Country, WeatherDataType
from .field_models import DeviceType, FieldDevice, DeviceCalibration, FieldDataUpload

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
            'file_url', 'status', 'error_log', 'created_at',
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


class DeviceTypeSerializer(serializers.ModelSerializer):
    """Serializer for DeviceType model"""
    class Meta:
        model = DeviceType
        fields = (
            'id', 'name', 'manufacturer', 'model_number', 'description',
            'communication_protocol', 'power_source', 'battery_life_days',
            'firmware_version', 'has_temperature', 'has_precipitation',
            'has_humidity', 'has_wind', 'has_air_quality', 'has_soil_moisture',
            'has_water_level', 'created_at', 'updated_at'
        )


class FieldDeviceSerializer(GeoFeatureModelSerializer):
    """Serializer for FieldDevice model"""
    device_type_name = serializers.CharField(source='device_type.name', read_only=True)
    weather_station_name = serializers.CharField(source='weather_station.name', read_only=True)
    battery_status = serializers.SerializerMethodField()
    
    class Meta:
        model = FieldDevice
        geo_field = 'location'
        fields = (
            'id', 'device_id', 'name', 'device_type', 'device_type_name',
            'weather_station', 'weather_station_name', 'location', 'status',
            'installation_date', 'last_communication', 'battery_level',
            'battery_status', 'signal_strength', 'firmware_version',
            'transmission_interval', 'notes', 'created_at', 'updated_at'
        )

    def get_battery_status(self, obj):
        """Return battery status as a string with color coding"""
        if obj.battery_level is None:
            return "Unknown"
        elif obj.battery_level < 20:
            return "Critical"
        elif obj.battery_level < 40:
            return "Low"
        elif obj.battery_level < 70:
            return "Medium"
        return "Good"


class DeviceCalibrationSerializer(serializers.ModelSerializer):
    """Serializer for DeviceCalibration model"""
    device_name = serializers.CharField(source='device.name', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    
    class Meta:
        model = DeviceCalibration
        fields = (
            'id', 'device', 'device_name', 'calibration_date',
            'next_calibration_date', 'performed_by', 'performed_by_name',
            'temperature_offset', 'humidity_offset', 'pressure_offset',
            'certificate_number', 'notes', 'created_at', 'updated_at'
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

class FieldDataUploadSerializer(serializers.ModelSerializer):
    """Serializer for FieldDataUpload model"""
    device_type_name = serializers.CharField(source='device_type.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = FieldDataUpload
        fields = (
            'id', 'title', 'description', 'data_file', 'data_format',
            'device_type', 'device_type_name', 'upload_date', 'status',
            'processed_count', 'error_count', 'error_log', 'created_by',
            'created_by_name'
        )
        read_only_fields = ('processed_count', 'error_count', 'error_log', 'status', 'upload_date', 'created_by')
    process_threshold = serializers.IntegerField(read_only=True)
    latest_data = StackedDataSerializer(read_only=True)

