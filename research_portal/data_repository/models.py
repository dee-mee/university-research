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
    version_number = models.CharField(max_length=20)  # Change to CharField for semantic versioning
    description = models.TextField()
    file_path = models.FileField(upload_to='dataset_versions/')
    file_size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['dataset', 'version_number']

    def __str__(self):
        return f"{self.dataset.title} - Version {self.version_number}"
    
    def save(self, *args, **kwargs):
        if self.file_path:
            self.file_size = self.file_path.size
        super().save(*args, **kwargs)
    
    @property
    def has_time_series(self):
        return all(key in self.metadata for key in ['time_start', 'time_end', 'time_resolution'])
    
    @property
    def time_start(self):
        return self.metadata.get('time_start')
    
    @property
    def time_end(self):
        return self.metadata.get('time_end')
    
    @property
    def time_resolution(self):
        return self.metadata.get('time_resolution')
    
    @property
    def variables(self):
        return self.metadata.get('variables', [])
    
    def get_time_series_data(self, variable=None):
        """
        Returns time series data for visualization.
        If no variable is specified, returns data for the first variable.
        """
        # This is a placeholder - in a real implementation, this would read from the actual file
        # and return properly formatted time series data
        import random
        from datetime import datetime, timedelta
        
        if not self.has_time_series:
            return None
        
        if variable is None and self.variables:
            variable = self.variables[0]
        elif variable is None:
            return None
        
        try:
            start = datetime.fromisoformat(self.time_start)
            end = datetime.fromisoformat(self.time_end)
        except (ValueError, TypeError):
            return None
        
        # Generate dummy data based on time resolution
        data_points = []
        current = start
        
        if self.time_resolution == 'daily':
            delta = timedelta(days=1)
        elif self.time_resolution == 'monthly':
            delta = timedelta(days=30)  # Approximation
        elif self.time_resolution == 'yearly':
            delta = timedelta(days=365)  # Approximation
        elif self.time_resolution == 'hourly':
            delta = timedelta(hours=1)
        else:
            delta = timedelta(days=1)  # Default to daily
        
        while current <= end:
            timestamp = int(current.timestamp() * 1000)  # Convert to milliseconds for Highcharts
            value = random.uniform(0, 100)  # Generate random value
            data_points.append([timestamp, value])
            current += delta
        
        return data_points

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
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_stacks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=True)
    datasets = models.ManyToManyField(Dataset, through='StackedDatasetItem', related_name='stacks')
    stacking_order = models.JSONField(default=list, blank=True)  # Store the order of datasets in the stack
    variables = models.JSONField(default=list, blank=True)  # Store selected variables for each dataset
    time_period = models.JSONField(default=dict, blank=True)  # Store time period settings
    spatial_resolution = models.CharField(max_length=50, blank=True)  # Target resolution for stacking
    output_format = models.CharField(max_length=50, default='netCDF')  # Output format for stacked data
    result_file = models.FileField(upload_to='stacked_datasets/', null=True, blank=True)  # Generated stacked file
    processing_time = models.DurationField(null=True, blank=True)  # How long it took to generate
    status = models.CharField(max_length=20, default='pending')  # pending, processing, completed, failed
    error_message = models.TextField(blank=True)  # If status is failed

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            
            # Ensure slug is unique
            counter = 1
            original_slug = self.slug
            while StackedDataset.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
                
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('repository:stacked_dataset_detail', kwargs={'slug': self.slug})
    
    @property
    def is_generated(self):
        return self.result_file is not None and self.status == 'completed'
    
    def get_common_variables(self):
        """Returns variables that are common across all datasets in the stack"""
        if not self.stackeddatasetitem_set.exists():
            return []
        
        # Get variables from first item
        first_item = self.stackeddatasetitem_set.first()
        if not first_item.selected_variables:
            return []
        
        common_vars = set(first_item.selected_variables)
        
        # Intersect with variables from other items
        for item in self.stackeddatasetitem_set.all()[1:]:
            if not item.selected_variables:
                return []
            common_vars.intersection_update(set(item.selected_variables))
        
        return list(common_vars)
    
    def get_time_series_data(self):
        """
        Returns time series data for the stacked dataset.
        This is a placeholder - in a real implementation, this would read from the actual file.
        """
        if not self.is_generated:
            return {}
        
        import random
        from datetime import datetime, timedelta
        
        # Get common variables
        variables = self.get_common_variables()
        if not variables:
            return {}
        
        # Parse time period
        try:
            start = datetime.fromisoformat(self.time_period.get('start', '2020-01-01'))
            end = datetime.fromisoformat(self.time_period.get('end', '2020-12-31'))
        except (ValueError, TypeError):
            start = datetime(2020, 1, 1)
            end = datetime(2020, 12, 31)
        
        # Default to daily resolution
        resolution = self.time_period.get('resolution', 'daily')
        
        # Generate dummy data for each variable
        result = {}
        for variable in variables:
            # Create different aggregations (all, year, month, day)
            result[variable] = {
                'all': generate_time_series(start, end, resolution),
                'year': generate_time_series(start, end, 'yearly'),
                'month': generate_time_series(start, end, 'monthly'),
                'day': generate_time_series(start, end, 'daily')
            }
        
        return result

class StackedDatasetItem(models.Model):
    stacked_dataset = models.ForeignKey(StackedDataset, on_delete=models.CASCADE)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    version = models.ForeignKey(DatasetVersion, on_delete=models.CASCADE, null=True, blank=True)
    order = models.IntegerField(default=0)  # Position in the stack
    selected_variables = models.JSONField(default=list, blank=True)  # Variables selected for this dataset
    time_period = models.JSONField(default=dict, blank=True)  # Time period settings for this dataset
    spatial_resolution = models.CharField(max_length=50, blank=True)  # Resolution for this dataset
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ['stacked_dataset', 'dataset', 'order']

    def __str__(self):
        version_info = f" (v{self.version.version_number})" if self.version else ""
        return f"{self.stacked_dataset.name} - {self.dataset.title}{version_info} ({self.order})"
    
    def get_time_series_data(self, variable=None):
        """Returns time series data for this item in the stack"""
        if self.version:
            return self.version.get_time_series_data(variable)
        return None

# Helper function for generating time series data
def generate_time_series(start_date, end_date, resolution='daily'):
    """Generate dummy time series data for demonstration purposes"""
    import random
    from datetime import datetime, timedelta
    
    data_points = []
    current = start_date
    
    if resolution == 'daily':
        delta = timedelta(days=1)
    elif resolution == 'monthly':
        delta = timedelta(days=30)  # Approximation
    elif resolution == 'yearly':
        delta = timedelta(days=365)  # Approximation
    elif resolution == 'hourly':
        delta = timedelta(hours=1)
    else:
        delta = timedelta(days=1)  # Default to daily
    
    while current <= end_date:
        timestamp = int(current.timestamp() * 1000)  # Convert to milliseconds for Highcharts
        value = random.uniform(0, 100)  # Generate random value
        data_points.append([timestamp, value])
        current += delta
    
    return data_points
