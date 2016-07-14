
from django.conf.urls import patterns, url, include
from django.contrib import admin

import views

urlpatterns = patterns('',
    url(r'^$', views.dashboard, name='dashboard'),
    url(r'^myunits/$', views.myunits, name='myunits'),
    url(r'^ca_dashboard/$', views.cadashboard, name='cadashboard'),
    url(r'^sna_dashboard/$', views.snadashboard, name='snadashboard'),
    url(r'^student_dashboard/$', views.studentdashboard, name='studentdashboard'),
    url(r'^mydashboard/$', views.mydashboard, name='mydashboard'),
    url(r'^pyldavis/$', views.pyldavis, name='pyldavis'),
    url(r'^myclassifications/$', views.myclassifications, name='myclassifications'),
    url(r'^ccadashboard/$', views.ccadashboard, name='ccadashboard'),
    url(r'^ccadata/$', views.ccadata, name='ccadata'),
)
