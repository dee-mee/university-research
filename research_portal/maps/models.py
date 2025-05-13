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
            
            # Only set season if the field exists in the database
            try:
                # Determine whether station is in Southern Hemisphere
                is_southern = self.station.is_southern_hemisphere
                
                # Determine season based on month and hemisphere
                if is_southern:
                    # Southern Hemisphere has opposite seasons
                    if self.month in [12, 1, 2]:
                        self.season = 'summer'
                    elif self.month in [3, 4, 5]:
                        self.season = 'autumn'
                    elif self.month in [6, 7, 8]:
                        self.season = 'winter'
                    else:  # 9, 10, 11
                        self.season = 'spring'
                else:
                    # Northern Hemisphere seasons
                    if self.month in [12, 1, 2]:
                        self.season = 'winter'
                    elif self.month in [3, 4, 5]:
                        self.season = 'spring'
                    elif self.month in [6, 7, 8]:
                        self.season = 'summer'
                    else:  # 9, 10, 11
                        self.season = 'autumn'
            except Exception:
                # If the season field doesn't exist yet (e.g., during migrations),
                # just skip setting it rather than failing
                logger.debug("Could not set season field, it may not exist yet", exc_info=True)
                pass
                
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