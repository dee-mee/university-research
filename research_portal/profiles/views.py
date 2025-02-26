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

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        Profile.objects.create(user=user, reg_number=serializer.validated_data['reg_number'])

    def get(self, request, *args, **kwargs):
        form = UserRegistrationForm()
        return render(request, 'profiles/register.html', {'form': form})

    def post(self, request, *args, **kwargs):
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            if request.is_ajax():
                return JsonResponse({'success': True})
            return redirect('login')
        if request.is_ajax():
            return JsonResponse({'success': False, 'message': form.errors})
        return render(request, 'profiles/register.html', {'form': form})

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
            reg_number = form.cleaned_data.get('reg_number')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=reg_number, password=password)
            if user is not None:
                login(request, user)
                if request.is_ajax():
                    return JsonResponse({'success': True})
                return redirect('research:index')
            else:
                form.add_error(None, 'Invalid username or password')
        if request.is_ajax():
            return JsonResponse({'success': False, 'message': form.errors})
    else:
        form = LoginForm()
    return render(request, 'profiles/login.html', {'form': form})