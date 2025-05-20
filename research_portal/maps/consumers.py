"""
WebSocket consumers for real-time data updates
"""
import json
import logging
import time
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

        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Cancel heartbeat task if running
        if hasattr(self, 'heartbeat_task'):
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.group_name}")
    
    async def send_heartbeat(self):
        """Send periodic heartbeats to keep connection alive"""
        heartbeat_interval = getattr(settings, 'WEBSOCKET_HEARTBEAT_INTERVAL', 30)  # seconds
        try:
            while True:
                await asyncio.sleep(heartbeat_interval)
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat',
                    'timestamp': timezone.now().isoformat()
                }))
                logger.debug(f"Heartbeat sent: {self.group_name}")
        except asyncio.CancelledError:
            # Task was cancelled during disconnect
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat: {str(e)}")

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'heartbeat_ack':
                # Client acknowledges heartbeat - nothing to do
                return
            
            elif message_type == 'reconnect_info':
                # Store reconnection information from client
                self.last_received_seq = data.get('last_received_seq')
                self.client_id = data.get('client_id')
                
                # Send missed messages if any
                if hasattr(self, 'last_received_seq') and self.last_received_seq is not None:
                    missed_messages = await self.get_missed_messages(self.last_received_seq)
                    if missed_messages:
                        await self.send(text_data=json.dumps({
                            'type': 'missed_messages',
                            'messages': missed_messages
                        }))
                
                # Confirm reconnection
                await self.send(text_data=json.dumps({
                    'type': 'reconnect_success',
                    'client_id': self.client_id,
                    'server_time': timezone.now().isoformat()
                }))
            
            elif message_type == 'subscribe':
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
            
            elif message_type == 'get_config':
                # Handle device configuration requests
                device_id = data.get('device_id')
                if device_id:
                    config = await self.get_device_config(device_id)
                    await self.send(text_data=json.dumps({
                        'type': 'device_config',
                        'device_id': device_id,
                        'config': config
                    }))
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    @database_sync_to_async
    def get_device_config(self, device_id):
        """
        Get device configuration settings
        
        Args:
            device_id: ID of the device
            
        Returns:
            dict: Device configuration settings
        """
        try:
            device = FieldDevice.objects.get(device_id=device_id)
            
            # Get device configuration - extend with your actual configuration model
            config = {
                'sampling_rate': device.sampling_rate if hasattr(device, 'sampling_rate') else 60,
                'reporting_interval': device.reporting_interval if hasattr(device, 'reporting_interval') else 300,
                'power_save_mode': device.power_save_mode if hasattr(device, 'power_save_mode') else 'normal',
                'alert_thresholds': device.alert_thresholds if hasattr(device, 'alert_thresholds') else {},
                'sensors_enabled': device.sensors_enabled if hasattr(device, 'sensors_enabled') else [],
                'firmware_version': device.firmware_version if hasattr(device, 'firmware_version') else '1.0',
                'update_available': False  # Placeholder, implement actual update check logic
            }
            
            return config
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found for config: {device_id}")
            return {}
    
    @database_sync_to_async
    def get_missed_messages(self, last_sequence):
        """
        Retrieve messages that the client might have missed during disconnection
        
        Args:
            last_sequence: Last message sequence number received by client
            
        Returns:
            list: Missed messages
        """
        # This is a placeholder implementation
        # In a real implementation, you would store messages with sequence numbers
        # and retrieve undelivered ones from a cache or database
        return []

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
        
        # Initialize metrics collection
        self.metrics = {
            'messages_received': 0,
            'bytes_received': 0,
            'processing_time': 0,
            'connection_start': time.time()
        }
        
        # Accept the connection
        await self.accept()
        logger.info(f"Batch data WebSocket connected: {self.group_name}")
        
        # Send connection info including protocol versions supported
        await self.send(text_data=json.dumps({
            'type': 'connection_info',
            'supports_binary': True,
            'supports_compression': True,
            'max_payload_size': getattr(settings, 'WEBSOCKET_MAX_PAYLOAD_SIZE', 10 * 1024 * 1024),  # 10MB default
            'protocol_versions': ['1.0', '1.1', '2.0'],  # Include protocol versions supported
            'server_time': timezone.now().isoformat()
        }))
        
        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Cancel heartbeat task if running
        if hasattr(self, 'heartbeat_task'):
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
                
        # Log connection metrics
        connection_duration = time.time() - self.metrics['connection_start']
        logger.info(
            f"BatchDataConsumer metrics: connection_duration={connection_duration:.2f}s, "
            f"messages={self.metrics['messages_received']}, "
            f"bytes={self.metrics['bytes_received']}, "
            f"processing_time={self.metrics['processing_time']:.2f}s"
        )
        
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"Batch data WebSocket disconnected: {self.group_name}")
    
    async def send_heartbeat(self):
        """Send periodic heartbeats to keep connection alive"""
        heartbeat_interval = getattr(settings, 'WEBSOCKET_HEARTBEAT_INTERVAL', 30)  # seconds
        try:
            while True:
                await asyncio.sleep(heartbeat_interval)
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat',
                    'timestamp': timezone.now().isoformat(),
                    'device_id': self.device_id
                }))
                logger.debug(f"Heartbeat sent: {self.group_name}")
        except asyncio.CancelledError:
            # Task was cancelled during disconnect
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat: {str(e)}")
    
    async def receive(self, text_data=None, bytes_data=None):
        """Handle messages from WebSocket with optimized processing"""
        start_time = time.time()
        
        try:
            # Track metrics
            self.metrics['messages_received'] += 1
            
            if bytes_data:
                # Handle binary data
                self.metrics['bytes_received'] += len(bytes_data)
                await self.process_binary_data(bytes_data)
            elif text_data:
                # Track text data size
                self.metrics['bytes_received'] += len(text_data)
                
                # Use a streaming JSON parser for large payloads
                data = json.loads(text_data)
                message_type = data.get('type')
                
                if message_type == 'protocol_selection':
                    # Handle client protocol version selection
                    protocol_version = data.get('version')
                    self.protocol_version = protocol_version
                    logger.info(f"Client selected protocol version: {protocol_version}")
                    await self.send(text_data=json.dumps({
                        'type': 'protocol_accepted',
                        'version': protocol_version
                    }))
                
                elif message_type == 'compressed_batch':
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
                
                elif message_type == 'heartbeat_ack':
                    # Client acknowledges heartbeat - nothing to do
                    pass
                    
                elif message_type == 'config_request':
                    # Handle device requesting updated configuration
                    config = await self.get_device_config()
                    await self.send(text_data=json.dumps({
                        'type': 'config_update',
                        'config': config
                    }))
                    
                else:
                    logger.warning(f"Unknown message type: {message_type}")
        
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
        finally:
            # Update processing time metric
            processing_time = time.time() - start_time
            self.metrics['processing_time'] += processing_time
    
    async def process_binary_data(self, binary_data):
        """
        Process binary format data (more efficient than JSON for large datasets)
        
        Binary format: 
        - First 4 bytes: Message type identifier
        - Next 4 bytes: Device ID length
        - Next N bytes: Device ID string
        - Remaining bytes: Data payload (format depends on message type)
        
        Args:
            binary_data: Raw binary data from the WebSocket
        """
        import struct
        import msgpack
        
        try:
            # Extract header information
            header_format = "!I"  # 4-byte unsigned integer for message type
            header_size = struct.calcsize(header_format)
            
            if len(binary_data) < header_size:
                raise ValueError("Binary message too short")
                
            message_type, = struct.unpack(header_format, binary_data[:header_size])
            
            # Skip header
            data = binary_data[header_size:]
            
            # Process based on message type code
            if message_type == 1:  # Batch data in MessagePack format
                # Use MessagePack for efficient binary serialization
                unpacked_data = msgpack.unpackb(data, raw=False)
                
                # Process the unpacked data
                result = await self.process_optimized_batch(
                    self.device_id, 
                    unpacked_data.get('records', [])
                )
                
                # Send response as binary MessagePack
                response = {
                    'status': 'success',
                    'records_processed': result['processed'],
                    'errors': result['errors']
                }
                
                await self.send(bytes_data=struct.pack(header_format, 101) + msgpack.packb(response))
                
            elif message_type == 2:  # Time series data
                # Unpack time series data
                unpacked_data = msgpack.unpackb(data, raw=False)
                
                result = await self.process_stacked_timeseries(
                    self.device_id,
                    unpacked_data.get('start_time'),
                    unpacked_data.get('end_time'),
                    unpacked_data.get('interval'),
                    unpacked_data.get('metrics', {})
                )
                
                # Send response as binary MessagePack
                response = {
                    'status': 'success',
                    'records_created': result['created']
                }
                
                await self.send(bytes_data=struct.pack(header_format, 102) + msgpack.packb(response))
                
            else:
                logger.warning(f"Unknown binary message type: {message_type}")
                # Send error response
                response = {
                    'status': 'error',
                    'message': f'Unknown binary message type: {message_type}'
                }
                await self.send(bytes_data=struct.pack(header_format, 255) + msgpack.packb(response))
                
        except Exception as e:
            logger.error(f"Error processing binary data: {str(e)}")
            # Send error response
            response = {
                'status': 'error',
                'message': str(e)
            }
            
            try:
                import msgpack
                await self.send(bytes_data=struct.pack("!I", 255) + msgpack.packb(response))
            except:
                # Fallback to text if binary response fails
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Binary processing error: {str(e)}'
                }))
    
    @database_sync_to_async
    def get_device_config(self):
        """Get device configuration settings"""
        try:
            device = FieldDevice.objects.get(device_id=self.device_id)
            
            # Get device configuration
            config = {
                'sampling_rate': device.sampling_rate if hasattr(device, 'sampling_rate') else 60,
                'reporting_interval': device.reporting_interval if hasattr(device, 'reporting_interval') else 300,
                'power_save_mode': device.power_save_mode if hasattr(device, 'power_save_mode') else 'normal',
                'alert_thresholds': device.alert_thresholds if hasattr(device, 'alert_thresholds') else {},
                'sensors_enabled': device.sensors_enabled if hasattr(device, 'sensors_enabled') else [],
                'firmware_version': device.firmware_version if hasattr(device, 'firmware_version') else '1.0'
            }
            
            return config
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found: {self.device_id}")
            return {}
    
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
                            latitude = float(record.get('latitude', 0))
                            longitude = float(record.get('longitude', 0))
                            
                            # Convert data to JSON string
                            data_json = json.dumps(record.get('data', {}))
                            
                            records.append((
                                upload.id,
                                device.id,
                                timestamp,
                                latitude, 
                                longitude,
                                data_json
                            ))
                            
                            processed_count += 1
                        except Exception as e:
                            logger.error(f"Error preparing record: {str(e)}")
                            error_count += 1
                    
                    # Use PostgreSQL's COPY FROM for maximum performance
                    with connection.cursor() as cursor:
                        table_name = FieldDataRecord._meta.db_table
                        columns = ['upload_id', 'device_id', 'timestamp', 
                                   'latitude', 'longitude', 'data']
                        
                        # Create a StringIO to store the data
                        from io import StringIO
                        data_file = StringIO()
                        
                        # Write the records to the StringIO
                        for record in records:
                            # Format the values for COPY
                            values = [
                                str(record[0]),  # upload_id
                                str(record[1]),  # device_id
                                record[2].isoformat(),  # timestamp
                                str(record[3]),  # latitude
                                str(record[4]),  # longitude
                                record[5]  # data (JSON string)
                            ]
                            data_file.write('\t'.join(values) + '\n')
                        
                        # Reset the StringIO position
                        data_file.seek(0)
                        
                        # Execute the COPY FROM
                        cursor.copy_from(
                            file=data_file,
                            table=table_name,
                            columns=columns
                        )
                else:
                    # Fallback to bulk_create for non-PostgreSQL databases
                    records_to_create = []
                    for record in batch_data:
                        try:
                            timestamp = timezone.datetime.fromisoformat(
                                record.get('timestamp').replace('Z', '+00:00')
                            )
                            
                            record_obj = FieldDataRecord(
                                upload=upload,
                                device=device,
                                timestamp=timestamp,
                                latitude=record.get('latitude'),
                                longitude=record.get('longitude'),
                                data=record.get('data', {})
                            )
                            records_to_create.append(record_obj)
                            processed_count += 1
                        except Exception as e:
                            logger.error(f"Error creating record: {str(e)}")
                            error_count += 1
                    
                    # Use bulk create for better performance
                    FieldDataRecord.objects.bulk_create(records_to_create)
                
                # Update device last communication time
                device.last_communication = timezone.now()
                device.save(update_fields=['last_communication'])
                
                # Update upload record
                upload.processed_count = processed_count
                upload.error_count = error_count
                upload.status = 'completed'
                upload.save()
                
                # Send update to monitoring channel
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                
                async_to_sync = import_module('asgiref.sync').async_to_sync
                async_to_sync(channel_layer.group_send)(
                    'data_monitoring',
                    {
                        'type': 'batch_upload_completed',
                        'device_id': device_id,
                        'upload_id': upload.id,
                        'processed_count': processed_count,
                        'error_count': error_count,
                        'timestamp': timezone.now().isoformat()
                    }
                )
            
            return {'processed': processed_count, 'errors': error_count}
        
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found: {device_id}")
            raise ValueError(f"Device not found: {device_id}")
        
        except Exception as e:
            logger.error(f"Error processing batch data: {str(e)}")
            raise
    
    @database_sync_to_async
    def process_stacked_timeseries(self, station_id, start_time, end_time, interval, metrics):
        """
        Process time series data for multiple metrics
        
        Args:
            station_id: ID of the station/device
            start_time: ISO formatted start time
            end_time: ISO formatted end time
            interval: Sampling interval in seconds
            metrics: Dictionary of metric names and values
            
        Returns:
            dict: Processing results
        """
        from django.db import transaction
        from datetime import datetime, timedelta
        import pandas as pd
        
        try:
            device = FieldDevice.objects.get(device_id=station_id)
            
            # Parse start and end times
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Create date range using pandas for efficient time series handling
            date_range = pd.date_range(start=start, end=end, freq=f"{interval}S")
            
            # Create an upload record
            upload = FieldDataUpload.objects.create(
                title=f"Time series data for {device.name}",
                description=f"From {start} to {end} at {interval}s intervals",
                status='processing',
                data_format='json',
                device_type=device.device_type,
            )
            
            with transaction.atomic():
                records_to_create = []
                
                # Get extra metadata if provided
                lat = metrics.get('latitude')
                lon = metrics.get('longitude')
                
                # Create records for each timestamp
                for i, timestamp in enumerate(date_range):
                    data = {}
                    
                    # Add all metrics for this timestamp
                    for metric_name, values in metrics.items():
                        if metric_name not in ('latitude', 'longitude') and isinstance(values, list):
                            # Skip non-data fields, ensure values is a list
                            if i < len(values):
                                data[metric_name] = values[i]
                    
                    # Create the record
                    record = FieldDataRecord(
                        upload=upload,
                        device=device,
                        timestamp=timestamp,
                        latitude=lat[i] if isinstance(lat, list) and i < len(lat) else None,
                        longitude=lon[i] if isinstance(lon, list) and i < len(lon) else None,
                        data=data
                    )
                    records_to_create.append(record)
                
                # Bulk create all records
                FieldDataRecord.objects.bulk_create(records_to_create)
                
                # Update upload status
                upload.processed_count = len(records_to_create)
                upload.status = 'completed'
                upload.save()
                
                # Update device last communication
                device.last_communication = timezone.now()
                device.save(update_fields=['last_communication'])
            
            return {'created': len(records_to_create)}
        
        except FieldDevice.DoesNotExist:
            logger.error(f"Device not found: {station_id}")
            raise ValueError(f"Device not found: {station_id}")
        
        except Exception as e:
            logger.error(f"Error processing time series: {str(e)}")
            raise
