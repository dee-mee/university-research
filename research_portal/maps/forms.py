import os
import csv
import io
from django import forms
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from .models import Country, WeatherStation, WeatherDataType, ClimateData


class BaseImportForm(forms.Form):
    """Base form with common fields and methods for all import forms"""
    IMPORT_CHOICES = [
        ('stations', _('Weather Stations')),
        ('climate_data', _('Climate Data')),
        ('weather_types', _('Weather Data Types')),
        ('alerts', _('Weather Alerts')),
    ]

    import_type = forms.ChoiceField(
        choices=IMPORT_CHOICES,
        label=_("Import Type"),
        widget=forms.RadioSelect,
        initial='stations',
        help_text=_("Select the type of data you want to import.")
    )

    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        label=_("Country"),
        required=False,
        help_text=_("Optional: Specify the country for the data being imported."),
        empty_label=_("All Countries")
    )

    overwrite_existing = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Overwrite Existing Records"),
        help_text=_("If checked, existing records with the same ID will be updated.")
    )

    skip_errors = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Skip Errors"),
        help_text=_("If checked, the import will continue even if some rows have errors.")
    )

    def get_required_headers(self):
        """Return the required headers based on the import type"""
        import_type = self.cleaned_data.get('import_type')

        if import_type == 'stations':
            return ['name', 'station_id', 'latitude', 'longitude']
        elif import_type == 'climate_data':
            return ['station_id', 'timestamp', 'temperature', 'humidity', 'precipitation']
        elif import_type == 'weather_types':
            return ['name', 'display_name', 'unit']
        elif import_type == 'alerts':
            return ['title', 'description', 'station_id', 'severity', 'data_type']

        return []

    def validate_headers(self, headers):
        """Validate that the file has the required headers"""
        required_headers = self.get_required_headers()
        missing_headers = [h for h in required_headers if h not in headers]

        if missing_headers:
            raise forms.ValidationError(
                _("Missing required headers: %(headers)s"),
                params={'headers': ', '.join(missing_headers)}
            )

    def preview_data(self, file_obj, max_rows=5):
        """Preview the first few rows of the file"""
        if not file_obj:
            return []

        # Save current position to reset after preview
        current_position = file_obj.tell()
        file_obj.seek(0)

        try:
            # Try to read as CSV
            reader = csv.DictReader(io.StringIO(file_obj.read().decode('utf-8')))
            rows = [row for row in reader][:max_rows]

            # Validate headers if we have rows
            if rows and hasattr(reader, 'fieldnames'):
                self.validate_headers(reader.fieldnames)

            # Reset file pointer
            file_obj.seek(current_position)
            return rows
        except Exception as e:
            # Reset file pointer
            file_obj.seek(current_position)
            raise forms.ValidationError(f"Error previewing file: {str(e)}")


class CSVUploadForm(BaseImportForm):
    """Form for uploading CSV files"""
    IMPORT_CHOICES = [
        ('stations', _('Weather Stations')),
        ('climate_data', _('Climate Data')),
        ('weather_data_types', _('Weather Data Types')),
        ('countries', _('Countries')),
    ]
    
    PROCESSING_CHOICES = [
        ('direct', _('Direct Database Insert')),
        ('stack', _('Add to Data Stack')),
    ]
    
    import_type = forms.ChoiceField(
        choices=IMPORT_CHOICES,
        label=_("Import Type"),
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='stations',
        help_text=_("Select the type of data you want to import.")
    )
    
    processing_mode = forms.ChoiceField(
        choices=PROCESSING_CHOICES,
        label=_("Processing Mode"),
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='direct',
        help_text=_("Choose how to process climate data. Stack mode adds to stations' data stacks for later processing.")
    )
    
    csv_file = forms.FileField(
        label=_("CSV File"),
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv,.txt'}),
        help_text=_("Select a CSV file to upload. Required file format depends on the import type."),
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'txt'])]
    )

    def clean(self):
        cleaned_data = super().clean()
        
        # Get import_type and csv_file
        import_type = cleaned_data.get('import_type')
        csv_file = cleaned_data.get('csv_file')
        
        # Only show processing_mode for climate data
        if import_type != 'climate_data':
            cleaned_data['processing_mode'] = 'direct'
        
        # Validate file is present
        if not csv_file:
            self.add_error('csv_file', _("Please select a file to upload."))
            return cleaned_data
            
        # Check file extension
        if not csv_file.name.lower().endswith(('.csv', '.txt')):
            self.add_error('csv_file', _("The file must be a CSV or TXT file."))
            
        # Check file size (max 50MB)
        if csv_file.size > 50 * 1024 * 1024:  # 50MB in bytes
            self.add_error('csv_file', _("The file size must be under 50MB."))
            
        return cleaned_data


class ExcelUploadForm(BaseImportForm):
    """Form for uploading Excel files"""
    excel_file = forms.FileField(
        label=_("Excel File"),
        help_text=_("Select an Excel file (.xlsx, .xls) to upload."),
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])]
    )

    sheet_name = forms.CharField(
        label=_("Sheet Name"),
        required=False,
        help_text=_("Optional: Enter the name of the sheet to import. Leave blank to use the first sheet.")
    )

    def clean_excel_file(self):
        excel_file = self.cleaned_data.get('excel_file')
        if not excel_file:
            return None

        # Check file extension
        if not excel_file.name.lower().endswith(('.xlsx', '.xls')):
            raise forms.ValidationError(_("The file must be an Excel file (.xlsx or .xls)."))

        # Check file size (max 50MB)
        if excel_file.size > 50 * 1024 * 1024:  # 50MB in bytes
            raise forms.ValidationError(_("The file size must be under 50MB."))

        # We'll validate the Excel content in the view
        return excel_file


class FlashDriveImportForm(BaseImportForm):
    """Form for importing data from a flash drive"""
    drive_path = forms.CharField(
        label=_("Flash Drive Path"),
        initial="/media/usb",
        help_text=_("Enter the path where the flash drive is mounted.")
    )

    file_pattern = forms.CharField(
        label=_("File Pattern"),
        initial="*.csv",
        help_text=_("Enter a pattern to match files (e.g., *.csv, station_data_*.txt).")
    )

    recursive = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Search Recursively"),
        help_text=_("If checked, subdirectories will be searched for matching files.")
    )

    def clean_drive_path(self):
        drive_path = self.cleaned_data.get('drive_path')
        if not drive_path:
            return None

        # Security: Ensure the path is within allowed directories
        allowed_prefixes = ['/media', '/mnt', '/run/media']
        if not any(drive_path.startswith(prefix) for prefix in allowed_prefixes):
            raise forms.ValidationError(
                _("The path must be within an allowed directory: %(dirs)s"),
                params={'dirs': ', '.join(allowed_prefixes)}
            )

        # Check if the path exists
        if not os.path.exists(drive_path):
            raise forms.ValidationError(_("The specified path does not exist."))

        # Check if the path is a directory
        if not os.path.isdir(drive_path):
            raise forms.ValidationError(_("The specified path is not a directory."))

        return drive_path


class DataMappingForm(forms.Form):
    """Form for mapping columns when importing data"""

    def __init__(self, *args, headers=None, import_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.import_type = import_type

        if not headers:
            return

        # Get the model fields based on import type
        model_fields = self._get_model_fields()

        # Create a dropdown field for each header to map to model fields
        for header in headers:
            field_name = f"map_{header}"
            self.fields[field_name] = forms.ChoiceField(
                choices=[('', '-- Ignore --')] + model_fields,
                required=False,
                label=f"Map '{header}' to",
                initial=self._guess_mapping(header, model_fields)
            )

    def _get_model_fields(self):
        """Get the fields for the selected model"""
        if self.import_type == 'stations':
            return [
                ('name', 'Station Name'),
                ('station_id', 'Station ID'),
                ('latitude', 'Latitude'),
                ('longitude', 'Longitude'),
                ('altitude', 'Altitude'),
                ('description', 'Description'),
                ('is_active', 'Is Active'),
                ('date_installed', 'Installation Date'),
                ('region', 'Region'),
            ]
        elif self.import_type == 'climate_data':
            return [
                ('station_id', 'Station ID'),
                ('timestamp', 'Timestamp'),
                ('temperature', 'Temperature (°C)'),
                ('humidity', 'Humidity (%)'),
                ('precipitation', 'Precipitation (mm)'),
                ('wind_speed', 'Wind Speed (m/s)'),
                ('wind_direction', 'Wind Direction (°)'),
                ('air_quality_index', 'Air Quality Index'),
                ('barometric_pressure', 'Pressure (hPa)'),
                ('cloud_cover', 'Cloud Cover (%)'),
                ('soil_moisture', 'Soil Moisture (%)'),
                ('water_level', 'Water Level (m)'),
                ('uv_index', 'UV Index'),
                ('data_quality', 'Data Quality'),
            ]
        elif self.import_type == 'weather_types':
            return [
                ('name', 'Type Name'),
                ('display_name', 'Display Name'),
                ('unit', 'Unit'),
                ('description', 'Description'),
                ('min_value', 'Minimum Value'),
                ('max_value', 'Maximum Value'),
                ('icon', 'Icon'),
            ]

        return []

    def _guess_mapping(self, header, model_fields):
        """Try to guess the mapping based on header name"""
        header_lower = header.lower().replace(' ', '_')

        # Direct matches
        for field_id, field_name in model_fields:
            if field_id.lower() == header_lower:
                return field_id

        # Partial matches
        for field_id, field_name in model_fields:
            if field_id.lower() in header_lower or header_lower in field_id.lower():
                return field_id

        # Default mappings for common variations
        mapping = {
            'lat': 'latitude',
            'lon': 'longitude',
            'long': 'longitude',
            'alt': 'altitude',
            'temp': 'temperature',
            'precip': 'precipitation',
            'humid': 'humidity',
            'press': 'barometric_pressure',
            'id': 'station_id',
            'quality': 'data_quality',
            'time': 'timestamp',
            'date': 'timestamp'
        }

        for key, value in mapping.items():
            if key in header_lower:
                for field_id, _ in model_fields:
                    if field_id == value:
                        return field_id

        return ''


class DataExportForm(forms.Form):
    """Form for exporting climate data"""
    FORMAT_CHOICES = [
        ('csv', _('CSV')),
        ('json', _('JSON')),
        ('geojson', _('GeoJSON')),
        ('excel', _('Excel')),
        ('netcdf', _('NetCDF')),
    ]

    stations = forms.ModelMultipleChoiceField(
        queryset=WeatherStation.objects.filter(is_active=True),
        required=False,
        label=_("Weather Stations"),
        help_text=_("Select the weather stations to export data from. Leave empty to include all stations.")
    )

    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        required=False,
        label=_("Country"),
        help_text=_("Filter by country. Leave empty to include all countries."),
        empty_label=_("All Countries")
    )

    data_types = forms.ModelMultipleChoiceField(
        queryset=WeatherDataType.objects.all(),
        required=False,
        label=_("Data Types"),
        help_text=_("Select the types of weather data to include. Leave empty to include all data types.")
    )

    date_from = forms.DateTimeField(
        label=_("Date From"),
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text=_("Start date and time for the data export (inclusive).")
    )

    date_to = forms.DateTimeField(
        label=_("Date To"),
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text=_("End date and time for the data export (inclusive).")
    )

    years = forms.MultipleChoiceField(
        choices=[(year, str(year)) for year in range(1950, 2026)],
        required=False,
        label=_("Filter by Years"),
        help_text=_("Optionally select specific years to include. Leave empty to use the date range above.")
    )

    export_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        label=_("Export Format"),
        initial='csv',
        help_text=_("Select the format for the exported data.")
    )

    include_metadata = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Include Metadata"),
        help_text=_("Include station and data type information in the export.")
    )

    data_quality = forms.ChoiceField(
        choices=[
            ('', _('All Quality Levels')),
            ('high', _('High Quality Only')),
            ('high,medium', _('High and Medium Quality')),
        ],
        required=False,
        label=_("Minimum Data Quality"),
        help_text=_("Filter data by quality level.")
    )

    # Spatial filtering options
    spatial_filter = forms.ChoiceField(
        choices=[
            ('none', _('No Spatial Filter')),
            ('country', _('Filter by Country')),
            ('bounding_box', _('Filter by Bounding Box')),
            ('radius', _('Filter by Radius from Point')),
        ],
        initial='none',
        label=_("Spatial Filter Type"),
        help_text=_("Choose how to spatially filter the data.")
    )

    # Bounding box coordinates (only used if spatial_filter=bounding_box)
    min_latitude = forms.FloatField(
        required=False,
        label=_("South Latitude"),
        min_value=-90,
        max_value=90,
        help_text=_("Southern boundary of the bounding box (decimal degrees).")
    )

    max_latitude = forms.FloatField(
        required=False,
        label=_("North Latitude"),
        min_value=-90,
        max_value=90,
        help_text=_("Northern boundary of the bounding box (decimal degrees).")
    )

    min_longitude = forms.FloatField(
        required=False,
        label=_("West Longitude"),
        min_value=-180,
        max_value=180,
        help_text=_("Western boundary of the bounding box (decimal degrees).")
    )

    max_longitude = forms.FloatField(
        required=False,
        label=_("East Longitude"),
        min_value=-180,
        max_value=180,
        help_text=_("Eastern boundary of the bounding box (decimal degrees).")
    )

    # Radius search (only used if spatial_filter=radius)
    center_latitude = forms.FloatField(
        required=False,
        label=_("Center Latitude"),
        min_value=-90,
        max_value=90,
        help_text=_("Latitude of the center point (decimal degrees).")
    )

    center_longitude = forms.FloatField(
        required=False,
        label=_("Center Longitude"),
        min_value=-180,
        max_value=180,
        help_text=_("Longitude of the center point (decimal degrees).")
    )

    radius_km = forms.FloatField(
        required=False,
        label=_("Radius (km)"),
        min_value=0,
        help_text=_("Radius from the center point in kilometers.")
    )

    # Advanced options for large exports
    chunk_size = forms.IntegerField(
        required=False,
        initial=10000,
        min_value=1000,
        max_value=100000,
        label=_("Chunk Size"),
        help_text=_("Number of records per file for large exports (will create multiple files).")
    )

    email_notification = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Send Email Notification"),
        help_text=_("Send an email when the export is ready (recommended for large exports).")
    )

    compression = forms.ChoiceField(
        choices=[
            ('none', _('No Compression')),
            ('zip', _('ZIP Archive')),
            ('gzip', _('GZIP Compression')),
        ],
        initial='none',
        required=False,
        label=_("Compression"),
        help_text=_("Compress the export files to reduce size.")
    )

    def clean(self):
        cleaned_data = super().clean()

        # Validate date range
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            self.add_error('date_to', _("End date must be after start date."))

        # Validate spatial filter parameters
        spatial_filter = cleaned_data.get('spatial_filter')

        if spatial_filter == 'bounding_box':
            min_lat = cleaned_data.get('min_latitude')
            max_lat = cleaned_data.get('max_latitude')
            min_lon = cleaned_data.get('min_longitude')
            max_lon = cleaned_data.get('max_longitude')

            if None in (min_lat, max_lat, min_lon, max_lon):
                self.add_error('spatial_filter', _("All bounding box coordinates are required."))
            elif min_lat >= max_lat:
                self.add_error('min_latitude', _("South latitude must be less than north latitude."))
            elif min_lon >= max_lon:
                self.add_error('min_longitude', _("West longitude must be less than east longitude."))

        elif spatial_filter == 'radius':
            center_lat = cleaned_data.get('center_latitude')
            center_lon = cleaned_data.get('center_longitude')
            radius = cleaned_data.get('radius_km')

            if None in (center_lat, center_lon, radius):
                self.add_error('spatial_filter', _("Center coordinates and radius are required."))
            elif radius <= 0:
                self.add_error('radius_km', _("Radius must be greater than zero."))

        return cleaned_data


class BulkImportForm(forms.Form):
    """Form for batch import operations"""

    source_directory = forms.CharField(
        label=_("Source Directory"),
        help_text=_("Directory containing multiple data files to import."),
        initial="/media/data/import"
    )

    file_pattern = forms.CharField(
        label=_("File Pattern"),
        help_text=_("Pattern to match files (e.g., '*.csv', 'station_data_*.txt')."),
        initial="*.csv"
    )

    import_type = forms.ChoiceField(
        choices=BaseImportForm.IMPORT_CHOICES,
        label=_("Import Type"),
        initial='climate_data',
        help_text=_("Type of data being imported.")
    )

    schedule = forms.ChoiceField(
        choices=[
            ('now', _('Import Now')),
            ('later', _('Schedule Import')),
        ],
        initial='now',
        label=_("Import Timing"),
        help_text=_("Choose when to run the import.")
    )

    scheduled_time = forms.DateTimeField(
        required=False,
        label=_("Scheduled Time"),
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text=_("When to run the scheduled import.")
    )

    notification_email = forms.EmailField(
        required=False,
        label=_("Notification Email"),
        help_text=_("Email to notify when import is complete.")
    )

    def clean(self):
        cleaned_data = super().clean()

        # Validate scheduled import
        if cleaned_data.get('schedule') == 'later' and not cleaned_data.get('scheduled_time'):
            self.add_error('scheduled_time', _("Scheduled time is required for scheduled imports."))

        # Validate source directory
        source_dir = cleaned_data.get('source_directory')
        if source_dir:
            if not os.path.exists(source_dir):
                self.add_error('source_directory', _("Directory does not exist."))
            elif not os.path.isdir(source_dir):
                self.add_error('source_directory', _("Path is not a directory."))

        return cleaned_data


class DataTransformForm(forms.Form):
    """Form for transforming imported data before loading into database"""

    # Temperature conversion
    temperature_unit = forms.ChoiceField(
        choices=[
            ('C', _('Celsius (°C)')),
            ('F', _('Fahrenheit (°F)')),
            ('K', _('Kelvin (K)')),
        ],
        initial='C',
        label=_("Temperature Unit in Data"),
        help_text=_("Unit of temperature in the imported data (will be converted to Celsius).")
    )

    # Precipitation conversion
    precipitation_unit = forms.ChoiceField(
        choices=[
            ('mm', _('Millimeters (mm)')),
            ('in', _('Inches (in)')),
            ('cm', _('Centimeters (cm)')),
        ],
        initial='mm',
        label=_("Precipitation Unit in Data"),
        help_text=_("Unit of precipitation in the imported data (will be converted to mm).")
    )

    # Timestamp timezone
    timezone = forms.ChoiceField(
        choices=[
            ('UTC', 'UTC'),
            ('local', _('Local Time (as specified in data)')),
        ],
        initial='UTC',
        label=_("Timestamp Timezone"),
        help_text=_("Timezone of timestamps in the imported data.")
    )

    # Data validation
    validate_data = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Validate Data"),
        help_text=_("Validate data against reasonable ranges and mark outliers.")
    )

    # Missing data handling
    missing_data = forms.ChoiceField(
        choices=[
            ('skip', _('Skip Records with Missing Data')),
            ('null', _('Import as NULL Values')),
            ('interpolate', _('Interpolate from Surrounding Values')),
        ],
        initial='null',
        label=_("Missing Data Handling"),
        help_text=_("How to handle missing values in the imported data.")
    )


# Add a new form for data stack settings
class DataStackSettingsForm(forms.ModelForm):
    """Form for configuring a weather station's data stack settings"""
    
    class Meta:
        model = WeatherStation
        fields = ['max_stack_size', 'auto_process', 'process_threshold']
        widgets = {
            'max_stack_size': forms.NumberInput(attrs={'class': 'form-control'}),
            'process_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'auto_process': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'max_stack_size': _("Maximum number of readings that can be stored in the stack"),
            'auto_process': _("Automatically process readings when threshold is reached"),
            'process_threshold': _("Number of readings that triggers automatic processing"),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        max_stack_size = cleaned_data.get('max_stack_size')
        process_threshold = cleaned_data.get('process_threshold')
        
        if max_stack_size is not None and process_threshold is not None:
            if process_threshold > max_stack_size:
                self.add_error('process_threshold', _("Process threshold cannot be greater than max stack size"))
                
        return cleaned_data