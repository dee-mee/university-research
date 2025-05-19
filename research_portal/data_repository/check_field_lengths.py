#!/usr/bin/env python
"""
A utility script to check field lengths in the models and recommend fixes.
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
from django.db import connection

def check_model_fields():
    """Check database field lengths and print recommendations"""
    print("=== Checking Dataset Model Field Lengths ===")
    
    # Check all char fields in Dataset model
    for field in Dataset._meta.get_fields():
        if field.__class__.__name__ == 'CharField':
            print(f"- {field.name}: {field.max_length} characters")
            
            # Check if any data is near the limit
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {Dataset._meta.db_table}
                    WHERE LENGTH({field.name}) > {field.max_length * 0.8}
                """)
                count = cursor.fetchone()[0]
                if count > 0:
                    print(f"  ⚠️ {count} records use > 80% of max length")
                    
                    # Get the longest value for this field
                    cursor.execute(f"""
                        SELECT {field.name}, LENGTH({field.name}) as chars
                        FROM {Dataset._meta.db_table}
                        ORDER BY chars DESC
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    if result:
                        value, length = result
                        print(f"  📏 Longest value: '{value[:50]}{'...' if len(value) > 50 else ''}' ({length} chars)")
    
    print("\n=== Recommendations ===")
    print("To fix the string length errors, add/update the following in your models.py file:")
    print("""
    # Increase field lengths for frequently hitting limits
    isimip_id = models.CharField(max_length=150, blank=True, null=True)
    
    # Other fields to consider increasing if you see warnings above:
    # title = models.CharField(max_length=255, unique=True)
    # simulation_round = models.CharField(max_length=100, blank=True, null=True)
    # impact_model = models.CharField(max_length=100, blank=True, null=True)
    # climate_forcing = models.CharField(max_length=100, blank=True, null=True)
    # climate_scenario = models.CharField(max_length=100, blank=True, null=True)
    """)

if __name__ == "__main__":
    check_model_fields()
