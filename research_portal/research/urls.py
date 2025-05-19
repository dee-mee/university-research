from django.urls import path
from . import views

app_name = 'research'

urlpatterns = [
    path('', views.index, name='index'),
    path('homepage/', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('people/', views.people, name='people'),
    
    path('vlirous/', views.vlirous, name='vlirous'),
    path('about/', views.about, name='about'),
    path('sub-projects/', views.sub_projects, name='sub_projects'),
    path('sub-projects/<int:project_id>/', views.sub_project_detail, name='sub_project_detail'),
    path('research/', views.research, name='research'),
    path('community/', views.community, name='community'),
    path('contact/', views.contact, name='contact'),
    path('latest-activities/', views.latest_activities, name='latest_activities'),
    path('alerts/', views.alerts, name='alerts'),
    path('messages/', views.messages, name='messages'),
] 