# admin.py
from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import WeatherStation, ClimateData, DataExport

@admin.register(WeatherStation)
class WeatherStationAdmin(GISModelAdmin):
    list_display = ('name', 'latitude', 'longitude', 'is_active', 'date_installed')
    list_filter = ('is_active', 'date_installed')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Location Information', {
            'fields': ('location', 'altitude', 'date_installed')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class ClimateDataInline(admin.TabularInline):
    model = ClimateData
    extra = 0
    fields = ('timestamp', 'temperature', 'humidity', 'precipitation', 'data_quality')
    readonly_fields = ('created_at',)
    can_delete = True
    max_num = 10


@admin.register(ClimateData)
class ClimateDataAdmin(admin.ModelAdmin):
    list_display = ('station', 'timestamp', 'temperature', 'humidity', 'precipitation', 'data_quality')
    list_filter = ('data_quality', 'station', 'timestamp')
    search_fields = ('station__name',)
    date_hierarchy = 'timestamp'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('station', 'timestamp', 'data_quality')
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


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = ('user', 'station', 'export_format', 'date_from', 'date_to', 'created_at')
    list_filter = ('export_format', 'created_at')
    readonly_fields = ('created_at',)