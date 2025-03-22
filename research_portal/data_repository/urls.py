from django.urls import path
from . import views

app_name = 'repository'

urlpatterns = [
    path('', views.DatasetListView.as_view(), name='dataset_list'),
    path('dataset/<slug:slug>/', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path('dataset/create/', views.DatasetCreateView.as_view(), name='dataset_create'),
    path('dataset/<slug:slug>/edit/', views.DatasetUpdateView.as_view(), name='dataset_edit'),
    path('dataset/<int:dataset_id>/version/create/', views.dataset_version_create, name='version_create'),
    path('dataset/<int:dataset_id>/version/<int:version_id>/download/', views.dataset_download, name='dataset_download'),
    path('category/<slug:category_slug>/', views.category_datasets, name='category_datasets'),
    path('my-datasets/', views.DatasetListView.as_view(template_name='data_repository/my_datasets.html'), {'user_datasets': True}, name='my_datasets'),
    path('download-history/', views.DatasetListView.as_view(template_name='data_repository/download_history.html'), {'show_downloads': True}, name='download_history'),
]
