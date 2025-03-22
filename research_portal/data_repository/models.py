from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

class DatasetCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='subcategories', on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Dataset Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Dataset(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    category = models.ForeignKey(DatasetCategory, on_delete=models.PROTECT)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    thumbnail = models.ImageField(upload_to='dataset_thumbnails/', null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=50, default='DerivedOutputData')
    simulation = models.CharField(max_length=50, blank=True, null=True)
    model = models.CharField(max_length=50, blank=True, null=True)
    variables = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('repository:dataset_detail', kwargs={'slug': self.slug})

class DatasetVersion(models.Model):
    dataset = models.ForeignKey(Dataset, related_name='versions', on_delete=models.CASCADE)
    version_number = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    file_path = models.FileField(upload_to='datasets/')
    file_size = models.BigIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.dataset.title} - v{self.version_number}"

    def save(self, *args, **kwargs):
        if self.file_path:
            self.file_size = self.file_path.size
        if self.is_current:
            # Set all other versions of this dataset to not current
            DatasetVersion.objects.filter(dataset=self.dataset).update(is_current=False)
        super().save(*args, **kwargs)

class DatasetAccess(models.Model):
    ACCESS_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),
        ('restricted', 'Restricted'),
    )

    dataset = models.ForeignKey(Dataset, related_name='access', on_delete=models.CASCADE)
    access_type = models.CharField(max_length=10, choices=ACCESS_CHOICES, default='public')
    allowed_users = models.ManyToManyField(User, blank=True, related_name='accessible_datasets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Dataset Access'

    def __str__(self):
        return f"{self.dataset.title} - {self.access_type}"

class DatasetDownload(models.Model):
    dataset = models.ForeignKey(Dataset, related_name='downloads', on_delete=models.CASCADE)
    version = models.ForeignKey(DatasetVersion, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-downloaded_at']

    def __str__(self):
        return f"{self.dataset.title} - {self.user} - {self.downloaded_at}"
