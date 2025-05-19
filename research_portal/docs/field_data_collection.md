# Field Data Collection System Documentation

## Overview

The Field Data Collection System is designed to collect, store, and visualize data from field devices deployed in various locations. The system supports multiple types of field devices and provides a comprehensive interface for managing and analyzing collected data.

## System Architecture

### Main Components

1. **Field Devices**
   - IoT devices deployed in the field
   - Collect environmental and operational data
   - Can be of different types with varying capabilities

2. **Data Collection API**
   - RESTful API endpoint for device data submission
   - Handles device registration and data storage
   - Provides status updates and error handling

3. **Web Interface**
   - Interactive map-based visualization
   - Device management dashboard
   - Data analysis and reporting tools

## Field Device Integration

### Device Registration

When a new device first sends data, the system will automatically register it if it doesn't exist in the database. The device must provide a unique `device_id` which will be used as its identifier.

### Data Transmission Protocol

#### API Endpoint
```
POST /api/field-data-uploads/upload_data/
```

#### Required Request Format
```json
{
    "device_id": "string",  // Required - Unique device identifier
    "timestamp": "2023-05-13T15:36:31+03:00",  // Required - ISO 8601 timestamp
    "latitude": 37.7749,  // Required - Device's current latitude
    "longitude": -122.4194,  // Required - Device's current longitude
    "data": {  // Required - Device-specific data
        "temperature": 25.5,  // Example: Temperature reading
        "humidity": 60,  // Example: Humidity reading
        "battery_voltage": 3.8,  // Battery voltage
        "signal_strength": -75  // Signal strength
        // ... other device-specific data fields
    }
}
```

### Response Format

#### Success Response (201 Created)
```json
{
    "status": "success",
    "message": "Data uploaded successfully",
    "device_status": "active"  // Current status of the device
}
```

#### Error Response (400 Bad Request)
```json
{
    "error": "Missing required fields"
}
```

## Data Management

### Device Types

The system supports different types of field devices, each with its own characteristics:

```python
class DeviceType:
    name: str  # Name of the device type
    manufacturer: str  # Device manufacturer
    model_number: str  # Device model number
    communication_protocol: str  # Communication method (WiFi, LoRa, etc.)
    power_source: str  # Power source type
    battery_life_days: int  # Expected battery life
    firmware_version: str  # Current firmware version
    
    # Data capabilities
    has_temperature: bool
    has_precipitation: bool
    has_humidity: bool
    has_wind: bool
    has_air_quality: bool
    has_soil_moisture: bool
    has_water_level: bool
```

### Device Statuses

Field devices can have different operational statuses:

- `active`: Device is operational and communicating normally
- `maintenance`: Device requires maintenance
- `inactive`: Device is not currently active
- `lost`: Device has been lost or is not communicating

### Data Storage

All collected data is stored in two main models:

1. `FieldDataUpload`
   - Stores batch uploads of field device data
   - Tracks upload status and processing progress
   - Maintains error logs if data processing fails

2. `FieldDataRecord`
   - Individual data points from devices
   - Stores timestamp, location, and device-specific data
   - Linked to both the upload batch and the device

## Web Interface Features

### Map Visualization

The system provides an interactive map interface with the following features:

1. **Data Source Filtering**
   - Toggle visibility of Weather Stations, Field Devices, and Manual Entries
   - Count badges showing number of items for each category
   - Reset filters button

2. **Field Device Status Filtering**
   - Filter by device status (active, maintenance, inactive, lost)
   - Status count indicators
   - Color-coded markers based on status

3. **Battery Level Filtering**
   - Filter by battery level ranges (good, low, critical)
   - Battery indicator on device markers
   - Battery level count indicators

### Device Popups

When clicking on a field device marker, the popup displays:

- Device name and ID
- Device type information
- Current status and last communication time
- Battery level with visual indicator
- Signal strength
- Quick action buttons for viewing details and calibration

## Admin Interface

The admin interface provides comprehensive management capabilities:

1. **Device Management**
   - View and edit device information
   - Track device status and maintenance schedules
   - View battery levels and signal strengths
   - Manage device calibrations

2. **Data Uploads**
   - View upload history
   - Monitor processing status
   - View error logs
   - Download processed data

3. **Data Records**
   - Search and filter device data
   - View data trends
   - Export data for analysis

## Error Handling

The system implements robust error handling:

1. **Data Validation**
   - Validates incoming data format
   - Checks for required fields
   - Verifies data ranges and types

2. **Error Logging**
   - Stores detailed error information
   - Tracks failed uploads
   - Provides error messages for troubleshooting

3. **Status Updates**
   - Updates device status based on communication
   - Triggers maintenance alerts
   - Logs battery level warnings

## Security Considerations

1. **API Authentication**
   - Currently set to AllowAny for testing
   - Should be changed to proper authentication in production
   - Consider implementing API keys or tokens for field devices

2. **Data Validation**
   - All incoming data is validated
   - Prevents injection attacks
   - Ensures data integrity

## Best Practices for Field Devices

1. **Data Transmission**
   - Send data at regular intervals based on device capabilities
   - Include timestamps in UTC
   - Send battery level and signal strength with each transmission

2. **Error Handling**
   - Implement retry logic for failed transmissions
   - Log errors locally if unable to communicate
   - Implement power-saving modes when battery is low

3. **Device Maintenance**
   - Regularly check battery levels
   - Perform maintenance when scheduled
   - Update firmware as needed

## Future Enhancements

1. **Advanced Analytics**
   - Implement data trend analysis
   - Add predictive maintenance alerts
   - Create custom dashboards

2. **Device Management**
   - Add remote device configuration
   - Implement firmware update system
   - Add device grouping and organization

3. **API Improvements**
   - Add bulk data upload support
   - Implement data compression
   - Add rate limiting and throttling

4. **Visualization**
   - Add heat maps for data density
   - Implement time-series analysis
   - Add custom visualization options

## Troubleshooting

### Common Issues

1. **Device Not Showing Up**
   - Check if device ID is unique
   - Verify network connectivity
   - Check API endpoint URL

2. **Data Not Updating**
   - Check device battery level
   - Verify signal strength
   - Check device status

3. **API Errors**
   - Check request format
   - Verify required fields
   - Check server logs for errors

### Support Information

For technical support, please contact:
- Support Email: support@example.com
- Documentation: https://docs.example.com/field-data-collection
- GitHub Repository: https://github.com/example/field-data-collection
