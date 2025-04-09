from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from profiles.models import Profile
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Diagnose and fix login issues'

    def add_arguments(self, parser):
        parser.add_argument('--id_number', type=str, help='Check specific ID number')
        parser.add_argument('--fix', action='store_true', help='Fix issues automatically')

    def handle(self, *args, **options):
        id_number = options.get('id_number')
        fix = options.get('fix', False)
        
        self.stdout.write(self.style.SUCCESS('Checking for login issues...'))
        
        # Check if there are users without profiles
        users_without_profiles = User.objects.filter(profile__isnull=True)
        if users_without_profiles.exists():
            self.stdout.write(self.style.WARNING(f'Found {users_without_profiles.count()} users without profiles'))
            if fix:
                for user in users_without_profiles:
                    Profile.objects.create(user=user)
                self.stdout.write(self.style.SUCCESS(f'Created profiles for {users_without_profiles.count()} users'))
        
        # Check for profiles with null id_number
        profiles_without_id = Profile.objects.filter(id_number__isnull=True)
        if profiles_without_id.exists():
            self.stdout.write(self.style.WARNING(f'Found {profiles_without_id.count()} profiles without ID numbers'))
            if fix:
                for profile in profiles_without_id:
                    profile.id_number = f'TEMP{profile.user.id}'
                    profile.save()
                self.stdout.write(self.style.SUCCESS(f'Set temporary ID numbers for {profiles_without_id.count()} profiles'))
        
        # Check specific ID number if provided
        if id_number:
            try:
                profile = Profile.objects.get(id_number=id_number)
                self.stdout.write(self.style.SUCCESS(f'Found profile with ID number {id_number}:'))
                self.stdout.write(f'User: {profile.user.username}')
                self.stdout.write(f'Name: {profile.user.get_full_name()}')
                self.stdout.write(f'Email: {profile.user.email}')
                self.stdout.write(f'Role: {profile.role}')
                self.stdout.write(f'Is active: {profile.user.is_active}')
            except Profile.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'No profile found with ID number: {id_number}'))
                
        self.stdout.write(self.style.SUCCESS('Done checking for login issues.'))
