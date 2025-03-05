from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

class Profile(models.Model):
    # One-to-One relationship with Django's User model
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    first_name = models.CharField(max_length=30, help_text="First name")
    last_name = models.CharField(max_length=30, help_text="Last name")
    middle_name = models.CharField(
        max_length=30, 
        blank=True, 
        null=True, 
        help_text="Optional middle name"
    )
    
    phone_number = models.CharField(
        max_length=15, 
        unique=True, 
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$', 
                message='Enter a valid phone number'
            )
        ],
        help_text="Staff phone number"
    )
    
    id_number = models.CharField(
        max_length=20, 
        unique=True, 
        validators=[
            RegexValidator(
                regex=r'^[A-Z0-9]+$', 
                message='ID number must be alphanumeric'
            )
        ],
        help_text="Staff unique identification number"
    )
    
    dob = models.DateField(
        help_text="Date of Birth",
        null=True,  # Optional if needed
        blank=True  # Allows form submission without DOB
    )
    
    gender = models.CharField(
        max_length=10, 
        choices=[
            ('male', 'Male'), 
            ('female', 'Female'), 
            ('other', 'Other')
        ],
        help_text="Staff gender"
    )

    location = models.CharField(
        max_length=100, 
        blank=True, 
        null=True
    )
    
    bio = models.TextField(
        blank=True, 
        null=True
    )

    def __str__(self):
        return f"{self.user.get_full_name()} Profile"

    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'