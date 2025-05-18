"""
WebSocket consumers for real-time data updates
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .field_models import FieldDevice, FieldDataRecord, Alert, FieldDataUpload
from django.conf import settings
import asyncio

logger = logging.getLogger(__name__)

class FieldDataConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time field data updates
    """
    async def connect(self):
        """Handle WebSocket connection"""
        # Get the device ID from the URL route
        self.device_id = self.scope['url_route']['kwargs'].get('device_id', 'all')
        
        # Create a unique group name for this connection
        if self.device_id == 'all':
            self.group_name = 'field_data_all'
        else:
            self.group_name = f'field_data_{self.device_id}'
        
        # Join the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Send initial data
        if self.device_id == 'all':
            devices = await self.get_all_devices()
        else:
            devices = await self.get_device(self.device_id)
            
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'devices': devices
        }))
        
        logger.info(f"WebSocket connected: {self.group_name}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.group_name}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe':
                # Handle subscription to specific devices
                devices = data.get('devices', [])
                if devices:
                    for device_id in devices:
                        await self.channel_layer.group_add(
                            f'field_data_{device_id}',
                            self.channel_name
                        )
                    
                    await self.send(text_data=json.dumps({
                        'type': 'subscription_success',
                        'devices': devices
                    }))
            
            elif message_type == 'unsubscribe':
                # Handle unsubscription from specific devices
                devices = data.get('devices', [])
                if devices:
                    for device_id in devices:
                        await self.channel_layer.group_discard(
                            f'field_data_{device_id}',
                            self.channel_name
                        )
                    
                    await self.send(text_data=json.dumps({
                        'type': 'unsubscription_success',
                        'devices': devices
                    }))
            
            elif message_type == 'batch_data':
                # Handle batch data upload
                device_id = data.get('device_id')
                batch_data = data.get('data', [])
                
                if device_id and batch_data:
                    # Process batch data asynchronously
                    task_id = await self.process_batch_data(device_id, batch_data)
                    
                    await self.send(text_data=json.dumps({
                        'type': 'batch_processing',
                        'status': 'started',
                        'task_id': task_id
                    }))
            
            elif message_type == 'stacked_data':
                # Handle stacked data (time series data for multiple metrics)
                device_id = data.get('device_id')
                stacked_data = data.get('stacked_data', {})
                
                if device_id and stacked_data:
                    # Process stacked time series data
                    result = await self.process_stacked_data(device_id, stacked_data)
                    
                    await self.send(text_data=json.dumps({
                        'type': 'stacked_data_result',
                        'status': 'processed',
                        'records_added': result['count'],
                        'device_id': device_id
                    }))
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def field_data_update(self, event):
        """Handle field data updates from other parts of the application"""
        message_type = event.get('type')
        
        if message_type == 'data_update':
            # Send data update
            await self.send(text_data=json.dumps({
                'type': 'data_update',
                'device_id': event['device_id'],
                'data': event['data'],
                'timestamp': event['timestamp'],
            }))
        
        elif message_type == 'status_update':
            # Send status update
            await self.send(text_data=json.dumps({
                'type': 'status_update',
                'device_id': event['device_id'],
                'status': event['status'],
                'last_communication': event['last_communication'],
                'battery_level': event['battery_level'],
                'signal_strength': event['signal_strength'],
            }))
        
        elif message_type == 'alert':
            # Send alert notification
            await self.send(text_data=json.dumps({
                'type': 'alert',
                'alert': event['alert'],
            }))
        
        elif message_type == 'device_reset':
            # Send device reset notification
            await self.send(text_data=json.dumps({
                'type': 'device_reset',
                'device_id': event['device_id'],
                'status': 'active',
                'message': 'Device has been reset',
            }))
    
    async def device_status_update(self, event):
        """Handle device status updates from other parts of the application"""
        # Send the update to the WebSocket
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'device_id': event['device_id'],
            'status': event['status']
        }))
    
    async def alert_notification(self, event):
        """Handle alert notifications from other parts of the application"""
        # Send the alert to the WebSocket
        await self.send(text_data=json.dumps({
            'type': 'alert',
            'device_id': event['device_id'],
            'alert_type': event['alert_type'],
            'message': event['message'],
            'timestamp': event['timestamp'],
            'severity': event['severity']
        }))
    
    def _get_all_devices(self):
        """Synchronous helper to get all devices"""
        devices = FieldDevice.objects.all()
        return self._prepare_devices_data(devices)

    async def get_all_devices(self):
        """Get all devices with their latest data"""
        return await database_sync_to_async(self._get_all_devices)()

    def _get_device_alerts(self, device_id):
        """Synchronous helper to get device alerts"""
        alerts = Alert.objects.filter(
            device_id=device_id,
            timestamp__gte=timezone.now() - timezone.timedelta(days=7)
        ).order_by('-timestamp')[:10]

        return [
            {
                'id': alert.id,
                'type': alert.get_alert_type_display(),
                'message': alert.message,
                'severity': alert.get_severity_display(),
                'timestamp': alert.timestamp.isoformat(),
                'acknowledged': alert.acknowledged,
                'acknowledged_by': alert.acknowledged_by.username if alert.acknowledged_by else None,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            }
            for alert in alerts
        ]

    async def get_device_alerts(self, device_id):
        """Get recent alerts for a device"""
        return await database_sync_to_async(self._get_device_alerts)(device_id)

    def _get_device_status(self, device_id):
        """Synchronous helper to get device status"""
        device = FieldDevice.objects.get(id=device_id)
        latest_record = FieldDataRecord.objects.filter(
            device_id=device_id
        ).order_by('-timestamp').first()

        device_data = {
            'id': device.id,
            'name': device.name,
            'device_type': device.device_type.name,
            'status': device.status,
            'last_communication': device.last_communication.isoformat() if device.last_communication else None,
            'battery_level': device.battery_level,
            'signal_strength': device.signal_strength,
            'location': {
                'latitude': device.location.y if device.location else None,
                'longitude': device.location.x if device.location else None,
            },
            'latest_data': latest_record.data if latest_record else None,
            'alerts': self._get_device_alerts(device_id),
        }

        if latest_record:
            device_data['latest_data'] = {
                'timestamp': latest_record.timestamp.isoformat(),
                'data': latest_record.data
            }

        return device_data

    def _get_device(self, device_id):
        """Synchronous helper to get a specific device"""
        try:
            device = FieldDevice.objects.get(id=device_id)
            latest_record = FieldDataRecord.objects.filter(
                device=device
            ).order_by('-timestamp').first()
            
            device_data = {
                'id': device.id,
                'device_id': device.device_id,
                'name': device.name,
                'status': device.status,
                'battery_level': device.battery_level,
                'signal_strength': device.signal_strength,
                'last_communication': device.last_communication.isoformat() if device.last_communication else None,
            }
            
            if latest_record:
                device_data['latest_data'] = {
                    'timestamp': latest_record.timestamp.isoformat(),
                    'data': latest_record.data
                }
            
            return [device_data]
        except FieldDevice.DoesNotExist:
            return []

    async def get_device(self, device_id):
        """Get a specific device with its latest data"""
        return await database_sync_to_async(self._get_device)(device_id)

    @database_sync_to_async
    def process_batch_data(self, device_id, batch_data):
        """
        Process batch data efficiently
        
        Args:
            device_id: ID of the device sending the data
            batch_data: List of data records
            
        Returns:
            task_id: ID of the created processing task
        """
        from django.db import transaction
        
        try:
            # Get the device
            device = FieldDevice.objects.get(device_id=device_id)
            
            # Create an upload record
            upload = FieldDataUpload.objects.create(
                title=f"Batch upload for {device.name}",
                description=f"Automatic batch upload from device {device_id}",
                status='processing',
                data_format='json',
                device_type=device.device_type,
            )
            
            # Use bulk create for efficiency - prepare records
            with transaction.atomic():
                records_to_create = []
                error_count = 0
                
                # Use a buffer size to avoid creating too many objects at once
                buffer_size = getattr(settings, 'BATCH_PROCESSING_BUFFER_SIZE', 1000)
                
                for i, record_data in enumerate(batch_data):
                    try:
                        timestamp = timezone.datetime.fromisoformat(record_data.get('timestamp'))
                        lat = record_data.get('latitude')
                        lon = record_data.get('longitude')
                        data_payload = record_data.get('data', {})
                        
                        record = FieldDataRecord(
                            upload=upload,
                            device=device,
                            timestamp=timestamp,
                            latitude=lat,
                            longitude=lon,
                            data=data_payload
                        )
                        records_to_create.append(record)
                        
                        # If buffer is full or this is the last record, bulk create
                        if (i + 1) % buffer_size == 0 or i == len(batch_data) - 1:
                            FieldDataRecord.objects.bulk_create(records_to_create)
                            records_to_create = []
                    
                    except Exception as e:
                        logger.error(f"Error processing record: {str(e)}")
                        error_count += 1
                
                # Update device last communication time
                device.last_communication = timezone.now()
                device.save(update_fields=['last_communication', 'updated_at'])
                
                # Update upload record
                upload.processed_count = len(batch_data) - error_count
                upload.error_count = error_count
                upload.status = 'completed'
                upload.save()
            
            return str(upload.id)
        
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found: {device_id}")
            raise ValueError(f"Device not found: {device_id}")
        
        except Exception as e:
            logger.error(f"Error processing batch data: {str(e)}")
            raise
    
    @database_sync_to_async
    def process_stacked_data(self, device_id, stacked_data):
        """
        Process stacked time series data efficiently
        
        Args:
            device_id: ID of the device sending data
            stacked_data: Dictionary with timestamps as keys and measurements as values
            
        Returns:
            dict: Result with count of records processed
        """
        from django.db import transaction
        from datetime import datetime
        
        try:
            device = FieldDevice.objects.get(device_id=device_id)
            
            # Create an upload record
            upload = FieldDataUpload.objects.create(
                title=f"Stacked data upload for {device.name}",
                description=f"Time series data from device {device_id}",
                status='processing',
                data_format='json',
                device_type=device.device_type,
            )
            
            with transaction.atomic():
                records_to_create = []
                for timestamp_str, measurements in stacked_data.items():
                    try:
                        # Handle various timestamp formats
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        
                        # Get location from measurements or use last known location
                        latitude = measurements.get('latitude')
                        longitude = measurements.get('longitude')
                        
                        # Create data record
                        record = FieldDataRecord(
                            upload=upload,
                            device=device,
                            timestamp=timestamp,
                            latitude=latitude,
                            longitude=longitude,
                            data=measurements
                        )
                        records_to_create.append(record)
                        
                    except Exception as e:
                        logger.error(f"Error processing stacked data record: {str(e)}")
                
                # Bulk create all records at once for improved efficiency
                FieldDataRecord.objects.bulk_create(records_to_create)
                
                # Update the upload status
                upload.processed_count = len(records_to_create)
                upload.status = 'completed'
                upload.save()
                
                # Update device last communication time
                device.last_communication = timezone.now()
                device.save(update_fields=['last_communication', 'updated_at'])
            
            return {'count': len(records_to_create)}
        
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found for stacked data: {device_id}")
            raise ValueError(f"Device not found: {device_id}")
        
        except Exception as e:
            logger.error(f"Error processing stacked data: {str(e)}")
            raise

class BatchDataConsumer(AsyncWebsocketConsumer):
    """
    Specialized WebSocket consumer for high-volume batch data processing
    from field stations with optimized memory usage and performance
    """
    async def connect(self):
        """Handle WebSocket connection"""
        self.device_id = self.scope['url_route']['kwargs'].get('device_id')
        self.group_name = f'batch_data_{self.device_id}'
        
        # Join the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        logger.info(f"Batch data WebSocket connected: {self.group_name}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"Batch data WebSocket disconnected: {self.group_name}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket with optimized processing"""
        try:
            # Use a streaming JSON parser for large payloads
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'compressed_batch':
                # Handle compressed batch data (e.g., gzipped)
                import base64
                import gzip
                import io
                
                compressed_data = data.get('compressed_data')
                if not compressed_data:
                    raise ValueError("Missing compressed_data field")
                
                # Decode and decompress
                decoded = base64.b64decode(compressed_data)
                with gzip.open(io.BytesIO(decoded), 'rt') as f:
                    decompressed_data = json.load(f)
                
                # Process the decompressed data
                batch_data = decompressed_data.get('data', [])
                result = await self.process_optimized_batch(self.device_id, batch_data)
                
                await self.send(text_data=json.dumps({
                    'type': 'batch_result',
                    'status': 'success',
                    'records_processed': result['processed'],
                    'errors': result['errors']
                }))
                
            elif message_type == 'chunked_batch_start':
                # Initialize a new chunked batch upload session
                self.current_batch_id = f"{self.device_id}_{timezone.now().timestamp()}"
                self.chunks_received = 0
                self.total_chunks = data.get('total_chunks', 0)
                self.chunk_data = []
                
                await self.send(text_data=json.dumps({
                    'type': 'chunked_batch_ack',
                    'batch_id': self.current_batch_id,
                    'status': 'ready'
                }))
                
            elif message_type == 'chunked_batch_data':
                # Process a chunk of data in a multi-chunk upload
                chunk_index = data.get('chunk_index')
                chunk = data.get('chunk', [])
                batch_id = data.get('batch_id')
                
                if batch_id != getattr(self, 'current_batch_id', None):
                    raise ValueError("Invalid batch ID")
                
                # Append this chunk's data
                self.chunk_data.extend(chunk)
                self.chunks_received += 1
                
                await self.send(text_data=json.dumps({
                    'type': 'chunk_received',
                    'chunk_index': chunk_index,
                    'status': 'received'
                }))
                
                # If all chunks received, process the complete batch
                if self.chunks_received == self.total_chunks:
                    result = await self.process_optimized_batch(self.device_id, self.chunk_data)
                    
                    await self.send(text_data=json.dumps({
                        'type': 'chunked_batch_complete',
                        'status': 'success',
                        'records_processed': result['processed'],
                        'errors': result['errors'],
                        'batch_id': self.current_batch_id
                    }))
                    
                    # Clear batch data
                    self.chunk_data = []
                    self.current_batch_id = None
            
            elif message_type == 'stacked_timeseries':
                # Handle efficient time series data import
                station_id = self.device_id
                start_time = data.get('start_time')
                end_time = data.get('end_time')
                interval = data.get('interval')  # in seconds
                metrics = data.get('metrics', {})
                
                result = await self.process_stacked_timeseries(
                    station_id, start_time, end_time, interval, metrics
                )
                
                await self.send(text_data=json.dumps({
                    'type': 'stacked_timeseries_result',
                    'status': 'success',
                    'records_created': result['created']
                }))
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received in batch processor")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in batch processor: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    @database_sync_to_async
    def process_optimized_batch(self, device_id, batch_data):
        """
        Process batch data with maximum efficiency using database features
        
        Args:
            device_id: ID of the device/station sending data
            batch_data: List of data records
            
        Returns:
            dict: Processing results
        """
        from django.db import connection, transaction
        import psycopg2.extras
        
        try:
            device = FieldDevice.objects.get(device_id=device_id)
            
            # Create upload record
            upload = FieldDataUpload.objects.create(
                title=f"Optimized batch upload for {device.name}",
                description=f"High-efficiency upload from station {device_id}",
                status='processing',
                data_format='json',
                device_type=device.device_type,
            )
            
            error_count = 0
            processed_count = 0
            
            with transaction.atomic():
                # If PostgreSQL with COPY support is available, use it for maximum efficiency
                if connection.vendor == 'postgresql':
                    # Prepare data for bulk insert
                    records = []
                    for record in batch_data:
                        try:
                            timestamp = timezone.datetime.fromisoformat(
                                record.get('timestamp').replace('Z', '+00:00')
                            )
                            latitude = record.get('latitude')
                            longitude = record.get('longitude')
                            data_payload = json.dumps(record.get('data', {}))
                            
                            records.append((
                                upload.id,
                                device.id,
                                timestamp,
                                latitude, 
                                longitude,
                                data_payload
                            ))
                            processed_count += 1
                        except Exception as e:
                            logger.error(f"Error preparing record for bulk insert: {str(e)}")
                            error_count += 1
                    
                    if records:
                        with connection.cursor() as cursor:
                            # Get the proper table name
                            table_name = FieldDataRecord._meta.db_table
                            
                            # Use the PostgreSQL COPY command for extremely fast bulk insert
                            cursor.execute("SELECT 1")  # Dummy command to get a psycopg2 cursor
                            psycopg2_cursor = cursor.cursor
                            
                            columns = [
                                'upload_id', 'device_id', 'timestamp', 
                                'latitude', 'longitude', 'data'
                            ]
                            
                            psycopg2.extras.execute_values(
                                psycopg2_cursor,
                                f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES %s",
                                records,
                                template=None,
                                page_size=1000
                            )
                else:
                    # Fall back to Django's bulk_create for other databases
                    records_to_create = []
                    for record in batch_data:
                        try:
                            timestamp = timezone.datetime.fromisoformat(
                                record.get('timestamp').replace('Z', '+00:00')
                            )
                            latitude = record.get('latitude')
                            longitude = record.get('longitude')
                            data_payload = record.get('data', {})
                            
                            records_to_create.append(FieldDataRecord(
                                upload=upload,
                                device=device,
                                timestamp=timestamp,
                                latitude=latitude,
                                longitude=longitude,
                                data=data_payload
                            ))
                            processed_count += 1
                        except Exception as e:
                            logger.error(f"Error creating record: {str(e)}")
                            error_count += 1
                    
                    # Use bulk_create with batch_size for memory efficiency
                    if records_to_create:
                        FieldDataRecord.objects.bulk_create(
                            records_to_create,
                            batch_size=1000
                        )
                
                # Update device last communication time
                device.last_communication = timezone.now()
                device.save(update_fields=['last_communication', 'updated_at'])
                
                # Update upload record
                upload.processed_count = processed_count
                upload.error_count = error_count
                upload.status = 'completed'
                upload.save()
            
            return {'processed': processed_count, 'errors': error_count}
            
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found for batch processing: {device_id}")
            raise ValueError(f"Device not found: {device_id}")
        except Exception as e:
            logger.error(f"Error in optimized batch processing: {str(e)}")
            raise
    
    @database_sync_to_async
    def process_stacked_timeseries(self, station_id, start_time, end_time, interval, metrics):
        """
        Process stacked time series data efficiently by generating data points
        at regular intervals
        
        Args:
            station_id: ID of the station
            start_time: ISO format start time
            end_time: ISO format end time
            interval: Time interval in seconds
            metrics: Dict of metrics with their values over time
            
        Returns:
            dict: Processing results
        """
        from datetime import datetime, timedelta
        
        try:
            device = FieldDevice.objects.get(device_id=station_id)
            
            # Parse times
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Create upload record
            upload = FieldDataUpload.objects.create(
                title=f"Stacked timeseries for {device.name}",
                description=f"Regular interval data from {start} to {end}",
                status='processing',
                data_format='timeseries',
                device_type=device.device_type,
            )
            
            # Get fixed location from device if not in metrics
            default_lat = device.default_latitude
            default_lon = device.default_longitude
            
            records_to_create = []
            current_time = start
            
            # Generate data points at specified intervals
            while current_time <= end:
                data_point = {}
                
                # Build data point from metrics
                for metric_name, metric_values in metrics.items():
                    # Interpolate value for this timestamp if not exact
                    timestamp_str = current_time.isoformat()
                    
                    if timestamp_str in metric_values:
                        # Exact match
                        data_point[metric_name] = metric_values[timestamp_str]
                    else:
                        # Find closest values and interpolate
                        # For simplicity, use the last known value
                        # A more sophisticated approach would use proper interpolation
                        earlier_values = [
                            (ts, val) for ts, val in metric_values.items()
                            if datetime.fromisoformat(ts.replace('Z', '+00:00')) <= current_time
                        ]
                        
                        if earlier_values:
                            # Get the most recent earlier value
                            data_point[metric_name] = earlier_values[-1][1]
                
                # Create record if we have any data
                if data_point:
                    record = FieldDataRecord(
                        upload=upload,
                        device=device,
                        timestamp=current_time,
                        latitude=data_point.get('latitude', default_lat),
                        longitude=data_point.get('longitude', default_lon),
                        data=data_point
                    )
                    records_to_create.append(record)
                
                # Move to next interval
                current_time += timedelta(seconds=interval)
            
            # Bulk create all records
            with transaction.atomic():
                FieldDataRecord.objects.bulk_create(records_to_create, batch_size=1000)
                
                # Update upload record
                upload.processed_count = len(records_to_create)
                upload.status = 'completed'
                upload.save()
            
            return {'created': len(records_to_create)}
            
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found for timeseries: {station_id}")
            raise ValueError(f"Device not found: {station_id}")
        except Exception as e:
            logger.error(f"Error processing stacked timeseries: {str(e)}")
            raise
