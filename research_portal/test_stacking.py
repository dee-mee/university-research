from django.core.management.base import BaseCommand
from your_app.models import WeatherStation, ClimateData
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta
import random
import json

class Command(BaseCommand):
    help = 'Test the data stacking functionality of WeatherStation model'

    def handle(self, *args, **options):
        self.stdout.write('Creating test station...')
        
        # Create test station
        test_station = WeatherStation(
            name="Test Station Alpha",
            station_id="TST001",
            description="Test station for stacking functionality",
            location=Point(-122.4194, 37.7749),
            altitude=16.0,
            is_active=True,
            date_installed=datetime.now().date(),
            has_temperature=True,
            has_precipitation=True,
            has_humidity=True,
            has_wind=True,
            max_stack_size=1000,
            auto_process=False,
            process_threshold=100
        )
        test_station.save()
        
        # Add the rest of the test code here
        # ...
        
        self.stdout.write(self.style.SUCCESS('Testing completed!'))