from django.shortcuts import render
from .models import NewsItem

def index(request):
    news_items = NewsItem.objects.all().order_by('-date')
    return render(request, 'index.html', {'news_items': news_items})

def contact(request):
    return render(request, 'contact/contact.html')

def map_view(request):
    return render(request, 'contact/map.html')

    

