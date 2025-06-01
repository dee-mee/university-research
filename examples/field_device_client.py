import requests
import json
import time
from datetime import datetime
import random
import logging
from typing import Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FieldDeviceClient:
    def __init__(self, device_id: str, server_url: str):
        """
        Initialize the field device client
        
        Args:
            device_id: Unique identifier for this device
            server_url: URL of the data collection server
        """
        self.device_id = device_id
        self.server_url = server_url.rstrip('/')
        self.api_endpoint = f"{self.server_url}/api/field-data-uploads/upload_data/"
        self.session = requests.Session()
        self.battery_level = 100
        self.signal_strength = -75
        
        # Initialize device location (can be updated later)
        self.latitude = 37.7749  # Example: San Francisco
        self.longitude = -122.4194
        
        # Initialize sensor readings
        self.temperature = 25.0
        self.humidity = 60.0
        
        # Initialize last communication time
        self.last_communication = datetime.now()
        
        logger.info(f"Field device client initialized with ID: {self.device_id}")

    def _get_current_data(self) -> Dict:
        """Get current sensor readings and device status"""
        self.temperature += random.uniform(-0.5, 0.5)
        self.humidity += random.uniform(-2, 2)
        
        # Simulate battery drain
        if self.battery_level > 0:
            self.battery_level -= 0.1
        
        # Simulate signal strength changes
        self.signal_strength += random.randint(-2, 2)
        self.signal_strength = max(-100, min(-50, self.signal_strength))
        
        return {
            "temperature": round(self.temperature, 1),
            "humidity": round(self.humidity, 1),
            "battery_voltage": round(self.battery_level / 100 * 4.2, 2),
            "signal_strength": self.signal_strength
        }

    def _prepare_payload(self) -> Dict:
        """Prepare the payload for data upload"""
        data = self._get_current_data()
        
        payload = {
            "device_id": self.device_id,
            "timestamp": datetime.now().isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "data": data
        }
        
        return payload

    def _handle_error(self, response: requests.Response) -> None:
        """Handle API errors"""
        try:
            error_data = response.json()
            error_message = error_data.get('error', 'Unknown error')
            logger.error(f"API Error: {error_message}")
            
            # Implement retry logic based on error type
            if response.status_code == 429:  # Too Many Requests
                logger.info("Rate limit hit, waiting before retry...")
                time.sleep(60)  # Wait 1 minute before retrying
            elif response.status_code == 400:  # Bad Request
                logger.error("Invalid data format, check payload")
                # Implement data validation and correction
            else:
                logger.error(f"Unexpected error: {response.status_code}")
                # Implement general error handling
        except json.JSONDecodeError:
            logger.error("Invalid response format from server")

    def send_data(self) -> bool:
        """
        Send data to the server
        
        Returns:
            True if data was successfully sent, False otherwise
        """
        try:
            payload = self._prepare_payload()
            logger.info(f"Sending data to server: {payload}")
            
            try:
                response = self.session.post(
                    self.api_endpoint,
                    json=payload,
                    timeout=10  # 10 second timeout
                )
                response.raise_for_status()  # Raise an exception for bad status codes
                
                # Try to parse the response as JSON
                response_data = response.json()
                if response_data.get('status') == 'success':
                    logger.info("Data uploaded successfully")
                    self.last_communication = datetime.now()
                    return True
                else:
                    error_message = response_data.get('error', 'Unknown error')
                    logger.error(f"Server error: {error_message}")
                    return False
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error: {str(e)}")
                return False
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {str(e)}")
                return False
            except json.JSONDecodeError:
                logger.error("Invalid JSON response from server")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Network error: {str(e)}")
            return False

    def update_location(self, latitude: float, longitude: float) -> None:
        """Update device location"""
        self.latitude = latitude
        self.longitude = longitude
        logger.info(f"Device location updated to: {latitude}, {longitude}")

    def update_battery_level(self, level: float) -> None:
        """Update battery level"""
        self.battery_level = level
        logger.info(f"Battery level updated to: {level}%")

    def run(self, interval: int = 300) -> None:
        """
        Run the device client in a loop
        
        Args:
            interval: Time between data transmissions in seconds (default: 300s)
        """
        while True:
            try:
                success = self.send_data()
                if success:
                    # Only wait if successful
                    time.sleep(interval)
                else:
                    # Wait a shorter time before retrying on failure
                    time.sleep(60)
                    
            except KeyboardInterrupt:
                logger.info("Device client stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Field Device Data Client')
    parser.add_argument('--device-id', required=True, help='Unique identifier for this device')
    parser.add_argument('--server-url', required=True, help='URL of the data collection server')
    parser.add_argument('--interval', type=int, default=300, help='Time between data transmissions in seconds (default: 300)')
    
    args = parser.parse_args()
    
    # Create device client
    client = FieldDeviceClient(args.device_id, args.server_url)
    
    # Start sending data
    client.run(interval=args.interval)
