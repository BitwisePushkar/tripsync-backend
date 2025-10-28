from django.db import models
from django.conf import settings

class Post(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=50)
    desc = models.CharField(max_length=1000)
    loc = models.CharField(max_length=75,blank=True,null=True)
    loc_rating=models.IntegerField(blank=True,null=True)
    img = models.ImageField(upload_to='images/', blank=True, null=True)
    vid = models.FileField(upload_to='videos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    