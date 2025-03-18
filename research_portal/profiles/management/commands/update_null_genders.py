from django.core.management.base import BaseCommand
from profiles.models import Profile

class Command(BaseCommand):
    help = 'Updates all null values to default values'

    def handle(self, *args, **options):
        # Update gender
        gender_updates = Profile.objects.filter(gender__isnull=True).update(gender='other')
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {gender_updates} profiles with null gender values to "other"')
        )

        # Update id_number with a placeholder
        id_updates = 0
        for profile in Profile.objects.filter(id_number__isnull=True):
            profile.id_number = f'TEMP{profile.user.id}'
            profile.save()
            id_updates += 1
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {id_updates} profiles with null ID numbers')
        )

        # Update phone_number with a placeholder
        phone_updates = 0
        for profile in Profile.objects.filter(phone_number__isnull=True):
            profile.phone_number = f'+000{profile.user.id}'
            profile.save()
            phone_updates += 1
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {phone_updates} profiles with null phone numbers')
        ) 