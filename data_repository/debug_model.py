#!/usr/bin/env python
"""
Small utility to debug Django model fields.
Helps identify field types to avoid type errors.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')

try:
    import cgi
except ImportError:
    import compat_cgi
    sys.modules['cgi'] = compat_cgi

django.setup()

from data_repository.models import Dataset, DatasetVersion, DatasetCategory
import psycopg2
from django.db import connection

def inspect_models():
    """Print the field types of the models we're using"""
    print("=== DatasetVersion Model Fields ===")
    for field in DatasetVersion._meta.get_fields():
        print(f"- {field.name}: {field.__class__.__name__}")
        
    print("\n=== Dataset Model Fields ===")
    for field in Dataset._meta.get_fields():
        print(f"- {field.name}: {field.__class__.__name__}")

def inspect_database_schema():
    """Check the actual database schema"""
    print("\n=== Database Table Schema ===")
    with connection.cursor() as cursor:
        # Get the table name
        table_name = DatasetVersion._meta.db_table
        print(f"Table name: {table_name}")
        
        # Get column details
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        
        print(f"\nColumns in {table_name}:")
        for column in columns:
            print(f"- {column[0]}: {column[1]} (nullable: {column[2]})")

if __name__ == "__main__":
    inspect_models()
    inspect_database_schema()
