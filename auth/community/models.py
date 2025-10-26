from django.db import models

class Post(models.Model):
    profilename=models.CharField(max_legnth=50)
    title = models.CharField(max_legnth=50)
    desc = models.CharField(max_length=1000)
    loc = models.charField(max_legnth=75,blank=True,null=True)
    loc_rating=models.IntegerField(blank=True,null=True)
    img = models.ImageField(upload_to='images/', blank=True, null=True)
    vid = models.FileField(upload_to='videos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    