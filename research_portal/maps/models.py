# models.py
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class WeatherStation(models.Model):
    """Weather station or climate data collection point"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    location = models.PointField(srid=4326, geography=True)
    altitude = models.FloatField(help_text="Altitude in meters above sea level", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_installed = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Weather Station")
        verbose_name_plural = _("Weather Stations")
        ordering = ["name"]
    
    def __str__(self):
        return self.name
    
    @property
    def latitude(self):
        return self.location.y
    
    @property
    def longitude(self):
        return self.location.x


class ClimateData(models.Model):
    """Climate data measurements collected from weather stations"""
    QUALITY_CHOICES = [
        ('high', _('High')),
        ('medium', _('Medium')),
        ('low', _('Low')),
        ('uncertain', _('Uncertain')),
    ]
    
    station = models.ForeignKey(WeatherStation, on_delete=models.CASCADE, related_name='climate_data')
    timestamp = models.DateTimeField()
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
        ]
    
    def __str__(self):
        return f"{self.station.name} - {self.timestamp}"


class DataExport(models.Model):
    """Tracks data exports by users"""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('geojson', 'GeoJSON'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    station = models.ForeignKey(WeatherStation, on_delete=models.SET_NULL, null=True, blank=True)
    export_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    date_from = models.DateTimeField()
    date_to = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Data Export")
        verbose_name_plural = _("Data Exports")
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Export {self.export_format} - {self.created_at}"
