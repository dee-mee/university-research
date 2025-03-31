import os
import django
from django.core.files import File
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')
django.setup()

from data_repository.models import Dataset, DatasetVersion

def add_dataset_version():
    # Get the existing dataset
    dataset = Dataset.objects.get(id=10)  # Test Climate Dataset
    
    # Get the first user (for demonstration)
    User = get_user_model()
    user = User.objects.first()
    
    # Update dataset metadata
    dataset.path = "/data/ISIMIP3b/OutputData/water_global/WATERGAP2-4c/gfdl-esm4/historical/histsoc"
    dataset.isimip_id = "ISIMIP3b_water_global_WATERGAP2-4c_gfdl-esm4_historical_histsoc_2015"
    dataset.simulation_round = "ISIMIP3b"
    dataset.impact_model = "WATERGAP2-4c"
    dataset.climate_forcing = "GFDL-ESM4"
    dataset.climate_scenario = "historical"
    dataset.data_product = "OutputData"
    dataset.bias_adjustment = "v2.1"
    dataset.time_step = "daily"
    dataset.period = "1850-2014"
    dataset.publication = "https://doi.org/10.48364/ISIMIP.842396.1"
    dataset.save()
    
    # Create a new version with the test file
    with open('test_data.csv', 'rb') as f:
        file_size = f.seek(0, 2)  # Get file size
        f.seek(0)  # Reset file pointer to beginning
        version = DatasetVersion.objects.create(
            dataset=dataset,
            version_number=2,  # Increment version number
            description='Updated version with more detailed data',
            is_current=True,
            file_path=File(f),
            file_size=file_size,
            created_by=user
        )
        # Set previous versions as not current
        DatasetVersion.objects.filter(dataset=dataset).exclude(id=version.id).update(is_current=False)
    
    print(f'Added version {version.version_number} to dataset: {dataset.title}')
    print(f'Version ID: {version.id}')
    print(f'Updated dataset metadata successfully')

if __name__ == '__main__':
    add_dataset_version() 