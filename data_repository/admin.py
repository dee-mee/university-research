from django.contrib import admin
from .models import (
    Dataset, 
    DatasetVersion, 
    DatasetCategory, 
    DatasetAccess, 
    DatasetDownload,
    StackedDataset,
    StackedDatasetItem
)

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_by', 'created_at', 'status')
    list_filter = ('status', 'category', 'is_featured')
    search_fields = ('title', 'description', 'created_by__username')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'version_number', 'created_at', 'is_current')
    list_filter = ('is_current', 'created_at')
    search_fields = ('dataset__title', 'version_number')

@admin.register(DatasetCategory)
class DatasetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'order')
    list_filter = ('parent',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}

admin.site.register(DatasetAccess)
admin.site.register(DatasetDownload)
admin.site.register(StackedDataset)
admin.site.register(StackedDatasetItem)
