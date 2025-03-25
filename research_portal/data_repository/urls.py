from django.urls import path
from . import views

app_name = 'repository'

urlpatterns = [
    path('', views.DatasetListView.as_view(), name='dataset_list'),
    path('dataset/<int:pk>/', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path('dataset/create/', views.DatasetCreateView.as_view(), name='dataset_create'),
    path('dataset/<int:pk>/update/', views.DatasetUpdateView.as_view(), name='dataset_update'),
    path('dataset/<int:dataset_id>/download/', views.dataset_download, name='dataset_download'),
    path('dataset/<int:dataset_id>/download/<int:version_id>/', views.dataset_download, name='version_download'),
    path('dataset/<int:dataset_id>/version/create/', views.dataset_version_create, name='version_create'),
    path('api/dataset/<int:dataset_id>/', views.get_dataset_details, name='get_dataset_details'),
    path('category/<slug:category_slug>/', views.category_datasets, name='category_datasets'),
    path('stack/', views.StackedDatasetListView.as_view(), name='stacked_dataset_list'),
    path('stack/<int:pk>/', views.StackedDatasetDetailView.as_view(), name='stacked_dataset_detail'),
    path('stack/create/', views.StackedDatasetCreateView.as_view(), name='stacked_dataset_create'),
    path('stack/<int:stacked_dataset_id>/add/', views.add_dataset_to_stack, name='add_to_stack'),
    path('stack/<int:stacked_dataset_id>/remove/<int:item_id>/', views.remove_dataset_from_stack, name='remove_from_stack'),
    path('stack/<int:stacked_dataset_id>/reorder/', views.reorder_stack, name='reorder_stack'),
    path('stack/<int:stacked_dataset_id>/generate/', views.generate_stacked_dataset, name='generate_stack'),
    path('my-datasets/', views.DatasetListView.as_view(template_name='data_repository/my_datasets.html'), {'user_datasets': True}, name='my_datasets'),
    path('download-history/', views.DatasetListView.as_view(template_name='data_repository/download_history.html'), {'show_downloads': True}, name='download_history'),
]
