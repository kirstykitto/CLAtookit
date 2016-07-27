from django.shortcuts import render
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse
from django.db import connection
from utils import *
from clatoolkit.models import OauthFlowTemp, UnitOffering, DashboardReflection, LearningRecord, Classification, UserClassification, GroupMap, UserTrelloCourseBoardMap
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from functools import wraps
from django.db.models import Q
import datetime
from django.db.models import Count
import random
from rest_framework import status
from django.http import JsonResponse

from rest_framework.decorators import api_view
from rest_framework.response import Response

import requests

#Attach trello board
@login_required
@api_view()
def get_trello_boards(request):
    user_profile = UserProfile.objects.get(user=request.user)
    trello_member_id = user_profile.trello_account_name
    token_qs = OauthFlowTemp.objects.get(googleid=trello_member_id)
    token = token_qs.transferdata
    key = request.GET.get('key')
    course_code = request.GET.get('course_code')

    print key + ' >>>>> ' + token

    trello_boardsList_url = 'https://api.trello.com/1/member/me/boards?key=%s&token=%s' % (key,token)

    r = requests.get(trello_boardsList_url)
    print "got response %s" % r.json()

    print 'course_code: %s' % (course_code)
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
def add_board_to_course(request):
    course = UnitOffering.objects.get(code=request.GET.get('course_code'))
    board_list = course.attached_trello_boards

    print 'board list %s' % (board_list)
    print 'board list is "": %s' % (board_list == '')

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
        course_code = request.GET.get('course_code')


        trello_user_course_map = UserTrelloCourseBoardMap.objects.filter(user=request.user, course_code=course_code)

        if trello_user_course_map:

            token_qs = OauthFlowTemp.objects.filter(googleid=request.user.userprofile.trello_account_name)
            if token_qs:
                key = getPluginKey('trello')

                http = 'https://api.trello.com/1/boards/%s?key=%s&token=%s' % (trello_user_course_map[0].board_id,key,token_qs[0].transferdata)

                print http

                r = requests.get(http)

                print 'result: %s' % (r.json())

                board = r.json()

                response = {'data': '<a href="'+board['url']+'""><i class="fa fa-trello" aria-hidden="true"></i>   '+board['name']+'</a> | '
                            '<a href="/dashboard/removeBoard?course_code='+course_code+'">Remove</a>', 'course_code': course_code}

                return Response(response)
        else:
            response = {'data': '<a href="#" onclick="javascript:get_and_link_board(\''+course_code+'\')">Attach a Trello Board to plan your Work!</a>'
                            '<div id="trello_board_display"></div>', 'course_code': course_code}
            return Response(response)

@login_required
def myunits(request):
    context = RequestContext(request)
    # Only get units that the user is assigned to to
    units = UnitOffering.objects.filter(users=request.user, enabled=True)
    role = request.user.userprofile.role

    show_dashboardnav = False

    shownocontentwarning = False

    trello_attached = not request.user.userprofile.trello_account_name == ''

    print trello_attached

    #if student check if the student has imported data
    if role=='Student':
        username = request.user.username
        if LearningRecord.objects.filter(username__iexact=username).count() == 0:
            shownocontentwarning = True

    context_dict = {'title': "My Units", 'units': units, 'show_dashboardnav':show_dashboardnav, 'shownocontentwarning': shownocontentwarning, 'role': role,
                     'trello_attached_to_acc': trello_attached}

    return render_to_response('dashboard/myunits.html', context_dict, context)

@check_access(required_roles=['Staff'])
@login_required
def dashboard(request):
    context = RequestContext(request)

    course_code = request.GET.get('course_code')
    platform = request.GET.get('platform')

    title = "Activity Dashboard: %s (Platform: %s)" % (course_code, platform)
    show_dashboardnav = True

    profiling = ""
    profiling = profiling + "| Verb Timelines %s" % (str(datetime.datetime.now()))
    posts_timeline = get_timeseries('created', platform, course_code)
    shares_timeline = get_timeseries('shared', platform, course_code)
    likes_timeline = get_timeseries('liked', platform, course_code)
    comments_timeline = get_timeseries('commented', platform, course_code)

    show_allplatforms_widgets = False
    twitter_timeline = ""
    facebook_timeline = ""
    forum_timeline = ""
    youtube_timeline = ""

    profiling = profiling + "| Platform Timelines %s" % (str(datetime.datetime.now()))
    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.xapi->'context'->>'platform'='%s'" % (platform)
    else:
        twitter_timeline = get_timeseries_byplatform("Twitter", course_code)
        facebook_timeline = get_timeseries_byplatform("Facebook", course_code)
        forum_timeline = get_timeseries_byplatform("Forum", course_code)
        youtube_timeline = get_timeseries_byplatform("YouTube", course_code)
        diigo_timeline = get_timeseries_byplatform("Diigo", course_code)
        blog_timeline = get_timeseries_byplatform("Blog", course_code)
        show_allplatforms_widgets = True

    profiling = profiling + "| Pies %s" % (str(datetime.datetime.now()))
    cursor = connection.cursor()
    cursor.execute("""SELECT clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US' as verb, count(clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US') as counts
                        FROM clatoolkit_learningrecord
                        WHERE clatoolkit_learningrecord.course_code='%s' %s
                        GROUP BY clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US';
                    """ % (course_code, platformclause))
    result = cursor.fetchall()

    activity_pie_series = ""
    for row in result:
        activity_pie_series = activity_pie_series + "['%s',  %s]," % (row[0],row[1])

    cursor = connection.cursor()
    cursor.execute("""SELECT clatoolkit_learningrecord.xapi->'context'->>'platform' as platform, count(clatoolkit_learningrecord.xapi->'verb'->'display'->>'en-US') as counts
                        FROM clatoolkit_learningrecord
                        WHERE clatoolkit_learningrecord.course_code='%s'
                        GROUP BY clatoolkit_learningrecord.xapi->'context'->>'platform';
                    """ % (course_code))
    result = cursor.fetchall()

    platformactivity_pie_series = ""
    for row in result:
        platformactivity_pie_series = platformactivity_pie_series + "['%s',  %s]," % (row[0],row[1])

    #active members table
    profiling = profiling + "| Active Members %s" % (str(datetime.datetime.now()))
    activememberstable = get_active_members_table(platform, course_code) #get_cached_active_users(platform, course_code)

    profiling = profiling + "| Top Content %s" % (str(datetime.datetime.now()))
    topcontenttable = get_cached_top_content(platform, course_code) #get_top_content_table(platform, course_code)
    profiling = profiling + "| End Top Content %s" % (str(datetime.datetime.now()))

    context_dict = {'profiling': profiling, 'show_dashboardnav':show_dashboardnav, 'course_code':course_code, 'platform':platform, 'twitter_timeline': twitter_timeline, 'facebook_timeline': facebook_timeline, 'forum_timeline': forum_timeline, 'youtube_timeline':youtube_timeline, 'diigo_timeline':diigo_timeline, 'blog_timeline':blog_timeline, 'show_allplatforms_widgets': show_allplatforms_widgets, 'platformactivity_pie_series': platformactivity_pie_series,  'title': title, 'activememberstable': activememberstable, 'topcontenttable': topcontenttable, 'activity_pie_series': activity_pie_series, 'posts_timeline': posts_timeline, 'shares_timeline': shares_timeline, 'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline }

    return render_to_response('dashboard/dashboard.html', context_dict, context)

@check_access(required_roles=['Staff'])
@login_required
def cadashboard(request):
    context = RequestContext(request)

    course_code = None
    platform = None
    no_topics = 3

    if request.method == 'POST':
        course_code = request.POST['course_code']
        platform = request.POST['platform']
        no_topics = int(request.POST['no_topics'])
    else:
        course_code = request.GET.get('course_code')
        platform = request.GET.get('platform')

    title = "Content Analysis Dashboard: %s (Platform: %s)" % (course_code, platform)
    show_dashboardnav = True

    posts_timeline = get_timeseries('created', platform, course_code)
    shares_timeline = get_timeseries('shared', platform, course_code)
    likes_timeline = get_timeseries('liked', platform, course_code)
    comments_timeline = get_timeseries('commented', platform, course_code)

    tags = get_wordcloud(platform, course_code)

    sentiments = getClassifiedCounts(platform, course_code, classifier="VaderSentiment")
    coi = getClassifiedCounts(platform, course_code, classifier="NaiveBayes_t1.model")

    topic_model_output, sentimenttopic_piebubblesdataset = nmf(platform, no_topics, course_code, start_date=None, end_date=None)

    context_dict = {'show_dashboardnav':show_dashboardnav, 'course_code':course_code, 'platform':platform, 'title': title, 'course_code':course_code, 'platform':platform, 'sentiments': sentiments, 'coi': coi, 'tags': tags, 'posts_timeline': posts_timeline, 'shares_timeline': shares_timeline, 'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline, 'no_topics': no_topics, 'topic_model_output': topic_model_output, 'sentimenttopic_piebubblesdataset':sentimenttopic_piebubblesdataset }
    return render_to_response('dashboard/cadashboard.html', context_dict, context)

@check_access(required_roles=['Staff'])
@login_required
def snadashboard(request):
    context = RequestContext(request)

    course_code = request.GET.get('course_code')
    platform = request.GET.get('platform')

    title = "SNA Dashboard: %s (Platform: %s)" % (course_code, platform)
    show_dashboardnav = True

    posts_timeline = get_timeseries('created', platform, course_code)
    shares_timeline = get_timeseries('shared', platform, course_code)
    likes_timeline = get_timeseries('liked', platform, course_code)
    comments_timeline = get_timeseries('commented', platform, course_code)

    sna_json = sna_buildjson(platform, course_code, relationshipstoinclude="'mentioned','liked','shared','commented'")
    #sna_neighbours = getNeighbours(sna_json)
    centrality = getCentrality(sna_json)
    context_dict = {
        'show_dashboardnav':show_dashboardnav,'course_code':course_code, 'platform':platform, 
        'title': title, 'sna_json': sna_json, 'posts_timeline': posts_timeline, 
        'shares_timeline': shares_timeline, 'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline,
        'centrality': centrality
    }

    return render_to_response('dashboard/snadashboard.html', context_dict, context)

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
    twitter_id, fb_id, forum_id = get_smids_fromusername(username)
    sm_usernames_dict = {'Twitter': twitter_id, 'Facebook': fb_id, 'Forum': forum_id}
    sm_usernames = [twitter_id, fb_id, forum_id]

    sm_usernames_str = ','.join("'{0}'".format(x) for x in sm_usernames)

    title = "Student Dashboard: %s, (Twitter: %s, Facebook: %s, Forum: %s)" % (course_code, twitter_id, fb_id, forum_id)
    show_dashboardnav = True

    #print "Verb timelines", datetime.datetime.now()
    posts_timeline = get_timeseries('created', platform, course_code, username=username)
    shares_timeline = get_timeseries('shared', platform, course_code, username=username)
    likes_timeline = get_timeseries('liked', platform, course_code, username=username)
    comments_timeline = get_timeseries('commented', platform, course_code, username=username)

    #print "Activity by Platform", datetime.datetime.now()
    cursor = connection.cursor()
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
    sna_json = sna_buildjson(platform, course_code, username=username, relationshipstoinclude="'mentioned','liked','shared','commented'")

    #print "Word Cloud", datetime.datetime.now()
    tags = get_wordcloud(platform, course_code, username=username)

    sentiments = getClassifiedCounts(platform, course_code, username=username, classifier="VaderSentiment")
    coi = getClassifiedCounts(platform, course_code, username=username, classifier="NaiveBayes_t1.model")

    context_dict = {'show_allplatforms_widgets': show_allplatforms_widgets, 'twitter_timeline': twitter_timeline, 'facebook_timeline': facebook_timeline, 'forum_timeline':forum_timeline, 'youtube_timeline':youtube_timeline, 'diigo_timeline':diigo_timeline, 'blog_timeline':blog_timeline, 'platformactivity_pie_series':platformactivity_pie_series, 'show_dashboardnav':show_dashboardnav, 'course_code':course_code, 'platform':platform, 'title': title, 'course_code':course_code, 'platform':platform, 'username':username, 'sna_json': sna_json,  'tags': tags, 'topcontenttable': topcontenttable, 'activity_pie_series': activity_pie_series, 'posts_timeline': posts_timeline, 'shares_timeline': shares_timeline, 'likes_timeline': likes_timeline, 'comments_timeline': comments_timeline, 'sentiments': sentiments, 'coi': coi }

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

    twitter_id, fb_id, forum_id = get_smids_fromuid(uid)
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
    coi = getClassifiedCounts(platform, course_code, username=username, classifier="NaiveBayes_t1.model")

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