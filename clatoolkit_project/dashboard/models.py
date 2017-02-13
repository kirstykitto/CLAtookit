'''from django.db import models
from clatoolkit.models import UnitOffering

class al2_classifier(models.Model):
    construct = models.CharField(max_length=52, blank=false)
    data_source = models.CharField(max_length=52, blank=false)
    model = models.CharField(max_length=52, blank=false)
    construct = models.ForeignKey(al2_construct)
    default = models.BooleanField(default=false)

class al2_construct(models.Model):
    name = models.CharField(max_length=52, blank=false)
    labels = models.CharField(max_length=255, blank=false)
'''
