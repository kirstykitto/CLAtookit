from dataintegration.core.plugins import registry
from dataintegration.core.plugins.base import DIBasePlugin, DIPluginDashboardMixin
#from dataintegration.core.socialmediarecipebuilder import *
#from dataintegration.core.recipepermissions import *

from dataintegration.core.importer import *
from dataintegration.core.di_utils import * #Formerly dataintegration.core.recipepermissions
from xapi.statement.builder import * #Formerly dataintegration.core.socialmediabuilder

import dateutil.parser
from twython import Twython
import os
from xapi.statement.xapi_settings import xapi_settings


class TwitterPlugin(DIBasePlugin, DIPluginDashboardMixin):

    platform = xapi_settings.PLATFORM_TWITTER
    platform_url = "https://twitter.com/"

    xapi_verbs = [xapi_settings.VERB_CREATED, xapi_settings.VERB_SHARED, 
                  xapi_settings.VERB_LIKED, xapi_settings.VERB_COMMENTED]
    xapi_objects = [xapi_settings.OBJECT_NOTE]

    user_api_association_name = 'Twitter Username' # eg the username for a signed up user that will appear in data extracted via a social API
    unit_api_association_name = 'Hashtags' # eg hashtags or a group name

    config_json_keys = ['app_key', 'app_secret', 'oauth_token', 'oauth_token_secret']

    #from DIPluginDashboardMixin
    xapi_objects_to_includein_platformactivitywidget = [xapi_settings.OBJECT_NOTE]
    xapi_verbs_to_includein_verbactivitywidget = [xapi_settings.VERB_CREATED, xapi_settings.VERB_SHARED, 
                                                  xapi_settings.VERB_LIKED, xapi_settings.VERB_COMMENTED]

    def __init__(self):
        pass

    def perform_import(self, retrieval_param, unit):

        # Setup Twitter API Keys
        app_key = os.environ.get("TWITTER_APP_KEY")
        app_secret = os.environ.get("TWITTER_APP_SECRET")
        oauth_token = os.environ.get("TWITTER_OAUTH_TOKEN")
        oauth_token_secret = os.environ.get("TWITTER_OAUTH_TOKEN_SECRET")

        twitter = Twython(app_key, app_secret, oauth_token, oauth_token_secret)

        count = 0
        next_max_id = None
        results = None
        while True:
            try:
                if count == 0:
                    results = twitter.search(q=retrieval_param,count=100, result_type='recent')
                else:
                    results = twitter.search(q=retrieval_param,count=100,max_id=next_max_id, result_type='recent')

                for tweet in results['statuses']:
                    self.insert_tweet(tweet, unit)

                if 'next_results' not in results['search_metadata']:
                        break
                else:
                    next_results_url_params = results['search_metadata']['next_results']
                    next_max_id = next_results_url_params.split('max_id=')[1].split('&')[0]
                count += 1
            except KeyError:
                    # When there are no more pages (['paging']['next']), break from the
                    # loop and end the script.
                    break

    def insert_tweet(self, tweet, unit):
        message = tweet['text']
        timestamp = dateutil.parser.parse(tweet['created_at'])
        username = tweet['user']['screen_name']
        fullname = tweet['user']['name']
        post_id = self.platform_url + username + '/status/' + str(tweet['id'])
        retweeted = False
        retweeted_id = None
        retweeted_username = None
        if 'retweeted_status' in tweet:
            retweeted = True
            retweeted_id = self.platform_url + username + '/status/' + str(tweet['retweeted_status']['id'])
            retweeted_username = tweet['retweeted_status']['user']['screen_name']
            # get hashtags
        tags = []
        hashtags = tweet['entities']['hashtags']
        for hashtag in hashtags:
            tag = hashtag['text']
            tags.append(tag)
        # get @mentions
        # favorite_count
        mentions = []
        atmentions = tweet['entities']['user_mentions']
        for usermention in atmentions:
            mention = "@" + str(usermention['screen_name'])
            tags.append(mention)

        if username_exists(username, unit, self.platform):
            user = get_user_from_screen_name(username, self.platform)
            if retweeted:
                if username_exists(retweeted_username, unit, self.platform):
                    parent_user = get_user_from_screen_name(retweeted_username, self.platform)
                    insert_share(user, post_id, retweeted_id, message, timestamp, unit, self.platform, self.platform_url, tags=tags, parent_user=parent_user)
                else:
                    insert_share(user, post_id, retweeted_id, message, timestamp, unit, self.platform, self.platform_url, tags=tags, parent_external_user=retweeted_username)
            else:
                insert_post(user, post_id, message, timestamp, unit, self.platform, self.platform_url, tags=tags)


    def get_verbs(self):
        return self.xapi_verbs
            
    def get_objects(self):
        return self.xapi_objects


registry.register(TwitterPlugin)