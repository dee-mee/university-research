from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.html import format_html
from .models import WeatherStation, ClimateData, DataExport, Country, WeatherDataType, WeatherAlert

@admin.register(Country)
class CountryAdmin(GISModelAdmin):
    list_display = ('name', 'code', 'station_count')
    search_fields = ('name', 'code')
    
    def station_count(self, obj):
        return obj.stations.count()
    station_count.short_description = 'Number of Stations'


@admin.register(WeatherDataType)
class WeatherDataTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'unit', 'min_value', 'max_value')
    search_fields = ('name', 'display_name')
    list_filter = ('unit',)


@admin.register(WeatherStation)
class WeatherStationAdmin(GISModelAdmin):
    list_display = ('name', 'station_id', 'country', 'is_active', 'date_installed', 'data_types_available')
    list_filter = ('is_active', 'country', 'has_temperature', 'has_precipitation', 'has_humidity', 'has_wind', 'has_air_quality')
    search_fields = ('name', 'station_id', 'description', 'country__name')
    readonly_fields = ('created_at', 'updated_at', 'map_preview')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'station_id', 'description', 'is_active')
        }),
        ('Geographic Information', {
            'fields': ('location', 'map_preview', 'altitude', 'country', 'region')
        }),
        ('Station Timeline', {
            'fields': ('date_installed', 'date_decommissioned')
        }),
        ('Available Data Types', {
            'fields': ('has_temperature', 'has_precipitation', 'has_humidity', 'has_wind', 
                      'has_air_quality', 'has_soil_moisture', 'has_water_level')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def map_preview(self, obj):
        if obj and obj.location:
            return format_html(
                '<img src="https://maps.googleapis.com/maps/api/staticmap?center={},{}&zoom=12&size=400x300&maptype=roadmap'
                '&markers=color:red%7C{},{}&key=YOUR_API_KEY" width="400" height="300"/>',
                obj.latitude, obj.longitude, obj.latitude, obj.longitude
            )
        return "No location data"
    map_preview.short_description = "Map Preview"
    
    def data_types_available(self, obj):
        return ", ".join(obj.available_data_types())
    data_types_available.short_description = "Available Data"


class ClimateDataInline(admin.TabularInline):
    model = ClimateData
    extra = 0
    fields = ('timestamp', 'temperature', 'humidity', 'precipitation', 'data_quality')
    readonly_fields = ('created_at', 'year', 'month')
    can_delete = True
    max_num = 10


@admin.register(ClimateData)
class ClimateDataAdmin(admin.ModelAdmin):
    list_display = ('station', 'timestamp', 'year', 'month', 'temperature', 'humidity', 'precipitation', 'data_quality')
    list_filter = ('data_quality', 'station', 'year', 'month', 'station__country')
    search_fields = ('station__name', 'station__station_id')
    date_hierarchy = 'timestamp'
    readonly_fields = ('created_at', 'updated_at', 'year', 'month')
    
    fieldsets = (
        (None, {
            'fields': ('station', 'timestamp', 'year', 'month', 'data_quality')
        }),
        ('Atmospheric Conditions', {
            'fields': ('temperature', 'humidity', 'precipitation', 'air_quality_index', 'uv_index')
        }),
        ('Wind Data', {
            'fields': ('wind_speed', 'wind_direction', 'barometric_pressure', 'cloud_cover')
        }),
        ('Ground Conditions', {
            'fields': ('soil_moisture', 'water_level')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        # Optimize queryset by prefetching related objects
        return super().get_queryset(request).select_related('station', 'station__country')


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = ('user', 'export_format', 'date_from', 'date_to', 'created_at', 'status', 'country_filter')
    list_filter = ('export_format', 'status', 'created_at', 'country')
    readonly_fields = ('created_at', 'completed_at')
    filter_horizontal = ('stations', 'data_types')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'export_format', 'status', 'include_metadata')
        }),
        ('Data Selection Filters', {
            'fields': ('stations', 'country', 'data_types', 'min_data_quality')
        }),
        ('Geographic Filters', {
            'fields': ('bounding_box',),
        }),
        ('Time Filters', {
            'fields': ('date_from', 'date_to', 'years')
        }),
        ('Export Details', {
            'fields': ('file_url', 'error_message', 'created_at', 'completed_at')
        }),
    )
    
    def country_filter(self, obj):
        return obj.country.name if obj.country else "All Countries"
    country_filter.short_description = "Country Filter"


@admin.register(WeatherAlert)
class WeatherAlertAdmin(GISModelAdmin):
    list_display = ('title', 'station', 'data_type', 'severity', 'status', 'created_at')
    list_filter = ('severity', 'status', 'data_type', 'country')
    search_fields = ('title', 'description', 'station__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'severity', 'status')
        }),
        ('Alert Details', {
            'fields': ('station', 'country', 'data_type', 'threshold_value', 'affected_area')
        }),
        ('Timing', {
            'fields': ('created_at', 'updated_at', 'resolved_at')
        }),
        ('Notifications', {
            'fields': ('notify_email', 'notify_sms', 'notify_push'),
            'classes': ('collapse',)
        }),
    )