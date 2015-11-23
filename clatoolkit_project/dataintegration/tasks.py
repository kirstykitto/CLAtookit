from __future__ import absolute_import

from clatoolkit.models import UserProfile, LearningRecord, UnitOffering
from dataintegration import socialmediabuilder
from django.db import connections

import json
import requests
from pprint import pprint
import dateutil.parser
import ast
from twython import Twython
import json
from bs4 import BeautifulSoup
from urllib2 import urlopen
from django.db import connection
from dashboard.utils import *

### youtube integration ###
from dataintegration.googleLib import *
from dataintegration.models import Video, Comment
import os
from clatoolkit.models import UnitOffering, UserProfile


##############################################
# Extract data from YouTube via APIs
##############################################
def injest_youtube(request, course_code, channelIds, http, course_id):
    #print course_code,course_id
    #ytList = injest_youtubeData(request, course_code, channelIds, http)

    loginUserInfo = request.user
    #youtube_getpersonalchannel(course_code, http, loginUserInfo)
    #vList = injest_youtube_like(course_code, http, loginUserInfo)
    vList = []
    channelCommList = injest_youtube_comment(course_code, channelIds, http, loginUserInfo, course_id)

    #channelCommList = injest_youtube_comment(course_code, channelIds, http, loginUserInfo, False)
    # Retrieve all video IDs in registered channels, and then retrieve all user's comments in the videos.
    #channelIDList = channelIds.split('\r\n')
    #videoIds = getAllVideoIDsInChannel(channelIDList, http)
    #videoCommList = injest_youtube_comment(course_code, videoIds, http, loginUserInfo, True)
    #channelCommList.extend(videoCommList)

    ytList = []
    ytList.append(vList)
    ytList.append(channelCommList)
    return ytList


#############################################################
# Get Logged in users personal channel
#############################################################
def youtube_getpersonalchannel(request, course_code, channelIds, http, course_id):
    #print course_code,course_id
    #ytList = injest_youtubeData(request, course_code, channelIds, http)

    loginUserInfo = request.user
    #print "youtube_getpersonalchannel"
    service = build('youtube', 'v3', http=http)

    ret = service.channels().list(
                part = 'contentDetails',
                mine = True
                ).execute()
    #print ret
    return ret['items'][0]['id']

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
    #Don't think this code above works had to write another method to get the comment thread from a channel

    # Retrieve all video IDs in registered channels, and then retrieve all user's comments in the videos.
    channelIDList = channelIds.split('\r\n')
    videoIds,playlists = getAllVideoIDsInChannel(channelIDList, http)
    vidsinplaylist = getAllVideoIDsInPlaylist(playlists, http)
    videoIds.extend(vidsinplaylist)
    #channelcommentthreads = getChannelCommentThreads(channelIDList, http)
    videoCommList = injest_youtube_commentById(course_code, videoIds, http, loginUserInfo, True, course_id)
    channelCommList.extend(videoCommList)
    print "Video ID comment extraction result: " + str(len(channelCommList))
    return channelCommList


#############################################################
# Extract commented videos from YouTube and insert it into DB
#############################################################
def injest_youtube_commentById(course_code, allIds, http, loginUserInfo, isVideoIdSearch, course_id):
    print loginUserInfo
    isFirstTime = True
    nextPageToken = ""
    commList = []
    id_creator_dict = None

    if not isinstance(allIds, list):
        ids = allIds.split(os.linesep)
    else:
        ids = allIds

    #Get all users in the unit(course)
    usersInUnit = getAllUsersInCourseById(course_code) #course_id

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
            tempList, id_creator_dict = getCommentsFromResponse(ret, course_code, loginUserInfo.username, usersInUnit)
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
        print comment
        #print comment.authorChannelUrl, comment.authorDisplayName
        userInfo = getUserDetailsByGoogleAccount(comment.authorDispName, usersInUnit)
        usr_dict = {'googleAcName': userInfo['googleAcName'], 'email': userInfo['email']}
        """
        insert_comment(usr_dict, comment.parentId, comment.commId,
                        comment.text, loginUserInfo.username, comment_from_name,
                        comment.updatedAt, course_code, STR_PLATFORM_NAME_YOUTUBE, STR_PLATFORM_URL_YOUTUBE, comment.commId, "")
        """
        parentusername = "-"
        if comment.commId in id_creator_dict:
            parentusername = id_creator_dict[comment.commId]
        insert_comment(usr_dict, comment.parentId, comment.commId,
                        comment.text, userInfo['googleAcName'], userInfo['username'],
                        comment.updatedAt, course_code, STR_PLATFORM_NAME_YOUTUBE, STR_PLATFORM_URL_YOUTUBE, parentusername)

    return commList

def getUserDetailsByGoogleAccount(authorName, usersInUnit):
    userInfo = {'googleAcName': "Unknown User" }
    userInfo['email'] = "unknown"
    userInfo['username'] = "Unknown"
    for user in usersInUnit:
        if user.userprofile is not None and authorName == user.userprofile.google_account_name:
            userInfo = {'googleAcName': user.userprofile.google_account_name }
            userInfo['email'] = user.email
            userInfo['username'] = user.username
    return userInfo


##############################################
# Get all video IDs in registered channels
##############################################
def getAllVideoIDsInChannel(channelIds, http):
    ret = []
    playlists = []
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
                #print "Video Ids"
                print item['id']
                info = item['id']
                if info.get('videoId'):
                    ret.append(item['id']['videoId'])
                    #print item['id']['videoId']
                elif info.get('kind')=='youtube#playlist':
                    playlists.append(info.get('playlistId'))

            isFirstTime = False

        # Initialize the flag for next loop
        isFirstTime = True
        nextPageToken = ""

    return ret,playlists


###################################################################################
# Get comment threads directly linked to a channel (i.e., under the discussion tab)
###################################################################################
def getChannelCommentThreads(channelIds, http):
    ret = []
    isFirstTime = True
    nextPageToken = ""

    #Create youtube API controller
    service = build('youtube', 'v3', http=http)
    idVal = "id"
    resultOrder = "time"
    maxResultsNum = 50

    for cid in channelIds:
        while isFirstTime or nextPageToken is not "":
            if nextPageToken is not "":
                searchRet = service.commentThreads().list(
                    part = idVal,
                    maxResults = maxResultsNum,
                    order = resultOrder,
                    channelId = cid,
                    pageToken = nextPageToken
                ).execute()
            else:
                searchRet = service.commentThreads().list(
                    part = idVal,
                    maxResults = maxResultsNum,
                    order = resultOrder,
                    channelId = cid
                ).execute()

            #When an error occurs
            if searchRet.get('error'):
                print "An error has occured in getChannelCommentThreads() method."
                return ret

            if searchRet.get('nextPageToken'):
                nextPageToken = str(searchRet['nextPageToken'])
            else:
                nextPageToken = ""

            #Loop to get all items
            for item in searchRet['items']:
                #print "Video Ids"
                print item['id']
                if item['id']:
                    ret.append(item['id'])

            isFirstTime = False

        # Initialize the flag for next loop
        isFirstTime = True
        nextPageToken = ""

    return ret


##############################################
# Get all video IDs from a playlist
##############################################
def getAllVideoIDsInPlaylist(playlistids, http):
    print "getAllVideoIDsInPlaylist called"
    ret = []
    isFirstTime = True
    nextPageToken = ""

    #Create youtube API controller
    service = build('youtube', 'v3', http=http)
    maxResultsNum = 50

    for cid in playlistids:
        while isFirstTime or nextPageToken is not "":
            if nextPageToken is not "":
                searchRet = service.playlistItems().list(
                    part = 'contentDetails',
                    maxResults = maxResultsNum,
                    playlistId = cid,
                    pageToken = nextPageToken
                ).execute()
            else:
                searchRet = service.playlistItems().list(
                    part = 'contentDetails',
                    maxResults = maxResultsNum,
                    playlistId = cid
                ).execute()

            #When an error occurs
            if searchRet.get('error'):
                print "An error has occured in getAllVideoIDsInPlaylist() method."
                return ret

            if searchRet.get('nextPageToken'):
                nextPageToken = str(searchRet['nextPageToken'])
            else:
                nextPageToken = ""

            #Loop to get all items
            for item in searchRet['items']:
                #print "Video Ids"
                print "vid in playlist", item['contentDetails']['videoId']
                if item['contentDetails']['videoId']:
                    ret.append(item['contentDetails']['videoId'])

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
    '''
    if isVideoIdSearch == False:
        print "channel comment", ret
    '''
    return ret



#############################################################
# Retrieve comments from YouTube API response
#############################################################
#def getCommentsFromResponse(apiResponse, course_code, userName, googleAcName, course_id):
def getCommentsFromResponse(apiResponse, course_code, userName, usersInUnit):
    commList = []
    id_creator_dict = {}

    #When an error occurs
    if apiResponse.get('error'):
        return commList

    #Loop to get all items
    for item in apiResponse['items']:
        #Check if the comment is already in DB
        print item
        records = LearningRecord.objects.filter(
            platform = STR_PLATFORM_NAME_YOUTUBE, course_code = course_code,
            platformid = item['id'], verb = "commented")
        if(len(records) > 0):
            continue

        author = item['snippet']['topLevelComment']['snippet']['authorDisplayName']
        authorChannelUrl = item['snippet']['topLevelComment']['snippet']['authorChannelUrl']
        print author, authorChannelUrl
        # Check if the author of the comment is the same as the login user's google account name.
        #if author == googleAcName:
        if matchCommentAuthorName(authorChannelUrl, usersInUnit):
            comm = Comment()
            comm.commId = item['id']
            # Top level comment's parent ID is the same as ID
            comm.parentId = item['id']
            comm.authorDispName = authorChannelUrl #author
            #comm.parentUsername = authorChannelUrl
            #comm.authorChannelUrl = authorChannelUrl
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
            id_creator_dict[item['id']] = authorChannelUrl

        #Check if replies exist
        if item.get('replies'):
            for reply in item['replies']['comments']:
                #Check if the comment is already in DB
                records = LearningRecord.objects.filter(
                    platform = STR_PLATFORM_NAME_YOUTUBE, course_code = course_code,
                    platformid = reply['id'], username = userName, verb = "commented")
                if(len(records) > 0):
                    continue

                author = reply['snippet']['authorDisplayName']
                authorChannelUrl = reply['snippet']['authorChannelUrl']
                # Check if the author of the comment is the same as the login user's google account name.
                #if author == googleAcName:
                if matchCommentAuthorName(authorChannelUrl, usersInUnit):
                    replyComm = Comment()
                    replyComm.isReply = True
                    replyComm.commId = reply['id']
                    snippet = reply['snippet']
                    replyComm.authorDispName = snippet['authorChannelUrl'] #snippet['authorDisplayName']
                    id_creator_dict[reply['id']] = snippet['authorChannelUrl']
                    #replyComm.authorDispName = snippet['authorDisplayName']
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

    return commList,id_creator_dict


def getAllUsersInCourseById(course_code):
    unit = UnitOffering.objects.filter(code = course_code).get()
    users = unit.users.all()
    return users

def matchCommentAuthorName(author, usersInUnit):
    for user in usersInUnit:
        if user.userprofile is not None and author == user.userprofile.google_account_name:
            return True

    return False


#############################################################
# End Youtube Integration
#############################################################


def injest_twitter(sent_hashtag, course_code):
    get_oldtweets(course_code, sent_hashtag)
    #print "sent_hashtag:", sent_hashtag

    # Setup Twitter API Keys
    app_key = "barKrgroD3LcyHRwehvaiv1Zu"
    app_secret = "v6awGTCTP6wNJNhMPzmUzuIi1bAfNuoFOuPq1LXoCNjyqOIUki"
    oauth_token = "1851621-4eTSnqZehoeVBWqUxGERiPKjnTsVEFaJ77MnTWKRfo"
    oauth_token_secret = "4ZoEKJ9hnbviCuFtfGq2hBdCsfuX6eyqvvkbFGEeytE0U"

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

def insert_tweet(tweet, course_code):
    platform = "Twitter"
    platform_url = "http://www.twitter.com/"
    message = tweet['text']
    #print message
    timestamp = dateutil.parser.parse(tweet['created_at'])
    username = tweet['user']['screen_name']
    #print username, message
    fullname = tweet['user']['name']
    post_id = platform_url + username + '/status/' + str(tweet['id'])
    retweeted = False
    retweeted_id = None
    retweeted_username = None
    if 'retweeted_status' in tweet:
        retweeted = True
        #print tweet['retweeted_status']
        retweeted_id = platform_url + username + '/status/' + str(tweet['retweeted_status']['id'])
        retweeted_username = tweet['retweeted_status']['user']['screen_name']
        # get hashtags
    tags = []
    hashtags = tweet['entities']['hashtags']
    for hashtag in hashtags:
        #print hashtag['text']
        tag = hashtag['text']
        tags.append(tag)
    # get @mentions
    # favorite_count
    mentions = []
    atmentions = tweet['entities']['user_mentions']
    for usermention in atmentions:
        mention = "@" + str(usermention['screen_name'])
        tags.append(mention)
    #print post_id
    print twitterusername_exists(username, course_code)
    if twitterusername_exists(username, course_code):
        usr_dict = get_userdetails_twitter(username)
        if retweeted:
            insert_share(usr_dict, post_id, retweeted_id, message,username,fullname, timestamp, course_code, platform, platform_url, tags=tags, shared_username=retweeted_username)
        else:
            print post_id
            insert_post(usr_dict, post_id,message,fullname,username, timestamp, course_code, platform, platform_url, tags=tags)

def insert_twitter_lrs(statuses, course_code):
    #print statuses
    for tweet in statuses:
        insert_tweet(tweet, course_code)

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
            if fbid_exists(from_uid, course_code):
                usr_dict = get_userdetails(from_uid)
                insert_post(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url)

            if 'likes' in pst:
                for like in pst['likes']['data']:
                    like_uid = like['id']
                    like_name = like['name']

                    if fbid_exists(like_uid, course_code):
                        usr_dict = get_userdetails(like_uid)
                        insert_like(usr_dict, post_id, like_uid, like_name, message, course_code, platform, platform_url, liked_username=from_uid)

            if 'comments' in pst:
                for comment in pst['comments']['data']:
                    comment_created_time = comment['created_time']
                    comment_from_uid = comment['from']['id']
                    comment_from_name = comment['from']['name']
                    comment_message = comment['message']
                    comment_id = comment['id']
                    if fbid_exists(comment_from_uid, course_code):
                        usr_dict = get_userdetails(comment_from_uid)
                        insert_comment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, parentusername=from_uid)

def twitterusername_exists(screen_name, course_code):
    tw_id_exists = False
    usrs = UserProfile.objects.filter(twitter_id__iexact=screen_name)
    #print usrs
    if len(usrs) > 0:
        usr_prof = usrs[0]
        usr = usr_prof.user
        user_in_course = check_ifuserincourse(usr, course_code)
        if user_in_course:
            tw_id_exists = True
        else:
            tw_id_exists = False
    return tw_id_exists

def check_ifuserincourse(user, course_id):
    print "check_ifuserincourse", UnitOffering.objects.filter(code=course_id, users=user)
    if UnitOffering.objects.filter(code=course_id, users=user).count() > 0:
        return True
    else:
        return False

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

def fbid_exists(fb_id, course_code):
    fb_id_exists = False
    usrs = UserProfile.objects.filter(fb_id__iexact=fb_id)
    if len(usrs) > 0:
        usr_prof = usrs[0]
        usr = usr_prof.user
        user_in_course = check_ifuserincourse(usr, course_code)
        if user_in_course:
            fb_id_exists = True
        else:
            fb_id_exists = False
    return fb_id_exists

def forumid_exists(forum_id, course_code):
    forumid_exists = False
    usrs = UserProfile.objects.filter(forum_id__iexact=forum_id)
    print "forumid_exists", usrs
    if len(usrs) > 0:
        usr_prof = usrs[0]
        usr = usr_prof.user
        print "forumid_exists_user", usr
        user_in_course = check_ifuserincourse(usr, course_code)
        if user_in_course:
            forumid_exists = True
        else:
            forumid_exists = False
    return forumid_exists

def get_userdetails_forum(screen_name):
    usr_dict = {'screen_name':screen_name}
    try:
        usr = UserProfile.objects.filter(forum_id__iexact=screen_name).get()
    except UserProfile.DoesNotExist:
        usr = None

    if usr is not None:
        usr_dict['email'] = usr.user.email
        #usr_dict['lrs_endpoint'] = usr.ll_endpoint
        #usr_dict['lrs_username'] = usr.ll_username
        #usr_dict['lrs_password'] = usr.ll_password
    else:
            usr_dict['email'] = 'test@gmail.com'
    return usr_dict

'''
Forum Scraper Code
'''

def make_soup(url):
    html = urlopen(url).read()
    return BeautifulSoup(html, "lxml")

def get_forumlinks(url):
    forums = []

    soup = make_soup(url)
    forum_containers = soup.findAll("ul", "forum")
    for forum_item in forum_containers:
        forum_link = forum_item.find("a", "bbp-forum-title").attrs['href']
        forum_title = forum_item.find("a", "bbp-forum-title").string
        forum_text = forum_item.find("div", "bbp-forum-content").string
        if forum_text is None:
            forum_text = ""
        forum_user = "admin"
        forum_dict = {'forum_link': forum_link, 'forum_title': forum_title, 'forum_text': forum_text }
        forums.append(forum_dict)
        #print forums

    return forums

def get_topiclinks(url):
    topics = []

    soup = make_soup(url)
    topic_containers = soup.findAll("ul", "topic")
    for topic_item in topic_containers:
        topic_link = topic_item.find("a", "bbp-topic-permalink").attrs['href']
        topic_title = topic_item.find("a", "bbp-topic-permalink").string
        topic_author = topic_item.find("a", "bbp-author-avatar").attrs['href']
        #print topic_title, topic_link, topic_author[0:-1]
        topic_dict = {'topic_link': topic_link, 'topic_title': topic_title, 'topic_author': topic_author }
        topics.append(topic_dict)

    return topics

def get_posts(topic_url):
    posts = []

    soup = make_soup(topic_url)

    posts_container = soup.findAll("ul", "forums")

    post_containers = posts_container[0].findAll("li")
    for post in post_containers:
        if post.find("span", "bbp-reply-post-date") is not None:
            post_date = post.find("span", "bbp-reply-post-date").string
            post_permalink = post.find("a", "bbp-reply-permalink").attrs['href']
            post_user_link = post.find("a", "bbp-author-avatar").attrs['href']
            post_content = str(post.find("div", "bbp-reply-content"))
            #post_content = message.decode('utf-8').encode('ascii', 'ignore') #post_content.replace(u"\u2018", "'").replace(u"\u2019", "'").replace(u"\u2013", "-").replace(u"\ud83d", " ").replace(u"\ude09", " ").replace(u"\u00a0l", " ").replace(u"\ud83d", " ").replace(u"\u2026", " ").replace(u"\ude09", " ").replace(u"\u00a0"," ")

            #print "post_content_div", post_content
            #post_content = post_content_div.renderContents() #post_content_div.string #post_content_div.find("p").string
            #print "renderContents", post_content.renderContents()
            post_dict = {'post_permalink': post_permalink, 'post_user_link': post_user_link, 'post_date': post_date, 'post_content': post_content }
            posts.append(post_dict)

    return posts

def ingest_forum(url, course_code):
    url = "http://2015.informationprograms.info/forums/"
    platform = "Forum"

    forums  = get_forumlinks(url)
    for forum in forums:
        forum_link = forum["forum_link"]
        forum_title = forum["forum_link"]
        forum_text = forum["forum_link"]
        forum_author = "admin"
        #forum_authorlink =
        # insert forum in xapi
        #print forum_author, forumid_exists(forum_author, course_code)
        if forumid_exists(forum_author, course_code):
            usr_dict = get_userdetails_forum(forum_author)
            insert_post(usr_dict, forum_link,forum_text,forum_author,forum_author, dateutil.parser.parse("1 July 2015 2pm"), course_code, platform, url)
            #print "insert_post"

        topics = get_topiclinks(forum_link)
        for topic in topics:
            topic_link = topic["topic_link"]

            posts = get_posts(topic_link)
            for post in posts:
                post_permalink = post["post_permalink"]
                post_user_link = post["post_user_link"]
                post_date = post["post_date"]
                post_date = dateutil.parser.parse(post_date.replace(" at "," "))
                post_content = post["post_content"]
                post_user_link = post_user_link[:-1]
                post_username = post_user_link[(post_user_link.rfind('/')+1):]
                # insert each post in xapi
                #print post_user_link, post_user_link.rfind('/'), post_username, post_date
                if forumid_exists(post_username, course_code):
                    usr_dict = get_userdetails_forum(post_username)
                    print post_permalink, post_content, post_user_link, post_date
                    insert_comment(usr_dict, forum_link, post_permalink, post_content, post_username, post_username, post_date, course_code, platform, url, shared_username=forum_author)
                    print "insert_comment"

'''

End Forum Scraper Code
'''

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

    return usr_dict

def get_oldtweets(course_code,hashtag):
    cursor = connections['tweetimport'].cursor()
    sql = "SELECT tweet FROM tweets WHERE hashtag='%s';" %(hashtag)
    #print sql
    row_count = cursor.execute(sql);
    result = cursor.fetchall()
    for row in result:
        insert_tweet(json.loads(row[0]), course_code)

def check_ifnotinlocallrs(course_code, platform, platform_id):
    lrs_matchingstatements = LearningRecord.objects.filter(course_code=course_code, platform=platform, platformid=platform_id)
    print lrs_matchingstatements
    if len(lrs_matchingstatements)==0:
        return True
    else:
        return False

def insert_post(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmediabuilder.socialmedia_builder(verb='created', platform=platform, account_name=from_uid, account_homepage=platform_url, object_type='Note', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_name, course_code=course_code, tags=tags)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = socialmediabuilder.pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=get_username_fromsmid(from_uid, platform), platformid=post_id, message=message, datetimestamp=created_time)
        lrs.save()
        for tag in tags:
            if tag[0]=="@":
                socialrelationship = SocialRelationship(verb = "mentioned", fromusername=get_username_fromsmid(from_uid,platform), tousername=get_username_fromsmid(tag[1:],platform), platform=platform, message=message, datetimestamp=created_time, course_code=course_code, platformid=post_id)
                socialrelationship.save()

def insert_like(usr_dict, post_id, like_uid, like_name, message, course_code, platform, platform_url, liked_username=None):
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmediabuilder.socialmedia_builder(verb='liked', platform=platform, account_name=like_uid, account_homepage=platform_url, object_type='Note', object_id=post_id, message=message, account_email=usr_dict['email'], user_name=like_name, course_code=course_code)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = socialmediabuilder.pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='liked', platform=platform, username=get_username_fromsmid(like_uid, platform), platformid=post_id, message=message, platformparentid=post_id, parentusername=get_username_fromsmid(liked_username,platform), datetimestamp=created_time)
        lrs.save()
        socialrelationship = SocialRelationship(verb = "liked", fromusername=get_username_fromsmid(like_uid,platform), tousername=get_username_fromsmid(liked_username,platform), platform=platform, message=message, datetimestamp=created_time, course_code=course_code, platformid=post_id)
        socialrelationship.save()

def insert_comment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, shared_username=None):
    if check_ifnotinlocallrs(course_code, platform, comment_id):
        stm = socialmediabuilder.socialmedia_builder(verb='commented', platform=platform, account_name=comment_from_uid, account_homepage=platform_url, object_type='Note', object_id=comment_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code )
        jsn = ast.literal_eval(stm.to_json())
        stm_json = socialmediabuilder.pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='commented', platform=platform, username=get_username_fromsmid(comment_from_uid, platform), platformid=comment_id, platformparentid=post_id, parentusername=get_username_fromsmid(shared_username,platform), message=comment_message, datetimestamp=comment_created_time)
        lrs.save()
        socialrelationship = SocialRelationship(verb = "commented", fromusername=get_username_fromsmid(comment_from_uid,platform), tousername=get_username_fromsmid(shared_username,platform), platform=platform, message=comment_message, datetimestamp=comment_created_time, course_code=course_code, platformid=comment_id)
        socialrelationship.save()

def insert_share(usr_dict, post_id, share_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, tags=[], shared_username=None):
    if check_ifnotinlocallrs(course_code, platform, share_id):
        stm = socialmediabuilder.socialmedia_builder(verb='shared', platform=platform, account_name=comment_from_uid, account_homepage=platform_url, object_type='Note', object_id=share_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code, tags=tags )
        jsn = ast.literal_eval(stm.to_json())
        stm_json = socialmediabuilder.pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='shared', platform=platform, username=get_username_fromsmid(comment_from_uid, platform), platformid=share_id, platformparentid=post_id, parentusername=get_username_fromsmid(shared_username,platform), message=comment_message, datetimestamp=comment_created_time)
        lrs.save()
        socialrelationship = SocialRelationship(verb = "shared", fromusername=get_username_fromsmid(comment_from_uid,platform), tousername=get_username_fromsmid(shared_username,platform), platform=platform, message=comment_message, datetimestamp=comment_created_time, course_code=course_code, platformid=share_id)
        socialrelationship.save()

def updateLRS():

    # for each unit that is enabled
    units = UnitOffering.objects.filter(enabled=True)

    # get all xapi statements for course
    for unit in units:
        ll_endpoint = unit.ll_endpoint
        ll_username = unit.ll_username
        ll_password = unit.ll_password
        unit_code = unit.code
        #extract xapi data
        cursor = connection.cursor()
        cursor.execute("""SELECT clatoolkit_learningrecord.verb, clatoolkit_learningrecord.platform, clatoolkit_learningrecord.username, clatoolkit_learningrecord.platformid, clatoolkit_learningrecord.platformparentid, clatoolkit_learningrecord.parentusername, clatoolkit_learningrecord.xapi->'object'->'definition'->'name'->>'en-US', clatoolkit_learningrecord.xapi->>'timestamp', obj
                          FROM clatoolkit_learningrecord, json_array_elements(clatoolkit_learningrecord.xapi->'context'->'contextActivities'->'other') obj
                          WHERE clatoolkit_learningrecord.course_code='%s';
                       """ % (unit_code))
        result = cursor.fetchall()
        # submit to LRS
        for stm in result:
            #construct xapi statement
            verb = stm[0]
            platform = stm[1]
            platformusername = stm[2]
            platformid = stm[3]
            parentid = stm[4]
            parentusername = stm[5]
            message = stm[6]
            timestamp = stm[7]
            context_dict = stm[8]
            atmentions = []
            hashtags = []
            #print context_dict
            for item in context_dict:
                if item == "definition":
                    context_ref = context_dict[item]["name"]["en-US"]
                    if context_ref[0] == "@":
                        atmentions.append(context_ref)
                    elif context_ref[0] == "#":
                        hashtags.append(context_ref)
            # construct statement using socialmediabuilder
            if platform == "Twitter":
                message = "Refer to object id to retrieve tweet."
            #print verb, platform, platformusername, platformid, message, timestamp
            #print atmentions
            #print hashtags
            userdict = {}
            if platform == "Twitter":
                usr_dict = get_userdetails_twitter(username)
            elif platform == "Facebook":
                usr_dict = get_userdetails(username)
            elif platform == "Forum":
                usr_dict = get_userdetails_forum(username)

            lrs_stm = None
            if verb == "created":
                lrs_stm = socialmediabuilder.socialmedia_builder(verb='created', platform=platform, account_name=username, account_homepage=platform_url, object_type='Note', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_name, course_code=course_code, tags=tags)
            elif verb == "liked":
                lrs_stm = socialmediabuilder.socialmedia_builder(verb='liked', platform=platform, account_name=username, account_homepage=platform_url, object_type='Note', object_id='post_id', message=message, account_email=usr_dict['email'], user_name=like_name, course_code=course_code)
            elif verb == "commented":
                lrs_stm = socialmediabuilder.socialmedia_builder(verb='commented', platform=platform, account_name=username, account_homepage=platform_url, object_type='Note', object_id=comment_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code )
            elif verb == "shared":
                lrs_stm = socialmediabuilder.socialmedia_builder(verb='shared', platform=platform, account_name=username, account_homepage=platform_url, object_type='Note', object_id=share_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code, tags=tags )

            # send xapi statement to LRS

            # if successful update senttolrs flag
            '''
            locallrs = LearningRecord(platformid=post_id)
            locallrs.senttolrs = True
            locallrs.save()
            '''

'''
// Expand all view conversations
$("span.expand-stream-item.js-view-details").click();

tweets = $('div .tweet');
twt_array = [];
console.log(tweets.length)
for (i=0;i<tweets.length;i++)
{
    console.log(i)
    twt = tweets[i];
    twt_id = twt.dataset.itemId;
    console.log(twt_id);
    twt_array.push(twt_id);
}
console.log(twt_array);
twt_array.join(',')
#alert(twt_array)
'''



'''
{u'snippet':
    {u'isPublic': True, u'channelId': u'UCc4dGQLlc3xPLUGcEpSdHyw', u'videoId': u'X_F2F-AwwxY', u'canReply': True,
    u'totalReplyCount': 0, u'topLevelComment':
    {u'snippet':
    {u'authorChannelUrl': u'http://www.youtube.com/channel/UCgWmpb4qnKicxbFqaMoAhnA',
    u'authorDisplayName': u'CLA Toolkit ALASI 2015 Workshop', u'channelId': u'UCc4dGQLlc3xPLUGcEpSdHyw',
    u'videoId': u'X_F2F-AwwxY', u'publishedAt': u'2015-11-03T04:28:01.443Z', u'viewerRating': u'none',
    u'authorChannelId': {u'value': u'UCgWmpb4qnKicxbFqaMoAhnA'}, u'canRate': True, u'likeCount': 0, u'updatedAt': u'2015-11-03T04:28:01.443Z',
    u'authorProfileImageUrl': u'https://lh3.googleusercontent.com/-XdUIqdMkCWA/AAAAAAAAAAI/AAAAAAAAAAA/4252rscbv5M/photo.jpg?sz=50',
    u'authorGoogleplusProfileUrl': u'https://plus.google.com/108930139764469032263',
    u'textDisplay': u'More research into policies is needed\ufeff'}, u'kind': u'youtube#comment',
    u'etag': u'"0KG1mRN7bm3nResDPKHQZpg5-do/FqdG83kr6KoeSAlG_oW7KHh4tvw"',
    u'id': u'z13dxnshpuexwfbie04cf3xp2uebe1ob1o00k'}},
    u'kind': u'youtube#commentThread', u'etag': u'"0KG1mRN7bm3nResDPKHQZpg5-do/n7c50pnIAZOteKEEtKPsrqUFiLc"',
    u'id': u'z13dxnshpuexwfbie04cf3xp2uebe1ob1o00k'}


{u'snippet':
{u'isPublic': True, u'channelId': u'UCc4dGQLlc3xPLUGcEpSdHyw', u'videoId': u'2_Pi96pRRdc', u'canReply': True, u'totalReplyCount': 0,
u'topLevelComment': {u'snippet': {u'authorChannelUrl': u'http://www.youtube.com/channel/UC8dsMVHSb22wRSS_5xR4v9A',
u'authorDisplayName': u'Aneesha Bakharia', u'channelId': u'UCc4dGQLlc3xPLUGcEpSdHyw', u'videoId': u'2_Pi96pRRdc', u'publishedAt': u'2015-10-28T23:02:26.442Z', u'viewerRating': u'none', u'authorChannelId': {u'value': u'UC8dsMVHSb22wRSS_5xR4v9A'}, u'canRate': True, u'likeCount': 0, u'updatedAt': u'2015-10-28T23:02:26.442Z', u'authorProfileImageUrl': u'https://lh3.googleusercontent.com/-XdUIqdMkCWA/AAAAAAAAAAI/AAAAAAAAAAA/4252rscbv5M/photo.jpg?sz=50', u'authorGoogleplusProfileUrl': u'https://plus.google.com/112502824417235079678', u'textDisplay': u'Is there a link for more info on the project?\ufeff'}, u'kind': u'youtube#comment', u'etag': u'"0KG1mRN7bm3nResDPKHQZpg5-do/dvz5o_bYJDU2ZetcSCAGnTJfb9Y"', u'id': u'z13iv3xaqznuuvgon04cdhlh5rimdlmieik'}}, u'kind': u'youtube#commentThread', u'etag': u'"0KG1mRN7bm3nResDPKHQZpg5-do/EgsldZ9y1LxA3L_ZBFdDQySLQiQ"', u'id': u'z13iv3xaqznuuvgon04cdhlh5rimdlmieik'}
'''
