"""
WebSocket consumers for real-time data updates
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .field_models import FieldDevice, FieldDataRecord, Alert

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
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
    
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
