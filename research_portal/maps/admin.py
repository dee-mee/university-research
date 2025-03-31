from django.contrib import admin
from django.contrib.gis.admin import GeoModelAdmin  # Changed from GISModelAdmin to GeoModelAdmin
from django.utils.html import format_html
from .models import WeatherStation, ClimateData, DataExport, Country, WeatherDataType, WeatherAlert

@admin.register(Country)
class CountryAdmin(GeoModelAdmin):  # Changed from GISModelAdmin to GeoModelAdmin
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
class WeatherStationAdmin(GeoModelAdmin):  # Changed from GISModelAdmin to GeoModelAdmin
    list_display = ('name', 'station_id', 'country', 'is_active', 'date_installed', 'data_types_available', 'stack_info')
    list_filter = ('is_active', 'country', 'has_temperature', 'has_precipitation', 'has_humidity', 'has_wind', 'has_air_quality', 'auto_process')
    search_fields = ('name', 'station_id', 'description', 'country__name')
    readonly_fields = ('created_at', 'updated_at', 'map_preview', 'stack_size', 'last_data_feed', 'stack_preview')
    actions = ['process_data_stacks', 'clear_data_stacks']
    
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
        ('Data Stack Configuration', {
            'fields': ('max_stack_size', 'auto_process', 'process_threshold', 'stack_size', 'last_data_feed', 'stack_preview'),
            'classes': ('collapse',),
            'description': 'Configure how the station handles stacked data readings.'
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
    
    def stack_size(self, obj):
        """Display the current size of the data stack"""
        return obj.stack_size()
    stack_size.short_description = "Stack Size"
    
    def stack_info(self, obj):
        """Display stack info in the list view"""
        size = obj.stack_size()
        if size == 0:
            return "No stacked data"
        elif obj.auto_process and size >= obj.process_threshold:
            return format_html('<span style="color: #ff9900;">{} readings (auto-process at {})</span>', size, obj.process_threshold)
        elif size >= obj.max_stack_size * 0.9:  # 90% full
            return format_html('<span style="color: #ff0000;">{} readings (max: {})</span>', size, obj.max_stack_size)
        else:
            return format_html('{} readings', size)
    stack_info.short_description = "Data Stack"
    
    def stack_preview(self, obj):
        """Show a preview of the latest stacked data items"""
        import json
        
        size = obj.stack_size()
        if size == 0:
            return "No data in stack"
            
        try:
            stack_data = json.loads(obj.data_stack)
            if not stack_data:
                return "Stack is empty"
                
            # Take the last 5 items (most recent first)
            preview_data = stack_data[-5:]
            
            # Format the data as an HTML table
            html = '<table style="border-collapse: collapse; width: 100%;">'
            html += '<tr style="background-color: #f2f2f2;"><th style="padding: 8px; text-align: left;">Timestamp</th>'
            html += '<th style="padding: 8px; text-align: left;">Data</th></tr>'
            
            for item in reversed(preview_data):  # Show most recent at the top
                timestamp = item.get('timestamp', 'Unknown time')
                html += f'<tr><td style="border: 1px solid #ddd; padding: 8px;">{timestamp}</td>'
                
                # Format data values
                data_values = []
                for key, value in item.items():
                    if key != 'timestamp':
                        data_values.append(f"{key}: {value}")
                
                html += f'<td style="border: 1px solid #ddd; padding: 8px;">{", ".join(data_values)}</td></tr>'
            
            html += '</table>'
            
            if size > 5:
                html += f'<p>{size - 5} more readings not shown</p>'
                
            return format_html(html)
            
        except Exception as e:
            return f"Error displaying stack data: {str(e)}"
    stack_preview.short_description = "Stack Preview"
    
    def process_data_stacks(self, request, queryset):
        """Process the data stacks for selected weather stations"""
        records_total = 0
        stations_processed = 0
        
        for station in queryset:
            records_processed = station.process_data_stack()
            if records_processed > 0:
                stations_processed += 1
                records_total += records_processed
        
        if records_total > 0:
            self.message_user(request, f"Successfully processed {records_total} readings from {stations_processed} stations.")
        else:
            self.message_user(request, f"No data found to process in the selected stations.")
    process_data_stacks.short_description = "Process data stacks for selected stations"
    
    def clear_data_stacks(self, request, queryset):
        """Clear the data stacks for selected weather stations"""
        import json
        
        stations_cleared = 0
        readings_cleared = 0
        
        for station in queryset:
            stack_size = station.stack_size()
            if stack_size > 0:
                readings_cleared += stack_size
                station.data_stack = json.dumps([])
                station.save(update_fields=['data_stack'])
                stations_cleared += 1
        
        if stations_cleared > 0:
            self.message_user(request, f"Cleared {readings_cleared} readings from {stations_cleared} stations.")
        else:
            self.message_user(request, "No data stacks were cleared. Stacks may already be empty.")
    clear_data_stacks.short_description = "Clear data stacks for selected stations"


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
    readonly_fields = ('created_at', 'updated_at', 'last_downloaded')
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
            'fields': ('file', 'error_message', 'created_at', 'updated_at', 'last_downloaded', 'download_count')
        }),
    )
    
    def country_filter(self, obj):
        return obj.country.name if obj.country else "All Countries"
    country_filter.short_description = "Country Filter"


@admin.register(WeatherAlert)
class WeatherAlertAdmin(GeoModelAdmin):  # Changed from GISModelAdmin to GeoModelAdmin
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