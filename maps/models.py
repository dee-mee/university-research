from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import ArrayField
import json
import logging
from datetime import datetime
from django.db import transaction
from django.conf import settings

# Add import for Dataset model
from data_repository.models import Dataset

# Set up logger
logger = logging.getLogger(__name__)

class Country(models.Model):
    """Country information for geographic filtering"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True)  # ISO 3166-1 alpha-3 code
    boundary = models.MultiPolygonField(srid=4326, geography=True, null=True, blank=True)
    # Add field for hemisphere to properly calculate seasons
    is_southern_hemisphere = models.BooleanField(
        default=False, 
        help_text="Whether this country is predominantly in the Southern Hemisphere"
    )
    
    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ["name"]
    
    def __str__(self):
        return self.name


class WeatherStation(models.Model):
    """Weather station or climate data collection point"""
    name = models.CharField(max_length=255)
    station_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    location = models.PointField(srid=4326, geography=True, spatial_index=True)  # Add spatial_index=True for better performance
    altitude = models.FloatField(help_text="Altitude in meters above sea level", null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, related_name='stations')
    region = models.CharField(max_length=100, blank=True, null=True, help_text="Administrative region within country")
    is_active = models.BooleanField(default=True)
    date_installed = models.DateField(null=True, blank=True)
    date_decommissioned = models.DateField(null=True, blank=True)
    date_decommissioned = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Data availability flags
    has_temperature = models.BooleanField(default=True)
    has_precipitation = models.BooleanField(default=True)
    has_humidity = models.BooleanField(default=True)
    has_wind = models.BooleanField(default=True)
    has_air_quality = models.BooleanField(default=False)
    has_soil_moisture = models.BooleanField(default=False)
    has_water_level = models.BooleanField(default=False)
    
    # Replace TextField with JSONField for better performance and data integrity
    # Fall back to TextField if Django version doesn't support JSONField
    try:
        from django.db.models import JSONField
        data_stack = JSONField(blank=True, null=True, default=list, 
            help_text="Stack of pending data readings")
    except ImportError:
        data_stack = models.TextField(blank=True, null=True, 
            help_text="JSON serialized stack of pending data readings")
    
    last_data_feed = models.DateTimeField(null=True, blank=True, help_text="Timestamp of last data feed")
    max_stack_size = models.PositiveIntegerField(default=1000, help_text="Maximum number of items in the data stack")
    auto_process = models.BooleanField(default=False, help_text="Whether to automatically process data when stack reaches threshold")
    process_threshold = models.PositiveIntegerField(default=100, help_text="Threshold for auto-processing stack data")
    
    # Relationship to Dataset model
    datasets = models.ManyToManyField(Dataset, blank=True, related_name='weather_stations')
    
    class Meta:
        verbose_name = _("Weather Station")
        verbose_name_plural = _("Weather Stations")
        ordering = ["name"]
        indexes = [
            models.Index(fields=['country']),
            models.Index(fields=['is_active']),
            # Add index for timestamp fields to improve querying
            models.Index(fields=['last_data_feed']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.station_id})"
        return f"{self.name} ({self.station_id})"
    
    @property
    def latitude(self):
        return self.location.y
    
    @property
    def longitude(self):
        return self.location.x

    @property
    def is_southern_hemisphere(self):
        """Determine if the station is in the Southern Hemisphere"""
        if self.country:
            try:
                # Try to get the is_southern_hemisphere field
                return self.country.is_southern_hemisphere
            except AttributeError:
                # Fall back to latitude if the field doesn't exist yet
                pass
        # Default to latitude check
        return self.latitude < 0

    def to_representation(self):
        """Convert to GeoJSON compatible format"""
        return {
            'type': 'Feature',
            'properties': {
                'id': self.id,
                'name': self.name,
                'station_id': self.station_id,
                'country': self.country.name if self.country else None,
                'is_active': self.is_active,
                'altitude': self.altitude,
                'data_types': self.available_data_types(),
            },
            'geometry': {
                'type': 'Point',
                'coordinates': [self.longitude, self.latitude]
            }
        }
    
    def available_data_types(self):
        """Return a list of data types available from this station"""
        data_types = []
        if self.has_temperature:
            data_types.append('temperature')
        if self.has_precipitation:
            data_types.append('precipitation')
        if self.has_humidity:
            data_types.append('humidity')
        if self.has_wind:
            data_types.append('wind')
        if self.has_air_quality:
            data_types.append('air_quality')
        if self.has_soil_moisture:
            data_types.append('soil_moisture')
        if self.has_water_level:
            data_types.append('water_level')
        return data_types

    def push_data(self, data_dict):
        """
        Push a data reading onto the stack for later processing
        
        Args:
            data_dict (dict): Dictionary containing the weather measurement data
        
        Returns:
            bool: True if successfully added, False if stack is full
        """
        # Validate input data
        if not isinstance(data_dict, dict):
            logger.error(f"Invalid data format for station {self.id}: Expected dict, got {type(data_dict)}")
            return False
            
        # Initialize stack_data based on the field type (JSONField or TextField)
        if isinstance(self.data_stack, list):
            # JSONField case
            stack_data = self.data_stack or []
        else:
            # TextField case - needs parsing
            stack_data = []
            if self.data_stack:
                try:
                    stack_data = json.loads(self.data_stack)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse data_stack for station {self.id}")
                    stack_data = []
        
        # Check if stack is full
        if len(stack_data) >= self.max_stack_size:
            logger.warning(f"Data stack full for station {self.id}")
            return False
            
        # Add timestamp if not provided
        if 'timestamp' not in data_dict:
            data_dict['timestamp'] = datetime.now().isoformat()
        
        # Push data to stack
        stack_data.append(data_dict)
        
        # Update the stack with transaction for data safety
        with transaction.atomic():
            if isinstance(self.data_stack, list):
                # JSONField case
                self.data_stack = stack_data
            else:
                # TextField case - needs serialization
                self.data_stack = json.dumps(stack_data)
            
            self.last_data_feed = datetime.now()
            self.save(update_fields=['data_stack', 'last_data_feed'])
        
        # Auto process if enabled and threshold reached
        if self.auto_process and len(stack_data) >= self.process_threshold:
            logger.info(f"Auto-processing {len(stack_data)} readings for station {self.id}")
            self.process_data_stack()
        
        return True
    
    def pop_data(self):
        """
        Pop the most recent data reading from the stack
        
        Returns:
            dict: The data reading, or None if stack is empty
        """
        # Initialize stack_data based on the field type (JSONField or TextField)
        if isinstance(self.data_stack, list):
            # JSONField case
            stack_data = self.data_stack or []
        else:
            # TextField case - needs parsing
            if not self.data_stack:
                return None
                
            try:
                stack_data = json.loads(self.data_stack)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse data_stack for station {self.id}")
                return None
                
        if not stack_data:
            return None
                
        # Pop the last item
        data = stack_data.pop()
        
        # Update the stack with transaction for data safety
        with transaction.atomic():
            if isinstance(self.data_stack, list):
                # JSONField case
                self.data_stack = stack_data
            else:
                # TextField case - needs serialization
                self.data_stack = json.dumps(stack_data)
                
            self.save(update_fields=['data_stack'])
            
        return data
    
    def peek_data(self):
        """
        Look at the most recent data reading without removing it
        
        Returns:
            dict: The data reading, or None if stack is empty
        """
        # Initialize stack_data based on the field type (JSONField or TextField)
        if isinstance(self.data_stack, list):
            # JSONField case
            stack_data = self.data_stack or []
        else:
            # TextField case - needs parsing
            if not self.data_stack:
                return None
                
            try:
                stack_data = json.loads(self.data_stack)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse data_stack for station {self.id}")
                return None
                
        if not stack_data:
            return None
                
        return stack_data[-1]
    
    def stack_size(self):
        """
        Get the current size of the data stack
        
        Returns:
            int: Number of items in the stack
        """
        # Initialize stack_data based on the field type (JSONField or TextField)
        if isinstance(self.data_stack, list):
            # JSONField case
            return len(self.data_stack or [])
        else:
            # TextField case - needs parsing
            if not self.data_stack:
                return 0
                
            try:
                stack_data = json.loads(self.data_stack)
                return len(stack_data)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse data_stack for station {self.id}")
                return 0
    
    def process_data_stack(self):
        """
        Process all data in the stack and create ClimateData records
        
        Returns:
            int: Number of records processed
        """
        # Import here to avoid circular import at module level
        # but use the model registry to avoid fully circular import
        from django.apps import apps
        ClimateData = apps.get_model('maps', 'ClimateData')
        
        # Initialize stack_data based on the field type (JSONField or TextField)
        if isinstance(self.data_stack, list):
            # JSONField case
            stack_data = self.data_stack or []
        else:
            # TextField case - needs parsing
            if not self.data_stack:
                return 0
                
            try:
                stack_data = json.loads(self.data_stack)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse data_stack for station {self.id}")
                return 0
            
        if not stack_data:
            return 0
            
        count = 0
        # Wrap the processing in a transaction for data integrity
        try:
            with transaction.atomic():
                new_climate_data = []
                
                for data_reading in stack_data:
                    # Convert timestamp string to datetime
                    timestamp = (
                        datetime.fromisoformat(data_reading.pop('timestamp'))
                        if isinstance(data_reading.get('timestamp'), str)
                        else data_reading.pop('timestamp', datetime.now())
                    )
                    
                    # Create climate data record
                    climate_data = ClimateData(
                        station=self,
                        timestamp=timestamp,
                        **{k: v for k, v in data_reading.items() if hasattr(ClimateData, k)}
                    )
                    # Save will be called later in bulk_create
                    new_climate_data.append(climate_data)
                    count += 1
                
                # Bulk create for better performance
                if new_climate_data:
                    ClimateData.objects.bulk_create(new_climate_data)
                    
                # Clear the stack after successful processing
                if isinstance(self.data_stack, list):
                    # JSONField case
                    self.data_stack = []
                else:
                    # TextField case - needs serialization
                    self.data_stack = json.dumps([])
                    
                self.save(update_fields=['data_stack'])
                
            logger.info(f"Successfully processed {count} readings for station {self.id}")
            return count
            
        except Exception as e:
            # Log error with more details
            logger.error(f"Error processing data stack for station {self.id}: {str(e)}", exc_info=True)
            return 0
    
    def link_to_repository(self, dataset_id):
        """Associate this station with a dataset in the repository"""
        try:
            dataset = Dataset.objects.get(id=dataset_id)
            self.datasets.add(dataset)
            return True
        except Dataset.DoesNotExist:
            logger.error(f"Dataset with ID {dataset_id} does not exist")
            return False
    
    def get_repository_datasets(self):
        """Get all datasets in the repository linked to this station"""
        return self.datasets.all()
        
    def get_latest_dataset_version(self, dataset_id=None):
        """Get latest version of a linked dataset or any dataset if id not specified"""
        from data_repository.models import DatasetVersion
        
        if dataset_id:
            try:
                dataset = self.datasets.get(id=dataset_id)
                return DatasetVersion.objects.filter(dataset=dataset).order_by('-version_number').first()
            except Dataset.DoesNotExist:
                return None
        else:
            # Get the latest version of any linked dataset
            latest_versions = []
            for dataset in self.datasets.all():
                latest_version = DatasetVersion.objects.filter(dataset=dataset).order_by('-version_number').first()
                if latest_version:
                    latest_versions.append(latest_version)
                    
            if not latest_versions:
                return None
                
            # Return the version with the most recent created_at date
            return sorted(latest_versions, key=lambda v: v.created_at, reverse=True)[0]
            
    def export_to_repository(self, title, description, category_id, creator_id):
        """
        Export station data to the data repository
        
        Args:
            title: Title for the new dataset
            description: Description for the new dataset
            category_id: ID of the category for the new dataset
            creator_id: ID of the user creating the dataset
            
        Returns:
            tuple: (dataset, created) where created is True if a new dataset was created
        """
        from django.contrib.auth import get_user_model
        from data_repository.models import DatasetCategory, DatasetVersion
        import tempfile
        import os
        import csv
        from django.core.files import File
        
        User = get_user_model()
        
        try:
            category = DatasetCategory.objects.get(id=category_id)
            creator = User.objects.get(id=creator_id)
            
            # Check for existing dataset with this station
            dataset = None
            created = False
            
            # Create a new dataset
            dataset = Dataset.objects.create(
                title=title,
                description=description,
                category=category,
                created_by=creator,
                status='published',
                metadata={
                    'source_type': 'weather_station',
                    'station_id': self.id,
                    'station_name': self.name,
                    'data_types': self.available_data_types(),
                    'location': {
                        'latitude': self.latitude,
                        'longitude': self.longitude,
                    }
                }
            )
            created = True
            
            # Link this station to the dataset
            self.datasets.add(dataset)
            
            # Export data to CSV file for the first version
            climate_data = self.climate_data.all().order_by('timestamp')
            
            if climate_data.exists():
                # Create a temporary file to store the CSV data
                with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_file:
                    temp_path = temp_file.name
                    
                    # Create CSV writer
                    writer = csv.writer(temp_file)
                    
                    # Write header row
                    header = ['timestamp', 'year', 'month', 'season', 'temperature', 'humidity',
                              'precipitation', 'air_quality_index', 'wind_speed', 'wind_direction',
                              'barometric_pressure', 'cloud_cover', 'soil_moisture', 'water_level',
                              'data_quality', 'uv_index']
                    writer.writerow(header)
                    
                    # Write data rows
                    for data in climate_data:
                        row = [
                            data.timestamp.isoformat(),
                            data.year,
                            data.month,
                            data.season,
                            data.temperature if data.temperature is not None else '',
                            data.humidity if data.humidity is not None else '',
                            data.precipitation if data.precipitation is not None else '',
                            data.air_quality_index if data.air_quality_index is not None else '',
                            data.wind_speed if data.wind_speed is not None else '',
                            data.wind_direction if data.wind_direction is not None else '',
                            data.barometric_pressure if data.barometric_pressure is not None else '',
                            data.cloud_cover if data.cloud_cover is not None else '',
                            data.soil_moisture if data.soil_moisture is not None else '',
                            data.water_level if data.water_level is not None else '',
                            data.data_quality,
                            data.uv_index if data.uv_index is not None else ''
                        ]
                        writer.writerow(row)
                
                # Create first dataset version
                with open(temp_path, 'rb') as file_obj:
                    version = DatasetVersion.objects.create(
                        dataset=dataset,
                        version_number='1.0.0',
                        created_by=creator,
                        description=f"Initial version with data from {self.name} weather station",
                        file_path=File(file_obj, name=f"{self.name.replace(' ', '_')}_data.csv"),
                        is_current=True,
                        metadata={
                            'row_count': climate_data.count(),
                            'time_series': True,
                            'time_start': climate_data.earliest('timestamp').timestamp.isoformat() if climate_data.exists() else None,
                            'time_end': climate_data.latest('timestamp').timestamp.isoformat() if climate_data.exists() else None,
                            'time_resolution': 'variable',
                            'variables': [dt for dt in self.available_data_types() if any(
                                getattr(cd, dt, None) is not None for cd in climate_data[:10]
                            )]
                        }
                    )
                
                # Clean up temporary file
                os.unlink(temp_path)
                
            return dataset, created
            
        except (DatasetCategory.DoesNotExist, User.DoesNotExist) as e:
            logger.error(f"Error exporting station {self.id} to repository: {str(e)}")
            return None, False
        except Exception as e:
            logger.error(f"Unexpected error exporting station {self.id} to repository: {str(e)}", exc_info=True)
            return None, False
        

class WeatherDataType(models.Model):
    """Defines different types of weather data that can be queried individually"""
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True, help_text="Unit of measurement")
    min_value = models.FloatField(null=True, blank=True, help_text="Minimum valid value")
    max_value = models.FloatField(null=True, blank=True, help_text="Maximum valid value")
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Icon identifier for UI display")
    
    class Meta:
        verbose_name = _("Weather Data Type")
        verbose_name_plural = _("Weather Data Types")
        ordering = ["name"]
    
    def __str__(self):
        return f"{self.display_name} ({self.unit})" if self.unit else self.display_name


class ClimateData(models.Model):
    """Climate data measurements collected from weather stations"""
    QUALITY_CHOICES = [
        ('high', _('High')),
        ('medium', _('Medium')),
        ('low', _('Low')),
        ('uncertain', _('Uncertain')),
    ]
    
    SEASON_CHOICES = [
        ('winter', _('Winter')),
        ('spring', _('Spring')),
        ('summer', _('Summer')),
        ('autumn', _('Autumn')),
    ]
    
    station = models.ForeignKey(WeatherStation, on_delete=models.CASCADE, related_name='climate_data')
    timestamp = models.DateTimeField(db_index=True)
    year = models.IntegerField(db_index=True, help_text="Year of the measurement for easier filtering", default=2000)
    month = models.IntegerField(db_index=True, help_text="Month of the measurement for easier filtering", default=1)
    season = models.CharField(
        max_length=10, 
        choices=SEASON_CHOICES, 
        db_index=True, 
        help_text="Season of the measurement",
        default='summer'  # Default to summer for existing records
    )
    
    # Weather measurements with enhanced validation
    temperature = models.FloatField(
        help_text="Temperature in Celsius", 
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
        null=True, blank=True
    )
    humidity = models.FloatField(
        help_text="Relative humidity (%)", 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True
    )
    precipitation = models.FloatField(
        help_text="Precipitation in mm", 
        validators=[MinValueValidator(0), MaxValueValidator(10000)],
        null=True, blank=True
    )
    air_quality_index = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(500)],
        null=True, blank=True
    )
    wind_speed = models.FloatField(
        help_text="Wind speed in m/s", 
        validators=[MinValueValidator(0), MaxValueValidator(200)],
        null=True, blank=True
    )
    wind_direction = models.FloatField(
        help_text="Wind direction in degrees (0-360)",
        validators=[MinValueValidator(0), MaxValueValidator(360)],
        null=True, blank=True
    )
    barometric_pressure = models.FloatField(
        help_text="Pressure in hPa", 
        validators=[MinValueValidator(800), MaxValueValidator(1200)],
        null=True, blank=True
    )
    cloud_cover = models.FloatField(
        help_text="Cloud cover (%)",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True
    )
    soil_moisture = models.FloatField(
        help_text="Soil moisture (%)",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True
    )
    water_level = models.FloatField(
        help_text="Water level in meters", 
        validators=[MinValueValidator(-50), MaxValueValidator(100)],
        null=True, blank=True
    )
    data_quality = models.CharField(max_length=10, choices=QUALITY_CHOICES, default='medium')
    uv_index = models.FloatField(
        help_text="UV index",
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Climate Data")
        verbose_name_plural = _("Climate Data")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['station', 'timestamp']),
            models.Index(fields=['year', 'month']),
            models.Index(fields=['station', 'year']),
            models.Index(fields=['season']),
            models.Index(fields=['station', 'season']),
        ]
        # Add constraint to speed up spatial/temporal queries
        constraints = [
            models.UniqueConstraint(
                fields=['station', 'timestamp'], 
                name='unique_station_timestamp'
            )
        ]
    
    def __str__(self):
        return f"{self.station.name} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        # Auto-populate year and month fields
        if self.timestamp:
            self.year = self.timestamp.year
            self.month = self.timestamp.month
            
            # No regional season determination - each station stands alone
            # Season needs to be explicitly set if required
                
        super().save(*args, **kwargs)


class DataExport(models.Model):
    """Tracks data exports by users with enhanced filtering capabilities"""
    """Tracks data exports by users with enhanced filtering capabilities"""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('geojson', 'GeoJSON'),
        ('netcdf', 'NetCDF'),
        ('excel', 'Excel'),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]
    
    # Existing fields - do not change these
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    stations = models.ManyToManyField(WeatherStation, blank=True, related_name='exports')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    data_types = models.ManyToManyField(WeatherDataType, related_name='exports', help_text="Types of weather data to include")
    bounding_box = models.PolygonField(srid=4326, null=True, blank=True, help_text="Geographic area for the export")
    date_from = models.DateTimeField()
    date_to = models.DateTimeField()
    years = ArrayField(models.IntegerField(), blank=True, null=True, help_text="Specific years to include")
    min_data_quality = models.CharField(max_length=10, choices=ClimateData.QUALITY_CHOICES, default='medium')
    export_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    include_metadata = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0, help_text="Number of times this export has been downloaded")
    error_log = models.TextField(blank=True, null=True)
    
    # New fields we're adding
    file = models.FileField(upload_to='exports/', null=True, blank=True, help_text="The exported data file")
    updated_at = models.DateTimeField(auto_now=True)
    last_downloaded = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    class Meta:
        verbose_name = _("Data Export")
        verbose_name_plural = _("Data Exports")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Export {self.id} - {self.get_export_format_display()} - {self.created_at}"
    
    def get_download_url(self):
        """Generate a secure download URL with a signature"""
        if not self.file:
            return None
            
        from django.core.signing import Signer
        from django.urls import reverse
        
        signer = Signer()
        signature = signer.sign(str(self.id)).split(':')[1]
        
        return reverse('maps:secure_export_download', kwargs={
            'export_id': self.id,
            'signature': signature
        })


class WeatherAlert(models.Model):
    """Alerts for extreme weather conditions"""
    SEVERITY_CHOICES = [
        ('info', _('Information')),
        ('warning', _('Warning')),
        ('danger', _('Danger')),
        ('emergency', _('Emergency')),
    ]
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('resolved', _('Resolved')),
        ('monitoring', _('Monitoring')),
    ]
    
    station = models.ForeignKey(WeatherStation, on_delete=models.CASCADE, related_name='alerts')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    affected_area = models.PolygonField(srid=4326, null=True, blank=True, help_text="Geographic area affected by this alert")
    
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    affected_area = models.PolygonField(srid=4326, null=True, blank=True, help_text="Geographic area affected by this alert")
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    data_type = models.ForeignKey(WeatherDataType, on_delete=models.CASCADE, related_name='alerts', null=True)
    threshold_value = models.FloatField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Optional: Notification settings
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    notify_push = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = _("Weather Alert")
        verbose_name_plural = _("Weather Alerts")
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.get_severity_display()}: {self.title} ({self.station.name})"

# Import field models at the end of the file to ensure Django recognizes them
# This ensures all models are properly included in migrations

# Import field-related models at the end of the file
from .field_models import (
    AlertType,
    AlertSeverity,
    Alert, 
    DeviceType, 
    FieldDevice, 
    DeviceCalibration, 
    FieldDataRecord, 
    FieldDataUpload,
    FieldDataUploadManual
)