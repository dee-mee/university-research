"""
WebSocket URL routing for the maps application
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/field-data/(?P<device_id>\w+)/$', consumers.FieldDataConsumer.as_asgi()),
]
