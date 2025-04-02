"""
URL configuration for research_portal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from profiles.views import logout_view
from django.conf import settings
from django.conf.urls.static import static
from maps.views import ImportSuccessView
from django.views.generic import RedirectView

# Import custom admin settings
import research_portal.admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('maps/', include('maps.urls', namespace='maps')),
    # We should NOT include maps.urls at the root - that was causing the duplicate/confused URLs
    # path('', include('maps.urls')), # Remove this line
    path('', include('research.urls')),
    path('', include('profiles.urls')),
    # Remove this duplicate include - it's already included with namespace above
    # path('', include('maps.urls')),
    path('repository/', include('data_repository.urls', namespace='repository')),
    path('api-auth/', include('rest_framework.urls')),
    path('logout/', logout_view, name='logout'),
    
    # Add API fallback redirects to fix 404 errors
    path('api/weather-stations/', RedirectView.as_view(url='/maps/api/weather-stations/', permanent=False)),
    path('api/map-data/', RedirectView.as_view(url='/maps/api/map-data/', permanent=False)),
    path('api/climate-data/', RedirectView.as_view(url='/maps/api/climate-data/', permanent=False)),
    path('api/climate-data/recent/', RedirectView.as_view(url='/maps/api/climate-data/recent/', permanent=False)),
    path('debug_stations/', RedirectView.as_view(url='/maps/debug_stations/', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)