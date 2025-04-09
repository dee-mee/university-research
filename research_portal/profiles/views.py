import logging
from pyexpat.errors import messages
from django.shortcuts import render, redirect
from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_protect
from .serializers import RegisterSerializer, LoginSerializer, PasswordResetSerializer
from .forms import LoginForm, ProfileEditForm, UserRegistrationForm
from .models import Profile
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.serializers import serialize
import csv
import json


logger = logging.getLogger(__name__)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    
    def perform_create(self, serializer):
        serializer.save()
    
    def get(self, request, *args, **kwargs):
        form = UserRegistrationForm()
        return render(request, 'profiles/register.html', {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                return redirect('profiles:login')  # Redirect to login after successful registration
            except Exception as e:
                logger.error(f"Error during registration: {e}")
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': form.errors})
        return render(request, 'profiles/register.html', {'form': form})

class PasswordResetView(generics.GenericAPIView):
    serializer_class = PasswordResetSerializer
    
    def post(self, request, *args, **kwargs):
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if User.objects.filter(email=email).exists():
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    email_template_name='profiles/password_reset_email.html'
                )
                return JsonResponse({"message": "Password reset link sent"}, status=status.HTTP_200_OK)
            else:
                return JsonResponse({"message": "This email is not registered"}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse({"message": form.errors}, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        form = PasswordResetForm()
        return render(request, 'profiles/password_reset.html', {'form': form})

@csrf_protect
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                # User is already authenticated in form.clean()
                user = form.cleaned_data.get('user')
                login(request, user)
                
                # Log successful login
                logger.info(f"User logged in successfully: {user.username}")
                
                # Check if it's an AJAX request
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                return redirect('profiles:dashboard')  # Redirect to dashboard after login
            except Exception as e:
                logger.error(f"Login error: {e}")
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
        else:
            # Form is invalid, prepare error messages
            errors = form.errors
            logger.warning(f"Login form validation failed: {errors}")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': errors})
            # For non-AJAX requests, continue to render the form with errors
    else:
        form = LoginForm()
    
    return render(request, 'profiles/login.html', {'form': form})

@login_required
def settings_view(request):
    """
    Render the user's settings page
    """
    return render(request, 'profiles/settings.html', {
        'user': request.user
    })

@login_required
def notifications_view(request):
    """
    Render the user's notifications settings page
    """
    return render(request, 'profiles/notifications.html', {
        'user': request.user
    })

@login_required
def privacy_view(request):
    """
    Render the user's privacy settings page
    """
    return render(request, 'profiles/privacy.html', {
        'user': request.user
    })

def logout_view(request):
    logout(request)
    return redirect('profiles:login')

@login_required
def dashboard_view(request):
    """Display dashboard based on user role"""
    user = request.user
    try:
        role = user.profile.role
    except:
        role = 'project_member'  # Default role if profile doesn't exist
    
    # Determine which dashboard template to use based on role
    template_map = {
        'phd_student': 'profiles/dashboards/phd_dashboard.html',
        'local_coordinator': 'profiles/dashboards/coordinator_dashboard.html',
        'project_leader': 'profiles/dashboards/leader_dashboard.html',
        'project_member': 'profiles/dashboards/member_dashboard.html',
        'admin': 'profiles/dashboards/admin_dashboard.html',
    }
    
    template = template_map.get(role, 'profiles/dashboard.html')
    
    # Common context for all dashboards
    context = {
        'user': user,
        'role': role,
        'role_display': user.profile.get_role_display_name() if hasattr(user, 'profile') else '',
        'dashboard_url': 'profiles:dashboard',
        'profile_url': 'profiles:profile',
        'maps_url': 'maps:map',
        'repository_url': 'repository:dataset_list',
        'edit_profile_url': 'profiles:edit_profile',
        'logout_url': 'profiles:logout'
    }
    
    # Add role-specific context
    if role == 'project_leader':
        # For project leaders, add project management info
        context['managed_projects'] = []  # Add query for projects they manage
    elif role == 'local_coordinator':
        # For coordinators, add location-specific info
        context['location_stats'] = []  # Add location statistics
    
    return render(request, template, context)

def homepage_view(request):
    return render(request, 'index.html')

@login_required
def profile_view(request):
    """
    Render the user's profile page
    """
    try:
        profile = request.user.profile
        return render(request, 'profiles/profile.html', {
            'profile': profile,
            'user': request.user
        })
    except Profile.DoesNotExist:
        # Redirect to create profile if it doesn't exist
        return redirect('profiles:create_profile')

@login_required
def export_profile(request, export_format):
    """
    Export user profile data in specified format
    """
    try:
        profile = request.user.profile
        
        # Prepare profile data
        profile_data = {
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'email': request.user.email,
            'middle_name': profile.middle_name,
            'phone_number': profile.phone_number,
            'id_number': profile.id_number,
            'date_of_birth': str(profile.dob),
            'gender': profile.gender,
            'location': profile.location or '',
            'bio': profile.bio or ''
        }
        
        # Export based on format
        if export_format == 'json':
            response = HttpResponse(
                json.dumps(profile_data, indent=4), 
                content_type='application/json'
            )
            response['Content-Disposition'] = 'attachment; filename="profile_export.json"'
            return response
        
        elif export_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="profile_export.csv"'
            
            # Write CSV
            writer = csv.DictWriter(response, fieldnames=profile_data.keys())
            writer.writeheader()
            writer.writerow(profile_data)
            
            return response
        
        else:
            return JsonResponse({'error': 'Invalid export format'}, status=400)
    
    except Profile.DoesNotExist:
        return JsonResponse({'error': 'Profile not found'}, status=404)

@login_required
def edit_profile(request):
    """
    Handle profile editing
    """
    try:
        # Get or create profile if it doesn't exist
        profile, created = Profile.objects.get_or_create(user=request.user)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error accessing profile: {str(e)}"}, status=500)

    if request.method == 'POST':
        # Handle profile form
        profile_form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        
        # Handle user model fields
        user_form_data = {
            'first_name': request.POST.get('first_name'),
            'last_name': request.POST.get('last_name'),
            'email': request.POST.get('email')
        }
        
        if profile_form.is_valid():
            try:
                # Update profile
                profile = profile_form.save(commit=False)
                profile.user = request.user
                profile.save()

                # Update user model fields
                user = request.user
                user.first_name = user_form_data['first_name']
                user.last_name = user_form_data['last_name']
                user.email = user_form_data['email']
                user.save()

                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Profile updated successfully!'
                    })
                else:
                    messages.success(request, 'Profile updated successfully!')
                    return redirect('profiles:profile')
            
            except Exception as e:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f"Error updating profile: {str(e)}"
                    }, status=500)
                else:
                    messages.error(request, f"Error updating profile: {str(e)}")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Please correct the errors in the form.',
                    'errors': profile_form.errors
                }, status=400)
            else:
                messages.error(request, 'Please correct the errors in the form.')
                return render(request, 'profiles/edit_profile.html', {
                    'form': profile_form,
                    'user_form_data': {
                        'first_name': request.POST.get('first_name', request.user.first_name),
                        'last_name': request.POST.get('last_name', request.user.last_name)
                    }
                })

    else:
        # Initial form load
        profile_form = ProfileEditForm(instance=profile, initial={
            'email': request.user.email,
            'location': profile.location,
            'role': profile.role,
            'department': profile.department,
            'research_interests': profile.research_interests,
            'phone': profile.phone,
            'linkedin': profile.linkedin,
            'scholar': profile.scholar
        })

    return render(request, 'profiles/edit_profile.html', {
        'form': profile_form,
        'user_form_data': {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name
        }
    })