### These modules are required.
from django.http import HttpResponse
from django.shortcuts import render
from django.http import HttpResponseRedirect
from oauth2client.client import OAuth2WebServerFlow
import httplib2
from apiclient.discovery import build

CLIENT_ID = ''
CLIENT_SECRET = ''
SCOPE_YOUTUBE = 'https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtubepartner'
REDIRECT_URI = 'http://127.0.0.1:8000/dataintegration/ytAuthCallback'

STR_YT_VIDEO_BASE_URL = "https://www.youtube.com/watch?v="
STR_YT_CHANNEL_BASE_URL = "https://www.youtube.com/channel/"
STR_PLATFORM_NAME_YOUTUBE = "YouTube"
STR_PLATFORM_URL_YOUTUBE = "https://www.youtube.com"
STR_OBJ_TYPE_VIDEO = 'Video'


# For YouTube OAuth authentication
FLOW_YOUTUBE = OAuth2WebServerFlow(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scope=SCOPE_YOUTUBE,
    redirect_uri=REDIRECT_URI
)

"""
# For Google Drive OAuth authentication
FLOW_GDRIVE = OAuth2WebServerFlow(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scope=SCOPE_YOUTUBE,
    redirect_uri=REDIRECT_URI
)
"""

##############################################
# Google API authentication step 2
##############################################
def googleAuth(request, flow):
    #Authenticate
    code = request.GET.get('code', None)
    #credentials = FLOW.step2_exchange(code)
    credentials = flow.step2_exchange(code)
    http = httplib2.Http()
    http = credentials.authorize(http)
    return http
