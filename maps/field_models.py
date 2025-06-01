from django.contrib.gis.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime, timedelta
from .models import WeatherStation, ClimateData

class AlertType(models.TextChoices):
    """Alert types for field devices"""
    BATTERY_LOW = 'battery_low', 'Battery Low'
    SIGNAL_WEAK = 'signal_weak', 'Weak Signal'
    CONNECTION_LOST = 'connection_lost', 'Connection Lost'
    TEMPERATURE_HIGH = 'temperature_high', 'High Temperature'
    TEMPERATURE_LOW = 'temperature_low', 'Low Temperature'
    HUMIDITY_HIGH = 'humidity_high', 'High Humidity'
    HUMIDITY_LOW = 'humidity_low', 'Low Humidity'
    CALIBRATION_DUE = 'calibration_due', 'Calibration Due'
    MAINTENANCE_REQUIRED = 'maintenance_required', 'Maintenance Required'
    CUSTOM = 'custom', 'Custom Alert'


class AlertSeverity(models.TextChoices):
    """Alert severity levels"""
    INFO = 'info', 'Information'
    WARNING = 'warning', 'Warning'
    CRITICAL = 'critical', 'Critical'


class Alert(models.Model):
    """Model for device alerts"""
    device = models.ForeignKey(
        'FieldDevice',
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    alert_type = models.CharField(
        max_length=50,
        choices=AlertType.choices
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(
        max_length=20,
        choices=AlertSeverity.choices,
        default=AlertSeverity.WARNING
    )
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device']),
            models.Index(fields=['alert_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['acknowledged']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.get_alert_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def acknowledge(self, user):
        """Acknowledge the alert"""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()

class DeviceType(models.Model):
    """Defines types of field devices that can be used for data collection"""
    name = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100)
    model_number = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Technical specifications
    PROTOCOL_CHOICES = [
        ('wifi', _('WiFi')),
        ('lora', _('LoRa')),
        ('cellular', _('Cellular')),
        ('bluetooth', _('Bluetooth')),
        ('zigbee', _('ZigBee')),
        ('other', _('Other')),
    ]
    
    POWER_CHOICES = [
        ('battery', _('Battery')),
        ('solar', _('Solar')),
        ('mains', _('Mains Power')),
        ('hybrid', _('Hybrid')),
    ]
    
    communication_protocol = models.CharField(
        max_length=20, 
        choices=PROTOCOL_CHOICES,
        default='wifi'
    )
    power_source = models.CharField(
        max_length=20,
        choices=POWER_CHOICES,
        default='battery'
    )
    battery_life_days = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Expected battery life in days under normal operation"
    )
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    
    # Data capabilities
    has_temperature = models.BooleanField(default=True)
    has_precipitation = models.BooleanField(default=True)
    has_humidity = models.BooleanField(default=True)
    has_wind = models.BooleanField(default=True)
    has_air_quality = models.BooleanField(default=False)
    has_soil_moisture = models.BooleanField(default=False)
    has_water_level = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Device Type")
        verbose_name_plural = _("Device Types")
        ordering = ["name", "manufacturer"]
    
    def __str__(self):
        return f"{self.name} ({self.manufacturer})"


class FieldDevice(models.Model):
    """Physical device deployed in the field for data collection"""
    device_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name='devices')
    weather_station = models.ForeignKey(
        WeatherStation, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='field_devices',
        help_text="Associated weather station, if any"
    )
    location = models.PointField(
        srid=4326, 
        geography=True, 
        spatial_index=True,
        null=True,
        blank=True,
        help_text="Current device location"
    )
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('maintenance', _('Under Maintenance')),
        ('calibration', _('Calibration Required')),
        ('lost', _('Lost/Missing')),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Operational data
    installation_date = models.DateField(null=True, blank=True)
    last_communication = models.DateTimeField(null=True, blank=True)
    battery_level = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, 
        blank=True,
        help_text="Battery level in percentage"
    )
    signal_strength = models.IntegerField(
        validators=[MinValueValidator(-120), MaxValueValidator(0)],
        null=True,
        blank=True,
        help_text="Signal strength in dBm"
    )
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    
    # Configuration
    transmission_interval = models.PositiveIntegerField(
        default=60,
        help_text="Data transmission interval in minutes"
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Field Device")
        verbose_name_plural = _("Field Devices")
        ordering = ["name"]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['device_type']),
            models.Index(fields=['weather_station']),
            models.Index(fields=['battery_level']),
            models.Index(fields=['last_communication']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.device_id})"
    
    @property
    def battery_status(self):
        """Return the battery status category"""
        if self.battery_level is None:
            return _('Unknown')
        if self.battery_level < 20:
            return _('Low')
        elif self.battery_level < 50:
            return _('Medium')
        return _('Good')

    @property
    def needs_attention(self):
        """Determine if the device needs attention"""
        if not self.last_communication:
            return True
        if self.status in ['maintenance', 'calibration', 'lost']:
            return True
        if self.battery_level is not None and self.battery_level < 20:
            return True
        return False

    def get_battery_status_display(self):
        """Return a display-friendly version of battery status"""
        status = self.battery_status
        if status:
            return status
        return _('Unknown')

    def get_needs_attention_display(self):
        """Return a display-friendly version of needs_attention"""
        return _('Yes') if self.needs_attention else _('No')


class DeviceCalibration(models.Model):
    """Records calibration events for field devices"""
    device = models.ForeignKey(FieldDevice, on_delete=models.CASCADE, related_name='calibrations')
    calibration_date = models.DateTimeField()
    next_calibration_date = models.DateField(null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_DEFAULT,
        default=1,  # Default to admin user
        related_name='calibrations_performed'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Device Calibration")
        verbose_name_plural = _("Device Calibrations")


class FieldDataRecord(models.Model):
    """Individual data record from a field device"""
    upload = models.ForeignKey(
        'FieldDataUpload',
        on_delete=models.CASCADE,
        related_name='records'
    )
    device = models.ForeignKey(
        FieldDevice,
        on_delete=models.CASCADE,
        related_name='data_records'
    )
    timestamp = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    location = models.PointField(
        srid=4326,
        geography=True,
        spatial_index=True,
        null=True,
        blank=True
    )
    data = models.JSONField()
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Field Data Record")
        verbose_name_plural = _("Field Data Records")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['processed']),
            models.Index(fields=['upload']),
        ]
    
    def __str__(self):
        return f"{self.device.device_id} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """Automatically calculate location from coordinates"""
        if self.latitude is not None and self.longitude is not None:
            self.location = Point(self.longitude, self.latitude)
        super().save(*args, **kwargs)
        ordering = ["-calibration_date"]
    
    def __str__(self):
        return f"{self.device.name} - {self.calibration_date.strftime('%Y-%m-%d')}"


class FieldDataUpload(models.Model):
    """Manages batch uploads of field device data"""
    UPLOAD_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]
    
    DATA_FORMAT_CHOICES = [
        ('csv', _('CSV')),
        ('json', _('JSON')),
        ('excel', _('Excel')),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    data_file = models.FileField(upload_to='field_data_uploads/')
    data_format = models.CharField(max_length=10, choices=DATA_FORMAT_CHOICES, default='csv')
    device_type = models.ForeignKey(DeviceType, on_delete=models.SET_NULL, null=True, blank=True, related_name='data_uploads')
    upload_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=UPLOAD_STATUS_CHOICES, default='pending')
    processed_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='field_data_uploads')
    
    class Meta:
        verbose_name = _("Field Data Upload")
        verbose_name_plural = _("Field Data Uploads")
        ordering = ["-upload_date"]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['device_type']),
            models.Index(fields=['upload_date']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.upload_date.strftime('%Y-%m-%d %H:%M')})"


class FieldDataUploadManual(models.Model):
    """Tracks manual data uploads from field technicians"""
    uploader = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='field_uploads'
    )
    weather_station = models.ForeignKey(
        WeatherStation, 
        on_delete=models.CASCADE, 
        related_name='field_uploads'
    )
    device = models.ForeignKey(
        FieldDevice, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='data_uploads'
    )
    
    upload_date = models.DateTimeField(auto_now_add=True)
    data_date = models.DateField(help_text="Date the data was collected")
    
    STATUS_CHOICES = [
        ('pending', _('Pending Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('processed', _('Processed')),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # File upload or direct data entry
    file = models.FileField(
        upload_to='field_uploads/',
        null=True,
        blank=True,
        help_text="CSV or Excel file with field data"
    )
    
    # For direct data entry
    error_log = models.TextField(null=True, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    precipitation = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    # Location where data was collected (may differ from station location)
    collection_location = models.PointField(
        srid=4326, 
        geography=True, 
        null=True, 
        blank=True
    )
    
    # Photo documentation
    photo = models.ImageField(
        upload_to='field_photos/',
        null=True,
        blank=True,
        help_text="Photo documentation of field conditions"
    )
    
    # Review information
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reviewed_uploads'
    )
    review_date = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = _("Field Data Upload")
        verbose_name_plural = _("Field Data Uploads")
        ordering = ["-upload_date"]
    
    def __str__(self):
        return f"Upload by {self.uploader.username if self.uploader else 'Unknown'} on {self.upload_date.strftime('%Y-%m-%d')}"
    
    def save(self, *args, **kwargs):
        # Create climate data record if approved
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if not is_new and self.status == 'approved' and not hasattr(self, '_processed'):
            self._create_climate_data()
            self.status = 'processed'
            self._processed = True
            self.save(update_fields=['status'])
    
    def _create_climate_data(self):
        """Create a ClimateData record from this upload"""
        if self.temperature is not None or self.humidity is not None or self.precipitation is not None:
            # Create timestamp from date
            timestamp = datetime.combine(self.data_date, datetime.min.time())
            
            # Determine data source
            if self.device:
                data_source = 'field_device'
            else:
                data_source = 'manual'
            
            ClimateData.objects.create(
                station=self.weather_station,
                timestamp=timestamp,
                temperature=self.temperature,
                humidity=self.humidity,
                precipitation=self.precipitation,
                data_quality='medium',  # Default quality for field data
                data_source=data_source,  # Set the data source
            )
