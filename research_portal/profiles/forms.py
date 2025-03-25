from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from .models import Profile
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone

class UserRegistrationForm(forms.ModelForm):
    first_name = forms.CharField()
    middle_name = forms.CharField(required=False)
    last_name = forms.CharField()
    phone_number = forms.CharField()
    id_number = forms.CharField()
    dob = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'max': timezone.now().date().isoformat()
        }),
        label="Date of Birth"
    )
    gender = forms.ChoiceField(choices=[('male', 'Male'), ('female', 'Female')])
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    class Meta:
        model = User
        fields = ('email',)  # Only include email field from User model

    def clean_id_number(self):
        id_number = self.cleaned_data.get('id_number')
        if Profile.objects.filter(id_number=id_number).exists():
            raise forms.ValidationError("A user with that ID number already exists.")
        return id_number

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if Profile.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("A user with that phone number already exists.")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def clean_password2(self):
        cd = self.cleaned_data
        if cd.get('password') != cd.get('password2'):
            raise forms.ValidationError("Passwords don't match.")
        return cd.get('password2')

    def clean_dob(self):
        dob = self.cleaned_data.get('dob')
        if dob:
            if dob > timezone.now().date():
                raise forms.ValidationError("Date of birth cannot be in the future.")
            if dob < timezone.now().date() - timezone.timedelta(days=365*100):
                raise forms.ValidationError("Please enter a valid date of birth.")
        return dob

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Set username to email
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                middle_name=self.cleaned_data.get('middle_name', ''),
                phone_number=self.cleaned_data['phone_number'],
                id_number=self.cleaned_data['id_number'],
                dob=self.cleaned_data['dob'],
                gender=self.cleaned_data['gender']
            )
        return user

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(max_length=254)

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, label="Email or ID Number")
    password = forms.CharField(widget=forms.PasswordInput)
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if username and password:
            # First try to authenticate with email
            user = authenticate(username=username, password=password)
            
            # If that fails, try to find user by ID number
            if not user:
                try:
                    profile = Profile.objects.get(id_number=username)
                    user = authenticate(username=profile.user.username, password=password)
                except Profile.DoesNotExist:
                    pass
            
            if not user:
                raise forms.ValidationError("Invalid email/ID number or password")
            else:
                cleaned_data['user'] = user
                
        return cleaned_data

class ProfileEditForm(forms.ModelForm):
    """
    Form for editing user profile details
    """
    first_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Profile
        fields = [
            'first_name',
            'last_name',
            'middle_name', 
            'phone_number', 
            'id_number', 
            'dob', 
            'gender', 
            'location', 
            'bio'
        ]
        widgets = {
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
