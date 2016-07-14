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
from clatoolkit.models import UserProfile, UnitOffering, DashboardReflection, LearningRecord, SocialRelationship, CachedContent, Classification
from django.db.models import Q, Count
from django.utils.html import strip_tags
import re
from vaderSentiment.vaderSentiment import sentiment as vaderSentiment
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn import decomposition
from sklearn.feature_extraction.stop_words import ENGLISH_STOP_WORDS
import numpy as np
from sklearn.cluster import AffinityPropagation

import subprocess
import igraph
from collections import OrderedDict

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
        SELECT clatoolkit_learningrecord.message as content, clatoolkit_learningrecord.id
        FROM clatoolkit_learningrecord
        WHERE clatoolkit_learningrecord.course_code='%s' %s %s %s
    """ % (course_code, platformclause, userclause, dateclause))
    result = cursor.fetchall()
    content_list = []
    id_list = []
    for row in result:
        #content_list.append(row[0])
        content = strip_tags(row[0])
        content = content.replace('"','')
        content = re.sub(r'[^\w\s]','',content) #quick fix to remove punctuation
        content_list.append(content)
        id_list.append(row[1])

    return content_list,id_list

def getClassifiedCounts(platform, course_code, username=None, start_date=None, end_date=None, classifier=None):
    classification_dict = None
    if classifier == "VaderSentiment":
        classification_dict = {'positive':0, 'neutral':0, 'negative':0}
    else:
        classification_dict = {'Triggering':0, 'Exploration':0, 'Integration':0, 'Resolution':0, 'Other':0}
    #elif classifier == "NaiveBayes_t1.model":

    kwargs = {'classifier':classifier, 'xapistatement__course_code': course_code}
    if classifier == "VaderSentiment":
        kwargs['classifier']=classifier
    else:
        classifier_name = "nb_%s_%s.model" % (course_code,"YouTube")
        kwargs['classifier']= classifier_name
    if username is not None:
        kwargs['xapistatement__username']=username
    if start_date is not None:
        kwargs['xapistatement__datetimestamp__range']=(start_date, end_date)

    counts_for_pie = ""
    counts = Classification.objects.values('classification').filter(**kwargs).order_by().annotate(Count('classification'))
    for count in counts:
        #print count
        counts_for_pie = counts_for_pie + "['%s',  %s]," % (count['classification'],count['classification__count'])
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

def nmf(platform, no_topics, course_code, start_date=None, end_date=None):
    documents,ids = get_allcontent_byplatform(platform, course_code, start_date=start_date, end_date=end_date)
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

        #print nmf_topic_doc_ids
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

        for topic in nmf_topic_terms:
            vals = ""
            radius = 0
            topiclabel = "Topic %d" % (topic + 1)

            classification_dict = {'Positive':0, 'Neutral':0, 'Negative':0}
            kwargs = {'classifier':classifier, 'xapistatement__course_code': course_code, 'xapistatement__id__in':nmf_topic_doc_ids[topic]}
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

def get_wordcloud(platform, course_code, username=None, start_date=None, end_date=None):
    #print "get_wordcloud", platform, course_code
    docs = None
    ids = None
    documents = None
    if username is not None:
        docs,ids = get_allcontent_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date)
    else:
        docs,ids = get_allcontent_byplatform(platform, course_code, start_date=start_date, end_date=end_date)

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
    #print sql
    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    node_dict = {}
    count = 1
    for row in result:
        node_dict[row[0]] = count
        count += 1
    #print "node_dict", node_dict
    return node_dict

def get_relationships_byplatform(platform, course_code, username=None, start_date=None, end_date=None, relationshipstoinclude=None):
    platformclause = ""
    if platform != "all":
        platformclause = " AND clatoolkit_socialrelationship.platform='%s'" % (platform)

    userclause = ""
    if username is not None:
        userclause = " AND (clatoolkit_socialrelationship.fromusername='%s' OR clatoolkit_socialrelationship.tousername='%s')" % (username,username)

    dateclause = ""
    if start_date is not None:
        dateclause = " AND clatoolkit_socialrelationship.datetimestamp BETWEEN '%s' AND '%s'" % (start_date, end_date)

    relationshipclause = ""
    if relationshipstoinclude is not None and relationshipstoinclude!='-':
        relationshipclause = " AND clatoolkit_socialrelationship.verb IN (%s) " % (relationshipstoinclude)
    else:
        relationshipclause = " AND clatoolkit_socialrelationship.verb NOT IN ('mentioned','shared','liked','commented') "

    count = 1
    nodes_in_sna_dict = {}

    sql = """
            SELECT clatoolkit_socialrelationship.fromusername, clatoolkit_socialrelationship.tousername, clatoolkit_socialrelationship.verb, clatoolkit_socialrelationship.platform
            FROM   clatoolkit_socialrelationship
            WHERE  clatoolkit_socialrelationship.course_code='%s' %s %s %s %s
          """ % (course_code, platformclause, userclause, dateclause, relationshipclause)
    #print sql
    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()

    edge_dict = defaultdict(int)
    mention_dict = defaultdict(int)
    comment_dict = defaultdict(int)
    share_dict = defaultdict(int)
    for row in result:
        display_username = row[0]
        verb = row[2]
        display_related_username = row[1]
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

def sna_buildjson(platform, course_code, username=None, start_date=None, end_date=None, relationshipstoinclude=None):

    node_dict = None
    edge_dict = None
    nodes_in_sna_dict = None
    if username is not None:
        node_dict = get_nodes_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date)
        edge_dict, nodes_in_sna_dict, mention_dict, share_dict, comment_dict = get_relationships_byplatform(platform, course_code, username=username, start_date=start_date, end_date=end_date, relationshipstoinclude=relationshipstoinclude)
    else:
        node_dict = get_nodes_byplatform(platform, course_code, start_date=start_date, end_date=end_date)
        edge_dict, nodes_in_sna_dict, mention_dict, share_dict, comment_dict = get_relationships_byplatform(platform, course_code, start_date=start_date, end_date=end_date, relationshipstoinclude=relationshipstoinclude)

    #node_dict.update(nodes_in_sna_dict)
    for key in nodes_in_sna_dict:
        node_dict[key] = 1
    count = 1
    for key in node_dict:
        node_dict[key] = count
        count = count + 1

    #print node_dict, node_dict

    node_type_colours = {'Staff':{'border':'#661A00','fill':'#CC3300'}, 'Student':{'border':'#003D99','fill':'#0066FF'}, 'Visitor':{'border':'black','fill':'white'}}
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
    count = 1
    for node in node_dict:
        #print node
        username = node
        role = get_role_fromusername(node, platform)
        node_border = node_type_colours[role]['border']
        node_fill = node_type_colours[role]['fill']
        #json_str_list.append('{"id": %d, "label": "%s", "color": {"background":"%s", "border":"%s"}, "value": %d},' % (node_dict[node], username, node_fill, node_border, degree[node_dict[node]]))
        json_str_list.append('{"id": %d, "label": "%s", "color": {"background":"%s", "border":"%s"}, "value": %d},' % (node_dict[node], username, node_fill, node_border, node_degree_dict[node]))
        count = count + 1
    json_str_list[len(json_str_list)-1] = json_str_list[len(json_str_list)-1][0:-1]
    json_str_list.append("],")

    # Build edge json

    json_str_list.append('"edges": [')

    idcount = 1;
    for relationshiptype in dict_types:
        for edge_str in dict_types[relationshiptype]:
            edgefrom, edgeto = edge_str.split('__')
            if edgefrom in node_dict and edgeto in node_dict:
                json_str_list.append('{"id": %d, "from": %s, "to": %s, "arrows":{"to":{"scaleFactor":0.4}}, "label":"%s", "color":"%s", "value":%d, "title": "%d" },' % (idcount, node_dict[edgefrom], node_dict[edgeto], relationshiptype, relationship_type_colours[relationshiptype], dict_types[relationshiptype][edge_str], dict_types[relationshiptype][edge_str]))
                idcount += 1
    if json_str_list[len(json_str_list)-1][-1:] == ',':
        json_str_list[len(json_str_list)-1] = json_str_list[len(json_str_list)-1][0:-1]
    json_str_list.append("]}")
    #print ''.join(json_str_list)
    return ''.join(json_str_list)

def sentiment_classifier(course_code):
    # delete all previous classifications
    Classification.objects.filter(classifier='VaderSentiment').delete()
    # get messages
    sm_objs = LearningRecord.objects.filter(course_code=course_code)

    for sm_obj in sm_objs:
        message = sm_obj.message.encode('utf-8', 'replace')
        sentiment = "Neutral"
        vs = vaderSentiment(message)
        #print vs, message
        #print "\n\t" + str(vs)
        if (vs['compound'] > 0):
            sentiment = "Positive"
        elif (vs['compound'] < 0):
            sentiment = "Negative"
        # Save Classification
        classification_obj = Classification(xapistatement=sm_obj,classification=sentiment,classifier='VaderSentiment')
        classification_obj.save()

"""
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
"""

def getCentrality(jsonStr):

    g = _createGraphElements(json.loads(jsonStr))
    #print(g)
    #layout = g.layout("kk")
    #igraph.plot(g, layout=layout)
    dc = OrderedDict({"ids": g.vs["ids"], "label": g.vs["label"]})
    digits = 2
    numOfNodes = g.vcount()
    dc["inDegree"] = _roundNumbers(_normaliseDegree(g.degree(mode="in"), numOfNodes), digits)
    dc["outDegree"] = _roundNumbers(_normaliseDegree(g.degree(mode="out"), numOfNodes), digits)
    dc["totalDegree"] = _roundNumbers(_normaliseDegree(g.degree(), numOfNodes), digits)
    dc["betweenness"] = _roundNumbers(g.betweenness(directed=True), digits)
    dc["inCloseness"] = _roundNumbers(g.closeness(mode="in"), digits)
    dc["outCloseness"] = _roundNumbers(g.closeness(mode="out"), digits)
    dc["totalCloseness"] = _roundNumbers(g.closeness(), digits)
    dc["eigenvector"] = _roundNumbers(g.eigenvector_centrality(directed=True, scale=True), digits)
    dc["density"] = _roundNumber(g.density(loops=True), digits)

    return json.dumps(dc)

def _createGraphElements(jdata):
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

def _roundNumbers(targetArray, digits):
    index = 0
    for num in targetArray:
        targetArray[index] = _roundNumber(num, digits)
        index = index + 1

    return targetArray

def _roundNumber(target, digits):
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
    

