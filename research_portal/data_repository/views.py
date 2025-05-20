from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q

@login_required
def my_datasets(request):
    """View to display datasets created by the current user."""
    user_datasets = Dataset.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(user_datasets, 10)  # Show 10 datasets per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'datasets': page_obj,
        'page_obj': page_obj,
        'title': 'My Datasets'
    }
    return render(request, 'data_repository/my_datasets.html', context)

@login_required
def download_history(request):
    """View to display user's download history."""
    # Get download history for the current user
    downloads = DatasetDownload.objects.filter(user=request.user).order_by('-downloaded_at')
    
    # Add dataset versions to the context for each download
    for download in downloads:
        download.version = download.dataset.versions.first()  # Get the latest version
        download.dataset_title = download.dataset.title
        download.version_size = download.version.size
    
    # Pagination
    paginator = Paginator(downloads, 10)  # Show 10 downloads per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'downloads': page_obj,
        'page_obj': page_obj,
        'title': 'Download History'
    }
    return render(request, 'data_repository/download_history.html', context)

import json
import os

# Import the models
from .models import (
    Dataset, 
    DatasetCategory, 
    DatasetVersion, 
    DatasetAccess,
    DatasetDownload,
    StackedDataset,
    StackedDatasetItem
)

# Import the forms (assuming these are defined elsewhere)
from .forms import (
    DatasetForm, 
    DatasetVersionForm, 
    StackedDatasetForm,
    StackedDatasetItemForm
)

class DatasetListView(ListView):
    model = Dataset
    template_name = 'data_repository/dataset_list.html'
    context_object_name = 'datasets'
    paginate_by = 10

    def get_queryset(self):
        queryset = Dataset.objects.all().order_by('-created_at')
        query = self.request.GET.get('q')
        
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(isimip_id__icontains=query) |
                Q(simulation_round__icontains=query) |
                Q(impact_model__icontains=query) |
                Q(climate_forcing__icontains=query)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_datasets'] = Dataset.objects.count()
        context['selected_count'] = 0  # This would be updated via JavaScript
        context['total_size'] = 0  # This would be updated via JavaScript
        return context

class DatasetDetailView(DetailView):
    model = Dataset
    template_name = 'data_repository/dataset_detail.html'
    context_object_name = 'dataset'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['versions'] = self.object.versions.all()
        return context

class DatasetCreateView(LoginRequiredMixin, CreateView):
    model = Dataset
    template_name = 'data_repository/dataset_form.html'
    fields = ['title', 'description', 'path', 'isimip_id', 'simulation_round', 
              'impact_model', 'climate_forcing', 'climate_scenario', 'bias_adjustment',
              'time_step', 'period', 'publication']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class DatasetUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Dataset
    form_class = DatasetForm
    template_name = 'data_repository/dataset_form.html'
    success_url = reverse_lazy('repository:dataset_list')

    def test_func(self):
        dataset = self.get_object()
        return dataset.created_by == self.request.user or \
               dataset.access_controls.filter(user=self.request.user, can_edit=True).exists()

class StackedDatasetListView(LoginRequiredMixin, ListView):
    model = StackedDataset
    template_name = 'data_repository/stacked_dataset_list.html'
    context_object_name = 'stacked_datasets'

    def get_queryset(self):
        return StackedDataset.objects.filter(
            Q(created_by=self.request.user) | Q(is_public=True)
        )

class StackedDatasetDetailView(LoginRequiredMixin, DetailView):
    model = StackedDataset
    template_name = 'data_repository/stacked_dataset_detail.html'
    context_object_name = 'stacked_dataset'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.stackeddatasetitem_set.all().order_by('order')
        return context

class StackedDatasetCreateView(LoginRequiredMixin, CreateView):
    model = StackedDataset
    form_class = StackedDatasetForm
    template_name = 'data_repository/stacked_dataset_form.html'
    success_url = reverse_lazy('repository:stacked_dataset_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

@login_required
def add_dataset_to_stack(request, stacked_dataset_id):
    stacked_dataset = get_object_or_404(StackedDataset, id=stacked_dataset_id)
    if request.method == 'POST':
        form = StackedDatasetItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.stacked_dataset = stacked_dataset
            item.save()
            messages.success(request, 'Dataset added to stack successfully.')
            return redirect('repository:stacked_dataset_detail', slug=stacked_dataset.slug)
    else:
        form = StackedDatasetItemForm()
    return render(request, 'data_repository/add_dataset_to_stack.html', {'form': form})

@login_required
def remove_dataset_from_stack(request, stacked_dataset_id, item_id):
    stacked_dataset = get_object_or_404(StackedDataset, id=stacked_dataset_id)
    item = get_object_or_404(StackedDatasetItem, id=item_id, stacked_dataset=stacked_dataset)
    if stacked_dataset.created_by == request.user:
        item.delete()
        messages.success(request, 'Dataset removed from stack successfully.')
    return redirect('repository:stacked_dataset_detail', slug=stacked_dataset.slug)

@login_required
def reorder_stack(request, stacked_dataset_id):
    stacked_dataset = get_object_or_404(StackedDataset, id=stacked_dataset_id)
    if request.method == 'POST' and stacked_dataset.created_by == request.user:
        new_order = request.POST.getlist('order[]')
        for index, item_id in enumerate(new_order):
            StackedDatasetItem.objects.filter(id=item_id).update(order=index)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def generate_stacked_dataset(request, stacked_dataset_id):
    stacked_dataset = get_object_or_404(StackedDataset, id=stacked_dataset_id)
    if stacked_dataset.created_by != request.user:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    # Here you would implement the actual data stacking logic
    # This could involve:
    # 1. Reading the source datasets
    # 2. Aligning spatial and temporal dimensions
    # 3. Stacking the data according to the specified order
    # 4. Saving the result in the specified format

    # For now, we'll just return a success message
    return JsonResponse({
        'status': 'success',
        'message': 'Stacked dataset generation started'
    })

@login_required
def dataset_version_create(request, dataset_id):
    """View for creating a new version of a dataset with enhanced file handling and metadata extraction."""
    dataset = get_object_or_404(Dataset, pk=dataset_id, created_by=request.user)
    
    if request.method == 'POST':
        form = DatasetVersionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Create version but don't save to DB yet
                version = form.save(commit=False)
                version.dataset = dataset
                version.created_by = request.user
                
                # Process uploaded file
                uploaded_file = request.FILES.get('file_path')
                if uploaded_file:
                    # Validate file size
                    if uploaded_file.size > 1024 * 1024 * 100:  # 100 MB limit
                        messages.error(request, 'File too large. Maximum file size is 100 MB.')
                        return render(request, 'data_repository/version_form.html', {
                            'form': form, 'dataset': dataset
                        })
                    
                    # Set file size
                    version.file_size = uploaded_file.size
                    
                    # Try to extract additional metadata based on file type
                    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                    metadata = version.metadata or {}
                    
                    try:
                        from .csv_import import extract_csv_metadata, csv_to_time_series_json
                        
                        # Extract metadata based on file type
                        if file_ext in ['.csv', '.txt']:
                            # Use our specialized CSV metadata extractor
                            csv_metadata = extract_csv_metadata(uploaded_file)
                            
                            # Add extracted metadata
                            for key, value in csv_metadata.items():
                                if key not in ['sample_rows']:  # Skip raw data
                                    metadata[key] = value
                                        
                            # Add time series data if detected
                            if csv_metadata.get('time_columns') and csv_metadata.get('value_columns'):
                                try:
                                    # Reset file pointer
                                    uploaded_file.seek(0)
                                    
                                    # Convert to time series JSON for preview
                                    time_column = csv_metadata['time_columns'][0] if csv_metadata['time_columns'] else None
                                    value_columns = csv_metadata['value_columns']
                                    
                                    # Generate time series preview
                                    time_series_data = csv_to_time_series_json(uploaded_file, time_column, value_columns)
                                    metadata['time_series_preview'] = time_series_data
                                except Exception as e:
                                    metadata['time_series_error'] = str(e)
                            
                        elif file_ext in ['.json']:
                            # Reset file position to beginning
                            uploaded_file.seek(0)
                            sample = uploaded_file.read(10000)
                            uploaded_file.seek(0)
                            
                            # Try to parse JSON structure
                            import json
                            try:
                                json_data = json.loads(sample)
                                if isinstance(json_data, dict):
                                    # Extract metadata if present in the file
                                    if 'metadata' in json_data and isinstance(json_data['metadata'], dict):
                                        file_metadata = json_data.get('metadata', {})
                                        for key, value in file_metadata.items():
                                            metadata[f'file_{key}'] = value
                                    
                                    # Look for variables
                                    if 'variables' in json_data and isinstance(json_data['variables'], list):
                                        metadata['detected_variables'] = json_data['variables']
                                    
                                    # Look for time series data
                                    if 'data' in json_data and isinstance(json_data['data'], dict):
                                        metadata['contains_time_series'] = True
                                        
                                        # Sample some variables
                                        variable_samples = []
                                        for var, data in json_data['data'].items():
                                            if isinstance(data, dict) and 'times' in data and 'values' in data:
                                                variable_samples.append(var)
                                                if len(variable_samples) >= 5:  # Limit to 5 samples
                                                    break
                                        
                                        if variable_samples:
                                            metadata['variable_samples'] = variable_samples
                                
                                metadata['file_format'] = 'json'
                            except json.JSONDecodeError:
                                # Not valid JSON or only partial content read
                                metadata['file_format'] = 'json'
                                metadata['parse_error'] = 'Could not parse JSON structure from sample'
                            
                        elif file_ext in ['.nc', '.netcdf']:
                            metadata['file_format'] = 'netcdf'
                            
                            # Try to extract NetCDF metadata if netCDF4 is available
                            try:
                                import netCDF4 as nc
                                import numpy as np
                                import tempfile
                                
                                # Save to temp file since netCDF4 needs a file path
                                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                                    for chunk in uploaded_file.chunks():
                                        tmp.write(chunk)
                                    tmp_path = tmp.name
                                
                                try:
                                    # Extract metadata from NetCDF file
                                    with nc.Dataset(tmp_path, 'r') as nc_data:
                                        # Get global attributes
                                        global_attrs = {}
                                        for attr in nc_data.ncattrs():
                                            global_attrs[attr] = nc_data.getncattr(attr)
                                        
                                        metadata['global_attributes'] = global_attrs
                                        
                                        # Get dimensions
                                        dimensions = {}
                                        for dim_name, dim in nc_data.dimensions.items():
                                            dimensions[dim_name] = {
                                                'size': len(dim),
                                                'unlimited': dim.isunlimited()
                                            }
                                        
                                        metadata['dimensions'] = dimensions
                                        
                                        # Get variables
                                        variables = []
                                        for var_name, var in nc_data.variables.items():
                                            variables.append(var_name)
                                        
                                        metadata['variables'] = variables
                                        
                                        # Look for time dimension
                                        time_var = None
                                        for var_name in nc_data.variables:
                                            if var_name.lower() == 'time' or 'time' in nc_data.variables[var_name].ncattrs():
                                                time_var = nc_data.variables[var_name]
                                                break
                                        
                                        if time_var is not None:
                                            # Try to extract time information
                                            time_attrs = {}
                                            for attr in time_var.ncattrs():
                                                time_attrs[attr] = time_var.getncattr(attr)
                                            
                                            metadata['time_attributes'] = time_attrs
                                finally:
                                    # Clean up temp file
                                    os.unlink(tmp_path)
                                    
                            except ImportError:
                                metadata['netcdf_note'] = 'NetCDF library not available for metadata extraction'
                            except Exception as e:
                                metadata['netcdf_error'] = str(e)
                                
                        elif file_ext in ['.xls', '.xlsx']:
                            metadata['file_format'] = 'excel'
                            
                            try:
                                import pandas as pd
                                
                                # Read Excel file
                                df = pd.read_excel(uploaded_file, nrows=5)
                                
                                # Get column names
                                metadata['sheet_columns'] = list(df.columns)
                                
                                # Detect possible time columns
                                time_cols = []
                                for col in df.columns:
                                    if col.lower().find('time') >= 0 or col.lower().find('date') >= 0:
                                        time_cols.append(col)
                                
                                if time_cols:
                                    metadata['possible_time_columns'] = time_cols
                                
                                # Get sheet names
                                uploaded_file.seek(0)
                                xls = pd.ExcelFile(uploaded_file)
                                metadata['sheet_names'] = xls.sheet_names
                                
                            except ImportError:
                                metadata['excel_note'] = 'Pandas library not available for Excel metadata extraction'
                            except Exception as e:
                                metadata['excel_error'] = str(e)
                        
                        # Update metadata in version
                        version.metadata = metadata
                    except Exception as e:
                        # Log error but continue with upload
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error extracting metadata: {str(e)}")
                        
                        # Add error note to metadata
                        metadata['metadata_extraction_error'] = str(e)
                        version.metadata = metadata
                
                # Set all other versions as not current
                dataset.versions.update(is_current=False)
                version.is_current = True
                
                # Save the version
                version.save()
                
                # Success message
                file_format = metadata.get('file_format', 'unknown')
                success_message = f'New version {version.version_number} uploaded successfully!'
                
                # Add additional details based on file type
                if file_format == 'csv':
                    row_count = metadata.get('row_count', 0)
                    if row_count:
                        success_message += f' Detected {row_count} rows of data.'
                    
                    col_count = len(metadata.get('headers', []))
                    if col_count:
                        success_message += f' Found {col_count} columns.'
                
                messages.success(request, success_message)
                return redirect('repository:dataset_detail', dataset_id=dataset.id)
                
            except Exception as e:
                messages.error(request, f'Error saving dataset version: {str(e)}')
                return render(request, 'data_repository/version_form.html', {
                    'form': form, 'dataset': dataset
                })
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DatasetVersionForm()
    
    return render(request, 'data_repository/version_form.html', {
        'form': form,
        'dataset': dataset
    })

def category_datasets(request, category_slug):
    category = get_object_or_404(DatasetCategory, slug=category_slug)
    datasets = Dataset.objects.filter(
        Q(category=category) | Q(category__parent=category),
        status='published'
    )
    
    return render(request, 'data_repository/category_datasets.html', {
        'category': category,
        'datasets': datasets
    })

def dataset_list(request):
    """View for listing all datasets with search and filtering."""
    datasets = Dataset.objects.all()
    categories = DatasetCategory.objects.all()
    
    # Search functionality
    query = request.GET.get('q', '')
    if query:
        datasets = datasets.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Category filter
    category_id = request.GET.get('category')
    if category_id:
        datasets = datasets.filter(category_id=category_id)
    
    # Version filter
    version_filter = request.GET.get('version_filter', 'all')
    if version_filter == 'latest':
        datasets = datasets.filter(versions__is_current=True).distinct()
    
    # Pagination
    paginator = Paginator(datasets, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'datasets': page_obj,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'version_filter': version_filter,
    }
    return render(request, 'data_repository/dataset_list.html', context)

def dataset_detail(request, dataset_id):
    """View for displaying detailed information about a specific dataset."""
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        current_version = dataset.versions.filter(is_current=True).first()
        
        context = {
            'dataset': dataset,
            'current_version': current_version,
            'versions': dataset.versions.all().order_by('-created_at'),
        }
        return render(request, 'data_repository/dataset_detail.html', context)
    except Dataset.DoesNotExist:
        return render(request, 'data_repository/dataset_not_found.html', {'dataset_id': dataset_id}, status=404)

@login_required
def dataset_download(request, dataset_id, version_id=None):
    """View for handling dataset downloads."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    if version_id:
        version = get_object_or_404(DatasetVersion, id=version_id, dataset=dataset)
    else:
        version = dataset.versions.filter(is_current=True).first()
    
    if not version:
        return HttpResponse("No version available for download", status=404)
    
    # Check access permissions
    access = DatasetAccess.objects.filter(dataset=dataset).first()
    if not access or (access.access_type == 'private' and request.user != dataset.created_by):
        return HttpResponse("Access denied", status=403)
    
    # Record download
    access.record_download(request.user)
    
    # Serve file
    response = HttpResponse(version.file, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{version.file.name}"'
    return response

@login_required
def dataset_create(request):
    """View for creating a new dataset."""
    if request.method == 'POST':
        form = DatasetForm(request.POST, request.FILES)
        if form.is_valid():
            dataset = form.save(commit=False)
            dataset.created_by = request.user
            dataset.save()
            messages.success(request, f'Dataset "{dataset.title}" was successfully created.')
            return redirect('repository:dataset_detail', dataset_id=dataset.id)
        else:
            messages.error(request, 'There was an error creating your dataset. Please check the form and try again.')
    else:
        form = DatasetForm()
    
    return render(request, 'data_repository/dataset_form.html', {'form': form})

@login_required
def version_create(request, dataset_id):
    """View for creating a new version of a dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    if request.user != dataset.created_by:
        messages.error(request, 'You do not have permission to add versions to this dataset.')
        return HttpResponse("Access denied", status=403)
    
    if request.method == 'POST':
        form = DatasetVersionForm(request.POST, request.FILES)
        if form.is_valid():
            version = form.save(commit=False)
            version.dataset = dataset
            version.created_by = request.user
            
            # Update current version
            dataset.versions.filter(is_current=True).update(is_current=False)
            version.is_current = True
            version.save()
            
            messages.success(request, f'Version {version.version_number} was successfully uploaded.')
            return redirect('repository:dataset_detail', dataset_id=dataset.id)
        else:
            messages.error(request, 'There was an error uploading your dataset version. Please check the form and try again.')
    else:
        form = DatasetVersionForm()
    
    return render(request, 'data_repository/version_form.html', {'form': form, 'dataset': dataset})

def get_dataset_details(request, dataset_id):
    """API endpoint for getting dataset details."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    current_version = dataset.versions.filter(is_current=True).first()
    
    data = {
        'id': dataset.id,
        'title': dataset.title,
        'description': dataset.description,
        'category': dataset.category.name,
        'created_by': dataset.created_by.get_full_name(),
        'created_at': dataset.created_at.isoformat(),
        'current_version': {
            'id': current_version.id,
            'version_number': current_version.version_number,
            'file_size': current_version.file_size,
            'created_at': current_version.created_at.isoformat(),
        } if current_version else None,
    }
    return JsonResponse(data)

def dataset_timeseries(request, dataset_id, variable):
    """API endpoint to get time series data for a specific variable of a dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    current_version = dataset.versions.filter(is_current=True).first()
    
    if not current_version or not current_version.has_time_series:
        return JsonResponse({'error': 'No time series data available for this dataset'}, status=404)
    
    # Get time series data for the specified variable
    time_series_data = current_version.get_time_series_data(variable)
    
    if not time_series_data:
        return JsonResponse({'error': f'No data available for variable {variable}'}, status=404)
    
    # Create response with different time aggregations
    response_data = {
        'dataset_id': dataset_id,
        'variable': variable,
        'version': current_version.version_number,
        'time_resolution': current_version.time_resolution,
        'time_start': current_version.time_start,
        'time_end': current_version.time_end,
        'data': time_series_data
    }
    
    return JsonResponse(response_data)

def api_dataset_timeseries(request, dataset_id):
    """API endpoint to get time series data for all variables of a dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    current_version = dataset.versions.filter(is_current=True).first()
    
    if not current_version or not current_version.has_time_series:
        return JsonResponse({'error': 'No time series data available for this dataset'}, status=404)
    
    # Get available variables
    variables = current_version.variables
    
    if not variables:
        return JsonResponse({'error': 'No variables available for this dataset'}, status=404)
    
    # Get time series data for all variables
    time_series_data = {}
    for variable in variables:
        variable_data = current_version.get_time_series_data(variable)
        if variable_data:
            time_series_data[variable] = {
                'all': variable_data,
                # You can add more aggregations here if needed
            }
    response_data = {
        'dataset_id': dataset_id,
        'version': current_version.version_number,
        'time_resolution': current_version.time_resolution,
        'time_start': current_version.time_start,
        'time_end': current_version.time_end,
        'variables': variables,
        'data': time_series_data
    }
    
    return JsonResponse(response_data)

@login_required
def dataset_create(request):
    """View for creating a new dataset."""
    if request.method == 'POST':
        form = DatasetForm(request.POST, request.FILES)
        if form.is_valid():
            dataset = form.save(commit=False)
            dataset.created_by = request.user
            dataset.save()
            messages.success(request, f'Dataset "{dataset.title}" was successfully created.')
            return redirect('repository:dataset_detail', dataset_id=dataset.id)
        else:
            messages.error(request, 'There was an error creating your dataset. Please check the form and try again.')
    else:
        form = DatasetForm()
    
    return render(request, 'data_repository/dataset_form.html', {'form': form})

@login_required
def version_create(request, dataset_id):
    """View for creating a new version of a dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    if request.user != dataset.created_by:
        messages.error(request, 'You do not have permission to add versions to this dataset.')
        return HttpResponse("Access denied", status=403)
    
    if request.method == 'POST':
        form = DatasetVersionForm(request.POST, request.FILES)
        if form.is_valid():
            version = form.save(commit=False)
            version.dataset = dataset
            version.created_by = request.user
            
            # Update current version
            dataset.versions.filter(is_current=True).update(is_current=False)
            version.is_current = True
            version.save()
            
            messages.success(request, f'Version {version.version_number} was successfully uploaded.')
            return redirect('repository:dataset_detail', dataset_id=dataset.id)
        else:
            messages.error(request, 'There was an error uploading your dataset version. Please check the form and try again.')
    else:
        form = DatasetVersionForm()
    
    return render(request, 'data_repository/version_form.html', {'form': form, 'dataset': dataset})

def get_dataset_details(request, dataset_id):
    """API endpoint for getting dataset details."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    current_version = dataset.versions.filter(is_current=True).first()
    
    data = {
        'id': dataset.id,
        'title': dataset.title,
        'description': dataset.description,
        'category': dataset.category.name,
        'created_by': dataset.created_by.get_full_name(),
        'created_at': dataset.created_at.isoformat(),
        'current_version': {
            'id': current_version.id,
            'version_number': current_version.version_number,
            'file_size': current_version.file_size,
            'created_at': current_version.created_at.isoformat(),
        } if current_version else None,
    }
    return JsonResponse(data)

def dataset_timeseries(request, dataset_id, variable):
    """API endpoint to get time series data for a specific variable of a dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    current_version = dataset.versions.filter(is_current=True).first()
    
    if not current_version or not current_version.has_time_series:
        return JsonResponse({'error': 'No time series data available for this dataset'}, status=404)
    
    # Get time series data for the specified variable
    time_series_data = current_version.get_time_series_data(variable)
    
    if not time_series_data:
        return JsonResponse({'error': f'No data available for variable {variable}'}, status=404)
    
    # Create response with different time aggregations
    response_data = {
        'dataset_id': dataset_id,
        'variable': variable,
        'version': current_version.version_number,
        'time_resolution': current_version.time_resolution,
        'time_start': current_version.time_start,
        'time_end': current_version.time_end,
        'data': time_series_data
    }
    
    return JsonResponse(response_data)

def api_dataset_timeseries(request, dataset_id):
    """API endpoint to get time series data for all variables of a dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    current_version = dataset.versions.filter(is_current=True).first()
    
    if not current_version or not current_version.has_time_series:
        return JsonResponse({'error': 'No time series data available for this dataset'}, status=404)
    
    # Get available variables
    variables = current_version.variables
    
    if not variables:
        return JsonResponse({'error': 'No variables available for this dataset'}, status=404)
    
    # Get time series data for all variables
    time_series_data = {}
    for variable in variables:
        variable_data = current_version.get_time_series_data(variable)
        if variable_data:
            time_series_data[variable] = {
                'all': variable_data,
                # You can add more aggregations here if needed
            }
    
    response_data = {
        'dataset_id': dataset_id,
        'version': current_version.version_number,
        'time_resolution': current_version.time_resolution,
        'time_start': current_version.time_start,
        'time_end': current_version.time_end,
        'variables': variables,
        'data': time_series_data
    }
    
    return JsonResponse(response_data)

def api_version_variables(request, version_id):
    """API endpoint to get variables available in a specific version."""
    version = get_object_or_404(DatasetVersion, id=version_id)
    
    variables = version.variables
    
    response_data = {
        'version_id': version_id,
        'dataset_id': version.dataset_id,
        'version_number': version.version_number,
        'variables': variables
    }
    
    return JsonResponse(response_data)

def api_dataset_versions(request, dataset_id):
    """API endpoint to get all versions of a specific dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    versions = dataset.versions.all().order_by('-created_at')
    
    versions_data = []
    for version in versions:
        versions_data.append({
            'id': version.id,
            'version_number': version.version_number,
            'description': version.description,
            'created_at': version.created_at.isoformat(),
            'is_current': version.is_current,
            'file_size': version.file_size,
            'has_time_series': version.has_time_series,
            'time_resolution': version.time_resolution,
            'variables': version.variables
        })
    
    response_data = {
        'dataset_id': dataset_id,
        'dataset_title': dataset.title,
        'versions_count': len(versions_data),
        'versions': versions_data
    }
    
    return JsonResponse(response_data)

@login_required
def delete_stacked_dataset(request, stacked_dataset_id):
    """View for deleting a stacked dataset."""
    stacked_dataset = get_object_or_404(StackedDataset, id=stacked_dataset_id)
    
    # Only allow the creator to delete the stacked dataset
    if stacked_dataset.created_by != request.user:
        messages.error(request, 'You do not have permission to delete this stacked dataset.')
        return redirect('repository:stacked_dataset_list')
    
    if request.method == 'POST':
        # Delete associated file if it exists
        if stacked_dataset.result_file:
            try:
                stacked_dataset.result_file.delete()
            except Exception as e:
                # Log the exception but continue with deletion
                print(f"Error deleting file: {e}")
        
        # Delete the stacked dataset
        stacked_dataset.delete()
        messages.success(request, 'Stacked dataset was successfully deleted.')
        return redirect('repository:stacked_dataset_list')
    else:
        # If accessed with GET request, redirect to confirmation page or just redirect to list
        # For simplicity, we're just redirecting to the list view
        # You might want to implement a confirmation page in a real application
        return redirect('repository:stacked_dataset_list')

@login_required
def create_stack_from_selection(request):
    """Creates a new stack from selected datasets."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        name = data.get('name')
        description = data.get('description', '')
        is_public = data.get('is_public', True)
        datasets = data.get('datasets', [])
        
        # Validate inputs
        if not name:
            return JsonResponse({'success': False, 'error': 'Stack name is required'}, status=400)
        
        if not datasets:
            return JsonResponse({'success': False, 'error': 'No datasets selected'}, status=400)
        
        # Create the stacked dataset
        stacked_dataset = StackedDataset.objects.create(
            name=name,
            description=description,
            is_public=is_public,
            created_by=request.user
        )
        
        # Add selected datasets to the stack
        for i, dataset_info in enumerate(datasets):
            dataset_id = dataset_info.get('id')
            version_id = dataset_info.get('version_id')
            
            dataset = get_object_or_404(Dataset, id=dataset_id)
            
            # Create stacked dataset item
            item = StackedDatasetItem(
                stacked_dataset=stacked_dataset,
                dataset=dataset,
                order=i
            )
            
            # If a specific version was selected, try to set it
            if version_id:
                try:
                    # Use the attribute we added in the form for dataset_version_id
                    item.dataset_version_id = int(version_id)
                except (ValueError, TypeError):
                    pass
            
            item.save()
        
        return JsonResponse({
            'success': True, 
            'redirect_url': reverse_lazy('repository:stacked_dataset_detail', kwargs={'slug': stacked_dataset.slug})
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_GET
def get_time_series_data(request, version_id):
    """API endpoint to retrieve time series data for visualization"""
    try:
        # Get the dataset version
        version = DatasetVersion.objects.get(id=version_id)
        
        # Check if user has access to this dataset
        # Instead of automatically redirecting to login, return a proper JSON response
        if not request.user.is_authenticated:
            # For datasets that require login
            dataset_status = getattr(version.dataset, 'status', 'private')
            if dataset_status != 'published':
                return JsonResponse({'error': 'Authentication required'}, status=401)
        
        # If we get here, either the user is authenticated or the dataset is public
        
        # Extract time series data from the dataset file
        result = {}
        
        # Check file format and metadata
        if not version.file_path:
            return JsonResponse({'error': 'No file available'}, status=404)
            
        file_format = version.metadata.get('format', '').lower() if version.metadata else ''
        file_path = version.file_path.path
        
        if file_format == 'json' or file_path.lower().endswith('.json'):
            # Read JSON file
            try:
                with open(file_path, 'r') as f:
                    file_data = json.load(f)
                    
                # Extract data from our JSON format
                if 'data' in file_data and isinstance(file_data['data'], dict):
                    for variable, data in file_data['data'].items():
                        if 'times' in data and 'values' in data:
                            result[variable] = {
                                'times': data['times'],
                                'values': data['values'],
                            }
            except Exception as e:
                return JsonResponse({'error': f'Error reading JSON data: {str(e)}'}, status=500)
                
        elif file_format == 'csv' or file_path.lower().endswith('.csv'):
            # Read CSV file
            try:
                import pandas as pd
                df = pd.read_csv(file_path)
                
                # Extract data from columns (assuming first column is date/time)
                date_col = df.columns[0]
                for column in df.columns[1:]:  # Skip the date column
                    result[column] = {
                        'times': df[date_col].tolist(),
                        'values': df[column].tolist()
                    }
            except Exception as e:
                return JsonResponse({'error': f'Error reading CSV data: {str(e)}'}, status=500)
                
        elif file_format == 'netcdf' or file_path.lower().endswith('.nc'):
            # Read NetCDF file
            try:
                import netCDF4 as nc
                import numpy as np
                from datetime import datetime, timedelta
                
                with nc.Dataset(file_path, 'r') as nc_data:
                    # Get time variable and units
                    time_var = nc_data.variables.get('time')
                    if time_var is None:
                        for var_name in nc_data.variables:
                            if 'time' in var_name.lower():
                                time_var = nc_data.variables[var_name]
                                break
                    
                    # Convert time to datetime objects
                    if time_var is not None:
                        time_units = time_var.units
                        calendar = getattr(time_var, 'calendar', 'standard')
                        
                        # Extract reference date from units (e.g., "days since 2000-01-01")
                        try:
                            units_parts = time_units.split('since')
                            if len(units_parts) > 1:
                                ref_date_str = units_parts[1].strip()
                                ref_date = nc.num2date(0, time_units, calendar)
                                
                                times = nc.num2date(time_var[:], time_units, calendar)
                                time_strings = [t.isoformat() for t in times]
                                
                                # For each variable, extract data
                                for var_name, variable in nc_data.variables.items():
                                    # Skip non-data variables (like dimensions)
                                    if var_name != 'time' and len(variable.shape) > 0:
                                        # Only include variables with time dimension
                                        if variable.shape[0] == len(time_strings):
                                            # Convert to float for JSON serialization 
                                            values = variable[:].data.tolist() if hasattr(variable[:], 'data') else variable[:].tolist()
                                            result[var_name] = {
                                                'times': time_strings,
                                                'values': values
                                            }
                        except Exception as e:
                            # If time extraction fails, just read raw data
                            for var_name, variable in nc_data.variables.items():
                                if var_name != 'time' and len(variable.shape) > 0:
                                    values = variable[:].data.tolist() if hasattr(variable[:], 'data') else variable[:].tolist()
                                    pseudo_times = list(range(len(values)))
                                    result[var_name] = {
                                        'times': pseudo_times,
                                        'values': values
                                    }
            except Exception as e:
                return JsonResponse({'error': f'Error reading NetCDF data: {str(e)}'}, status=500)
                
        # If no data was extracted, return an empty object with error message
        if not result:
            return JsonResponse({'error': 'No time series data found in file'}, status=404)
            
        return JsonResponse(result)
    
    except DatasetVersion.DoesNotExist:
        return JsonResponse({'error': 'Dataset version not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Function to check if user has access to a dataset
def has_access_to_dataset(user, dataset):
    # Public datasets are accessible to all authenticated users
    if dataset.status == 'published':
        return True
    # Owner always has access
    if dataset.created_by == user:
        return True
    # Admin always has access
    if user.is_staff:
        return True
    # Check for specific access grants
    return DatasetAccess.objects.filter(dataset=dataset, user=user).exists()
