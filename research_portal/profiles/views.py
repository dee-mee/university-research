from django.shortcuts import render, redirect
from django.http import JsonResponse
from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_protect
from .serializers import RegisterSerializer, LoginSerializer, PasswordResetSerializer
from .forms import LoginForm, UserRegistrationForm
from .models import Profile
from django.contrib.auth.decorators import login_required

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
            user = form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('login')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': form.errors})
        return render(request, 'profiles/register.html', {'form': form})

class PasswordResetView(generics.GenericAPIView):
    serializer_class = PasswordResetSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Implement password reset logic here
        return Response({"message": "Password reset link sent"}, status=status.HTTP_200_OK)
    
    def get(self, request):
        return render(request, 'profiles/password_reset.html')

@csrf_protect
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            # User is already authenticated in form.clean()
            user = form.cleaned_data.get('user')
            login(request, user)
            
            # Check if it's an AJAX request
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('dashboard')  # Redirect to dashboard after login
        else:
            # Form is invalid, prepare error messages
            errors = form.errors
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': errors})
    else:
        form = LoginForm()
    
    return render(request, 'profiles/login.html', {'form': form})

@login_required
def dashboard_view(request):
    return render(request, 'profiles/dashboard.html')