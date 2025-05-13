"""
Management command to create predefined device types
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _
from maps.field_models import DeviceType

class Command(BaseCommand):
    help = 'Creates predefined device types for field data collection'

    def handle(self, *args, **options):
        # Create a list of device types
        device_types = [
            {
                'name': 'Weather Station Pro',
                'manufacturer': 'EcoSense Technologies',
                'model_number': 'WS-5000',
                'description': 'Professional-grade weather station with comprehensive sensor suite',
                'communication_protocol': 'cellular',
                'power_source': 'solar',
                'battery_life_days': 180,
                'firmware_version': '2.1.0',
                'has_temperature': True,
                'has_precipitation': True,
                'has_humidity': True,
                'has_wind': True,
                'has_air_quality': True,
                'has_soil_moisture': False,
                'has_water_level': False,
            },
            {
                'name': 'Soil Monitoring System',
                'manufacturer': 'AgriTech Solutions',
                'model_number': 'SMS-200',
                'description': 'Specialized device for soil condition monitoring',
                'communication_protocol': 'lora',
                'power_source': 'battery',
                'battery_life_days': 90,
                'firmware_version': '1.5.2',
                'has_temperature': True,
                'has_precipitation': False,
                'has_humidity': True,
                'has_wind': False,
                'has_air_quality': False,
                'has_soil_moisture': True,
                'has_water_level': False,
            },
            {
                'name': 'Hydrology Monitor',
                'manufacturer': 'WaterTech Systems',
                'model_number': 'HM-350',
                'description': 'Water level and quality monitoring system for rivers and lakes',
                'communication_protocol': 'cellular',
                'power_source': 'solar',
                'battery_life_days': 120,
                'firmware_version': '3.0.1',
                'has_temperature': True,
                'has_precipitation': True,
                'has_humidity': False,
                'has_wind': False,
                'has_air_quality': False,
                'has_soil_moisture': False,
                'has_water_level': True,
            },
            {
                'name': 'Air Quality Sensor',
                'manufacturer': 'CleanAir Monitoring',
                'model_number': 'AQS-100',
                'description': 'Specialized air quality monitoring device for urban environments',
                'communication_protocol': 'wifi',
                'power_source': 'mains',
                'battery_life_days': None,
                'firmware_version': '2.3.0',
                'has_temperature': True,
                'has_precipitation': False,
                'has_humidity': True,
                'has_wind': False,
                'has_air_quality': True,
                'has_soil_moisture': False,
                'has_water_level': False,
            },
            {
                'name': 'Compact Weather Station',
                'manufacturer': 'FieldSense',
                'model_number': 'CWS-50',
                'description': 'Portable, battery-powered weather station for temporary deployments',
                'communication_protocol': 'bluetooth',
                'power_source': 'battery',
                'battery_life_days': 30,
                'firmware_version': '1.2.0',
                'has_temperature': True,
                'has_precipitation': True,
                'has_humidity': True,
                'has_wind': True,
                'has_air_quality': False,
                'has_soil_moisture': False,
                'has_water_level': False,
            },
        ]

        # Create device types
        created_count = 0
        updated_count = 0
        
        for device_type_data in device_types:
            device_type, created = DeviceType.objects.update_or_create(
                name=device_type_data['name'],
                manufacturer=device_type_data['manufacturer'],
                defaults=device_type_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created device type: {device_type.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated device type: {device_type.name}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully created {created_count} and updated {updated_count} device types'
        ))
