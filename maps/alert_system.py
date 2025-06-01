"""
Alert system for field devices
"""
import logging
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .field_models import Alert, AlertType, AlertSeverity

logger = logging.getLogger(__name__)

# Alert model is now defined in alert_models.py


def check_for_alerts(device, sensor_data):
    """
    Check for alert conditions based on device data
    
    Args:
        device: The FieldDevice object
        sensor_data: Dictionary of sensor readings
        
    Returns:
        list: List of alert dictionaries
    """
    alerts = []
    
    # Check battery level
    if 'battery_voltage' in sensor_data:
        battery_voltage = sensor_data['battery_voltage']
        if battery_voltage < 3.3:
            alerts.append({
                'type': AlertType.BATTERY_LOW,
                'message': f"Battery level critical: {battery_voltage}V",
                'severity': AlertSeverity.CRITICAL
            })
        elif battery_voltage < 3.6:
            alerts.append({
                'type': AlertType.BATTERY_LOW,
                'message': f"Battery level low: {battery_voltage}V",
                'severity': AlertSeverity.WARNING
            })
    
    # Check signal strength
    if 'signal_strength' in sensor_data:
        signal_strength = sensor_data['signal_strength']
        if signal_strength < -90:
            alerts.append({
                'type': AlertType.SIGNAL_WEAK,
                'message': f"Signal strength critical: {signal_strength} dBm",
                'severity': AlertSeverity.WARNING
            })
    
    # Check temperature
    if 'temperature' in sensor_data:
        temperature = sensor_data['temperature']
        
        # Get device type to determine thresholds
        device_type = device.device_type
        
        # Default thresholds
        temp_high = 45.0
        temp_low = -10.0
        
        # Use device type specific thresholds if available
        if device_type and hasattr(device_type, 'temperature_high_threshold'):
            temp_high = device_type.temperature_high_threshold
        
        if device_type and hasattr(device_type, 'temperature_low_threshold'):
            temp_low = device_type.temperature_low_threshold
        
        if temperature > temp_high:
            alerts.append({
                'type': AlertType.TEMPERATURE_HIGH,
                'message': f"Temperature too high: {temperature}°C",
                'severity': AlertSeverity.WARNING
            })
        elif temperature < temp_low:
            alerts.append({
                'type': AlertType.TEMPERATURE_LOW,
                'message': f"Temperature too low: {temperature}°C",
                'severity': AlertSeverity.WARNING
            })
    
    # Check humidity
    if 'humidity' in sensor_data:
        humidity = sensor_data['humidity']
        if humidity > 95:
            alerts.append({
                'type': AlertType.HUMIDITY_HIGH,
                'message': f"Humidity too high: {humidity}%",
                'severity': AlertSeverity.WARNING
            })
        elif humidity < 5:
            alerts.append({
                'type': AlertType.HUMIDITY_LOW,
                'message': f"Humidity too low: {humidity}%",
                'severity': AlertSeverity.WARNING
            })
    
    # Create alert records in the database
    for alert in alerts:
        Alert.objects.create(
            device=device,
            alert_type=alert['type'],
            message=alert['message'],
            severity=alert['severity']
        )
        
        # Log the alert
        log_level = logging.WARNING
        if alert['severity'] == AlertSeverity.CRITICAL:
            log_level = logging.ERROR
        elif alert['severity'] == AlertSeverity.INFO:
            log_level = logging.INFO
            
        logger.log(log_level, f"Alert for {device.name} ({device.device_id}): {alert['message']}")
    
    return alerts


def send_alert_notifications(alert):
    """
    Send notifications for an alert
    
    Args:
        alert: The Alert object
    """
    # Only send notifications for critical alerts
    if alert.severity != AlertSeverity.CRITICAL:
        return
    
    # Get users to notify (e.g., admins)
    admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
    
    if not admin_emails:
        logger.warning("No admin emails found for alert notification")
        return
    
    # Send email notification
    try:
        subject = f"CRITICAL ALERT: {alert.device.name} - {alert.get_alert_type_display()}"
        message = f"""
Critical alert detected for field device:

Device: {alert.device.name} ({alert.device.device_id})
Alert Type: {alert.get_alert_type_display()}
Message: {alert.message}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Please check the device as soon as possible.

--
University Research Portal
"""
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        send_mail(subject, message, from_email, admin_emails, fail_silently=False)
        
        logger.info(f"Alert notification sent to {len(admin_emails)} admins")
    except Exception as e:
        logger.error(f"Failed to send alert notification: {str(e)}")


def check_device_connection_status():
    """
    Check for devices that haven't communicated recently
    This should be run as a scheduled task
    """
    from .field_models import FieldDevice
    
    # Get threshold time (e.g., 24 hours ago)
    threshold_time = timezone.now() - timezone.timedelta(hours=24)
    
    # Find devices that haven't communicated since the threshold
    disconnected_devices = FieldDevice.objects.filter(
        last_communication__lt=threshold_time,
        status='active'  # Only check active devices
    )
    
    for device in disconnected_devices:
        # Create connection lost alert
        alert = Alert.objects.create(
            device=device,
            alert_type=AlertType.CONNECTION_LOST,
            message=f"Device has not communicated since {device.last_communication.strftime('%Y-%m-%d %H:%M')}",
            severity=AlertSeverity.WARNING
        )
        
        # Update device status
        device.status = 'lost'
        device.save(update_fields=['status'])
        
        logger.warning(f"Connection lost alert created for {device.name} ({device.device_id})")
    
    return len(disconnected_devices)
