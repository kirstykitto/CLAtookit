__author__ = 'zak'

import os
import json

from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User

from connector import AuthRequest
from xapi.models import OAuthTempRequestToken, ClientApp
from xapi.models import UserAccessToken_LRS as AccessToken

"""
This file contains code used to connect to an LRS via Oauth and
retreive various access tokens.

Utilising OAuth 1.0, the flow used to connect to the LRS is as follows:

Send auth request to LRS with callback as parameter, and:
oauth_consumer_key, oauth_signature_method, oauth_signature, oauth_nonce, oauth_timestamp
as headers. The oauth_signature is created using basic signature string hashed using
HMAC-SHA1 digest

GET http://lrs/xapi/OAuth/initiate?oauth_callback=http://callback_url

If this process if successful, the LRS will respond with:
oauth_token, oauth_token_secret, and oauth_callback_confirmed. Next, we exchange the token
with the LRS for an access token with the oauth_token and oauth_callback as params.

GET http://lrs/xapi/OAuth/authorize?oauth_token=token_code&oauth_callback=http://callback_url

In this step, the LRS will redirect to the given callback with a oauth_verifier code where the user
confirms the authorization process.

GET http://lrs/xapi/OAuth/token

Upon the user accepting, a final request is sent back to the lrs with:
oauth_consumer_key, oauth_token, oauth_signature_method, oauth_signature, oauth_verifier, oauth_timestamp,
oauth_nonce. Once again, the signature is created by hashing the basic signature string via HMAC-SHA1. If
this process succeeds, the LRS will return the access token to make authorized requests.

"""

class LRS_Auth(object):

    CALLBACK_PATH = '/xapi/lrsauth_callback'

    def __init__(self, provider_id, callback = None, **kwargs):
        try:
            app = ClientApp.objects.get(id = provider_id)
        except ObjectDoesNotExist:
            raise ValueError('Could not initialize LRS_Auth instance. Provider ID: %s' % provider_id)

        self.CONSUMER_KEY = app.get_key()
        self.CONSUMER_SECRET = app.get_secret()

        self.BASE_URL = app.get_base_url()
        self.REQUEST_TOKEN_URL = app.get_auth_request_url()
        self.ACCESS_TOKEN_URL = app.get_access_token_url()
        self.AUTHORIZATION_URL = app.get_authorization_url()
        self.STATEMENTS_URL = app.get_xapi_statement_url()
        self.PROVIDER_ID = provider_id
        self.CALLBACK_URL = ''
        if callback is not None:
            self.CALLBACK_URL = callback + self.CALLBACK_PATH


        # Save Access-token exchange url to env TODO: Find a better way to handle this.
        # os.environ['ACCESS_TOKEN_URL'] = self.ACCESS_TOKEN_URL


    def get_statement(self, user_id, filters=None, limit=None, more_path = None):
        #Get user access token
        user = User.objects.get(id=user_id)
        t = None
        try:
            t = AccessToken.objects.get(user_id=user)
        except AccessToken.DoesNotExist:
            # raise Exception("Error has occurred. User %s does not have LRS access token." % (user.username))
            print "***** Error has occurred. User %s does not have LRS access token. *****" % (user.username)
            return

        # When user wants xAPI statements in next page 
        # (LRS returnes up to 100 statements at once if user does not specify limit)
        statement_url = self.STATEMENTS_URL
        if more_path:
            statement_url = self.BASE_URL + more_path

        consumer = AuthRequest(self.CONSUMER_KEY,self.CONSUMER_SECRET,
                               token = t.access_token, token_secret = t.access_token_secret)

        kwargs = {}
        #extract filters
        if filters is not None:
            kwargs['filters'] = filters

        (code,content) = consumer.request(statement_url, **kwargs)

        if str(code) != '200':
            raise Exception("Could not get xapi statments. Status: %s, Message: %s" % (code,content))
        else:
            return json.loads(content)



    # function for sending xapi statements to the LRS
    # requires user_id to retreive user access token
    # TODO: Implement batch sends
    def transfer_statement(self, user_id, statement=None, batch=False):

        if not batch and statement is not None:
            #Get user access token
            user = User.objects.get(id=user_id)
            t = None
            try:
                t = AccessToken.objects.get(user_id=user)
            except AccessToken.DoesNotExist:
                # raise Exception("Error has occurred. User %s does not have LRS access token." % (user.username))
                print "Error has occurred. User %s does not have LRS access token. Data will not be imported." % (user.username)
                return

            consumer = AuthRequest(self.CONSUMER_KEY,self.CONSUMER_SECRET,
                                   token=t.access_token,token_secret=t.access_token_secret)
            (code, content) = consumer.request(self.STATEMENTS_URL, data=statement)
            
            # ADL_LRS returns status 204 for successful statement transfers
            if str(code) != '200' and str(code) != '204':
                raise Exception("Could not send xapi statement with status code %s. Message: %s" % (code,content))
            else:
                # return 'xAPI was successfully sent. HTTP Code: %s, content: %s' % (code, content)
                return code, content


    def authenticate(self, user_id):

        import urlparse

        # Create a consumer utilising the key and secret provided by lrs
        # Because this is an auth-flow we need to supply a callback url
        consumer = AuthRequest(self.CONSUMER_KEY,self.CONSUMER_SECRET,callback=self.CALLBACK_URL)

        # 1st Leg: Get temp request token to exchange for access token
        # print 'Getting temp req token from: %s' % self.REQUEST_TOKEN_URL

        # print "self.REQUEST_TOKEN_URL  %s " % (self.REQUEST_TOKEN_URL)
        (status_code,content) = consumer.request(self.REQUEST_TOKEN_URL)

        # We're expecting a dict (request/response)
        # a string here likely is an error string
        #if type(resp) is str:
        #    raise Exception(resp)

        #print 'Got response code: %s' % resp.getcode()

        # status code 200 to let us know everything is a-okay
        if  status_code != 200:
            raise Exception("Unexpected server response: %s. Message: %s" % (status_code,content))

        # parse qsl and get returned data
        request_token = dict(urlparse.parse_qsl(content))

        #print "Request Token:"
        #print "     - oauth_token           = %s" % request_token['oauth_token']
        #print "     - oauth_token_secret    = %s" % request_token['oauth_token_secret']
        #print "     - callback_confirmed    = %s" % request_token
        #print

        # Store temp token and and temp token_secret for 3rd leg of auth
        # in the 3rd leg, we exchange this temp token & secret for authorized access_token
        user = User.objects.get(id=user_id)
        app = ClientApp.objects.get(id = self.PROVIDER_ID)
        tmp_reqToken = OAuthTempRequestToken(user_id=user_id, token=request_token['oauth_token'], 
            secret=request_token['oauth_token_secret'], clientapp = app)
        tmp_reqToken.save()

        # 2nd leg: Redirect to lrs to allow user to confirm access token permissions
        return self.lrs_2ndstep_redirect(request_token['oauth_token'], self.CALLBACK_URL, self.CONSUMER_KEY, user_id)

    def lrs_2ndstep_redirect(self, token, callback, consumer_key, user):
        oauth_token_param = '?oauth_token=%s' % token
        oauth_callback_param = '&oauth_callback=%s' % callback
        consumer_key = '&consumer_key=%s' % consumer_key
        user = '&clau=%s' % user

        # print 'authorization url: ' + self.AUTHORIZATION_URL + oauth_token_param + oauth_callback_param + consumer_key

        #3rd leg found in views.py
        return self.AUTHORIZATION_URL + oauth_token_param + oauth_callback_param + consumer_key + user





#class DefaultLRS():












###################################
##           Graveyard           ##
###################################

"""import time
import oauth.oauth as oauth
import requests
import urlparse
import cgi
from urllib import urlencode

#Local/production settings
LOCAL = True
SCHEME = 'http' if LOCAL else 'https' #http
SERVER = '127.0.0.1' if LOCAL else 'lrs.beyondlms.org'
PORT = '8000' if LOCAL else '443' #8000

# fake urls for test server
REQUEST_TOKEN_URL = '%s://%s:%s%s' % (SCHEME,SERVER,PORT,'xapi/oauth/initiate')
ACCESS_TOKEN_URL = '%s://%s:%s%s' % (SCHEME,SERVER,PORT,'xapi/oauth/token')
AUTHORIZATION_URL = '%s://%s:%s%s' % (SCHEME,SERVER,PORT, 'xapi/oauth/authorize')
CALLBACK_URL = 'oob'
RESOURCE_URL = '%s://%s:%s%s' % (SCHEME,SERVER,PORT, 'xapi/statements')

# include scope if required
INCLUDE_SCOPE = False

# scope (space delimited)
SCOPE = {"scope": "statements/write define statements/read/mine"}

# error file location
ERROR_FILE = '/error.html'

class SimpleOAuthClient(oauth.OAuthClient):

    def __init__(self, request_token_url='', access_token_url='', authorization_url=''):
        self.request_token_url = request_token_url
        self.access_token_url = access_token_url
        self.authorization_url = authorization_url

    def fetch_request_token(self, oauth_request):
        path = oauth_request.to_url()

        if (INCLUDE_SCOPE):
            path = path + "&%s" % urlencode(SCOPE)

        response = requests.get(path, header=oauth_request.to_header(), verify=False)

        if response.status_code != 200:
            print 'Failure: %s' % response.status_code

            f = open(ERROR_FILE, 'w')
            f.write(response.content)
            f.close()
            print 'Error written to %s' % ERROR_FILE

        return oauth.OAuthToken.from_string(response.content)

    def fetch_access_token(self, oauth_request):
        response = requests.get(oauth_request.to_url(), headers=oauth_request.to_header(), verify=False)

        return oauth.OAuthToken.from_string(response.content)

    def authorize_token(self, oauth_request):
        response = requests.get(oauth_request.to_url(), allow_rediects=False, verify=False)

        # rediect code expected
        if response.status_code != 200:
            if response.status_code > 300  and response.status_code < 400:
                newurl = response.headers['location']
                parts = urlparse.urlparse(newurl)[2:]

                print parts[2]

                u = urlparse.urlparse(parts[2])

                return 'http://localhost:8000?oauth_verifier=%s' % raw_input("go to %s, verify, enter PIN here: " % u['next'])

            else:
                print "Failure: %s" % response.status_code
                f = open(ERROR_FILE, 'w')
                f.write(response.content)
                f.close()
                print "text written to %s" % ERROR_FILE
                raise Exception("Something didnt work right\nresponse: %s -- %s" % (response.status_code, response.content))
"""
