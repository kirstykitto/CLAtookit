from django.shortcuts import render
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.http import HttpResponse
from django.db import connection
from utils import *
from clatoolkit.models import OfflinePlatformAuthToken, UserProfile, OauthFlowTemp, UnitOffering, UnitOfferingMembership, DashboardReflection, LearningRecord, Classification, UserClassification, GroupMap, UserTrelloCourseBoardMap
from dataintegration.models import PlatformConfig
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from functools import wraps
from django.db.models import Q
import datetime
from django.db.models import Count
import random
from rest_framework import status
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied

from rest_framework.decorators import api_view
from rest_framework.response import Response

import requests

#API endpoint to grab a list of trello boards to attach to course
@login_required
@api_view()
def get_trello_boards(request):
    user_profile = UserProfile.objects.get(user=request.user)
    trello_member_id = user_profile.trello_account_name

    token_qs = OfflinePlatformAuthToken.objects.get(user_smid=trello_member_id)
    token = token_qs.token
    key = request.GET.get('key')
    course_code = request.GET.get('course_code')

    #print key + ' >>>>> ' + token

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

        html_resp = '<a href="#" class="board_choice" onclick="javascript:add_board(\''+course_code+'\',\''+board_id+'\')">'+board_name+'</a>'

        board_namesList.append(html_resp)
        board_namesList.append('</li>')
    board_namesList.append('</ul>')

    return Response(('').join(board_namesList))

@login_required
@api_view()
#API endpoint to allow students to attach a board to course
def add_board_to_course(request):
    course = UnitOffering.objects.get(code=request.GET.get('course_code'))
    board_list = course.attached_trello_boards

    #print 'board list %s' % (board_list)
    #print 'board list is "": %s' % (board_list == '')

    if board_list == '':
        new_board_list = request.GET.get('id')
    else:
        new_board_list = board_list+','+request.GET.get('id')

    course.attached_trello_boards = new_board_list

    course.save()

    trello_user_course_map = UserTrelloCourseBoardMap(user=request.user, course_code=course.code, board_id=request.GET.get('id'))

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
                    course_code = request.POST['course_code']
                else:
                    course_code = request.GET.get('course_code')
                # Check that user is a member of the course
                unit = UnitOffering.objects.filter(code=course_code, users=request.user.id)
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
    course_code = request.GET.get('course_code')

    trello_user_course_map = UserTrelloCourseBoardMap.objects.filter(user=request.user, course_code=course_code)
    unit = UnitOffering.objects.get(code=course_code)

    #pythonic code below removes the ID of the attached board being removed
    unit.attached_trello_boards = ','.join([board for board in unit.attached_trello_boards.split(',')
                           if board is not trello_user_course_map.board_id[0]])

    unit.save()

    trello_user_course_map.delete()

    return myunits(request)

@login_required
@api_view()
def trello_myunits_restview(request):
        #Get course code, and match it with the user to obtain the board ID for the user for their specified course.
        course_code = request.GET.get('course_code')
        trello_user_course_map = UserTrelloCourseBoardMap.objects.filter(user=request.user, course_code=course_code)

        #If a board exists for the user and it's attached to the course
        if trello_user_course_map:
            #Get user auth token for trello
            token_qs = OfflinePlatformAuthToken.objects.filter(user_smid=request.user.userprofile.trello_account_name)

            #if the token exists, grab the board from trello on behalf of the user
            if token_qs:
                key = getPluginKey('trello')

                http = 'https://api.trello.com/1/boards/%s?key=%s&token=%s' % (trello_user_course_map[0].board_id,key,token_qs[0].token)

                #print http

                r = requests.get(http)

                #print 'result: %s' % (r.json())

                board = r.json()

                response = {'data': '<a href="'+board['url']+'""><i class="fa fa-trello" aria-hidden="true"></i>   '+board['name']+'</a> | '
                            '<a href="/dashboard/removeBoard?course_code='+course_code+'">Remove</a>', 'course_code': course_code}

                return Response(response)

        else: #Otherwise, we'll give the student the option to attach their trello board
            response = {'data': '<a href="#" onclick="javascript:get_and_link_board(\''+course_code+'\')">Attach a Trello Board to plan your Work!</a>'
                            '<div id="trello_board_display"></div>', 'course_code': course_code}
            return Response(response)


@login_required
def myunits(request):
    context = RequestContext(request)

    # Get a users memberships to unit offerings
    memberships = UnitOfferingMembership.objects.filter(user=request.user, unit__enabled=True).select_related('unit')

    # Get Plugin details
    for i in range(0, len(memberships)):
        platform_configs = memberships[i].unit.platformconfig_set.all()
        if len(platform_configs) > 0:
            memberships[i].plugins = []
        for config in platform_configs:
            platform = config.platform
            groups = settings.DATAINTEGRATION_PLUGINS[platform].get_groups(memberships[i].unit)
            memberships[i].plugins.append({
                "label": platform,
                "platform": platform,
                "refresh": reverse("{}_refresh".format(platform)),
                "groups": groups
            })

    role = request.user.userprofile.role

    show_dashboardnav = False

    shownocontentwarning = False

    trello_attached = not request.user.userprofile.trello_account_name == ''

    # if student check if the student has imported data
    if role == 'Student':
        if LearningRecord.objects.filter(user=request.user).count() == 0:
            shownocontentwarning = True

    context_dict = {'title': "My Units", 'memberships': memberships, 'show_dashboardnav': show_dashboardnav,
                    'shownocontentwarning': shownocontentwarning, 'role': role,
                    'trello_attached_to_acc': trello_attached}

    return render_to_response('dashboard/myunits.html', context_dict, context)


@login_required
def dashboard(request):
    context = RequestContext(request)

    unit_id = request.GET.get('unit')
    unit = UnitOffering.objects.get(id=unit_id)

    # If the user is an admin for the course
    if UnitOfferingMembership.is_admin(request.user, unit):

        platform = request.GET.get('platform')

        title = "Activity Dashboard: %s (Platform: %s)" % (unit.code, platform)
        show_dashboardnav = True

        profiling = ""
        profiling = profiling + "| Verb Timelines %s" % (str(datetime.datetime.now()))
        posts_timeline = get_timeseries('created', platform, unit)
        shares_timeline = get_timeseries('shared', platform, unit)
        likes_timeline = get_timeseries('liked', platform, unit)
        comments_timeline = get_timeseries('commented', platform, unit)

        show_allplatforms_widgets = False
        twitter_timeline = ""
        facebook_timeline = ""
        forum_timeline = ""
        youtube_timeline = ""
        diigo_timeline = ""
        blog_timeline = ""
        github_timeline = ""
        trello_timeline = ""

        profiling = profiling + "| Platform Timelines %s" % (str(datetime.datetime.now()))
        platformclause = ""

        #TODO: This will need to change upon implementation of teaching periods

        if platform != "all":
            platformclause = " AND clatoolkit_learningrecord.xapi->'context'->>'platform'='%s'" % (platform)
        else:
            twitter_timeline = get_timeseries_byplatform("Twitter", unit)
            facebook_timeline = get_timeseries_byplatform("Facebook", unit)
            forum_timeline = get_timeseries_byplatform("Forum", unit)
            youtube_timeline = get_timeseries_byplatform("YouTube", unit)
            diigo_timeline = get_timeseries_byplatform("Diigo", unit)
            blog_timeline = get_timeseries_byplatform("Blog", unit)
            github_timeline = get_timeseries_byplatform("GitHub", unit)
            trello_timeline = get_timeseries_byplatform("trello", unit)
            show_allplatforms_widgets = True

        profiling = profiling + "| Pies %s" % (str(datetime.datetime.now()))
        cursor = connection.cursor()
        cursor.execute("""SELECT clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US' as verb, count(clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US') as counts
                            FROM clatoolkit_learningrecord
                            WHERE clatoolkit_learningrecord.unit_id='%s' %s
                            GROUP BY clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US';
                        """ % (unit.id, platformclause))
        result = cursor.fetchall()

        activity_pie_series = ""
        for row in result:
            activity_pie_series = activity_pie_series + "['%s',  %s]," % (row[0],row[1])

        cursor = connection.cursor()
        cursor.execute("""SELECT clatoolkit_learningrecord.xapi->'context'->>'platform' as platform, count(clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US') as counts
                            FROM clatoolkit_learningrecord
                            WHERE clatoolkit_learningrecord.unit_id='%s'
                            GROUP BY clatoolkit_learningrecord.xapi->'context'->>'platform';
                        """ % (unit.id))
        result = cursor.fetchall()

        platformactivity_pie_series = ""
        for row in result:
            platformactivity_pie_series = platformactivity_pie_series + "['%s',  %s]," % (row[0],row[1])

        #active members table
        profiling = profiling + "| Active Members %s" % (str(datetime.datetime.now()))

        p = platform if platform != "all" else None
        activememberstable = get_active_members_table(unit, p)

        profiling = profiling + "| Top Content %s" % (str(datetime.datetime.now()))
        topcontenttable = get_cached_top_content(platform, unit)
        profiling = profiling + "| End Top Content %s" % (str(datetime.datetime.now()))

        context_dict = {'profiling': profiling, 'show_dashboardnav':show_dashboardnav,
        'course_code':unit.code, 'platform':platform,
        'twitter_timeline': twitter_timeline, 'facebook_timeline': facebook_timeline, 'forum_timeline': forum_timeline,
        'youtube_timeline':youtube_timeline, 'diigo_timeline':diigo_timeline, 'blog_timeline':blog_timeline,
        'github_timeline': github_timeline, 'trello_timeline': trello_timeline,
        'show_allplatforms_widgets': show_allplatforms_widgets, 'platformactivity_pie_series': platformactivity_pie_series,
        'title': title, 'activememberstable': activememberstable, 'topcontenttable': topcontenttable,
        'activity_pie_series': activity_pie_series, 'posts_timeline': posts_timeline, 'shares_timeline': shares_timeline,
        'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline }

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
        show_dashboardnav = True

        posts_timeline = get_timeseries('created', platform, unit)
        shares_timeline = get_timeseries('shared', platform, unit)
        likes_timeline = get_timeseries('liked', platform, unit)
        comments_timeline = get_timeseries('commented', platform, unit)

        tags = get_wordcloud(platform, unit)

        sentiments = getClassifiedCounts(platform, unit, classifier="VaderSentiment")
        coi = getClassifiedCounts(platform, unit, classifier="NaiveBayes_t1.model")

        topic_model_output, sentimenttopic_piebubblesdataset = nmf(platform, no_topics, unit, start_date=None, end_date=None)

        context_dict = {'show_dashboardnav': show_dashboardnav, 'unit': unit, 'platform': platform, 'title': title,
                        'sentiments': sentiments, 'coi': coi, 'tags': tags, 'posts_timeline': posts_timeline,
                        'shares_timeline': shares_timeline, 'likes_timeline': likes_timeline,
                        'comments_timeline': comments_timeline, 'no_topics': no_topics,
                        'topic_model_output': topic_model_output,
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
        show_dashboardnav = True

        posts_timeline = get_timeseries('created', platform, unit)
        shares_timeline = get_timeseries('shared', platform, unit)
        likes_timeline = get_timeseries('liked', platform, unit)
        comments_timeline = get_timeseries('commented', platform, unit)

        sna_json = sna_buildjson(platform, unit, relationshipstoinclude="'mentioned','liked','shared','commented'")
        #sna_neighbours = getNeighbours(sna_json)
        centrality = getCentrality(sna_json)
        context_dict = {'show_dashboardnav': show_dashboardnav, 'unit': unit, 'platform': platform, 'title': title,
                        'sna_json': sna_json, 'posts_timeline': posts_timeline, 'shares_timeline': shares_timeline,
                        'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline,
                        'centrality': centrality}

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

    course_code = None
    platform = None
    username = None

    course_code = request.GET.get('course_code')
    platform = request.GET.get('platform')
    username = request.GET.get('username')
    username_platform = request.GET.get('username_platform')

    #userid = get_smids_fromusername(username)
    twitter_id, fb_id, forum_id, github_id, trello_id, blog_id, diigo_id = get_smids_fromusername(username)
    sm_usernames_dict = {'Twitter': twitter_id, 'Facebook': fb_id, 'Forum': forum_id}
    sm_usernames = [twitter_id, fb_id, forum_id]

    sm_usernames_str = ','.join("'{0}'".format(x) for x in sm_usernames)

    title = "Student Dashboard: %s, (Twitter: %s, Facebook: %s, Forum: %s)" % (course_code, twitter_id, fb_id, forum_id)

    if course_code == 'IFN614':
            title = "Student Dashboard: %s, (Twitter: %s, Blog: %s)" % (course_code, twitter_id, blog_id)


    show_dashboardnav = True

    #print "Verb timelines", datetime.datetime.now()
    posts_timeline = get_timeseries('created', platform, course_code, username=username)
    shares_timeline = get_timeseries('shared', platform, course_code, username=username)
    likes_timeline = get_timeseries('liked', platform, course_code, username=username)
    comments_timeline = get_timeseries('commented', platform, course_code, username=username)

    #print "Activity by Platform", datetime.datetime.now()
    cursor = connection.cursor()
    #if course_code == 'IFN614':
    #    cursor.execute("""SELECT clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US' as verb, count(clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US') as counts
    #                        FROM clatoolkit_learningrecord
    #                        WHERE clatoolkit_learningrecord.course_code='%s' AND clatoolkit_learningrecord.username='%s' AND clatoolkit_learningrecord.datetimestamp > '%s'
    #                        GROUP BY clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US';
    #                """ % (course_code, username, '29-06-2016'))
    #else:
    cursor.execute("""SELECT clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US' as verb, count(clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US') as counts
                    FROM clatoolkit_learningrecord
                    WHERE clatoolkit_learningrecord.course_code='%s' AND clatoolkit_learningrecord.username='%s'
                    GROUP BY clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US';
            """ % (course_code, username))
    result = cursor.fetchall()

    activity_pie_series = ""
    for row in result:
        activity_pie_series = activity_pie_series + "['%s',  %s]," % (row[0],row[1])

    show_allplatforms_widgets = False
    twitter_timeline = ""
    facebook_timeline = ""
    forum_timeline = ""
    youtube_timeline = ""
    diigo_timeline = ""
    blog_timeline = ""
    github_timeline = ""
    trello_timeline = ""

    #print "Platform timelines", datetime.datetime.now()
    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.xapi->'context'->>'platform'='%s'" % (platform)
    else:
        twitter_timeline = get_timeseries_byplatform("Twitter", course_code, username)
        facebook_timeline = get_timeseries_byplatform("Facebook", course_code, username)
        forum_timeline = get_timeseries_byplatform("Forum", course_code, username)
        youtube_timeline = get_timeseries_byplatform("YouTube", course_code, username)
        diigo_timeline = get_timeseries_byplatform("Diggo", course_code, username)
        blog_timeline = get_timeseries_byplatform("Blog", course_code, username)
        github_timeline = get_timeseries_byplatform("GitHub", course_code)
        trello_timeline = get_timeseries_byplatform("trello", course_code)

        show_allplatforms_widgets = True

    cursor = connection.cursor()
    cursor.execute("""SELECT clatoolkit_learningrecord.xapi->'context'->>'platform' as platform, count(clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US') as counts
                        FROM clatoolkit_learningrecord
                        WHERE clatoolkit_learningrecord.course_code='%s' AND clatoolkit_learningrecord.username='%s'
                        GROUP BY clatoolkit_learningrecord.xapi->'context'->>'platform';
                    """ % (course_code, username))
    result = cursor.fetchall()

    platformactivity_pie_series = ""
    for row in result:
        platformactivity_pie_series = platformactivity_pie_series + "['%s',  %s]," % (row[0],row[1])

    #print "Top Content", datetime.datetime.now()
    topcontenttable = get_top_content_table(platform, course_code, username=username)

    #print "SNA", datetime.datetime.now()
    if course_code == 'IFN614':
        sna_json = sna_buildjson(platform, course_code, start_date='15-06-2016', end_date='20-12-2016', relationshipstoinclude="'mentioned','liked','shared','commented'")
    else:
        sna_json = sna_buildjson(platform, course_code, relationshipstoinclude="'mentioned','liked','shared','commented'")


    #print "Word Cloud", datetime.datetime.now()
    tags = get_wordcloud(platform, course_code, username=username)

    sentiments = getClassifiedCounts(platform, course_code, username=username, classifier="VaderSentiment")

    coi = getClassifiedCounts(platform, course_code, username=username, classifier="nb_"+course_code+"_"+platform+".model")


    context_dict = {'show_allplatforms_widgets': show_allplatforms_widgets, 
    'twitter_timeline': twitter_timeline, 'facebook_timeline': facebook_timeline, 
    'forum_timeline':forum_timeline, 'youtube_timeline':youtube_timeline, 'diigo_timeline':diigo_timeline, 
    'blog_timeline':blog_timeline, 'github_timeline': github_timeline, 'trello_timeline': trello_timeline,
    'platformactivity_pie_series':platformactivity_pie_series, 'show_dashboardnav':show_dashboardnav, 
    'course_code':course_code, 'platform':platform, 'title': title, 'course_code':course_code, 
    'platform':platform, 'username':username, 'sna_json': sna_json,  'tags': tags, 
    'topcontenttable': topcontenttable, 'activity_pie_series': activity_pie_series, 
    'posts_timeline': posts_timeline, 'shares_timeline': shares_timeline, 
    'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline, 
    'sentiments': sentiments, 'coi': coi }

    return render_to_response('dashboard/studentdashboard.html', context_dict, context)

@check_access(required_roles=['Student'])
@login_required
def mydashboard(request):
    context = RequestContext(request)

    course_code = None
    platform = None
    username = request.user.username
    uid = request.user.id

    if request.method == 'POST':
        course_code = request.POST['course_code']
        platform = request.POST['platform']
        #username = request.POST['username']

        # save reflection
        reflectiontext = request.POST['reflectiontext']
        rating = request.POST['rating']
        reflect = DashboardReflection(strategy=reflectiontext,rating=rating,username=username)
        reflect.save()

    else:
        course_code = request.GET.get('course_code')
        platform = request.GET.get('platform')
        #username = request.GET.get('username')

    twitter_id, fb_id, forum_id, github_id, trello_id, blog_id, diigo_id = get_smids_fromuid(uid)
    sm_usernames = [twitter_id, fb_id, forum_id]
    sm_usernames_str = ','.join("'{0}'".format(x) for x in sm_usernames)

    title = "Student Dashboard: %s, %s" % (course_code, username)
    show_dashboardnav = True

    posts_timeline = get_timeseries('created', platform, course_code, username=username)
    shares_timeline = get_timeseries('shared', platform, course_code, username=username)
    likes_timeline = get_timeseries('liked', platform, course_code, username=username)
    comments_timeline = get_timeseries('commented', platform, course_code, username=username)

    cursor = connection.cursor()
    cursor.execute("""SELECT clatoolkit_learningrecord.verb as verb, count(clatoolkit_learningrecord.verb) as counts
                        FROM clatoolkit_learningrecord
                        WHERE clatoolkit_learningrecord.course_code='%s' AND clatoolkit_learningrecord.username='%s'
                        GROUP BY clatoolkit_learningrecord.verb;
                    """ % (course_code, username))
    result = cursor.fetchall()

    activity_pie_series = ""
    for row in result:
        activity_pie_series = activity_pie_series + "['%s',  %s]," % (row[0],row[1])

    show_allplatforms_widgets = False
    twitter_timeline = ""
    facebook_timeline = ""
    forum_timeline = ""
    youtube_timeline = ""
    diigo_timeline = ""
    blog_timeline = ""

    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)
    else:
        twitter_timeline = get_timeseries_byplatform("Twitter", course_code, username)
        facebook_timeline = get_timeseries_byplatform("Facebook", course_code, username)
        forum_timeline = get_timeseries_byplatform("Forum", course_code, username)
        youtube_timeline = get_timeseries_byplatform("YouTube", course_code, username)
        diigo_timeline = get_timeseries_byplatform("Diigo", course_code, username)
        blog_timeline = get_timeseries_byplatform("Blog", course_code, username)
        show_allplatforms_widgets = True

    cursor = connection.cursor()
    cursor.execute("""SELECT clatoolkit_learningrecord.platform as platform, count(clatoolkit_learningrecord.verb) as counts
                        FROM clatoolkit_learningrecord
                        WHERE clatoolkit_learningrecord.course_code='%s' AND clatoolkit_learningrecord.username='%s'
                        GROUP BY clatoolkit_learningrecord.platform;
                    """ % (course_code, username))
    result = cursor.fetchall()

    platformactivity_pie_series = ""
    for row in result:
        platformactivity_pie_series = platformactivity_pie_series + "['%s',  %s]," % (row[0],row[1])

    #topcontenttable = get_top_content_table(platform, course_code, username=username)

    sna_json = sna_buildjson(platform, course_code, relationshipstoinclude="'mentioned','liked','shared','commented'")
    centrality = getCentrality(sna_json)
    tags = get_wordcloud(platform, course_code, username=username)

    sentiments = getClassifiedCounts(platform, course_code, username=username, classifier="VaderSentiment")

    coi = getClassifiedCounts(platform, course_code, username=username, classifier="nb_"+course_code+"_"+platform+".model")


    reflections = DashboardReflection.objects.filter(username=username)
    context_dict = {'show_allplatforms_widgets': show_allplatforms_widgets, 
        'forum_timeline': forum_timeline, 'twitter_timeline': twitter_timeline, 
        'facebook_timeline': facebook_timeline, 'youtube_timeline': youtube_timeline, 
        'diigo_timeline':diigo_timeline, 'blog_timeline':blog_timeline, 
        'platformactivity_pie_series':platformactivity_pie_series, 
        'show_dashboardnav':show_dashboardnav, 'course_code':course_code, 
        'platform':platform, 'title': title, 'course_code':course_code, 'platform':platform, 
        'username':username, 'reflections':reflections, 'sna_json': sna_json,
        'tags': tags, 'activity_pie_series': activity_pie_series, 'posts_timeline': posts_timeline, 
        'shares_timeline': shares_timeline, 'likes_timeline': likes_timeline, 
        'comments_timeline': comments_timeline, 'sentiments': sentiments, 'coi': coi,
        'centrality': centrality
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

    course_code = request.GET.get('course_code')
    platform = request.GET.get('platform')

    title = "CCA Dashboard: %s (Platform: %s)" % (course_code, platform)
    
    """
    show_dashboardnav = True

    posts_timeline = get_timeseries('created', platform, course_code)
    shares_timeline = get_timeseries('shared', platform, course_code)
    likes_timeline = get_timeseries('liked', platform, course_code)
    comments_timeline = get_timeseries('commented', platform, course_code)

    sna_json = sna_buildjson(platform, course_code, relationshipstoinclude="'mentioned','liked','shared','commented'")
    centrality = getCentrality(sna_json)
    context_dict = {
        'show_dashboardnav':show_dashboardnav,'course_code':course_code, 'platform':platform, 
        'title': title, 'sna_json': sna_json, 'posts_timeline': posts_timeline, 
        'shares_timeline': shares_timeline, 'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline,
        'centrality': centrality
    }
    """
    context_dict = {'course_code':course_code, 'platform':platform, 'title': title, }
    
    return render_to_response('dashboard/ccadashboard.html', context_dict, context)


@login_required
def ccadata(request):

    # print request.GET.get('course_code')
    # print request.GET.get('platform')

    result = getCCAData(request.user, request.GET.get('course_code'), request.GET.get('platform'))
    
    #print result

    response = JsonResponse(result, status=status.HTTP_200_OK)

    return response


@login_required
def get_platform_timeseries(request):

    context = RequestContext(request)
    # platform = request.GET.get('platform')
    platform_names = []

    # Should all platform be shown in timeseries? or ones in the unit?
    platform_names = ["Twitter", "Facebook", "Forum", "YouTube", "Diigo", "Blog", "trello", "GitHub"]
    # if request.GET.get('platform') is None:
    #     platform_names = ["Twitter", "Facebook", "Forum", "YouTube", "Diigo", "Blog", "trello", "GitHub"]
    # else:
    #     # TODO: Enable this code if needed. Not tested.
    #     platform_names = request.GET.get('platform').split(',')

    val = get_platform_timeseries_dataset(request.GET.get('course_code'), platform_names = platform_names)
    # return HttpResponse(json_str, content_type='application/json; charset=UTF-8', status=status)
    response = JsonResponse(val, status=status.HTTP_200_OK)
    return response


@login_required
def get_platform_activity(request):
    context = RequestContext(request)
    # platform = request.GET.get('platform')
    platform_names = []
    if request.GET.get('platform') is not None:
        # TODO: Enable this code if needed. Not tested.
        platform_names = request.GET.get('platform').split(',')

    val = get_activity_dataset(request.GET.get('course_code'), platform_names)
    response = JsonResponse(val, status=status.HTTP_200_OK)
    return response
