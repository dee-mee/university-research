import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.utils import timezone
from maps.models import WeatherStation, ClimateData
from maps.field_models import DeviceType, FieldDevice, FieldDataUpload, FieldDataRecord
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Generates sample data for development and testing'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing data before generating new data')
        parser.add_argument('--users', type=int, default=3, help='Number of sample users to create')
        parser.add_argument('--stations', type=int, default=5, help='Number of weather stations to create')
        parser.add_argument('--devices', type=int, default=10, help='Number of field devices to create')
        parser.add_argument('--days', type=int, default=30, help='Number of days of historical data to generate')

    def handle(self, *args, **options):
        clear = options['clear']
        num_users = options['users']
        num_stations = options['stations']
        num_devices = options['devices']
        days = options['days']

        if clear:
            self.stdout.write(self.style.WARNING('Clearing existing data...'))
            self.clear_data()

        self.stdout.write(self.style.SUCCESS('Generating sample data...'))
        
        # Create admin user if not exists
        admin = self.create_admin_user()
        
        # Create sample users
        users = self.create_sample_users(num_users)
        
        # Create device types
        device_types = self.create_device_types()
        
        # Create weather stations
        stations = self.create_weather_stations(num_stations)
        
        # Create field devices
        devices = self.create_field_devices(num_devices, stations, device_types, users)
        
        # Generate climate data
        self.generate_climate_data(stations, days, users)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated sample data with {len(stations)} stations and {len(devices)} devices'))

    def clear_data(self):
        """Clear existing data"""
        models_to_clear = [
            FieldDataRecord,
            FieldDataUpload,
            FieldDevice,
            DeviceType,
            ClimateData,
            WeatherStation,
        ]
        
        # Keep admin users
        admin_users = list(User.objects.filter(is_superuser=True))
        
        # Clear all other users
        User.objects.exclude(is_superuser=True).delete()
        
        # Clear other data
        for model in models_to_clear:
            model.objects.all().delete()
            
        # Restore admin users
        for user in admin_users:
            user.save()

    def create_admin_user(self):
        """Create admin user if not exists"""
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        if created:
            admin.set_password('admin')
            admin.save()
            self.stdout.write(self.style.SUCCESS('Created admin user (username: admin, password: admin)'))
        return admin

    def create_sample_users(self, count):
        """Create sample users"""
        users = []
        for i in range(1, count + 1):
            user, created = User.objects.get_or_create(
                username=f'user{i}',
                defaults={
                    'email': f'user{i}@example.com',
                    'first_name': f'User',
                    'last_name': f'{i}',
                    'is_active': True
                }
            )
            if created:
                user.set_password('password')
                user.save()
                users.append(user)
        self.stdout.write(self.style.SUCCESS(f'Created {len(users)} sample users'))
        return users

    def create_device_types(self):
        """Create device types"""
        types = [
            {
                'name': 'Weather Station Pro',
                'manufacturer': 'EcoSense',
                'model_number': 'WS-5000',
                'description': 'Professional weather monitoring station',
                'communication_protocol': 'cellular',
                'power_source': 'solar',
                'battery_life_days': 180,
                'has_temperature': True,
                'has_humidity': True,
                'has_precipitation': True,
                'has_wind': True,
                'has_air_quality': True,
            },
            {
                'name': 'Soil Sensor Basic',
                'manufacturer': 'AgriTech',
                'model_number': 'SS-200',
                'description': 'Basic soil moisture and temperature sensor',
                'communication_protocol': 'lora',
                'power_source': 'battery',
                'battery_life_days': 365,
                'has_temperature': True,
                'has_soil_moisture': True,
            },
            {
                'name': 'Water Quality Monitor',
                'manufacturer': 'HydroSense',
                'model_number': 'WQ-1000',
                'description': 'Water quality monitoring device',
                'communication_protocol': 'cellular',
                'power_source': 'solar',
                'battery_life_days': 90,
                'has_temperature': True,
                'has_ph': True,
                'has_turbidity': True,
                'has_conductivity': True,
            }
        ]
        
        device_types = []
        for type_data in types:
            device_type, created = DeviceType.objects.get_or_create(
                name=type_data['name'],
                manufacturer=type_data['manufacturer'],
                defaults=type_data
            )
            device_types.append(device_type)
            
        self.stdout.write(self.style.SUCCESS(f'Created {len(device_types)} device types'))
        return device_types

    def create_weather_stations(self, count):
        """Create weather stations"""
        stations = []
        regions = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret', 'Kakamega', 'Kisii', 'Meru', 'Nyeri', 'Garissa']
        
        for i in range(count):
            region = regions[i % len(regions)]
            station = WeatherStation.objects.create(
                name=f'{region} Station {i + 1}',
                station_id=f'STN-{region.upper()}-{i + 1:03d}',
                description=f'Weather monitoring station in {region}',
                location=Point(
                    random.uniform(33.0, 42.0),  # Kenya longitude range
                    random.uniform(-4.7, 4.7),    # Kenya latitude range
                    srid=4326
                ),
                altitude=random.randint(0, 3000),
                is_active=random.choice([True, True, True, False]),  # 75% chance of being active
                has_temperature=True,
                has_precipitation=True,
                has_humidity=True,
                has_wind=True,
                has_air_quality=random.choice([True, False]),
            )
            stations.append(station)
            
        self.stdout.write(self.style.SUCCESS(f'Created {len(stations)} weather stations'))
        return stations

    def create_field_devices(self, count, stations, device_types, users):
        """Create field devices"""
        status_choices = ['active', 'maintenance', 'inactive', 'lost']
        devices = []
        
        for i in range(count):
            device = FieldDevice.objects.create(
                device_id=f'DEV-{i + 1:04d}',
                name=f'Device {i + 1}',
                device_type=random.choice(device_types),
                weather_station=random.choice(stations) if random.random() > 0.3 else None,  # 70% chance of being assigned to a station
                location=Point(
                    random.uniform(33.0, 42.0),  # Kenya longitude range
                    random.uniform(-4.7, 4.7),    # Kenya latitude range
                    srid=4326
                ),
                status=random.choices(
                    status_choices,
                    weights=[0.7, 0.1, 0.1, 0.1],  # 70% active, 10% each for others
                    k=1
                )[0],
                battery_level=random.randint(0, 100),
                signal_strength=random.randint(-120, -50),
                firmware_version=f'1.{random.randint(0, 5)}.{random.randint(0, 9)}',
                notes=f'Sample field device {i + 1}',
                installed_by=random.choice(users),
                installation_date=timezone.now() - timedelta(days=random.randint(1, 365)),
            )
            devices.append(device)
            
        self.stdout.write(self.style.SUCCESS(f'Created {len(devices)} field devices'))
        return devices

    def generate_climate_data(self, stations, days, users):
        """Generate climate data for stations"""
        now = timezone.now()
        start_date = now - timedelta(days=days)
        
        for station in stations:
            # Create a data upload record
            upload = FieldDataUpload.objects.create(
                title=f'Initial data import for {station.name}',
                description=f'Automatically generated sample data',
                data_format='generated',
                status='completed',
                created_by=random.choice(users),
            )
            
            # Generate data points
            current_date = start_date
            while current_date <= now:
                # Generate data for each hour
                for hour in range(24):
                    timestamp = current_date + timedelta(hours=hour)
                    
                    # Create climate data
                    ClimateData.objects.create(
                        station=station,
                        timestamp=timestamp,
                        temperature=random.uniform(10, 35),  # Typical temperature range in Kenya
                        humidity=random.uniform(30, 90),      # Typical humidity range
                        precipitation=random.uniform(0, 10) if random.random() > 0.7 else 0,  # 30% chance of rain
                        wind_speed=random.uniform(0, 20),     # Wind speed in km/h
                        wind_direction=random.uniform(0, 360),  # Wind direction in degrees
                        barometric_pressure=random.uniform(950, 1050),  # Pressure in hPa
                        data_quality=random.choice(['high', 'medium', 'high', 'high']),  # Mostly high quality
                        data_source='station',
                        notes=f'Sample data for {timestamp}',
                    )
                    
                    # Create field data records for some devices
                    if random.random() > 0.8:  # 20% chance per hour
                        device = random.choice(station.field_devices.all())
                        FieldDataRecord.objects.create(
                            upload=upload,
                            device=device,
                            device_id=device.device_id,
                            timestamp=timestamp,
                            latitude=device.location.y,
                            longitude=device.location.x,
                            location=device.location,
                            data={
                                'temperature': random.uniform(10, 35),
                                'humidity': random.uniform(30, 90),
                                'battery': random.uniform(3.0, 4.2),
                                'signal': random.randint(-120, -50),
                            },
                            processed=True,
                        )
                
                current_date += timedelta(days=1)
                
            self.stdout.write(self.style.SUCCESS(f'Generated climate data for {station.name}'))
