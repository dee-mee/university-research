from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import IntegrityError, ProgrammingError

class Command(BaseCommand):
    help = 'Applies SQL migrations for field data collection features'

    def handle(self, *args, **options):
        # SQL statements to create the new tables and add fields to existing tables
        SQL_STATEMENTS = [
            # Add data_source field to ClimateData table
            """
            ALTER TABLE maps_climatedata 
            ADD COLUMN data_source varchar(15) NOT NULL DEFAULT 'station';
            """,
            
            # Create DeviceType table
            """
            CREATE TABLE maps_devicetype (
                id serial PRIMARY KEY,
                name varchar(100) NOT NULL,
                manufacturer varchar(100) NOT NULL,
                model_number varchar(50) NULL,
                description text NULL,
                communication_protocol varchar(20) NOT NULL,
                power_source varchar(20) NOT NULL,
                battery_life_days integer NULL,
                firmware_version varchar(50) NULL,
                has_temperature boolean NOT NULL,
                has_precipitation boolean NOT NULL,
                has_humidity boolean NOT NULL,
                has_wind boolean NOT NULL,
                has_air_quality boolean NOT NULL,
                has_soil_moisture boolean NOT NULL,
                has_water_level boolean NOT NULL,
                created_at timestamp with time zone NOT NULL,
                updated_at timestamp with time zone NOT NULL
            );
            """,
            
            # Create FieldDevice table
            """
            CREATE TABLE maps_fielddevice (
                id serial PRIMARY KEY,
                device_id varchar(100) NOT NULL UNIQUE,
                name varchar(255) NOT NULL,
                status varchar(20) NOT NULL,
                installation_date date NULL,
                last_communication timestamp with time zone NULL,
                battery_level double precision NULL,
                signal_strength integer NULL,
                firmware_version varchar(50) NULL,
                transmission_interval integer NOT NULL,
                notes text NULL,
                created_at timestamp with time zone NOT NULL,
                updated_at timestamp with time zone NOT NULL,
                device_type_id integer NOT NULL REFERENCES maps_devicetype(id),
                location geography(Point, 4326) NULL,
                weather_station_id integer NULL REFERENCES maps_weatherstation(id)
            );
            """,
            
            # Create indexes for FieldDevice
            """
            CREATE INDEX maps_fielddevice_status_idx ON maps_fielddevice(status);
            """,
            """
            CREATE INDEX maps_fielddevice_device_type_id_idx ON maps_fielddevice(device_type_id);
            """,
            """
            CREATE INDEX maps_fielddevice_weather_station_id_idx ON maps_fielddevice(weather_station_id);
            """,
            
            # Create DeviceCalibration table
            """
            CREATE TABLE maps_devicecalibration (
                id serial PRIMARY KEY,
                calibration_date timestamp with time zone NOT NULL,
                next_calibration_date timestamp with time zone NOT NULL,
                temperature_offset double precision NULL,
                humidity_offset double precision NULL,
                pressure_offset double precision NULL,
                notes text NULL,
                certificate_number varchar(100) NULL,
                created_at timestamp with time zone NOT NULL,
                updated_at timestamp with time zone NOT NULL,
                device_id integer NOT NULL REFERENCES maps_fielddevice(id),
                performed_by_id integer NULL REFERENCES auth_user(id)
            );
            """,
            
            # Create FieldDataUpload table
            """
            CREATE TABLE maps_fielddataupload (
                id serial PRIMARY KEY,
                upload_date timestamp with time zone NOT NULL,
                data_date date NOT NULL,
                status varchar(20) NOT NULL,
                file varchar(100) NULL,
                temperature double precision NULL,
                humidity double precision NULL,
                precipitation double precision NULL,
                notes text NULL,
                photo varchar(100) NULL,
                review_date timestamp with time zone NULL,
                review_notes text NULL,
                collection_location geography(Point, 4326) NULL,
                device_id integer NULL REFERENCES maps_fielddevice(id),
                reviewed_by_id integer NULL REFERENCES auth_user(id),
                uploader_id integer NULL REFERENCES auth_user(id),
                weather_station_id integer NOT NULL REFERENCES maps_weatherstation(id)
            );
            """
        ]

        cursor = connection.cursor()
        success_count = 0
        error_count = 0
        
        self.stdout.write(self.style.SUCCESS("\n===== FIELD DATA COLLECTION MIGRATION =====\n"))
        self.stdout.write(f"Found {len(SQL_STATEMENTS)} SQL statements to execute.\n")
        
        for i, sql in enumerate(SQL_STATEMENTS):
            statement_name = f"Statement {i+1}/{len(SQL_STATEMENTS)}"
            if "ADD COLUMN data_source" in sql:
                statement_name = "Adding data_source field to ClimateData"
            elif "CREATE TABLE maps_devicetype" in sql:
                statement_name = "Creating DeviceType table"
            elif "CREATE TABLE maps_fielddevice" in sql:
                statement_name = "Creating FieldDevice table"
            elif "CREATE INDEX" in sql and "fielddevice" in sql:
                statement_name = "Creating index on FieldDevice"
            elif "CREATE TABLE maps_devicecalibration" in sql:
                statement_name = "Creating DeviceCalibration table"
            elif "CREATE TABLE maps_fielddataupload" in sql:
                statement_name = "Creating FieldDataUpload table"
                
            self.stdout.write(f"Executing: {statement_name}...")
            try:
                cursor.execute(sql)
                connection.commit()
                self.stdout.write(self.style.SUCCESS(f"✅ {statement_name} executed successfully."))
                success_count += 1
            except (IntegrityError, ProgrammingError) as e:
                error_message = str(e)
                if "already exists" in error_message:
                    self.stdout.write(self.style.WARNING(f"⚠️ {statement_name} skipped: {error_message}"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Error executing {statement_name}: {error_message}"))
                    error_count += 1
                # Continue with other statements even if one fails
                connection.rollback()
        
        self.stdout.write(self.style.SUCCESS(f"\n===== MIGRATION SUMMARY ====="))
        self.stdout.write(f"Total statements: {len(SQL_STATEMENTS)}")
        self.stdout.write(f"Successfully executed: {success_count}")
        self.stdout.write(f"Errors: {error_count}")
        self.stdout.write(self.style.SUCCESS(f"Migration {'completed successfully' if error_count == 0 else 'completed with errors'}.\n"))
