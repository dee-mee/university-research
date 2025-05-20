from django.contrib import admin
from .models import NewsItem

@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'date')
    search_fields = ('title', 'description')
    date_hierarchy = 'date'
    
    fieldsets = (
        (None, {
            'fields': ('title', 'date')
        }),
        ('Content', {
            'fields': ('image', 'description')
        }),
    )
