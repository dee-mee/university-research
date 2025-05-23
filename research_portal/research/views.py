from django.shortcuts import render
from .models import NewsItem

def index(request):
    news_items = NewsItem.objects.all().order_by('-date')
    return render(request, 'index.html', {'news_items': news_items})

def homepage(request):
    return render(request, 'index.html')

def contact(request):
    return render(request, 'contact/contact.html')

    
def people(request):
    return render(request, 'contact/people.html')


def vlirous(request):
    return render(request, 'research/vlirous.html')

def about(request):
    return render(request, 'research/about.html')

def sub_projects(request):
    return render(request, 'research/sub_projects.html')

def research(request):
    return render(request, 'research/research.html')

def community(request):
    return render(request, 'research/community.html')

def latest_activities(request):
    return render(request, 'research/latest_activities.html')

def sub_project_detail(request, project_id):
    return render(request, 'research/sub_project_detail.html', {'project_id': project_id})

def alerts(request):
    # In a real implementation, you would fetch alerts from a database
    # For now, we're just rendering the template with static data
    return render(request, 'alerts.html')

def messages(request):
    # In a real implementation, you would fetch messages from a database
    # For now, we're just rendering the template with static data
    return render(request, 'messages.html')
