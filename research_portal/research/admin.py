from django.contrib import admin
from .models import NewsItem

class NewsItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'date')
    search_fields = ('title', 'description')
    list_filter = ('date',)

admin.site.register(NewsItem, NewsItemAdmin)
