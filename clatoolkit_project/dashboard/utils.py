from django.db import connection
from gensim import corpora, models, similarities
from collections import defaultdict
import pyLDAvis.gensim
import os
import json
import funcy as fp
from pprint import pprint
#from dateutil.parser import parse
from django.contrib.auth.models import User
from clatoolkit.models import UserProfile, UnitOffering, DashboardReflection, LearningRecord, SocialRelationship, CachedContent
from django.db.models import Q
from django.utils.html import strip_tags
import networkx as nx
import re
import subprocess


def classify(course_code, platform):
    #Calls JAR to extract and classify messages
    #$ java -cp /dataintegration/MLWrapper/CLAToolKit_JavaMLWrapper-0.1.jar load.from_clatk ./config.json [course_code] [platform]
    try:
        os.popen(['java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.from_clatk config.json ' + course_code + ' ' + platform]);
        return True
    except Exception, e:
        return e


def train(course_code, platform):
    #Call JAR to Train of UserReclassifications
    #$ java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.train_onUserClassifications ./config.json [course_code] [platform]
    try:
        os.popen('java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.train_onUserClassifications config.json ' + course_code + ' ' + platform);
        return True
    except Exception, e:
        return e

def get_uid_fromsmid(username, platform):
    userprofile = None
    if platform == "Twitter":
        userprofile = UserProfile.objects.filter(twitter_id__iexact=username)
    elif platform == "Facebook":
        userprofile = UserProfile.objects.filter(fb_id__iexact=username)
    elif platform == "Forum":
        userprofile = UserProfile.objects.filter(forum_id__iexact=username)
    else:
        #platform must be = all
        userprofile = UserProfile.objects.filter(Q(twitter_id__iexact=username) | Q(fb_id__iexact=username) | Q(forum_id__iexact=username))

    id = userprofile[0].user.id
    return id

def get_username_fromsmid(sm_id, platform):
    #print "sm_id", sm_id
    userprofile = None
    if platform == "Twitter":
        userprofile = UserProfile.objects.filter(twitter_id__iexact=sm_id)
    elif platform == "Facebook":
        userprofile = UserProfile.objects.filter(fb_id__iexact=sm_id)
    elif platform == "Forum":
        userprofile = UserProfile.objects.filter(forum_id__iexact=sm_id)
    else:
        #platform must be = all
        userprofile = UserProfile.objects.filter(Q(twitter_id__iexact=sm_id) | Q(fb_id__iexact=sm_id) | Q(forum_id__iexact=sm_id))
    if len(userprofile)>0:
        username = userprofile[0].user.username
    else:
        username = sm_id # user may not be registered but display platform username
    return username

def get_role_fromusername(username, platform):
    user = User.objects.filter(username=username)
    role = ""
    if len(user)>0:
        role = user[0].userprofile.role
    else:
        role = 'Visitor' # user may not be registered but display platform username
    return role

def get_smids_fromuid(uid):
    user = User.objects.get(pk=uid)
    twitter_id = user.userprofile.twitter_id
    fb_id = user.userprofile.fb_id
    forum_id = user.userprofile.forum_id
    return twitter_id, fb_id, forum_id

def get_smids_fromusername(username):
    user = User.objects.get(username=username)
    twitter_id = user.userprofile.twitter_id
    fb_id = user.userprofile.fb_id
    forum_id = user.userprofile.forum_id
    return twitter_id, fb_id, forum_id

def get_timeseries(sm_verb, sm_platform, course_code, username=None):
    # more info on postgres timeseries
    # http://no0p.github.io/postgresql/2014/05/08/timeseries-tips-pg.html

    platformclause = ""
    if sm_platform != "all":
        platformclause = " AND clatoolkit_learningrecord.xapi->'context'->>'platform'='%s'" % (sm_platform)

    userclause = ""
    if username is not None:
        userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
        #sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
        #userclause = " AND clatoolkit_learningrecord.username IN (%s)" % (sm_usernames_str)

    cursor = connection.cursor()
    cursor.execute("""
    with filled_dates as (
      select day, 0 as blank_count from
        generate_series('2015-06-01 00:00'::timestamptz, current_date::timestamptz, '1 day')
          as day
    ),
    daily_counts as (
    select date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD')) as day, count(*) as smcount
    FROM clatoolkit_learningrecord
    WHERE clatoolkit_learningrecord.verb='%s' %s AND clatoolkit_learningrecord.course_code='%s' %s
    group by date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD'))
    order by date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD')) asc
    )
    select filled_dates.day,
           coalesce(daily_counts.smcount, filled_dates.blank_count) as signups
      from filled_dates
        left outer join daily_counts on daily_counts.day = filled_dates.day
      order by filled_dates.day;
    """ % (sm_verb, platformclause, course_code, userclause))
    result = cursor.fetchall()
    dataset_list = []
    for row in result:
        curdate = row[0] #parse(row[0])
        datapoint = "[Date.UTC(%s,%s,%s),%s]" % (curdate.year,curdate.month-1,curdate.day,row[1])
        dataset_list.append(datapoint)
    dataset = ','.join(map(str, dataset_list))
    return dataset

def get_timeseries_byplatform(sm_platform, course_code, username=None):

    userclause = ""
    if username is not None:
        userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
        #sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
        #userclause = " AND clatoolkit_learningrecord.username ILIKE any(array[%s])" % (sm_usernames_str)

    cursor = connection.cursor()
    cursor.execute("""
    with filled_dates as (
      select day, 0 as blank_count from
        generate_series('2015-06-01 00:00'::timestamptz, current_date::timestamptz, '1 day')
          as day
    ),
    daily_counts as (
    select date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD')) as day, count(*) as smcount
    FROM clatoolkit_learningrecord
    WHERE clatoolkit_learningrecord.xapi->'context'->>'platform'='%s' AND clatoolkit_learningrecord.course_code='%s' %s
    group by date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD'))
    order by date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD')) asc
    )
    select filled_dates.day,
           coalesce(daily_counts.smcount, filled_dates.blank_count) as signups
      from filled_dates
        left outer join daily_counts on daily_counts.day = filled_dates.day
      order by filled_dates.day;
    """ % (sm_platform, course_code, userclause))
    result = cursor.fetchall()
    dataset_list = []
    for row in result:
        curdate = row[0] #parse(row[0])
        datapoint = "[Date.UTC(%s,%s,%s),%s]" % (curdate.year,curdate.month-1,curdate.day,row[1])
        dataset_list.append(datapoint)
    dataset = ','.join(map(str, dataset_list))
    return dataset

def get_active_members_table(platform, course_code):

    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    cursor = connection.cursor()
    cursor.execute("""
        SELECT distinct clatoolkit_learningrecord.username, clatoolkit_learningrecord.platform
        FROM clatoolkit_learningrecord
        WHERE clatoolkit_learningrecord.course_code='%s' %s
    """ % (course_code, platformclause))
    result = cursor.fetchall()
    table = []
    for row in result:
        #sm_userid = row[0]
        sm_platform = row[1]
        username = row[0] #get_username_fromsmid(sm_userid, sm_platform)
        '''
        if username is None:
            username = sm_userid
        '''
        noposts = get_verbuse_byuser(username, "created", sm_platform, course_code)
        nolikes = get_verbuse_byuser(username, "liked", sm_platform, course_code)
        noshares = get_verbuse_byuser(username, "shared", sm_platform, course_code)
        nocomments = get_verbuse_byuser(username, "commented", sm_platform, course_code)

        table_html = '<tr><td><a href="/dashboard/student_dashboard?course_code=%s&platform=%s&username=%s&username_platform=%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (course_code, platform, row[0], sm_platform, username, noposts, nolikes, noshares, nocomments, row[1])
        table.append(table_html)
    table_str = ''.join(table)
    return table_str

def get_verbuse_byuser(username, verb, platform, course_code):

    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    cursor = connection.cursor()
    cursor.execute("""
        select count(clatoolkit_learningrecord.username)
        FROM clatoolkit_learningrecord
        WHERE clatoolkit_learningrecord.username='%s' AND clatoolkit_learningrecord.verb='%s' AND clatoolkit_learningrecord.course_code='%s' %s
    """ % (username, verb, course_code, platformclause))
    result = cursor.fetchone()
    count = result[0]
    return count

def get_top_content_table(platform, course_code, username=None):

    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    userclause = ""
    if username is not None:
        userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
        #sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
        #userclause = " AND clatoolkit_learningrecord.username ILIKE any(array[%s]) LIMIT 20" % (sm_usernames_str)

    cursor = connection.cursor()
    # distinct
    cursor.execute("""
    SELECT clatoolkit_learningrecord.platformid, clatoolkit_learningrecord.xapi->'object'->'definition'->'name'->>'en-US', clatoolkit_learningrecord.username, clatoolkit_learningrecord.xapi->>'timestamp', clatoolkit_learningrecord.platform
    FROM clatoolkit_learningrecord
    WHERE clatoolkit_learningrecord.course_code='%s' %s %s
    """ % (course_code, platformclause, userclause))
    result = cursor.fetchall()
    table = []
    for row in result:
        id = row[0]
        sm_userid = row[2]
        username = get_username_fromsmid(sm_userid, platform)
        if username is None:
            username = sm_userid

        post = row[1] #parse(row[0])
        nolikes = contentcount_byverb(id, "liked", platform, course_code)
        noshares = contentcount_byverb(id, "shared", platform, course_code)
        nocomments = contentcount_byverb(id, "commented", platform, course_code)
        posted_on = row[3]
        table_html = "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (username, post, posted_on, nolikes, noshares, nocomments, row[4])
        table.append(table_html)
    table_str = ''.join(table)
    return table_str

def get_cached_top_content(platform, course_code):
    cached_content = None
    if platform=="all":
        cached_content = CachedContent.objects.filter(course_code=course_code)
    else:
        cached_content = CachedContent.objects.filter(platform=platform,course_code=course_code)
    #print platform, course_code, cached_content
    content_output = []
    for platformcontent in cached_content:
        content_output.append(platformcontent.htmltable)
    content_output_str = ''.join(content_output)
    return content_output_str

def get_cached_active_users(platform, course_code):
    cached_content = None
    if platform=="all":
        cached_content = CachedContent.objects.filter(course_code=course_code)
    else:
        cached_content = CachedContent.objects.filter(platform=platform,course_code=course_code)
    #print platform, course_code, cached_content
    content_output = []
    for platformcontent in cached_content:
        content_output.append(platformcontent.activitytable)
    content_output_str = ''.join(content_output)
    return content_output_str

def contentcount_byverb(id, verb, platform, course_code, username=None):

    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    userclause = ""
    if username is not None:
        userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
        #sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
        #userclause = " AND clatoolkit_learningrecord.username IN %s" % (sm_usernames_str)

    cursor = connection.cursor()
    sql = ""

    if verb =='shared':
        sql = """
            SELECT count(*)
            FROM clatoolkit_learningrecord
            WHERE
            clatoolkit_learningrecord.verb='%s'
            AND clatoolkit_learningrecord.course_code='%s' %s %s
            AND (clatoolkit_learningrecord.platformid='%s' OR
            clatoolkit_learningrecord.platformparentid='%s');
        """ % (verb, course_code, platformclause, userclause, id, id)
    else:
        sql = """
        SELECT count(*)
        FROM clatoolkit_learningrecord
        WHERE clatoolkit_learningrecord.verb='%s' %s %s AND clatoolkit_learningrecord.platformid='%s'
        """ % (verb, platformclause, userclause, id)
    cursor.execute(sql)
    result = cursor.fetchone()
    count = result[0]
    return count

def get_allcontent_byplatform(platform, course_code, username=None, start_date=None, end_date=None):

    dateclause = ""
    if start_date is not None:
        dateclause = " AND clatoolkit_learningrecord.datetimestamp BETWEEN '%s' AND '%s'" % (start_date, end_date)

    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    userclause = ""
    if username is not None:
        userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
        #sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
        #userclause = " AND clatoolkit_learningrecord.username IN (%s)" % (sm_usernames_str)

    cursor = connection.cursor()
    cursor.execute("""
        SELECT clatoolkit_learningrecord.message as content
        FROM clatoolkit_learningrecord
        WHERE clatoolkit_learningrecord.course_code='%s' %s %s %s
    """ % (course_code, platformclause, userclause, dateclause))
    result = cursor.fetchall()
    content_list = []
    for row in result:
        #content_list.append(row[0])
        content = strip_tags(row[0])
        content = content.replace('"','')
        content = re.sub(r'[^\w\s]','',content) #quick fix to remove punctuation
        content_list.append(content)

    return content_list

def loadStopWords(stopWordFile):
    stopWords = []
    for line in open(stopWordFile):
        for word in line.split( ): #in case more than one per line
            stopWords.append(word)
    return stopWords

def remove_stopwords(documents):
    stop_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'englishstop.txt')
    stoplist = loadStopWords(stop_path)
    texts = [[word for word in document.lower().split() if word not in stoplist] for document in documents]
    '''
    # remove words that appear only once
    frequency = defaultdict(int)
    for text in texts:
        for token in text:
            frequency[token] += 1

    texts = [[token for token in text if frequency[token] > 1] for text in texts]

    for txt in texts:
        print txt
    '''
    #texts = [[token for token in text if not token.contains('"') > 1] for text in texts]
    return texts

def get_LDAVis_JSON(platform, num_topics, course_code, start_date=None, end_date=None):
    #print "get_LDAVis_JSON"
    documents = remove_stopwords(get_allcontent_byplatform(platform, course_code, start_date=start_date, end_date=end_date))

    # Make dictionary
    dictionary = corpora.Dictionary(documents)

    #Create and save corpus
    corpus = [dictionary.doc2bow(text) for text in documents]

    #Run LDA
    model = models.ldamodel.LdaModel(corpus, id2word=dictionary, num_topics=num_topics)

    tmp = pyLDAvis.gensim.prepare(model, corpus, dictionary).to_json()
    #print tmp
    #tmp = model.show_topics(num_topics=20, num_words=5, log=False, formatted=False)

    return tmp

'''
def CalculateWeights(arrValues, weightsCount):
    # converted to python from http://stackoverflow.com/questions/4991354/set-font-size-in-tag-cloud-based-on-occurances
    arrWeights = [];
    minValue = 999999;
    maxValue = -1;
    for i in arrValues:
        curValue = i
        if (curValue < minValue):
            minValue = curValue
        if (curValue > maxValue):
            maxValue = curValue

    diff = weightsCount / (maxValue - minValue);
    for i in arrValues:
        curValue = i
        if (curValue == minValue):
            arrWeights.append(1)
        elif (curValue == maxValue):
            arrWeights.append(weightsCount)
        else:
            arrWeights.append(int(curValue * diff) + 1)
            #arrWeights.append(int(curValue * diff, 10) + 1)
    return arrWeights
'''

def get_wordcloud(platform, course_code, username=None, start_date=None, end_date=None):
    #print "get_wordcloud", platform, course_code
    documents = None
    if username is not None:
        documents = remove_stopwords(get_allcontent_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date))
    else:
        documents = remove_stopwords(get_allcontent_byplatform(platform, course_code, start_date=start_date, end_date=end_date))
    print documents
    # Make dictionary
    dictionary = corpora.Dictionary(documents)

    #Create and save corpus
    corpus = [dictionary.doc2bow(text) for text in documents]

    #Calculate Term Frequencies
    term_freqs_dict = fp.merge_with(sum, *corpus)
    N = len(term_freqs_dict)

    vocab = [dictionary[id] for id in xrange(N)]
    freqs = [term_freqs_dict[id] for id in xrange(N)]

    term_freqs = zip(vocab,freqs)
    word_tags = []

    for term_freq_pair in term_freqs:
        #print "term_freq_pair", term_freq_pair
        if ((not term_freq_pair[0].startswith('http')) or (term_freq_pair[0]=='-')):
            weight = 0
            if type(term_freq_pair[1]) is tuple:
                weight = int(term_freq_pair[1][1])
            else:
                weight = int(term_freq_pair[1])
            word_tags.append('{"text": "%s", "weight": %d},' % (term_freq_pair[0], weight))
            #word_tags.append('<li class="tag%d"><a href="#">%s</a></li>' % (term_freq_pair[1], term_freq_pair[0]))
    tags = "[" + ''.join(word_tags)[:-1] + "]"
    #print tags
    return tags

def get_nodes_byplatform(platform, course_code, username=None, start_date=None, end_date=None):

    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    userclause = ""
    if username is not None:
        userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
        #sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
        #userclause = " AND clatoolkit_learningrecord.username IN (%s)" % (sm_usernames_str)

    dateclause = ""
    if start_date is not None:
        dateclause = " AND clatoolkit_learningrecord.datetimestamp BETWEEN '%s' AND '%s'" % (start_date, end_date)

    sql = """
            SELECT distinct clatoolkit_learningrecord.username
            FROM clatoolkit_learningrecord
            WHERE clatoolkit_learningrecord.course_code='%s' %s %s %s
          """ % (course_code, platformclause, userclause, dateclause)
    print sql
    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    node_dict = {}
    count = 1
    for row in result:
        node_dict[row[0]] = count
        count += 1
    print "node_dict", node_dict
    return node_dict

def get_relationships_byplatform(platform, course_code, username=None, start_date=None, end_date=None):


    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    userclause = ""
    if username is not None:
        userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
        #sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
        #userclause = " AND clatoolkit_learningrecord.username IN (%s)" % (sm_usernames_str)

    dateclause = ""
    if start_date is not None:
        dateclause = " AND clatoolkit_learningrecord.datetimestamp BETWEEN '%s' AND '%s'" % (start_date, end_date)

    count = 1
    nodes_in_sna_dict = {}
    #first get @mentions
    #and add edge based on @mention
    #This query gets #hashtags as well and needs to be refined
    sql = """
            SELECT clatoolkit_learningrecord.username, clatoolkit_learningrecord.verb, obj, clatoolkit_learningrecord.platform
            FROM   clatoolkit_learningrecord, json_array_elements(clatoolkit_learningrecord.xapi->'context'->'contextActivities'->'other') obj
            WHERE  clatoolkit_learningrecord.course_code='%s' %s %s %s
          """ % (course_code, platformclause, userclause, dateclause)
    cursor = connection.cursor()
    cursor.execute(sql)
    #print username, sql
    result = cursor.fetchall()
    edge_dict = defaultdict(int)
    mention_dict = defaultdict(int)
    comment_dict = defaultdict(int)
    share_dict = defaultdict(int)
    for row in result:
        #print row[1]
        dict = row[2] #json.loads(row[1])
        #print row[0]
        # get @mention
        #"{"definition": {"type": "http://id.tincanapi.com/activitytype/tag", "name": {"en-US": "@sbuckshum"}}, "id": "http://id.tincanapi.com/activity/tags/tincan", "objectType": "Activity"}"
        tag = dict["definition"]["name"]["en-US"]
        if tag.startswith('@'): # hastags are also returned in query and need to be filtered out
            from_node = get_username_fromsmid(row[0], row[3])
            to_node = get_username_fromsmid(tag[1:], row[3]) #remove @symbol
            edgekey = "%s__%s" % (from_node,to_node)
            edge_dict[edgekey] += 1
            mention_dict[edgekey] += 1
            if from_node not in nodes_in_sna_dict:
                nodes_in_sna_dict[from_node] = count
                count += 1
            if to_node not in nodes_in_sna_dict:
                nodes_in_sna_dict[to_node] = count
                count += 1

    #get all statements with platformparentid
    sql = """
            SELECT clatoolkit_learningrecord.username, clatoolkit_learningrecord.verb, clatoolkit_learningrecord.parentusername, clatoolkit_learningrecord.platform, clatoolkit_learningrecord.platformparentid
            FROM clatoolkit_learningrecord
            WHERE COALESCE(clatoolkit_learningrecord.platformparentid, '') != '' AND clatoolkit_learningrecord.course_code='%s' %s %s
          """ % (course_code, platformclause, userclause)

    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    #print sql
    for row in result:
        #print row
        platform_username = row[0]
        verb = row[1]
        platform_parent_username = row[2]
        row_platform = row[3] #if platform=all then need to know rows platform
        display_username = get_username_fromsmid(platform_username, row_platform)
        display_related_username = get_username_fromsmid(platform_parent_username, row_platform)
        #print "platform_username", platform_username, "display_username", display_username
        #print "platform_parent_username", platform_parent_username, "display_related_username", display_related_username
        from_node = display_username
        to_node = display_related_username
        edgekey = "%s__%s" % (from_node,to_node)
        edge_dict[edgekey] += 1
        if verb=="shared":
            share_dict[edgekey] += 1
        elif verb=="commented":
            comment_dict[edgekey] += 1
        if from_node not in nodes_in_sna_dict:
            nodes_in_sna_dict[from_node] = count
            count += 1
        if to_node not in nodes_in_sna_dict:
            nodes_in_sna_dict[to_node] = count
            count += 1
    return edge_dict, nodes_in_sna_dict, mention_dict, share_dict, comment_dict

def sna_buildjson(platform, course_code, username=None, start_date=None, end_date=None):

    print username
    node_dict = None
    edge_dict = None
    nodes_in_sna_dict = None
    if username is not None:
        node_dict = get_nodes_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date)
        edge_dict, nodes_in_sna_dict, mention_dict, share_dict, comment_dict = get_relationships_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date)
    else:
        node_dict = get_nodes_byplatform(platform, course_code, start_date=start_date, end_date=end_date)
        edge_dict, nodes_in_sna_dict, mention_dict, share_dict, comment_dict = get_relationships_byplatform(platform, course_code, start_date=start_date, end_date=end_date)

    node_type_colours = {'Staff':{'border':'#661A00','fill':'#CC3300'}, 'Student':{'border':'#003D99','fill':'#0066FF'}, 'Visitor':{'border':'black','fill':'white'}}
    dict_types = {'mention': mention_dict, 'share': share_dict, 'comment': comment_dict}
    relationship_type_colours = {'mention': 'black', 'share': 'green', 'comment': 'red'}

    print node_dict
    print edge_dict

    json_str_list = []
    #print node_dict
    #print nodes_in_sna_dict
    #if username is not None:
    if len(nodes_in_sna_dict)>0:
        node_dict = nodes_in_sna_dict

    #pprint(node_dict)
    #pprint(nodes_in_sna_dict)
    #pprint(edge_dict)

    # make networkx graph from sna data
    G=nx.MultiGraph() # Create a multi-graph as multiple directed edges per verb
    # Add nodes
    for node in node_dict:
        G.add_node(node_dict[node])
    # Add edges
    for relationshiptype in dict_types:
        for edge_str in dict_types[relationshiptype]:
            edgefrom, edgeto = edge_str.split('__')
            if edgefrom in node_dict and edgeto in node_dict:
                edge_attributes = "{'weight':%d, 'verb':'%s'}" % (dict_types[relationshiptype][edge_str], relationshiptype)
                print edge_attributes
                G.add_edge(node_dict[edgefrom], node_dict[edgeto], edge_attributes)

    '''
    pr = nx.pagerank_numpy(G, alpha=0.9)
    print "pagerank", pr
    degree = nx.degree(G,weight='weight')
    print "degree", degree
    betweenness = nx.betweenness_centrality(G)
    print "betweenness", betweenness
    degree_centrality = nx.degree_centrality(G)
    print "degree_centrality", degree_centrality
    '''
    degree = nx.degree(G,weight='weight')
    #print "degree", degree

    # make json for vis.js display
    # Build node json
    json_str_list.append('{"nodes": [')
    for node in node_dict:
        #print node
        username = node
        role = get_role_fromusername(node, platform)
        node_border = node_type_colours[role]['border']
        node_fill = node_type_colours[role]['fill']
        json_str_list.append('{"id": %d, "label": "%s", "color": {"background":"%s", "border":"%s"}, "value": %d},' % (node_dict[node], username, node_fill, node_border, degree[node_dict[node]]))
    json_str_list[len(json_str_list)-1] = json_str_list[len(json_str_list)-1][0:-1]
    json_str_list.append("],")

    # Build edge json

    json_str_list.append('"edges": [')

    #print "mention_dict", mention_dict
    #print "share_dict", share_dict
    #print "comment_dict", comment_dict
    idcount = 1;
    for relationshiptype in dict_types:
        for edge_str in dict_types[relationshiptype]:
            edgefrom, edgeto = edge_str.split('__')
            if edgefrom in node_dict and edgeto in node_dict:
                json_str_list.append('{"id": %d, "from": %s, "to": %s, "arrows":{"to":{"scaleFactor":0.4}}, "label":"%s", "color":"%s", "value":%d, "title": "%d" },' % (idcount, node_dict[edgefrom], node_dict[edgeto], relationshiptype, relationship_type_colours[relationshiptype], dict_types[relationshiptype][edge_str], dict_types[relationshiptype][edge_str]))
                idcount += 1

    json_str_list[len(json_str_list)-1] = json_str_list[len(json_str_list)-1][0:-1]
    json_str_list.append("]}")
    return ''.join(json_str_list)
