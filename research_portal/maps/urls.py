from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.urls import re_path
from . import views
from .views import MapView, CSVUploadView, ImportSuccessView, flash_drive_import_view, field_data_upload
from .field_views import field_data_upload_detail, field_data_visualize, field_data_retry
from .api_views import DeviceTypeViewSet, FieldDeviceViewSet, DeviceCalibrationViewSet, FieldDataUploadViewSet
from .field_device_api import device_data_upload
from .field_data_views import field_data_analysis, field_data_analysis_api
from .batch_operations import batch_operations_view, batch_operations_api
from .field_dashboard_views import field_data_dashboard, device_data_api, device_alerts_api, device_reset_api
from .consumers import FieldDataConsumer

router = DefaultRouter()
router.register(r'weather-stations', views.WeatherStationViewSet)  
router.register(r'climate-data', views.ClimateDataViewSet)
router.register(r'weather-alerts', views.WeatherAlertViewSet)
router.register(r'device-types', DeviceTypeViewSet)
router.register(r'field-devices', FieldDeviceViewSet)
router.register(r'device-calibrations', DeviceCalibrationViewSet)
router.register(r'field-data-uploads', FieldDataUploadViewSet, basename='field-data-upload')

# Add custom action URL configuration
FieldDataUploadViewSet.basename = 'field-data-upload'
FieldDataUploadViewSet.action_urls = {
    'upload_data': 'field-data-uploads-upload_data'
}

app_name = 'maps'

urlpatterns = [
    # API endpoints
    path('api/field-data-uploads/upload_data/', device_data_upload, name='field_data_upload'),
    path('api/', include(router.urls)),
    path('api/map-data/', views.map_data, name='map_data'),
    path('api/climate-data/recent/', views.climate_data_recent, name='climate_data_recent'),
    path('api/climate-data/station/<int:station_id>/', views.climate_data_station, name='api_climate_data_station'),
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
    
    # WebSocket endpoints
    path('ws/field-data/<str:device_id>/', FieldDataConsumer.as_asgi(), name='field_data_ws'),
    
    # Debug endpoint outside the api/ namespace for backward compatibility
    path('debug_stations/', views.debug_stations, name='debug_stations_outside'),
    
    # Web views
    path('map/', views.MapView.as_view(), name='map'),
    path('station-data/', views.station_data_view, name='station_data'),
    path('stations/<str:station_id>/statistics/', views.station_statistics_view, name='station_statistics'),
    path('stations/<int:station_id>/export/', views.station_data_export_view, name='station_data_export'),
    path('stations/<int:station_id>/download/', views.download_station_data, name='download_station_data'),
    path('stations/<int:station_id>/stack/', views.station_data_stack_view, name='station_data_stack'),
    path('upload-csv/', views.CSVUploadView.as_view(), name='upload_csv'),
    
    # Field data collection
    path('field-data/upload/', field_data_upload, name='field_data_upload'),
    path('field-data/upload/<int:upload_id>/', field_data_upload_detail, name='field_data_upload_detail'),
    path('field-data/visualize/<int:upload_id>/', field_data_visualize, name='field_data_visualize'),
    path('field-data/retry/<int:upload_id>/', field_data_retry, name='field_data_retry'),
    path('field-data/analysis/', field_data_analysis, name='field_data_analysis'),
    path('api/field-data/analysis/', field_data_analysis_api, name='field_data_analysis_api'),
    
    # Batch operations
    path('field-devices/batch-operations/', batch_operations_view, name='batch_operations'),
    path('api/batch-operations/', batch_operations_api, name='batch_operations_api'),
    
    # Field data dashboard
    path('field-devices/dashboard/', field_data_dashboard, name='field_data_dashboard'),
    path('api/field-devices/<int:device_id>/data/', device_data_api, name='device_data_api'),
    path('api/field-devices/<int:device_id>/alerts/', device_alerts_api, name='device_alerts_api'),
    path('api/field-devices/<int:device_id>/reset/', device_reset_api, name='device_reset_api'),
    path('flash-drive-import/', views.flash_drive_import_view, name='flash_drive_import'),
    path('import-success/', views.ImportSuccessView.as_view(), name='import_success'),
    path('secure-export/<int:export_id>/<str:signature>/', views.secure_export_download, name='secure_export_download'),
    path('data-entry/', views.stack_data_entry, name='stack_data_entry'),
    path('process-stack/<int:station_id>/', views.process_station_stack, name='process_station_stack'),
]
