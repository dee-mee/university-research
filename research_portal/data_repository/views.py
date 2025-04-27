from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.db.models import Q, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Dataset, DatasetCategory, DatasetVersion, DatasetAccess, DatasetDownload, StackedDataset, StackedDatasetItem
from .forms import DatasetForm, DatasetVersionForm, DatasetAccessForm, StackedDatasetForm, StackedDatasetItemForm
import json

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
    dataset = get_object_or_404(Dataset, pk=dataset_id, created_by=request.user)
    
    if request.method == 'POST':
        form = DatasetVersionForm(request.POST, request.FILES)
        if form.is_valid():
            version = form.save(commit=False)
            version.dataset = dataset
            version.created_by = request.user
            
            # Set all other versions as not current
            dataset.versions.update(is_current=False)
            version.is_current = True
            version.save()
            
            messages.success(request, 'New version uploaded successfully.')
            return redirect('repository:dataset_detail', slug=dataset.slug)
    else:
        form = DatasetVersionForm()
    
    return render(request, 'data_repository/version_form.html', {
        'form': form,
        'dataset': dataset
    })

@login_required
def dataset_download(request, dataset_id, version_id):
    dataset = get_object_or_404(Dataset, pk=dataset_id)
    version = get_object_or_404(DatasetVersion, pk=version_id, dataset=dataset)
    
    # Check access permissions
    access = DatasetAccess.objects.get_or_create(dataset=dataset)[0]
    if access.access_type != 'public' and request.user != dataset.created_by and request.user not in access.allowed_users.all():
        messages.error(request, 'You do not have permission to download this dataset.')
        return redirect('repository:dataset_detail', slug=dataset.slug)
    
    # Record the download
    DatasetDownload.objects.create(
        dataset=dataset,
        version=version,
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Serve the file
    try:
        response = FileResponse(version.file_path, as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{version.file_path.name}"'
        return response
    except Exception as e:
        messages.error(request, 'Error downloading file. Please try again later.')
        return redirect('repository:dataset_detail', slug=dataset.slug)

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
