from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from .models import Profile

class UserRegistrationForm(forms.ModelForm):
    reg_number = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")
    
    class Meta:
        model = User
        fields = ('email',)  # Only include email field from User model
    
    def clean_reg_number(self):
        reg_number = self.cleaned_data.get('reg_number')
        if Profile.objects.filter(reg_number=reg_number).exists():
            raise forms.ValidationError("A user with that registration number already exists.")
        return reg_number
    
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
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Set username to email
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            Profile.objects.create(user=user, reg_number=self.cleaned_data['reg_number'])
        return user

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(max_length=254)

class LoginForm(forms.Form):
    reg_number = forms.CharField(max_length=150, label="Registration Number or Email")
    password = forms.CharField(widget=forms.PasswordInput)
    
    def clean(self):
        cleaned_data = super().clean()
        reg_number = cleaned_data.get('reg_number')
        password = cleaned_data.get('password')
        
        if reg_number and password:
            # First try direct login (if reg_number is actually an email/username)
            user = authenticate(username=reg_number, password=password)
            
            # If that fails, try to find user by registration number
            if user is None:
                try:
                    # Find the user associated with this registration number
                    profile = Profile.objects.get(reg_number=reg_number)
                    # Then try to authenticate with their username (email)
                    user = authenticate(username=profile.user.username, password=password)
                except Profile.DoesNotExist:
                    user = None
            
            if not user:
                raise forms.ValidationError("Invalid registration number/email or password")
            else:
                # Store the authenticated user in cleaned_data
                cleaned_data['user'] = user
                
        return cleaned_data