import requests
import json
import logging
from django.conf import settings
from .models import LocationMarker, EnvironmentalData, DataSource

logger = logging.getLogger(__name__)

def fetch_environmental_data(api_key=None):
    """
    Utility function to fetch environmental data from external API
    and update the database. This could be run as a scheduled task.
    """
    # Example implementation for OpenWeatherMap API
    # You should adapt this to your specific data provider
    
    if not api_key:
        api_key = getattr(settings, 'WEATHER_API_KEY', None)
        if not api_key:
            logger.error("No API key provided for weather data")
            return False
    
    # Get all location markers
    markers = LocationMarker.objects.all()
    
    # Find or create the data source
    data_source, created = DataSource.objects.get_or_create(
        name="OpenWeatherMap",
        defaults={
            'url': 'https://openweathermap.org/',
            'attribution_text': 'Data provided by OpenWeatherMap',
            'description': 'Real-time weather and environmental data'
        }
    )
    
    success_count = 0
    error_count = 0
    
    for marker in markers:
        try:
            # Example: fetch data from OpenWeatherMap API
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={marker.latitude}&lon={marker.longitude}&appid={api_key}&units=metric"
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            data = response.json()
            
            # Create environmental data record
            env_data = EnvironmentalData(
                location=marker,
                timestamp=datetime.datetime.now(),
                temperature=data.get('main', {}).get('temp'),
                humidity=data.get('main', {}).get('humidity'),
                wind_speed=data.get('wind', {}).get('speed'),
                wind_direction=data.get('wind', {}).get('deg'),
                barometric_pressure=data.get('main', {}).get('pressure'),
                visibility=data.get('visibility'),
                cloud_cover=data.get('clouds', {}).get('all'),
                data_source=data_source
            )
            
            # Check for precipitation if available
            if 'rain' in data:
                env_data.precipitation = data['rain'].get('1h', 0)
            
            env_data.save()
            success_count += 1
            
        except Exception as e:
            logger.error(f"Error fetching data for marker {marker.id}: {str(e)}")
            error_count += 1
    
    logger.info(f"Data fetch complete. Success: {success_count}, Errors: {error_count}")
    return success_count > 0

def check_alert_thresholds():
    """
    Utility function to check all active alert thresholds
    and notify users if thresholds are exceeded.
    This could be run as a scheduled task.
    """
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from .models import AlertThreshold
    
    # Get all active alert thresholds
    thresholds = AlertThreshold.objects.filter(active=True)
    
    for threshold in thresholds:
        # Get the latest environmental data for this marker
        try:
            latest_data = threshold.marker.environmental_data.latest()
            
            # Get the value to check
            metric_value = getattr(latest_data, threshold.metric, None)
            
            if metric_value is not None:
                # Check if threshold is exceeded
                threshold_exceeded = False
                
                if threshold.condition == 'gt' and metric_value > threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'lt' and metric_value < threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'eq' and metric_value == threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'gte' and metric_value >= threshold.value:
                    threshold_exceeded = True
                elif threshold.condition == 'lte' and metric_value <= threshold.value:
                    threshold_exceeded = True
                
                if threshold_exceeded:
                    # Notify the user (here we'll just email)
                    user_email = threshold.user.email
                    condition_display = threshold.get_condition_display()
                    metric_display = threshold.get_metric_display()
                    
                    if user_email:
                        message = f"""
                        Alert Notification
                        
                        Your alert threshold for {threshold.marker.name} has been triggered.
                        
                        {metric_display} is now {metric_value}, which is {condition_display} your threshold of {threshold.value}.
                        
                        Timestamp: {latest_data.timestamp}
                        
                        You can view more details on the map at {settings.BASE_URL}/markers/{threshold.marker.id}/
                        """
                        
                        send_mail(
                            f'Environmental Alert: {threshold.marker.name}',
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [user_email],
                            fail_silently=True,
                        )
                        
                        logger.info(f"Alert sent to {threshold.user.username} for {threshold.marker.name}")
        
        except Exception as e:
            logger.error(f"Error checking threshold {threshold.id}: {str(e)}")
    
    logger.info("Alert threshold check complete")