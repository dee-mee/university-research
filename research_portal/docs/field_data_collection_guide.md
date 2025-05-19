# Field Data Collection System Guide

## Overview

The Field Data Collection System is designed to collect, process, and visualize data from remote field devices deployed across various research sites. This system integrates with the University Research Portal to provide a comprehensive platform for environmental data collection and analysis.

## System Components

1. **Field Devices**: Physical devices deployed in the field that collect environmental data (temperature, humidity, etc.)
2. **Device Types**: Configuration templates for different types of field devices
3. **Data Upload API**: REST API endpoint for devices to send data to the central server
4. **Data Visualization**: Web interface for viewing and analyzing collected data

## Setting Up a Field Device

### 1. Create a Device Type

Before registering field devices, you need to create at least one device type:

```python
from maps.field_models import DeviceType

# Create a basic device type
device_type = DeviceType.objects.create(
    name="Weather Station",
    manufacturer="Research Equipment Inc.",
    model_number="WS-2000",
    communication_protocol="wifi",
    power_source="solar",
    battery_life_days=90,
    firmware_version="1.0.0",
    has_temperature=True,
    has_humidity=True,
    has_precipitation=True
)
```

### 2. Register a Field Device

Devices can be registered manually through the admin interface or automatically when they first connect:

```python
from maps.field_models import FieldDevice
from django.contrib.gis.geos import Point

# Create a new field device
device = FieldDevice.objects.create(
    device_id="FIELD_DEVICE_001",
    name="North Campus Weather Station",
    device_type=device_type,
    location=Point(-122.4194, 37.7749),  # longitude, latitude
    status="active",
    transmission_interval=60  # minutes
)
```

## Connecting Field Devices to the System

### API Endpoint

Field devices can upload data to the following endpoint:

```
POST /api/field-data-uploads/upload_data/
```

### Request Format

```json
{
    "device_id": "FIELD_DEVICE_001",
    "timestamp": "2025-05-13T15:36:31+03:00",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "data": {
        "temperature": 25.5,
        "humidity": 60,
        "battery_voltage": 3.8,
        "signal_strength": -75
    }
}
```

### Response Format

```json
{
    "status": "success",
    "message": "Data uploaded successfully",
    "device_status": "active",
    "device_id": "FIELD_DEVICE_001",
    "timestamp": "2025-05-13T15:36:31+03:00"
}
```

## Using the Field Device Client

The repository includes a Python client for field devices:

### Basic Usage

```bash
python examples/field_device_client.py --device-id FIELD_DEVICE_001 --server-url http://127.0.0.1:8000
```

### Client Options

- `--device-id`: Unique identifier for the device (required)
- `--server-url`: URL of the data collection server (required)
- `--interval`: Time between data transmissions in seconds (default: 300)

### Example Implementation

```python
# Initialize the client
client = FieldDeviceClient(device_id="FIELD_DEVICE_001", server_url="http://research-portal.example.com")

# Update device location if needed
client.update_location(latitude=37.7749, longitude=-122.4194)

# Start sending data
client.run(interval=300)  # Send data every 5 minutes
```

## Data Visualization

Field device data can be viewed on the map interface:

1. Navigate to `/maps/map/` in the research portal
2. Use the filter controls to show/hide different data sources
3. Click on field device markers to view detailed information

## Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure the server is running and accessible from the device's network
2. **Authentication Errors**: Verify that the device ID is registered in the system
3. **Invalid Data Format**: Check that the JSON payload matches the expected format

### Logging

The system logs device connections and data uploads. Check the server logs for detailed information:

```bash
tail -f /path/to/research_portal/logs/debug.log
```

## Security Considerations

- For production deployments, enable authentication for the API endpoints
- Review and update the permissions in `api_views.py` from `AllowAny` to appropriate permission classes
- Consider implementing rate limiting for the API endpoints

## Next Steps

- Implement data validation and filtering
- Add support for additional sensor types
- Enhance the visualization interface with time-series charts
- Develop automated alerts based on sensor readings
