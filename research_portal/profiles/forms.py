from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm

class UserRegistrationForm(forms.ModelForm):
    reg_number = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    class Meta:
        model = User
        fields = ('reg_number', 'email', 'first_name', 'last_name')

    def clean_password2(self):
        cd = self.cleaned_data
        if cd['password'] != cd['password2']:
            raise forms.ValidationError("Passwords don't match.")
        return cd['password2']

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(max_length=254)

class LoginForm(forms.Form):
    reg_number = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)