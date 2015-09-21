# example/simple/views.py
from __future__ import absolute_import

from django.http import HttpResponse
from django.shortcuts import render, render_to_response
from authomatic import Authomatic
from authomatic.adapters import DjangoAdapter
from authomatic.providers import oauth2

from django.template import RequestContext

from dataintegration.tasks import *
from .forms import FacebookGatherForm
#from dataintegration.forms import UserForm, UserProfileForm
import json
from pprint import pprint
from clatoolkit.models import UnitOffering, DashboardReflection, LearningRecord

### YouTube Integration ###
"""
from django.shortcuts import render
from django.http import HttpResponseRedirect
from oauth2client.client import OAuth2WebServerFlow
import httplib2
from apiclient.discovery import build
"""
from dataintegration.googleLib import *

courseCode = None
channelIds = None
#videoIds = None
courseId = None


##############################################
# Data Extraction for YouTube
##############################################
def refreshyoutube(request):
    global courseCode
    global channelIds
    global courseId
    courseCode = request.GET.get('course_code')
    channelIds = request.GET.get('channelIds')
    #videoIds = request.GET.get('videoIds')
    courseId = request.GET.get('course_id')

    authUri = FLOW_YOUTUBE.step1_get_authorize_url()
    #Redirect to REDIRECT_URI
    return HttpResponseRedirect(authUri)


##############################################
# Callback method from OAuth
##############################################
def ytAuthCallback(request):
    #Authenticate 
    http = googleAuth(request, FLOW_YOUTUBE)
    #Store extracted data into LRS
    ytList = injest_youtube(request, courseCode, channelIds, http, courseId)

    vList = ytList[0]
    vNum = len(vList)
    commList = ytList[1]
    commNum = len(commList)
    context_dict = {"vList": vList, "vNum": vNum, "commList": commList, "commNum": commNum}
    return render(request, 'dataintegration/ytresult.html', context_dict)


CONFIG = {
    # Auth information for Facebook App
    'fb': {
        'class_': oauth2.Facebook,

        'consumer_key': '',
        'consumer_secret': '',

        'scope': ['user_about_me', 'email', 'user_groups'],
    },
}

authomatic = Authomatic(CONFIG, '')


def home(request):
    form = FacebookGatherForm()
    return render(request, 'dataintegration/facebook.html', {'form': form})

def refreshtwitter(request):
    html_response = HttpResponse()

    course_code = request.GET.get('course_code')
    hastags = request.GET.get('hashtags')

    t = LearningRecord.objects.filter(platform='Twitter',course_code=course_code).delete()

    tags = hastags.split(',')
    for tag in tags:
        injest_twitter(tag, course_code)
    html_response.write('Twitter Refreshed.')
    return html_response

def login(request, group_id):
    # We we need the response object for the adapter.
    html_response = HttpResponse()

    result = authomatic.login(DjangoAdapter(request, html_response), 'fb')

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
            #course_code = request.GET.get('course_code')
            #platform = request.GET.get('platform')
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

                # Each provider has it's specific API.
                if result.provider.name == 'fb':
                    # Construct Facebook group Graph API call
                    #group_id = request.GET.get('group_id')

                    url = 'https://graph.facebook.com/'+group_id+'/feed'
                    unit_offering = UnitOffering.objects.filter(facebook_groups=group_id) #request.GET.get('course_code')
                    course_code = unit_offering[0].code
                    # Access user's protected resource.
                    access_response = result.provider.access(url)
                    #print access_response
                    #print access_response.data.get('data')
                    #fb_json = json.loads(access_response.data.get('data'))
                    #pprint(access_response.data.get('data'))
                    fb_feed = access_response.data.get('data')
                    paging = access_response.data.get('paging')
                    #pprint(paging)
                    #pprint(fb_json)
                    t = LearningRecord.objects.filter(platform='Facebook',course_code=course_code).delete()
                    injest_facebook(fb_feed, paging, course_code)
                    #injest_twitter("#clatest", "cla101")
                    html_response.write('Updating Facebook for ' + course_code)
                    '''
                    if access_response.status == 200:
                        # Parse response.
                        data = access_response.data.get('data')
                        paging = access_response.data.get('paging')
                        error = access_response.data.get('error')
                        if error:
                            html_response.write(u'Error: {0}!'.format(error))
                        elif data:
                            #result = send_data_to_lrs.delay(data, paging, html_response)
                            send_data_to_lrs(data, paging, html_response)
                            #print result.id
                            #html_response.write('<p>Data is being collected from the Facebook Page with an ID of ' + group_id + '</p>')
                            #html_response.write('<p>View your task status <a href="http://localhost:5555/'
                            #                    'task/'+result.id+'">here.</a></p>')
                            html_response.write('<p>Data was collected from the Facebook Page with an ID of ' + group_id + '</p>')

                    else:
                        html_response.write('Unknown error<br />')
                        html_response.write(u'Status: {0}'.format(html_response.status))
                    '''
    else:
        html_response.write('Auth Returned no Response.')

    return html_response

'''
def register(request):
    # Like before, get the request's context.
    context = RequestContext(request)

    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST)

        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            # Save the user's form data to the database.
            user = user_form.save()

            # Now we hash the password with the set_password method.
            # Once hashed, we can update the user object.
            user.set_password(user.password)
            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            profile.user = user

            # Now we save the UserProfile model instance.
            profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            print user_form.errors, profile_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserForm()
        profile_form = UserProfileForm()


    # Render the template depending on the context.
    return render_to_response(
        'dataintegration/register.html',
            {'user_form': user_form, 'profile_form': profile_form, 'registered': registered},
            context)
'''
def get_social_media_id(request):
    '''
    Gets users social media IDs for use in signup for information integration.
    :param request:
    :return:
    '''
    # TODO: Add social media functionality apart from facebook
    # We we need the response object for the adapter.
    html_response = HttpResponse()

    result = authomatic.login(DjangoAdapter(request, html_response), 'fb')


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
