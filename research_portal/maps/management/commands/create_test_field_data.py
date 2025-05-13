from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta
import random
import string
from random import randint

from maps.models import WeatherStation, Country
from maps.field_models import (
    DeviceType, FieldDevice, DeviceCalibration, FieldDataUpload, FieldDataRecord
)

class Command(BaseCommand):
    help = 'Create test field device data'

    def generate_random_string(self, length):
        letters = string.ascii_letters
        return ''.join(random.choice(letters) for _ in range(length))

    def create_test_device_type(self):
        return DeviceType.objects.create(
            name=f"Test Device Type {self.generate_random_string(5)}",
            description="Test device type for demonstration",
            model_number=self.generate_random_string(8),
            manufacturer="Test Manufacturer",
            data_format="JSON",
            battery_type="Lithium",
            signal_protocol="LoRaWAN",
            supports_gps=True,
            supports_bluetooth=True,
            supports_wifi=True,
            supports_lora=True,
            battery_life_days=365,
            calibration_interval_days=90,
            maintenance_interval_days=180
        )

    def create_test_field_device(self, device_type, status):
        return FieldDevice.objects.create(
            name=f"Test Device {self.generate_random_string(5)}",
            device_id=self.generate_random_string(10),
            device_type=device_type,
            serial_number=self.generate_random_string(12),
            firmware_version="1.0.0",
            location=Point(random.uniform(-180, 180), random.uniform(-90, 90)),
            installation_date=datetime.now() - timedelta(days=random.randint(30, 365)),
            last_location_update=datetime.now() - timedelta(days=random.randint(0, 30)),
            status=status,
            battery_level=random.randint(0, 100),
            signal_strength=random.randint(-100, -50),
            collection_interval=300,  # 5 minutes
            data_retention_days=30,
            calibration_due=datetime.now() + timedelta(days=90)
        )

    def create_test_calibration(self, field_device):
        return DeviceCalibration.objects.create(
            field_device=field_device,
            calibration_date=datetime.now() - timedelta(days=random.randint(0, 90)),
            calibrated_by="Test Technician",
            status="completed",
            calibration_notes="Test calibration performed successfully",
            calibration_data={
                "temperature_offset": random.uniform(-2.0, 2.0),
                "humidity_offset": random.uniform(-5.0, 5.0),
                "battery_voltage": random.uniform(3.0, 4.2)
            }
        )

    def create_test_field_data_upload(self):
        return FieldDataUpload.objects.create(
            title="Test Data Upload",
            description="Test data upload for demonstration",
            status="completed",
            file_type="json",
            total_records=100,
            processed_records=100,
            failed_records=0
        )

    def create_test_field_data_records(self, upload, device):
        for i in range(24):  # Create 24 hours of data
            timestamp = datetime.now() - timedelta(hours=i)
            FieldDataRecord.objects.create(
                upload=upload,
                device=device,
                device_id=device.device_id,
                timestamp=timestamp,
                latitude=device.location.y,
                longitude=device.location.x,
                data={
                    "temperature": random.uniform(-20, 40),
                    "humidity": random.uniform(0, 100),
                    "battery_voltage": random.uniform(3.0, 4.2),
                    "signal_strength": random.randint(-100, -50)
                }
            )

    def handle(self, *args, **options):
        # Create test device types
        device_type_1 = self.create_test_device_type()
        device_type_2 = self.create_test_device_type()

        # Create test field devices with different statuses
        statuses = ['active', 'maintenance', 'inactive', 'lost']
        for status in statuses:
            device = self.create_test_field_device(device_type_1, status)
            self.create_test_calibration(device)

            # Create a data upload for this device
            upload = self.create_test_field_data_upload()
            self.create_test_field_data_records(upload, device)

        # Create additional devices with different battery levels
        for i in range(3):
            battery_level = random.randint(0, 100)
            status = 'active' if battery_level > 20 else 'maintenance'
            device = self.create_test_field_device(device_type_2, status)
            device.battery_level = battery_level
            device.save()
            self.create_test_calibration(device)

        self.stdout.write(self.style.SUCCESS('Successfully created test field device data'))
