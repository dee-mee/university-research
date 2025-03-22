from django import forms
from .models import Dataset, DatasetVersion


class DatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ['title', 'description', 'category', 'thumbnail', 'is_featured', 'metadata']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'metadata': forms.JSONField(required=False),
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
            'metadata': forms.JSONField(required=False),
        }

    def clean_version_number(self):
        version_number = self.cleaned_data['version_number']
        if not version_number:
            raise forms.ValidationError('Version number is required.')
        return version_number

    def clean_file_path(self):
        file_path = self.cleaned_data['file_path']
        if not file_path:
            raise forms.ValidationError('File is required.')
        return file_path
