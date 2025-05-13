"""
Views for field data analysis and visualization
"""
import json
import logging
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max, Min, Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .field_models import FieldDevice, DeviceType, FieldDataRecord

logger = logging.getLogger(__name__)

@login_required
def field_data_analysis(request):
    """
    View for field data analysis page
    """
    # Get all devices for the filter dropdown
    devices = FieldDevice.objects.all().order_by('name')
    
    context = {
        'devices': devices,
    }
    
    return render(request, 'maps/field_data_analysis.html', context)

@api_view(['GET'])
def field_data_analysis_api(request):
    """
    API endpoint for field data analysis
    """
    # Get filter parameters
    device_id = request.GET.get('device_id', 'all')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse dates
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        # Add one day to end_date to include the whole day
        end_date = end_date + timedelta(days=1)
    except (ValueError, TypeError):
        # Default to last 7 days if dates are invalid
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)
    
    # Filter records by date range
    records = FieldDataRecord.objects.filter(
        timestamp__gte=start_date,
        timestamp__lt=end_date
    ).select_related('device')
    
    # Filter by device if specified
    if device_id != 'all':
        records = records.filter(device_id=device_id)
    
    # Get unique devices in the filtered records
    device_ids = records.values_list('device_id', flat=True).distinct()
    devices = FieldDevice.objects.filter(id__in=device_ids)
    
    # Generate a color for each device
    colors = [
        '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b',
        '#6f42c1', '#5a5c69', '#858796', '#2e59d9', '#17a673'
    ]
    
    # Prepare data for each device
    device_data = []
    for i, device in enumerate(devices):
        # Get records for this device
        device_records = records.filter(device=device)
        
        # Extract data for charts
        temperature_data = []
        humidity_data = []
        battery_data = []
        signal_data = []
        
        for record in device_records:
            timestamp = record.timestamp.isoformat()
            data = record.data
            
            if data.get('temperature') is not None:
                temperature_data.append({
                    'timestamp': timestamp,
                    'value': data.get('temperature')
                })
            
            if data.get('humidity') is not None:
                humidity_data.append({
                    'timestamp': timestamp,
                    'value': data.get('humidity')
                })
            
            if data.get('battery_voltage') is not None:
                battery_data.append({
                    'timestamp': timestamp,
                    'value': data.get('battery_voltage')
                })
            
            if data.get('signal_strength') is not None:
                signal_data.append({
                    'timestamp': timestamp,
                    'value': data.get('signal_strength')
                })
        
        # Get latest location
        latest_record = device_records.order_by('-timestamp').first()
        latitude = None
        longitude = None
        
        if latest_record:
            latitude = latest_record.latitude
            longitude = latest_record.longitude
        
        # Add device data
        device_data.append({
            'id': device.id,
            'name': device.name,
            'device_id': device.device_id,
            'device_type': device.device_type.name if device.device_type else 'Unknown',
            'color': colors[i % len(colors)],
            'latitude': latitude,
            'longitude': longitude,
            'temperature_data': temperature_data,
            'humidity_data': humidity_data,
            'battery_data': battery_data,
            'signal_data': signal_data
        })
    
    # Calculate summary metrics
    summary = {
        'total_readings': records.count(),
        'avg_temperature': None,
        'avg_humidity': None,
        'avg_battery': None
    }
    
    # Calculate averages from the data
    temperature_values = []
    humidity_values = []
    battery_values = []
    
    for record in records:
        data = record.data
        
        if data.get('temperature') is not None:
            temperature_values.append(data.get('temperature'))
        
        if data.get('humidity') is not None:
            humidity_values.append(data.get('humidity'))
        
        if data.get('battery_voltage') is not None:
            battery_values.append(data.get('battery_voltage'))
    
    if temperature_values:
        summary['avg_temperature'] = sum(temperature_values) / len(temperature_values)
    
    if humidity_values:
        summary['avg_humidity'] = sum(humidity_values) / len(humidity_values)
    
    if battery_values:
        summary['avg_battery'] = sum(battery_values) / len(battery_values)
    
    # Get recent data for the table
    recent_data = []
    for record in records.order_by('-timestamp')[:50]:
        data = record.data
        
        recent_data.append({
            'id': record.id,
            'device_name': record.device.name,
            'device_id': record.device.device_id,
            'timestamp': record.timestamp.isoformat(),
            'temperature': data.get('temperature'),
            'humidity': data.get('humidity'),
            'battery_voltage': data.get('battery_voltage'),
            'signal_strength': data.get('signal_strength')
        })
    
    # Prepare response
    response_data = {
        'devices': device_data,
        'summary': summary,
        'recent_data': recent_data
    }
    
    return JsonResponse(response_data)
