import os
import django
from django.core.files import File
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')
django.setup()

from data_repository.models import Dataset, DatasetVersion, DatasetCategory

def create_test_dataset():
    User = get_user_model()
    user = User.objects.first()
    category = DatasetCategory.objects.first()
    
    # Create the dataset with metadata
    dataset = Dataset.objects.create(
        title='Global Water Resources Assessment 2024',
        description='This dataset contains global water resources assessment data for the year 2024, including river discharge, water temperature, and water stress indicators. The data is based on the WATERGAP2-4c model and GFDL-ESM4 climate forcing.',
        category=category,
        created_by=user,
        path='/data/ISIMIP3b/OutputData/water_global/WATERGAP2-4c/gfdl-esm4/historical/histsoc',
        isimip_id='ISIMIP3b_water_global_WATERGAP2-4c_gfdl-esm4_historical_histsoc_2015',
        simulation_round='ISIMIP3b',
        impact_model='WATERGAP2-4c',
        climate_forcing='GFDL-ESM4',
        climate_scenario='historical',
        data_product='OutputData',
        bias_adjustment='v2.1',
        time_step='daily',
        period='1850-2014',
        publication='https://doi.org/10.48364/ISIMIP.842396.1'
    )
    
    # Create a version with the test file
    with open('test_data.csv', 'rb') as f:
        file_size = f.seek(0, 2)  # Get file size
        f.seek(0)  # Reset file pointer to beginning
        version = DatasetVersion.objects.create(
            dataset=dataset,
            version_number=1,
            description='Initial version containing daily water resources data',
            is_current=True,
            file_path=File(f),
            file_size=file_size,
            created_by=user
        )
    
    print(f'Created dataset with ID: {dataset.id}')
    print(f'Created version with ID: {version.id}')

if __name__ == '__main__':
    create_test_dataset() 