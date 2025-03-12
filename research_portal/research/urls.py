from django.urls import path
from . import views

app_name = 'research'

urlpatterns = [
    path('', views.index, name='index'),
    path('homepage/', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('map/', views.map_view, name='map'),
    path('people/', views.people, name='people'),
]
