from django.db import models
from django.contrib.auth.models import User

class DataSource(models.Model):
    """Model to track different data sources for attribution"""
    name = models.CharField(max_length=100)
    url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    attribution_text = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name

class LocationMarker(models.Model):
    """Model for map markers with location information"""
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    elevation = models.FloatField(blank=True, null=True)
    land_use_classification = models.CharField(max_length=50, blank=True, null=True)
    ecological_zone = models.CharField(max_length=50, blank=True, null=True)
    conservation_status = models.CharField(max_length=50, blank=True, null=True)
    population_density = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude})"
    
    class Meta:
        unique_together = ('latitude', 'longitude')

class EnvironmentalData(models.Model):
    """Model for environmental data readings associated with markers"""
    location = models.ForeignKey(LocationMarker, on_delete=models.CASCADE, related_name='environmental_data')
    timestamp = models.DateTimeField()
    temperature = models.FloatField(blank=True, null=True)
    humidity = models.FloatField(blank=True, null=True)
    precipitation = models.FloatField(blank=True, null=True)
    air_quality_index = models.FloatField(blank=True, null=True)
    wind_speed = models.FloatField(blank=True, null=True)
    wind_direction = models.CharField(max_length=10, blank=True, null=True)
    barometric_pressure = models.FloatField(blank=True, null=True)
    uv_index = models.FloatField(blank=True, null=True)
    visibility = models.FloatField(blank=True, null=True)
    cloud_cover = models.FloatField(blank=True, null=True)
    soil_moisture = models.FloatField(blank=True, null=True)
    water_level = models.FloatField(blank=True, null=True)
    vegetation_index = models.FloatField(blank=True, null=True)
    data_quality = models.FloatField(default=1.0, help_text="Score between 0-1 indicating data quality")
    data_source = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Data for {self.location.name} at {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']
        get_latest_by = 'timestamp'

class UserMarkerAnnotation(models.Model):
    """Model for user annotations on markers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    marker = models.ForeignKey(LocationMarker, on_delete=models.CASCADE, related_name='annotations')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Annotation by {self.user.username} on {self.marker.name}"

class AlertThreshold(models.Model):
    """Model for user-defined alert thresholds on environmental metrics"""
    METRIC_CHOICES = [
        ('temperature', 'Temperature'),
        ('humidity', 'Humidity'),
        ('precipitation', 'Precipitation'),
        ('air_quality_index', 'Air Quality Index'),
        ('wind_speed', 'Wind Speed'),
        ('barometric_pressure', 'Barometric Pressure'),
        ('uv_index', 'UV Index'),
        ('soil_moisture', 'Soil Moisture'),
        ('water_level', 'Water Level'),
    ]
    
    CONDITION_CHOICES = [
        ('gt', 'Greater Than'),
        ('lt', 'Less Than'),
        ('eq', 'Equal To'),
        ('gte', 'Greater Than or Equal To'),
        ('lte', 'Less Than or Equal To'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    marker = models.ForeignKey(LocationMarker, on_delete=models.CASCADE, related_name='alert_thresholds')
    metric = models.CharField(max_length=30, choices=METRIC_CHOICES)
    condition = models.CharField(max_length=3, choices=CONDITION_CHOICES)
    value = models.FloatField()
    active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Alert for {self.marker.name} when {self.metric} is {self.condition} {self.value}"