from django.core.management.base import BaseCommand
from maps.models import ClimateData
from django.db import transaction
from django.db.models import F, Case, When, Value, CharField

class Command(BaseCommand):
    help = 'Sets a default season value for all climate data records'

    def handle(self, *args, **options):
        self.stdout.write('Setting default season value...')
        
        try:
            with transaction.atomic():
                # Simply set a default season value without regional or hemisphere considerations
                # Each station's season value should be set explicitly if needed
                ClimateData.objects.update(
                    season=Value('unspecified', output_field=CharField())
                )
                
            self.stdout.write(self.style.SUCCESS('Successfully set default season value'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting season field: {str(e)}'))
