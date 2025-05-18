from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.gis import forms
from django.contrib.gis.geos import Point
from django.urls import path, reverse
from django.shortcuts import redirect, render
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
import json
from .models import (
    Country, WeatherStation, ClimateData, WeatherDataType,
    DataExport, WeatherAlert
)
from .field_models import (
    DeviceType, FieldDevice, DeviceCalibration, FieldDataUpload, FieldDataRecord
)

@admin.register(Country)
class CountryAdmin(GISModelAdmin):
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
class WeatherStationAdmin(GISModelAdmin):
    list_display = ('name', 'station_id', 'country', 'is_active', 'date_installed', 'stack_info')
    list_filter = ('is_active', 'country', 'date_installed', 'has_temperature', 'has_precipitation')
    search_fields = ('name', 'station_id', 'description')
    readonly_fields = ('created_at', 'updated_at', 'stack_size', 'stack_preview', 'map_preview', 'latitude', 'longitude')
    actions = ['process_data_stacks', 'clear_data_stacks', 'mark_as_active', 'mark_as_inactive', 'bulk_update_data_types']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'station_id', 'description')
        }),
        ('Location', {
            'fields': ('location', 'altitude', 'country', 'region', 'map_preview', 'latitude', 'longitude')
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
        ('Data Stack Settings', {
            'fields': ('stack_size', 'data_stack', 'stack_preview', 'max_stack_size', 'auto_process', 'process_threshold', 'last_data_feed'),
            'classes': ('collapse',),
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('add-marker/', self.admin_site.admin_view(self.add_marker_view), name='maps_weatherstation_add_marker'),
            path('bulk-import/', self.admin_site.admin_view(self.bulk_import_view), name='maps_weatherstation_bulk_import'),
            path('api/geocode/', self.admin_site.admin_view(self.geocode_api), name='maps_weatherstation_api_geocode'),
        ]
        return custom_urls + urls
    
    def stack_size(self, obj):
        """Display the current size of the data stack"""
        return obj.stack_size()
    stack_size.short_description = "Stack Size"
    
    def stack_info(self, obj):
        """Display stack info in the list view"""
        size = obj.stack_size()
        if size == 0:
            return format_html('<span style="color: #888;">Empty</span>')
        elif obj.auto_process and size >= obj.process_threshold:
            return format_html('<span style="color: #ff9900;">{} readings (auto-process at {})</span>', size, obj.process_threshold)
        elif size >= obj.max_stack_size * 0.9:  # 90% full
            return format_html('<span style="color: #ff0000;">{} readings (max: {})</span>', size, obj.max_stack_size)
        else:
            return format_html('<span style="color: #28a745;">{} readings</span>', size)
    stack_info.short_description = "Data Stack"
    
    def map_preview(self, obj):
        """Display a small map preview with the station marker"""
        if not obj.pk or not obj.location:
            return "Save the station first to see map preview"
            
        return format_html('''
            <div id="map_preview" style="width: 100%; height: 300px; margin-top: 10px;"></div>
            <script>
                django.jQuery(document).ready(function() {{
                    // Initialize the map
                    var map = L.map('map_preview').setView([{lat}, {lng}], 10);
                    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    }}).addTo(map);
                    
                    // Add marker
                    var marker = L.marker([{lat}, {lng}], {{
                        draggable: false,
                        title: "{name}"
                    }}).addTo(map);
                    
                    // Add popup with station info
                    marker.bindPopup("<b>{name}</b><br>ID: {station_id}<br>Altitude: {altitude}m");
                }});
            </script>
        ''', lat=obj.latitude, lng=obj.longitude, name=obj.name, station_id=obj.station_id or 'N/A', altitude=obj.altitude or 0)
    map_preview.short_description = "Map Preview"
    map_preview.allow_tags = True
    
    def stack_preview(self, obj):
        """Show a preview of the latest stacked data items"""
        import json
        
        size = obj.stack_size()
        if size == 0:
            return "No data in stack"
            
        try:
            # Handle both JSONField and TextField types
            if isinstance(obj.data_stack, list):
                stack_data = obj.data_stack
            else:
                stack_data = json.loads(obj.data_stack or '[]')
                
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
    stack_preview.allow_tags = True
    
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
            self.message_user(request, "No data found to process in the selected stations.")
    process_data_stacks.short_description = "Process data stacks for selected stations"
    
    def clear_data_stacks(self, request, queryset):
        """Clear the data stacks for selected weather stations"""
        import json
        
        stations_cleared = 0
        readings_cleared = 0
        
        for station in queryset:
            stack_size = station.stack_size()
            if stack_size > 0:
                # Clear the stack based on field type
                if isinstance(station.data_stack, list):
                    station.data_stack = []
                else:
                    station.data_stack = json.dumps([])
                station.save(update_fields=['data_stack'])
                
                stations_cleared += 1
                readings_cleared += stack_size
        
        if stations_cleared > 0:
            self.message_user(request, f"Cleared {readings_cleared} readings from {stations_cleared} stations.")
        else:
            self.message_user(request, "No data found to clear in the selected stations.")
    clear_data_stacks.short_description = "Clear data stacks for selected stations"
    
    def mark_as_active(self, request, queryset):
        """Mark selected stations as active"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} stations marked as active.")
    mark_as_active.short_description = "Mark selected stations as active"
    
    def mark_as_inactive(self, request, queryset):
        """Mark selected stations as inactive"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} stations marked as inactive.")
    mark_as_inactive.short_description = "Mark selected stations as inactive"
    
    def bulk_update_data_types(self, request, queryset):
        """Bulk update available data types for selected stations"""
        data_types = ['has_temperature', 'has_precipitation', 'has_humidity', 
                      'has_wind', 'has_air_quality', 'has_soil_moisture', 'has_water_level']
        
        if 'apply' in request.POST:
            # Process the form
            for data_type in data_types:
                if data_type in request.POST:
                    value = request.POST[data_type] == 'on'
                    queryset.update(**{data_type: value})
            
            self.message_user(request, f"Updated data types for {queryset.count()} stations.")
            return redirect(request.get_full_path())
        
        # Render form
        return render(request, 'admin/maps/bulk_update_data_types.html', {
            'title': "Bulk update data types",
            'queryset': queryset,
            'data_types': data_types,
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })
    bulk_update_data_types.short_description = "Bulk update data types"
    
    def add_marker_view(self, request):
        """View for adding a station marker on a map"""
        if request.method == 'POST':
            form = self.get_form(request, None, change=False)
            
            if 'location' in request.POST:
                try:
                    # Parse coordinates from the map
                    coords = json.loads(request.POST['location'])
                    longitude, latitude = coords
                    point = Point(float(longitude), float(latitude), srid=4326)
                    
                    # Set the location field with the picked coordinates
                    form.initial['location'] = point
                    
                    # Create object with the form data
                    obj = self.save_form(request, form, change=False)
                    obj.location = point  # Ensure location is set correctly
                    obj.save()
                    
                    # Return to the form with prefilled location
                    messages.success(request, f"Station created at location: {latitude:.6f}, {longitude:.6f}")
                    return self.response_add(request, obj)
                except Exception as e:
                    messages.error(request, f"Error setting location: {str(e)}")
            
            if form.is_valid():
                obj = self.save_form(request, form, change=False)
                return self.response_add(request, obj)
        else:
            form = self.get_form(request, None, change=False)
        
        context = {
            'title': "Add Weather Station",
            'form': form,
            'opts': self.model._meta,
            'add': True,
            'change': False,
            'is_popup': False,
            'save_as': False,
            'has_delete_permission': False,
            'has_add_permission': True,
            'has_change_permission': False,
            'media': self.media,
        }
        
        return render(request, 'admin/maps/weatherstation/add_map_marker.html', context)
    
    def bulk_import_view(self, request):
        """View for bulk importing weather stations from CSV"""
        if request.method == 'POST':
            if 'csv_file' not in request.FILES:
                messages.error(request, "Please select a CSV file to upload")
                return redirect('admin:maps_weatherstation_bulk_import')
            
            file = request.FILES['csv_file']
            if not file.name.endswith('.csv'):
                messages.error(request, "Please upload a CSV file")
                return redirect('admin:maps_weatherstation_bulk_import')
            
            # Process the CSV file
            try:
                import csv
                from io import TextIOWrapper
                from django.contrib.gis.geos import Point
                
                csv_file = TextIOWrapper(file, encoding='utf-8-sig')
                reader = csv.DictReader(csv_file)
                
                stations_created = 0
                errors = []
                
                for row in reader:
                    try:
                        # Get required fields
                        name = row.get('name')
                        latitude = float(row.get('latitude', 0))
                        longitude = float(row.get('longitude', 0))
                        
                        if not name or not latitude or not longitude:
                            errors.append(f"Row {reader.line_num}: Missing required fields")
                            continue
                        
                        # Create the station
                        station = WeatherStation(
                            name=name,
                            station_id=row.get('station_id'),
                            description=row.get('description', ''),
                            location=Point(longitude, latitude, srid=4326),
                            altitude=float(row.get('altitude', 0)) if row.get('altitude') else None,
                            is_active=row.get('is_active', '').lower() == 'true'
                        )
                        
                        # Handle optional data type flags
                        for data_type in ['has_temperature', 'has_precipitation', 'has_humidity', 
                                          'has_wind', 'has_air_quality', 'has_soil_moisture', 'has_water_level']:
                            if data_type in row:
                                setattr(station, data_type, row[data_type].lower() == 'true')
                        
                        station.save()
                        stations_created += 1
                        
                    except Exception as e:
                        errors.append(f"Row {reader.line_num}: {str(e)}")
                
                # Report results
                if stations_created > 0:
                    messages.success(request, f"Successfully created {stations_created} weather stations")
                
                if errors:
                    messages.warning(request, f"Encountered {len(errors)} errors: {'; '.join(errors[:5])}")
                    if len(errors) > 5:
                        messages.warning(request, f"...and {len(errors) - 5} more errors")
                
                return redirect('admin:maps_weatherstation_changelist')
                
            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
                return redirect('admin:maps_weatherstation_bulk_import')
        
        return render(request, 'admin/maps/weatherstation/bulk_import.html', {
            'title': "Bulk Import Weather Stations",
            'opts': self.model._meta,
        })
    
    def geocode_api(self, request):
        """API endpoint for geocoding location names"""
        if 'q' not in request.GET:
            return JsonResponse({'error': 'Missing query parameter'}, status=400)
        
        query = request.GET['q']
        
        try:
            # Simple example using Nominatim (for production use a paid API with proper error handling)
            import requests
            
            response = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={
                    'q': query,
                    'format': 'json',
                    'limit': 5,
                },
                headers={'User-Agent': 'WeatherStationAdmin/1.0'}
            )
            
            if response.status_code == 200:
                results = []
                for item in response.json():
                    results.append({
                        'name': item.get('display_name'),
                        'lat': float(item.get('lat')),
                        'lon': float(item.get('lon')),
                    })
                return JsonResponse({'results': results})
            else:
                return JsonResponse({'error': 'Geocoding service error'}, status=502)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get_form(self, request, obj=None, **kwargs):
        """Override form to use a more enhanced map widget"""
        form = super().get_form(request, obj, **kwargs)
        return form

    def latitude(self, obj):
        """Display the latitude of the weather station"""
        if obj.location:
            return obj.location.y
        return None
    latitude.short_description = "Latitude"

    def longitude(self, obj):
        """Display the longitude of the weather station"""
        if obj.location:
            return obj.location.x
        return None
    longitude.short_description = "Longitude"

class ClimateDataInline(admin.TabularInline):
    model = ClimateData
    extra = 0
    fields = ('timestamp', 'temperature', 'precipitation', 'data_quality')
    readonly_fields = ('timestamp',)
    can_delete = True
    max_num = 5
    show_change_link = True
    verbose_name = "Recent Climate Data"
    verbose_name_plural = "Recent Climate Data"
    
    def get_queryset(self, request):
        """Limit to most recent records only for better performance"""
        queryset = super().get_queryset(request)
        return queryset.order_by('-timestamp')[:5]

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

@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'manufacturer', 'communication_protocol', 'power_source', 'battery_life_days', 'created_at')
    list_filter = ('communication_protocol', 'power_source', 'has_temperature', 'has_precipitation', 'has_humidity', 'has_wind')
    search_fields = ('name', 'manufacturer', 'model_number')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'manufacturer', 'model_number', 'description')
        }),
        ('Technical Specifications', {
            'fields': (
                'communication_protocol',
                'power_source',
                'battery_life_days',
                'firmware_version'
            )
        }),
        ('Data Capabilities', {
            'fields': (
                'has_temperature',
                'has_precipitation',
                'has_humidity',
                'has_wind',
                'has_air_quality',
                'has_soil_moisture',
                'has_water_level'
            )
        }),
    )

@admin.register(FieldDevice)
class FieldDeviceAdmin(GISModelAdmin):
    list_display = ('name', 'device_id', 'device_type', 'status', 'battery_level', 'signal_strength', 'last_communication')
    list_display_links = ('name',)
    list_filter = ('status', 'device_type')
    search_fields = ('name', 'device_id', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'device_id', 'device_type', 'weather_station')
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Status', {
            'fields': (
                'status',
                'installation_date',
                'last_communication'
            )
        }),
        ('Operational Data', {
            'fields': (
                'battery_level',
                'signal_strength',
                'firmware_version',
                'transmission_interval'
            )
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )

@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'export_format', 'status', 'created_at', 'download_count')
    list_filter = ('status', 'export_format', 'created_at', 'min_data_quality')
    search_fields = ('user__username', 'error_log')
    readonly_fields = ('created_at', 'updated_at', 'download_count')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'status', 'export_format', 'include_metadata')
        }),
        ('Data Selection', {
            'fields': ('stations', 'country', 'data_types', 'date_from', 'date_to', 'years', 'min_data_quality')
        }),
        ('Geographic Filter', {
            'fields': ('bounding_box',),
            'classes': ('collapse',),
        }),
        ('Export File', {
            'fields': ('file', 'download_count', 'last_downloaded')
        }),
        ('Status Details', {
            'fields': ('created_at', 'updated_at', 'error_log')
        }),
    )

@admin.register(WeatherAlert)
class WeatherAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'station', 'severity', 'status', 'created_at')
    list_filter = ('severity', 'status', 'created_at')
    search_fields = ('title', 'description', 'station__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'station', 'data_type', 'threshold_value')
        }),
        ('Status', {
            'fields': ('severity', 'status', 'created_at', 'updated_at', 'resolved_at')
        }),
        ('Location', {
            'fields': ('country', 'affected_area')
        }),
        ('Notifications', {
            'fields': ('notify_email', 'notify_sms', 'notify_push'),
            'classes': ('collapse',),
        }),
    )

@admin.register(DeviceCalibration)
class DeviceCalibrationAdmin(admin.ModelAdmin):
    list_display = ('device', 'calibration_date', 'performed_by', 'next_calibration_date')
    list_filter = ('calibration_date', 'next_calibration_date')
    search_fields = ('device__name', 'device__device_id', 'notes')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('device', 'calibration_date', 'next_calibration_date', 'performed_by')
        }),
        ('Calibration Details', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )

@admin.register(FieldDataUpload)
class FieldDataUploadAdmin(admin.ModelAdmin):
    list_display = ('title', 'device_type', 'created_by', 'upload_date', 'status', 'processed_count')
    list_filter = ('status', 'upload_date', 'device_type')
    search_fields = ('title', 'description', 'created_by__username')
    readonly_fields = ('upload_date', 'processed_count', 'error_count')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'device_type', 'created_by')
        }),
        ('File Details', {
            'fields': ('data_file', 'data_format')
        }),
        ('Processing Status', {
            'fields': ('status', 'upload_date', 'processed_count', 'error_count', 'error_log')
        }),
    )

@admin.register(FieldDataRecord)
class FieldDataRecordAdmin(admin.ModelAdmin):
    list_display = ('device', 'timestamp', 'processed', 'created_at')
    list_filter = ('device', 'timestamp', 'processed')
    search_fields = ('device__name', 'device__device_id')
    
    fieldsets = (
        (None, {
            'fields': ('device', 'timestamp', 'upload')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'location')
        }),
        ('Data', {
            'fields': ('data', 'processed')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )