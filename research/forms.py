from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    id_number = forms.CharField(
        max_length=20,
        help_text='Enter your National ID number or Passport number',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    registration_number = forms.CharField(
        max_length=20,
        required=False,
        help_text='Enter your student/staff registration number (if applicable)',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
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

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('id_number', 'registration_number', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_id_number(self):
        id_number = self.cleaned_data.get('id_number')
        if id_number:
            id_number = id_number.upper()
            if CustomUser.objects.filter(id_number=id_number).exists():
                raise forms.ValidationError("This ID number is already registered.")
        return id_number

    def clean_registration_number(self):
        reg_number = self.cleaned_data.get('registration_number')
        if reg_number:
            reg_number = reg_number.upper()
            if CustomUser.objects.filter(registration_number=reg_number).exists():
                raise forms.ValidationError("This registration number is already registered.")
        return reg_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.id_number  # Set username to id_number
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user