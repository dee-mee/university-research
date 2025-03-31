import os
import django
from django.core.files import File
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')
django.setup()

from data_repository.models import Dataset, DatasetVersion

def update_dataset_9():
    # Create test data file
    with open('test_data_9.txt', 'w') as f:
        f.write("This is test data for dataset 9")
    
    # Get dataset and user
    dataset = Dataset.objects.get(id=9)
    User = get_user_model()
    user = User.objects.first()
    
    # Create new version
    with open('test_data_9.txt', 'rb') as f:
        file_size = f.seek(0, 2)  # Get file size
        f.seek(0)  # Reset file pointer to beginning
        version = DatasetVersion.objects.create(
            dataset=dataset,
            version_number=1,
            description='Test version with file',
            is_current=True,
            file_path=File(f),
            file_size=file_size,
            created_by=user
        )
    
    # Set previous versions as not current
    DatasetVersion.objects.filter(dataset=dataset).exclude(id=version.id).update(is_current=False)
    
    print(f'Created new version {version.id} with file')

if __name__ == '__main__':
    update_dataset_9() 