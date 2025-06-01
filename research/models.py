from django.db import models

class NewsItem(models.Model):
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='news_images/')
    date = models.DateTimeField()
    description = models.TextField()

    def __str__(self):
        return self.title