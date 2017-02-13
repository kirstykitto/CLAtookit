from django.db import connection
from gensim import corpora, models, similarities
from collections import defaultdict
import pyLDAvis.gensim
import os
import re
import json
import copy
import funcy as fp
import numpy as np
import subprocess
import jgraph
from pprint import pprint
from collections import OrderedDict
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.utils.html import strip_tags
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn import decomposition
from sklearn.feature_extraction.stop_words import ENGLISH_STOP_WORDS
from sklearn.cluster import AffinityPropagation
from vaderSentiment.vaderSentiment import sentiment as vaderSentiment
from clatoolkit.models import UserProfile, UnitOffering, DashboardReflection, LearningRecord, SocialRelationship, CachedContent, Classification
from common.util import Utility

from xapi.statement.xapi_settings import xapi_settings
from xapi.statement.xapi_getter import xapi_getter
from xapi.statement.xapi_filter import xapi_filter
from xapi.oauth_consumer.operative import LRS_Auth



def getPluginKey(platform):
    return settings.DATAINTEGRATION_PLUGINS[platform].api_config_dict['api_key']

def classify(course_code, platform):
    #Calls JAR to extract and classify messages
    #$ java -cp /dataintegration/MLWrapper/CLAToolKit_JavaMLWrapper-0.1.jar load.from_clatk ./config.json [course_code] [platform]
    print platform
    p = os.popen('java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.from_clatk config.json ' + course_code + ' ' + platform)
    print p
    return p
    '''
    try:
        os.popen(['java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.from_clatk config.json ' + course_code + ' ' + platform])
        return True
    except Exception, e:
        print e
        return e
    '''


def train(course_code, platform):
    #Call JAR to Train of UserReclassifications
    #$ java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.train_onUserClassifications ./config.json [course_code] [platform]
    p = os.popen('java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.train_onUserClassifications config.json ' + course_code + ' ' + platform);
    print p
    return p
    '''
    try:
        os.popen('java -cp CLAToolKit_JavaMLWrapper-0.1.jar load.train_onUserClassifications config.json ' + course_code + ' ' + platform);
        return True
    except Exception, e:
        return e
    '''

def get_uid_fromsmid(username, platform):
    userprofile = None
    if platform == "Twitter":
        userprofile = UserProfile.objects.filter(twitter_id__iexact=username)
    elif platform == "Facebook":
        userprofile = UserProfile.objects.filter(fb_id__iexact=username)
    elif platform == "Forum":
        userprofile = UserProfile.objects.filter(forum_id__iexact=username)
    elif platform == "YouTube":
            userprofile = UserProfile.objects.filter(google_account_name__iexact=username)
    else:
        #platform must be = all
        userprofile = UserProfile.objects.filter(Q(twitter_id__iexact=username) | Q(fb_id__iexact=username) | Q(forum_id__iexact=username) | Q(google_account_name__iexact=username))

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
    elif platform == "YouTube":
            userprofile = UserProfile.objects.filter(google_account_name__iexact=sm_id)
    else:
        #platform must be = all
        userprofile = UserProfile.objects.filter(Q(twitter_id__iexact=sm_id) | Q(fb_id__iexact=sm_id) | Q(forum_id__iexact=sm_id) | Q(google_account_name__iexact=sm_id))
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
    github_id = user.userprofile.github_account_name
    trello_id = user.userprofile.trello_account_name
    blog_id = user.userprofile.blog_id
    diigo_id = user.userprofile.diigo_username
    return twitter_id, fb_id, forum_id, github_id, trello_id, blog_id, diigo_id

def get_smids_fromusername(username):
    user = User.objects.get(username=username)
    twitter_id = user.userprofile.twitter_id
    fb_id = user.userprofile.fb_id
    forum_id = user.userprofile.forum_id
    github_id = user.userprofile.github_account_name
    trello_id = user.userprofile.trello_account_name
    blog_id = user.userprofile.blog_id
    diigo_id = user.userprofile.diigo_username
    return twitter_id, fb_id, forum_id, github_id, trello_id, blog_id, diigo_id


def get_timeseries(unit, sm_verb = None, sm_platform = None, user = None, without_date_utc = False):
    # more info on postgres timeseries
    # http://no0p.github.io/postgresql/2014/05/08/timeseries-tips-pg.html

    platformclause = ""
    if sm_platform is not None and sm_platform != "all":
        platformclause = " and clatoolkit_learningrecord.platform = '%s' " % (sm_platform)

    verb_clause = ""
    if sm_verb is not None:
        verb_clause = " and clatoolkit_learningrecord.verb = '%s' " % (sm_verb)
        
    userclause = ""
    if user is not None:
        userclause = " and clatoolkit_learningrecord.user_id = %s " % (user.id)

    # with filled_dates: Generate date series with count 0 
    # E.g.
    # 2016-12-01 00:00:00+10", 0
    # 2016-12-02 00:00:00+10", 0
    # 2016-12-03 00:00:00+10", 0 
    # ...
    #
    # with daily_counts: Count the number of verbs on each day
    # E.g. 
    # 2016-12-23 00:00:00+10, 3
    # 2017-01-25 00:00:00+10, 1
    #
    # Main SQL: Select date series with actual count
    # If the same date exist in daily_counts, value of smcount will be returned as a result.
    # 2016-12-01, 0
    # ...
    # 2016-12-23, 3
    # 2016-12-24, 0 
    # ...
    sql = """
        with filled_dates as (
            SELECT generate_series( 
                (select start_date from clatoolkit_unitoffering where id = %s)
                 ,(select end_date from clatoolkit_unitoffering where id = %s)
                 , interval '1 day'
            ) as day, 0 as blank_count
        ),
        daily_counts as (
            select 
            date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.datetimestamp as text) from 1 for 11), 'YYYY-MM-DD')) as day, 
            count(*) as smcount
            FROM clatoolkit_learningrecord
            WHERE clatoolkit_learningrecord.unit_id = %s 
            %s %s %s
            group by day
            order by day asc
        )
        select 
        to_date(to_char(filled_dates.day, 'YYYY-MM-DD'), 'YYYY-MM-DD') date
        , coalesce(daily_counts.smcount, filled_dates.blank_count) as counts
        from filled_dates
        left outer join daily_counts on daily_counts.day = filled_dates.day
        order by filled_dates.day;
    """ % (unit.id, unit.id, unit.id, userclause, platformclause, verb_clause)

    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    dataset_list = []

    for row in result:
        curdate = row[0]
        # In JavaScript, month starts at 0, thus subtract 1 from the month
        datapoint = ""
        if without_date_utc:
            datapoint = "%s,%s,%s,%s" % (curdate.year,curdate.month-1,curdate.day,row[1])
        else:
            datapoint = "[Date.UTC(%s, %s, %s), %s]" % (curdate.year, curdate.month - 1, curdate.day, row[1])
        dataset_list.append(datapoint)

    if without_date_utc:
        return dataset_list
    else:
        return ','.join(map(str, dataset_list))


# def get_timeseries_byplatform(sm_platform, unit, username=None, without_date_utc=False):
#     userclause = ""
#     if username is not None:
#         userclause = " AND clatoolkit_learningrecord.username='%s'" % (username)
#         # sm_usernames_str = ','.join("'{0}'".format(x) for x in username)
#         # userclause = " AND clatoolkit_learningrecord.username ILIKE any(array[%s])" % (sm_usernames_str)

#     cursor = connection.cursor()
#     cursor.execute("""
#     with filled_dates as (
#       select day, 0 as blank_count from
#         generate_series('2015-06-01 00:00'::timestamptz, current_date::timestamptz, '1 day')
#           as day
#     ),
#     daily_counts as (
#     select date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD')) as day, count(*) as smcount
#     FROM clatoolkit_learningrecord
#     WHERE clatoolkit_learningrecord.xapi->'context'->>'platform'='%s' AND clatoolkit_learningrecord.unit_id='%s' %s
#     group by date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD'))
#     order by date_trunc('day', to_timestamp(substring(CAST(clatoolkit_learningrecord.xapi->'timestamp' as text) from 2 for 11), 'YYYY-MM-DD')) asc
#     )
#     select filled_dates.day,
#            coalesce(daily_counts.smcount, filled_dates.blank_count) as signups
#       from filled_dates
#         left outer join daily_counts on daily_counts.day = filled_dates.day
#       order by filled_dates.day;
#     """ % (sm_platform, unit.id, userclause))
#     result = cursor.fetchall()
#     dataset_list = []
#     for row in result:
#         curdate = row[0]  # parse(row[0])
#         datapoint = ""
#         if without_date_utc:
#             datapoint = "%s,%s,%s,%s" % (curdate.year, curdate.month - 1, curdate.day, row[1])
#         else:
#             datapoint = "[Date.UTC(%s,%s,%s),%s]" % (curdate.year, curdate.month - 1, curdate.day, row[1])
#         dataset_list.append(datapoint)

#     if without_date_utc:
#         return dataset_list
#     else:
#         dataset = ','.join(map(str, dataset_list))
#         return dataset


def get_active_members_table(unit, platform = None):
    users = User.objects.filter(learningrecord__unit = unit).distinct()

    table = []
    for user in users:
        if platform is None or platform == 'all':
            platforms = user.learningrecord_set.values_list("platform").distinct()
            platforms = [p[0] for p in platforms]
            platforms = ", ".join(platforms)
        else:
            platforms = platform

        num_posts = 0
        num_likes = 0
        num_shares = 0
        num_comments = 0
        
        group_by_column = 'verb'
        obj_counts = get_object_count(unit, group_by_column, platform, user)
        
        for dict_obj in obj_counts:
            if dict_obj[group_by_column] == xapi_settings.VERB_CREATED:
                num_posts = dict_obj['count']
            elif dict_obj[group_by_column] == xapi_settings.VERB_LIKED:
                num_likes = dict_obj['count']
            elif dict_obj[group_by_column] == xapi_settings.VERB_SHARED:
                num_shares = dict_obj['count']
            elif dict_obj[group_by_column] == xapi_settings.VERB_COMMENTED:
                num_comments = dict_obj['count']

        table_html = '<tr><td><a href="/dashboard/student_dashboard?course_id={}&platform={}&user={}">{} {}</a></td>'\
                     '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                     unit.id, platform, user.id, user.first_name, user.last_name, 
                     num_posts, num_likes, num_shares, num_comments, platforms)
        table.append(table_html)

    table_str = ''.join(table)
    return table_str


def get_user_verb_use(user, verb, unit, platform=None):
    if platform:
        return LearningRecord.objects.filter(user=user, unit=unit, verb=verb, platform=platform).count()

    return LearningRecord.objects.filter(user=user, unit=unit, verb=verb).count()


def get_top_content_table(unit, platform=None, user=None):

    if platform and user:
        records = LearningRecord.objects.filter(unit=unit, platform=platform, user=user,
                                                platformparentid="").prefetch_related('user')
    elif platform:
        records = LearningRecord.objects.filter(unit=unit, platform=platform, platformparentid="").prefetch_related(
            'user')
    elif user:
        records = LearningRecord.objects.filter(unit=unit, user=user, platformparentid="").prefetch_related('user')
    else:
        records = LearningRecord.objects.filter(unit=unit, platformparentid="").prefetch_related('user')

    table = []

    for lr in records:
        num_likes = child_count_by_verb(lr, xapi_settings.VERB_LIKED, unit)
        num_shares = child_count_by_verb(lr, xapi_settings.VERB_SHARED, unit)
        num_comments = child_count_by_verb(lr, xapi_settings.VERB_COMMENTED, unit)

        # Get xAPI from LRS
        filters = xapi_filter()
        getter = xapi_getter()
        filters.statement_id = lr.statement_id
        stmt = getter.get_xapi_statements(lr.unit_id, lr.user_id, filters)

        message = stmt[0]['object']['definition']['name']['en-US']
        activity_date = stmt[0]['timestamp']
        # table_html = """<tr><td>{} {}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>""".format(
        #     lr.user.first_name, lr.user.last_name, lr.message, lr.datetimestamp, num_likes, num_shares, num_comments,
        #     lr.platform)
        table_html = """<tr><td>{} {}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>""".format(
            lr.user.first_name, lr.user.last_name, message, activity_date, num_likes, num_shares, num_comments,
            lr.platform)

        table.append(table_html)
    table_str = ''.join(table)
    return table_str


def get_cached_top_content(platform, unit):
    if platform == "all":
        cached_content = CachedContent.objects.filter(unit=unit)
    else:
        cached_content = CachedContent.objects.filter(platform=platform, unit=unit)

    content_output = []
    for platformcontent in cached_content:
        content_output.append(platformcontent.htmltable)
    content_output_str = ''.join(content_output)
    return content_output_str


def get_cached_active_users(platform, unit):
    cached_content = None
    if platform == "all":
        cached_content = CachedContent.objects.filter(unit=unit)
    else:
        cached_content = CachedContent.objects.filter(platform=platform, unit=unit)

    content_output = []
    for platformcontent in cached_content:
        content_output.append(platformcontent.activitytable)
    content_output_str = ''.join(content_output)
    return content_output_str


def child_count_by_verb(lr, verb, unit):
    return LearningRecord.objects.filter(Q(platformparentid=lr.platformid) | Q(id=lr.id), Q(verb=verb),
                                         Q(unit=unit)).count()


def get_allcontent_byplatform(platform, unit, user = None, start_date=None, end_date=None):
    # Create filters to retrieve xAPI
    filters = xapi_filter()
    filters.course = unit.code
    if start_date is not None:
        filters.since = start_date

    if end_date is not None:
        filters.until = end_date

    if platform != "all":
        filters.platform = platform

    user_id = None
    if user:
        user_id = user.id
    getter = xapi_getter()
    statements = getter.get_xapi_statements(unit.id, user_id, filters)

    content_list = []
    id_list = []
    for row in statements:
        content = strip_tags(row['object']['definition']['name']['en-US'])
        content = content.replace('"','')
        content = re.sub(r'[^\w\s]','',content) #quick fix to remove punctuation
        content_list.append(content)
        # Is id_list used?
        id_list.append(row['id'])

    return content_list, id_list


def getClassifiedCounts(platform, unit, user = None, start_date=None, end_date=None, classifier=None):
    classification_dict = None
    if classifier == "VaderSentiment":
        classification_dict = {'positive':0, 'neutral':0, 'negative':0}
    else:
        classification_dict = {'Triggering':0, 'Exploration':0, 'Integration':0, 'Resolution':0, 'Other':0}
    #elif classifier == "NaiveBayes_t1.model":

    kwargs = {'classifier':classifier, 'xapistatement__unit_id': unit.id}
    if classifier == "VaderSentiment":
        kwargs['classifier']=classifier
    else:
        classifier_name = "nb_%s_%s.model" % (unit.id, platform)
        kwargs['classifier'] = classifier_name

    if user is not None:
        # kwargs['xapistatement__username']=username
        records = LearningRecord.objects.filter(user = user)
        record_id_list = []
        for record in records:
            record_id_list.append(record.id)

        kwargs['xapistatement__id__in'] = record_id_list
    if start_date is not None and end_date is not None:
        # kwargs['xapistatement__datetimestamp__range']=(start_date, end_date)
        kwargs['created_at__range']=(start_date, end_date)

    counts_for_pie = ""
    counts = Classification.objects.values('classification').filter(**kwargs).order_by().annotate(Count('classification'))
    for count in counts:
        #print count
        counts_for_pie = counts_for_pie + "['%s', %s]," % (count['classification'],count['classification__count'])
    return counts_for_pie


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
    docs,ids = get_allcontent_byplatform(platform, course_code, start_date=start_date, end_date=end_date)
    documents = remove_stopwords(docs)

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

def nmf(platform, no_topics, unit, start_date=None, end_date=None):
    documents,ids = get_allcontent_byplatform(platform, unit, start_date=start_date, end_date=end_date)
    if len(documents)<5:
        d3_dataset = ""
        topic_output = "Not enough text to run Topic Modeling."
    else:
        min_df = 2
        tfidf = TfidfVectorizer(stop_words=ENGLISH_STOP_WORDS, lowercase=True, strip_accents="unicode", use_idf=True, norm="l2", min_df = min_df, ngram_range=(1,4))
        A = tfidf.fit_transform(documents)

        num_terms = len(tfidf.vocabulary_)
        terms = [""] * num_terms
        for term in tfidf.vocabulary_.keys():
            terms[ tfidf.vocabulary_[term] ] = term

        model = decomposition.NMF(init="nndsvd", n_components=no_topics, max_iter=1000)
        W = model.fit_transform(A)
        H = model.components_

        nmf_topic_terms = {}
        nmf_topic_docs = {}
        nmf_topic_doc_ids = {}

        for topic_index in range( H.shape[0] ):
            top_indices = np.argsort( H[topic_index,:] )[::-1][0:10]
            term_ranking = [terms[i] for i in top_indices]
            nmf_topic_terms[topic_index] = term_ranking
            #tmp = "Topic %d: %s" % ( topic_index, ", ".join( term_ranking ) )

        for topic_index in range( W.shape[1] ):
            top_indices = np.argsort( W[:,topic_index] )[::-1][0:10]
            doc_ranking = [documents[i] for i in top_indices]
            id_ranking = [ids[i] for i in top_indices]
            nmf_topic_docs[topic_index] = doc_ranking
            nmf_topic_doc_ids[topic_index] = id_ranking

        topic_output = ""
        for topic in nmf_topic_terms:
            topic_output = topic_output + "<h2>Topic %d</h2>" % (topic + 1)
            topic_output = topic_output + "<p>"
            for term in nmf_topic_terms[topic]:
                topic_output = topic_output + '<a onClick="searchandhighlight(\'%s\')" class="btn btn-default btn-xs">%s</a> ' % (term, term)
            topic_output = topic_output + "<p>"
            topic_output = topic_output + "<ul>"
            for doc in nmf_topic_docs[topic]:
                topic_output = topic_output + "<li>%s</li>" % (doc)
            topic_output = topic_output + "</ul>"

        # find the % sentiment classification of each topic
        classification_dict = None
        classifier = 'VaderSentiment'
        '''
        if classifier == "VaderSentiment":
            classification_dict = {'Positive':0, 'Neutral':0, 'Negative':0}
        elif classifier == "NaiveBayes_t1.model":
            classification_dict = {'Triggering':0, 'Exploration':0, 'Integration':0, 'Resolution':0, 'Other':0}
        '''
        piebubblechart = {}
        feature_matrix = np.zeros(shape=(no_topics,3))
        course_code = unit.code

        # Get xAPI statement ID from statement ID
        new_nmf_topic_doc_ids = {}
        for t in nmf_topic_terms:
            id_list = []
            for stmt_id in nmf_topic_doc_ids[t]:
                try:
                    # statement id is unique, so don't have to check unit code
                    lrecord = LearningRecord.objects.get(statement_id = stmt_id)
                    id_list.append(lrecord.id)
                except:
                    pass

                new_nmf_topic_doc_ids[t] = id_list

        # Replace with new list (it has xapi statement IDs)
        nmf_topic_doc_ids = new_nmf_topic_doc_ids
        # print '==============='
        # print nmf_topic_doc_ids

        for topic in nmf_topic_terms:
            vals = ""
            radius = 0
            topiclabel = "Topic %d" % (topic + 1)

            classification_dict = {'Positive':0, 'Neutral':0, 'Negative':0}
            # kwargs = {'classifier':classifier, 'xapistatement__course_code': course_code, 'xapistatement__id__in':nmf_topic_doc_ids[topic]}
            kwargs = {'classifier':classifier, 'xapistatement__id__in':nmf_topic_doc_ids[topic]}

            #print Classification.objects.values('classification').filter(**kwargs).order_by().annotate(Count('classification')).query
            counts = Classification.objects.values('classification').filter(**kwargs).order_by().annotate(Count('classification'))
            for count in counts:
                #print count
                classification_dict[count['classification']] = count['classification__count']
            vals = "%d,%d,%d" % (classification_dict['Positive'],classification_dict['Negative'],classification_dict['Neutral'])
            print vals
            radius = classification_dict['Positive'] + classification_dict['Negative'] + classification_dict['Neutral']
            feature_matrix[topic,0] = classification_dict['Positive']
            feature_matrix[topic,1] = classification_dict['Negative']
            feature_matrix[topic,2] = classification_dict['Neutral']
            piebubblechart[topic] = {'label':topiclabel, 'vals':vals, 'radius':radius}

        # Perform Affinity Propogation
        af = AffinityPropagation(preference=-50).fit(feature_matrix)
        cluster_centers_indices = af.cluster_centers_indices_
        aflabels = af.labels_

        n_clusters_ = len(cluster_centers_indices)
        #print 'n_clusters_', n_clusters_, aflabels
        #print feature_matrix

        # generate piebubblechart dataset for d3.js
        #print piebubblechart
        d3_dataset = ""
        for topic in piebubblechart:
            #print topic
            # output format - {label: "Topic 1", vals: [10, 20], cluster: 1, radius: 30},
            d3_dataset = d3_dataset + '{label: "%s", vals: [%s], cluster: %d, radius: %d},' % (piebubblechart[topic]['label'], piebubblechart[topic]['vals'], aflabels[topic], piebubblechart[topic]['radius'])

    return topic_output, d3_dataset


def get_wordcloud(platform, unit, user = None, start_date=None, end_date=None):
    docs = None
    ids = None
    documents = None
    if user is not None:
        docs, ids = get_allcontent_byplatform(platform, unit, user = user, start_date=start_date, end_date=end_date)
    else:
        docs, ids = get_allcontent_byplatform(platform, unit, start_date=start_date, end_date=end_date)

    documents = remove_stopwords(docs)
    #print documents
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

            if (weight > 3):
                #print weight
                word_tags.append('{"text": "%s", "weight": %d},' % (term_freq_pair[0], weight))
                #word_tags.append('["%s", %d],' % (term_freq_pair[0], weight))
            #word_tags.append('<li class="tag%d"><a href="#">%s</a></li>' % (term_freq_pair[1], term_freq_pair[0]))
    tags = "[" + ''.join(word_tags)[:-1] + "]"
    #print tags
    return tags


def get_nodes_by_platform(unit, start_date=None, end_date=None, platform=None):
    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_learningrecord.platform='%s'" % (platform)

    dateclause = ""
    if start_date is not None:
        dateclause = " AND clatoolkit_learningrecord.datetimestamp BETWEEN '%s' AND '%s'" % (start_date, end_date)

    sql = """
            SELECT distinct user_id --, statement_id
            FROM clatoolkit_learningrecord
            WHERE unit_id='%s' %s %s
          """ % (unit.id, platformclause, dateclause)
    # print sql
    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()

    node_dict = {}
    count = 1
    for row in result:
        node_dict[row[0]] = count
        count += 1

    return node_dict


def get_relationships_byplatform(platform, unit, user = None, start_date=None, end_date=None, 
                                 relationshipstoinclude=None):
    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_socialrelationship.platform='%s'" % (platform)

    userclause = ""
    if user is not None:
        userclause = " AND (clatoolkit_socialrelationship.from_user_id='%s'", \
                            " OR clatoolkit_socialrelationship.to_user_id='%s')" % (user.id, user.id)

    dateclause = ""
    if start_date is not None:
        dateclause = " AND clatoolkit_socialrelationship.datetimestamp BETWEEN '%s' AND '%s'" % (start_date, end_date)

    relationshipclause = ""
    if relationshipstoinclude is not None and relationshipstoinclude != '-':
        relationshipclause = " AND clatoolkit_socialrelationship.verb IN (%s) " % (relationshipstoinclude)
    else:
        relationshipclause = " AND clatoolkit_socialrelationship.verb NOT IN ('mentioned','shared','liked','commented') "

    count = 1
    nodes_in_sna_dict = {}

    sql = """
            SELECT clatoolkit_socialrelationship.from_user_id, 
                   clatoolkit_socialrelationship.to_user_id, 
                   clatoolkit_socialrelationship.verb, 
                   clatoolkit_socialrelationship.platform,
                   clatoolkit_socialrelationship.to_external_user
            FROM   clatoolkit_socialrelationship
            WHERE  clatoolkit_socialrelationship.unit_id='%s' %s %s %s %s
          """ % (unit.id, platformclause, userclause, dateclause, relationshipclause)
    # print sql
    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()

    count = 1
    nodes_in_sna_dict = {}

    edge_dict = defaultdict(int)
    mention_dict = defaultdict(int)
    comment_dict = defaultdict(int)
    share_dict = defaultdict(int)
    for row in result:
        from_user = None
        to_user = None
        # These are actually user ID, not user name.
        display_username = row[0]
        display_related_username = row[1]
        try:
            from_user = User.objects.get(id = row[0])
            display_username = from_user.username
        except:
            display_username = row[0]

        try:
            to_user = User.objects.get(id = row[1])
            display_related_username = to_user.username
        except:
            # get parent user from to_external_user column
            display_related_username = row[4]

        verb = row[2]
        row_platform = row[3]
        from_node = display_username
        to_node = display_related_username
        edgekey = "%s__%s" % (from_node,to_node)
        edge_dict[edgekey] += 1
        if verb=="shared":
            share_dict[edgekey] += 1
        elif verb=="commented":
            comment_dict[edgekey] += 1
        elif verb=="mentioned":
            mention_dict[edgekey] += 1
        if from_node not in nodes_in_sna_dict:
            nodes_in_sna_dict[from_node] = count
            count += 1
        if to_node not in nodes_in_sna_dict:
            nodes_in_sna_dict[to_node] = count
            count += 1
    return edge_dict, nodes_in_sna_dict, mention_dict, share_dict, comment_dict



def sna_buildjson(platform, unit, username=None, start_date=None, end_date=None, relationshipstoinclude=None):

    node_dict = None
    edge_dict = None
    nodes_in_sna_dict = None
    
    #if username is not None:
    #    node_dict = get_nodes_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date)
    #    edge_dict, nodes_in_sna_dict, mention_dict, share_dict, comment_dict = get_relationships_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date, relationshipstoinclude=relationshipstoinclude)
    #else:
    node_dict = get_nodes_by_platform(unit, start_date, end_date, platform)

    # print '----- node_dict -----'
    # print node_dict

    count = 1
    # Get user name from user ID
    new_node_dict = {}
    for key in node_dict:
        user = None
        try:
            user = User.objects.get(id = key)
            new_node_dict[user.username] = count
        except:
            new_node_dict[key] = count
            
        count = count + 1

    # replace the original dict with new one
    node_dict = new_node_dict

    # print 'node_dict'
    # print node_dict

    edge_dict, nodes_in_sna_dict, mention_dict, \
    share_dict, comment_dict = get_relationships_byplatform(platform,
                                                            unit,
                                                            start_date=start_date,
                                                            end_date=end_date,
                                                            relationshipstoinclude=relationshipstoinclude)

    # print '----- nodes_in_sna_dict -----'
    # print nodes_in_sna_dict
    # node_dict.update(nodes_in_sna_dict)
    for key in nodes_in_sna_dict:
        node_dict[key] = 1
    count = 1
    for key in node_dict:
        node_dict[key] = count
        count = count + 1

    #print node_dict, node_dict

    # print '----- node_dict -----'
    # print node_dict

    node_type_colours = {'Staff':{'border':'#661A00','fill':'#CC3300'}, \
                         'Student':{'border':'#003D99','fill':'#0066FF'}, \
                         'Visitor':{'border':'black','fill':'white'}}
    dict_types = {'mention': mention_dict, 'share': share_dict, 'comment': comment_dict}
    relationship_type_colours = {'mention': 'grey', 'share': 'green', 'comment': 'red'}

    json_str_list = []
    node_degree_dict = {}
    for node in node_dict:
        node_degree_dict[node] = 1
    # Add degrees based upon edges
    for relationshiptype in dict_types:
        for edge_str in dict_types[relationshiptype]:
            edgefrom, edgeto = edge_str.split('__')
            if edgefrom in node_dict and edgeto in node_dict:
                node_degree_dict[edgefrom] += 1
                node_degree_dict[edgeto] += 1

    # make json for vis.js display
    # Build node json
    json_str_list.append('{"nodes": [')
    #count = 1
    for node in node_dict:
        #print node
        username = node
        u = None
        uid = None
        try:
            # Node is user id and we want user name
            u = User.objects.get(username = node)
            # username = u.username
            uid = str(u.id)
        except:
            username = node
            uid = ''
        
        role = get_role_fromusername(node, platform)
        node_border = node_type_colours[role]['border']
        node_fill = node_type_colours[role]['fill']
        #json_str_list.append('{"id": %d, "label": "%s", "color": {"background":"%s", "border":"%s"}, "value": %d},' % (node_dict[node], username, node_fill, node_border, degree[node_dict[node]]))
        json_str_list.append('{"id": %d, "label": "%s", "uid": "%s", "color": {"background":"%s", "border":"%s"}, "value": %d},' % 
                            (node_dict[node], username, uid, node_fill, node_border, node_degree_dict[node]))
        #count = count + 1
    #json_str_list[len(json_str_list)-1] = json_str_list[len(json_str_list)-1][0:-1]

    if json_str_list[len(json_str_list)-1][-1:] == ',':
        json_str_list[len(json_str_list)-1] = json_str_list[len(json_str_list)-1][0:-1]

    json_str_list.append("],")

    #print 'SNA JSON (edges): %s' % (''.join(json_str_list))

    # Build edge json

    json_str_list.append('"edges": [')

    idcount = 1
    for relationshiptype in dict_types:
        for edge_str in dict_types[relationshiptype]:
            edgefrom, edgeto = edge_str.split('__')
            if edgefrom in node_dict and edgeto in node_dict:
                json_str_list.append('{"id": %d, "from": %s, "to": %s, "arrows":{"to":{"scaleFactor":0.4}}, "label":"%s", "color":"%s", "value":%d, "title": "%d" },' % (idcount, node_dict[edgefrom], node_dict[edgeto], relationshiptype, relationship_type_colours[relationshiptype], dict_types[relationshiptype][edge_str], dict_types[relationshiptype][edge_str]))
                idcount += 1


    if json_str_list[len(json_str_list)-1][-1:] == ',':
        json_str_list[len(json_str_list)-1] = json_str_list[len(json_str_list)-1][0:-1]

    json_str_list.append("]}")
    #print 'SNA JSON: %s' % (''.join(json_str_list))
    return ''.join(json_str_list)


def sentiment_classifier(unit):
    # delete all previous classifications
    Classification.objects.filter(classifier='VaderSentiment').delete()
    # get messages
    sm_objs = LearningRecord.objects.filter(unit=unit)

    for sm_obj in sm_objs:

        # Get xAPI from LRS
        filters = xapi_filter()
        getter = xapi_getter()
        filters.statement_id = sm_obj.statement_id
        stmt = getter.get_xapi_statements(sm_obj.unit_id, sm_obj.user_id, filters)
        message = stmt[0]['object']['definition']['name']['en-US']
        message  = message.encode('utf-8', 'replace')

        sentiment = "Neutral"
        vs = vaderSentiment(message)
        #print vs, message
        #print "\n\t" + str(vs)
        if (vs['compound'] > 0):
            sentiment = "Positive"
        elif (vs['compound'] < 0):
            sentiment = "Negative"
        # Save Classification
        classification_obj = Classification(xapistatement=sm_obj,classification=sentiment,classifier='VaderSentiment')#,classifier_model='VaderSentiment')

        classification_obj.save()


def getNeighbours(jsonStr):
    data = json.loads(jsonStr)
    nodes = data["nodes"]
    edges = data["edges"]
    allNeighbours = {"nodes": []}
    
    for node in nodes:
        neighbours = {"id": node["id"], "neighbours": []}
        for edge in edges:
            #insert directly connected node's ID
            if edge["from"] == node["id"]:
                neighbours["neighbours"].append(edge["to"])
            elif edge["to"] == node["id"]:
                neighbours["neighbours"].append(edge["from"])
        # remove duplicated id from the array before adding it to allNeighbours object
        neighbours["neighbours"] = list(set(neighbours["neighbours"]))
        allNeighbours["nodes"].append(neighbours)

    allNeighbours = json.dumps(allNeighbours)
    return allNeighbours

def get_centrality(jsonStr):
    g = _create_graphElements(json.loads(str(jsonStr)))
    #print(g)
    #layout = g.layout("kk")
    #igraph.plot(g, layout=layout)
    dc = OrderedDict({"ids": g.vs["ids"], "label": g.vs["label"]})
    digits = 2
    numOfNodes = g.vcount()
    dc["inDegree"] = _round_numbers(_normaliseDegree(g.degree(mode="in"), numOfNodes), digits)
    dc["outDegree"] = _round_numbers(_normaliseDegree(g.degree(mode="out"), numOfNodes), digits)
    dc["totalDegree"] = _round_numbers(_normaliseDegree(g.degree(), numOfNodes), digits)
    dc["betweenness"] = _round_numbers(g.betweenness(directed=True), digits)
    dc["inCloseness"] = _round_numbers(g.closeness(mode="in"), digits)
    dc["outCloseness"] = _round_numbers(g.closeness(mode="out"), digits)
    dc["totalCloseness"] = _round_numbers(g.closeness(), digits)
    dc["eigenvector"] = _round_numbers(g.eigenvector_centrality(directed=True, scale=True), digits)
    dc["density"] = _round_number(g.density(loops=True), digits)

    return json.dumps(dc)

def _create_graphElements(jdata):
    ids = []
    labels = []
    for node in jdata["nodes"]:
        ids.append(node["id"])
        labels.append(node["label"])

    connections = []
    for edge in jdata["edges"]:
        #create a tuple and set it in the array
        for val in range(0, int(edge["value"])):
            # create the same edges 'edge["value"]' times
            # edge index starts at 0, so -1 needed
            connections.append( (int(edge["from"]) - 1, int(edge["to"]) - 1) )

    g = igraph.Graph(directed=True)
    g.add_vertices(len(ids))
    g.vs["ids"] = ids
    g.vs["label"] = labels
    g.add_edges(connections)
    return g


def _normaliseDegree(targetArray, numOfNodes):
    if numOfNodes == 0:
        return 0

    index = 0
    #To normalize the degree, degree is divided by n-1, where n is the number of vertices in the graph.
    for num in targetArray:
        if (numOfNodes - 1) <= 0:
            targetArray[index] = 0
        else:
            targetArray[index] = float(num) / (numOfNodes - 1)
            
        index = index + 1

    return targetArray

def _round_numbers(targetArray, digits):
    if type(targetArray) is not list:
        return [targetArray]

    index = 0
    for num in targetArray:
        targetArray[index] = _round_number(num, digits)
        index = index + 1

    return targetArray

def _round_number(target, digits):
    return round(target, digits)


def getCCAData(user, course_code, platform):
    # result = {
    #     "nodes":[
    #         {"node":0,"name":"node0"},
    #         {"node":1,"name":"node1"},
    #         {"node":2,"name":"node2"},
    #         {"node":3,"name":"node3"},
    #     ],
    #     "links":[
    #         {"source":0,"target":1,"value":4},
    #         {"source":1,"target":2,"value":5},
    #         {"source":2,"target":3,"value":7},
    #     ]
    # }

    #     result = {
    # "nodes":[
    # {"node":0,"name":"node0"},
    # {"node":1,"name":"node1"},
    # {"node":2,"name":"node2"},
    # {"node":3,"name":"node3"},
    # {"node":4,"name":"node4"}
    # ],
    # "links":[
    # {"source":0,"target":2,"value":2},
    # {"source":1,"target":3,"value":2},
    # {"source":2,"target":3,"value":2},
    # {"source":2,"target":4,"value":2},
    # {"source":3,"target":4,"value":4}
    # ]}


    result = { "nodes":[], "links":[], "info":[] }
    cursor = connection.cursor()
    cursor.execute("""
        SELECT lrc.xapi->'context'->'contextActivities'->'other'->0->'definition'->'name'->>'en-US' as otherObjType,
        lrc.xapi->'context'->'contextActivities'->'parent'->0->>'id' as repourl
        FROM clatoolkit_learningrecord as lrc
        where lrc.username = '%s' and lrc.platform = '%s' and lrc.course_code = '%s'
    """ % (user.username, platform, course_code))

    records = cursor.fetchall()

    if len(records) == 0:
        return result

    repourl = ""
    for row in records:
        #print row[0]
        if row[0] == 'commit':
            repourl = row[1]
            break

    if repourl == "":
        return result

    cursor.execute("""
        SELECT  distinct 
            lrc.xapi->'context'->'contextActivities'->'other'->0->>'id' as commiturl
        FROM clatoolkit_learningrecord as lrc
        where lrc.xapi->'context'->'contextActivities'->'other'->0->'definition'->'name'->>'en-US'='commit'
        and lrc.xapi->'context'->'contextActivities'->'parent'->0->>'id'='%s'
        """ % (repourl))

    records = cursor.fetchall()
    if len(records) == 0:
        return result

    commitUrlList = []
    for row in records:
        commitUrlList.append(row[0])

    index = 0
    totalLines = 0
    commitTotal = 0
    filepaths = []
    diffs = []
    verbs = []
    for commitUrl in commitUrlList:
        #print ("commit url = " + commitUrl)

        cursor.execute("""
            SELECT  lrc.xapi->'actor'->>'name' as cla_account,
                lrc.xapi->'actor'->'account'->>'name' as github_account,
                lrc.xapi->'verb'->'display'->>'en-US',
                lrc.xapi->'object'->'definition'->'name'->>'en-US' as diffs,
                lrc.xapi->'object'->>'id' as filepath,
                lrc.xapi->>'timestamp' as timestamp,
                lrc.xapi->'context'->'contextActivities'->'other'->0->>'id' as repourl,
                lrc.xapi->'context'->'contextActivities'->'parent'->0->>'id' as commiturl,
                lrc.numofcontentadd,
                lrc.numofcontentdel
            FROM clatoolkit_learningrecord as lrc
            where lrc.xapi->'context'->'contextActivities'->'other'->0->>'id'='%s'
            and lrc.xapi->'context'->'contextActivities'->'parent'->0->>'id'='%s'
            and lrc.xapi->'verb'->'display'->>'en-US' in ('%s', '%s', '%s')
            order by timestamp asc
            """ % (repourl, commitUrl, "added", "updated", "removed"))

        records = cursor.fetchall()
        if len(records) == 0:
            print "This commit has no files."
            #index -= 1
            continue

        row = None
        #for row in records:
        for row in records: 
            #row = records[i]
            verbs.append(row[2])
            diffs.append(row[3])
            filepaths.append(row[4])
            commitTotal += row[8] - row[9]

        node = {"node": index, "name": row[1]}
        info = {"node": index, "cla_name": row[0], "name": row[1], "verb": verbs, "diffs": diffs,
        "filepaths": filepaths, "timestamp": row[5], "repourl": row[6], "commiturl": row[7], "commitlines": commitTotal}
        result["nodes"].append(node)
        result["info"].append(info)
        filepaths = []
        diffs = []
        verbs = []
        #totalLines += row[8] - row[9]
        #prevCommitUrl = row[7]
        print "commit total = " + str(commitTotal)
        if index < len(commitUrlList) - 1:
            totalLines += commitTotal
            print "totalLines = " + str(totalLines)
            link = {"source": index, "target": index + 1,"value":totalLines}
            result["links"].append(link)
            index += 1
            commitTotal = 0

    return result


def get_platform_timeseries_dataset(course_id, platform_names, username=None):

    unit = UnitOffering.objects.get(id = course_id)
    series = []
    for platform in platform_names:
        platformVal = OrderedDict ([
                ('name', platform),
                ('id', 'dataseries_' + platform),
                ('data', get_timeseries(unit, None, platform, without_date_utc = True))
        ])
        series.append(platformVal)

    return OrderedDict([ ('series', series)])


def get_platform_activity_dataset(course_id, platforms, username=None):
    platform_dataset = {}

    platform_count_data = get_platform_count_chart_data(course_id, platforms, 
        chart_title = 'Total number of activities', 
        chart_yAxis_title = 'Total number of activities')

    for platform in platforms:
        verb_count_data = get_verb_count_chart_data(course_id, platform, 
            chart_title = 'Total number of activities', 
            chart_yAxis_title = 'Total number of activities', show_table = 0)
        platform_setting = settings.DATAINTEGRATION_PLUGINS[platform]
        detail_data = get_object_values_chart_data(course_id, platform, 
                        chart_title = 'Activity details', 
                        chart_yAxis_title = 'Activity details',
                        obj_mapper = platform_setting.VERB_OBJECT_MAPPER,
                        obj_disp_names = platform_setting.get_display_names(platform_setting.VERB_OBJECT_MAPPER))
        # detail_data = []
        platform_dataset[platform] = {
            'overview': verb_count_data,
            'details': detail_data
        }

    # set total activities of each platform
    platform_dataset['total'] = {
        'total': platform_count_data
    }
    # Set total
    # platform_dataset['total'] = platform_count_data
    ret = OrderedDict ([
            # ('platforms', platforms),
            ('charts', platform_dataset)
    ])

    return ret


def get_platform_count_chart_data(course_id, platforms, chart_title = '', chart_yAxis_title = ''):
    categories, all_data = get_platform_count(platforms, course_id)

    return create_chart_data_obj(categories, platforms, all_data, chart_title = chart_title, 
        chart_yAxis_title = chart_yAxis_title, show_table = 0, countable = 1)


def get_object_values_chart_data(course_id, platform, chart_title = '', 
    chart_yAxis_title = '', obj_mapper = None, obj_disp_names = None):
    pluginObj = settings.DATAINTEGRATION_PLUGINS[platform]
    verbs = sorted(pluginObj.get_verbs())
    other_context_types = pluginObj.get_other_contextActivity_types(verbs)
    categories, all_data = get_object_values(platform, course_id)

    return create_chart_data_obj(categories, other_context_types, all_data, chart_title = chart_title, 
        chart_yAxis_title = chart_yAxis_title, obj_mapper = obj_mapper, 
        obj_disp_names = obj_disp_names, show_table = 0, countable = 0)


def get_verb_count_chart_data(course_id, platform, chart_title = '', chart_yAxis_title = '', show_table = 1):
    pluginObj = settings.DATAINTEGRATION_PLUGINS[platform]
    # Need to be sorted
    verbs = sorted(pluginObj.get_verbs())
    categories, all_data = get_verb_count(platform, course_id)

    charts = []
    # if chart_type is None or chart_type == '':
    #     chart_type = 'column'

    if show_table is None or show_table != 1:
        show_table = 0

    return create_chart_data_obj(categories, verbs, all_data, chart_title = chart_title, 
        chart_yAxis_title = chart_yAxis_title, show_table = show_table, countable = 1)


def create_chart_data_obj(categories, seriesname, data, chart_title = '', 
    chart_yAxis_title = '', obj_mapper = None, obj_disp_names = None,
    show_table = 1, countable = 1):
    chartVal = OrderedDict ([
            # ('type', chart_type),
            ('title', chart_title),
            ('categories', categories),
            ('seriesName', seriesname),
            ('yAxis', OrderedDict([('title', chart_yAxis_title)])),
            ('data', data),
            ('showTable', show_table), # 1 = Show table with the graph, 0 = Don't show table
            ('countable', countable),
    ])
    if obj_mapper is not None:
        chartVal['objectMapper'] = obj_mapper
    if obj_disp_names is not None:
        chartVal['objectDisplayNames'] = obj_disp_names

    return chartVal



def get_platform_count(platforms, course_id):
    categories = []
    data = {}
    if platforms is None or len(platforms) == 0 or course_id is None or course_id == '':
        return categories, data

    cursor = connection.cursor()
    platforms_str = ''
    for p in platforms:
        if platforms_str != '':
            platforms_str = platforms_str + ', '
        platforms_str = platforms_str + "'" + p + "'"

    sql = """
        select 
        user_id
        , username
        , platform
        , to_char(datetimestamp, 'YYYY,MM,DD') as date_imported
        , count(verb)
        from clatoolkit_learningrecord as cl
        join auth_user on cl.user_id = auth_user.id
        where platform in ({})
        and unit_id = {}
        group by user_id, username, platform, date_imported
        order by user_id, username, platform, date_imported desc
    """.format(platforms_str, course_id)
    cursor.execute(sql)

    # print cursor.query
    result = cursor.fetchall()
    categories, data, series_names = retrieve_data_from_rows(result)
    return categories, data


def get_verb_count(platform, course_id):
    categories = []
    data = {}
    if platform is None or platform == '' or course_id is None or course_id == '':
        return categories, data

    cursor = connection.cursor()
    cursor.execute("""
        select 
        user_id
        , username
        , verb
        , to_char(datetimestamp, 'YYYY,MM,DD') as date_imported
        , count(verb)
        from clatoolkit_learningrecord as cl
        join auth_user on cl.user_id = auth_user.id
        where platform = %s
        and unit_id = %s
        group by user_id, username, verb, date_imported
        order by user_id, username, verb, date_imported desc
    """, [platform, course_id])

    result = cursor.fetchall()
    categories, data, series_names = retrieve_data_from_rows(result)
    return categories, data



def get_object_values(platform, course_id):
    categories = []
    data = {}
    if platform is None or platform == '' or course_id is None or course_id == '':
        return categories, data

    # cursor = connection.cursor()
    # cursor.execute("""select username
    #     , verb
    #     , xapi->'context'->'contextActivities'->'other' as other_context
    #     , to_char(to_date(clatoolkit_learningrecord.xapi->>'timestamp', 'YYYY-MM-DD'), 'YYYY,MM,DD') as date_imported
    #     , clatoolkit_learningrecord.xapi->'object'->'definition'->'name'->>'en-US' as val
    #     from clatoolkit_learningrecord
    #     where platform = %s
    #     and unit_id = %s
    #     order by username, verb, date_imported asc
    # """, [platform, course_id])

    # result = cursor.fetchall()
    # platform_setting = settings.DATAINTEGRATION_PLUGINS[platform]
    # result = platform_setting.get_detail_values_by_fetch_results(result)

    unit = UnitOffering.objects.get(id = course_id)
    filters = xapi_filter()
    filters.platform = platform
    filters.course = unit.code
    getter = xapi_getter()
    result = settings.DATAINTEGRATION_PLUGINS[platform].get_detail_values_by_fetch_results(
                                                            getter.get_xapi_statements(course_id, None, filters))

    username = ''
    series = {}
    verb = '' # This may not be verb. It could be something else such as Trello action type.
    dates = []
    values = []
    for row in result:
        comma = ','
        date_string = Utility.format_date(row[2], comma, comma, True)
        if username == '' or username != row[0]:
            if username != '':
                # Save previous all verbs and its values of the user
                obj = OrderedDict([
                    ('name', verb), # verb
                    ('date', copy.deepcopy(dates)),
                    ('values', copy.deepcopy(values))
                ])

                # Multiple Trello actions belong to the same verb 
                #   (e.g. "update checklist status" and "move card" belong to updated)
                # The two action may be processed one after another in this loop.
                # For instance, 1. user update checklist status, 2. create a card, 3. update another checklist status, and so on.
                # In this case, variable "series" already has an element named updateCheckItemStateOnCard when the loop reaches No.3.
                # Then, the date and the values in "series" variable needs to be extended.
                if series.has_key(verb):
                    existing = series[verb]
                    existing['date'].extend(obj['date'])
                    existing['values'].extend(obj['values'])
                else:
                    series[verb] = obj
                data[username] = series


            # Initialise all variables
            username = row[0]
            series = {}
            verb = row[1]
            dates = [date_string]
            values = [str(row[3])]
            categories.append(username)

        elif username == row[0] and verb == row[1]:
            # Same user and same verb.
            dates.append(date_string)
            values.append(str(row[3]))

        elif username == row[0] and verb != row[1]:
            # Save previous verb and its value
            obj = OrderedDict([
                ('name', verb), # verb
                ('date', copy.deepcopy(dates)), 
                ('values', copy.deepcopy(values))
            ])
            if series.has_key(verb):
                existing = series[verb]
                existing['date'].extend(obj['date'])
                existing['values'].extend(obj['values'])
            else:
                series[verb] = obj

            verb = row[1]
            dates = [date_string]
            values = [str(row[3])]

    # Save the last one
    obj = OrderedDict([
        ('name', verb), # verb
        ('date', copy.deepcopy(dates)), 
        ('values', copy.deepcopy(values))
    ])
    if series.has_key(verb):
        existing = series[verb]
        existing['date'].extend(obj['date'])
        existing['values'].extend(obj['values'])
    else:
        series[verb] = obj

    data[username] = series
    # Sort category
    categories.sort()
    return categories, data

def retrieve_data_from_rows(result):
    categories = []
    series_names = []
    data = {}
    username = ''
    series = {}
    val = ''# val
    dates = [] # date
    values = []
    for row in result:
        # Format date 
        comma = ','
        date_string = Utility.format_date(row[3], comma, comma, True)
        if username == '' or username != row[1]:
            if username != '':
                # Save previous all vals and its values of the user
                obj = OrderedDict([
                    ('name', val), # val
                    ('date', copy.deepcopy(dates)),
                    ('values', copy.deepcopy(values))
                ])
                series[val] = obj
                if not val in series_names:
                    series_names.append(val)
                data[username] = series

            # Initialise all variables
            username = row[1]
            series = {}
            val = row[2] # val
            dates = [date_string] # date
            values = [int(row[4])] # number of vals imported on the date
            categories.append(username)

        elif username == row[1] and val == row[2]:
            # Same user and same val.
            dates.append(date_string)
            values.append(int(row[4]))

        elif username == row[1] and val != row[2]:
            # Save previous val and its value
            obj = OrderedDict([
                ('name', val), # val
                ('date', copy.deepcopy(dates)), 
                ('values', copy.deepcopy(values))
            ])
            series[val] = obj
            if not val in series_names:
                series_names.append(val)
            val = row[2] # val
            dates = [date_string] # date
            values = [int(row[4])] # number of vals imported on the date

    # Save the last one
    obj = OrderedDict([
        ('name', val), # val
        ('date', copy.deepcopy(dates)), 
        ('values', copy.deepcopy(values))
    ])
    series[val] = obj
    if not val in series_names:
        series_names.append(val)
    data[username] = series

    return categories, data, series_names


# This returns all repository name that user has. 
# Private and organization repositories are included (It actually depends on the parameter scope
def get_all_reponames(token, course_id):
    from github import Github

    github_settings = settings.DATAINTEGRATION_PLUGINS[xapi_settings.PLATFORM_GITHUB]
    gh = Github(login_or_token = token, per_page = github_settings.per_page)

    count = 0
    gh_user = gh.get_user()
    repos = gh_user.get_repos(type='all', sort='full_name', direction='asc').get_page(count)

    ret = []
    while True:
        for repo in repos:
            owner = OrderedDict([
                ('name', repo.owner.login),
                ('url', repo.owner.html_url),
                ('avatar_url', repo.owner.avatar_url),
            ])
            obj = OrderedDict([
                ('name', repo.full_name),
                ('url', repo.html_url),
                ('owner', owner),
            ])
            ret.append(obj)

        # Code for paging 
        count = count + 1
        repos = gh_user.get_repos(type='all', sort='full_name', direction='asc').get_page(count)
        temp = list(repos)
        if len(temp) == 0:
            #Break from while
            break;

    return OrderedDict([('repos', ret), ('course_id', course_id)])


def get_verb_timeline_data(unit, platform = None, user = None):
    posts_series = get_timeseries(unit, xapi_settings.VERB_CREATED, platform, user)
    shares_series = get_timeseries(unit, xapi_settings.VERB_SHARED, platform, user)
    likes_series = get_timeseries(unit, xapi_settings.VERB_LIKED, platform, user)
    comments_series = get_timeseries(unit, xapi_settings.VERB_COMMENTED, platform, user)
    return {'posts': posts_series, 'shares': shares_series, 'likes': likes_series, 'comments': comments_series}


def get_platform_timeline_data(unit, platform = None, user = None):
    tw_series = get_timeseries(unit, None, xapi_settings.PLATFORM_TWITTER, user)
    fb_series = get_timeseries(unit, None, xapi_settings.PLATFORM_FACEBOOK, user)
    bl_series = get_timeseries(unit, None, xapi_settings.PLATFORM_BLOG, user)
    yt_series = get_timeseries(unit, None, xapi_settings.PLATFORM_YOUTUBE, user)
    tr_series = get_timeseries(unit, None, xapi_settings.PLATFORM_TRELLO, user)
    gh_series = get_timeseries(unit, None, xapi_settings.PLATFORM_GITHUB, user)

    return {xapi_settings.PLATFORM_TWITTER: tw_series, xapi_settings.PLATFORM_FACEBOOK: fb_series, 
            xapi_settings.PLATFORM_BLOG: bl_series, xapi_settings.PLATFORM_YOUTUBE: yt_series,
            xapi_settings.PLATFORM_TRELLO: tr_series, xapi_settings.PLATFORM_GITHUB: gh_series}


def get_verb_pie_data(unit, platform = None, user = None):
    return get_activity_pie_data(unit, True, platform, user)


def get_platform_pie_data(unit, user = None):
    return get_activity_pie_data(unit, False, None, user)


def get_activity_pie_data(unit, get_verb_count = True, platform = None, user = None):
    value = 'verb' if get_verb_count else 'platform'
    records = get_object_count(unit, value, platform, user)
    pie_series = ''
    for row in records:
        pie_series = pie_series + "['%s', %s]," % (row[value], row['count'])
        
    return pie_series


def get_object_count(unit, group_by_name, platform = None, user = None, verb = None):
    records = LearningRecord.objects.filter(unit = unit)
    if user is not None:
        records = records.filter(user = user)

    if platform is not None and platform != 'all':
        records = records.filter(platform = platform)

    if verb is not None:
        records = records.filter(verb = verb)

    return records.values(group_by_name).annotate(count=Count(group_by_name))



def get_issue_list(course_id):

    # Get issues assigned to the users in the course
    unit = UnitOffering.objects.get(id = course_id)
    filters = xapi_filter()
    filters.platform = xapi_settings.PLATFORM_GITHUB
    filters.course = unit.code
    getter = xapi_getter()
    stmts = getter.get_xapi_statements(course_id, None, filters)

    assigned_users = get_assigned_users(stmts)
    issue_status = get_issue_status(stmts)

    for issue_url in issue_status:
        status = xapi_settings.VERB_OPENED
        issue = issue_status[issue_url]

        # Count the number of opened/closed
        count_open = issue.count(xapi_settings.VERB_OPENED)
        count_close = issue.count(xapi_settings.VERB_CLOSED)
        if count_open == count_close:
            status = xapi_settings.VERB_CLOSED
            
        for assignee in assigned_users:
            issue_objs = assigned_users[assignee]
            for issue in issue_objs:
                if issue.get(issue_url) is not None:
                    issue[issue_url] = status
                    
    ret = OrderedDict([
        ('assigned_users', assigned_users),
    ])

    return ret


def get_issue_status(xapi_statements):

    issues = {}
    for statement in xapi_statements:
        # Ignore other activities
        verb = statement['verb']['display']['en-US']
        if not (verb == xapi_settings.VERB_OPENED or verb == xapi_settings.VERB_CLOSED) \
            or statement['object']['definition']['type'] != xapi_settings.get_object_iri(xapi_settings.OBJECT_NOTE):
            continue

        issue_url = statement['object']['id']
        # Save verb in the array to count the number of opened/closed to determine whether the issue is opened/closed
        if issue_url not in issues:
            issues[issue_url] = [verb]
        else:
            issues[issue_url].append(verb)

    return issues

def get_assigned_users(xapi_statements):
# def get_assigned_issues(course_id):

    assigned_users = {}
    for statement in xapi_statements:
        # Ignore other activities
        if statement['verb']['display']['en-US'] != xapi_settings.VERB_ADDED \
            or statement['object']['definition']['type'] != xapi_settings.get_object_iri(xapi_settings.OBJECT_PERSON):
            continue

        assignee = statement['object']['definition']['name']['en-US']
        issue_url = statement['context']['contextActivities']['parent'][0]['id']

        if assignee not in assigned_users:
            # Save the status of the issue as open temporarily. 
            # The status will be upudated later
            assigned_users[assignee] = [{issue_url: xapi_settings.VERB_OPENED}]
        else:
            issue_objs = assigned_users[assignee]
            for issue in issue_objs:
                if issue.get(issue_url) is None:
                    # Save the status of the issue as open temporarily. 
                    # The status will be upudated later
                    issue_objs.append({issue_url: xapi_settings.VERB_OPENED})
                    # assigned_users[assignee] = issue_objs
                    break

    return assigned_users
