"""
Batch operations for field devices
"""
import json
import logging
import csv
import os
from datetime import datetime, timedelta
from io import StringIO
import pandas as pd
from django.http import JsonResponse, HttpResponse, FileResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .field_models import FieldDevice, DeviceType, DeviceCalibration, FieldDataRecord

logger = logging.getLogger(__name__)

@login_required
def batch_operations_view(request):
    """
    View for batch operations page
    """
    # Get all devices and device types for the filter dropdowns
    devices = FieldDevice.objects.all().select_related('device_type').order_by('name')
    device_types = DeviceType.objects.all().order_by('name')
    
    context = {
        'devices': devices,
        'device_types': device_types,
    }
    
    return render(request, 'maps/batch_operations.html', context)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_operations_api(request):
    """
    API endpoint for batch operations
    """
    try:
        data = json.loads(request.body)
        operation = data.get('operation')
        device_ids = data.get('devices', [])
        params = data.get('params', {})
        
        # Validate input
        if not operation:
            return JsonResponse({'error': 'Operation is required'}, status=400)
        
        if not device_ids:
            return JsonResponse({'error': 'At least one device must be selected'}, status=400)
        
        # Get the devices
        devices = FieldDevice.objects.filter(id__in=device_ids)
        if not devices:
            return JsonResponse({'error': 'No valid devices found'}, status=400)
        
        # Execute the operation
        if operation == 'update_status':
            results = update_device_status(devices, params, request.user)
        elif operation == 'schedule_calibration':
            results = schedule_device_calibration(devices, params, request.user)
        elif operation == 'update_firmware':
            results = update_device_firmware(devices, params, request.user)
        elif operation == 'reset_device':
            results = reset_devices(devices, params, request.user)
        elif operation == 'export_data':
            return export_device_data(devices, params, request.user)
        else:
            return JsonResponse({'error': f'Unknown operation: {operation}'}, status=400)
        
        # Return the results
        return JsonResponse({
            'success': True,
            'message': f'Operation {operation} completed successfully',
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Error in batch operation: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

def update_device_status(devices, params, user):
    """
    Update the status of multiple devices
    """
    results = []
    new_status = params.get('new_status')
    notes = params.get('notes', '')
    
    if not new_status:
        raise ValueError("New status is required")
    
    with transaction.atomic():
        for device in devices:
            try:
                old_status = device.status
                device.status = new_status
                device.save(update_fields=['status'])
                
                # Log the status change
                logger.info(f"Device {device.name} ({device.device_id}) status changed from {old_status} to {new_status} by {user.username}")
                
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': True,
                    'message': f"Status updated from {old_status} to {new_status}"
                })
            except Exception as e:
                logger.error(f"Error updating status for device {device.name}: {str(e)}")
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': False,
                    'message': f"Error: {str(e)}"
                })
    
    return results

def schedule_device_calibration(devices, params, user):
    """
    Schedule calibration for multiple devices
    """
    results = []
    calibration_date_str = params.get('calibration_date')
    notes = params.get('notes', '')
    
    if not calibration_date_str:
        raise ValueError("Calibration date is required")
    
    try:
        calibration_date = datetime.strptime(calibration_date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Invalid calibration date format")
    
    with transaction.atomic():
        for device in devices:
            try:
                # Create calibration record
                calibration = DeviceCalibration.objects.create(
                    device=device,
                    calibration_date=timezone.now(),
                    next_calibration_date=calibration_date.date(),
                    performed_by=user,
                    notes=notes
                )
                
                # Update device status to indicate calibration
                device.status = 'calibration'
                device.save(update_fields=['status'])
                
                logger.info(f"Calibration scheduled for device {device.name} ({device.device_id}) on {calibration_date_str} by {user.username}")
                
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': True,
                    'message': f"Calibration scheduled for {calibration_date_str}"
                })
            except Exception as e:
                logger.error(f"Error scheduling calibration for device {device.name}: {str(e)}")
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': False,
                    'message': f"Error: {str(e)}"
                })
    
    return results

def update_device_firmware(devices, params, user):
    """
    Update firmware for multiple devices
    """
    results = []
    firmware_version = params.get('firmware_version')
    notes = params.get('notes', '')
    
    if not firmware_version:
        raise ValueError("Firmware version is required")
    
    with transaction.atomic():
        for device in devices:
            try:
                old_firmware = device.firmware_version
                device.firmware_version = firmware_version
                device.last_firmware_update = timezone.now()
                device.save(update_fields=['firmware_version', 'last_firmware_update'])
                
                logger.info(f"Firmware updated for device {device.name} ({device.device_id}) from {old_firmware} to {firmware_version} by {user.username}")
                
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': True,
                    'message': f"Firmware updated from {old_firmware or 'unknown'} to {firmware_version}"
                })
            except Exception as e:
                logger.error(f"Error updating firmware for device {device.name}: {str(e)}")
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': False,
                    'message': f"Error: {str(e)}"
                })
    
    return results

def reset_devices(devices, params, user):
    """
    Reset multiple devices
    """
    results = []
    notes = params.get('notes', '')
    
    with transaction.atomic():
        for device in devices:
            try:
                # Perform reset operations
                device.last_reset = timezone.now()
                device.save(update_fields=['last_reset'])
                
                logger.info(f"Device {device.name} ({device.device_id}) reset by {user.username}")
                
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': True,
                    'message': "Device reset successfully"
                })
            except Exception as e:
                logger.error(f"Error resetting device {device.name}: {str(e)}")
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'success': False,
                    'message': f"Error: {str(e)}"
                })
    
    return results

def export_device_data(devices, params, user):
    """
    Export data for multiple devices
    """
    start_date_str = params.get('start_date')
    end_date_str = params.get('end_date')
    export_format = params.get('format', 'csv')
    
    # Set default dates if not provided
    if not start_date_str:
        start_date = timezone.now() - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Invalid start date format")
    
    if not end_date_str:
        end_date = timezone.now()
    else:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # Add one day to include the end date
            end_date = end_date + timedelta(days=1)
        except ValueError:
            raise ValueError("Invalid end date format")
    
    # Get the data records
    records = FieldDataRecord.objects.filter(
        device__in=devices,
        timestamp__gte=start_date,
        timestamp__lt=end_date
    ).order_by('device', 'timestamp')
    
    # Prepare the data for export
    export_data = []
    for record in records:
        data_dict = {
            'device_id': record.device.device_id,
            'device_name': record.device.name,
            'timestamp': record.timestamp.isoformat(),
            'latitude': record.latitude,
            'longitude': record.longitude,
        }
        
        # Add sensor data fields
        for key, value in record.data.items():
            data_dict[key] = value
        
        export_data.append(data_dict)
    
    # Generate the export file
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"device_data_export_{timestamp}"
    
    if export_format == 'csv':
        return export_as_csv(export_data, filename)
    elif export_format == 'json':
        return export_as_json(export_data, filename)
    elif export_format == 'excel':
        return export_as_excel(export_data, filename)
    else:
        raise ValueError(f"Unsupported export format: {export_format}")

def export_as_csv(data, filename):
    """
    Export data as CSV
    """
    if not data:
        return JsonResponse({
            'error': 'No data to export'
        }, status=400)
    
    # Get all possible column names
    columns = set()
    for item in data:
        columns.update(item.keys())
    
    columns = sorted(list(columns))
    
    # Create CSV file
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    
    for item in data:
        writer.writerow(item)
    
    # Create the response
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    
    return response

def export_as_json(data, filename):
    """
    Export data as JSON
    """
    if not data:
        return JsonResponse({
            'error': 'No data to export'
        }, status=400)
    
    # Create the response
    response = JsonResponse(data, safe=False)
    response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
    
    return response

def export_as_excel(data, filename):
    """
    Export data as Excel
    """
    if not data:
        return JsonResponse({
            'error': 'No data to export'
        }, status=400)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file
    excel_file = f"{settings.MEDIA_ROOT}/exports/{filename}.xlsx"
    os.makedirs(os.path.dirname(excel_file), exist_ok=True)
    
    # Write to Excel
    df.to_excel(excel_file, index=False)
    
    # Create the response
    response = FileResponse(open(excel_file, 'rb'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    
    return response
