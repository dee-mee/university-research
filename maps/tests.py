from django.test import TestCase
from django.contrib.gis.geos import Point
from .models import WeatherStation, ClimateData
from datetime import datetime, timedelta
import random
import json

class WeatherStationStackTests(TestCase):
    def setUp(self):
        # Create test station
        self.test_station = WeatherStation.objects.create(
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
    
    def test_push_data(self):
        # Test pushing data to stack
        data = {
            "timestamp": datetime.now().isoformat(),
            "temperature": 22.5,
            "humidity": 65.0
        }
        self.assertTrue(self.test_station.push_data(data))
        self.assertEqual(self.test_station.stack_size(), 1)
    
    def test_stack_operations(self):
        # Test push, peek, and pop operations
        data = {
            "timestamp": datetime.now().isoformat(),
            "temperature": 22.5
        }
        self.test_station.push_data(data)
        
        # Test peek
        peek_data = self.test_station.peek_data()
        self.assertEqual(peek_data["temperature"], 22.5)
        self.assertEqual(self.test_station.stack_size(), 1)  # Size unchanged after peek
        
        # Test pop
        pop_data = self.test_station.pop_data()
        self.assertEqual(pop_data["temperature"], 22.5)
        self.assertEqual(self.test_station.stack_size(), 0)  # Size reduced after pop
    
    def test_process_data_stack(self):
        # Generate test data
        for i in range(10):
            data = {
                "timestamp": (datetime.now() + timedelta(hours=i)).isoformat(),
                "temperature": 20.0 + i
            }
            self.test_station.push_data(data)
        
        # Process stack
        initial_count = ClimateData.objects.count()
        processed = self.test_station.process_data_stack()
        self.assertEqual(processed, 10)
        self.assertEqual(ClimateData.objects.count(), initial_count + 10)
        self.assertEqual(self.test_station.stack_size(), 0)
    
    def test_auto_processing(self):
        # Configure auto processing
        self.test_station.auto_process = True
        self.test_station.process_threshold = 5
        self.test_station.save()
        
        # Push data until threshold
        for i in range(6):  # 6 > threshold of 5
            data = {
                "timestamp": (datetime.now() + timedelta(minutes=i)).isoformat(),
                "temperature": 20.0 + i
            }
            self.test_station.push_data(data)
        
        # Stack should be auto-processed once threshold was reached
        self.assertEqual(self.test_station.stack_size(), 0)
        self.assertEqual(ClimateData.objects.filter(station=self.test_station).count(), 6)