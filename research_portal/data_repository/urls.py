from django.urls import path
from . import views

app_name = 'repository'

urlpatterns = [
    # Dataset views
    path('', views.dataset_list, name='dataset_list'),
    path('dataset/<int:dataset_id>/', views.dataset_detail, name='dataset_detail'),
    path('dataset/create/', views.dataset_create, name='dataset_create'),
    path('dataset/<int:dataset_id>/edit/', views.DatasetUpdateView.as_view(), name='dataset_update'),
    path('dataset/<slug:slug>/', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path('dataset/<int:dataset_id>/download/<int:version_id>/', views.dataset_download, name='dataset_download'),
    path('dataset/<int:dataset_id>/version/create/', views.version_create, name='version_create'),
    path('dataset/<int:dataset_id>/timeseries/<str:variable>/', views.dataset_timeseries, name='dataset_timeseries'),
    
    # User-specific views
    path('my-datasets/', views.my_datasets, name='my_datasets'),
    path('download-history/', views.download_history, name='download_history'),
    
    # Category views
    path('category/<slug:category_slug>/', views.category_datasets, name='category_datasets'),
    
    # Stack management
    path('stacks/', views.StackedDatasetListView.as_view(), name='stacked_dataset_list'),
    path('stacks/create/', views.StackedDatasetCreateView.as_view(), name='stacked_dataset_create'),
    path('stacks/<slug:slug>/', views.StackedDatasetDetailView.as_view(), name='stacked_dataset_detail'),
    path('stacks/<int:stacked_dataset_id>/add-dataset/', views.add_dataset_to_stack, name='add_dataset_to_stack'),
    path('stacks/<int:stacked_dataset_id>/remove-dataset/<int:item_id>/', views.remove_dataset_from_stack, name='remove_dataset_from_stack'),
    path('stacks/<int:stacked_dataset_id>/reorder/', views.reorder_stack, name='reorder_stack'),
    path('stacks/<int:stacked_dataset_id>/generate/', views.generate_stacked_dataset, name='generate_stacked_dataset'),
    path('stacks/<int:stacked_dataset_id>/delete/', views.delete_stacked_dataset, name='delete_stacked_dataset'),
    path('stacks/create-from-selection/', views.create_stack_from_selection, name='create_stack'),
    
    # API endpoints
    path('api/version/<int:version_id>/variables/', views.api_version_variables, name='api_version_variables'),
    path('api/dataset-version/<int:version_id>/time-series-data/', views.get_time_series_data, name='api_time_series_data'),
]
