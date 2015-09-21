from __future__ import absolute_import

from clatoolkit.models import UserProfile, LearningRecord
from dataintegration import socialmediabuilder

import json
import requests
from pprint import pprint
import dateutil.parser
import ast
from twython import Twython


### youtube integration ###
from dataintegration.googleLib import *
from dataintegration.models import Video, Comment
import os
from clatoolkit.models import UnitOffering, UserProfile


##############################################
# Extract data from YouTube via APIs
##############################################
def injest_youtube(request, course_code, channelIds, http, course_id):

    loginUserInfo = request.user
    vList = injest_youtube_like(course_code, http, loginUserInfo)
    channelCommList = injest_youtube_comment(course_code, channelIds, http, loginUserInfo, course_id)
    
    ytList = []
    ytList.append(vList)
    ytList.append(channelCommList)
    return ytList


#############################################################
# Extract "like"d videos from YouTube and insert it into DB
#############################################################
def injest_youtube_like(course_code, http, loginUserInfo):
    isFirstTime = True
    nextPageToken = ""
    vList = []
    # The maxResults parameter specifies the maximum number of items that should be returned in the result set.(integer, 1-50)
    maxResultsNum = 50

    while isFirstTime or nextPageToken is not "":
        idVal = "id,snippet"
        myRatingVal = "like"
        service = build('youtube', 'v3', http=http)

        #Call videos API to get videos that user "like"d
        if nextPageToken is not "":
            ret = service.videos().list(
                part = idVal,
                maxResults = maxResultsNum,
                myRating = myRatingVal,
                pageToken = nextPageToken
            ).execute()
        else:
            ret = service.videos().list(
                part = idVal,
                maxResults = maxResultsNum,
                myRating = myRatingVal
            ).execute()

        #Check the number of result
        if ret.get('nextPageToken'):
            nextPageToken = ret['nextPageToken']
        else:
            nextPageToken = ""

        #Loop to get all items
        for item in ret['items']:
            video = Video()
            video.videoId = item['id']

            #Check if the data already exists in DB
            records = LearningRecord.objects.filter(
                platform = STR_PLATFORM_NAME_YOUTUBE, course_code = course_code, 
                platformparentid = video.videoId, username = loginUserInfo.username, verb="liked")
            if(len(records) > 0):
                continue

            video.videoUrl = STR_YT_VIDEO_BASE_URL + item['id']
            #title = item['snippet']['title']
            video.videoTitle = item['snippet']['title']
            #Add video info to the list object
            vList.append(video)

        isFirstTime = False
    
    usr_dict = {'google_account_name': loginUserInfo.userprofile.google_account_name }
    usr_dict['email'] = loginUserInfo.email
    like_name = None
    for video in vList:
        #Insert collected data into DB
        insert_like(usr_dict, video.videoUrl, loginUserInfo.username, like_name, 
                    video.videoTitle, course_code, STR_PLATFORM_NAME_YOUTUBE, STR_PLATFORM_URL_YOUTUBE, 
                    STR_OBJ_TYPE_VIDEO, "", video.videoId)
    
    return vList


def injest_youtube_comment(course_code, channelIds, http, loginUserInfo, course_id):
    
    channelCommList = injest_youtube_commentById(course_code, channelIds, http, loginUserInfo, False, course_id)
    print "Channel ID comment extraction result: " + str(len(channelCommList))

    # Retrieve all video IDs in registered channels, and then retrieve all user's comments in the videos.
    channelIDList = channelIds.split('\r\n')
    videoIds = getAllVideoIDsInChannel(channelIDList, http)
    videoCommList = injest_youtube_commentById(course_code, videoIds, http, loginUserInfo, True, course_id)
    channelCommList.extend(videoCommList)
    print "Video ID comment extraction result: " + str(len(channelCommList))
    return channelCommList


#############################################################
# Extract commented videos from YouTube and insert it into DB
#############################################################
def injest_youtube_commentById(course_code, allIds, http, loginUserInfo, isVideoIdSearch, course_id):
    isFirstTime = True
    nextPageToken = ""
    commList = []

    if not isinstance(allIds, list):
        ids = allIds.split(os.linesep)
    else:
        ids = allIds

    #Get all users in the unit(course)
    usersInUnit = getAllUsersInCourseById(course_id)

    for singleId in ids:
        #Get comments by channel ID
        while isFirstTime or nextPageToken is not "":
            ret = extractCommentsById(singleId, nextPageToken, isVideoIdSearch, http)
            #Check the number of result
            if ret.get('nextPageToken'):
                nextPageToken = ret['nextPageToken']
            else:
                nextPageToken = ""

            # Retrieve comments from API response
            #tempList = getCommentsFromResponse(ret, course_code, 
            #    loginUserInfo.username, loginUserInfo.userprofile.google_account_name, course_id)
            tempList = getCommentsFromResponse(ret, course_code, loginUserInfo.username, usersInUnit)
            commList.extend(tempList)
            isFirstTime = False

        # Initialize the flag for next loop
        isFirstTime = True
        nextPageToken = ""

    #usr_dict = {'google_account_name': loginUserInfo.userprofile.google_account_name }
    #usr_dict['email'] = loginUserInfo.email
    for comment in commList:
        #usr_dict['email'] = loginUserInfo.email
        #comment_from_name = loginUserInfo.username
        userInfo = getUserDetailsDict(comment, usersInUnit)
        usr_dict = {'googleAcName': userInfo['googleAcName'], 'email': userInfo['email']}
        """
        insert_comment(usr_dict, comment.parentId, comment.commId, 
                        comment.text, loginUserInfo.username, comment_from_name, 
                        comment.updatedAt, course_code, STR_PLATFORM_NAME_YOUTUBE, STR_PLATFORM_URL_YOUTUBE, comment.commId, "")
        """
        insert_comment(usr_dict, comment.parentId, comment.commId, 
                        comment.text, userInfo['username'], userInfo['username'], 
                        comment.updatedAt, course_code, STR_PLATFORM_NAME_YOUTUBE, STR_PLATFORM_URL_YOUTUBE, comment.commId, "")
    return commList


def getUserDetailsDict(comment, usersInUnit):
    userInfo = {}
    for user in usersInUnit:
        if user.userprofile is not None and comment.authorDispName == user.userprofile.google_account_name:
            userInfo = {'googleAcName': user.userprofile.google_account_name }
            userInfo['email'] = user.email
            userInfo['username'] = user.username
    return userInfo


##############################################
# Get all video IDs in registered channels
##############################################
def getAllVideoIDsInChannel(channelIds, http):
    ret = []
    isFirstTime = True
    nextPageToken = ""

    #Create youtube API controller
    service = build('youtube', 'v3', http=http)
    idVal = "id"
    resultOrder = "date"
    maxResultsNum = 50

    for cid in channelIds:
        while isFirstTime or nextPageToken is not "":
            if nextPageToken is not "":
                searchRet = service.search().list(
                    part = idVal,
                    maxResults = maxResultsNum,
                    order = resultOrder,
                    channelId = cid,
                    pageToken = nextPageToken
                ).execute()
            else:
                searchRet = service.search().list(
                    part = idVal,
                    maxResults = maxResultsNum,
                    order = resultOrder,
                    channelId = cid
                ).execute()
                
            #When an error occurs
            if searchRet.get('error'):
                print "An error has occured in getAllVideoIDsInChannel() method."
                return ret

            if searchRet.get('nextPageToken'):
                nextPageToken = str(searchRet['nextPageToken'])
            else:
                nextPageToken = ""

            #Loop to get all items
            for item in searchRet['items']:
                #print item['id']
                info = item['id']
                if info.get('videoId'):
                    ret.append(item['id']['videoId'])
                    #print item['id']['videoId']

            isFirstTime = False

        # Initialize the flag for next loop
        isFirstTime = True
        nextPageToken = ""

    return ret


################################################################
# Extract comments by either channel ID or video ID from YouTube
################################################################
def extractCommentsById(singleId, nextPageToken, isVideoIdSearch, http):
    #Create youtube API controller
    service = build('youtube', 'v3', http=http)
    idVal = "id,snippet,replies"
    resultOrder = "time"
    maxResultsNum = 100
    ret = []

    if isVideoIdSearch:
        # Extract data from social media by video ID
        if nextPageToken is not "":
            ret = service.commentThreads().list(
                part = idVal,
                maxResults = maxResultsNum,
                order = resultOrder,
                videoId = singleId,
                pageToken = nextPageToken
            ).execute()
        else:
            ret = service.commentThreads().list(
                part = idVal,
                maxResults = maxResultsNum,
                order = resultOrder,
                videoId = singleId
            ).execute()
    else:
        # Extract data from social media by channel ID
        if nextPageToken is not "":
            ret = service.commentThreads().list(
                part = idVal,
                maxResults = maxResultsNum,
                order = resultOrder,
                channelId = singleId,
                pageToken = nextPageToken
            ).execute()
        else:
            ret = service.commentThreads().list(
                part = idVal,
                maxResults = maxResultsNum,
                order = resultOrder,
                channelId = singleId
            ).execute()

    return ret



#############################################################
# Retrieve comments from YouTube API response
#############################################################
#def getCommentsFromResponse(apiResponse, course_code, userName, googleAcName, course_id):
def getCommentsFromResponse(apiResponse, course_code, userName, usersInUnit):
    commList = []

    #When an error occurs
    if apiResponse.get('error'):
        return commList

    #Loop to get all items
    for item in apiResponse['items']:
        #Check if the comment is already in DB
        records = LearningRecord.objects.filter(
            platform = STR_PLATFORM_NAME_YOUTUBE, course_code = course_code, 
            platformid = item['id'], verb = "commented")
        if(len(records) > 0):
            continue

        author = item['snippet']['topLevelComment']['snippet']['authorDisplayName']
        # Check if the author of the comment is the same as the login user's google account name.
        #if author == googleAcName:
        if matchCommentAuthorName(author, usersInUnit):
            comm = Comment()
            comm.commId = item['id']
            # Top level comment's parent ID is the same as ID
            comm.parentId = item['id']
            comm.authorDispName = author
            comm.isReply = False

            snippet = item['snippet']
            secondSnippet = item['snippet']['topLevelComment']['snippet']
            if secondSnippet.get('textOriginal'):
                comm.text = secondSnippet['textOriginal']
            else:
                comm.text = secondSnippet['textDisplay']

            if snippet.get('videoId'):
                comm.videoId = snippet['videoId']
                comm.videoUrl = STR_YT_VIDEO_BASE_URL + comm.videoId
            if snippet.get('channelId'):
                comm.channelId = snippet['channelId']
                comm.channelUrl = STR_YT_CHANNEL_BASE_URL + comm.channelId

            # Timestamp that the comment was published. 
            # UpdatedAt is the same as publishedAt when the comment isn't updated.
            comm.updatedAt = secondSnippet['updatedAt']
            commList.append(comm)

        #Check if replies exist
        if item.get('replies'):
            for reply in item['replies']['comments']:
                #Check if the comment is already in DB
                records = LearningRecord.objects.filter(
                    platform = STR_PLATFORM_NAME_YOUTUBE, course_code = course_code, 
                    platformid = reply['id'], verb = "commented")
                if(len(records) > 0):
                    continue

                author = reply['snippet']['authorDisplayName']

                # Check if the author of the comment is the same as the login user's google account name.
                #if author == googleAcName:
                if matchCommentAuthorName(author, usersInUnit):
                    replyComm = Comment()
                    replyComm.isReply = True
                    replyComm.commId = reply['id']
                    snippet = reply['snippet']
                    replyComm.authorDispName = snippet['authorDisplayName']
                    replyComm.parentId = snippet['parentId']

                    if snippet.get('textOriginal'):
                        replyComm.text = snippet['textOriginal']
                    else:
                        replyComm.text = snippet['textDisplay']

                    if snippet.get('videoId'):
                        replyComm.videoId = snippet['videoId']
                        replyComm.videoUrl = STR_YT_VIDEO_BASE_URL + replyComm.videoId
                    if snippet.get('channelId'):
                        replyComm.channelId = snippet['channelId']
                        replyComm.channelUrl = STR_YT_CHANNEL_BASE_URL + replyComm.channelId

                    replyComm.updatedAt = snippet['updatedAt']
                    commList.append(replyComm)

    return commList


def getAllUsersInCourseById(course_id):
    unit = UnitOffering.objects.filter(id = course_id).get()
    users = unit.users.all()
    return users

def matchCommentAuthorName(author, usersInUnit):
    for user in usersInUnit:
        if user.userprofile is not None and author == user.userprofile.google_account_name:
            return True

    return False


def injest_twitter(sent_hashtag, course_code):

    #print "sent_hashtag:", sent_hashtag

    # Setup Twitter API Keys
    app_key = ""
    app_secret = ""
    oauth_token = ""
    oauth_token_secret = ""

    twitter = Twython(app_key, app_secret, oauth_token, oauth_token_secret)

    # Add hash to start of hashtag
    # hashtag = '#' + hashtag
    # see https://dev.twitter.com/rest/reference/get/search/tweets for search options
    count = 0
    next_max_id = None
    results = None
    while True:
        try:
            if count==0:
                print "count 0"
                results = twitter.search(q=sent_hashtag,count=100, result_type='mixed')
            else:
                print "count +"
                results = twitter.search(q=sent_hashtag,count=100,max_id=next_max_id, result_type='mixed')
            #print results
            insert_twitter_lrs(results['statuses'], course_code)

            if 'next_results' not in results['search_metadata']:
                    break
            else:
                next_results_url_params    = results['search_metadata']['next_results']
                next_max_id = next_results_url_params.split('max_id=')[1].split('&')[0]
                print next_max_id
            count += 1
        except KeyError:
                # When there are no more pages (['paging']['next']), break from the
                # loop and end the script.
                break


def insert_twitter_lrs(statuses, course_code):
    platform = "Twitter"
    platform_url = "http://www.twitter.com/"
    #print statuses
    for tweet in statuses:
        message = tweet['text']

        timestamp = dateutil.parser.parse(tweet['created_at'])
        username = tweet['user']['screen_name']
        print username, message
        fullname = tweet['user']['name']
        post_id = platform_url + username + '/status/' + str(tweet['id'])
        retweeted = False
        retweeted_id = None
        if 'retweeted_status' in tweet:
            retweeted = True
            retweeted_id = tweet['retweeted_status']['id']
        # get hashtags
        tags = []
        hashtags = tweet['entities']['hashtags']
        for hashtag in hashtags:
            #print hashtag['text']
            tag = hashtag['text']
            tags.append(tag)
        # get @mentions
        mentions = []
        atmentions = tweet['entities']['user_mentions']
        for usermention in atmentions:
            mention = "@" + str(usermention['screen_name'])
            tags.append(mention)

        if twitterusername_exists(username):
            usr_dict = get_userdetails_twitter(username)
            if retweeted:
                insert_share(usr_dict, post_id, retweeted_id, message,username,fullname, timestamp, course_code, platform, platform_url, tags=tags)
            else:
                insert_post(usr_dict, post_id,message,fullname,username, timestamp, course_code, platform, platform_url, tags=tags)

def injest_facebook(data, paging, course_code):
    """
    Sends formatted data to LRS
    1. Parses facebook feed
    2. Uses construct_tincan_statement to format data ready to send for the LRS
    3. Sends to the LRS and Saves to postgres json field
    :param data: Graph API query data
    :param paging: Graph API query paging data: next page (if there is one)
    :param course_code: The unit offering code
    :return:
    """
    while True:
        try:
            insert_facebook_lrs(fb_feed=data, course_code=course_code)
            fb_resp = requests.get(paging['next']).json()
            data = fb_resp['data']
            if 'paging' not in fb_resp:
                break
            else:
                paging = fb_resp['paging']
        except KeyError:
            # When there are no more pages (['paging']['next']), break from the
            # loop and end the script.
            break

def insert_facebook_lrs(fb_feed, course_code):
    """
    1. Parses facebook feed
    2. Uses construct_tincan_statement to format data ready to send for the LRS
    3. Sends to the LRS and Saves to postgres json field
    :param fb_feed: Facebook Feed as dict
    :param course_code: The unit offering code
    :return:
    """
    platform = "Facebook"
    platform_url = "http://www.facebook.com/"
    for pst in fb_feed:
        if 'message' in pst:
            post_type = pst['type']
            created_time = dateutil.parser.parse(pst['created_time'])
            from_uid = pst['from']['id']
            from_name = pst['from']['name']
            post_id = pst['actions'][0]['link']
            message = pst['message']
            if fbid_exists(from_uid):
                usr_dict = get_userdetails(from_uid)
                insert_post(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url)

            if 'likes' in pst:
                for like in pst['likes']['data']:
                    like_uid = like['id']
                    like_name = like['name']

                    if fbid_exists(like_uid):
                        usr_dict = get_userdetails(like_uid)
                        insert_like(usr_dict, post_id, like_uid, like_name, message, course_code, platform, platform_url)

            if 'comments' in pst:
                for comment in pst['comments']['data']:
                    comment_created_time = comment['created_time']
                    comment_from_uid = comment['from']['id']
                    comment_from_name = comment['from']['name']
                    comment_message = comment['message']
                    comment_id = comment['id']
                    if fbid_exists(comment_from_uid):
                        usr_dict = get_userdetails(comment_from_uid)
                        insert_comment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url)

def twitterusername_exists(screen_name):
    tw_id_exists = False
    if UserProfile.objects.filter(twitter_id__iexact=screen_name).count() > 0:
        tw_id_exists = True

    if tw_id_exists == False:
        tmp_user_dict = {'aneesha':'aneesha.bakharia@qut.edu.au','dannmallet':'dg.mallet@qut.edu.au', 'LuptonMandy': 'mandy.lupton@qut.edu.au', 'AndrewResearch':'andrew.gibson@qut.edu.au', 'KirstyKitto': 'kirsty.kitto@qut.edu.au' , 'skdevitt': 'kate.devitt@qut.edu.au' }
        if screen_name in tmp_user_dict:
            tw_id_exists = True
        else:
            tw_id_exists = False
    return tw_id_exists

def get_userdetails_twitter(screen_name):
    usr_dict = {'screen_name':screen_name}
    try:
        usr = UserProfile.objects.filter(twitter_id__iexact=screen_name).get()
    except UserProfile.DoesNotExist:
        usr = None

    if usr is not None:
        usr_dict['email'] = usr.user.email
        #usr_dict['lrs_endpoint'] = usr.ll_endpoint
        #usr_dict['lrs_username'] = usr.ll_username
        #usr_dict['lrs_password'] = usr.ll_password
    else:
        tmp_user_dict = {'aneesha':'aneesha.bakharia@qut.edu.au','dannmallet':'dg.mallet@qut.edu.au', 'LuptonMandy': 'mandy.lupton@qut.edu.au', 'AndrewResearch':'andrew.gibson@qut.edu.au', 'KirstyKitto': 'kirsty.kitto@qut.edu.au' , 'skdevitt': 'kate.devitt@qut.edu.au' }
        if screen_name in tmp_user_dict:
            usr_dict['email'] = tmp_user_dict[screen_name]
        else:
            usr_dict['email'] = 'test@gmail.com'
    return usr_dict

def fbid_exists(fb_id):
    fb_id_exists = False
    if UserProfile.objects.filter(fb_id__iexact=fb_id).count() > 0:
        fb_id_exists = True

    if fb_id_exists == False:
        tmp_user_dict = {10152850610457657:'kate.devitt@qut.edu.au',10153944872937892:'aneesha.bakharia@qut.edu.au', 10153189868088612: 'mandy.lupton@qut.edu.au', 856974831053214:'andrew.gibson@qut.edu.au'}
        if fb_id in tmp_user_dict:
            fb_id_exists = True
        else:
            fb_id_exists = False
    return fb_id_exists

def get_userdetails(fb_id):
    usr_dict = {'fb_id':fb_id}
    try:
        usr = UserProfile.objects.filter(fb_id__iexact=fb_id).get()
    except UserProfile.DoesNotExist:
        usr = None

    if usr is not None:
        usr_dict['email'] = usr.user.email
        #usr_dict['lrs_endpoint'] = usr.ll_endpoint
        #usr_dict['lrs_username'] = usr.ll_username
        #usr_dict['lrs_password'] = usr.ll_password
    else:
        tmp_user_dict = {10152850610457657:'kate.devitt@qut.edu.au',10153944872937892:'aneesha.bakharia@qut.edu.au', 10153189868088612: 'mandy.lupton@qut.edu.au', 856974831053214:'andrew.gibson@qut.edu.au'}
        if fb_id in tmp_user_dict:
            usr_dict['email'] = tmp_user_dict[fb_id]
        else:
            usr_dict['email'] = 'test@gmail.com'
    return usr_dict

def insert_post(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url, tags=[]):
    stm = socialmediabuilder.socialmedia_builder(verb='created', platform=platform, account_name=from_uid, account_homepage=platform_url, object_type='Note', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_name, course_code=course_code, tags=tags)
    jsn = ast.literal_eval(stm.to_json())
    stm_json = socialmediabuilder.pretty_print_json(jsn)
    lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=from_uid)
    lrs.save()

def insert_like(usr_dict, post_id, like_uid, like_name, message, course_code, platform, platform_url, obj_type, platformID, platformParentID):
    #stm = socialmediabuilder.socialmedia_builder(verb='liked', platform=platform, account_name=like_uid, account_homepage=platform_url, object_type='Note', object_id='post_id', message=message, account_email=usr_dict['email'], user_name=like_name, course_code=course_code)
    stm = socialmediabuilder.socialmedia_builder(verb='liked', platform=platform, account_name=like_uid, account_homepage=platform_url, object_type=obj_type, object_id='post_id', message=message, account_email=usr_dict['email'], user_name=like_name, course_code=course_code)
    jsn = ast.literal_eval(stm.to_json())
    stm_json = socialmediabuilder.pretty_print_json(jsn)
    lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='liked', platform=platform, username=like_uid, platformid=platformID, platformparentid=platformParentID)
    lrs.save()

def insert_comment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, platformID, platformParentID):
    stm = socialmediabuilder.socialmedia_builder(verb='commented', platform=platform, account_name=comment_from_uid, account_homepage=platform_url, object_type='Note', object_id=comment_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code )
    jsn = ast.literal_eval(stm.to_json())
    stm_json = socialmediabuilder.pretty_print_json(jsn)
    #lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='commented', platform=platform, username=comment_from_uid)
    lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='commented', platform=platform, username=comment_from_uid, platformid=platformID, platformparentid=platformParentID)
    lrs.save()
    
def insert_share(usr_dict, post_id, share_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, tags=[]):
    stm = socialmediabuilder.socialmedia_builder(verb='shared', platform=platform, account_name=comment_from_uid, account_homepage=platform_url, object_type='Note', object_id=share_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code, tags=tags )
    jsn = ast.literal_eval(stm.to_json())
    stm_json = socialmediabuilder.pretty_print_json(jsn)
    lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='shared', platform=platform, username=comment_from_uid)
    lrs.save()
