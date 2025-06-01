"""URL patterns for integrated maps and data repository views"""
from django.urls import path
from . import views

app_name = 'integration'

urlpatterns = [
    # Unified import/export views
    path('import/', views.unified_import_view, name='unified_import'),
    path('export/', views.export_data_view, name='export_data'),
    path('sync/', views.sync_data_view, name='sync_data'),
    
    # API endpoints
    path('api/check-file-format/', views.check_file_format, name='check_file_format'),
    path('api/import/', views.api_import, name='api_import'),
    path('api/integrated-data/', views.integrated_data_api, name='integrated_data_api'),
    
    # Data synchronization
    path('export-station/<int:station_id>/', views.export_station_to_repository_view, 
         name='export_station_to_repository'),
]