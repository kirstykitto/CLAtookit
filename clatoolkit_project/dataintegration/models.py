from django.db import models
from django_pgjson.fields import JsonField
from clatoolkit.models import UnitOffering


# Create your models here.


class Comment(models.Model):
    commId = models.CharField(max_length=100)
    authorDispName = models.CharField(max_length=1000)
    text = models.CharField(max_length=10000)
    videoId = models.CharField(max_length=20)
    videoUrl = models.CharField(max_length=1000)
    parentId = models.CharField(max_length=50)
    parentUsername = models.CharField(max_length=1000, blank=True)
    isReply = models.BooleanField()
    updatedAt = models.CharField(max_length=30)


class Video(models.Model):
    videoId = models.CharField(max_length=20)
    videoUrl = models.CharField(max_length=1000)
    videoTitle = models.CharField(max_length=300)
    channelId = models.CharField(max_length=30)
    channelUrl = models.CharField(max_length=1000)
    # videoList = models.ManyToManyField('self')
    # commentList = models.ManyToManyField(Comment)


class PlatformConfig(models.Model):
    unit = models.ForeignKey(UnitOffering)
    platform = models.CharField(max_length=50)
    config = JsonField()
