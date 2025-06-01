from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from maps.models import WeatherStation
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Adds weather station locations without populating test data'

    def handle(self, *args, **options):
        # Station location data
        stations = [
            # Kisumu Area
            {
                'name': 'Kisumu Central Station',
                'description': 'Main weather monitoring station in Kisumu City',
                'latitude': -0.0917,
                'longitude': 34.7680,
                'altitude': 1131
            },
            {
                'name': 'Kisumu Airport Station',
                'description': 'Weather monitoring at Kisumu International Airport',
                'latitude': -0.0864,
                'longitude': 34.7289,
                'altitude': 1157
            },
            # Lake Victoria Area
            {
                'name': 'Lake Victoria Station',
                'description': 'Lakeside monitoring station',
                'latitude': -0.1500,
                'longitude': 34.0000,
                'altitude': 1135
            },
            {
                'name': 'Rusinga Island Station',
                'description': 'Island weather monitoring station',
                'latitude': -0.3667,
                'longitude': 34.1667,
                'altitude': 1140
            },
            # Siaya Area
            {
                'name': 'Siaya Town Station',
                'description': 'Central Siaya weather monitoring',
                'latitude': 0.0612,
                'longitude': 34.2881,
                'altitude': 1348
            },
            {
                'name': 'Bondo Station',
                'description': 'Bondo area weather monitoring',
                'latitude': 0.0987,
                'longitude': 34.2809,
                'altitude': 1257
            },
            # Vihiga Area
            {
                'name': 'Vihiga Central Station',
                'description': 'Main Vihiga weather station',
                'latitude': 0.0171,
                'longitude': 34.7221,
                'altitude': 1750
            },
            {
                'name': 'Mbale Station',
                'description': 'Mbale area monitoring station',
                'latitude': 0.0415,
                'longitude': 34.7208,
                'altitude': 1680
            }
        ]

        for station_data in stations:
            # Check if station already exists to avoid duplicates
            existing = WeatherStation.objects.filter(name=station_data['name']).first()
            if existing:
                self.stdout.write(self.style.WARNING(f'Station already exists: {station_data["name"]}'))
                continue
                
            station = WeatherStation.objects.create(
                name=station_data['name'],
                description=station_data['description'],
                location=Point(station_data['longitude'], station_data['latitude']),
                altitude=station_data['altitude'],
                is_active=True,
                date_installed=timezone.now().date() - timedelta(days=30)
            )
            
            self.stdout.write(self.style.SUCCESS(f'Created station: {station.name}'))