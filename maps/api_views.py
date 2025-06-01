import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import datetime
from rest_framework.views import APIView
from django.db.models import Max

# Set up logger
logger = logging.getLogger(__name__)

from .field_models import DeviceType, FieldDevice, DeviceCalibration, FieldDataUpload, FieldDataRecord
from .models import WeatherStation
from .serializers import (
    DeviceTypeSerializer,
    FieldDeviceSerializer,
    DeviceCalibrationSerializer,
    FieldDataUploadSerializer
)

class DeviceTypeViewSet(viewsets.ModelViewSet):
    """API endpoint for managing device types"""
    queryset = DeviceType.objects.all()
    serializer_class = DeviceTypeSerializer
    permission_classes = [AllowAny]  # Changed to AllowAny for testing
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

class FieldDeviceViewSet(viewsets.ModelViewSet):
    """API endpoint for managing field devices"""
    queryset = FieldDevice.objects.all()
    serializer_class = FieldDeviceSerializer
    permission_classes = [AllowAny]  # Changed to AllowAny for testing
    
    def perform_create(self, serializer):
        device = serializer.save(created_by=self.request.user)
        # Update last communication time for new devices
        device.last_communication = timezone.now()
        device.save()
    
    def perform_update(self, serializer):
        device = serializer.save(updated_by=self.request.user)
        # Update last communication time if location is updated
        if 'location' in serializer.validated_data:
            device.last_communication = timezone.now()
            device.save()
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update device status and optionally trigger maintenance"""
        device = self.get_object()
        status = request.data.get('status')
        
        if status not in dict(FieldDevice.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        device.status = status
        device.save()
        
        return Response(
            {'status': 'success', 'device_status': device.status},
            status=status.HTTP_200_OK
        )

class DeviceCalibrationViewSet(viewsets.ModelViewSet):
    """API endpoint for managing device calibrations"""
    queryset = DeviceCalibration.objects.all()
    serializer_class = DeviceCalibrationSerializer
    permission_classes = [AllowAny]  # Changed to AllowAny for testing
    
    def perform_create(self, serializer):
        calibration = serializer.save(created_by=self.request.user)
        # Update device's last calibration date
        device = calibration.device
        device.last_calibration = calibration.calibration_date
        device.save()
        return calibration
    
    @action(detail=True, methods=['post'])
    def generate_certificate(self, request, pk=None):
        """Generate calibration certificate"""
        calibration = self.get_object()
        
        # Generate certificate logic here
        certificate_number = f"CAL-{calibration.device.device_id}-{calibration.calibration_date.strftime('%Y%m%d')}"
        
        calibration.certificate_number = certificate_number
        calibration.save()
        
        return Response(
            {'certificate_number': certificate_number},
            status=status.HTTP_200_OK
        )


class FieldDataUploadViewSet(viewsets.ModelViewSet):
    """API endpoint for managing field data uploads"""
    queryset = FieldDataUpload.objects.all()
    serializer_class = FieldDataUploadSerializer
    permission_classes = [AllowAny]  # Changed to AllowAny for testing

    @action(detail=False, methods=['post'])
    def upload_data(self, request):
        """
        Endpoint for field devices to upload data
        
        Expected request body format:
        {
            "device_id": "string",
            "timestamp": "2023-05-13T15:36:31+03:00",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "data": {
                "temperature": 25.5,
                "humidity": 60,
                "battery_voltage": 3.8,
                "signal_strength": -75
            }
        }
        """
        try:
            device_id = request.data.get('device_id')
            timestamp = request.data.get('timestamp')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            data = request.data.get('data')

            if not all([device_id, timestamp, latitude, longitude, data]):
                return Response(
                    {'error': 'Missing required fields', 'received_data': request.data},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create device
            device = FieldDevice.objects.filter(device_id=device_id).first()
            if not device:
                # Create new device if it doesn't exist
                device_type = DeviceType.objects.first()  # Use default device type
                if not device_type:
                    return Response(
                        {
                            'error': 'No device type configured',
                            'device_id': device_id,
                            'available_device_types': list(DeviceType.objects.values_list('name', flat=True))
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                device = FieldDevice.objects.create(
                    device_id=device_id,
                    device_type=device_type,
                    name=f"Device {device_id}",
                    location=Point(longitude, latitude)
                )

            # Update device location and last communication
            device.location = Point(longitude, latitude)
            device.last_communication = timezone.now()
            device.save()

            # Create or get data upload
            upload, created = FieldDataUpload.objects.get_or_create(
                title=f"Data Upload for {device_id}",
                defaults={
                    'description': f"Automatic upload from device {device_id}",
                    'status': 'completed'
                }
            )

            # Create data record
            try:
                logger.info(f"Creating data record for device {device_id}")
                logger.info(f"Data: {data}")
                logger.info(f"Timestamp: {timestamp}")
                
                record = FieldDataRecord.objects.create(
                    upload=upload,
                    device=device,
                    timestamp=timezone.make_aware(datetime.fromisoformat(timestamp)),
                    latitude=latitude,
                    longitude=longitude,
                    data=data
                )
                
                logger.info(f"Created data record: {record.id}")
                
                return Response(
                    {
                        'status': 'success',
                        'message': 'Data uploaded successfully',
                        'device_status': device.status,
                        'record_id': record.id
                    },
                    status=status.HTTP_201_CREATED
                )
                return Response(
                    {
                        'status': 'success',
                        'message': 'Data uploaded successfully',
                        'device_status': device.status,
                        'record_id': record.id
                    },
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                return Response(
                    {
                        'error': f'Failed to create data record: {str(e)}',
                        'device_id': device_id,
                        'timestamp': timestamp
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(
                {
                    'status': 'success',
                    'message': 'Data uploaded successfully',
                    'device_status': device.status
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    queryset = FieldDataUpload.objects.all()
    serializer_class = FieldDataUploadSerializer
    permission_classes = [AllowAny]  # Changed to AllowAny for testing
    
    def perform_create(self, serializer):
        upload = serializer.save(created_by=self.request.user)
        # Start processing the uploaded file asynchronously
        self.process_upload(upload)
        return upload
    
    def process_upload(self, upload):
        """Process the uploaded file in the background"""
        # Update status to processing
        upload.status = 'processing'
        upload.save()
        
        try:
            # This would be implemented as a background task in production
            # For now, we'll just simulate processing
            import time
            time.sleep(1)  # Simulate processing time
            
            # Update status to completed
            upload.status = 'completed'
            upload.processed_count = 10  # Example count
            upload.save()
        except Exception as e:
            # Log the error and update status
            upload.status = 'failed'
            upload.error_log = str(e)
            upload.save()

class StationViewSet(viewsets.ViewSet):
    """API endpoint for retrieving all station data for the map"""
    permission_classes = [AllowAny]  # Allow public access to station locations
    
    def list(self, request):
        """Return a list of all stations with their location and status information"""
        # Get weather stations only - avoiding field device tables
        weather_stations = WeatherStation.objects.all().annotate(
            last_data_received=Max('climate_data__timestamp')
        )
        
        # Combine data from weather stations only
        stations = []
        
        # Process weather stations
        for station in weather_stations:
            is_online = station.is_active
            if station.last_data_received:
                time_diff = timezone.now() - station.last_data_received
                is_online = time_diff.total_seconds() < 86400  # 24 hours
            
            stations.append({
                'id': f"ws_{station.id}",
                'name': station.name,
                'device_type': 'weather_station',
                'latitude': station.latitude,
                'longitude': station.longitude,
                'location_name': station.location_description if hasattr(station, 'location_description') else '',
                'status': 'active' if station.is_active else 'inactive',
                'is_online': is_online,
                'last_data_received': station.last_data_received,
                'has_alerts': False,  # Default value since we're not checking alerts
                'battery_level': None,
                'signal_strength': None,
                'show_label': True
            })
        
        # Return only weather stations
        return Response(stations)
