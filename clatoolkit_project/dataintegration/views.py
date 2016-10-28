# example/simple/views.py
from __future__ import absolute_import

from django.http import HttpResponse, Http404
from django.shortcuts import render, render_to_response
from authomatic import Authomatic
from authomatic.adapters import DjangoAdapter
from authomatic.providers import oauth2, oauth1
from dashboard.utils import *
from django.template import RequestContext
from dataintegration.tasks import *
from .forms import FacebookGatherForm
import json
from pprint import pprint
from clatoolkit.models import UserProfile, OfflinePlatformAuthToken, UserTrelloCourseBoardMap, ApiCredentials, UnitOffering, DashboardReflection, LearningRecord, SocialRelationship, CachedContent, GroupMap, OauthFlowTemp
from django.db import connection
import dateutil.parser
from dashboard.utils import *
from dataintegration.groupbuilder import *
from dataintegration.core.processingpipeline import *
from dataintegration.core.recipepermissions import *
from dataintegration.plugins.wordpress.cladi_plugin import WordPressPlugin


from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.conf import settings

from dataintegration.googleLib import *
from oauth2client.client import OAuth2WebServerFlow
from django.contrib.sites.shortcuts import get_current_site

import os
import requests

##############################################
# Process Trello Link
##############################################
@api_view(['GET'])
def process_trello(request):
    token = request.GET.get("token")
    key = request.GET.get("key")

    trello_member_url = 'https://api.trello.com/1/tokens/%s/member?key=%s' % (token, key)

    #Get trello member ID
    r = requests.get(trello_member_url)
    #print "got response %s" % r.json()
    member_json = r.json()
    member_id = member_json['id']

    token_storage = OfflinePlatformAuthToken(user_smid=member_id, token=token, platform='trello') #OauthFlowTemp(googleid=member_id, transferdata=token, platform='trello')
    token_storage.save()

    return Response(member_id)


##############################################
# Trello Data Extraction
##############################################
# TODO: ADD STUDENT REFRESH
@api_view()
def refreshtrello(request):
    course_code = request.GET.get('course_code')
    trello_courseboard_ids = request.GET.get('boards')
    trello_courseboard_ids = trello_courseboard_ids.split(',')

    trello_plugin = settings.DATAINTEGRATION_PLUGINS['trello']
    diag_count = 0

    for board_id in trello_courseboard_ids:
        trello_user_course_map = UserTrelloCourseBoardMap.objects.filter(board_id=board_id).filter(course_code=course_code)[0]
        #print 'got trello user course board map: %s' % (trello_user_course_map)

        user = trello_user_course_map.user
        usr_profile = UserProfile.objects.get(user=user)
        usr_offline_auth = OfflinePlatformAuthToken.objects.get(user_smid=usr_profile.trello_account_name)

        #print 'Performing Trello Board Import for User: %s' % (user)
        trello_plugin.perform_import(board_id, course_code, token=usr_offline_auth.token)
        diag_count = diag_count + 1

    post_smimport(course_code, 'trello')

    return Response('<b>Trello refresh complete: %s users updated.</b>' % (diag_count))


##############################################
# GitHub Data Extraction
##############################################
def refreshgithub(request):

    html_response = HttpResponse()
    unit_id = request.GET.get('unit')
    try:
        unit = UnitOffering.objects.get(id=unit_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    repoUrls = request.GET.get('urls')

    github_plugin = settings.DATAINTEGRATION_PLUGINS['GitHub']
    github_plugin.perform_import(repoUrls, unit)
    post_smimport(unit, "GitHub")

    return render(request, 'dataintegration/githubresult.html')


##############################################
# Data Extraction for YouTube
##############################################
def refreshgoogleauthflow(request):
    course_code = request.GET.get('course_code')
    channelIds = request.GET.get('channelIds')
    platform = request.GET.get('platform')

    user = request.user
    youtube_plugin = settings.DATAINTEGRATION_PLUGINS['YouTube']

    #print 'Got youtube plugin: %s' % (youtube_plugin)
    #print 'With client ID and Secret key: %s and %s' % (youtube_plugin.api_config_dict['CLIENT_ID'], youtube_plugin.api_config_dict['CLIENT_SECRET'])

    redirecturl= 'http://' + get_current_site(request).domain + '/dataintegration/ytAuthCallback'

    # store request data in temp table
    # there is no other way to send these with the url (in querystring) as the return url must be registered
    # and session var won't save due to redirect
    twitter_id, fb_id, forum_id, google_id, github_id, trello_id = get_smids_fromuid(user.id)
    t = OauthFlowTemp.objects.filter(googleid=google_id).delete()
    temp_transfer_data = OauthFlowTemp(googleid=google_id, course_code=course_code, platform=platform, transferdata=channelIds)
    temp_transfer_data.save()

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id=youtube_plugin.api_config_dict['CLIENT_ID'],
        client_secret=youtube_plugin.api_config_dict['CLIENT_SECRET'],
        scope=youtube_plugin.scope,
        redirect_uri=redirecturl
    )

    authUri = FLOW_YOUTUBE.step1_get_authorize_url()
    #Redirect to REDIRECT_URI
    return HttpResponseRedirect(authUri)

def ytAuthCallback(request):

    html_response = HttpResponse()

    youtube_plugin = settings.DATAINTEGRATION_PLUGINS['YouTube']

    redirecturl= 'http://' + get_current_site(request).domain + '/dataintegration/ytAuthCallback'

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id=youtube_plugin.api_config_dict['CLIENT_ID'],
        client_secret=youtube_plugin.api_config_dict['CLIENT_SECRET'],
        scope=youtube_plugin.scope,
        redirect_uri=redirecturl
    )

    http = googleAuth(request, FLOW_YOUTUBE)
    user = request.user

    user_channelid = youtube_getpersonalchannel(request, http)
    #print user_channelid
    t = OauthFlowTemp.objects.filter(googleid='http://www.youtube.com/channel/'+user_channelid)
  #  if not len(t):
    #t = OauthFlowTemp.objects.filter(googleid=user_channelid)
    #print t.all()
    course_code = t[0].course_code
    platform = t[0].platform
    channelIds = t[0].transferdata

    ytList = youtube_plugin.perform_import(channelIds, course_code, http)

    vList = ytList[0]
    vNum = len(vList)
    commList = ytList[1]
    commNum = len(commList)
    context_dict = {"vList": vList, "vNum": vNum, "commList": commList, "commNum": commNum}

    post_smimport(course_code, platform)

    return render(request, 'dataintegration/ytresult.html', context_dict)

##############################################
# Data Extraction for YouTube
##############################################
def get_youtubechannel(request):
    youtube_plugin = settings.DATAINTEGRATION_PLUGINS['YouTube']

    redirecturl= 'http://' + get_current_site(request).domain + '/dataintegration/showyoutubechannel'

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id=youtube_plugin.api_config_dict['CLIENT_ID'],
        client_secret=youtube_plugin.api_config_dict['CLIENT_SECRET'],
        scope=youtube_plugin.scope,
        redirect_uri=redirecturl
    )

    authUri = FLOW_YOUTUBE.step1_get_authorize_url()
    #Redirect to REDIRECT_URI
    return HttpResponseRedirect(authUri)

def showyoutubechannel(request):

    youtube_plugin = settings.DATAINTEGRATION_PLUGINS['YouTube']

    redirecturl= 'http://' + get_current_site(request).domain + '/dataintegration/showyoutubechannel'

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id=youtube_plugin.api_config_dict['CLIENT_ID'],
        client_secret=youtube_plugin.api_config_dict['CLIENT_SECRET'],
        scope=youtube_plugin.scope,
        redirect_uri=redirecturl
    )

    http = googleAuth(request, FLOW_YOUTUBE)

    channel_url = youtube_getpersonalchannel(request, http)

    html_response = HttpResponse()

    if channel_url:
        html_response.write(u'<h2>Your YouTube Channel URL is: http://www.youtube.com/channel/{0}</h2>'.format(channel_url))
    else:
        html_response.write('No Channel url found. Please ensure that you are logged into YouTube and try again.')

    return html_response

def home(request):
    form = FacebookGatherForm()
    return render(request, 'dataintegration/facebook.html', {'form': form})


def refreshtwitter(request):
    unit_id = request.GET.get('unit')

    try:
        unit = UnitOffering.objects.get(id=unit_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    hastags = request.GET.get('hashtags')

    tags = hastags.split(',')
    for tag in tags:
        hashtag = tag if tag.startswith("#") else "#" + tag

        twitter_plugin = settings.DATAINTEGRATION_PLUGINS['Twitter']
        twitter_plugin.perform_import(hashtag, unit)

    # TODO
    # post_smimport(course_code, "Twitter")

    return HttpResponse('Twitter Refreshed.')


def refreshdiigo(request):
    html_response = HttpResponse()

    diigo_plugin = settings.DATAINTEGRATION_PLUGINS['Diigo']

    course_code = request.GET.get('course_code')
    hastags = request.GET.get('tags')

    tags = hastags.split(',')
    for tag in tags:
        diigo_plugin.perform_import(tag, course_code)

    post_smimport(course_code, "Diigo")

    html_response.write('Diigo Refreshed.')
    return html_response


def refreshblog(request):
    html_response = HttpResponse()

    blog_plugin = settings.DATAINTEGRATION_PLUGINS['Blog']

    course_code = request.GET.get('course_code')
    hastags = request.GET.get('urls')

    urls = hastags.split(',')
    for url in urls:
        blog_plugin.perform_import(url, course_code)

    post_smimport(course_code, "Blog")

    html_response.write('Blog Refreshed.')
    return html_response


def dipluginauthomaticlogin(request):
    
    if request.GET.get('context') is not None:
        request.GET = request.GET.copy()

        state_dict = request.GET.pop('context')
        state_dict = state_dict[0]
        state_dict = json.loads(state_dict)

        request.session['platform'] = state_dict['platform']
        request.session['unit'] = state_dict['unit']
        request.session['group_id'] = state_dict['group']

    platform = request.session['platform']

    html_response = HttpResponse()

    if (platform in settings.DATAINTEGRATION_PLUGINS_INCLUDEAUTHOMATIC):
        di_plugin = settings.DATAINTEGRATION_PLUGINS[platform]
        authomatic = Authomatic(di_plugin.authomatic_config_json, di_plugin.authomatic_secretkey)
        result = authomatic.login(DjangoAdapter(request, html_response), di_plugin.authomatic_config_key, report_errors=True)

        # If there is no result, the login procedure is still pending.
        # Don't write anything to the response if there is no result!
        if result:
            # If there is result, the login procedure is over and we can write to response.
            html_response.write('<a href="..">Home</a>')

            if result.error:
                # Login procedure finished with an error.
                html_response.write('<h2>Error: {0}</h2>'.format(result.error.message))

            elif result.user:
                # Hooray, we have the user!
                # OAuth 2.0 and OAuth 1.0a provide only limited user data on login,
                # We need to update the user to get more info.
                if not (result.user.name and result.user.id):
                    result.user.update()

                # Welcome the user.
                html_response.write(u'<p>Hi {0}</p>'.format(result.user.name))
                # response.write(u'<h2>Your id is: {0}</h2>'.format(result.user.id))
                # response.write(u'<h2>Your email is: {0}</h2>'.format(result.user.email))

                # If there are credentials (only by AuthorizationProvider),
                # we can _access user's protected resources.
                if result.user.credentials:
                    group_id = request.session['group_id']
                    unit_id = request.session['unit']
                    unit = UnitOffering.objects.get(id=unit_id)
                    if result.provider.name == 'fb':
                        di_plugin.perform_import(group_id, unit, result)

                        post_smimport(unit, "facebook")

                        #Remove all data stored in session for this view to avoid cache issues
                        del request.session['platform']
                        del request.session['unit']
                        del request.session['group_id']
                        html_response.write('Updating Facebook for {} {}'.format(unit.code, unit.name))
        else:
            html_response.write('Auth Returned no Response.')

    return html_response


def get_social_media_id(request):
    '''
    Gets users social media IDs for use in signup for information integration.
    :param request:
    :return:
    '''
    # TODO: Add social media functionality apart from facebook
    # We we need the response object for the adapter.
    html_response = HttpResponse()

    if (request.GET.get('context') is not None):
        request.GET = request.GET.copy()

        state_dict = request.GET.pop('context')
        state_dict = state_dict[0]
        state_dict = json.loads(state_dict)

        #print str(state_dict)

        request.session['platform'] = state_dict['platform']
        #request.session['course_code'] = state_dict['course_code']
        #request.session['group_id'] = state_dict['group']

    #print 'Data stored in session: %s, %s, %s' % (request.session['platform'], request.session['course_code'], request.session['group_id'])

    platform = request.session['platform']


    #Facebook endpoints break on GET variables.....
    #platform = request.GET.get('platform')

    if (platform in settings.DATAINTEGRATION_PLUGINS_INCLUDEAUTHOMATIC):

        di_plugin = settings.DATAINTEGRATION_PLUGINS[platform]
        authomatic = Authomatic(di_plugin.authomatic_config_json, di_plugin.authomatic_secretkey)
        result = authomatic.login(DjangoAdapter(request, html_response), di_plugin.authomatic_config_key, report_errors=True)

        # If there is no result, the login procedure is still pending.
        # Don't write anything to the response if there is no result!
        if result:
            # If there is result, the login procedure is over and we can write to response.
            #html_response.write('<a href="..">Home</a>')

            if result.error:
                # Login procedure finished with an error.
                html_response.write('<p>Error: {0}</p>'.format(result.error.message))

            elif result.user:
                # Hooray, we have the user!

                # OAuth 2.0 and OAuth 1.0a provide only limited user data on login,
                # We need to update the user to get more info.
                if not (result.user.name and result.user.id):
                    result.user.update()

                # Welcome the user.
                # html_response.write(u'<p>Hi {0}</p>'.format(result.user.name))
                html_response.write(u'<h2>Your Facebook id is: {0}</h2>'.format(result.user.id))
        else:
            html_response.write('Auth Returned no Response.')

    return html_response

def refreshforum(request):
    html_response = HttpResponse()

    course_code = request.GET.get('course_code')
    forumurl = request.GET.get('forumurl')

    forum_plugin = settings.DATAINTEGRATION_PLUGINS['Forum']
    forum_plugin.perform_import("", course_code)

    post_smimport(course_code, "Forum")

    html_response.write('Forum Refreshed.')
    return html_response

def sendtolrs(request):
    html_response = HttpResponse()

    updateLRS()

    html_response.write('Statements Sent to LRS.')
    return html_response

def assigngroups(request):
    html_response = HttpResponse()
    course_code = request.GET.get('course_code', None)
    GroupMap.objects.filter(course_code=course_code).delete()
    assign_groups_class(course_code)
    html_response.write('Groups Assigned')
    return html_response
