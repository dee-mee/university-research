#!/usr/bin/env python
"""
A utility script to check existing migrations.
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

from django.db.migrations.loader import MigrationLoader

def check_migrations():
    """List all applied migrations for data_repository app."""
    print("=== Checking Applied Migrations ===")
    connection = django.db.connections['default']
    loader = MigrationLoader(connection)
    
    # Get all migrations for data_repository app
    app_migrations = sorted([
        (name, migration) 
        for (app, name), migration in loader.graph.nodes.items() 
        if app == 'data_repository'
    ], key=lambda x: x[0])
    
    if not app_migrations:
        print("No migrations found for data_repository app.")
        return
    
    print("Available migrations for data_repository app:")
    for name, migration in app_migrations:
        print(f"- {name}{' (applied)' if loader.applied_migrations.get(('data_repository', name)) else ''}")
    
    # Find the latest migration
    latest_migration = app_migrations[-1][0]
    print(f"\nLatest migration is: {latest_migration}")
    print("\nUpdate your new migration to depend on this one.")

if __name__ == "__main__":
    check_migrations()
