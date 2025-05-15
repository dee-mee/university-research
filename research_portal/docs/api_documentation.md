# API Documentation

## Overview
The Field Data Collection System provides a RESTful API for interacting with field devices and managing data. All API endpoints use JSON for data exchange.

## Authentication

### Token Authentication
- Required for all endpoints
- Token must be included in Authorization header
- Example: `Authorization: Token your_token_here`

### Session Authentication
- Alternative authentication method
- Requires valid session cookie

## Rate Limiting
- 100 requests per minute
- 1000 requests per hour
- IP-based rate limiting
- Exempt for authenticated users

## Error Handling
All responses follow this format:
```json
{
    "success": boolean,
    "data": {},
    "error": string,
    "error_code": string
}
```

## API Endpoints

### 1. Device Management

#### Get All Devices
```
GET /api/devices/
```
Response:
```json
{
    "count": integer,
    "next": string,
    "previous": string,
    "results": [
        {
            "id": integer,
            "device_id": string,
            "name": string,
            "device_type": integer,
            "location": {
                "type": "Point",
                "coordinates": [longitude, latitude]
            },
            "status": string,
            "battery_level": float,
            "signal_strength": integer
        }
    ]
}
```

#### Create Device
```
POST /api/devices/
```
Request:
```json
{
    "device_id": string,
    "name": string,
    "device_type": integer,
    "latitude": float,
    "longitude": float,
    "status": string
}
```

### 2. Data Collection

#### Upload Field Data
```
POST /api/field-data/upload/
```
Request:
```json
{
    "device_id": string,
    "timestamp": string,
    "latitude": float,
    "longitude": float,
    "data": {
        "temperature": float,
        "humidity": float,
        "battery_voltage": float,
        "signal_strength": integer
    }
}
```

#### Get Historical Data
```
GET /api/data/historical/
```
Parameters:
- `device_id`: string
- `start_date`: string
- `end_date`: string
- `data_type`: string

### 3. Data Analysis

#### Get Statistics
```
GET /api/data/statistics/
```
Parameters:
- `device_id`: string
- `metric`: string
- `timeframe`: string

#### Generate Report
```
POST /api/reports/generate/
```
Request:
```json
{
    "device_ids": [string],
    "start_date": string,
    "end_date": string,
    "metrics": [string],
    "format": string
}
```

### 4. Alert System

#### Create Alert Rule
```
POST /api/alerts/rules/
```
Request:
```json
{
    "device_id": string,
    "metric": string,
    "threshold": float,
    "comparison": string,
    "notification_channels": [string]
}
```

#### Get Alert History
```
GET /api/alerts/history/
```
Parameters:
- `device_id`: string
- `start_date`: string
- `end_date`: string

### 5. WebSocket API

#### Connection
```
ws://your-domain/ws/field-data/{device_id}/
```

#### Message Types
1. Data Update
```json
{
    "type": "data_update",
    "device_id": string,
    "data": {
        "temperature": float,
        "humidity": float,
        "battery_voltage": float,
        "signal_strength": integer
    }
}
```

2. Status Update
```json
{
    "type": "status_update",
    "device_id": string,
    "status": string,
    "battery_level": float,
    "signal_strength": integer
}
```

3. Alert Notification
```json
{
    "type": "alert",
    "device_id": string,
    "alert_type": string,
    "message": string
}
```

## Response Codes

### Success
- 200 OK: Successful request
- 201 Created: Resource created
- 204 No Content: Successful update

### Errors
- 400 Bad Request: Invalid request
- 401 Unauthorized: Authentication required
- 403 Forbidden: Insufficient permissions
- 404 Not Found: Resource not found
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Server error

## Security

### Data Protection
- All data is encrypted in transit
- Sensitive data is encrypted at rest
- Token-based authentication
- Rate limiting
- IP whitelisting

### Best Practices
1. Always use HTTPS
2. Store tokens securely
3. Implement proper error handling
4. Validate all inputs
5. Use proper rate limiting

## Examples

### Python Example
```python
import requests

headers = {
    'Authorization': 'Token your_token_here'
}

# Get device data
response = requests.get(
    'http://your-domain/api/devices/',
    headers=headers
)

# Upload data
data = {
    'device_id': 'device123',
    'timestamp': '2023-05-15T12:00:00+03:00',
    'data': {
        'temperature': 25.5,
        'humidity': 60.0
    }
}
response = requests.post(
    'http://your-domain/api/field-data/upload/',
    json=data,
    headers=headers
)
```

### JavaScript Example
```javascript
// Get device data
fetch('http://your-domain/api/devices/', {
    headers: {
        'Authorization': 'Token your_token_here'
    }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error(error));

// Upload data
const data = {
    device_id: 'device123',
    timestamp: '2023-05-15T12:00:00+03:00',
    data: {
        temperature: 25.5,
        humidity: 60.0
    }
};

fetch('http://your-domain/api/field-data/upload/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Token your_token_here'
    },
    body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error(error));
```

## Version History
- 1.0.0: Initial API release
- 1.1.0: Added WebSocket support
- 1.2.0: Added data analysis endpoints
- 1.3.0: Enhanced security features
- 1.4.0: Improved error handling
