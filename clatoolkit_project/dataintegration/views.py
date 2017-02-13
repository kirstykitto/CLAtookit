# example/simple/views.py
from __future__ import absolute_import

from django.http import HttpResponse, Http404, HttpResponseServerError
from django.shortcuts import render, render_to_response
from authomatic import Authomatic
from authomatic.adapters import DjangoAdapter
from authomatic.providers import oauth2
from dashboard.utils import *
from django.template import RequestContext
from dataintegration.tasks import *
from .forms import FacebookGatherForm
import json
from pprint import pprint
from clatoolkit.models import UserProfile, OfflinePlatformAuthToken, UserPlatformResourceMap, ApiCredentials, UnitOffering, DashboardReflection, LearningRecord, SocialRelationship, CachedContent, GroupMap, OauthFlowTemp
from django.db import connection
import dateutil.parser
from dashboard.utils import *
from dataintegration.groupbuilder import *
from dataintegration.core.processingpipeline import *
from dataintegration.core.di_utils import * #from dataintegration.core.recipepermissions import *


from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.conf import settings
from django.shortcuts import redirect

from dataintegration.googleLib import *
from oauth2client.client import OAuth2WebServerFlow
from django.contrib.sites.shortcuts import get_current_site

import os
import requests

from xapi.statement.xapi_settings import xapi_settings
from common.util import Utility


##############################################
# Process Trello Link
##############################################
@api_view(['GET'])
def process_trello(request):
    token = request.GET.get("token")
    # key = request.GET.get("key")
    key = os.environ.get('TRELLO_API_KEY')
    trello_member_url = 'https://api.trello.com/1/tokens/%s/member?key=%s' % (token, key)

    #Get trello member ID
    r = requests.get(trello_member_url)
    #print "got response %s" % r.json()
    member_json = r.json()
    member_id = member_json['id']

    tokens = OfflinePlatformAuthToken.objects.filter(user_smid=member_id, platform=xapi_settings.PLATFORM_TRELLO)
    if len(tokens) == 1:
        # Update token
        token_storage = tokens[0]
        token_storage.token = token
    elif len(tokens) > 1:
        return HttpResponseServerError('<h1>Internal Server Error (500)</h1><p>More than one records were found.</p>')
    else:
        token_storage = OfflinePlatformAuthToken(user_smid=member_id, token=token, platform=xapi_settings.PLATFORM_TRELLO)
    token_storage.save()
    return Response(member_id)


##############################################
# Trello Data Extraction
##############################################
# TODO: ADD STUDENT REFRESH
@api_view()
def refreshtrello(request):
    course_id = request.GET.get('course_id')
    unit = UnitOffering.objects.get(id = course_id)
    trello_courseboard_ids = request.GET.get('boards')
    trello_courseboard_ids = trello_courseboard_ids.split(',')
    user_count = len(trello_courseboard_ids)

    trello_plugin = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_TRELLO]
    diag_count = 0
    # remove deplicated board IDs
    trello_courseboard_ids = list(set(trello_courseboard_ids))
    for board_id in trello_courseboard_ids:
        trello_user_course_map = UserPlatformResourceMap.objects.filter(
            unit=unit, platform=xapi_settings.PLATFORM_TRELLO).filter(resource_id=board_id)[0]

        user = trello_user_course_map.user
        usr_profile = UserProfile.objects.get(user=user)
        usr_offline_auth = OfflinePlatformAuthToken.objects.get(user_smid=usr_profile.trello_account_name)

        #print 'Performing Trello Board Import for User: %s' % (user)
        trello_plugin.perform_import(board_id, unit, token = usr_offline_auth.token)
        diag_count = diag_count + 1

    post_smimport(unit, xapi_settings.PLATFORM_TRELLO)

    # return Response('<b>Trello refresh complete: %s users updated.</b>' % (str(user_count)))
    html_response = HttpResponse()
    html_response.write('<b>Trello refresh complete: %s users updated.</b>' % (str(user_count)))
    html_response.write('<p><a href="/dashboard/myunits/">Go back to dashboard</a></p>')
    return html_response


##############################################
# GitHub Data Extraction
##############################################
def refreshgithub(request):

    html_response = HttpResponse()
    course_id = request.GET.get('course_id')
    unit = None
    try:
        unit = UnitOffering.objects.get(id=course_id)
    except UnitOffering.DoesNotExist:
        raise Http404
    
    resources = UserPlatformResourceMap.objects.filter(unit=course_id, platform=xapi_settings.PLATFORM_GITHUB)

    id_list = []
    details = []
    for resource in resources:
        # Save the repo name to avoid retrieving the same data again and again
        # If the repository name (resource_id) is in the id_list, the repo is already processed, so skip the process.
        if resource.resource_id in id_list:
            continue

        # Get user's token
        user = User.objects.get(pk=resource.user_id)
        token = OfflinePlatformAuthToken.objects.get(
            user_smid=user.userprofile.github_account_name, platform=xapi_settings.PLATFORM_GITHUB)
        obj = {'repo_name': resource.resource_id, 'token': token.token}
        details.append(obj)
        id_list.append(resource.resource_id)

    github_plugin = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_GITHUB]
    github_plugin.perform_import(details, unit)
    post_smimport(unit, xapi_settings.PLATFORM_GITHUB)

    return render(request, 'dataintegration/githubresult.html')




##############################################
# Data Extraction for YouTube
##############################################
def refreshgoogleauthflow(request):
    course_id = request.GET.get('course_id')
    channel_ids = request.GET.get('channel_ids')
    platform = request.GET.get('platform')
    unit = None
    try:
        unit = UnitOffering.objects.get(id=course_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    user = request.user
    platform_plugin = settings.DATAINTEGRATION_PLUGINS[platform]

    #print 'Got youtube plugin: %s' % (platform_plugin)
    #print 'With client ID and Secret key: %s and %s' % (platform_plugin.api_config_dict['CLIENT_ID'], platform_plugin.api_config_dict['CLIENT_SECRET'])

    # store request data in temp table
    # there is no other way to send these with the url (in querystring) as the return url must be registered
    # and session var won't save due to redirect
    twitter_id, fb_id, forum_id, blog_id, google_id, github_id, trello_id = get_smids_fromuid(user.id)
    t = OauthFlowTemp.objects.filter(user = request.user).delete()
    temp_transfer_data = OauthFlowTemp(platform=platform, transferdata=channel_ids, unit=unit, user = request.user)
    temp_transfer_data.save()

    client_id = ''
    client_secret = ''
    redirecturl = ''
    if platform == xapi_settings.PLATFORM_YOUTUBE:
        client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        redirecturl = get_youtube_callback_url(request)
    else:
        # When other Google service is integrated, there will be code here
        return HttpResponseServerError

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id = client_id,
        client_secret = client_secret,
        scope = platform_plugin.scope,
        redirect_uri = redirecturl
    )

    authUri = FLOW_YOUTUBE.step1_get_authorize_url()
    #Redirect to REDIRECT_URI
    return HttpResponseRedirect(authUri)


def ytAuthCallback(request):
    html_response = HttpResponse()
    youtube_plugin = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_YOUTUBE]
    redirecturl = get_youtube_callback_url(request)

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id=os.environ.get("YOUTUBE_CLIENT_ID"),
        client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET"),
        scope=youtube_plugin.scope,
        redirect_uri=redirecturl
    )

    http = googleAuth(request, FLOW_YOUTUBE)
    user = request.user
    t = OauthFlowTemp.objects.filter(user = request.user, platform = xapi_settings.PLATFORM_YOUTUBE)

    unit = t[0].unit
    platform = t[0].platform
    channel_ids = t[0].transferdata
    # Delete the record
    t.delete()

    # Start data import
    youtube_plugin.perform_import(channel_ids, unit, http)

    return render(request, 'dataintegration/ytresult.html', {})


##############################################
# Data Extraction for YouTube
##############################################
def get_youtubechannel(request):
    youtube_plugin = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_YOUTUBE]
    # redirecturl= 'http://' + get_current_site(request).domain + '/dataintegration/showyoutubechannel'
    redirecturl = get_youtube_user_channel_url(request)

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id=os.environ.get("YOUTUBE_CLIENT_ID"),
        client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET"),
        scope=youtube_plugin.scope,
        redirect_uri=redirecturl
    )

    authUri = FLOW_YOUTUBE.step1_get_authorize_url()
    #Redirect to REDIRECT_URI
    return HttpResponseRedirect(authUri)



def showyoutubechannel(request):

    youtube_plugin = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_YOUTUBE]
    # redirecturl= 'http://' + get_current_site(request).domain + '/dataintegration/showyoutubechannel'
    redirecturl = get_youtube_user_channel_url(request)

    FLOW_YOUTUBE = OAuth2WebServerFlow(
        client_id=os.environ.get("YOUTUBE_CLIENT_ID"),
        client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET"),
        scope=youtube_plugin.scope,
        redirect_uri=redirecturl
    )

    http = googleAuth(request, FLOW_YOUTUBE)
    channel_url = youtube_getpersonalchannel(request, http)
    html_response = HttpResponse()

    if channel_url:
        # Automatically set user's channel url in the textbox
        script_set_id = 'window.opener.$("#id_google_account_name").val("http://www.youtube.com/channel/%s");' % (channel_url)
        script_set_msg = 'window.opener.$("#youtube_channel_url_msg").html("%s");' % ('Got your YouTube channel URL!')
        # script_set_token = 'window.opener.$("#github_token").val("%s");' % (token)
        script_set_msg = script_set_msg + 'window.opener.$("#youtube_channel_url_msg").show();'
        script_set_msg = script_set_msg + 'window.opener.$("#youtube_auth_link").hide();'
        # Script for closing the popup window automatically
        html_resp = '<script>' + script_set_id + script_set_msg + 'window.close();</script>'
        html_response = HttpResponse()
        html_response.write(html_resp)
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

    blog_plugin = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_BLOG]

    course_id = request.GET.get('course_id')
    hastags = request.GET.get('urls')
    unit = None
    try:
        unit = UnitOffering.objects.get(id=course_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    urls = hastags.split(',')
    for url in urls:
        blog_plugin.perform_import(url, unit)

    post_smimport(unit, xapi_settings.PLATFORM_BLOG)

    html_response.write('Blog Refreshed.<br><p><a href="/dashboard/myunits/">Go back to dashboard</a></p>')
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
            html_response.write('<a href="/dashboard/myunits/">Go back to dashboard</a>')

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
                # html_response.write(u'<p>Hi {0}</p>'.format(result.user.name))
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
                        post_smimport(unit, xapi_settings.PLATFORM_FACEBOOK)

                        #Remove all data stored in session for this view to avoid cache issues
                        del request.session['platform']
                        del request.session['unit']
                        del request.session['group_id']

                        html_response.write('<h2>Facebook data import is complete.</h2>')
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


def github_auth(request):
    # Redirect to GitHub OAuth authentication page
    url = "https://github.com/login/oauth/authorize?"
    url = url + "client_id=%s" % (os.environ.get('GITHUB_CLIENT_ID'))
    url = url + "&redirect_uri=%s" % (os.environ.get('GITHUB_AUTH_REDIRECT_URL'))
    url = url + "&scope=user public_repo repo read:org"
    return redirect(url)

def github_client_auth(request):
    # This method is redirect url after user log in to GitHub and allows the CLA toolkit to
    # access to the user's information on GitHub.
    code = request.GET.get('code')
    url = "https://github.com/login/oauth/access_token?"
    # url = url + "scope=user public_repo repo read:org"
    url = url + "client_id=%s" % (os.environ.get('GITHUB_CLIENT_ID'))
    url = url + "&client_secret=%s" % (os.environ.get('GITHUB_CLIENT_SECRET'))
    url = url + "&code=%s" % (code)
    
    res = requests.get(url)
    res = res.text.split('&')[0]
    token = res.replace('access_token=', '')

    # Get access token 
    user_detail_url = "https://api.github.com/user?access_token=%s" % (token)
    res = requests.get(user_detail_url)
    user_json = json.loads(res.text)
    print user_json

    if not user_json.has_key('id'):
        return HttpResponseServerError('<h3>Error has occurred.</h3><p>Message: %s</p>' % (user_json['message']))
    # Save GitHub token
    # token_storage = OfflinePlatformAuthToken.objects.get(user_smid=user_json['id'], platform=xapi_settings.PLATFORM_GITHUB)
    # if token_storage:
    #     token_storage.token = token
    # else:
    #     token_storage = OfflinePlatformAuthToken(user_smid=user_json['id'], token=token, platform=xapi_settings.PLATFORM_GITHUB)
    tokens = OfflinePlatformAuthToken.objects.filter(user_smid=user_json['id'], platform=xapi_settings.PLATFORM_GITHUB)
    if len(tokens) == 1:
        token_storage = tokens[0]
        token_storage.token = token
    elif len(tokens) > 1:
        return HttpResponseServerError('<h1>Internal Server Error (500)</h1><p>More than one records were found.</h1>')
    else:
        token_storage = OfflinePlatformAuthToken(user_smid=user_json['id'], token=token, platform=xapi_settings.PLATFORM_GITHUB)
    token_storage.save()

    # Set user ID and access token in social media ID register or update page
    script_set_id = 'window.opener.$("#id_github_account_name").val("%s");' % (user_json['id'])
    script_set_msg = 'window.opener.$("#github-auth-msg").html("%s");' % ('GitHub user ID linked!')
    # script_set_token = 'window.opener.$("#github_token").val("%s");' % (token)
    script_set_msg = script_set_msg + 'window.opener.$("#github-auth-msg").show();'
    script_set_msg = script_set_msg + 'window.opener.$("#github_auth_link").hide();'

    html_resp = '<script>' + script_set_id + script_set_msg + 'window.close();</script>'
    html_response = HttpResponse()
    html_response.write(html_resp)
    return html_response