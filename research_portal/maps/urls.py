from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import MapView, CSVUploadView, ImportSuccessView, flash_drive_import_view

router = DefaultRouter()
router.register(r'weather-stations', views.WeatherStationViewSet)  
router.register(r'climate-data', views.ClimateDataViewSet)
router.register(r'weather-alerts', views.WeatherAlertViewSet)

app_name = 'maps'

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    path('api/map-data/', views.map_data, name='map_data'),
    path('api/climate-data/recent/', views.climate_data_recent, name='climate_data_recent'),
    path('api/stations/<int:station_id>/data/', views.station_climate_data, name='station_climate_data'),
    
    # Add new graph data API endpoint
    path('api/stations/<int:station_id>/graph-data/', views.station_graph_data, name='station_graph_data'),
    
    # Debug endpoint - make sure this is properly registered
    path('api/debug/stations/', views.debug_stations, name='debug_stations'),
    
    # Station data management
    path('api/stations/<int:station_id>/push-data/', views.push_station_data, name='push_station_data'),
    path('api/stations/<int:station_id>/process-stack/', views.process_station_stack, name='process_station_stack'),
    path('api/stations/<int:station_id>/stack-info/', views.get_stack_info, name='get_stack_info'),
    path('api/stations/<int:station_id>/clear-stack/', views.clear_station_stack, name='clear_station_stack'),
    
    # CSV import endpoints
    path('api/import-csv/', views.api_import_csv, name='api_import_csv'),
    
    # Debug endpoint outside the api/ namespace for backward compatibility
    path('debug_stations/', views.debug_stations, name='debug_stations_outside'),
    
    # Web views
    path('map/', views.MapView.as_view(), name='map'),
    path('stations/<int:station_id>/statistics/', views.station_statistics_view, name='station_statistics'),
    path('stations/<int:station_id>/export/', views.station_data_export_view, name='station_data_export'),
    path('stations/<int:station_id>/download/', views.download_station_data, name='download_station_data'),
    path('stations/<int:station_id>/stack/', views.station_data_stack_view, name='station_data_stack'),
    path('upload-csv/', views.CSVUploadView.as_view(), name='upload_csv'),
    path('flash-drive-import/', views.flash_drive_import_view, name='flash_drive_import'),
    path('import-success/', views.ImportSuccessView.as_view(), name='import_success'),
    path('secure-export/<int:export_id>/<str:signature>/', views.secure_export_download, name='secure_export_download'),
    path('data-entry/', views.stack_data_entry, name='stack_data_entry'),
    path('process-stack/<int:station_id>/', views.process_station_stack, name='process_station_stack'),
]
