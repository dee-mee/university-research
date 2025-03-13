# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import MapView

router = DefaultRouter()
router.register(r'stations', views.WeatherStationViewSet)
router.register(r'climate-data', views.ClimateDataViewSet)

app_name = 'maps'

urlpatterns = [
    path('maping/', views.MapView.as_view(), name='map'),  # Main map page at the root URL
    path('api/', include((router.urls, 'api'))),    # API endpoints under /api/
    
]
