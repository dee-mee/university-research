from django.contrib import admin
#from django.contrib.gis.admin import OSMGeoAdmin
from .models import (
    Country, WeatherStation, ClimateData, WeatherDataType,
    DataExport, WeatherAlert
)

#@admin.register(Country)
#class CountryAdmin(OSMGeoAdmin):
#    list_display = ('name', 'code', 'is_southern_hemisphere')
#    search_fields = ('name', 'code')
#    list_filter = ('is_southern_hemisphere',)
#    fieldsets = (
#        (None, {
#            'fields': ('name', 'code', 'is_southern_hemisphere')
#        }),
#        ('Geography', {
#            'fields': ('boundary',),
#            'classes': ('collapse',),
#        }),
#    )

#@admin.register(WeatherStation)
#class WeatherStationAdmin(OSMGeoAdmin):
#    list_display = ('name', 'station_id', 'country', 'is_active', 'date_installed')
#    list_filter = ('is_active', 'country', 'date_installed')
#    search_fields = ('name', 'station_id', 'description')
#    readonly_fields = ('created_at', 'updated_at', 'stack_size')
#    
#    fieldsets = (
#        (None, {
#            'fields': ('name', 'station_id', 'description')
#        }),
#        ('Location', {
#            'fields': ('location', 'altitude', 'country', 'region')
#        }),
#        ('Status', {
#            'fields': ('is_active', 'date_installed', 'date_decommissioned')
#        }),
#        ('Data Types Available', {
#            'fields': (
#                'has_temperature', 'has_precipitation', 'has_humidity',
#                'has_wind', 'has_air_quality', 'has_soil_moisture', 'has_water_level'
#            )
#        }),
#        ('Data Stack Configuration', {
#            'fields': ('max_stack_size', 'auto_process', 'process_threshold', 'stack_size')
#        }),
#        ('Timestamps', {
#            'fields': ('created_at', 'updated_at', 'last_data_feed'),
#            'classes': ('collapse',)
#        }),
#    )
#    
#    def stack_size(self, obj):
#        """Display the current size of the data stack"""
#        return obj.stack_size()
#    stack_size.short_description = "Stack Size"
#    
#    def stack_info(self, obj):
#        """Display stack info in the list view"""
#        size = obj.stack_size()
#        if size == 0:
#            return "No stacked data"
#        elif obj.auto_process and size >= obj.process_threshold:
#            return format_html('<span style="color: #ff9900;">{} readings (auto-process at {})</span>', size, obj.process_threshold)
#        elif size >= obj.max_stack_size * 0.9:  # 90% full
#            return format_html('<span style="color: #ff0000;">{} readings (max: {})</span>', size, obj.max_stack_size)
#        else:
#            return format_html('{} readings', size)
#    stack_info.short_description = "Data Stack"
#    
#    def stack_preview(self, obj):
#        """Show a preview of the latest stacked data items"""
#        import json
#        
#        size = obj.stack_size()
#        if size == 0:
#            return "No data in stack"
#            
#        try:
#            stack_data = json.loads(obj.data_stack)
#            if not stack_data:
#                return "Stack is empty"
#                
#            # Take the last 5 items (most recent first)
#            preview_data = stack_data[-5:]
#            
#            # Format the data as an HTML table
#            html = '<table style="border-collapse: collapse; width: 100%;">'
#            html += '<tr style="background-color: #f2f2f2;"><th style="padding: 8px; text-align: left;">Timestamp</th>'
#            html += '<th style="padding: 8px; text-align: left;">Data</th></tr>'
#            
#            for item in reversed(preview_data):  # Show most recent at the top
#                timestamp = item.get('timestamp', 'Unknown time')
#                html += f'<tr><td style="border: 1px solid #ddd; padding: 8px;">{timestamp}</td>'
#                
#                # Format data values
#                data_values = []
#                for key, value in item.items():
#                    if key != 'timestamp':
#                        data_values.append(f"{key}: {value}")
#                
#                html += f'<td style="border: 1px solid #ddd; padding: 8px;">{", ".join(data_values)}</td></tr>'
#            
#            html += '</table>'
#            
#            if size > 5:
#                html += f'<p>{size - 5} more readings not shown</p>'
#                
#            return format_html(html)
#            
#        except Exception as e:
#            return f"Error displaying stack data: {str(e)}"
#    stack_preview.short_description = "Stack Preview"
#    
#    def process_data_stacks(self, request, queryset):
#        """Process the data stacks for selected weather stations"""
#        records_total = 0
#        stations_processed = 0
#        
#        for station in queryset:
#            records_processed = station.process_data_stack()
#            if records_processed > 0:
#                stations_processed += 1
#                records_total += records_processed
#        
#        if records_total > 0:
#            self.message_user(request, f"Successfully processed {records_total} readings from {stations_processed} stations.")
#        else:
#            self.message_user(request, f"No data found to process in the selected stations.")
#    process_data_stacks.short_description = "Process data stacks for selected stations"
#    
#    def clear_data_stacks(self, request, queryset):


class ClimateDataInline(admin.TabularInline):
    model = ClimateData
    extra = 0
    fields = ('timestamp', 'temperature', 'humidity', 'precipitation', 'data_quality')
    readonly_fields = ('created_at', 'year', 'month')
    can_delete = True
    max_num = 10




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
    list_display = ('user', 'export_format', 'date_from', 'date_to', 'created_at', 'status', 'country_filter')
    list_filter = ('export_format', 'status', 'created_at', 'country')
    readonly_fields = ('created_at', 'updated_at', 'last_downloaded')
    filter_horizontal = ('stations', 'data_types')
    
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
            'fields': ('file', 'error_message', 'created_at', 'updated_at', 'last_downloaded', 'download_count')
        }),
    )
    
    def country_filter(self, obj):
        """
        Display the country name for a DataExport object
        """
        if obj.country:
            return obj.country.name
        return "-"
    
    country_filter.short_description = "Country"

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