from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import ArrayField
import json
from datetime import datetime


class Country(models.Model):
    """Country information for geographic filtering"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True)  # ISO 3166-1 alpha-3 code
    boundary = models.MultiPolygonField(srid=4326, geography=True, null=True, blank=True)
    
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
    location = models.PointField(srid=4326, geography=True)
    altitude = models.FloatField(help_text="Altitude in meters above sea level", null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, related_name='stations')
    region = models.CharField(max_length=100, blank=True, null=True, help_text="Administrative region within country")
    is_active = models.BooleanField(default=True)
    date_installed = models.DateField(null=True, blank=True)
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
    
    # Data stacking fields
    data_stack = models.TextField(blank=True, null=True, help_text="JSON serialized stack of pending data readings")
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
        ]
    
    def __str__(self):
        return f"{self.name} ({self.station_id})"
    
    @property
    def latitude(self):
        return self.location.y
    
    @property
    def longitude(self):
        return self.location.x

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
        stack_data = []
        if self.data_stack:
            try:
                stack_data = json.loads(self.data_stack)
            except json.JSONDecodeError:
                stack_data = []
        
        # Check if stack is full
        if len(stack_data) >= self.max_stack_size:
            return False
            
        # Add timestamp if not provided
        if 'timestamp' not in data_dict:
            data_dict['timestamp'] = datetime.now().isoformat()
        
        # Push data to stack
        stack_data.append(data_dict)
        self.data_stack = json.dumps(stack_data)
        self.last_data_feed = datetime.now()
        self.save(update_fields=['data_stack', 'last_data_feed'])
        
        # Auto process if enabled and threshold reached
        if self.auto_process and len(stack_data) >= self.process_threshold:
            self.process_data_stack()
        
        return True
    
    def pop_data(self):
        """
        Pop the most recent data reading from the stack
        
        Returns:
            dict: The data reading, or None if stack is empty
        """
        if not self.data_stack:
            return None
            
        try:
            stack_data = json.loads(self.data_stack)
            if not stack_data:
                return None
                
            data = stack_data.pop()
            self.data_stack = json.dumps(stack_data)
            self.save(update_fields=['data_stack'])
            return data
        except json.JSONDecodeError:
            return None
    
    def peek_data(self):
        """
        Look at the most recent data reading without removing it
        
        Returns:
            dict: The data reading, or None if stack is empty
        """
        if not self.data_stack:
            return None
            
        try:
            stack_data = json.loads(self.data_stack)
            if not stack_data:
                return None
                
            return stack_data[-1]
        except json.JSONDecodeError:
            return None
    
    def stack_size(self):
        """
        Get the current size of the data stack
        
        Returns:
            int: Number of items in the stack
        """
        if not self.data_stack:
            return 0
            
        try:
            stack_data = json.loads(self.data_stack)
            return len(stack_data)
        except json.JSONDecodeError:
            return 0
    
    def process_data_stack(self):
        """
        Process all data in the stack and create ClimateData records
        
        Returns:
            int: Number of records processed
        """
        from .models import ClimateData
        
        if not self.data_stack:
            return 0
            
        try:
            stack_data = json.loads(self.data_stack)
            if not stack_data:
                return 0
            
            count = 0
            for data_reading in stack_data:
                # Convert timestamp string to datetime
                timestamp = datetime.fromisoformat(data_reading.pop('timestamp')) if isinstance(data_reading.get('timestamp'), str) else data_reading.pop('timestamp', datetime.now())
                
                # Create climate data record
                climate_data = ClimateData(
                    station=self,
                    timestamp=timestamp,
                    **{k: v for k, v in data_reading.items() if hasattr(ClimateData, k)}
                )
                climate_data.save()
                count += 1
                
            # Clear the stack after processing
            self.data_stack = json.dumps([])
            self.save(update_fields=['data_stack'])
            return count
        except Exception as e:
            # Log error
            print(f"Error processing data stack: {e}")
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
    
    station = models.ForeignKey(WeatherStation, on_delete=models.CASCADE, related_name='climate_data')
    timestamp = models.DateTimeField(db_index=True)
    year = models.IntegerField(db_index=True, help_text="Year of the measurement for easier filtering")
    month = models.IntegerField(db_index=True, help_text="Month of the measurement for easier filtering")
    
    # Weather measurements
    temperature = models.FloatField(help_text="Temperature in Celsius", null=True, blank=True)
    humidity = models.FloatField(
        help_text="Relative humidity (%)", 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True
    )
    precipitation = models.FloatField(help_text="Precipitation in mm", null=True, blank=True)
    air_quality_index = models.IntegerField(null=True, blank=True)
    wind_speed = models.FloatField(help_text="Wind speed in m/s", null=True, blank=True)
    wind_direction = models.FloatField(
        help_text="Wind direction in degrees (0-360)",
        validators=[MinValueValidator(0), MaxValueValidator(360)],
        null=True, blank=True
    )
    barometric_pressure = models.FloatField(help_text="Pressure in hPa", null=True, blank=True)
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
    water_level = models.FloatField(help_text="Water level in meters", null=True, blank=True)
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
        super().save(*args, **kwargs)


class DataExport(models.Model):
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
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    stations = models.ManyToManyField(WeatherStation, blank=True, related_name='exports')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    data_types = models.ManyToManyField(WeatherDataType, related_name='exports', help_text="Types of weather data to include")
    
    # Spatial filters
    bounding_box = models.PolygonField(srid=4326, null=True, blank=True, help_text="Geographic area for the export")
    
    # Temporal filters
    date_from = models.DateTimeField()
    date_to = models.DateTimeField()
    years = ArrayField(models.IntegerField(), blank=True, null=True, help_text="Specific years to include")
    
    # Other filters
    min_data_quality = models.CharField(max_length=10, choices=ClimateData.QUALITY_CHOICES, default='medium')
    
    # Export details
    export_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    include_metadata = models.BooleanField(default=True)
    file_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = _("Data Export")
        verbose_name_plural = _("Data Exports")
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Export {self.export_format} - {self.created_at}"


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
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    data_type = models.ForeignKey(WeatherDataType, on_delete=models.CASCADE, related_name='alerts')
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