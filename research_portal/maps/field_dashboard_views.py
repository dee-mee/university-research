"""
Views for the field data dashboard
"""
import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from .field_models import FieldDevice, DeviceType, FieldDataRecord, Alert
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

@login_required
def field_data_dashboard(request):
    """
    View for the field data dashboard
    """
    # Get all device types for the filter dropdown
    device_types = DeviceType.objects.all().order_by('name')
    
    # Get all devices with their latest readings
    devices = FieldDevice.objects.all().select_related('device_type')
    
    # Get recent alerts
    recent_alerts = Alert.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).select_related('device').order_by('-timestamp')[:10]
    
    context = {
        'device_types': device_types,
        'devices': devices,
        'recent_alerts': recent_alerts,
    }
    
    return render(request, 'maps/field_data_dashboard.html', context)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_data_api(request, device_id):
    """
    API endpoint to get historical data for a specific device
    """
    try:
        # Get the device
        device = get_object_or_404(FieldDevice, id=device_id)
        
        # Get the data records
        records = FieldDataRecord.objects.filter(
            device=device
        ).order_by('-timestamp')[:100]  # Limit to last 100 records
        
        # Format the data
        data = []
        for record in records:
            data.append({
                'timestamp': record.timestamp.isoformat(),
                'data': record.data,
                'latitude': record.latitude,
                'longitude': record.longitude,
                'battery_level': record.data.get('battery_level'),
                'signal_strength': record.data.get('signal_strength'),
            })
            
        return Response({
            'success': True,
            'data': data,
            'device': {
                'id': device.id,
                'name': device.name,
                'device_type': device.device_type.name,
                'status': device.status,
                'last_communication': device.last_communication.isoformat() if device.last_communication else None,
                'battery_level': device.battery_level,
                'signal_strength': device.signal_strength,
            }
        })
    except Exception as e:
        logger.error(f"Error in device_data_api: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
        
        return Response(data)
    
    except FieldDevice.DoesNotExist:
        return Response({'error': 'Device not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting device data: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_alerts_api(request, device_id):
    """
    API endpoint to get alerts for a specific device
    """
    try:
        # Get the device
        device = get_object_or_404(FieldDevice, id=device_id)
        
        # Get recent alerts
        alerts = Alert.objects.filter(
            device=device,
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).order_by('-timestamp')[:10]
        
        # Format the alerts
        alert_data = []
        for alert in alerts:
            alert_data.append({
                'id': alert.id,
                'type': alert.get_alert_type_display(),
                'message': alert.message,
                'severity': alert.get_severity_display(),
                'timestamp': alert.timestamp.isoformat(),
                'acknowledged': alert.acknowledged,
                'acknowledged_by': alert.acknowledged_by.username if alert.acknowledged_by else None,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            })
            
        return Response({
            'success': True,
            'alerts': alert_data,
            'device': {
                'id': device.id,
                'name': device.name,
                'alert_count': alerts.count(),
                'critical_alerts': alerts.filter(severity='critical').count(),
            }
        })
    except Exception as e:
        logger.error(f"Error in device_alerts_api: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
        
        return Response(data)
    
    except FieldDevice.DoesNotExist:
        return Response({'error': 'Device not found'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_reset_api(request, device_id):
    """
    API endpoint to reset a device
    """
    try:
        device = get_object_or_404(FieldDevice, id=device_id)
        
        # Reset device status
        device.status = 'active'
        device.last_communication = timezone.now()
        device.battery_level = None
        device.signal_strength = None
        device.save()
        
        # Create reset alert
        Alert.objects.create(
            device=device,
            alert_type='device_reset',
            message=f'Device {device.name} has been reset',
            severity='info'
        )
        
        return Response({
            'success': True,
            'message': f'Device {device.name} has been reset'
        })
        return Response({'error': 'Device not found'}, status=404)
    except Exception as e:
        logger.error(f"Error resetting device: {str(e)}")
        return Response({'error': str(e)}, status=500)
