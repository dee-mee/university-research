"""
Tasks for background processing using Celery.
To use these tasks, Celery must be configured in the project settings.
"""
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    # Define a function decorator that just runs the function directly
    def shared_task(func):
        return func
    CELERY_AVAILABLE = False

@shared_task
def process_data_export(export_id):
    """
    Process a data export in the background
    
    Args:
        export_id: ID of the DataExport to process
    """
    from .models import DataExport
    from .utils import create_secure_export_file
    
    try:
        # Get the export object
        export = DataExport.objects.get(id=export_id)
        
        # Mark as processing
        export.status = 'processing'
        export.save(update_fields=['status'])
        
        # Build the query for climate data
        from .models import ClimateData
        query = ClimateData.objects.filter(
            timestamp__gte=export.date_from,
            timestamp__lte=export.date_to
        )
        
        # Apply filters
        stations = export.stations.all()
        if stations:
            query = query.filter(station__in=stations)
            
        if export.country:
            query = query.filter(station__country=export.country)
            
        if export.years:
            query = query.filter(year__in=export.years)
            
        if export.min_data_quality:
            # Handle multiple quality levels separated by commas
            quality_levels = export.min_data_quality.split(',')
            query = query.filter(data_quality__in=quality_levels)
            
        # Create the export file
        create_secure_export_file(export, query, export.export_format)
        
        # Mark as completed
        export.status = 'completed'
        export.completed_at = timezone.now()
        export.save(update_fields=['status', 'completed_at'])
        
        # Send notification email if user provided
        if export.user and export.user.email:
            from django.urls import reverse
            from django.contrib.sites.models import Site
            
            site = Site.objects.get_current()
            domain = site.domain
            
            download_url = f"https://{domain}{export.get_secure_download_url()}"
            
            send_mail(
                f'Your {export.export_format.upper()} Export is Ready',
                f'Your requested data export is now ready to download. '
                f'You can download it using this link: {download_url}',
                settings.DEFAULT_FROM_EMAIL,
                [export.user.email],
                fail_silently=True
            )
            
        logger.info(f"Successfully processed export {export_id}")
        
    except Exception as e:
        logger.error(f"Error processing export {export_id}: {str(e)}", exc_info=True)
        
        # Update export status
        try:
            export = DataExport.objects.get(id=export_id)
            export.status = 'failed'
            export.error_message = str(e)
            export.sanitize_error_message()  # Remove sensitive details
            export.save(update_fields=['status', 'error_message'])
        except:
            pass

@shared_task
def clean_old_exports(days=30):
    """
    Delete export files older than the specified number of days
    
    Args:
        days: Number of days to keep exports (default: 30)
    """
    from .models import DataExport
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    try:
        old_exports = DataExport.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed']
        )
        
        count = 0
        for export in old_exports:
            if export.export_file:
                # Delete the file from storage
                try:
                    export.export_file.delete(save=False)
                    count += 1
                except Exception as e:
                    logger.error(f"Error deleting export file for {export.id}: {str(e)}")
        
        logger.info(f"Cleaned up {count} old export files")
    except Exception as e:
        logger.error(f"Error cleaning old exports: {str(e)}")

@shared_task
def auto_process_all_station_stacks():
    """Process data stacks for all stations that have auto_process enabled"""
    from .models import WeatherStation
    
    stations = WeatherStation.objects.filter(
        is_active=True,
        auto_process=True
    ).exclude(data_stack__isnull=True).exclude(data_stack='')
    
    processed_count = 0
    stations_count = 0
    
    for station in stations:
        try:
            stack_size = station.stack_size()
            if stack_size >= station.process_threshold:
                records = station.process_data_stack()
                if records > 0:
                    processed_count += records
                    stations_count += 1
        except Exception as e:
            logger.error(f"Error auto-processing stack for station {station.id}: {str(e)}")
    
    logger.info(f"Auto-processed {processed_count} records from {stations_count} stations")
    return processed_count
