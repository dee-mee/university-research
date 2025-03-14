# forms.py
from django import forms

class CSVUploadForm(forms.Form):
    IMPORT_CHOICES = [
        ('stations', 'Weather Stations'),
        ('climate_data', 'Climate Data'),
    ]
    
    import_type = forms.ChoiceField(
        choices=IMPORT_CHOICES,
        label="Import Type",
        widget=forms.RadioSelect,
        initial='stations',
        help_text="Select the type of data you want to import."
    )
    
    csv_file = forms.FileField(
        label="CSV File",
        help_text="Select a CSV file to upload. Make sure it has the required fields."
    )


class FlashDriveImportForm(forms.Form):
    IMPORT_CHOICES = [
        ('stations', 'Weather Stations'),
        ('climate_data', 'Climate Data'),
    ]
    
    import_type = forms.ChoiceField(
        choices=IMPORT_CHOICES,
        label="Import Type",
        widget=forms.RadioSelect,
        initial='stations',
        help_text="Select the type of data you want to import."
    )
    
    drive_path = forms.CharField(
        label="Flash Drive Path",
        initial="/media/usb",
        help_text="Enter the path where the flash drive is mounted."
    )