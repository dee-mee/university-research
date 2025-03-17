# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import MapView, CSVUploadView, ImportSuccessView, flash_drive_import_view

router = DefaultRouter()
router.register(r'weather-stations', views.WeatherStationViewSet)  # Changed from 'stations'
router.register(r'climate-data', views.ClimateDataViewSet)
router.register(r'weather-alerts', views.WeatherAlertViewSet)

app_name = 'maps'

urlpatterns = [
    path('maping/', views.MapView.as_view(), name='map'),  # Main map page
    path('api/', include((router.urls, 'api'))),  # API endpoints under /api/
    path('api/debug/stations/', views.debug_stations, name='debug_stations'),

    path('csv-upload/', CSVUploadView.as_view(), name='csv_upload'),
    path('upload/success/', ImportSuccessView.as_view(), name='import_success'),
    path('flash-drive-import/', flash_drive_import_view, name='flash_drive_import'),
]
