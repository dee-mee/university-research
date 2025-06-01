from django.apps import AppConfig


class MapsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'maps'

    def ready(self):
        from .views import setup_automated_imports
        # Use an environment variable for configuration
        import os
        drive_path = os.environ.get('FLASH_DRIVE_PATH', '/media/usb')
        import_interval = int(os.environ.get('IMPORT_INTERVAL', '3600'))
        setup_automated_imports(drive_path, import_interval)
