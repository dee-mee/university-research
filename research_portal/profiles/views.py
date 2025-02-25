from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_protect
from .serializers import RegisterSerializer, LoginSerializer, PasswordResetSerializer
from .forms import LoginForm
from .models import Profile

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        Profile.objects.create(user=user, username=serializer.validated_data['username'])

class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(username=serializer.validated_data['username'], password=serializer.validated_data['password'])
        if user is not None:
            login(request, user)
            return Response({"message": "Login successful"}, status=status.HTTP_200_OK)
        return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetView(generics.GenericAPIView):
    serializer_class = PasswordResetSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Implement password reset logic here
        return Response({"message": "Password reset link sent"}, status=status.HTTP_200_OK)


@csrf_protect
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            reg_number = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                if user.is_superuser:
                    return redirect('admin_dashboard')  # Redirect admin to admin dashboard
                else:
                    return redirect('user_dashboard')  # Redirect normal users to user dashboard
            else:
                form.add_error(None, 'Invalid username or password')
    else:
        form = LoginForm()
    return render(request, 'profiles/login.html', {'form': form})


@login_required
def user_dashboard(request):
    return render(request, 'dashboard/user_dashboard.html')
