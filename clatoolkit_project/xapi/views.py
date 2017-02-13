import oauth2 as oauth
from clatoolkit.models import UnitOffering
from common.util import Utility
from django.http import HttpResponse, HttpResponseServerError
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect

from models import OAuthTempRequestToken, UserAccessToken_LRS, ClientApp
from oauth_consumer.operative import LRS_Auth
from xapi.statement.xapi_getter import xapi_getter
from xapi.statement.xapi_filter import xapi_filter



@login_required
def get_lrs_access_token(request):
    provider_id = request.GET.get('provider_id')
    auth = LRS_Auth(provider_id = provider_id, callback = Utility.get_site_url(request))
    return redirect(auth.authenticate(request.user.id))


# Create your views here.
@login_required
def lrs_test_get_statements(request):
    unit_id = request.GET.get('unit_id')
    user_id = request.GET.get('user_id')
    
    unit = None
    user = None
    try:
        unit = UnitOffering.objects.get(id = unit_id)
    except ObjectDoesNotExist:
        return HttpResponseServerError('Error. Unit was not found.')

    if user_id is None or user_id == '':
        return HttpResponseServerError('Error. User was not found.')

    params = None
    if request.GET:
        params = dict(request.GET.iterlists())
        keys = params.keys()
        # Convert key:listvalue from querydict to items suitable for dict
        for i in range(len(keys)):
            if type(params[keys[i]]) is 'list' and len(params[keys[i]]) == 1:
                params[keys[i]] = params[keys[i]][0]

    filters = xapi_filter()
    getter = xapi_getter()
    ret = getter.get_xapi_statements(unit_id, user_id, filters)
    lrs = LRS_Auth(provider_id = unit.lrs_provider.id)
    ret = lrs.get_statement(user_id, filters=params)
    print ret
    
    # filters = xapi_filter()
    # filters.course = unit.code

    # # if platform is not None and platform != "all":
    # #     filters.platform = platform

    # getter = xapi_getter()
    # ret = getter.get_xapi_statements(unit_id, user_id, filters)

    # print 'statements count: %s ' % str(len(ret))
    
    # from datetime import datetime
    # import pytz
    # zone = pytz.timezone('Brisbane')


    # for stmt in ret:
    #     stmt_date = stmt['timestamp']
    #     # tdatetime = datetime.strptime(stmt_date, '%Y-%m-%d %H:%M:%S%z')
    #     jst_datetime_str = datetime.strftime(jst_datetime, '%Y-%m-%d %H:%M:%S %z')
    #     print tdatetime

    return HttpResponse(ret)


@login_required
def lrs_test_send(request):
    unit_id = request.GET.get('unit_id')
    unit = None
    try:
        unit = UnitOffering.objects.get(id = unit_id)
    except ObjectDoesNotExist:
        return HttpResponseServerError('Error. Unit was not found.')

    lrs = LRS_Auth(provider_id = unit.lrs_provider.id)
    statement = get_test_xAPI()
    return HttpResponse(lrs.transfer_statement(request.user.id, statement = statement))


def lrs_oauth_callback(request):
    import os
    import urlparse

    user_id = request.GET.get('user', None)

    print 'USERID: %s' % (user_id)
    user = User.objects.get(id=user_id)

    status = request.GET.get('status')
    if status is not None and status == 'fail':
        return HttpResponseServerError('Could not get access token.')

    request_token = OAuthTempRequestToken.objects.get(user_id=user)
    verifier = request.GET.get('oauth_verifier')

    token = oauth.Token(request_token.token, request_token.secret)
    request_token.delete() #delete temp token
    token.set_verifier(verifier)

    # Get Consumer info #Todo: change (most definitely) (IMPORTANT!!)
    # consumer_key, consumer_secret = get_consumer_key_and_secret()
    app = ClientApp.objects.get(id = request_token.clientapp.id)
    client = oauth.Client(oauth.Consumer(app.get_key(), app.get_secret()), token)

    # Exchange request_token for authed and verified access_token
    resp,content = client.request(app.get_access_token_url(), "POST")
    access_token = dict(urlparse.parse_qsl(content))

    if access_token['oauth_token']:
        UserAccessToken_LRS(user=user, access_token=access_token['oauth_token'],
                            access_token_secret=access_token['oauth_token_secret'],
                            clientapp = app).save()
        from django.shortcuts import render_to_response
        return render_to_response('xapi/get_access_token_successful.html')


def get_test_xAPI():
    return """{
        "id": "dc382d58-173a-4782-886d-7da23a700015",
        "verb": {
            "display": {
                "en-US": "created"
            },
            "id": "http://www.w3.org/ns/activitystreams#Create"
        },
        "timestamp": "2016-11-01T08:33:28.423000+00:00",
        "object": {
            "definition": {
                "type": "http://activitystrea.ms/specs/json/schema/activity-schema.html#task",
                "name": {
                    "en-US": "Add after removing board ID from the toolkit..."
                }
            },
            "id": "http://www.test.com/5818535876f64eded095ae82",
            "objectType": "Activity"
        },
        "actor": {
            "account": {
                "homePage": "http://www.trello.com/",
                "name": "clatoolkitdev"
            },
            "objectType": "Agent"
        },
        "authority": {
        "member": [
            {
                "mbox": "mailto:clatoolkitdev@gmail.com",
                "name": "clatoolkit",
                "objectType": "Agent"
            },
            {
                "account": {
                    "homePage": "http://example.com/XAPI/OAuth/token/",
                    "name": "4a77c7336e92425d9e56ec7bdb58223d"
                },
                "objectType": "Agent"
            }
        ],
        "objectType": "Group"
    },
        "version": "1.0.1",
        "context": {
            "platform": "Trello",
            "contextActivities": {
                "other": [],
                "parent": [
                    {
                        "id": "http://test.com/aaa",
                        "objectType": "Activity"
                    }
                ],
                "grouping": [
                    {
                        "definition": {
                            "name": {
                                "en-US": "TEST-UNIT"
                            },
                            "description": {
                                "en-US": "TEST-UNIT"
                            }
                        },
                        "id": "http://test.com/TEST-UNIT",
                        "objectType": "Activity"
                    }
                ]
            },
            "registration": "dc382d58-173a-4722-886d-7da68a925924"
        }
    }"""