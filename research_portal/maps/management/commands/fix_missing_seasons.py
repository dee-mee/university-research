from django.core.management.base import BaseCommand
from maps.models import ClimateData
from django.db import transaction
from django.db.models import F, Case, When, Value, CharField

class Command(BaseCommand):
    help = 'Populates the season field for existing climate data records'

    def handle(self, *args, **options):
        self.stdout.write('Starting to populate season field...')
        
        try:
            with transaction.atomic():
                # Use conditional expressions to determine season based on month
                ClimateData.objects.update(
                    season=Case(
                        When(month__in=[12, 1, 2], then=Value('winter')),
                        When(month__in=[3, 4, 5], then=Value('spring')),
                        When(month__in=[6, 7, 8], then=Value('summer')),
                        When(month__in=[9, 10, 11], then=Value('autumn')),
                        default=Value('winter'),
                        output_field=CharField(),
                    )
                )
                
            self.stdout.write(self.style.SUCCESS('Successfully populated season field'))
            
            # Report counts by season
            winter_count = ClimateData.objects.filter(season='winter').count()
            spring_count = ClimateData.objects.filter(season='spring').count()
            summer_count = ClimateData.objects.filter(season='summer').count()
            autumn_count = ClimateData.objects.filter(season='autumn').count()
            
            self.stdout.write(f'Winter: {winter_count}')
            self.stdout.write(f'Spring: {spring_count}')
            self.stdout.write(f'Summer: {summer_count}')
            self.stdout.write(f'Autumn: {autumn_count}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error populating season field: {str(e)}'))
