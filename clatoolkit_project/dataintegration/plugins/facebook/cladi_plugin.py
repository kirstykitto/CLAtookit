from dataintegration.core.plugins import registry
from dataintegration.core.plugins.base import DIBasePlugin, DIPluginDashboardMixin, DIAuthomaticPluginMixin
from dataintegration.core.socialmediarecipebuilder import *
from dataintegration.core.recipepermissions import *
import json
import dateutil.parser
from authomatic.providers import oauth2
import requests
import os


class FacebookPlugin(DIBasePlugin, DIPluginDashboardMixin, DIAuthomaticPluginMixin):

    platform = "Facebook"
    platform_url = "http://www.facebook.com/"

    xapi_verbs = ['created', 'shared', 'liked', 'commented']
    xapi_objects = ['Note']

    user_api_association_name = 'Facebook UID' # eg the username for a signed up user that will appear in data extracted via a social API
    unit_api_association_name = 'Group ID' # eg hashtags or a group name

    config_json_keys = ['consumer_key', 'consumer_secret']

    #from DIPluginDashboardMixin
    xapi_objects_to_includein_platformactivitywidget = ['Note']
    xapi_verbs_to_includein_verbactivitywidget = ['created', 'shared', 'liked', 'commented']

    #from AuthomaticPluginMixin
    authomatic_config_json = {}

    authomatic_config_key = 'fb'
    authomatic_secretkey = None

    def __init__(self):
        # Load api_config.json and convert to dict
        config_file = os.path.join(os.path.dirname(__file__), 'api_config.json')
        with open(config_file) as data_file:
            self.api_config_dict = json.load(data_file)

        #from AuthomaticPluginMixin
        self.authomatic_config_json = {
            # Auth information for Facebook App
            'fb': {
                'class_': oauth2.Facebook,
                'consumer_key': self.api_config_dict['consumer_key'],
                'consumer_secret': self.api_config_dict['consumer_secret'],

                'scope': ['user_about_me', 'email', 'user_groups'],
                },
            }

        self.authomatic_config_key = 'fb'

        self.authomatic_secretkey = str(self.api_config_dict['authomatic_secretkey'])

    def perform_import(self, retrieval_param, course_code, authomatic_result):
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

        url = 'https://graph.facebook.com/'+retrieval_param+'/feed'
        access_response = result.provider.access(url)
        data = access_response.data.get('data')
        paging = access_response.data.get('paging')
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

    def insert_facebook_lrs(self, fb_feed, course_code):
        """
        1. Parses facebook feed
        2. Uses construct_tincan_statement to format data ready to send for the LRS
        3. Sends to the LRS and Saves to postgres json field
        :param fb_feed: Facebook Feed as dict
        :param course_code: The unit offering code
        :return:
        """
        for pst in fb_feed:
            if 'message' in pst:
                post_type = pst['type']
                created_time = dateutil.parser.parse(pst['created_time'])
                from_uid = pst['from']['id']
                from_name = pst['from']['name']
                post_id = pst['actions'][0]['link']
                message = pst['message']
                if username_exists(from_uid, course_code, self.platform):
                    usr_dict = get_userdetails(from_uid, self.platform)
                    insert_post(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, self.platform, self.platform_url)

                if 'likes' in pst:
                    for like in pst['likes']['data']:
                        like_uid = like['id']
                        like_name = like['name']

                        if username_exists(like_uid, course_code, self.platform):
                            usr_dict = get_userdetails(like_uid, self.platform)
                            insert_like(usr_dict, post_id, like_uid, like_name, message, course_code, self.platform, self.platform_url, liked_username=from_uid)

                if 'comments' in pst:
                    for comment in pst['comments']['data']:
                        comment_created_time = comment['created_time']
                        comment_from_uid = comment['from']['id']
                        comment_from_name = comment['from']['name']
                        comment_message = comment['message']
                        comment_id = comment['id']
                        if username_exists(comment_from_uid, course_code, self.platform):
                            usr_dict = get_userdetails(comment_from_uid, self.platform)
                            insert_comment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, self.platform, self.platform_url, parentusername=from_uid)

registry.register(FacebookPlugin)

