# Field Device Connection and Data Flow System

This document provides a detailed explanation of the field device connection system, including how devices connect to the system, how data flows through the system, and how real-time updates are handled.

## Architecture Overview

The system uses a WebSocket-based architecture for real-time communication:

```
Field Device → API Endpoint → WebSocket Consumer → Browser Dashboard
```

## Key Components

### 1. WebSocket Consumer (FieldDataConsumer)
- Handles WebSocket connections from browsers
- Receives and broadcasts real-time updates
- Manages device subscriptions
- Located in `maps/consumers.py`

### 2. API Endpoint (device_data_upload)
- Receives data from field devices
- Validates incoming data
- Creates data records
- Triggers alerts
- Located in `maps/field_device_api.py`

## Connection Flow

### 1. Initial Connection
```python
# Device connects to the API endpoint
POST /maps/api/field-device-data/
```

### 2. Data Validation
```python
# In field_device_api.py
def device_data_upload(request):
    # Validate incoming data
    is_valid, cleaned_data, errors, warnings = validate_field_device_data(data)
    
    if not is_valid:
        return JsonResponse({'error': 'Validation failed'}, status=400)
```

### 3. Data Processing
```python
# Create or update device record
device = FieldDevice.objects.filter(device_id=device_id).first()
if not device:
    device = FieldDevice.objects.create(
        device_id=device_id,
        device_type=device_type,
        name=f"Device {device_id}",
        location=Point(longitude, latitude)
    )
```

### 4. Real-time Updates
```python
# Send updates via WebSocket
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
```

### 5. Alert System
```python
# Check for alerts
alerts = check_for_alerts(device, sensor_data)
if alerts:
    for alert in alerts:
        # Create alert record
        Alert.objects.create(
            device=device,
            alert_type=alert['type'],
            message=alert['message'],
            severity=alert['severity']
        )
```

## WebSocket Communication

The WebSocket consumer handles:
- Initial data load
- Real-time updates
- Device status changes
- Alerts

```python
# In consumers.py
class FieldDataConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.device_id = self.scope['url_route']['kwargs'].get('device_id', 'all')
        self.group_name = f'field_data_{self.device_id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
```

## Client-Side Implementation

The client-side JavaScript handles:
- WebSocket connection
- Real-time updates
- Map markers
- Device status
- Alerts

```javascript
// Initialize WebSocket
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/field-data/all/`;
    
    socket = new WebSocket(wsUrl);
    
    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        
        if (data.type === 'data_update') {
            updateDeviceData(data.device_id, data.data);
        } else if (data.type === 'alert') {
            addAlert(data);
        }
    };
}
```

## Connection States

The system tracks device states:
- Active: Device is communicating normally
- Maintenance: Device is under maintenance
- Inactive: Device is not active but known
- Lost: Device has not communicated recently
- Calibration: Device needs calibration

## Data Flow Example

When a temperature sensor sends data:
1. Device sends POST request to `/maps/api/field-device-data/`
2. Data is validated and stored
3. Temperature is checked against thresholds
4. If temperature is too high/low:
   - Alert is created
   - Alert is broadcast via WebSocket
   - Dashboard updates in real-time
5. Map marker is updated with new position
6. Charts are updated with new data point

## System Features

The architecture ensures:
- Real-time updates for all connected clients
- Efficient data distribution using WebSocket groups
- Automatic alert generation for abnormal readings
- Persistent storage of all device data
- Easy scalability for multiple devices

## Error Handling

The system includes multiple levels of error handling:
1. Data validation at API level
2. Connection state monitoring
3. Alert generation for critical issues
4. Automatic retry mechanisms
5. Logging of all errors and warnings

## Security Considerations

1. All WebSocket connections use secure protocols (wss://)
2. API endpoints require authentication
3. Data is validated before processing
4. Rate limiting is implemented to prevent abuse
5. Device IDs are validated against registered devices

## Performance Optimizations

1. WebSocket groups for efficient broadcasting
2. Database indexing for fast lookups
3. Asynchronous processing for real-time updates
4. Caching of frequently accessed data
5. Optimized query patterns

## Monitoring and Maintenance

The system provides:
- Real-time device status monitoring
- Alert history tracking
- Performance metrics collection
- Error reporting and logging
- Maintenance scheduling capabilities

This documentation provides a comprehensive overview of the field device connection system. For more detailed information about specific components or implementation details, please refer to the relevant code files in the `maps` directory.
