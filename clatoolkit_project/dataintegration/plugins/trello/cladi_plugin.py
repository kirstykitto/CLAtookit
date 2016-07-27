__author__ = 'zak'

from dataintegration.core.plugins import registry
from dataintegration.core.plugins.base import DIBasePlugin, DIPluginDashboardMixin, DIAuthomaticPluginMixin
from dataintegration.core.socialmediarecipebuilder import *
from dataintegration.core.recipepermissions import *
import json
import dateutil.parser
from authomatic.providers import oauth2
import requests
import os

#Trello pylib
from trello import TrelloClient

#OAuth for trello
from requests_oauthlib import OAuth1Session


class TrelloPlugin(DIBasePlugin, DIPluginDashboardMixin):

    platform = "trello"
    platform_url = "http://www.trello.com/"

    #created for "create" actions
    #added for "add" actions
    #updated for "update" actions
    #commented for card "comment" actions
    xapi_verbs = ['created', 'added', 'updated', 'commented', 'closed', 'opened']

    #Note for "commented" actions
    #Task for "created", "added", "updated", and "commented" actions
    #Collection for any "created", "added", "updated" List actions (tentative use)
    xapi_objects = ['Note', 'Task', 'Collection', 'Person', 'File', 'checklist-item', 'checklist']

    user_api_association_name = 'Trello UID' # eg the username for a signed up user that will appear in data extracted via a social API
    unit_api_association_name = 'Board ID' # eg hashtags or a group name

    config_json_keys = ['consumer_key', 'consumer_secret']

    #from DIPluginDashboardMixin
    xapi_objects_to_includein_platformactivitywidget = ['Note']
    xapi_verbs_to_includein_verbactivitywidget = ['created', 'shared', 'liked', 'commented']

    #for OAuth1 authentication
    token_request_url = ''

    def __init__(self):
        #Load api_config.json and convert to dict
        config_file = os.path.join(os.path.dirname(__file__), 'api_config.json')

        with open(config_file) as data_file:
            self.api_config_dict = json.load(data_file)

    #retreival param is the user_id
    def perform_import(self, retreival_param, course_code, token=None):
        #from clatoolkit.models import ApiCredentials
        #Set up trello auth and API
        #self.usercontext_storage_dict = json.load(ApiCredentials.objects.get(platform=retreival_param).credentials_json)

        self.TrelloCient = TrelloClient(
            api_key=self.api_config_dict['api_key'],
            #api_secret=self.api_config_dict['api_secret'],
            token=token
        )

        #Get user-registered board in trello
        trello_board = self.TrelloCient.get_board(retreival_param)

        #Get boards activity/action feed
        trello_board.fetch_actions('all') #fetch_actions() collects actions feed and stores to trello_board.actions

        #self.key = trello_board.api_key
        #self.token = trello_board.resource_owner_key

        self.import_TrelloActivity(trello_board.actions, course_code)

    def import_TrelloActivity(self, feed, course_code):
        #User needs to sign up username and board (board can be left out but is needed)
        print 'Beginning trello import!'

        for action in list(feed):
            #print 'action: %s' % (action)
            #action = json.load(action)

            #We need to connect this with our user profile somewhere when they initially auth
            u_id = action['idMemberCreator']
            author = action['memberCreator']['username']
            type = action['type'] #commentCard, updateCard, createList,etc
            data = action['data']
            date = action['date']
            board_name = data['board']['name']

            print 'got action type: %s' % (type)

            #print 'is action comment? %s' % (type == 'commentCard')
            #Get all 'commented' verb actions
            if (type == 'commentCard'):
                #do stuff
                target_obj_id = data['card']['shortLink']
                #date
                comment_from_uid = u_id
                comment_from_name = author
                comment_message = data['text']
                comment_id = action['id']

                if username_exists(comment_from_uid, course_code, self.platform):
                    usr_dict = get_userdetails(comment_from_uid, self.platform)
                    insert_comment(usr_dict, target_obj_id, comment_id,
                                   comment_message, comment_from_uid,
                                   comment_from_name, date, course_code,
                                   self.platform, self.platform_url)
                    print 'Inserted comment!'

            #print 'is action card creation? %s' % (type == 'createCard')
            #Get all 'create' verb actions
            if (type == 'createCard'): #, 'createList']):
                #date
                #list_id = data['list']['id']
                task_id = data['card']['shortLink']
                task_name = data['card']['name']

                if username_exists(u_id, course_code, self.platform):
                    usr_dict = get_userdetails(u_id, self.platform)
                    insert_task(usr_dict, task_id, task_name, u_id, author, date,
                                course_code, self.platform, self.platform_url) #, list_id=list_id)
                    print 'Inserted created card!'


            #Get all 'add' verbs (you tecnically aren't *creating* an attachment on
            #a card so....)
            #print 'is action an add event? %s' % (type in
            #    ['addAttachmentToCard', 'addMemberToBoard',
            #     'emailCard', 'addChecklistToCard'
            #     , 'addMemberToCard'])
            if (type in
                ['addAttachmentToCard', 'addMemberToBoard',
                 'emailCard', 'addChecklistToCard'
                 , 'addMemberToCard']):

                usr_dict = None
                if username_exists(u_id, course_code, self.platform):
                    usr_dict = get_userdetails(u_id, self.platform)

                if type is 'addAttachmentToCard' and usr_dict is not None:

                    target_id = data['card']['shortLink']
                    attachment = data['attachment']
                    attachment_id = attachment['id']
                    attachment_data = '%s - %s' % (attachment['name'], attachment['url'])
                    object_type = 'File'
                    shared_displayname = '%sc/%s' % (self.platform_url, target_id)

                    insert_added_object(usr_dict, target_id, attachment_id, attachment_data,
                                        u_id, author, date, course_code, self.platform, self.platform_url,
                                        object_type, shared_displayname=shared_displayname)

                    print 'Added attachment!'

                if type is 'addMemberToCard' and usr_dict is not None: #or 'addMemberToBoard':

                    target_id = data['card']['shortLink']
                    object_id = data['idMember']
                    object_data = action['memeber']['username']
                    object_type = 'Person'
                    shared_displayname = '%sc/%s' % (self.platform_url, target_id)

                    insert_added_object(usr_dict, target_id, object_id, object_data, u_id, author, date,
                                        course_code, self.platform, self.platform_url, object_type,
                                        shared_displayname=shared_displayname)

                    print 'Added add member to card!'

                if type is 'addChecklistToCard' and usr_dict is not None:

                    target_id = data['card']['shortlink']
                    object_id = data['idMember']
                    object_data = None
                    checklist_items = None
                    object_type = 'Collection'
                    shared_displayname = '%sc/%s' % (self.platform_url, target_id)

                    #get checklist contents
                    try:
                        checklist = self.TrelloCient.fetch_json('/checklists/' + data['checklist']['id'],)
                        checklist_items = checklist['checkItems']
                    except Exception:
                        print 'Could not retrieve checklist..'

                    #data will be a comma separated list of checklist-item ids (e.g.: 'id1,id2,id3...')
                    object_data = ','.join([item['id'] for item in checklist_items])

                    insert_added_object(usr_dict, target_id, object_id, object_data, u_id, author, date,
                                        course_code, self.platform, self.platform_url, object_type,
                                        shared_displayname=shared_displayname)

                    print 'added add checklist to card!'


            print 'is action type an update? %s' % (type in
                ['updateCheckItemStateOnCard', 'updateBoard',
                 'updateCard', 'updateCheckList',
                 'updateList', 'updateMember'])
            #Get all 'updated' verbs
            if (type in
                ['updateCheckItemStateOnCard', 'updateBoard',
                 'updateCard', 'updateCheckList',
                 'updateList', 'updateMember']):

                usr_dict = None
                if username_exists(u_id, course_code, self.platform):
                    usr_dict = get_userdetails(u_id, self.platform)

                #many checklist items will be bugged - we require webhooks!

                if type == 'updateCheckItemStateOnCard' and usr_dict is not None:

                    insert_updated_object(usr_dict,
                                          data['checkItem']['id'],
                                          data['checkItem']['state'],
                                          u_id, author, date, course_code,
                                          self.platform, self.platform_url,
                                          'checklist-item', obj_parent=data['checklist']['id'],
                                          obj_parent_type='checklist')

                    print 'add update checklist!'



                #type will only show 'updateCard'
                #up to us to figure out what's being updated
                if type == 'updateCard':
                    print 'data: %s' % (data)

                    #Get and store the values that were changed, usually it's only one
                    try:
                        change = [changed_value for changed_value in data['old']]
                    except Exception:
                       print 'Error occurred getting changes...'
                    #assert len(change) is 1

                    print 'got changes: %s' % (change)

                    #Insert all updates that aren't closed
                    if change[0] == 'pos':

                        if 'listBefore' in data:
                            insert_updated_object(usr_dict, data['card']['id'],
                                                  'Move card from %s to %s' % (data['listBefore']['name'], data['listAfter']['name']),
                                                  u_id, author, date, course_code,
                                                  self.platform, self.platform_url,
                                                  'Task', obj_parent=data['list']['name'],
                                                  obj_parent_type='Collection')
                        else:
                            insert_updated_object(usr_dict, data['card']['id'],
                                                  'Move card from %s to %s' % (data['old']['pos'], data['card']['pos']),
                                                  u_id, author, date, course_code,
                                                  self.platform, self.platform_url,
                                                  'Task', obj_parent=data['list']['name'],
                                                  obj_parent_type='Collection')
                        print 'added closed card!'
                    #add in close/open verbs
                    else:
                        if data['old'][change[0]] is False:
                            insert_closedopen_object(usr_dict, data['card']['id'],
                                                 '%s:%s' % ('Closed', data['card']['name']),
                                                 u_id, author, date, course_code,
                                                 self.platform, self.platform_url,
                                                 'Task', 'closed', obj_parent=data['list']['name'],
                                                 obj_parent_type='Collection')

                            print 'added closed/opened card!'

                        elif data['old'][change[0]] is True:
                            insert_closedopen_object(usr_dict, data['card']['id'],
                                                 '%s:%s' % ('Opened', data['card']['name']),
                                                 u_id, author, date, course_code,
                                                 self.platform, self.platform_url,
                                                 'Task', 'opened', obj_parent=data['list']['name'],
                                                 obj_parent_type='Collection')

                            print 'added closed/opened card!'


registry.register(TrelloPlugin)










