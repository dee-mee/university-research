"""
Views for the integration app

This module provides views for the integration between the data_repository and maps apps,
focusing on unified data import/export capabilities.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.files.uploadedfile import UploadedFile
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.utils import timezone
from datetime import timedelta

from maps.models import WeatherStation, ClimateData
from data_repository.models import Dataset, DatasetVersion
from .api_integration import (
    fetch_integrated_data, 
    unified_search, 
    get_datasets_by_station,
    get_stations_by_dataset,
    process_station_data_to_repository
)
from .data_connector import DataConnector, detect_file_format, convert_format


@login_required
def unified_import_view(request):
    """
    Unified view for importing data to either maps or data_repository app
    """
    if request.method == 'POST':
        # Process the form submission
        target_app = request.POST.get('target_app', 'maps')
        model_name = request.POST.get('model_name', '')
        id_field = request.POST.get('id_field', '')
        
        # Validate required fields
        if not model_name:
            messages.error(request, "Please specify a model name")
            return redirect('integration:unified_import')
        
        # Process file upload
        if 'file' not in request.FILES:
            messages.error(request, "Please select a file to upload")
            return redirect('integration:unified_import')
            
        upload_file = request.FILES['file']
        
        # Auto-detect file format if not specified
        file_format = request.POST.get('file_format', '')
        if not file_format:
            file_format = detect_file_format(upload_file)
        
        # Check if we need to convert the file format
        should_convert = request.POST.get('auto_convert', 'false') == 'true'
        
        # Get field mapping if provided
        mapping = {}
        for key, value in request.POST.items():
            if key.startswith('map_'):
                field_name = key[4:]  # Remove 'map_' prefix
                if value:  # Only add if a mapping was provided
                    mapping[field_name] = value
        
        # Import the data using the connector
        result = DataConnector.import_data(
            upload_file,
            file_format,
            target_app,
            model_name,
            id_field=id_field if id_field else None,
            mapping=mapping if mapping else None,
            convert=should_convert,
            validate=True
        )
        
        # Display results
        if result['success'] > 0:
            messages.success(
                request, 
                f"Successfully imported {result['success']} records "
                f"({result['error']} errors)"
            )
        else:
            messages.error(
                request, 
                f"Import failed: {result['errors'][0] if result['errors'] else 'Unknown error'}"
            )
            
        # Add warnings if any
        for warning in result.get('warnings', [])[:5]:  # Show only first 5 warnings
            messages.warning(request, warning)
        
        # Redirect back to the import form with the same parameters
        return redirect('integration:unified_import')
        
    # GET request - show the import form
    # Get available models for each app
    maps_models = [
        ('weather_station', 'Weather Station'),
        ('climate_data', 'Climate Data'),
        ('weather_data_type', 'Weather Data Type'),
        ('country', 'Country'),
        ('field_device', 'Field Device'),
        ('device_type', 'Device Type'),
    ]
    
    repository_models = [
        ('dataset', 'Dataset'),
        ('dataset_version', 'Dataset Version'),
        ('dataset_category', 'Dataset Category'),
        ('stacked_dataset', 'Stacked Dataset'),
    ]
    
    context = {
        'maps_models': maps_models,
        'repository_models': repository_models,
        'supported_formats': [
            ('auto', 'Auto-detect'),
            ('csv', 'CSV'),
            ('json', 'JSON'),
            ('excel', 'Excel'),
        ]
    }
    
    return render(request, 'integration/unified_import.html', context)


@login_required
@require_POST
def check_file_format(request):
    """
    AJAX endpoint to check the format of an uploaded file
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
        
    upload_file = request.FILES['file']
    
    # Use the utility to detect format
    file_format = detect_file_format(upload_file)
    
    # For certain formats, also extract field names
    fields = []
    
    if file_format == 'csv':
        try:
            # Use the CSV import utility to extract headers
            from data_repository.csv_import import extract_csv_metadata
            metadata = extract_csv_metadata(upload_file)
            fields = metadata.get('headers', [])
        except Exception as e:
            return JsonResponse({
                'format': file_format,
                'error': f"Error extracting fields: {str(e)}"
            })
    elif file_format == 'json':
        try:
            # Use the JSON import utility to extract fields
            from data_repository.json_import import extract_json_metadata
            metadata = extract_json_metadata(upload_file)
            fields = metadata.get('keys', [])
        except Exception as e:
            return JsonResponse({
                'format': file_format,
                'error': f"Error extracting fields: {str(e)}"
            })
    
    # Return the detected format and fields
    return JsonResponse({
        'format': file_format,
        'fields': fields
    })


@login_required
def sync_data_view(request):
    """View for synchronizing data between maps and data_repository apps"""
    if request.method == 'POST':
        action = request.POST.get('action', '')
        
        if action == 'sync_weather_data':
            # Get list of station IDs if provided
            station_ids = request.POST.get('station_ids', '')
            station_id_list = [int(id.strip()) for id in station_ids.split(',') if id.strip()] if station_ids else None
            
            # Call the sync function
            result = DataConnector.sync_weather_data_to_repository(station_ids=station_id_list)
            
            if result['errors']:
                messages.error(request, f"Sync completed with errors: {result['errors'][0]}")
            else:
                messages.success(
                    request, 
                    f"Successfully synced data: {result['datasets_created']} datasets created, "
                    f"{result['datasets_updated']} datasets updated"
                )
        
        return redirect('integration:sync_data')
    
    # GET request - show the sync form
    from maps.models import WeatherStation
    
    context = {
        'weather_stations': WeatherStation.objects.all(),
    }
    
    return render(request, 'integration/sync_data.html', context)


@login_required
@require_POST
def api_import(request):
    """API endpoint for importing data programmatically"""
    # Check for file
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
        
    # Get parameters
    target_app = request.POST.get('target_app', 'maps')
    model_name = request.POST.get('model_name', '')
    id_field = request.POST.get('id_field', '')
    file_format = request.POST.get('file_format', '')
    convert = request.POST.get('convert', 'false') == 'true'
    
    # Validate model name
    if not model_name:
        return JsonResponse({'error': 'Model name is required'}, status=400)
    
    # Get the file
    upload_file = request.FILES['file']
    
    # Auto-detect format if not specified
    if not file_format:
        file_format = detect_file_format(upload_file)
    
    # Process field mapping if provided
    mapping = {}
    for key, value in request.POST.items():
        if key.startswith('map_') and value:
            field_name = key[4:]  # Remove 'map_' prefix
            mapping[field_name] = value
    
    # Import the data
    result = DataConnector.import_data(
        upload_file,
        file_format,
        target_app,
        model_name,
        id_field=id_field if id_field else None,
        mapping=mapping if mapping else None,
        convert=convert,
        validate=True
    )
    
    # Return the result
    return JsonResponse(result)


@login_required
def export_data_view(request):
    """View for exporting data from either maps or data_repository app"""
    if request.method == 'POST':
        # Process export request
        source_app = request.POST.get('source_app', 'maps')
        model_name = request.POST.get('model_name', '')
        export_format = request.POST.get('export_format', 'json')
        include_related = request.POST.get('include_related', 'false') == 'true'
        
        # Validate required fields
        if not model_name:
            messages.error(request, "Please specify a model name")
            return redirect('integration:export_data')
        
        # Process query parameters
        query_params = {}
        for key, value in request.POST.items():
            if key.startswith('filter_') and value:
                field_name = key[7:]  # Remove 'filter_' prefix
                query_params[field_name] = value
        
        # Export the data
        content, content_format, filename = DataConnector.export_data(
            source_app,
            model_name,
            query_params=query_params,
            format=export_format,
            include_related=include_related
        )
        
        if not content:
            messages.error(request, "Export failed. See logs for details.")
            return redirect('integration:export_data')
        
        # Return the file as a download
        response = HttpResponse(content, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    # GET request - show export form
    # Get available models for each app
    maps_models = [
        ('weather_station', 'Weather Station'),
        ('climate_data', 'Climate Data'),
        ('weather_data_type', 'Weather Data Type'),
        ('country', 'Country'),
        ('field_device', 'Field Device'),
        ('device_type', 'Device Type'),
    ]
    
    repository_models = [
        ('dataset', 'Dataset'),
        ('dataset_version', 'Dataset Version'),
        ('dataset_category', 'Dataset Category'),
    ]
    
    context = {
        'maps_models': maps_models,
        'repository_models': repository_models,
        'export_formats': [
            ('json', 'JSON'),
            ('csv', 'CSV'),
            ('geojson', 'GeoJSON (for Weather Stations)'),
        ]
    }
    
    return render(request, 'integration/export_data.html', context)


class IntegratedDashboardView(LoginRequiredMixin, TemplateView):
    """Unified dashboard showing both maps and data repository content"""
    template_name = 'integration/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get active weather stations
        context['active_stations'] = WeatherStation.objects.filter(is_active=True).count()
        
        # Get total stations
        context['total_stations'] = WeatherStation.objects.count()
        
        # Get recent datasets from repository
        context['recent_datasets'] = Dataset.objects.all().order_by('-created_at')[:5]
        
        # Get featured datasets
        context['featured_datasets'] = Dataset.objects.filter(is_featured=True)[:3]
        
        # Get total datasets
        context['dataset_count'] = Dataset.objects.count()
        
        # Get latest climate data records
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)
        context['recent_data_count'] = ClimateData.objects.filter(
            timestamp__range=(start_date, end_date)
        ).count()
        
        return context


class StationWithDatasetsView(LoginRequiredMixin, DetailView):
    """Show a weather station with its associated datasets"""
    model = WeatherStation
    template_name = 'integration/station_with_datasets.html'
    context_object_name = 'station'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        station = self.get_object()
        
        # Get datasets linked to this station
        context['datasets'] = get_datasets_by_station(station.id)
        
        # Get climate data for visualization
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        context['climate_data'] = ClimateData.objects.filter(
            station=station, 
            timestamp__range=(start_date, end_date)
        ).order_by('timestamp')
        
        return context


class DatasetWithStationsView(LoginRequiredMixin, DetailView):
    """Show a dataset with the weather stations that contributed to it"""
    model = Dataset
    template_name = 'integration/dataset_with_stations.html'
    context_object_name = 'dataset'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dataset = self.get_object()
        
        # Get stations linked to this dataset
        context['stations'] = get_stations_by_dataset(dataset.id)
        
        # Get latest version of the dataset
        latest_version = DatasetVersion.objects.filter(
            dataset=dataset
        ).order_by('-version_number').first()
        context['latest_version'] = latest_version
        
        # Check if dataset has spatial attributes
        context['has_location'] = dataset.location is not None
        context['has_bounding_box'] = dataset.bounding_box is not None
        
        return context


class UnifiedSearchView(LoginRequiredMixin, TemplateView):
    """Search across both Maps and Data Repository"""
    template_name = 'integration/unified_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        
        if query:
            # Get search results using unified search
            context['search_results'] = unified_search(query)
            context['query'] = query
        
        return context


def integrated_data_api(request):
    """API endpoint for integrated data access"""
    station_id = request.GET.get('station_id')
    dataset_id = request.GET.get('dataset_id')
    
    # Get time range from request if provided
    time_range = None
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date and end_date:
        try:
            from django.utils.dateparse import parse_datetime
            time_range = (parse_datetime(start_date), parse_datetime(end_date))
        except (ValueError, TypeError):
            pass
    
    # Get integrated data
    result = fetch_integrated_data(
        station_id=station_id,
        dataset_id=dataset_id,
        time_range=time_range
    )
    
    return JsonResponse(result)


def export_station_to_repository_view(request, station_id):
    """View for exporting station data to repository"""
    if request.method != 'POST':
        # Only process POST requests
        return redirect('maps:station_detail', station_id=station_id)
    
    # Get station
    station = get_object_or_404(WeatherStation, id=station_id)
    
    # Get form data
    title = request.POST.get('title', f"Weather data from {station.name}")
    description = request.POST.get('description', '')
    category_id = request.POST.get('category_id')
    
    # Process the export
    dataset, created, message = process_station_data_to_repository(
        station_id=station_id,
        creator_id=request.user.id,
        title=title,
        description=description,
        category_id=category_id if category_id else None
    )
    
    if dataset:
        from django.contrib import messages
        if created:
            messages.success(request, f"Successfully created new dataset '{dataset.title}' in the repository")
        else:
            messages.info(request, f"Updated existing dataset '{dataset.title}' in the repository")
        
        # Redirect to the dataset detail page
        return redirect('repository:dataset_detail', pk=dataset.id)
    else:
        # Error occurred
        from django.contrib import messages
        messages.error(request, f"Failed to export data: {message}")
        return redirect('maps:station_detail', station_id=station_id)