from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Dataset, DatasetCategory, DatasetVersion, DatasetAccess, DatasetDownload
from .forms import DatasetForm, DatasetVersionForm

class DatasetListView(ListView):
    model = Dataset
    template_name = 'data_repository/dataset_list.html'
    context_object_name = 'datasets'
    paginate_by = 10

    def get_queryset(self):
        queryset = Dataset.objects.filter(status='published')
        
        # Search functionality
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(metadata__icontains=q) |
                Q(doi__icontains=q)
            )

        # Version filter
        version_filter = self.request.GET.get('version_filter', 'latest')
        if version_filter == 'latest':
            queryset = queryset.filter(versions__is_current=True)

        # Show archived files
        show_archived = self.request.GET.get('show_archived') == 'on'
        if not show_archived:
            queryset = queryset.filter(is_archived=False)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all main categories with their subcategories
        context['categories'] = DatasetCategory.objects.filter(parent=None).prefetch_related('subcategories')
        
        # View type (tree or facets)
        context['view_type'] = self.request.GET.get('view', 'tree')
        
        # Version filter
        context['version_filter'] = self.request.GET.get('version_filter', 'latest')
        
        # Show archived files
        context['show_archived'] = self.request.GET.get('show_archived') == 'on'
        
        # Selection info
        selected_datasets = self.request.GET.getlist('selected_datasets')
        context['selected_count'] = len(selected_datasets)
        
        # Calculate total size of selected datasets
        if selected_datasets:
            total_size = DatasetVersion.objects.filter(
                dataset_id__in=selected_datasets,
                is_current=True
            ).aggregate(total=Sum('file_size'))['total'] or 0
            context['total_size'] = total_size
        
        # Total datasets count
        context['total_datasets'] = Dataset.objects.filter(status='published').count()
        
        return context

class DatasetDetailView(DetailView):
    model = Dataset
    template_name = 'data_repository/dataset_detail.html'
    context_object_name = 'dataset'

    def get_queryset(self):
        return super().get_queryset().select_related('category', 'created_by')

class DatasetCreateView(LoginRequiredMixin, CreateView):
    model = Dataset
    form_class = DatasetForm
    template_name = 'data_repository/dataset_form.html'
    success_url = reverse_lazy('repository:dataset_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Dataset created successfully.')
        return super().form_valid(form)

class DatasetUpdateView(LoginRequiredMixin, UpdateView):
    model = Dataset
    form_class = DatasetForm
    template_name = 'data_repository/dataset_form.html'
    success_url = reverse_lazy('repository:dataset_list')

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Dataset updated successfully.')
        return super().form_valid(form)

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
    
    # Record the download
    DatasetDownload.objects.create(
        dataset=dataset,
        version=version,
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Serve the file
    response = HttpResponse(version.file_path, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{version.file_path.name}"'
    return response

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
