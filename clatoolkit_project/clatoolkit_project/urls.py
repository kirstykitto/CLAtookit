from django.conf.urls import patterns, include, url
from django.contrib import admin
from clatoolkit import views
from django.contrib.auth.views import password_reset, password_reset_done, password_reset_confirm, password_reset_complete
from clatoolkit.urls import router

urlpatterns = patterns('',
    url(r'^$', views.userlogin, name='userlogin'),
    url(r'^clatoolkit/', include('clatoolkit.urls')),
    url(r'^api/', include(router.urls)),
    url(r'^api/', include('api.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^dataintegration/', include('dataintegration.urls')),
    url(r'^dashboard/', include('dashboard.urls')),
    url(r'^xapi/', include('xapi.urls')),
    url(r'^logout/(?P<next_page>.*)/$', 'django.contrib.auth.views.logout', name='auth_logout_next'),
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name='auth_logout'),
    url(r'^reset-password/$', password_reset, name='reset_password'),
    url(r'^reset-password/done/$', password_reset_done, name='password_reset_done'),
    url(r'^reset-password/confirm/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$', password_reset_confirm, name='password_reset_confirm'),
    url(r'^reset-password/complete/$', password_reset_complete, name='password_reset_complete')
)
