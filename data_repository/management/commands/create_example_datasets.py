from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from data_repository.models import DatasetCategory, Dataset, DatasetVersion, DatasetAccess
from django.core.files.base import ContentFile
from django.conf import settings
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates example datasets and categories for the data repository'

    def handle(self, *args, **kwargs):
        # Create main categories following ISIMIP structure
        categories = {
            'climate': {
                'name': 'Climate Data',
                'description': 'Climate and weather datasets including temperature, precipitation, and other meteorological variables.',
                'order': 1,
                'subcategories': {
                    'gcm': {
                        'name': 'Global Climate Models',
                        'description': 'Outputs from global climate models including CMIP6 data.',
                        'order': 1
                    },
                    'rcm': {
                        'name': 'Regional Climate Models',
                        'description': 'High-resolution regional climate model outputs.',
                        'order': 2
                    }
                }
            },
            'socioeconomic': {
                'name': 'Socioeconomic Data',
                'description': 'Socioeconomic datasets including population, GDP, and other demographic indicators.',
                'order': 2,
                'subcategories': {
                    'population': {
                        'name': 'Population Data',
                        'description': 'Population projections and demographic data.',
                        'order': 1
                    },
                    'economic': {
                        'name': 'Economic Data',
                        'description': 'GDP and economic indicators.',
                        'order': 2
                    }
                }
            },
            'biophysical': {
                'name': 'Biophysical Data',
                'description': 'Biophysical datasets including land use, vegetation, and soil data.',
                'order': 3,
                'subcategories': {
                    'land': {
                        'name': 'Land Use',
                        'description': 'Land use and land cover data.',
                        'order': 1
                    },
                    'water': {
                        'name': 'Water Resources',
                        'description': 'Water availability and hydrological data.',
                        'order': 2
                    }
                }
            }
        }

        created_categories = {}
        created_subcategories = {}

        # Create main categories and their subcategories
        for slug, data in categories.items():
            category, created = DatasetCategory.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': data['name'],
                    'description': data['description'],
                    'order': data['order']
                }
            )
            created_categories[slug] = category
            self.stdout.write(f"{'Created' if created else 'Found'} category: {category.name}")

            # Create subcategories
            for sub_slug, sub_data in data['subcategories'].items():
                subcategory, created = DatasetCategory.objects.get_or_create(
                    slug=f"{slug}-{sub_slug}",
                    parent=category,
                    defaults={
                        'name': sub_data['name'],
                        'description': sub_data['description'],
                        'order': sub_data['order']
                    }
                )
                created_subcategories[f"{slug}-{sub_slug}"] = subcategory
                self.stdout.write(f"{'Created' if created else 'Found'} subcategory: {subcategory.name}")

        # Create example datasets following ISIMIP structure
        example_datasets = [
            {
                'title': 'CMIP6 Global Climate Model Outputs',
                'description': 'High-resolution climate model outputs from the Coupled Model Intercomparison Project Phase 6 (CMIP6), including temperature, precipitation, and other variables.',
                'category': 'climate-gcm',
                'is_featured': True,
                'metadata': {
                    'temporal_coverage': '1850-2100',
                    'spatial_resolution': '0.25° x 0.25°',
                    'variables': ['temperature', 'precipitation', 'humidity', 'wind_speed'],
                    'update_frequency': 'monthly',
                    'model_ensemble': 'CMIP6',
                    'scenarios': ['SSP1-2.6', 'SSP2-4.5', 'SSP3-7.0', 'SSP5-8.5']
                }
            },
            {
                'title': 'Regional Climate Model Data (CORDEX)',
                'description': 'High-resolution regional climate model outputs from the Coordinated Regional Climate Downscaling Experiment (CORDEX).',
                'category': 'climate-rcm',
                'is_featured': True,
                'metadata': {
                    'temporal_coverage': '1950-2100',
                    'spatial_resolution': '0.11° x 0.11°',
                    'variables': ['temperature', 'precipitation', 'solar_radiation'],
                    'update_frequency': 'daily',
                    'model_ensemble': 'CORDEX',
                    'domains': ['EUR-11', 'NAM-22', 'SAM-44']
                }
            },
            {
                'title': 'Global Population Projections (SSP)',
                'description': 'Future population projections under different Shared Socioeconomic Pathways (SSP).',
                'category': 'socioeconomic-population',
                'is_featured': True,
                'metadata': {
                    'temporal_coverage': '2020-2100',
                    'spatial_resolution': 'country-level',
                    'variables': ['total_population', 'age_distribution', 'urban_population'],
                    'update_frequency': '5-year',
                    'scenarios': ['SSP1', 'SSP2', 'SSP3', 'SSP4', 'SSP5']
                }
            },
            {
                'title': 'Global GDP Projections',
                'description': 'Future GDP projections under different socioeconomic scenarios.',
                'category': 'socioeconomic-economic',
                'is_featured': True,
                'metadata': {
                    'temporal_coverage': '2020-2100',
                    'spatial_resolution': 'country-level',
                    'variables': ['gdp', 'gdp_per_capita', 'economic_sectors'],
                    'update_frequency': '5-year',
                    'scenarios': ['SSP1', 'SSP2', 'SSP3', 'SSP4', 'SSP5']
                }
            },
            {
                'title': 'Global Land Use Change',
                'description': 'Historical and projected land use change data.',
                'category': 'biophysical-land',
                'is_featured': True,
                'metadata': {
                    'temporal_coverage': '1900-2100',
                    'spatial_resolution': '0.5° x 0.5°',
                    'variables': ['cropland', 'pasture', 'forest', 'urban'],
                    'update_frequency': '10-year',
                    'scenarios': ['SSP1', 'SSP2', 'SSP3', 'SSP4', 'SSP5']
                }
            },
            {
                'title': 'Global Water Availability',
                'description': 'Global water availability and hydrological data.',
                'category': 'biophysical-water',
                'is_featured': True,
                'metadata': {
                    'temporal_coverage': '1900-2100',
                    'spatial_resolution': '0.5° x 0.5°',
                    'variables': ['runoff', 'evapotranspiration', 'soil_moisture'],
                    'update_frequency': 'monthly',
                    'scenarios': ['SSP1', 'SSP2', 'SSP3', 'SSP4', 'SSP5']
                }
            }
        ]

        # Get or create a superuser for the example datasets
        superuser, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            superuser.set_password('admin')
            superuser.save()
            self.stdout.write('Created superuser: admin')

        # Create datasets
        for dataset_data in example_datasets:
            dataset, created = Dataset.objects.get_or_create(
                title=dataset_data['title'],
                defaults={
                    'description': dataset_data['description'],
                    'category': created_subcategories[dataset_data['category']],
                    'created_by': superuser,
                    'status': 'published',
                    'is_featured': dataset_data['is_featured'],
                    'metadata': dataset_data['metadata'],
                    'published_at': timezone.now()
                }
            )
            
            if created:
                # Create access settings
                DatasetAccess.objects.create(
                    dataset=dataset,
                    access_type='public'
                )
                
                # Create a dummy version (since we can't create actual files in this command)
                DatasetVersion.objects.create(
                    dataset=dataset,
                    version_number='1.0.0',
                    description='Initial version',
                    created_by=superuser,
                    is_current=True
                )
                
                self.stdout.write(f"Created dataset: {dataset.title}")
            else:
                self.stdout.write(f"Found dataset: {dataset.title}")

        self.stdout.write(self.style.SUCCESS('Successfully created example datasets and categories')) 