from django import forms
from .models import Dataset, DatasetVersion, DatasetAccess, DatasetCategory, StackedDataset, StackedDatasetItem
import json


class DatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ['title', 'description', 'category', 'is_featured', 'thumbnail', 'metadata', 'doi', 'type', 'simulation', 'model', 'variables']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'metadata': forms.Textarea(attrs={'class': 'json-editor', 'rows': 5}),
            'variables': forms.Textarea(attrs={'class': 'json-editor', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure category field has all available choices from DatasetCategory
        if 'category' in self.fields:
            self.fields['category'].queryset = DatasetCategory.objects.all()
    
    def clean_title(self):
        title = self.cleaned_data['title']
        if len(title) < 3:
            raise forms.ValidationError('Title must be at least 3 characters long.')
        return title

    def clean_description(self):
        description = self.cleaned_data['description']
        if len(description) < 10:
            raise forms.ValidationError('Description must be at least 10 characters long.')
        return description
    
    def clean_metadata(self):
        metadata = self.cleaned_data['metadata']
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except json.JSONDecodeError:
                raise forms.ValidationError('Invalid JSON format')
        return metadata
    
    def clean_variables(self):
        variables = self.cleaned_data['variables']
        if isinstance(variables, str):
            try:
                return json.loads(variables)
            except json.JSONDecodeError:
                raise forms.ValidationError('Invalid JSON format')
        return variables


class DatasetVersionForm(forms.ModelForm):
    time_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    time_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    time_resolution = forms.ChoiceField(
        choices=[
            ('', '-- Select Resolution --'),
            ('daily', 'Daily'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
            ('hourly', 'Hourly'),
            ('custom', 'Custom')
        ],
        required=False
    )
    variables = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'temperature, precipitation, etc.'}),
        required=False,
        help_text="Comma-separated list of variables included in this dataset"
    )
    
    class Meta:
        model = DatasetVersion
        fields = ['version_number', 'description', 'file_path', 'metadata']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'metadata': forms.Textarea(attrs={'class': 'json-editor', 'rows': 5}),
        }

    def clean_version_number(self):
        version_number = self.cleaned_data['version_number']
        if not version_number:
            raise forms.ValidationError('Version number is required.')
        return version_number

    def clean_file_path(self):
        file_path = self.cleaned_data['file_path']
        if not file_path:
            raise forms.ValidationError('File path is required.')
        return file_path
    
    def clean_metadata(self):
        metadata = self.cleaned_data['metadata']
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except json.JSONDecodeError:
                raise forms.ValidationError('Invalid JSON format')
        return metadata
    
    def clean_variables(self):
        variables = self.cleaned_data.get('variables')
        if variables:
            return [v.strip() for v in variables.split(',')]
        return []
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Add time series data to metadata
        metadata = instance.metadata or {}
        
        if self.cleaned_data.get('time_start'):
            metadata['time_start'] = self.cleaned_data['time_start'].isoformat()
        
        if self.cleaned_data.get('time_end'):
            metadata['time_end'] = self.cleaned_data['time_end'].isoformat()
        
        if self.cleaned_data.get('time_resolution'):
            metadata['time_resolution'] = self.cleaned_data['time_resolution']
        
        if self.cleaned_data.get('variables'):
            metadata['variables'] = self.clean_variables()
        
        instance.metadata = metadata
        
        if commit:
            instance.save()
        
        return instance


class DatasetAccessForm(forms.ModelForm):
    class Meta:
        model = DatasetAccess
        fields = ['user', 'can_edit', 'can_delete', 'can_share']


class StackedDatasetForm(forms.ModelForm):
    class Meta:
        model = StackedDataset
        fields = ['name', 'description', 'is_public', 'spatial_resolution', 'output_format']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class StackedDatasetItemForm(forms.ModelForm):
    selected_variables = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'temperature, precipitation, etc.'}),
        required=False,
        help_text="Comma-separated list of variables to include from this dataset"
    )
    time_period_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    time_period_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    class Meta:
        model = StackedDatasetItem
        fields = ['dataset', 'order', 'spatial_resolution']  # Removed 'version' field
        widgets = {
            'dataset': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'spatial_resolution': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 0.5° x 0.5°'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'instance' in kwargs and kwargs['instance']:
            self.fields['dataset'].initial = kwargs['instance'].dataset
            if kwargs['instance'].selected_variables:
                self.fields['selected_variables'].initial = ', '.join(kwargs['instance'].selected_variables)
            if kwargs['instance'].time_period:
                if 'start' in kwargs['instance'].time_period:
                    self.fields['time_period_start'].initial = kwargs['instance'].time_period['start']
                if 'end' in kwargs['instance'].time_period:
                    self.fields['time_period_end'].initial = kwargs['instance'].time_period['end']

        # Add dataset version choices dynamically
        if 'dataset' in self.fields:
            self.fields['dataset_version'] = forms.ChoiceField(
                label="Dataset Version",
                choices=[],
                required=False,
                widget=forms.Select(attrs={'class': 'form-select'})
            )

            # If we have initial dataset, populate versions
            if self.instance and self.instance.dataset_id:
                dataset = self.instance.dataset
                versions = dataset.versions.all()
                self.fields['dataset_version'].choices = [(v.id, v.version_number) for v in versions]
                
                # Set initial version if it exists
                if hasattr(self.instance, 'dataset_version_id') and self.instance.dataset_version_id:
                    self.fields['dataset_version'].initial = self.instance.dataset_version_id
    
    def clean_selected_variables(self):
        vars_input = self.cleaned_data.get('selected_variables')
        if vars_input:
            return [v.strip() for v in vars_input.split(',')]
        return []
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set selected variables
        instance.selected_variables = self.clean_selected_variables()
        
        # Set time period
        time_period = {}
        if self.cleaned_data.get('time_period_start'):
            time_period['start'] = self.cleaned_data['time_period_start'].isoformat()
        if self.cleaned_data.get('time_period_end'):
            time_period['end'] = self.cleaned_data['time_period_end'].isoformat()
        
        instance.time_period = time_period
        
        # Handle version if present in model
        if 'dataset_version' in self.cleaned_data and self.cleaned_data['dataset_version']:
            try:
                instance.dataset_version_id = int(self.cleaned_data['dataset_version'])
            except (ValueError, TypeError):
                pass
        
        if commit:
            instance.save()
        
        return instance
