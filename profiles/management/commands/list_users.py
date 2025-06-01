from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from profiles.models import Profile
from prettytable import PrettyTable

class Command(BaseCommand):
    help = 'List all users and their ID numbers'

    def add_arguments(self, parser):
        parser.add_argument('--role', type=str, help='Filter by role')

    def handle(self, *args, **options):
        role_filter = options.get('role')
        
        self.stdout.write(self.style.SUCCESS('Listing all users:'))
        
        # Create a pretty table for output
        table = PrettyTable()
        table.field_names = ["Username", "Full Name", "ID Number", "Role", "Email"]
        
        # Get profiles, optionally filtered by role
        profiles = Profile.objects.all()
        if role_filter:
            profiles = profiles.filter(role=role_filter)
        
        # Sort by username
        profiles = profiles.order_by('user__username')
        
        for profile in profiles:
            user = profile.user
            table.add_row([
                user.username,
                user.get_full_name(),
                profile.id_number or "N/A",
                profile.get_role_display_name() or "N/A",
                user.email
            ])
            
        self.stdout.write(str(table))
        self.stdout.write(self.style.SUCCESS(f'Total users: {profiles.count()}'))
        
        # List users without ID numbers
        profiles_without_id = profiles.filter(id_number__isnull=True)
        if profiles_without_id.exists():
            self.stdout.write(self.style.WARNING(f'Found {profiles_without_id.count()} users without ID numbers'))
            self.stdout.write("You can fix this with: python manage.py fix_login_issues --fix")
