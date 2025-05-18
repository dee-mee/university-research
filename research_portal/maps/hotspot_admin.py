from django.contrib.gis import admin
from django.contrib.gis.forms import OSMWidget
from django.contrib.gis.db import models
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Hotspot


class HotspotAdmin(admin.OSMGeoAdmin):
    list_display = ('name', 'status', 'priority', 'start_date', 'location_link', 'created_by')
    list_filter = ('status', 'priority', 'start_date')
    search_fields = ('name', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'created_by_display')
    date_hierarchy = 'start_date'
    filter_horizontal = ('related_stations',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'status', 'priority')
        }),
        ('Location', {
            'fields': ('location', 'radius')
        }),
        ('Timing', {
            'fields': ('start_date', 'end_date')
        }),
        ('Relationships', {
            'fields': ('related_stations',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_by_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        models.PointField: {'widget': OSMWidget(attrs={'default_lon': 37.0, 'default_lat': 0.0, 'map_width': 800, 'map_height': 500})},
    }
    
    def created_by_display(self, obj):
        if obj.created_by:
            url = reverse('admin:auth_user_change', args=[obj.created_by.id])
            return mark_safe(f'<a href="{url}">{obj.created_by.username}</a>')
        return '-' 
    created_by_display.short_description = 'Created By'
    
    def location_link(self, obj):
        if obj.location:
            lat, lng = obj.location.coords[1], obj.location.coords[0]
            google_maps_url = f"https://www.google.com/maps?q={lat},{lng}"
            return mark_safe(f'<a href="{google_maps_url}" target="_blank">View on Map</a>')
        return '-'
    location_link.short_description = 'Location'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only set created_by during the first save.
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)
    
    def has_change_permission(self, request, obj=None):
        if not obj:
            return True
        if request.user.is_superuser:
            return True
        return obj.created_by == request.user
    
    def has_delete_permission(self, request, obj=None):
        if not obj:
            return True
        if request.user.is_superuser:
            return True
        return obj.created_by == request.user
