from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    # One-to-One relationship with Django's User model
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=100, blank=True, null=True, help_text="User's role or position")
    department = models.CharField(max_length=100, blank=True, null=True, help_text="Department")
    research_interests = models.TextField(blank=True, null=True, help_text="Research interests")
    phone = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$', 
                message='Enter a valid phone number'
            )
        ],
        help_text="Phone number"
    )
    location = models.CharField(max_length=100, blank=True, null=True, help_text="Location")
    linkedin = models.URLField(blank=True, null=True, help_text="LinkedIn profile URL")
    scholar = models.URLField(blank=True, null=True, help_text="Google Scholar profile URL")
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.get_full_name()} Profile"

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()