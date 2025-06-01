from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from profiles.models import Profile
import random
import string

class Command(BaseCommand):
    help = 'Create a test user with a specific role'

    def add_arguments(self, parser):
        parser.add_argument('--role', type=str, default='project_leader', 
                            help='Role for the user (phd_student, local_coordinator, project_leader, project_member)')
        parser.add_argument('--id_number', type=str, 
                            help='Custom ID number (default: random)')
        parser.add_argument('--password', type=str, default='testpassword', 
                            help='Password for the user')

    def handle(self, *args, **options):
        role = options.get('role')
        password = options.get('password')
        id_number = options.get('id_number')
        
        if not id_number:
            # Generate a random ID number
            id_number = 'ID' + ''.join(random.choices(string.digits, k=6))
        
        # Check if the ID number already exists
        if Profile.objects.filter(id_number=id_number).exists():
            self.stdout.write(self.style.ERROR(f'ID number {id_number} already exists!'))
            return
        
        # Create username from role and id_number
        username = f"{role.replace('_', '')}{id_number[-4:]}"
        email = f"{username}@example.com"
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=role.replace('_', ' ').title(),
                last_name='User'
            )
            
            # Update profile
            profile = user.profile
            profile.id_number = id_number
            profile.role = role
            profile.department = 'Test Department'
            profile.phone_number = '123-456-7890'
            profile.gender = 'other'
            profile.save()
            
            self.stdout.write(self.style.SUCCESS(f'Successfully created {role} user:'))
            self.stdout.write(f'Username: {username}')
            self.stdout.write(f'ID Number: {id_number}')
            self.stdout.write(f'Password: {password}')
            self.stdout.write(f'Email: {email}')
            self.stdout.write(f'Role: {profile.get_role_display_name()}')
            self.stdout.write(self.style.SUCCESS('You can now log in with this ID number and password'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating user: {str(e)}'))
