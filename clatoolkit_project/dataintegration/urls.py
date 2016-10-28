from django.conf import settings
from django.conf.urls import patterns, url, include

from dataintegration import views

urlpatterns = []

for plugin in settings.DATAINTEGRATION_PLUGINS:
    if hasattr(settings.DATAINTEGRATION_PLUGINS[plugin], "get_url_patterns"):
        platform = settings.DATAINTEGRATION_PLUGINS[plugin].platform
        urlpatterns.append(
            url(r'^{}/'.format(platform), include(settings.DATAINTEGRATION_PLUGINS[plugin].get_url_patterns())))

urlpatterns += patterns(
    url(r'^home/$', views.home, name='home'),
    #url(r'^login/(?P<group_id>\d+)$', views.login, name='login'),
    url(r'^get_social/$', views.get_social_media_id, name='get_social'),
    url(r'^refreshtwitter/$', views.refreshtwitter, name='refreshtwitter'),
    url(r'^refreshdiigo/$', views.refreshdiigo, name='refreshdiigo'),
    url(r'^refreshblog/$', views.refreshblog, name='refreshblog'),
    url(r'^refreshforum/$', views.refreshforum, name='refreshforum'),
    url(r'^sendtolrs/$', views.sendtolrs, name='sendtolrs'),
    #url(r'^refreshyoutube/$', views.refreshyoutube, name='refreshyoutube'),
    url(r'^refreshgoogleauthflow/$', views.refreshgoogleauthflow, name='refreshgoogleauthflow'),
    url(r'^ytAuthCallback/$', views.ytAuthCallback, name='ytAuthCallback'),
    url(r'^get_youtubechannel/$', views.get_youtubechannel, name='get_youtubechannel'),
    url(r'^showyoutubechannel/$', views.showyoutubechannel, name='showtubechannel'),
    url(r'^assigngroups/$', views.assigngroups, name='assigngroups'),
    url(r'^dipluginauthomaticlogin/$', views.dipluginauthomaticlogin, name='dipluginauthomaticlogin'),
    url(r'^refreshgithub/$', views.refreshgithub, name='refreshgithub'),
    url(r'^process_trello/$', views.process_trello, name='processtrello'),
    url(r'^refreshtrello/$', views.refreshtrello, name='refreshtrello'),
    #url(r'^ytAuthCallback/(?P<course_id>\d+)/$', views.ytAuthCallback, name='ytAuthCallback'),
)
