#!/usr/bin/env python
"""
Test Data Generator for Research Portal
---------------------------------------
This script generates realistic test data for the research portal:
- Creates Dataset Categories (if they don't exist)
- Creates test users (if specified)
- Generates 1000 test datasets with appropriate metadata
- Creates dataset versions with mock files
- Sets up relationships between entities
"""

import os
import sys
import random
import datetime
import json
import io

# Setup Django environment before any other imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')

# Check for Python 3.13+ and create the compatibility module if needed
try:
    import cgi
except ImportError:
    print("Python 3.13+ detected: Creating and loading cgi compatibility layer")
    # Import directly from the module we've already created
    # First check if the module exists, if not we'll use the standalone script
    if not os.path.exists(os.path.join(sys.path[0], 'compat_cgi.py')):
        print("The compat_cgi.py file is missing. Please create it first.")
        sys.exit(1)
    
    # Import our compatibility module
    import compat_cgi
    
    # Replace the cgi module in sys.modules
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

from pathlib import Path
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
NUM_DATASETS = 10000  # You can adjust this for testing
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
        obj, created = DatasetCategory.objects.get_or_create(
            name=category['name'],
            defaults={"description": category['description']}
        )
        created_categories.append(obj)
    
    print(f"✅ Created/verified {len(created_categories)} categories")
    return created_categories

def create_test_users(num_users=5):
    """Create test users if they don't exist"""
    users = []
    for i in range(1, num_users + 1):
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
    
    # Make sure we have at least one superuser
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
    
    print(f"✅ Created/verified {len(users)} users")
    return users

def generate_time_series_data(start_date, end_date, resolution, variable_name):
    """Generate mock time series data based on the variable and resolution"""
    # Create date range based on resolution
    if resolution == 'hourly':
        # Fix deprecated 'H' frequency to use 'h' instead 
        date_range = pd.date_range(start=start_date, end=end_date, freq='h')
    elif resolution == 'daily':
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    elif resolution == 'monthly':
        # Fix deprecated 'M' frequency to use 'ME' instead
        date_range = pd.date_range(start=start_date, end=end_date, freq='ME')
    else:  # yearly
        # Fix deprecated 'Y' frequency to use 'YE' instead
        date_range = pd.date_range(start=start_date, end=end_date, freq='YE')
    
    # Generate values based on variable type (with some randomness and trends)
    n = len(date_range)
    
    # Base signal: seasonal component + trend + noise
    seasonal = np.sin(np.linspace(0, 12*np.pi, n))  # Seasonal pattern
    trend = np.linspace(0, 2, n)  # Increasing trend
    noise = np.random.normal(0, 0.5, n)  # Random noise
    
    if 'temperature' in variable_name:
        base = 15 + 10 * seasonal + trend + noise  # Temperature typically between 5-27°C
    elif 'precipitation' in variable_name:
        base = np.maximum(0, 5 * seasonal + trend + noise)  # Precipitation can't be negative
    elif 'discharge' in variable_name or 'runoff' in variable_name:
        base = np.maximum(0, 100 * seasonal + 20 * trend + 10 * noise)
    else:
        base = 50 + 25 * seasonal + 5 * trend + 10 * noise
    
    # Create the DataFrame
    df = pd.DataFrame({
        'date': date_range,
        variable_name: base
    })
    
    return df

def create_mock_dataset_file(dataset, version, format_type='netCDF'):
    """Create a mock dataset file based on the specified format"""
    variables = random.sample(VARIABLES, random.randint(1, 5))
    start_date = fake.date_between(start_date='-10y', end_date='-5y')
    end_date = fake.date_between(start_date='-5y', end_date='-1y')
    resolution = random.choice(TIME_RESOLUTIONS)
    
    # Use version number directly without replacing dots since it's already a string
    filename = f"dataset_{dataset.id}_v{version.version_number}"
    file_path = Path(f"/tmp/{filename}")
    
    # Generate time series data for each variable
    all_data = {}
    for var in variables:
        all_data[var] = generate_time_series_data(start_date, end_date, resolution, var)
    
    if format_type == 'netCDF':
        # Create a netCDF file with the data
        filename += ".nc"
        file_path = Path(f"/tmp/{filename}")
        
        # Create the netCDF file
        with nc.Dataset(file_path, 'w', format='NETCDF4') as ds:
            # Create dimensions
            time_dim = ds.createDimension('time', None)
            
            # Create time variable
            times = ds.createVariable('time', 'f8', ('time',))
            times.units = f'days since {start_date}'
            times.calendar = 'standard'
            
            # Add time values (days since start_date)
            dates = all_data[variables[0]]['date']
            time_values = [(date - pd.to_datetime(start_date)).total_seconds() / (24 * 60 * 60) for date in dates]
            times[:] = time_values
            
            # Create variables and add data
            for var_name in variables:
                var_data = all_data[var_name][var_name].values
                var = ds.createVariable(var_name, 'f4', ('time',))
                var.units = get_variable_units(var_name)
                var.long_name = var_name.replace('_', ' ').title()
                var[:] = var_data
    
    elif format_type == 'CSV':
        # Create a CSV file with the data
        filename += ".csv"
        file_path = Path(f"/tmp/{filename}")
        
        # Merge all variable data frames
        merged_df = all_data[variables[0]][['date']]
        for var in variables:
            merged_df[var] = all_data[var][var]
        
        # Save to CSV
        merged_df.to_csv(file_path, index=False)
    
    else:  # Default to JSON
        filename += ".json"
        file_path = Path(f"/tmp/{filename}")
        
        # Create a JSON structure
        json_data = {'dataset_info': {
            'title': dataset.title,
            'id': dataset.id,
            'version': version.version_number,
            'created_at': str(version.created_at),
            'variables': variables,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'resolution': resolution
        }}
        
        # Add data for each variable
        json_data['data'] = {}
        for var in variables:
            df = all_data[var]
            json_data['data'][var] = {
                'times': [str(d) for d in df['date'].tolist()],
                'values': df[var].tolist()
            }
        
        # Save to JSON
        with open(file_path, 'w') as f:
            json.dump(json_data, f, indent=2)
    
    return file_path, variables, start_date, end_date, resolution

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

def create_dataset_with_version(user, category, idx):
    """Create a dataset with an initial version"""
    # Generate dataset metadata
    # Limit title length to ensure it doesn't exceed the database field constraints
    base_title = f"{random.choice(['Climate', 'Hydrology', 'Agriculture', 'Water'])} {fake.bs()}"
    title = base_title[:245]  # Leave some room for other fields
    
    description = fake.paragraph(nb_sentences=5)
    simulation_round = random.choice(SIMULATION_ROUNDS)
    impact_model = random.choice(IMPACT_MODELS)
    climate_forcing = random.choice(CLIMATE_MODELS)
    climate_scenario = random.choice(CLIMATE_SCENARIOS)
    
    # Create a shorter isimip_id to prevent it from exceeding 50 chars
    isimip_id = f"ISIMIP-{simulation_round}-{impact_model}-{idx}"
    if len(isimip_id) > 50:
        # Truncate if needed to fit within the 50 char limit
        isimip_id = isimip_id[:50]
    
    # Create dataset with proper length constraints
    dataset = Dataset.objects.create(
        title=title,
        description=description,
        category=category,
        created_by=user,
        status='published',
        published_at=timezone.now(),
        is_featured=random.random() < 0.1,  # 10% chance of being featured
        simulation_round=simulation_round[:50] if simulation_round else None,  # Add length constraints
        impact_model=impact_model[:50] if impact_model else None,
        climate_forcing=climate_forcing[:50] if climate_forcing else None,
        climate_scenario=climate_scenario[:50] if climate_scenario else None,
        time_step=random.choice(TIME_RESOLUTIONS),
        period=f"{random.randint(1950, 2000)}-{random.randint(2001, 2100)}",
        isimip_id=isimip_id
    )
    
    # Create initial version - now using string versions since we fixed the schema
    version = DatasetVersion(
        dataset=dataset,
        version_number="1.0.0",  # Schema is now varchar so this will work
        description=f"Initial version of {title}",
        created_by=user,
        is_current=True
    )
    
    # Create a mock file and attach it to the version
    file_format = random.choice(['netCDF', 'CSV', 'JSON'])
    mock_file_path, variables, start_date, end_date, resolution = create_mock_dataset_file(
        dataset, version, file_format
    )
    
    # Open the file and attach it to the version
    with open(mock_file_path, 'rb') as f:
        version.file_path.save(
            os.path.basename(mock_file_path),
            django.core.files.File(f),
            save=False
        )
    
    # Add metadata about time series
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
    
    # Delete the temp file
    if os.path.exists(mock_file_path):
        os.remove(mock_file_path)
    
    # For some datasets, add a second version
    if random.random() < 0.3:  # 30% chance of having multiple versions
        second_version = DatasetVersion(
            dataset=dataset,
            version_number="1.1.0",  # Schema is now varchar so this will work
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
                django.core.files.File(f),
                save=False
            )
        
        # Update metadata for the new version
        metadata['time_end'] = end_date.isoformat()  # Extend the time range
        metadata['variables'] = variables  # Maybe some different variables
        metadata['version_changes'] = f"Improved {random.choice(variables)} calculations and extended time range."
        second_version.metadata = metadata
        second_version.save()
        
        # Update old version to not be current
        version.is_current = False
        version.save()
        
        # Delete the temp file
        if os.path.exists(mock_file_path):
            os.remove(mock_file_path)
    
    return dataset

def generate_test_data():
    """Main function to generate the test datasets"""
    
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
    
    # Allow batch sizes to prevent memory issues with large numbers
    batch_size = 100
    for batch_start in range(0, num_datasets, batch_size):
        batch_end = min(batch_start + batch_size, num_datasets)
        print(f"Processing batch {batch_start+1} to {batch_end}")
        
        for i in tqdm(range(batch_start, batch_end)):
            # Select a random user and category
            user = random.choice(users)
            category = random.choice(categories)
            
            try:
                dataset = create_dataset_with_version(user, category, i)
                datasets.append(dataset)
            except Exception as e:
                print(f"Error creating dataset {i}: {str(e)}")
                import traceback
                traceback.print_exc()
    
    print(f"✅ Successfully created {len(datasets)} datasets")
    
    # Print summary information
    print("\n===== DATA GENERATION SUMMARY =====")
    print(f"Total datasets created: {len(datasets)}")
    print(f"Categories used: {', '.join(c.name for c in categories)}")
    print(f"Users created: {len(users)}")
    
    # Count versions
    total_versions = DatasetVersion.objects.count()
    print(f"Total versions created: {total_versions}")
    
    # Count by category
    print("\nDatasets by category:")
    for category in categories:
        count = Dataset.objects.filter(category=category).count()
        print(f"  - {category.name}: {count}")
    
    print("\n✨ Test data generation complete! ✨")
    print("You can now test the application with these sample datasets.")

def check_version_field_type():
    """Check if version_number is actually an integer in the database despite model definition"""
    # First, try a direct database query to see the actual column type
    print("Checking database schema for version_number field...")
    try:
        with django.db.connection.cursor() as cursor:
            table_name = DatasetVersion._meta.db_table
            cursor.execute(f"""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}' AND column_name = 'version_number'
            """)
            result = cursor.fetchone()
            if result:
                column_type = result[0]
                print(f"Database column type for version_number: {column_type}")
                # Return True for any type other than integer/bigint (character varying, text, etc.)
                return column_type != 'integer' and column_type != 'bigint'
    except Exception as e:
        print(f"Could not check database schema: {e}")
    
    # If we can't determine the type from the schema, try a test save
    print("Testing version field with a sample object...")
    try:
        # Try to save an object with a string version number
        test_dataset = Dataset.objects.first()
        if not test_dataset:
            # If no datasets exist, assume the field is a string (safer option)
            print("No datasets available for testing, assuming version_number is string type")
            return True
            
        # Try saving with a string version and see if it works
        with django.db.transaction.atomic():
            test_version = DatasetVersion(
                dataset=test_dataset,
                version_number="test.version",
                description="Testing version field type",
                created_by=test_dataset.created_by,
                is_current=False
            )
            test_version.save()
            # If we get here without an error, it worked - roll back to avoid creating test data
            raise ValueError("Test transaction, rolling back")
            
    except ValueError as e:
        if str(e) == "Test transaction, rolling back":
            # Our intentional rollback - string type worked
            print("String version numbers are accepted by the database")
            return True
    except django.db.utils.DataError:
        # Got a data error - likely an integer field
        print("Database rejected string version number, using integers instead")
        return False
    except Exception as e:
        print(f"Error testing version field: {e}")
    
    # Default to string if we can't determine
    print("Defaulting to string version numbers")
    return True

# Run check at module load time
VERSION_FIELD_IS_STRING = check_version_field_type()
print(f"Using {'string' if VERSION_FIELD_IS_STRING else 'integer'} type for version_number field")

if __name__ == "__main__":
    try:
        generate_test_data()
    except Exception as e:
        print(f"Error running test data generation: {e}")
        import traceback
        traceback.print_exc()
        print("\nPlease make sure all dependencies are installed:")
        print("pip install faker pandas numpy netCDF4 tqdm")
        sys.exit(1)
