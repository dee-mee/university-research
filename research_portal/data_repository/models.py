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

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    category = models.ForeignKey(DatasetCategory, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
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
    
    # ISIMIP specific fields
    path = models.CharField(max_length=500, blank=True)
    isimip_id = models.CharField(max_length=200, blank=True)
    simulation_round = models.CharField(max_length=50, blank=True)
    impact_model = models.CharField(max_length=100, blank=True)
    climate_forcing = models.CharField(max_length=100, blank=True)
    climate_scenario = models.CharField(max_length=100, blank=True)
    data_product = models.CharField(max_length=100, blank=True)
    bias_adjustment = models.CharField(max_length=50, blank=True)
    time_step = models.CharField(max_length=50, blank=True)
    period = models.CharField(max_length=50, blank=True)
    publication = models.URLField(blank=True)

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
        return reverse('repository:dataset_detail', kwargs={'pk': self.pk})

class DatasetVersion(models.Model):
    dataset = models.ForeignKey(Dataset, related_name='versions', on_delete=models.CASCADE)
    version_number = models.IntegerField()
    description = models.TextField()
    file_path = models.FileField(upload_to='dataset_versions/')
    file_size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-version_number']
        unique_together = ['dataset', 'version_number']

    def __str__(self):
        return f"{self.dataset.title} - Version {self.version_number}"

    def save(self, *args, **kwargs):
        if self.file_path:
            self.file_size = self.file_path.size
        super().save(*args, **kwargs)

class DatasetAccess(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='access_controls')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_share = models.BooleanField(default=False)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='granted_access')

    class Meta:
        unique_together = ['dataset', 'user']

    def __str__(self):
        return f"{self.dataset.title} - {self.user.username}"

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

class StackedDataset(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_stacks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=True)
    datasets = models.ManyToManyField(Dataset, through='StackedDatasetItem', related_name='stacks')
    stacking_order = models.JSONField(default=list)  # Store the order of datasets in the stack
    variables = models.JSONField(default=list)  # Store selected variables for each dataset
    time_period = models.JSONField(default=dict)  # Store time period settings for each dataset
    spatial_resolution = models.CharField(max_length=50, blank=True)  # Target resolution for stacking
    output_format = models.CharField(max_length=50, default='netCDF')  # Output format for stacked data

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('repository:stacked_dataset_detail', kwargs={'slug': self.slug})

class StackedDatasetItem(models.Model):
    stacked_dataset = models.ForeignKey(StackedDataset, on_delete=models.CASCADE)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    order = models.IntegerField()  # Position in the stack
    selected_variables = models.JSONField(default=list)  # Variables selected for this dataset
    time_period = models.JSONField(default=dict)  # Time period settings for this dataset
    spatial_resolution = models.CharField(max_length=50, blank=True)  # Resolution for this dataset
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ['stacked_dataset', 'dataset', 'order']

    def __str__(self):
        return f"{self.stacked_dataset.name} - {self.dataset.title} ({self.order})"
