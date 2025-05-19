from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from django.contrib.auth.admin import UserAdmin  # Add this import for UserAdmin
from .models import Profile, Notification
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
    list_display = ('user', 'id_number', 'phone', 'location', 'role', 'get_formatted_role')
    search_fields = ('user__username', 'id_number', 'phone', 'location', 'role')
    list_filter = ('role',)
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        ('Authentication Information', {
            'fields': ('id_number',),
            'description': 'ID Number is used for login authentication and must be unique',
        }),
        ('Role Information', {
            'fields': ('role', 'department'),
            'description': 'Assign appropriate role to determine dashboard access',
        }),
        ('Contact Information', {
            'fields': ('phone', 'location', 'linkedin', 'scholar'),
        }),
        ('Research Information', {
            'fields': ('research_interests',),
        }),
        ('Profile Image', {
            'fields': ('profile_image',),
        }),
    )
    
    def get_formatted_role(self, obj):
        return obj.get_role_display_name()
    get_formatted_role.short_description = 'Role Type'
    
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
                    if len(row) < 6:  # Check basic length (including id_number)
                        continue
                    
                    # Create or update profile
                    try:
                        user = User.objects.get(username=row[0])
                        profile, created = Profile.objects.get_or_create(user=user)
                        
                        # Update profile fields
                        profile.phone = row[1]
                        profile.location = row[2]
                        profile.role = row[3]
                        profile.id_number = row[4]  # Add id_number field
                        profile.save()
                        
                        if created:
                            messages.success(request, f'Created profile for {user.username}')
                        else:
                            messages.success(request, f'Updated profile for {user.username}')
                    
                    except User.DoesNotExist:
                        messages.warning(request, f'User {row[0]} does not exist')
                    except Exception as e:
                        messages.error(request, f'Error processing row: {str(e)}')
                        
            except Exception as e:
                messages.error(request, f'Error processing CSV: {str(e)}')
                
            return redirect('admin:profiles_profile_changelist')
        
        form = CsvImportForm()
        payload = {"form": form}
        return render(
            request, "admin/csv_form.html", payload
        )

# Extend the User admin with Profile information
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'get_department', 'is_staff')
    list_select_related = ('profile',)
    
    def get_role(self, instance):
        return instance.profile.get_role_display_name()
    get_role.short_description = 'Role'
    
    def get_department(self, instance):
        return instance.profile.department
    get_department.short_description = 'Department'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'read', 'created_at')
    list_filter = ('read', 'created_at')
    search_fields = ('title', 'message', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'title', 'message')
        }),
        ('Details', {
            'fields': ('link', 'read', 'created_at', 'updated_at')
        }),
    )

admin.site.register(Profile, ProfileAdmin)
