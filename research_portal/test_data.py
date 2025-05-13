#!/usr/bin/env python
"""
Test Data Generator for Research Portal
---------------------------------------
This script generates realistic test data for the research portal:
- Creates Dataset Categories (if they don't exist)
- Creates test users (if specified)
- Generates test datasets with appropriate metadata
- Creates dataset versions with mock files
- Sets up relationships between entities
"""

import os
import sys
import random
import datetime
import json
import io
from pathlib import Path
from tempfile import mkdtemp

# Setup Django environment before any other imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')

# Check for Python 3.13+ and create the compatibility module if needed
try:
    import cgi
except ImportError:
    print("Python 3.13+ detected: Creating and loading cgi compatibility layer")
    if not os.path.exists(os.path.join(sys.path[0], 'compat_cgi.py')):
        print("The compat_cgi.py file is missing. Please create it first.")
        sys.exit(1)
    import compat_cgi
    sys.modules['cgi'] = compat_cgi
    print("Successfully loaded cgi compatibility module")

# Now continue with other imports
try:
    import numpy as np
    from faker import Faker
    import pandas as pd
    import netCDF4 as nc
except ImportError as e:
    print(f"ERROR: Missing required package: {e}")
    print("Please install required packages with: pip install numpy faker pandas netCDF4 tqdm")
    sys.exit(1)

from tqdm import tqdm

# Now initialize Django
try:
    import django
    django.setup()
except Exception as e:
    print(f"ERROR: Failed to initialize Django: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Import Django-specific modules
try:
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from django.core.files import File
    from django.db import transaction, IntegrityError
    from django.core.exceptions import ValidationError
    
    from data_repository.models import (
        Dataset, 
        DatasetCategory, 
        DatasetVersion, 
        DatasetAccess
    )
except Exception as e:
    print(f"ERROR: Failed to import Django modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Initialize Faker
fake = Faker()
User = get_user_model()

# Configuration
NUM_DATASETS = 100  # Reduced from 10000 for testing
SIMULATION_ROUNDS = ['ISIMIP2a', 'ISIMIP2b', 'ISIMIP3a', 'ISIMIP3b']
IMPACT_MODELS = ['WATERGAP', 'LPJmL', 'CLM4.5', 'H08', 'MPI-HM', 'PCR-GLOBWB', 'DBH']
CLIMATE_MODELS = ['GFDL-ESM2M', 'HadGEM2-ES', 'IPSL-CM5A-LR', 'MIROC5']
CLIMATE_SCENARIOS = ['historical', 'rcp26', 'rcp60', 'rcp85', 'ssp126', 'ssp370', 'ssp585']
VARIABLES = [
    'temperature', 'precipitation', 'discharge', 'evapotranspiration', 'soil_moisture',
    'groundwater', 'runoff', 'humidity', 'wind_speed', 'solar_radiation',
    'forest_cover', 'crop_yield', 'irrigation', 'water_demand', 'water_stress'
]
TIME_RESOLUTIONS = ['hourly', 'daily', 'monthly', 'yearly']
LICENSE_TYPES = ['open', 'restricted']

def create_categories():
    """Create dataset categories if they don't exist"""
    categories = [
        {'name': 'Hydrology', 'description': 'Hydrological data including streamflow, runoff, etc.'},
        {'name': 'Climate', 'description': 'Climate data including temperature, precipitation, etc.'},
        {'name': 'Agriculture', 'description': 'Agricultural data including crop yields, irrigation, etc.'},
        {'name': 'Forestry', 'description': 'Forestry data including forest cover, biomass, etc.'},
        {'name': 'Energy', 'description': 'Energy data including demand, production, etc.'},
        {'name': 'Water Resources', 'description': 'Water resources data including demand, stress, etc.'},
        {'name': 'Biodiversity', 'description': 'Biodiversity data including species distribution, etc.'},
        {'name': 'Socioeconomic', 'description': 'Socioeconomic data including population, GDP, etc.'},
    ]
    
    created_categories = []
    for category in categories:
        try:
            obj, created = DatasetCategory.objects.get_or_create(
                name=category['name'],
                defaults={"description": category['description']}
            )
            if created:
                print(f"Created category: {category['name']}")
            created_categories.append(obj)
        except IntegrityError:
            print(f"Category {category['name']} already exists, skipping...")
        except Exception as e:
            print(f"Error creating category {category['name']}: {str(e)}")
    
    if not created_categories:
        raise ValueError("No categories were created or found")
    
    print(f"✅ Created/verified {len(created_categories)} categories")
    return created_categories

def create_test_users(num_users=5):
    """Create test users if they don't exist"""
    users = []
    for i in range(1, num_users + 1):
        try:
            username = f"testuser{i}"
            email = f"testuser{i}@example.com"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "is_active": True
                }
            )
            if created:
                user.set_password("password123")
                user.save()
            users.append(user)
        except Exception as e:
            print(f"Error creating user {username}: {str(e)}")
    
    # Make sure we have at least one superuser
    try:
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "first_name": "Admin",
                "last_name": "User"
            }
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
        users.append(admin_user)
    except Exception as e:
        print(f"Error creating admin user: {str(e)}")
    
    if not users:
        raise ValueError("No users were created")
    
    print(f"✅ Created/verified {len(users)} users")
    return users

def generate_time_series_data(start_date, end_date, resolution, variable_name):
    """Generate mock time series data based on the variable and resolution"""
    try:
        # Create date range based on resolution
        if resolution == 'hourly':
            date_range = pd.date_range(start=start_date, end=end_date, freq='h')
        elif resolution == 'daily':
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        elif resolution == 'monthly':
            date_range = pd.date_range(start=start_date, end=end_date, freq='ME')
        else:  # yearly
            date_range = pd.date_range(start=start_date, end=end_date, freq='YE')
        
        # Generate values based on variable type
        n = len(date_range)
        seasonal = np.sin(np.linspace(0, 12*np.pi, n))
        trend = np.linspace(0, 2, n)
        noise = np.random.normal(0, 0.5, n)
        
        if 'temperature' in variable_name:
            base = 15 + 10 * seasonal + trend + noise
        elif 'precipitation' in variable_name:
            base = np.maximum(0, 5 * seasonal + trend + noise)
        elif 'discharge' in variable_name or 'runoff' in variable_name:
            base = np.maximum(0, 100 * seasonal + 20 * trend + 10 * noise)
        else:
            base = 50 + 25 * seasonal + 5 * trend + 10 * noise
        
        return pd.DataFrame({
            'date': date_range,
            variable_name: base
        })
    except Exception as e:
        print(f"Error generating time series data: {str(e)}")
        raise

def create_mock_dataset_file(dataset, version, format_type='netCDF'):
    """Create a mock dataset file based on the specified format"""
    try:
        # Create a temporary directory for file generation
        temp_dir = Path(mkdtemp())
        
        variables = random.sample(VARIABLES, random.randint(1, 5))
        start_date = fake.date_between(start_date='-10y', end_date='-5y')
        end_date = fake.date_between(start_date='-5y', end_date='-1y')
        resolution = random.choice(TIME_RESOLUTIONS)
        
        filename = f"dataset_{dataset.id}_v{version.version_number}"
        file_path = temp_dir / filename
        
        # Generate time series data for each variable
        all_data = {}
        for var in variables:
            all_data[var] = generate_time_series_data(start_date, end_date, resolution, var)
        
        if format_type == 'netCDF':
            file_path = file_path.with_suffix('.nc')
            with nc.Dataset(file_path, 'w', format='NETCDF4') as ds:
                time_dim = ds.createDimension('time', None)
                times = ds.createVariable('time', 'f8', ('time',))
                times.units = f'days since {start_date}'
                times.calendar = 'standard'
                
                dates = all_data[variables[0]]['date']
                time_values = [(date - pd.to_datetime(start_date)).total_seconds() / (24 * 60 * 60) for date in dates]
                times[:] = time_values
                
                for var_name in variables:
                    var_data = all_data[var_name][var_name].values
                    var = ds.createVariable(var_name, 'f4', ('time',))
                    var.units = get_variable_units(var_name)
                    var.long_name = var_name.replace('_', ' ').title()
                    var[:] = var_data
        
        elif format_type == 'CSV':
            file_path = file_path.with_suffix('.csv')
            merged_df = all_data[variables[0]][['date']]
            for var in variables:
                merged_df[var] = all_data[var][var]
            merged_df.to_csv(file_path, index=False)
        
        else:  # Default to JSON
            file_path = file_path.with_suffix('.json')
            json_data = {
                'dataset_info': {
                    'title': dataset.title,
                    'id': dataset.id,
                    'version': version.version_number,
                    'created_at': str(version.created_at),
                    'variables': variables,
                    'start_date': str(start_date),
                    'end_date': str(end_date),
                    'resolution': resolution
                },
                'data': {
                    var: {
                        'times': [str(d) for d in all_data[var]['date'].tolist()],
                        'values': all_data[var][var].tolist()
                    } for var in variables
                }
            }
            with open(file_path, 'w') as f:
                json.dump(json_data, f, indent=2)
        
        return file_path, variables, start_date, end_date, resolution
    except Exception as e:
        print(f"Error creating mock dataset file: {str(e)}")
        raise

def get_variable_units(variable_name):
    """Return appropriate units for each variable type"""
    units = {
        'temperature': 'degC',
        'precipitation': 'mm/day',
        'discharge': 'm3/s',
        'evapotranspiration': 'mm/day',
        'soil_moisture': 'kg/m2',
        'groundwater': 'm',
        'runoff': 'mm/day',
        'humidity': '%',
        'wind_speed': 'm/s',
        'solar_radiation': 'W/m2',
        'forest_cover': '%',
        'crop_yield': 't/ha',
        'irrigation': 'mm/day',
        'water_demand': 'm3/s',
        'water_stress': 'index'
    }
    return units.get(variable_name, 'dimensionless')

@transaction.atomic
def create_dataset_with_version(user, category, idx):
    """Create a dataset with an initial version"""
    try:
        # Generate dataset metadata
        base_title = f"{random.choice(['Climate', 'Hydrology', 'Agriculture', 'Water'])} {fake.bs()}"
        title = base_title[:245]  # Leave room for other fields
        
        description = fake.paragraph(nb_sentences=5)
        simulation_round = random.choice(SIMULATION_ROUNDS)
        impact_model = random.choice(IMPACT_MODELS)
        climate_forcing = random.choice(CLIMATE_MODELS)
        climate_scenario = random.choice(CLIMATE_SCENARIOS)
        
        isimip_id = f"ISIMIP-{simulation_round}-{impact_model}-{idx}"
        if len(isimip_id) > 50:
            isimip_id = isimip_id[:50]
        
        dataset = Dataset.objects.create(
            title=title,
            description=description,
            category=category,
            created_by=user,
            status='published',
            published_at=timezone.now(),
            is_featured=random.random() < 0.1,
            simulation_round=simulation_round[:50] if simulation_round else None,
            impact_model=impact_model[:50] if impact_model else None,
            climate_forcing=climate_forcing[:50] if climate_forcing else None,
            climate_scenario=climate_scenario[:50] if climate_scenario else None,
            time_step=random.choice(TIME_RESOLUTIONS),
            period=f"{random.randint(1950, 2000)}-{random.randint(2001, 2100)}",
            isimip_id=isimip_id
        )
        
        # Create initial version
        version = DatasetVersion(
            dataset=dataset,
            version_number="1.0.0",
            description=f"Initial version of {title}",
            created_by=user,
            is_current=True
        )
        
        # Create and attach mock file
        file_format = random.choice(['netCDF', 'CSV', 'JSON'])
        mock_file_path, variables, start_date, end_date, resolution = create_mock_dataset_file(
            dataset, version, file_format
        )
        
        with open(mock_file_path, 'rb') as f:
            version.file_path.save(
                os.path.basename(mock_file_path),
                File(f),
                save=False
            )
        
        # Add metadata
        metadata = {
            'time_start': start_date.isoformat(),
            'time_end': end_date.isoformat(),
            'time_resolution': resolution,
            'variables': variables,
            'format': file_format,
            'source': fake.url(),
            'contact': fake.email(),
            'license': random.choice(LICENSE_TYPES),
            'citation': f"{fake.name()} et al. ({start_date.year}). {title}. Journal of {fake.word().capitalize()} Data, {random.randint(1, 100)}({random.randint(1, 12)}), {random.randint(1, 1000)}-{random.randint(1001, 2000)}."
        }
        version.metadata = metadata
        version.save()
        
        # Clean up temp file
        if mock_file_path.exists():
            mock_file_path.unlink()
        
        # For some datasets, add a second version
        if random.random() < 0.3:  # 30% chance of having multiple versions
            second_version = DatasetVersion(
                dataset=dataset,
                version_number="1.1.0",
                description=f"Updated version with improvements to {random.choice(variables)}",
                created_by=user,
                is_current=True
            )
            
            mock_file_path, variables, start_date, end_date, resolution = create_mock_dataset_file(
                dataset, second_version, file_format
            )
            
            with open(mock_file_path, 'rb') as f:
                second_version.file_path.save(
                    os.path.basename(mock_file_path),
                    File(f),
                    save=False
                )
            
            metadata['time_end'] = end_date.isoformat()
            metadata['variables'] = variables
            metadata['version_changes'] = f"Improved {random.choice(variables)} calculations and extended time range."
            second_version.metadata = metadata
            second_version.save()
            
            version.is_current = False
            version.save()
            
            if mock_file_path.exists():
                mock_file_path.unlink()
        
        return dataset
    except Exception as e:
        print(f"Error creating dataset: {str(e)}")
        raise

@transaction.atomic
def generate_test_data():
    """Main function to generate the test datasets"""
    try:
        # Add support for specifying a smaller number of datasets via command line
        if len(sys.argv) > 1 and sys.argv[1].isdigit():
            num_datasets = int(sys.argv[1])
            print(f"Using command line specified count: {num_datasets} datasets")
        else:
            num_datasets = NUM_DATASETS
        
        print(f"🚀 Starting test data generation: {num_datasets} datasets")
        
        # Create categories
        categories = create_categories()
        
        # Create users
        users = create_test_users()
        
        # Generate datasets
        datasets = []
        print(f"⏳ Generating {num_datasets} datasets with versions...")
        
        # Process in batches to prevent memory issues
        batch_size = 10
        for batch_start in range(0, num_datasets, batch_size):
            batch_end = min(batch_start + batch_size, num_datasets)
            print(f"Processing batch {batch_start+1} to {batch_end}")
            
            for i in tqdm(range(batch_start, batch_end)):
                user = random.choice(users)
                category = random.choice(categories)
                
                try:
                    dataset = create_dataset_with_version(user, category, i)
                    datasets.append(dataset)
                except Exception as e:
                    print(f"Error creating dataset {i}: {str(e)}")
                    continue
        
        print(f"✅ Successfully created {len(datasets)} datasets")
        
        # Print summary
        print("\n===== DATA GENERATION SUMMARY =====")
        print(f"Total datasets created: {len(datasets)}")
        print(f"Categories used: {', '.join(c.name for c in categories)}")
        print(f"Users created: {len(users)}")
        
        total_versions = DatasetVersion.objects.count()
        print(f"Total versions created: {total_versions}")
        
        print("\nDatasets by category:")
        for category in categories:
            count = Dataset.objects.filter(category=category).count()
            print(f"  - {category.name}: {count}")
        
        print("\n✨ Test data generation complete! ✨")
        print("You can now test the application with these sample datasets.")
        
    except Exception as e:
        print(f"Error in test data generation: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        generate_test_data()
    except Exception as e:
        print(f"Script failed: {str(e)}")
        sys.exit(1)
