from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from .models import Profile
import csv
import io
from django.contrib.auth.models import User

class CsvImportForm(forms.Form):
    """Form for uploading CSV files"""
    csv_file = forms.FileField(
        label='Select a CSV file',
        help_text='The CSV file must include headers matching model field names'
    )

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'phone_number', 'id_number', 'gender')
    search_fields = ('user__username', 'first_name', 'last_name', 'phone_number', 'id_number')
    list_filter = ('gender',)
    
    # Add CSV import functionality
    change_list_template = 'admin/profiles/profile/change_list.html'
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import-csv/', self.import_csv, name='import_csv'),
        ]
        return my_urls + urls
    
    def import_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            
            # Validate file is CSV
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file')
                return redirect('admin:profiles_profile_changelist')
            
            # Process CSV file
            try:
                data_set = csv_file.read().decode('UTF-8')
                io_string = io.StringIO(data_set)
                next(io_string)  # Skip header row
                
                # Process each row
                for row in csv.reader(io_string, delimiter=',', quotechar='"'):
                    if len(row) < 8:  # Check basic length
                        continue
                        
                    email = row[0].strip()
                    first_name = row[1].strip()
                    last_name = row[2].strip()
                    middle_name = row[3].strip() if row[3].strip() else None
                    phone_number = row[4].strip()
                    id_number = row[5].strip()
                    dob = row[6].strip() or None
                    gender = row[7].strip().lower()
                    location = row[8].strip() if len(row) > 8 and row[8].strip() else None
                    bio = row[9].strip() if len(row) > 9 and row[9].strip() else None
                    
                    # Skip rows without critical data
                    if not (email and first_name and last_name and phone_number and id_number):
                        continue
                        
                    # Check if user exists, create if not
                    try:
                        user = User.objects.get(username=email)
                    except User.DoesNotExist:
                        # Create new user
                        user = User.objects.create_user(
                            username=email,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                            # Set a default password - should be changed
                            password='changeme123'
                        )
                    
                    # Check if profile exists
                    try:
                        profile = Profile.objects.get(user=user)
                        # Update existing profile
                        profile.first_name = first_name
                        profile.last_name = last_name
                        profile.middle_name = middle_name
                        profile.phone_number = phone_number
                        profile.id_number = id_number
                        profile.dob = dob
                        profile.gender = gender
                        profile.location = location
                        profile.bio = bio
                        profile.save()
                    except Profile.DoesNotExist:
                        # Create new profile
                        Profile.objects.create(
                            user=user,
                            first_name=first_name,
                            last_name=last_name,
                            middle_name=middle_name,
                            phone_number=phone_number,
                            id_number=id_number,
                            dob=dob,
                            gender=gender,
                            location=location,
                            bio=bio
                        )
                
                messages.success(request, 'CSV file imported successfully')
            except Exception as e:
                messages.error(request, f'Error importing CSV: {str(e)}')
            
            return redirect('admin:profiles_profile_changelist')
            
        form = CsvImportForm()
        context = {
            'form': form,
            'title': 'Import Profiles from CSV',
            'opts': self.model._meta,
        }
        return render(request, 'admin/csv_form.html', context)

admin.site.register(Profile, ProfileAdmin)
