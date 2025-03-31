from django import forms
from .models import Dataset, DatasetVersion, DatasetAccess, DatasetCategory, StackedDataset, StackedDatasetItem


class DatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ['title', 'description', 'category', 'is_featured', 'thumbnail', 'metadata', 'doi', 'type', 'simulation', 'model', 'variables']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'metadata': forms.JSONField(),
            'variables': forms.JSONField(),
        }

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


class DatasetVersionForm(forms.ModelForm):
    class Meta:
        model = DatasetVersion
        fields = ['version_number', 'description', 'file_path', 'metadata']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'metadata': forms.JSONField(),
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
    class Meta:
        model = StackedDatasetItem
        fields = ['dataset', 'order', 'selected_variables', 'time_period', 'spatial_resolution']
        widgets = {
            'selected_variables': forms.JSONField(),
            'time_period': forms.JSONField(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'instance' in kwargs and kwargs['instance']:
            self.fields['dataset'].initial = kwargs['instance'].dataset
            self.fields['selected_variables'].initial = kwargs['instance'].selected_variables
            self.fields['time_period'].initial = kwargs['instance'].time_period
