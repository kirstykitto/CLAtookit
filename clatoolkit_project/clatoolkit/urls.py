from django.conf.urls import patterns, url, include
from django.contrib import admin
from rest_framework.routers import DefaultRouter
import views

router = DefaultRouter()
router.register(r'learningrecord', views.LearningRecordViewSet)
router.register(r'socialrelationship', views.SocialRelationshipViewSet)
router.register(r'classification', views.ClassificationViewSet)
router.register(r'userclassification', views.UserClassificationViewSet)
#router.register(r'sna', views.SNARESTView, base_name="sna")

urlpatterns = patterns('',
    url(r'^register/$', views.register, name='register'),
    url(r'^eventregistration/$', views.eventregistration, name='eventregistration'),
    url(r'^socialmediaaccounts/$', views.socialmediaaccounts, name='socialmediaaccounts'),
    url(r'^sna/$', views.SNARESTView.as_view(), name='sna'),
    url(r'^wordcloud/$', views.WORDCLOUDView.as_view(), name='wordcloud'),
    url(r'^classificationpie/$', views.CLASSIFICATIONPieView.as_view(), name='classificationpie'),
    url(r'^topicmodel/$', views.TOPICMODELView.as_view(), name='topicmodel'),
    url(r'^classify/$', views.MLCLASSIFY.as_view(), name='classify'),
    url(r'^train/$', views.MLTRAIN.as_view(), name='train'),
    url(r'^externallinklog/$', views.EXTERNALLINKLOGView.as_view(), name='externallinklog'),
    url(r'^groupify/$', views.GROUPIFY.as_view(), name='groupify')
)
