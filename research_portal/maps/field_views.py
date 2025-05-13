import os
import csv
import json
import random
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .field_models import DeviceType, FieldDevice, DeviceCalibration, FieldDataUpload


@login_required
def field_data_upload(request):
    """View for uploading field data files"""
    if request.method == 'POST':
        # Handle file upload
        try:
            title = request.POST.get('title')
            description = request.POST.get('description')
            device_type_id = request.POST.get('device_type')
            data_format = request.POST.get('data_format')
            data_file = request.FILES.get('data_file')
            
            # Validate required fields
            if not title or not data_file or not data_format:
                messages.error(request, 'Please provide a title, data format, and upload a file.')
                return redirect('maps:field_data_upload')
            
            # Get device type if provided
            device_type = None
            if device_type_id:
                device_type = get_object_or_404(DeviceType, id=device_type_id)
            
            # Create upload record
            upload = FieldDataUpload.objects.create(
                title=title,
                description=description,
                device_type=device_type,
                data_format=data_format,
                data_file=data_file,
                created_by=request.user
            )
            
            # Process the file (in a real app, this would be done asynchronously)
            process_field_data_upload(upload)
            
            messages.success(request, f'File "{title}" uploaded successfully and is being processed.')
            return redirect('maps:field_data_upload_detail', upload_id=upload.id)
            
        except Exception as e:
            messages.error(request, f'Error uploading file: {str(e)}')
            return redirect('maps:field_data_upload')
    
    # GET request - show upload form
    device_types = DeviceType.objects.all()
    uploads = FieldDataUpload.objects.filter(created_by=request.user).order_by('-upload_date')[:10]
    
    return render(request, 'maps/field_data_upload.html', {
        'device_types': device_types,
        'uploads': uploads
    })


@login_required
def field_data_upload_detail(request, upload_id):
    """View for showing details of a field data upload"""
    upload = get_object_or_404(FieldDataUpload, id=upload_id)
    
    # Check if user has permission to view this upload
    if upload.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this upload.')
        return redirect('maps:field_data_upload')
    
    # Get data preview if available
    data_preview = None
    if upload.status == 'completed' and upload.processed_count > 0:
        data_preview = get_data_preview(upload)
    
    return render(request, 'maps/field_data_upload_detail.html', {
        'upload': upload,
        'data_preview': data_preview
    })


@login_required
def field_data_visualize(request, upload_id):
    """View for visualizing field data"""
    upload = get_object_or_404(FieldDataUpload, id=upload_id)
    
    # Check if user has permission to view this upload
    if upload.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this upload.')
        return redirect('maps:field_data_upload')
    
    # Check if upload is completed
    if upload.status != 'completed':
        messages.error(request, 'This upload is not yet processed. Please wait until processing is complete.')
        return redirect('maps:field_data_upload_detail', upload_id=upload.id)
    
    # Get field data for visualization
    field_data = get_field_data_for_visualization(upload)
    devices = FieldDevice.objects.filter(device_type=upload.device_type) if upload.device_type else FieldDevice.objects.all()
    
    return render(request, 'maps/field_data_visualize.html', {
        'upload': upload,
        'field_data_json': json.dumps(field_data),
        'devices': devices
    })


@login_required
def field_data_retry(request, upload_id):
    """Retry processing a failed upload"""
    upload = get_object_or_404(FieldDataUpload, id=upload_id)
    
    # Check if user has permission
    if upload.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to retry this upload.')
        return redirect('maps:field_data_upload')
    
    # Check if upload is in a failed state
    if upload.status != 'failed':
        messages.error(request, 'Only failed uploads can be retried.')
        return redirect('maps:field_data_upload_detail', upload_id=upload.id)
    
    # Reset upload status and error logs
    upload.status = 'pending'
    upload.error_count = 0
    upload.error_log = None
    upload.save()
    
    # Process the upload again
    process_field_data_upload(upload)
    
    messages.success(request, 'Upload processing has been restarted.')
    return redirect('maps:field_data_upload_detail', upload_id=upload.id)


# Helper functions for field data processing

def process_field_data_upload(upload):
    """Process a field data upload file"""
    try:
        # Update status to processing
        upload.status = 'processing'
        upload.save()
        
        # Process based on file format
        if upload.data_format == 'csv':
            process_csv_upload(upload)
        elif upload.data_format == 'json':
            process_json_upload(upload)
        elif upload.data_format == 'excel':
            process_excel_upload(upload)
        else:
            raise ValueError(f'Unsupported data format: {upload.data_format}')
        
        # Update status to completed
        upload.status = 'completed'
        upload.save()
        
    except Exception as e:
        # Log the error and update status
        upload.status = 'failed'
        upload.error_log = str(e)
        upload.save()


def process_csv_upload(upload):
    """Process a CSV file upload"""
    # In a real implementation, this would parse the CSV and create/update records
    # For demonstration, we'll just simulate processing
    
    try:
        # Read the CSV file
        file_path = upload.data_file.path
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Update processed count
        upload.processed_count = len(rows)
        upload.save()
        
    except Exception as e:
        upload.error_count += 1
        upload.error_log = f"Error processing CSV: {str(e)}"
        raise


def process_json_upload(upload):
    """Process a JSON file upload"""
    # Simulate JSON processing
    try:
        # Read the JSON file
        file_path = upload.data_file.path
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Update processed count
        if isinstance(data, list):
            upload.processed_count = len(data)
        elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            upload.processed_count = len(data['data'])
        else:
            upload.processed_count = 1
            
        upload.save()
        
    except Exception as e:
        upload.error_count += 1
        upload.error_log = f"Error processing JSON: {str(e)}"
        raise


def process_excel_upload(upload):
    """Process an Excel file upload"""
    # Simulate Excel processing
    try:
        # Read the Excel file
        file_path = upload.data_file.path
        df = pd.read_excel(file_path)
        
        # Update processed count
        upload.processed_count = len(df)
        upload.save()
        
    except Exception as e:
        upload.error_count += 1
        upload.error_log = f"Error processing Excel: {str(e)}"
        raise


def get_data_preview(upload):
    """Get a preview of the uploaded data"""
    try:
        file_path = upload.data_file.path
        
        if upload.data_format == 'csv':
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = []
                for i, row in enumerate(reader):
                    if i < 10:  # Limit to 10 rows for preview
                        rows.append(row)
                    else:
                        break
            return {'headers': headers, 'rows': rows}
            
        elif upload.data_format == 'json':
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list) and len(data) > 0:
                # Assume list of objects with same structure
                headers = list(data[0].keys())
                rows = [[item.get(h, '') for h in headers] for item in data[:10]]
                return {'headers': headers, 'rows': rows}
            elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                # Assume {data: [...]} structure
                if len(data['data']) > 0:
                    headers = list(data['data'][0].keys())
                    rows = [[item.get(h, '') for h in headers] for item in data['data'][:10]]
                    return {'headers': headers, 'rows': rows}
            
            # Fallback for other JSON structures
            return {'headers': ['Key', 'Value'], 'rows': [[k, str(v)] for k, v in list(data.items())[:10]]}
            
        elif upload.data_format == 'excel':
            df = pd.read_excel(file_path, nrows=10)
            headers = df.columns.tolist()
            rows = df.values.tolist()
            return {'headers': headers, 'rows': rows}
            
    except Exception as e:
        # Return error information
        return {'headers': ['Error'], 'rows': [[str(e)]]}
    
    return None


def get_field_data_for_visualization(upload):
    """Get field data in GeoJSON format for visualization"""
    # In a real implementation, this would fetch actual data from the database
    # For demonstration, we'll create sample data based on the upload
    
    # Create a GeoJSON structure
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    # Get devices of the specified type (or all if no type specified)
    devices = FieldDevice.objects.filter(device_type=upload.device_type) if upload.device_type else FieldDevice.objects.all()
    
    # For each device, create sample data points
    for device in devices:
        if device.location:  # Only include devices with location data
            # Create a feature for this device
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [device.location.x, device.location.y]  # [longitude, latitude]
                },
                "properties": {
                    "id": device.id,
                    "name": device.name,
                    "device_id": device.device_id,
                    "device_type": device.device_type.name if device.device_type else "Unknown",
                    "status": device.status,
                    "battery_level": device.battery_level or 50,  # Default to 50% if None
                    "signal_strength": device.signal_strength or -70,  # Default to -70 dBm if None
                    "last_communication": device.last_communication.isoformat() if device.last_communication else None,
                    "timestamp": timezone.now().isoformat(),
                    "temperature": round(20 + 5 * (0.5 - random.random()), 1),  # Random temperature between 15-25°C
                    "humidity": round(50 + 20 * (0.5 - random.random()), 1),  # Random humidity between 30-70%
                    "precipitation": round(5 * random.random(), 1),  # Random precipitation between 0-5mm
                    "data_quality": "high"
                }
            }
            
            geojson["features"].append(feature)
    
    return geojson
