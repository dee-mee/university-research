import logging
import json
import os
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .field_models import DeviceType, FieldDevice, FieldDataUpload, FieldDataRecord
from .models import WeatherStation
from .validators import validate_field_device_data
from .alert_system import check_for_alerts

logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([AllowAny])  # Change to IsAuthenticated for production
def device_data_upload(request):
    """
    Simple endpoint for field devices to upload data
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        # Parse JSON data from request body
        try:
            if isinstance(request.data, dict):
                data = request.data
            else:
                data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        
        # Validate the data
        is_valid, cleaned_data, errors, warnings = validate_field_device_data(data)
        
        if not is_valid:
            return JsonResponse({
                'error': 'Validation failed',
                'errors': errors,
                'received_data': data
            }, status=400)
        
        # Extract validated fields
        device_id = cleaned_data['device_id']
        timestamp = cleaned_data['timestamp']
        latitude = cleaned_data['latitude']
        longitude = cleaned_data['longitude']
        sensor_data = cleaned_data['data']
        
        logger.info(f"Received validated data from device {device_id}")
        
        # Log any warnings
        if warnings:
            logger.warning(f"Warnings for device {device_id}: {warnings}")
        
        # Get or create device
        device = FieldDevice.objects.filter(device_id=device_id).first()
        if not device:
            # Create new device if it doesn't exist
            device_type = DeviceType.objects.first()  # Use default device type
            if not device_type:
                return JsonResponse({
                    'error': 'No device type configured',
                    'device_id': device_id
                }, status=500)
            
            device = FieldDevice.objects.create(
                device_id=device_id,
                device_type=device_type,
                name=f"Device {device_id}",
                location=Point(longitude, latitude)
            )
            logger.info(f"Created new device: {device_id}")
        
        # Update device location and last communication
        device.location = Point(longitude, latitude)
        device.last_communication = timezone.now()
        device.save()
        
        # Skip creating FieldDataUpload and directly create a FieldDataRecord
        try:
            # Save the data to a file for reference
            filename = f'field_uploads/{device_id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
            os.makedirs(os.path.dirname(f"{settings.MEDIA_ROOT}/{filename}"), exist_ok=True)
            with open(f"{settings.MEDIA_ROOT}/{filename}", 'wb') as f:
                f.write(json.dumps(data).encode('utf-8'))
                
            # Create a simple response record
            logger.info(f"Device data received from {device_id}: {sensor_data}")
            
            # Send real-time update via WebSockets
            channel_layer = get_channel_layer()
            
            # Send to device-specific group
            async_to_sync(channel_layer.group_send)(
                f'field_data_{device.id}',
                {
                    'type': 'field_data_update',
                    'device_id': device.id,
                    'data': {
                        'timestamp': timestamp.isoformat(),
                        'device_id': device_id,
                        'latitude': latitude,
                        'longitude': longitude,
                        'sensor_data': sensor_data
                    }
                }
            )
            
            # Send to 'all' group
            async_to_sync(channel_layer.group_send)(
                'field_data_all',
                {
                    'type': 'field_data_update',
                    'device_id': device.id,
                    'data': {
                        'timestamp': timestamp.isoformat(),
                        'device_id': device_id,
                        'latitude': latitude,
                        'longitude': longitude,
                        'sensor_data': sensor_data
                    }
                }
            )
            
            # Check for alerts
            alerts = check_for_alerts(device, sensor_data)
            if alerts:
                for alert in alerts:
                    # Send alert via WebSockets
                    async_to_sync(channel_layer.group_send)(
                        f'field_data_{device.id}',
                        {
                            'type': 'alert_notification',
                            'device_id': device.id,
                            'alert_type': alert['type'],
                            'message': alert['message'],
                            'timestamp': timezone.now().isoformat(),
                            'severity': alert['severity']
                        }
                    )
                    
                    # Also send to 'all' group
                    async_to_sync(channel_layer.group_send)(
                        'field_data_all',
                        {
                            'type': 'alert_notification',
                            'device_id': device.id,
                            'alert_type': alert['type'],
                            'message': alert['message'],
                            'timestamp': timezone.now().isoformat(),
                            'severity': alert['severity']
                        }
                    )
            
            response_data = {
                'status': 'success',
                'message': 'Data uploaded successfully',
                'device_status': device.status,
                'device_id': device_id,
                'timestamp': timestamp.isoformat()
            }
            
            # Include any warnings in the response
            if warnings:
                response_data['warnings'] = warnings
                
            return JsonResponse(response_data, status=201)
            
        except Exception as e:
            logger.error(f"Error creating data record: {str(e)}")
            return JsonResponse({
                'error': f'Failed to create data record: {str(e)}',
                'device_id': device_id,
                'timestamp': timestamp
            }, status=500)
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
