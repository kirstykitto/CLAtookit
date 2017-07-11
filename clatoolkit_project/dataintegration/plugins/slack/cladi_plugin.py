import os
import urllib2
import json
import re
from common.util import Utility
from datetime import datetime
from dataintegration.core.plugins import registry
from dataintegration.core.plugins.base import DIBasePlugin, DIPluginDashboardMixin
from dataintegration.core.importer import *
from dataintegration.core.di_utils import * #Formerly dataintegration.core.recipepermissions
from xapi.statement.builder import * #Formerly dataintegration.core.socialmediabuilder
from xapi.statement.xapi_settings import xapi_settings
from django.contrib.auth.models import User
from slackclient import SlackClient



class SlackPlugin(DIBasePlugin, DIPluginDashboardMixin):

    class XAPIProperty(object):
        message = None
        user = None
        object_id = None
        parent_id = None
        object_type = None
        parent_object_type = None
        parent_user = None
        parent_user_external = None
        datetime = None
        other_context_list = []

        def __init__(self):
            pass
            
    platform = xapi_settings.PLATFORM_SLACK
    platform_url = "https://slack.com/"

    xapi_verbs = [xapi_settings.VERB_CREATED, xapi_settings.VERB_COMMENTED, xapi_settings.VERB_SHARED, 
                  xapi_settings.VERB_MENTIONED, xapi_settings.VERB_BOOKMARKED, xapi_settings.VERB_REMOVED,
                  xapi_settings.VERB_ATTACHED]
    xapi_objects = [xapi_settings.OBJECT_NOTE, xapi_settings.OBJECT_FILE, xapi_settings.VERB_COMMENTED]

    user_api_association_name = 'Slack Username' # eg the username for a signed up user that will appear in data extracted via a social API
    unit_api_association_name = 'Slack Team' # eg Slack team

    # The number of data (records) in a page in a Slack API response.
    per_page = 100

    TEAM_URL = 'https://%s.slack.com/'
    MESSAGE_URL = TEAM_URL + 'messages/%s'
    # This url is used as unique ID of xAPI statement (object ID)
    # The first %s is replaced with a team domain name, and the second one with channel name.
    # The third one is timestamp 
    ARCHIVE_MESSAGE_URL = 'https://%s.slack.com/archives/%s/p%s'

    # Subtypes
    SUBTYPE_FILE_COMMENT = 'file_comment'
    SUBTYPE_FILE_SHARE = 'file_share'
    SUBTYPE_FILE_MENTION = 'file_mention'
    SUBTYPE_PINNED_ITEM = 'pinned_item'
    SUBTYPE_UNPINNED_ITEM = 'unpinned_item'

    # Pinned item types
    PINNED_ITEM_MESSAGE = 'C'
    PINNED_ITEM_FILE = 'F'
    PINNED_ITEM_FILE_COMMENT = 'Fc'

    STAR_ITEM_TYPE_MESSAGE = 'message'
    STAR_ITEM_TYPE_FILE = 'file'
    STAR_ITEM_TYPE_FILE_COMMENT = 'file_comment'
    STAR_ITEM_TYPE_CHANNEL = 'channel'
    STAR_ITEM_TYPE_IM = 'im'
    STAR_ITEM_TYPE_GROUP = 'group'

    #from DIPluginDashboardMixin
    xapi_objects_to_includein_platformactivitywidget = [xapi_settings.OBJECT_COLLECTION, 
                                                        xapi_settings.OBJECT_FILE,
                                                        xapi_settings.VERB_COMMENTED]
    xapi_verbs_to_includein_verbactivitywidget = [xapi_settings.VERB_CREATED, xapi_settings.VERB_COMMENTED, 
                    xapi_settings.VERB_SHARED, xapi_settings.VERB_MENTIONED, xapi_settings.VERB_BOOKMARKED, 
                    xapi_settings.VERB_REMOVED, xapi_settings.VERB_ATTACHED]


    def __init__(self):
        pass


    def perform_import(self, retrieval_param, unit):
        
        # retrieval_param has access tokens of all users in a unit
        for details in retrieval_param:
            sc = SlackClient(details['access_token'])

            # Get team data
            team_info = self.get_team_info(sc)
            # Get all channel names in a team
            channels = self.get_channels(sc)
            # Get history of a channel
            self.import_channel_history(unit, sc, channels, team_info)
            # Get data about stars
            self.import_stars(details['slack_id'], unit, sc, team_info)


    def import_channel_history(self, unit, slack, channels, team_info):
        team_domain_name = team_info['team']['domain']

        for channel in channels:
            # Retrieve history from all channels in the team
            latest_timestamp = None
            history = None
            while(True):
                if latest_timestamp is None:
                    history = slack.api_call("channels.history", 
                                              channel = channel['id'], count = self.per_page)
                else:
                    # Get data in the next page
                    history = slack.api_call("channels.history", 
                                              channel = channel['id'], latest = latest_timestamp, count = self.per_page)

                messages = history['messages']
                for message in messages:
                    # Message
                    if 'subtype' in message:
                        subtype = message['subtype']
                        if subtype == self.SUBTYPE_FILE_COMMENT:
                            # Import a message on a file (file comment)
                            self.import_file_comment(message, unit, slack, team_domain_name, channel)

                        elif subtype == self.SUBTYPE_FILE_SHARE:
                            if message['upload'] == True:
                                # Import a uploaded file. (file upload)
                                self.import_file_upload(message, unit, slack, team_domain_name, channel)
                            elif message['upload'] == False:
                                # Import a shared file. (file share)
                                self.import_file_share(message, unit, slack, team_domain_name, channel)

                        elif subtype == self.SUBTYPE_FILE_MENTION:
                            # Import a file mentioned (file mention)
                            # Note: Users can mention a file when they copy the link to a file and paste it to message box.
                            self.import_file_mention(message, unit, slack, team_domain_name, channel)

                        elif subtype == self.SUBTYPE_PINNED_ITEM:
                            # Import data of pinned items 
                            self.import_pinned_item(message, unit, slack, team_domain_name, channel)

                        elif subtype == self.SUBTYPE_UNPINNED_ITEM:
                            #
                            # Note: unpinned_item is not included in the response of channel.history endpoint (28/02/2017)
                            # 
                            # Import unpinned items 
                            self.import_unpinned_item(message, unit, slack, team_domain_name, channel)
                            
                    else:
                        # Import messages and replies to a message
                        self.import_non_subtype_data(message, unit, slack, team_domain_name, channel)

                # Check if there is more history
                if history['has_more'] == False:
                    # There is no more data left. Break out of the while loop.
                    break
                else:
                    # There is more data left. 
                    # Save the timestamp of the last history to use it as a parameter for the next api call
                    last_message = messages[len(messages) - 1]
                    latest_timestamp = last_message['ts']

            # End of while(True)
        # End of for channel in channels:


    def import_non_subtype_data(self, message, unit, slack, team_domain_name, channel):
        if 'attachments' in message:
            # User shared message(s) (with or without his/her message)
            self.import_message_share(message, unit, slack, team_domain_name, channel)

        else:
            # User left a message on a channel or user replied to someone's message (in a thread).
            user = message['user']
            user = get_user_from_screen_name(user, self.platform)
            if user is None:
                return

            text = self.replace_slack_user_id_with_name(slack, message['text'])
            timestamp = message['ts'] # Unix timestamp.
            created_time = Utility.convert_unixtime_to_datetime(timestamp) # Datetime converted from unix timestamp
            
            object_id = self.get_slack_archive_url(team_domain_name, channel['name'], timestamp)

            if 'parent_user_id' in message:
                # User replied to someone's message (in a thread).
                parent_id = self.get_slack_archive_url(team_domain_name, channel['name'], message['thread_ts'])
                parent_user = get_user_from_screen_name(message['parent_user_id'], self.platform)
                insert_comment(user, parent_id, object_id, text, created_time, unit, self.platform, self.platform_url,
                    parent_user = parent_user)

            else:
                # User left a message on a channel 
                insert_post(user, object_id, text, created_time, unit, self.platform, self.platform_url)


    def import_file_comment(self, message, unit, slack, team_domain_name, channel):
        prop = self.get_file_comment_details(message, slack, team_domain_name, channel)
        if prop.user is None:
            return
        insert_comment(prop.user, prop.parent_id, prop.object_id, prop.message, prop.datetime, unit, 
                       self.platform, self.platform_url, parent_user = prop.parent_user)


    def import_file_share(self, message, unit, slack, team_domain_name, channel):
        prop = self.get_shared_file_details(message, slack, team_domain_name, channel)
        if prop.user is None:
            return
        insert_share(prop.user, prop.parent_id, prop.object_id, prop.message, prop.datetime, unit, 
                     prop.object_type, prop.parent_object_type,
                     self.platform, self.platform_url, parent_user = prop.parent_user)


    def import_file_mention(self, message, unit, slack, team_domain_name, channel):
        prop = self.get_shared_file_details(message, slack, team_domain_name, channel)
        if prop.user is None:
            return
        insert_mention(prop.user, prop.parent_id, prop.object_id, prop.message, prop.datetime, unit, 
            prop.object_type, prop.parent_object_type,
            self.platform, self.platform_url, parent_user = prop.parent_user)


    def import_file_upload(self, message, unit, slack, team_domain_name, channel):
        # Ignore files shared by bots
        if message['bot_id'] is not None:
            return

        user = get_user_from_screen_name(message['user'], self.platform)
        if user is None:
            return

        created_time = Utility.convert_unixtime_to_datetime(message['ts']) # Datetime converted from unix timestamp
        object_id = message['file']['permalink']
        text = message['file']['title']
        
        # When user uploaded a file, the parent is the channel
        parent_id = self.get_team_channel_url(team_domain_name, channel['name']) # Team's url
        parent_user = None
        parent_user_external = channel['name']
        other_context_list = []
        
        # If a user leaves a (initial) comment as the user uploads a file, 
        # import the comment in contextActivities property.
        if 'initial_comment' in message['file']:
            other_context_list.append(get_other_contextActivity(
                object_id, 'Object', message['file']['initial_comment']['comment'], 
                xapi_settings.get_object_iri(xapi_settings.OBJECT_NOTE)))

        insert_attach(user, parent_id, object_id, text, created_time, unit, 
                        xapi_settings.OBJECT_FILE, xapi_settings.OBJECT_COLLECTION,
                        self.platform, self.platform_url, parent_external_user = parent_user_external, 
                        other_contexts = other_context_list)

        # Note: When user shared a file with a comment, then the subtype will be file_comment.


    def import_pinned_item(self, message, unit, slack, team_domain_name, channel):
        # Pinned items are considered as shared items
        if message['item_type'] == self.PINNED_ITEM_MESSAGE:
            self.import_message_share(message, unit, slack, team_domain_name, channel)

        elif message['item_type'] == self.PINNED_ITEM_FILE:
            self.import_file_share(message, unit, slack, team_domain_name, channel)
            
        elif message['item_type'] == self.PINNED_ITEM_FILE_COMMENT:
            prop = self.get_file_comment_details(message, slack, team_domain_name, channel)
            if prop.user is None:
                return
            insert_share(prop.user, prop.parent_id, prop.object_id, prop.message, prop.datetime, unit, 
                     prop.object_type, prop.parent_object_type,
                     self.platform, self.platform_url, parent_user = prop.parent_user)

    
    def import_unpinned_item(self, message, unit, slack, team_domain_name, channel):

        #
        # Note: unpinned_item is not included in the response of channel.history endpoint (28/02/2017)
        # 
        if message['item_type'] == self.PINNED_ITEM_MESSAGE:
            # self.import_message_share(message, unit, slack, team_domain_name, channel)
            shared_msg_list = self.get_shared_message_list(message, slack, team_domain_name, channel)

            for shared_msg in shared_msg_list:
                if shared_msg.user is None:
                    continue
                insert_remove(shared_msg.user, shared_msg.object_id, shared_msg.message, 
                                shared_msg.datetime, unit, shared_msg.object_type, self.platform, self.platform_url)


        elif message['item_type'] == self.PINNED_ITEM_FILE:
            # self.import_file_share(message, unit, slack, team_domain_name, channel)
            prop = self.get_shared_file_details(message, slack, team_domain_name, channel)
            if prop.user is None:
                return

            insert_remove(prop.user, prop.object_id, prop.message, prop.datetime, unit, prop.object_type, 
                          self.platform, self.platform_url)

            
        elif message['item_type'] == self.PINNED_ITEM_FILE_COMMENT:
            prop = self.get_file_comment_details(message, slack, team_domain_name, channel)
            if prop.user is None:
                return

            insert_remove(prop.user, prop.object_id, prop.message, prop.datetime, unit, prop.object_type, 
                          self.platform, self.platform_url)


    def import_message_share(self, message, unit, slack, team_domain_name, channel):
        shared_msg_list = self.get_shared_message_list(message, slack, team_domain_name, channel)

        for shared_msg in shared_msg_list:
            if shared_msg.user is None:
                continue
            insert_share(shared_msg.user, shared_msg.parent_id, shared_msg.object_id, shared_msg.message, 
                         shared_msg.datetime, unit, shared_msg.object_type, shared_msg.parent_object_type, 
                         self.platform, self.platform_url, parent_user = shared_msg.parent_user, 
                         parent_external_user = shared_msg.parent_user_external, 
                         other_contexts = shared_msg.other_context_list)


    def import_stars(self, slack_user_id, unit, slack, team_info):
        team_domain_name = team_info['team']['domain']
        page  = 1
        while(True):
            # stars.list only returns the user's data. 
            # All users must be processed to retrieve all user's star data.
            stars = slack.api_call("stars.list", count = self.per_page, page = page)
            # TODO: Take care of pagination!
            
            for star_item in stars['items']:
                if star_item == self.STAR_ITEM_TYPE_IM or star_item == self.STAR_ITEM_TYPE_GROUP:
                    continue

                user = get_user_from_screen_name(slack_user_id, self.platform)
                if user is None:
                    continue
                #
                # Note: star data doesn't have timestamp!
                # timestamp = message['ts'] # Unix timestamp.
                starred_datetime = datetime.datetime.now()
                text = None
                object_id = None
                object_type = None
                parent_id = None
                parent_object_type = None

                # Starred a message
                if star_item['type'] == self.STAR_ITEM_TYPE_MESSAGE:
                    text = star_item['message']['text']
                    # Add user ID to prevent object id collision
                    object_id = star_item['message']['permalink'] + ('%s' % str(slack_user_id))
                    object_type = xapi_settings.OBJECT_NOTE
                    parent_id = star_item['message']['permalink']
                    parent_object_type = xapi_settings.OBJECT_NOTE

                # Starred a file
                elif star_item['type'] == self.STAR_ITEM_TYPE_FILE:
                    text = star_item['file']['title']
                    object_id = star_item['file']['permalink'] + ('%s' % str(slack_user_id))
                    object_type = xapi_settings.OBJECT_FILE
                    parent_id = star_item['file']['permalink']
                    parent_object_type = xapi_settings.OBJECT_FILE

                # Starred a file comment
                elif star_item['type'] == self.STAR_ITEM_TYPE_FILE_COMMENT:
                    text = star_item['comment']['comment']
                    object_id = star_item['file']['permalink'] + ('%s' % str(slack_user_id))
                    object_type = xapi_settings.OBJECT_NOTE
                    parent_id = star_item['file']['permalink']
                    parent_object_type = xapi_settings.OBJECT_NOTE

                # Starred a channel
                elif star_item['type'] == self.STAR_ITEM_TYPE_CHANNEL:
                    channel_info = self.get_channel_info(slack, star_item['channel'])
                    text = channel_info['channel']['name']
                    object_id = self.get_team_channel_url(team_domain_name, channel_info['channel']['name']) + ('%s' % str(slack_user_id))
                    object_type = xapi_settings.OBJECT_COLLECTION
                    parent_id = self.get_team_channel_url(team_domain_name, channel_info['channel']['name'])
                    parent_object_type = xapi_settings.OBJECT_COLLECTION

                # Convert Slack user IDs to user name
                text = self.replace_slack_user_id_with_name(slack, text)

                # Insert data into LRS
                insert_bookmark(user, parent_id, object_id, text, starred_datetime, unit, 
                                object_type, parent_object_type, self.platform, self.platform_url)

            paging_info = stars['paging']
            if int(paging_info['page']) < int(paging_info['pages']):
                # Increment the page number to get next page data
                page += 1
            else:
                # There is no more data. Break out of the while loop 
                break

        # End of while(True):


    def get_shared_message_list(self, message, slack, team_domain_name, channel):
        msg_list = []
        timestamp = message['ts'] # Unix timestamp.
        for attachment in message['attachments']:
            prop = self.XAPIProperty()
            prop.message = self.replace_slack_user_id_with_name(slack, attachment['text'])
            prop.user = get_user_from_screen_name(message['user'], self.platform)
            prop.object_id = self.get_slack_archive_url(team_domain_name, channel['name'], timestamp)
            prop.parent_id = self.get_slack_archive_url(team_domain_name, attachment['channel_name'], attachment['ts'])
            prop.object_type = xapi_settings.OBJECT_NOTE
            prop.parent_object_type = xapi_settings.OBJECT_NOTE
            prop.datetime = Utility.convert_unixtime_to_datetime(timestamp) # Datetime converted from unix timestamp
            
            slack_parent_user = self.get_slack_user_from_slackname(slack, attachment['author_subname'])
            if slack_parent_user is not None:
                prop.parent_user = get_user_from_screen_name(slack_parent_user['id'], self.platform)

            prop.parent_user_external = attachment['author_subname'] if prop.parent_user is None else None

            if 'text' in message and (message['text'] is not None and message['text'] != ''):
                # prop.additional_message = message['text']
                # If user left a comment as the user shared a message, 
                # the comment is imported in contextActivities property.
                prop.other_context_list = []
                prop.other_context_list.append(get_other_contextActivity(
                    prop.object_id, 'Object', message['text'],
                    xapi_settings.get_verb_iri(xapi_settings.VERB_COMMENTED)))

            msg_list.append(prop)

        return msg_list


    def get_shared_file_details(self, message, slack, team_domain_name, channel):

        # Ignore files shared by bots
        if 'bot_id' in message and message['bot_id'] is not None:
            return

        prop = self.XAPIProperty()
        property_name = 'file'
        if 'item' in message:
            # When item property is in message, that means the parameter "message" is a pinned item.
            property_name = 'item'

        prop.message = self.replace_slack_user_id_with_name(slack, message[property_name]['title'])
        prop.user = get_user_from_screen_name(message['user'], self.platform)
        prop.object_id = self.get_slack_archive_url(team_domain_name, channel['name'], message['ts'])

        # When user shared/pinned a file, the parent user is the owner of the file shared/pinned, 
        # and parent id is the file's url.
        prop.parent_id = message[property_name]['permalink']
        prop.object_type = xapi_settings.OBJECT_FILE
        prop.parent_object_type = xapi_settings.OBJECT_FILE
        prop.parent_user = get_user_from_screen_name(message[property_name]['user'], self.platform)
        prop.parent_user_external = message[property_name]['user'] if prop.parent_user is None else None
        prop.datetime = Utility.convert_unixtime_to_datetime(message['ts']) # Datetime converted from unix timestamp

        return prop


    def get_file_comment_details(self, message, slack, team_domain_name, channel):
        prop = self.XAPIProperty()
        prop.datetime = Utility.convert_unixtime_to_datetime(message['ts']) # Datetime converted from unix timestamp

        if 'file' in message:
            # Left a comment on a file
            prop.user = get_user_from_screen_name(message['comment']['user'], self.platform)
            prop.message = self.replace_slack_user_id_with_name(slack, message['comment']['comment'])
            prop.object_id = self.get_slack_archive_url(team_domain_name, channel['name'], message['comment']['timestamp'])
            prop.parent_id = message['file']['permalink']
            prop.object_type = xapi_settings.OBJECT_NOTE
            prop.parent_object_type = xapi_settings.OBJECT_FILE
            prop.parent_user = get_user_from_screen_name(message['file']['user'], self.platform)

        elif 'item' in message:
            # Pinned a comment that's on a file
            prop.user = get_user_from_screen_name(message['user'], self.platform)
            prop.message = self.replace_slack_user_id_with_name(slack, message['item']['comment'])
            prop.object_id = self.get_slack_archive_url(team_domain_name, channel['name'], message['ts'])
            prop.parent_id = self.get_slack_archive_url(team_domain_name, channel['name'], message['item']['timestamp'])
            prop.object_type = xapi_settings.OBJECT_NOTE
            prop.parent_object_type = xapi_settings.OBJECT_NOTE
            prop.parent_user = get_user_from_screen_name(message['item']['user'], self.platform)

        return prop


    def get_team_url(self, team_domain_name):
        return self.TEAM_URL % (team_domain_name)

    def get_team_channel_url(self, team_domain_name, channel_name):
        return self.MESSAGE_URL % (team_domain_name, channel_name)

    def get_slack_archive_url(self, team_domain_name, channel_name, timestamp):
        return self.ARCHIVE_MESSAGE_URL % (team_domain_name, channel_name, str(timestamp))

    def get_team_info(self, sclack):
        return sclack.api_call("team.info")

    def get_slack_user_from_slackid(self, slack, slack_id):
        return slack.api_call("users.info", user = slack_id)

    def get_channel_info(self, slack, channel_id):
        return slack.api_call("channels.info", channel = channel_id)

    def get_channels(self, slack):
        channels = []
        channel_list = slack.api_call("channels.list")
        for channel in channel_list['channels']:
            obj = {'id': channel['id'], 'name': channel['name']}
            channels.append(obj)

        return channels

    def get_slack_user_from_slackname(self, slack, name):
        members = slack.api_call("users.list")
        for member in members['members']:
            if member['name'] == name:
                return member

        return None

    def replace_slack_user_id_with_name(self, slack, text):
        regex_pattern = r'<@\w{9}>' # e.g. <@USER123ID>

        if text is None or text == '':
            return text

        # Replace fixed strings
        text = text.replace('<!here|@here>', '@here')
        text = text.replace('<!everyone>', '@everyone')
        text = text.replace('<!channel>', '@channel')

        # Find all Slack user IDs in a text string
        user_id_list = re.findall(regex_pattern, str(text))
        if len(user_id_list) == 0:
            return text

        # user_id_list has IDs "e.g. ['<@USER123ID>', '<@USER456XY>' ...]"
        for user_id in user_id_list:
            user_info = self.get_slack_user_from_slackid(slack, str(user_id[2:len(user_id) - 1]))
            if user_info['ok'] == True:
                # Replace the Slack id in the text with the Slack user name
                replace_with = '@%s' % user_info['user']['name']
                text = text.replace(user_id, replace_with)

        return text

registry.register(SlackPlugin)
