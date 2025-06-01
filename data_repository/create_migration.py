#!/usr/bin/env python
"""
Generate a migration file to increase CharField max_lengths
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')
django.setup()

from django.db.migrations.writer import MigrationWriter
from django.db.migrations import operations
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('data_repository', '0001_initial'),  # Update this to your last migration
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='isimip_id',
            field=django.db.models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='simulation_round',
            field=django.db.models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='impact_model',
            field=django.db.models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='climate_forcing',
            field=django.db.models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='climate_scenario',
            field=django.db.models.CharField(blank=True, max_length=100, null=True),
        ),
    ]

def create_migration_file():
    """Generate a migration file"""
    migration = Migration('increase_field_lengths', 'data_repository')
    
    # Get migration as string
    writer = MigrationWriter(migration)
    migration_string = writer.as_string()
    
    # Create migrations directory if it doesn't exist
    migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
    os.makedirs(migrations_dir, exist_ok=True)
    
    # Write the migration file
    migration_path = os.path.join(migrations_dir, '0002_increase_field_lengths.py')
    with open(migration_path, 'w') as f:
        f.write(migration_string)
    
    print(f"Migration file created at: {migration_path}")
    print("\nNow run the migration with:")
    print("python manage.py migrate data_repository")

if __name__ == "__main__":
    create_migration_file()
