import datetime
import random
import requests
from .utils import *
from functools import wraps
from django.shortcuts import render
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseServerError
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import connection
from django.db.models import Count
from django.db.models import Q
from clatoolkit.models import OfflinePlatformAuthToken, UserProfile, OauthFlowTemp, UnitOffering, UnitOfferingMembership, DashboardReflection, LearningRecord, Classification, UserClassification, GroupMap, UserPlatformResourceMap
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from xapi.models import ClientApp, UserAccessToken_LRS
from xapi.statement.xapi_settings import xapi_settings
from xapi.statement.xapi_filter import xapi_filter
from xapi.statement.xapi_getter import xapi_getter



#API endpoint to grab a list of trello boards to attach to course
@login_required
@api_view()
def get_trello_boards(request):
    user_profile = UserProfile.objects.get(user=request.user)
    trello_member_id = user_profile.trello_account_name
    token_qs = None
    try:
        token_qs = OfflinePlatformAuthToken.objects.get(user_smid=trello_member_id)
    except ObjectDoesNotExist:
        # When user smid is not found (This occurs when user hasn't registered their Trello ID yet)
        token_qs = None

    # Return error message to the client
    if token_qs is None:
        html_tags = '<p class="no-trello-id">Your Trello account is incorrect or not found.<br>'
        html_tags = html_tags + 'Register your account in Social Media Accounts update page before attaching a Trello board.<br>'
        html_tags = html_tags + '(Click your name (top right corner) - Social Media Accounts)</p>'
        return Response(('').join([html_tags]))

    token = token_qs.token
    key = os.environ.get('TRELLO_API_KEY')
    course_id = request.GET.get('course_id')
    trello_boardsList_url = 'https://api.trello.com/1/member/me/boards?key=%s&token=%s' % (key,token)

    r = requests.get(trello_boardsList_url)
    #print "got response %s" % r.json()
    boardsList = r.json()
    board_namesList = []
    board_namesList.append('<ul>')

    for board in boardsList:
        board_namesList.append('<li>')
        #board = json.load(board)

        #format to something nice :)
        board_name = board['name']
        board_url = board['url']
        board_id = board['id']
        html_resp = '<a href="#" class="board_choice" onclick="javascript:add_board(\''+course_id+'\',\''+board_id+'\',\'Trello\')">'+board_name+'</a>'

        board_namesList.append(html_resp)
        board_namesList.append('</li>')
    board_namesList.append('</ul>')

    return Response(('').join(board_namesList))

@login_required
@api_view()
#API endpoint to allow students to attach a board to course
def add_board_to_course(request):
    course = UnitOffering.objects.get(id=request.GET.get('course_id'))
    board_list = course.attached_trello_boards

    if board_list == '':
        new_board_list = request.GET.get('id')
    else:
        new_board_list = board_list+','+request.GET.get('id')

    course.attached_trello_boards = new_board_list
    course.save()

    trello_user_course_map = UserPlatformResourceMap(
        user=request.user, unit=course, resource_id=request.GET.get('id'), platform=xapi_settings.PLATFORM_TRELLO)
    trello_user_course_map.save()

    return Response('<b>Board successfully added to course - <a href="/dashboard/myunits/">Reload</a></b>')


def check_access(required_roles=None):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            # Check that user has correct role
            role = request.user.userprofile.role
            correct_role = False
            if role in required_roles:
                correct_role = True

            if correct_role:
                if request.method == 'POST':
                    course_id = request.POST['course_id']
                else:
                    course_id = request.GET.get('course_id')

                # Check that user is a member of the course
                unit = UnitOffering.objects.filter(id = course_id, users = request.user.id)
                if (len(unit) != 0):
                    return view(request, *args, **kwargs)
                else:
                    return HttpResponse('Access Denied - Not assigned to unit.')
            else:
                return HttpResponse('Access Denied - Incorrect Role.')
        return wrapper
    return decorator


@login_required
@api_view()
def trello_remove_board(request):
    course_id = request.GET.get('course_id')

    trello_user_course_map = None
    unit = None
    try:
        # trello_user_course_map = UserTrelloCourseBoardMap.objects.filter(user=request.user, course_code=course_code)
        trello_user_course_map = UserPlatformResourceMap.objects.filter(user=request.user, unit=course_id,
            platform=xapi_settings.PLATFORM_TRELLO)
        unit = UnitOffering.objects.get(id=course_id)
    except ObjectDoesNotExist:
        return HttpResponseServerError('<h2>Internal Server Error (500)</h2><p>Could not remove Trello Board.</p>')

    new_board_list = []
    same_board_list = []
    for board in unit.attached_trello_boards.split(','):
        if board != trello_user_course_map[0].resource_id:
            new_board_list.append(board)
        else:
            same_board_list.append(board)

    # Multiple users are likely to use the same Trello board.
    # So, two or more same board IDs are likely to be found in unit.attached_trello_boards column.
    # Since we only want to delete the user's board ID, we remove one of the same board IDs from the column.
    #
    # attached_trello_boards column only has board IDs.
    # So, we cannot identify exactly which ID is the user's when multiple same IDs exist.
    for index in range(1, len(same_board_list)):
        # Start the for loop from 1 (not 0) to remove one of the same board IDs.
        new_board_list.append(same_board_list[index])
    unit.attached_trello_boards = ','.join(new_board_list)

    unit.save()
    trello_user_course_map.delete()
    return myunits(request)

@login_required
@api_view()
def trello_myunits_restview(request):
        #Get course code, and match it with the user to obtain the board ID for the user for their specified course.
        course_id = request.GET.get('course_id')
        trello_user_course_map = UserPlatformResourceMap.objects.filter(
            user=request.user, unit=course_id, platform=xapi_settings.PLATFORM_TRELLO)

        #If a board exists for the user and it's attached to the course
        if trello_user_course_map:
            #Get user auth token for trello
            token_qs = OfflinePlatformAuthToken.objects.filter(user_smid=request.user.userprofile.trello_account_name)

            #if the token exists, grab the board from trello on behalf of the user
            if token_qs:
                key = os.environ.get("TRELLO_API_KEY")
                http = 'https://api.trello.com/1/boards/%s?key=%s&token=%s' % (trello_user_course_map[0].resource_id, key, token_qs[0].token)
                r = requests.get(http)
                board = r.json()
                response = {'data': '<a href="'+board['url']+'""><i class="fa fa-trello" aria-hidden="true"></i>   '+board['name']+'</a> | '
                            '<a href="/dashboard/removeBoard?course_id='+course_id+'">Remove</a>', 'course_id': course_id}

                return Response(response)

        else: #Otherwise, we'll give the student the option to attach their trello board
            response = {'data': '<a href="#" onclick="javascript:get_and_link_board(\''+course_id+'\')">Attach a Trello Board to plan your Work!</a>'
                            '<div id="trello_board_display"></div>', 'course_id': course_id}
            return Response(response)


@login_required
def myunits(request):
    context = RequestContext(request)

    # Get a users memberships to unit offerings
    memberships = UnitOfferingMembership.objects.filter(user=request.user, unit__enabled=True).select_related('unit')

    role = request.user.userprofile.role
    show_dashboardnav = False
    shownocontentwarning = False
    trello_attached = not request.user.userprofile.trello_account_name == ''
    github_attached = False
    tokens = OfflinePlatformAuthToken.objects.filter(
        user_smid=request.user.userprofile.github_account_name, platform=xapi_settings.PLATFORM_GITHUB)
    if len(tokens) == 1:
        github_attached = True

    has_token_list = {}
    for membership in memberships:
        token = UserAccessToken_LRS.objects.filter(user = request.user, clientapp = membership.unit.lrs_provider)
        has_user_token = True if len(token) == 1 else False
        if len(token) > 1:
            return HttpResponseServerError('More than one access token were found.')

        app = membership.unit.lrs_provider
        has_token_list[membership.unit.code] = {'lrs': app.provider, 'has_user_token': has_user_token}

    # if student check if the student has imported data
    if role == 'Student':
        if LearningRecord.objects.filter(user=request.user).count() == 0:
            shownocontentwarning = True

    context_dict = {'title': "My Units", 'memberships': memberships, 'show_dashboardnav': show_dashboardnav,
                    'shownocontentwarning': shownocontentwarning, 'role': role,
                    'trello_attached_to_acc': trello_attached, 'has_token_list': has_token_list,
                    'github_attached': github_attached}

    return render_to_response('dashboard/myunits.html', context_dict, context)

@login_required
def dashboard(request):
    context = RequestContext(request)

    unit_id = request.GET.get('unit')
    unit = UnitOffering.objects.get(id=unit_id)

    # If the user is an admin for the course
    if UnitOfferingMembership.is_admin(request.user, unit):
        # user = request.user
        platform = request.GET.get('platform')

        title = "Activity Dashboard: %s (Platform: %s)" % (unit.code, platform)
        show_dashboardnav = True

        # A flag for showing a platform activity time series and pie chart
        show_allplatforms_widgets = True
        if platform != "all":
            show_allplatforms_widgets = False

        activity_pie_series = get_verb_pie_data(unit, platform = platform)
        platformactivity_pie_series = get_platform_pie_data(unit)

        # Activity Time line data (verbs and platform)
        timeline_data = get_verb_timeline_data(unit, platform, None)
        platform_timeline_data = get_platform_timeline_data(unit, platform, None)

        # p = platform if platform != "all" else None
        activememberstable = get_active_members_table(unit, platform)
        topcontenttable = get_cached_top_content(platform, unit)

        context_dict = {
            'title': title, 'course_code':unit.code, 'platform':platform, 'show_dashboardnav':show_dashboardnav,
            'activememberstable': activememberstable, 'unit': unit,
            'topcontenttable': topcontenttable, 'show_allplatforms_widgets': show_allplatforms_widgets,

            'posts_timeline': timeline_data['posts'], 'shares_timeline': timeline_data['shares'],
            'likes_timeline': timeline_data['likes'], 'comments_timeline': timeline_data['comments'],

            'twitter_timeline': platform_timeline_data[xapi_settings.PLATFORM_TWITTER],
            'facebook_timeline': platform_timeline_data[xapi_settings.PLATFORM_FACEBOOK],
            'youtube_timeline': platform_timeline_data[xapi_settings.PLATFORM_YOUTUBE],
            'blog_timeline': platform_timeline_data[xapi_settings.PLATFORM_BLOG],
            'trello_timeline': platform_timeline_data[xapi_settings.PLATFORM_TRELLO],
            'github_timeline': platform_timeline_data[xapi_settings.PLATFORM_GITHUB],
            'forum_timeline': [], 'diigo_timeline':[],

            'activity_pie_series': activity_pie_series, 'platformactivity_pie_series': platformactivity_pie_series
            }

        return render_to_response('dashboard/dashboard.html', context_dict, context)

    else:
        raise PermissionDenied


@login_required
def cadashboard(request):
    context = RequestContext(request)

    platform = None
    no_topics = 3

    if request.method == 'POST':
        unit_id = request.POST['unit']
        platform = request.POST['platform']
        no_topics = int(request.POST['no_topics'])
    else:
        unit_id = request.GET.get('unit')
        platform = request.GET.get('platform')

    unit = UnitOffering.objects.get(id=unit_id)

    if UnitOfferingMembership.is_admin(request.user, unit):
        title = "Content Analysis Dashboard: %s (Platform: %s)" % (unit.code, platform)

        # timeline_data = get_verb_timeline_data(unit, None)
        timeline_data = get_verb_timeline_data(unit, platform, None)
        # Word Cloud
        tags = get_wordcloud(platform, unit)
        # Sentiments pie chart
        sentiments = getClassifiedCounts(platform, unit, classifier="VaderSentiment")
        # Community of Inquiry
        coi = getClassifiedCounts(platform, unit, classifier="NaiveBayes_t1.model")

        topic_model_output, sentimenttopic_piebubblesdataset = nmf(platform, no_topics, unit, start_date=None, end_date=None)

        context_dict = {'show_dashboardnav': True, 'unit': unit, 'platform': platform, 'title': title,

                        'posts_timeline': timeline_data['posts'], 'shares_timeline': timeline_data['shares'],
                        'likes_timeline': timeline_data['likes'], 'comments_timeline': timeline_data['comments'],

                        'sentiments': sentiments, 'coi': coi, 'tags': tags,
                        'no_topics': no_topics, 'topic_model_output': topic_model_output,
                        'sentimenttopic_piebubblesdataset': sentimenttopic_piebubblesdataset}

        return render_to_response('dashboard/cadashboard.html', context_dict, context)

    else:
        raise PermissionDenied


@login_required
def snadashboard(request):
    context = RequestContext(request)

    unit_id = request.GET.get('unit')
    unit = UnitOffering.objects.get(id=unit_id)

    if UnitOfferingMembership.is_admin(request.user, unit):

        platform = request.GET.get('platform')
        title = "SNA Dashboard: {} {} (Platform: {})".format(unit.code, unit.name, platform)

        # Activity Time line data (verbs and platform)
        timeline_data = get_verb_timeline_data(unit, platform, None)

        sna_json = sna_buildjson(platform, unit,
            relationshipstoinclude = "'%s', '%s', '%s', '%s'" % (xapi_settings.VERB_MENTIONED, xapi_settings.VERB_LIKED, \
                                                                 xapi_settings.VERB_SHARED, xapi_settings.VERB_COMMENTED))

        #sna_neighbours = getNeighbours(sna_json)
        centrality = get_centrality(sna_json)
        context_dict = {'show_dashboardnav': True, 'unit': unit, 'platform': platform, 'title': title,
                        'sna_json': sna_json, 'centrality': centrality, 'course_id': unit.id,

                        'posts_timeline': timeline_data['posts'], 'shares_timeline': timeline_data['shares'],
                        'likes_timeline': timeline_data['likes'], 'comments_timeline': timeline_data['comments']}

        return render_to_response('dashboard/snadashboard.html', context_dict, context)

    else:
        raise PermissionDenied


@check_access(required_roles=['Staff'])
@login_required
def pyldavis(request):
    context = RequestContext(request)
    if request.method == 'POST':
        course_code = request.POST['course_code']
        platform = request.POST['platform']
        start_date = request.POST.get('start_date', None)
        end_date = request.POST.get('end_date', None)
    else:
        course_code = request.GET.get('course_code')
        platform = request.GET.get('platform')
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)

    pyLDAVis_json = get_LDAVis_JSON(platform, 5, course_code, start_date=start_date, end_date=end_date)
    context_dict = {'title': "Topic Model", 'pyLDAVis_json': pyLDAVis_json}

    return render_to_response('dashboard/pyldavis.html', context_dict, context)


@check_access(required_roles=['Staff'])
@login_required
def studentdashboard(request):
    context = RequestContext(request)

    selected_user_id = request.GET.get('user')
    course_id = request.GET.get('course_id')
    platform = request.GET.get('platform')
    unit = None
    user = None
    try:
        unit = UnitOffering.objects.get(id = course_id)
        user = User.objects.get(id = selected_user_id)
    except:
        raise HttpResponseServerError('Unit or User not found.')

    course_code = unit.code
    username = user.username

    title = "Student Dashboard: %s, %s" % (course_code, username)
    # show_dashboardnav = True

    # Activity Time line data (verbs and platform)
    timeline_data = get_verb_timeline_data(unit, platform, user)
    platform_timeline_data = get_platform_timeline_data(unit, platform, user)

    # A flag for showing a platform activity time series and pie chart
    show_allplatforms_widgets = True
    if platform != "all":
        show_allplatforms_widgets = False

    # Get the number of verbs and platforms
    activity_pie_series = get_verb_pie_data(unit, platform = platform, user = user)
    platformactivity_pie_series = get_platform_pie_data(unit, user = user)

    sna_json = None
    centrality = None
    if unit.sn_analysis:
        sna_json = sna_buildjson(platform, unit, 
            relationshipstoinclude = "'%s', '%s', '%s', '%s'" % (xapi_settings.VERB_MENTIONED, xapi_settings.VERB_LIKED, \
                                                                 xapi_settings.VERB_SHARED, xapi_settings.VERB_COMMENTED))
        # Centrality data
        centrality = get_centrality(sna_json)
        
    # Word cloud tags
    tags = get_wordcloud(platform, unit, user = user)
    # Sentiments pie chart
    sentiments = getClassifiedCounts(platform, unit, user = user, classifier="VaderSentiment")
    # Community of Inquiry
    coi = None
    if unit.enable_coi_classifier:
        coi = getClassifiedCounts(platform, unit, user = user, classifier="nb_"+course_code+"_"+platform+".model")

    context_dict = {
        'title': title, 'course_code':course_code, 'course_id': unit.id, 'platform':platform,
        'username':username, 'unit': unit, 'user_id': user.id,
        'posts_timeline': timeline_data['posts'], 'shares_timeline': timeline_data['shares'],
        'likes_timeline': timeline_data['likes'], 'comments_timeline': timeline_data['comments'],

        'twitter_timeline': platform_timeline_data[xapi_settings.PLATFORM_TWITTER],
        'facebook_timeline': platform_timeline_data[xapi_settings.PLATFORM_FACEBOOK],
        'youtube_timeline': platform_timeline_data[xapi_settings.PLATFORM_YOUTUBE],
        'blog_timeline': platform_timeline_data[xapi_settings.PLATFORM_BLOG],
        'trello_timeline': platform_timeline_data[xapi_settings.PLATFORM_TRELLO],
        'github_timeline': platform_timeline_data[xapi_settings.PLATFORM_GITHUB],
        'forum_timeline': [], 'diigo_timeline':[], # These haven't been implemented

        'activity_pie_series': activity_pie_series,
        'platformactivity_pie_series':platformactivity_pie_series,
        'sna_json': sna_json, 'tags': tags, 'sentiments': sentiments, 'coi': coi, 'centrality': centrality,
        'show_allplatforms_widgets': show_allplatforms_widgets, 'show_dashboardnav':True
    }

    return render_to_response('dashboard/studentdashboard.html', context_dict, context)

@login_required
def cicaround_dashboard(request):
    context = RequestContext(request)

    unit_id = request.GET.get('unit')
    unit = UnitOffering.objects.get(id=unit_id)

    platforms = unit.get_required_platforms()

    user = request.user

    title = "CIC Around Dashboard: %s, %s" % (course_code, user.username)


@check_access(required_roles=['Student'])
@login_required
def mydashboard(request):
    context = RequestContext(request)

    course_code = None
    platform = None
    user = request.user

    if request.method == 'POST':
        course_id = request.POST['course_id']
        platform = request.POST['platform']
        unit = UnitOffering.objects.get(id = course_id)

        # save reflection
        reflectiontext = request.POST['reflectiontext']
        rating = request.POST['rating']
        reflect = DashboardReflection(strategy = reflectiontext, rating = rating, user = user, unit = unit)
        reflect.save()

    else:
        course_id = request.GET.get('course_id')
        platform = request.GET.get('platform')
        #username = request.GET.get('username')

    unit = UnitOffering.objects.get(id = course_id)
    course_code = unit.code

    title = "Student Dashboard: %s, %s" % (course_code, user.username)

    # Activity Time line data (verbs and platform)
    timeline_data = get_verb_timeline_data(unit, platform, user)
    platform_timeline_data = get_platform_timeline_data(unit, platform, user)

    # A flag for showing a platform activity time series and pie chart
    show_allplatforms_widgets = True
    if platform != "all":
        show_allplatforms_widgets = False

    # Get the number of verbs and platforms
    activity_pie_series = get_verb_pie_data(unit, platform = platform, user = user)
    platformactivity_pie_series = get_platform_pie_data(unit, user = user)

    # Word cloud tags
    tags = get_wordcloud(platform, unit, user = user)
    # Sentiments pie chart
    sentiments = getClassifiedCounts(platform, unit, user = user, classifier="VaderSentiment")
    # Dashboard reflection
    reflections = DashboardReflection.objects.filter(user = user, unit = unit)
    
    # SNA explorer data 
    sna_json = None
    centrality = None
    if unit.sn_analysis:
        sna_json = sna_buildjson(platform, unit, 
            # relationshipstoinclude="'mentioned','liked','shared','commented'")
            relationshipstoinclude = "'%s', '%s', '%s', '%s'" % (xapi_settings.VERB_MENTIONED, xapi_settings.VERB_LIKED, \
                                                                 xapi_settings.VERB_SHARED, xapi_settings.VERB_COMMENTED))
        # Centrality data
        centrality = get_centrality(sna_json)

    # Community of Inquiry
    coi = None
    if unit.enable_coi_classifier:
        coi = getClassifiedCounts(platform, unit, user = user, classifier="nb_"+course_code+"_"+platform+".model")

    context_dict = {
        'title': title, 'course_code':course_code, 'course_id': unit.id, 'platform':platform,
        'username': user.username, 'unit': unit, 'user_id': user.id,
        'posts_timeline': timeline_data['posts'], 'shares_timeline': timeline_data['shares'],
        'likes_timeline': timeline_data['likes'], 'comments_timeline': timeline_data['comments'],

        'twitter_timeline': platform_timeline_data[xapi_settings.PLATFORM_TWITTER],
        'facebook_timeline': platform_timeline_data[xapi_settings.PLATFORM_FACEBOOK],
        'youtube_timeline': platform_timeline_data[xapi_settings.PLATFORM_YOUTUBE],
        'blog_timeline': platform_timeline_data[xapi_settings.PLATFORM_BLOG],
        'trello_timeline': platform_timeline_data[xapi_settings.PLATFORM_TRELLO],
        'github_timeline': platform_timeline_data[xapi_settings.PLATFORM_GITHUB],
        'forum_timeline': [], 'diigo_timeline':[], # These haven't been implemented

        'activity_pie_series': activity_pie_series,
        'platformactivity_pie_series':platformactivity_pie_series,
        'show_allplatforms_widgets': show_allplatforms_widgets, 'show_dashboardnav': True,
        'sna_json': sna_json, 'tags': tags, 'centrality': centrality,
        'sentiments': sentiments, 'coi': coi, 'reflections':reflections
        }

    return render_to_response('dashboard/mydashboard.html', context_dict, context)


@login_required
def myclassifications(request):
    context = RequestContext(request)

    course_code = None
    platform = None

    user = request.user
    username = user.username
    uid = user.id

    course_code = request.GET.get('course_code')
    platform = request.GET.get('platform')

    #user_profile = UserProfile.objects.filter(user=user)

    group_id_seed = GroupMap.objects.filter(userId=user, course_code=course_code).values_list('groupId')

    inner_q = UserClassification.objects.filter(username=username).values_list('classification_id')
    #Need to add unique identifier to models to distinguish between classes
    #xapistatement__username=username,
    classifier_name = "nb_%s_%s.model" % (course_code,platform)
    classifications_list = list(Classification.objects.filter(classifier=classifier_name).exclude(id__in = inner_q))

    if len(group_id_seed)>0:
        random.seed(group_id_seed)
        random.shuffle(classifications_list)
    else:
        random.seed()
        random.shuffle(classifications_list)

    context_dict = {'course_code':course_code, 'platform':platform, 'title': "Community of Inquiry Classification", 'username':username, 'uid':uid, 'classifications': classifications_list }
    return render_to_response('dashboard/myclassifications.html', context_dict, context)


@login_required
def ccadashboard(request):
    context = RequestContext(request)

    course_id = request.GET.get('course_id')
    platform = request.GET.get('platform')
    unit = UnitOffering.objects.get(id = course_id)

    title = "CCA Dashboard: %s (Platform: %s)" % (unit.code, platform)
    context_dict = {'course_id':course_id, 'platform':platform, 'title': title, }

    return render_to_response('dashboard/ccadashboard.html', context_dict, context)


@login_required
def get_platform_timeseries_data(request):
    # context = RequestContext(request)
    # TODO: Get available platforms in the course dynamically
    # platform_names = ["Trello", "GitHub"]
    platform_names = request.GET.get('platform').split(',')
    val = get_platform_timeseries_dataset(request.GET.get('course_id'), platform_names = platform_names)
    response = JsonResponse(val, status=status.HTTP_200_OK)
    return response


@login_required
def get_platform_activities(request):
    # context = RequestContext(request)
    # platform_names = []
    platform_names = request.GET.get('platform').split(',')

    val = get_platform_activity_dataset(request.GET.get('course_id'), platform_names)
    response = JsonResponse(val, status=status.HTTP_200_OK)
    return response


def get_user_acitivities(request):
    platform_names = request.GET.get('platform').split(',')
    val = get_user_acitivities_dataset(request.GET.get('course_code'), platform_names)
    response = JsonResponse(val, status=status.HTTP_200_OK)
    return response


@login_required
def get_all_repos(request):
    course_id = request.GET.get('course_id')
    tokens = OfflinePlatformAuthToken.objects.filter(
        user_smid=request.user.userprofile.github_account_name, platform=xapi_settings.PLATFORM_GITHUB)
    if len(tokens) == 0 or len(tokens) > 1:
        return []

    val = get_all_reponames(tokens[0].token, course_id)
    return JsonResponse(val, status=status.HTTP_200_OK)


@login_required
def add_repo_to_course(request):
    course_id = request.GET.get('course_id')
    course = UnitOffering.objects.get(id=course_id)
    repo_name = request.GET.get('repo')
    ret = {'result': 'success'}

    resource_map = UserPlatformResourceMap.objects.filter(
        user=request.user, unit=course_id, platform=xapi_settings.PLATFORM_GITHUB)
    # If the same record exist, update the repository name
    if len(resource_map) == 1:
        resource_map[0].resource_id = repo_name
        resource_map[0].save()
    elif len(resource_map) > 1:
        # When more than one records were found (Usually this doesn't happen)
        ret = {'result': 'error', 'message': 'More than one records were found. Could not update repository name.'}
    else:
        # Add a new record
        resource_map = UserPlatformResourceMap(
            user=request.user, unit=course, resource_id=repo_name, platform=xapi_settings.PLATFORM_GITHUB)
        resource_map.save()

    return JsonResponse(ret, status=status.HTTP_200_OK)


@login_required
def get_github_attached_repo(request):
    course_id = request.GET.get('course_id')
    if course_id is None or course_id == '':
        return JsonResponse({'result': 'error', 'message': 'Course ID not found.',
            'course_id': course_id}, status=status.HTTP_200_OK)

    resource_map = UserPlatformResourceMap.objects.filter(
        user=request.user, unit=course_id, platform=xapi_settings.PLATFORM_GITHUB)

    if len(resource_map) == 0:
        return JsonResponse({'result': 'error', 'message': 'No records found.',
            'course_id': course_id}, status=status.HTTP_200_OK)

    resource = resource_map[0]
    gh_settings = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_GITHUB]
    obj = OrderedDict([
        ('result', 'success'),
        ('name', resource.resource_id),
        ('url', gh_settings.platform_url + resource.resource_id),
        ('course_id', course_id),
    ])

    return JsonResponse(obj, status=status.HTTP_200_OK)


@login_required
def remove_attached_repo(request):
    course_id = request.GET.get('course_id')
    if course_id is None or course_id == '':
        return JsonResponse({'result': 'error', 'message': 'Course ID not found.'}, status=status.HTTP_200_OK)

    resource_map = UserPlatformResourceMap.objects.filter(
        user=request.user, unit=course_id, platform=xapi_settings.PLATFORM_GITHUB)
    if len(resource_map) > 1:
        return JsonResponse({'result': 'error', 'message': 'More than one records were found.'}, status=status.HTTP_200_OK)

    resource_map.delete()
    ret = {'result': 'success'}
    return JsonResponse(ret, status=status.HTTP_200_OK)


@login_required
def get_github_contribution(request):
    # Get all issues and issues that each user was assigned to.
    course_id = request.GET.get('course_id')
    contribution = get_issue_list(course_id)

    return JsonResponse(contribution, status=status.HTTP_200_OK)


@login_required
def get_learning_records(request):
    course_id = request.GET.get('course_id')
    user_id = request.GET.get('user')
    platform = request.GET.get('platform')
    start_date = request.GET.get('datetimestamp_min')
    end_date = request.GET.get('datetimestamp_max')
    unit = None
    user = None

    try:
        unit = UnitOffering.objects.get(id = course_id)
        if user_id and user_id != '':
            user = User.objects.get(id = user_id)
        else:
            raise User.DoesNotExist

    except UnitOffering.DoesNotExist:
        # raise HttpResponseServerError('Unit or user not found.')
        # A selected user in SNA Explorer could be non-registered user.
        # So, instead of raising an error, return JSON error message
        return JsonResponse({'results': {'error': 'Unit not found.'}}, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return JsonResponse({'results': {'error': 'User not found.'}}, status=status.HTTP_200_OK)

    # Get xAPI statements
    filters = xapi_filter()
    filters.course = unit.code
    if platform is not None and platform != 'all' and platform != '':
        filters.platform = platform

    if start_date and start_date != '':
        filters.since = start_date

    if end_date and end_date != '':
        filters.until = end_date

    getter = xapi_getter()
    statements = getter.get_xapi_statements(unit.id, user_id, filters)
    lang = 'en-US'
    results = []
    for stmt in statements:
        parent_username = None
        learning_record = None
        try:
            learning_record = LearningRecord.objects.get(statement_id = stmt['id'])
            parent_user = User.objects.get(id = learning_record.parent_user_id)
            parent_username = parent_user.username
        except:
            # Get parent user (external user) from social relationship table
            if learning_record is not None:
                try:
                    sr = SocialRelationship.objects.get(platformid = learning_record.platformid,
                        unit = unit, user = user, verb = learning_record.verb, platform = learning_record.platform)
                    parent_username = sr.to_external_user
                except:
                    pass

        obj = {}
        name = ''
        if 'name' in stmt['authority']['member'][0]:
            name = stmt['authority']['member'][0]['name']
        else:
            name = stmt['authority']['member'][1]['name']

        obj['username'] = name
        obj['parentusername'] = parent_username
        obj['message'] = stmt['object']['definition']['name'][lang]
        obj['verb'] = stmt['verb']['display'][lang]
        obj['platform'] = stmt['context']['platform']
        obj['datetimestamp'] = stmt['timestamp']
        results.append(obj)

    return JsonResponse({'results': results}, status=status.HTTP_200_OK)
