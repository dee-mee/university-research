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
    path('', views.MapView.as_view(), name='index'),
    path('map/', views.MapView.as_view(), name='map'),  
    path('api/', include((router.urls, 'api'))),  
    path('api/debug/stations/', views.debug_stations, name='debug_stations'),
    path('csv-upload/', CSVUploadView.as_view(), name='csv_upload'),
    path('upload/success/', ImportSuccessView.as_view(), name='import_success'),
    path('flash-drive-import/', flash_drive_import_view, name='flash_drive_import'),
    path('api/map-data/', views.map_data, name='map_data'),
    path('api/import-csv/', views.api_import_csv, name='api_import_csv'),
    # Update URLs for statistics and data export with correct paths
    path('stations/<int:station_id>/statistics/', views.station_statistics_view, name='station_statistics'),
    path('stations/<int:station_id>/export/', views.station_data_export_view, name='station_data_export'),
    path('stations/<int:station_id>/download/', views.download_station_data, name='download_station_data'),
    
    # New URLs for stacked data functionality
    path('api/stations/<int:station_id>/push-data/', views.push_station_data, name='push_station_data'),
    path('api/stations/<int:station_id>/process-stack/', views.process_station_stack, name='process_station_stack'),
    path('api/stations/<int:station_id>/stack-info/', views.get_stack_info, name='get_stack_info'),
    path('stations/<int:station_id>/data-stack/', views.station_data_stack_view, name='station_data_stack'),
    
    # Add this new URL pattern for clearing the stack
    path('api/stations/<int:station_id>/clear-stack/', views.clear_station_stack, name='clear_station_stack'),
    
    # Make sure the API endpoint for climate data is accessible with a pattern that matches the JS
    path('api/climate-data/recent/', views.climate_data_recent, name='climate_data_recent'),
    
    # Add a custom data endpoint that JS can use as a fallback
    path('api/weather-stations/<int:station_id>/data/', views.station_climate_data, name='station_climate_data'),
]
