from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router for our API viewsets
router = DefaultRouter()
router.register(r'markers', views.LocationMarkerViewSet)
router.register(r'environmental-data', views.EnvironmentalDataViewSet)
router.register(r'annotations', views.UserMarkerAnnotationViewSet)
router.register(r'alerts', views.AlertThresholdViewSet)

urlpatterns = [
    # Web UI URLs
    path('', views.map_view, name='map'),
    path('markers/<int:marker_id>/', views.marker_detail_view, name='marker_detail'),
    
    # API URLs
    path('api/', include(router.urls)),
]