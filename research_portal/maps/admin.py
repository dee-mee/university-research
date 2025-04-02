from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import (
    Country, WeatherStation, ClimateData, WeatherDataType,
    DataExport, WeatherAlert
)

@admin.register(Country)
class CountryAdmin(OSMGeoAdmin):
    list_display = ('name', 'code', 'is_southern_hemisphere')
    search_fields = ('name', 'code')
    list_filter = ('is_southern_hemisphere',)
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_southern_hemisphere')
        }),
        ('Geography', {
            'fields': ('boundary',),
            'classes': ('collapse',),
        }),
    )

@admin.register(WeatherStation)
class WeatherStationAdmin(OSMGeoAdmin):
    list_display = ('name', 'station_id', 'country', 'is_active', 'date_installed')
    list_filter = ('is_active', 'country', 'date_installed')
    search_fields = ('name', 'station_id', 'description')
    readonly_fields = ('created_at', 'updated_at', 'stack_size')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'station_id', 'description')
        }),
        ('Location', {
            'fields': ('location', 'altitude', 'country', 'region')
        }),
        ('Status', {
            'fields': ('is_active', 'date_installed', 'date_decommissioned')
        }),
        ('Data Types Available', {
            'fields': (
                'has_temperature', 'has_precipitation', 'has_humidity',
                'has_wind', 'has_air_quality', 'has_soil_moisture', 'has_water_level'
            )
        }),
        ('Data Stack Configuration', {
            'fields': ('max_stack_size', 'auto_process', 'process_threshold', 'stack_size')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_data_feed'),
            'classes': ('collapse',)
        }),
    )
    
    def stack_size(self, obj):
        """Display the current size of the data stack"""
        return obj.stack_size() if obj else 0
    stack_size.short_description = "Current Stack Size"

@admin.register(ClimateData)
class ClimateDataAdmin(admin.ModelAdmin):
    list_display = ('station', 'timestamp', 'temperature', 'precipitation', 'data_quality')
    list_filter = ('station', 'year', 'month', 'season', 'data_quality')
    date_hierarchy = 'timestamp'
    search_fields = ('station__name',)
    readonly_fields = ('created_at', 'updated_at', 'year', 'month', 'season')
    
    fieldsets = (
        (None, {
            'fields': ('station', 'timestamp', 'data_quality')
        }),
        ('Auto-calculated Fields', {
            'fields': ('year', 'month', 'season'),
            'classes': ('collapse',)
        }),
        ('Temperature & Humidity', {
            'fields': ('temperature', 'humidity'),
        }),
        ('Precipitation', {
            'fields': ('precipitation',),
        }),
        ('Wind', {
            'fields': ('wind_speed', 'wind_direction'),
        }),
        ('Air & Pressure', {
            'fields': ('air_quality_index', 'barometric_pressure', 'uv_index'),
        }),
        ('Surface Conditions', {
            'fields': ('cloud_cover', 'soil_moisture', 'water_level'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(WeatherDataType)
class WeatherDataTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'unit')
    search_fields = ('name', 'display_name')
    fieldsets = (
        (None, {
            'fields': ('name', 'display_name', 'description', 'icon')
        }),
        ('Validation', {
            'fields': ('unit', 'min_value', 'max_value'),
        }),
    )

@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'export_format', 'created_at', 'status', 'download_count')
    list_filter = ('status', 'export_format', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'download_count', 'last_downloaded')
    search_fields = ('user__username', 'user__email')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'status', 'export_format', 'include_metadata')
        }),
        ('Data Selection', {
            'fields': ('stations', 'country', 'data_types', 'bounding_box')
        }),
        ('Time Period', {
            'fields': ('date_from', 'date_to', 'years', 'min_data_quality')
        }),
        ('Export Details', {
            'fields': ('file', 'download_count', 'last_downloaded', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(WeatherAlert)
class WeatherAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'station', 'data_type', 'severity', 'status', 'created_at')
    list_filter = ('severity', 'status', 'data_type')
    search_fields = ('title', 'description', 'station__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'station', 'country', 'data_type')
        }),
        ('Alert Details', {
            'fields': ('threshold_value', 'severity', 'status', 'affected_area')
        }),
        ('Notifications', {
            'fields': ('notify_email', 'notify_sms', 'notify_push')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at'),
            'classes': ('collapse',)
        }),
    )