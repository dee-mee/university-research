"""
WSGI config for research_portal project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')

application = get_wsgi_application()

# Add WhiteNoise to serve static files
from whitenoise import WhiteNoise
from django.conf import settings  # Add this import

application = WhiteNoise(application, root=os.path.join(settings.BASE_DIR, 'staticfiles'))
application.add_files(os.path.join(settings.BASE_DIR, 'static'), prefix='static/')
