from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.conf import settings
from django.db.utils import ProgrammingError
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clear all data from the database while keeping the schema intact'

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput', '--no-input',
            action='store_false',
            dest='interactive',
            help='Tells Django to NOT prompt the user for input of any kind.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting database cleanup...'))
        
        if options['interactive']:
            confirm = input('''\nWARNING: This will delete ALL data from the database.
Are you sure you want to continue? [y/N] ''')
            if confirm.lower() != 'y':
                self.stdout.write(self.style.NOTICE('Operation cancelled.'))
                return
        
        # Get a list of all tables in the database
        with connection.cursor() as cursor:
            # Get all tables in the public schema
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                AND table_name != 'spatial_ref_sys'  -- Keep PostGIS system table
                AND table_name NOT LIKE 'django_%%'  -- Keep Django system tables
                ORDER BY table_name
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            
            # Start a transaction
            with transaction.atomic():
                try:
                    # Disable triggers temporarily to avoid foreign key constraint issues
                    try:
                        cursor.execute('SET CONSTRAINTS ALL DEFERRED')
                    except Exception as e:
                        self.stdout.write(self.style.NOTICE(f'Could not defer constraints: {str(e)}'))
                    
                    # Truncate each table
                    for table in tables:
                        try:
                            self.stdout.write(f'Clearing table: {table}... ', ending='')
                            cursor.execute(f'TRUNCATE TABLE \"{table}\" CASCADE')
                            try:
                                cursor.execute(f'ALTER SEQUENCE IF EXISTS \"{table}_id_seq\" RESTART WITH 1')
                            except Exception as seq_err:
                                self.stdout.write(self.style.NOTICE(f'Could not reset sequence for {table}: {str(seq_err)}'))
                            self.stdout.write(self.style.SUCCESS('OK'))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
                            logger.error(f'Error clearing table {table}: {str(e)}')
                    
                    # Reset Django migrations to initial state
                    self.stdout.write('Resetting Django migrations... ', ending='')
                    try:
                        cursor.execute("""
                            DELETE FROM django_migrations;
                            INSERT INTO django_migrations (app, name, applied)
                            SELECT app, name, NOW() 
                            FROM (
                                VALUES 
                                    ('admin', '0001_initial', NOW()),
                                    ('auth', '0001_initial', NOW()),
                                    ('contenttypes', '0001_initial', NOW()),
                                    ('sessions', '0001_initial', NOW())
                            ) AS initial_migrations(app, name, applied);
                        """)
                        self.stdout.write(self.style.SUCCESS('OK'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error resetting migrations: {str(e)}'))
                        logger.error(f'Error resetting migrations: {str(e)}')
                        raise
                    
                    self.stdout.write(self.style.SUCCESS('\nDatabase cleanup completed successfully!'))
                    self.stdout.write(self.style.WARNING('\nPlease run the following commands to recreate the database structure:'))
                    self.stdout.write('1. python manage.py migrate')
                    self.stdout.write('2. python manage.py createsuperuser')
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'\nError during database cleanup: {str(e)}'))
                    logger.error(f'Database cleanup error: {str(e)}')
                    # The transaction will be rolled back automatically due to the with statement
                    raise
