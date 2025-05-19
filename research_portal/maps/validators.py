"""
Validators for field device data
"""
import re
import json
import logging
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class FieldDeviceDataValidator:
    """Validator for field device data uploads"""
    
    def __init__(self, data):
        self.data = data
        self.errors = []
        self.warnings = []
        self.cleaned_data = {}
    
    def validate(self):
        """Validate the field device data"""
        # Check for required fields
        self._validate_required_fields()
        
        # If required fields are missing, don't continue validation
        if self.errors:
            return False
        
        # Validate each field
        self._validate_device_id()
        self._validate_timestamp()
        self._validate_coordinates()
        self._validate_sensor_data()
        
        # If no errors, prepare cleaned data
        if not self.errors:
            self._prepare_cleaned_data()
            return True
        
        return False
    
    def _validate_required_fields(self):
        """Validate that all required fields are present"""
        required_fields = ['device_id', 'timestamp', 'latitude', 'longitude', 'data']
        for field in required_fields:
            if field not in self.data:
                self.errors.append(f"Missing required field: {field}")
    
    def _validate_device_id(self):
        """Validate device ID format"""
        device_id = self.data.get('device_id')
        if not re.match(r'^[A-Za-z0-9_-]{3,50}$', device_id):
            self.errors.append("Device ID must be 3-50 alphanumeric characters, underscores, or hyphens")
    
    def _validate_timestamp(self):
        """Validate timestamp format and value"""
        timestamp = self.data.get('timestamp')
        try:
            dt = datetime.fromisoformat(timestamp)
            
            # Check if timestamp is in the future
            now = timezone.now()
            if dt > now + timezone.timedelta(minutes=5):
                self.errors.append("Timestamp cannot be more than 5 minutes in the future")
            
            # Check if timestamp is too old
            if dt < now - timezone.timedelta(days=7):
                self.warnings.append("Timestamp is more than 7 days old")
                
        except (ValueError, TypeError):
            self.errors.append("Invalid timestamp format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SS+HH:MM)")
    
    def _validate_coordinates(self):
        """Validate latitude and longitude"""
        try:
            lat = float(self.data.get('latitude'))
            lon = float(self.data.get('longitude'))
            
            if not (-90 <= lat <= 90):
                self.errors.append("Latitude must be between -90 and 90")
            
            if not (-180 <= lon <= 180):
                self.errors.append("Longitude must be between -180 and 180")
                
        except (ValueError, TypeError):
            self.errors.append("Latitude and longitude must be valid numbers")
    
    def _validate_sensor_data(self):
        """Validate sensor data"""
        sensor_data = self.data.get('data')
        
        if not isinstance(sensor_data, dict):
            self.errors.append("Sensor data must be a JSON object")
            return
        
        # Validate temperature if present
        if 'temperature' in sensor_data:
            try:
                temp = float(sensor_data['temperature'])
                if not (-100 <= temp <= 100):
                    self.warnings.append("Temperature value is outside normal range (-100 to 100°C)")
            except (ValueError, TypeError):
                self.errors.append("Temperature must be a valid number")
        
        # Validate humidity if present
        if 'humidity' in sensor_data:
            try:
                humidity = float(sensor_data['humidity'])
                if not (0 <= humidity <= 100):
                    self.errors.append("Humidity must be between 0 and 100%")
            except (ValueError, TypeError):
                self.errors.append("Humidity must be a valid number")
        
        # Validate battery_voltage if present
        if 'battery_voltage' in sensor_data:
            try:
                voltage = float(sensor_data['battery_voltage'])
                if not (0 <= voltage <= 12):
                    self.warnings.append("Battery voltage is outside expected range (0 to 12V)")
            except (ValueError, TypeError):
                self.errors.append("Battery voltage must be a valid number")
        
        # Validate signal_strength if present
        if 'signal_strength' in sensor_data:
            try:
                signal = float(sensor_data['signal_strength'])
                if not (-120 <= signal <= 0):
                    self.errors.append("Signal strength must be between -120 and 0 dBm")
            except (ValueError, TypeError):
                self.errors.append("Signal strength must be a valid number")
    
    def _prepare_cleaned_data(self):
        """Prepare cleaned data after validation"""
        self.cleaned_data = {
            'device_id': self.data.get('device_id'),
            'timestamp': datetime.fromisoformat(self.data.get('timestamp')),
            'latitude': float(self.data.get('latitude')),
            'longitude': float(self.data.get('longitude')),
            'data': self.data.get('data')
        }
    
    def get_errors(self):
        """Get validation errors"""
        return self.errors
    
    def get_warnings(self):
        """Get validation warnings"""
        return self.warnings
    
    def get_cleaned_data(self):
        """Get cleaned data after validation"""
        return self.cleaned_data


def validate_field_device_data(data):
    """
    Validate field device data
    
    Args:
        data: The data to validate
        
    Returns:
        tuple: (is_valid, cleaned_data, errors, warnings)
    """
    validator = FieldDeviceDataValidator(data)
    is_valid = validator.validate()
    
    return (
        is_valid,
        validator.get_cleaned_data(),
        validator.get_errors(),
        validator.get_warnings()
    )
