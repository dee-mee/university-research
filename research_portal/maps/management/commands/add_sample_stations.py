from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from maps.models import WeatherStation, ClimateData
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Adds sample weather stations and climate data for Western Kenya'

    def handle(self, *args, **options):
        # Sample stations data for Western Kenya
        stations = [
            # Kisumu Area
            {
                'name': 'Kisumu Central Station',
                'description': 'Main weather monitoring station in Kisumu City',
                'latitude': -0.0917,
                'longitude': 34.7680,
                'altitude': 1131,
                'region': 'kisumu'
            },
            {
                'name': 'Kisumu Airport Station',
                'description': 'Weather monitoring at Kisumu International Airport',
                'latitude': -0.0864,
                'longitude': 34.7289,
                'altitude': 1157,
                'region': 'kisumu'
            },
            # Lake Victoria Area
            {
                'name': 'Lake Victoria Station',
                'description': 'Lakeside monitoring station',
                'latitude': -0.1500,
                'longitude': 34.0000,
                'altitude': 1135,
                'region': 'lake'
            },
            {
                'name': 'Rusinga Island Station',
                'description': 'Island weather monitoring station',
                'latitude': -0.3667,
                'longitude': 34.1667,
                'altitude': 1140,
                'region': 'lake'
            },
            # Siaya Area
            {
                'name': 'Siaya Town Station',
                'description': 'Central Siaya weather monitoring',
                'latitude': 0.0612,
                'longitude': 34.2881,
                'altitude': 1348,
                'region': 'siaya'
            },
            {
                'name': 'Bondo Station',
                'description': 'Bondo area weather monitoring',
                'latitude': 0.0987,
                'longitude': 34.2809,
                'altitude': 1257,
                'region': 'siaya'
            },
            # Vihiga Area
            {
                'name': 'Vihiga Central Station',
                'description': 'Main Vihiga weather station',
                'latitude': 0.0171,
                'longitude': 34.7221,
                'altitude': 1750,
                'region': 'vihiga'
            },
            {
                'name': 'Mbale Station',
                'description': 'Mbale area monitoring station',
                'latitude': 0.0415,
                'longitude': 34.7208,
                'altitude': 1680,
                'region': 'vihiga'
            }
        ]

        # First, clear existing data
        WeatherStation.objects.all().delete()
        ClimateData.objects.all().delete()

        for station_data in stations:
            station = WeatherStation.objects.create(
                name=station_data['name'],
                description=station_data['description'],
                location=Point(station_data['longitude'], station_data['latitude']),
                altitude=station_data['altitude'],
                is_active=True,
                date_installed=timezone.now().date() - timedelta(days=random.randint(30, 365))
            )
            
            self.stdout.write(self.style.SUCCESS(f'Created station: {station.name}'))
            
            # Add climate data for the past week with regional variations
            for i in range(7):
                for hour in range(0, 24, 3):  # Data every 3 hours
                    timestamp = timezone.now() - timedelta(days=i, hours=hour)
                    
                    # Base temperature varies by region and time of day
                    base_temp = self.get_regional_temperature(
                        station_data['region'],
                        hour,
                        station_data['altitude']
                    )
                    
                    # Add some random variation
                    temp_variation = random.uniform(-2, 2)
                    
                    ClimateData.objects.create(
                        station=station,
                        timestamp=timestamp,
                        temperature=base_temp + temp_variation,
                        humidity=self.get_regional_humidity(station_data['region'], hour),
                        precipitation=self.get_regional_precipitation(station_data['region']),
                        air_quality_index=random.randint(30, 150),
                        wind_speed=random.uniform(0, 15),
                        wind_direction=random.uniform(0, 360),
                        barometric_pressure=random.uniform(980, 1020),
                        cloud_cover=random.uniform(0, 100),
                        soil_moisture=random.uniform(20, 80),
                        water_level=random.uniform(0, 5) if station_data['region'] == 'lake' else 0,
                        data_quality='high',
                        uv_index=self.get_uv_index(hour)
                    )

    def get_regional_temperature(self, region, hour, altitude):
        # Temperature varies by region, time of day, and altitude
        time_factor = 1 - abs(hour - 14) / 14  # Peak at 2 PM
        altitude_factor = (altitude - 1100) / 1000  # Temperature decrease with altitude
        
        base_temps = {
            'lake': 28,
            'kisumu': 27,
            'siaya': 26,
            'vihiga': 24
        }
        
        base = base_temps.get(region, 25)
        return base + (5 * time_factor) - (6 * altitude_factor)

    def get_regional_humidity(self, region, hour):
        # Humidity varies by region and time of day
        base_humidity = {
            'lake': 75,
            'kisumu': 65,
            'siaya': 60,
            'vihiga': 70
        }
        
        # Higher humidity at night and early morning
        time_factor = 1 + (0.2 if hour < 6 or hour > 18 else 0)
        base = base_humidity.get(region, 65)
        return min(95, base * time_factor + random.uniform(-5, 5))

    def get_regional_precipitation(self, region):
        # Precipitation chance and amount varies by region
        if random.random() > 0.7:  # 30% chance of rain
            base_precip = {
                'lake': 15,
                'kisumu': 12,
                'siaya': 10,
                'vihiga': 18
            }
            return random.uniform(0, base_precip.get(region, 10))
        return 0

    def get_uv_index(self, hour):
        # UV index varies by time of day
        if 6 <= hour <= 18:  # Daylight hours
            base = 10 * (1 - abs(hour - 12) / 6)  # Peak at noon
            return max(0, min(11, base + random.uniform(-1, 1)))
        return 0 