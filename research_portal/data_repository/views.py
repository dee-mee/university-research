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
        form = DatasetForm(request.POST)
        if form.is_valid():
            dataset = form.save(commit=False)
            dataset.created_by = request.user
            dataset.save()
            return redirect('repository:dataset_detail', dataset_id=dataset.id)
    else:
        form = DatasetForm()
    
    return render(request, 'data_repository/dataset_form.html', {'form': form})

@login_required
def version_create(request, dataset_id):
    """View for creating a new version of a dataset."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    if request.user != dataset.created_by:
        return HttpResponse("Access denied", status=403)
    
    if request.method == 'POST':
        form = DatasetVersionForm(request.POST, request.FILES)
        if form.is_valid():
            version = form.save(commit=False)
            version.dataset = dataset
            version.save()
            
            # Update current version
            dataset.versions.filter(is_current=True).update(is_current=False)
            version.is_current = True
            version.save()
            
            return redirect('repository:dataset_detail', dataset_id=dataset.id)
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
