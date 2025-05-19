#!/usr/bin/env python
"""
Utility to fix database schema issues with the version_number field.
"""

import os
import sys

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')

try:
    import cgi
except ImportError:
    import compat_cgi
    sys.modules['cgi'] = compat_cgi

import django
django.setup()

from django.db import connection
from data_repository.models import DatasetVersion

def check_and_fix_schema():
    """Check if version_number is integer in DB but CharField in model, and fix if needed"""
    # Check current column type
    with connection.cursor() as cursor:
        table_name = DatasetVersion._meta.db_table
        cursor.execute(f"""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND column_name = 'version_number'
        """)
        result = cursor.fetchone()
        if not result:
            print("Could not find version_number column!")
            return
        
        column_type = result[0]
        print(f"Current database type for version_number: {column_type}")
        
        if column_type == 'integer' or column_type == 'bigint':
            print("Converting version_number column from integer to text...")
            
            # Get existing data first
            cursor.execute(f"SELECT id, version_number FROM {table_name}")
            existing_versions = cursor.fetchall()
            
            # Create a backup of existing data
            backup = {}
            for id, version_number in existing_versions:
                backup[id] = version_number
            
            # Alter the column type
            try:
                cursor.execute(f"ALTER TABLE {table_name} ALTER COLUMN version_number TYPE varchar(50)")
                print("Column type changed successfully!")
                
                # Update the data to be semantic versions
                for id, version_number in existing_versions:
                    semantic_version = f"{version_number}.0.0"
                    cursor.execute(
                        f"UPDATE {table_name} SET version_number = %s WHERE id = %s", 
                        [semantic_version, id]
                    )
                print(f"Updated {len(existing_versions)} rows with semantic versions.")
                
                # Commit the transaction
                connection.commit()
                print("Changes committed to database.")
                
            except Exception as e:
                print(f"Error altering column: {e}")
                print("Rolling back changes.")
                connection.rollback()
        else:
            print("Column type is already compatible with model definition. No changes needed.")

if __name__ == "__main__":
    check_and_fix_schema()
