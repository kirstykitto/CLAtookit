import json
import uuid
import ast
import pprint
import datetime
from dataintegration.core.recipepermissions import *
from clatoolkit.models import SocialRelationship, LearningRecord

from tincan import (
    RemoteLRS,
    Statement,
    Agent,
    AgentAccount,
    Verb,
    Activity,
    Context,
    ContextActivities,
    ActivityList,
    LanguageMap,
    ActivityDefinition,
    StateDocument,
    Group,
    Result,
    Score
)

#from resources import lrs_properties

def pretty_print_json(jsn):
    pretty_json = json.dumps(jsn, sort_keys=True, indent=4, separators=(',', ': '))
    return pretty_json

def write_json_tofile(filename, jsn):
    pretty_json = pretty_print_json(jsn)
    with open(filename, 'w') as file_:
        file_.write(pretty_json)

def save_statement_tofile(filename,stm):
    jsn = ast.literal_eval(stm.to_json())
    write_json_tofile(filename, jsn)

def statement_builder(actor, verb, object, context, result, timestamp=None):
    statement = None
    if timestamp is None:
        statement = Statement(
            actor=actor,
            verb=verb,
            object=object,
            context=context,
            result=result,
        )
    else:
        statement = Statement(
            actor=actor,
            verb=verb,
            object=object,
            context=context,
            result=result,
            timestamp=timestamp
        )
    return statement


def get_other_contextActivity(obj_id, obj_type, def_name, def_type):
    ret = {}
    definition = {'name': def_name}
    definition['type'] = def_type
    ret['obj_id'] = obj_id
    ret['obj_type'] = obj_type
    ret['definition'] = definition
    return ret


def socialmedia_builder(verb, platform, account_name, account_homepage, object_type, object_id,
                        message, tags=[], parent_object_type=None, parent_id=None, rating=None, instructor_name=None,
                        instructor_email=None, team_name=None, course_code=None, account_email=None, user_name=None,
                        timestamp=None, other_contexts=[]):

    verbmapper = {
                  'created': 'http://www.w3.org/ns/activitystreams#Create',
                  'shared': 'http://activitystrea.ms/schema/1.0/share',
                  'liked': 'http://activitystrea.ms/schema/1.0/like',
                  'rated': 'http://id.tincanapi.com/verb/rated',
                  'commented': 'http://adlnet.gov/expapi/verbs/commented',
                  'added': 'http://www.w3.org/ns/activitystreams#Add',
                  'updated': 'http://activitystrea.ms/schema/1.0/update',
                  'removed': 'http://activitystrea.ms/schema/1.0/remove',
                  'deleted': 'http://www.w3.org/ns/activitystreams#Delete',
                  'opened': 'http://activitystrea.ms/schema/1.0/open',
                  'closed': 'http://activitystrea.ms/schema/1.0/close',

    }

    objectmapper = {
                    'Note': 'http://activitystrea.ms/schema/1.0/note',
                    'Tag': 'http://id.tincanapi.com/activitytype/tag',
                    'Article': 'http://activitystrea.ms/schema/1.0/article',
                    'Video': 'http://activitystrea.ms/schema/1.0/video',
                    'Bookmark': 'http://activitystrea.ms/schema/1.0/bookmark',
                    'Collection': 'http://activitystrea.ms/schema/1.0/collection',
                    'File': 'http://activitystrea.ms/schema/1.0/file',
                    'Task': 'http://activitystrea.ms/specs/json/schema/activity-schema.html#task',
                    'checklist': 'http://id.tincanapi.com/activitytype/checklist',
                    'checklist-item': 'http://id.tincanapi.com/activitytype/checklist-item',
                    'Person': 'http://activitystrea.ms/head/activity-schema.html#person',
    }

    agentaccount = AgentAccount(name=account_name, home_page=account_homepage)
    actor = Agent(account=agentaccount)
    if (account_email is not None):
        actor.mbox = account_email
    if (user_name is not None):
        actor.name = user_name

    verb_obj = Verb(id=verbmapper[verb],display=LanguageMap({'en-US': verb}))

    #message = message.decode('utf-8').encode('ascii', 'ignore') #message.decode('utf-8').replace(u"\u2018", "'").replace(u"\u2019", "'").replace(u"\u2013", "-").replace(u"\ud83d", " ").replace(u"\ude09", " ").replace(u"\u00a0l", " ").replace(u"\ud83d", " ").replace(u"\u2026", " ").replace(u"\ude09", " ").replace(u"\u00a0"," ")

    object = Activity(
        id=object_id,
        object_type=object_type,
        definition=ActivityDefinition(
            name=LanguageMap({'en-US': message}),
            type=objectmapper[object_type]
        ),
    )

    taglist = []
    for tag in tags:
        tagobject = Activity(
            id='http://id.tincanapi.com/activity/tags/tincan',
            object_type='Activity',
            definition=ActivityDefinition(
                name=LanguageMap({'en-US': tag}),
                type=objectmapper['Tag']
                ),
            )
        taglist.append(tagobject)

    # Add "other" in contextActivities
    other_contexts_list = []
    for other in other_contexts:
        other_context_obj = Activity(
            id = other['obj_id'],
            object_type = other['obj_type'],
            definition=ActivityDefinition(
                name = LanguageMap({'en-US': other['definition']['name']}),
                type = other['definition']['type']
            ),
        )
        other_contexts_list.append(other_context_obj)
    taglist.extend(other_contexts_list)

    parentlist = []
    if (verb in ['liked','shared','commented','rated']):
        parentobject = Activity(
            id=parent_id,
            object_type=parent_object_type,
            )
        parentlist.append(parentobject)
    elif (platform == 'GitHub' or platform.lower() == 'trello'):
        parentobject = Activity(
            id=parent_id,
            object_type=parent_object_type,
            )
        parentlist.append(parentobject)

    courselist = []
    if unit is not None:
        courseobject = Activity(
            id=unit.id,
            object_type='Course',
            definition=ActivityDefinition(type="http://adlnet.gov/expapi/activities/course")
        )
        courselist.append(courseobject)

    instructor = None
    if (instructor_name is not None):
        instructor=Agent(name=instructor_name,mbox=instructor_email)

    team = None
    if (team_name is not None):
        team = Group(Agent(name=team_name), object_type='Group')

    result = None
    if (rating is not None):
        rating_as_float = float(rating)
        result = Result(score=Score(raw=rating_as_float))

    context = Context(
        registration=uuid.uuid4(),
        platform=platform,
        instructor=instructor,
        team=team,
        context_activities=ContextActivities(other=ActivityList(taglist),parent=ActivityList(parentlist),grouping=ActivityList(courselist))
    )

    statement = statement_builder(actor, verb_obj, object, context, result, timestamp)

    return statement


def insert_post(user, post_id, message, created_time, unit, platform, platform_url, platform_group_id=None, tags=()):
    verb = 'created'

    if check_ifnotinlocallrs(unit, platform, post_id, user, verb):
        lrs = LearningRecord(xapi=None, unit=unit, verb=verb, platform=platform, user=user, platformid=post_id,
                             message=message, datetimestamp=created_time, platform_group_id=platform_group_id)
        lrs.save()
        for tag in tags:
            if tag[0] == "@":
                # If the user exists, use their user object else reference them as an external user
                if username_exists(tag[1:], unit, platform):
                    to_user = get_user_from_screen_name(tag[1:], platform)
                    external_user = None
                else:
                    to_user = None
                    external_user = tag[1:]

                sr = SocialRelationship(verb="mentioned", from_user=user, to_user=to_user,
                                        to_external_user=external_user, platform=platform, message=message,
                                        datetimestamp=created_time, unit=unit, platformid=post_id)
                sr.save()

def insert_blogpost(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url, tags=[]):
    #print 'from_name: %s\n from_uid: %s\n' % (from_name,from_uid)
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmedia_builder(verb='created', platform=platform, account_name=from_name, account_homepage=platform_url, object_type='Article', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_uid, course_code=course_code, tags=tags)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=from_name, platformid=post_id, message=message, datetimestamp=created_time)
        lrs.save()
        for tag in tags:
            if tag[0]=="@":
                socialrelationship = SocialRelationship(verb = "mentioned", fromusername=get_username_fromsmid(from_name,platform), tousername=get_username_fromsmid(tag[1:],platform), platform=platform, message=message, datetimestamp=created_time, course_code=course_code, platformid=post_id)

                socialrelationship.save()


def insert_like(user, post_id, message, unit, platform, platform_group_id=None, created_time=None, parent_user=None,
                parent_user_external=None):

    verb = "liked"

    if check_ifnotinlocallrs(unit, platform, post_id, user, verb):
        lrs = LearningRecord(xapi=None, unit=unit, verb=verb, platform=platform, platform_group_id=platform_group_id,
                             user=user, platformid=post_id, message=message, platformparentid=post_id,
                             parent_user=parent_user, parent_user_external=parent_user_external,
                             datetimestamp=created_time)
        lrs.save()

        sr = SocialRelationship(unit=unit, verb=verb, from_user=user, to_user=parent_user,
                                to_external_user=parent_user_external, platform=platform,
                                platform_group_id=platform_group_id, message=message, datetimestamp=created_time,
                                platformid=post_id)
        sr.save()


def insert_blogcomment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, shared_username=None, shared_displayname=None):

    #print "1: %s\n 2: %s\n 3: %s\n 4: %s" % (comment_from_uid, comment_from_name,shared_username,shared_displayname)

    if check_ifnotinlocallrs(course_code, platform, comment_id):
        if shared_displayname is not None:
            stm = socialmedia_builder(verb='commented', platform=platform, account_name=comment_from_uid, account_homepage=platform_url, object_type='Note', object_id=comment_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code )
            jsn = ast.literal_eval(stm.to_json())
            stm_json = pretty_print_json(jsn)
            lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='commented', platform=platform, username=get_username_fromsmid(comment_from_uid, platform), platformid=comment_id, platformparentid=post_id, parentusername=get_username_fromsmid(shared_displayname,platform), parentdisplayname=shared_displayname, message=comment_message, datetimestamp=comment_created_time)
            lrs.save()
            print "COMMENT SAVED!"
            socialrelationship = SocialRelationship(verb = "commented", fromusername=get_username_fromsmid(comment_from_uid,platform), tousername=get_username_fromsmid(shared_username,platform), platform=platform, message=comment_message, datetimestamp=comment_created_time, course_code=course_code, platformid=comment_id)
            socialrelationship.save()


def insert_comment(user, post_id, comment_id, comment_message, comment_created_time, unit, platform, platform_url,
                   platform_group_id=None, parent_user=None, parent_user_external=None):
    if check_ifnotinlocallrs(unit, platform, comment_id):

        lrs = LearningRecord(xapi=None, unit=unit, verb='commented', platform=platform, user=user,
                             platformid=comment_id, platformparentid=post_id, platform_group_id=platform_group_id,
                             parent_user=parent_user, parent_user_external=parent_user_external,
                             message=comment_message, datetimestamp=comment_created_time)
        lrs.save()

        sr = SocialRelationship(verb="commented", from_user=user, to_user=parent_user,
                                to_external_user=parent_user_external, platform=platform,
                                platform_group_id=platform_group_id, message=comment_message,
                                datetimestamp=comment_created_time, unit=unit, platformid=comment_id)
        sr.save()


def insert_share(user, post_id, share_id, comment_message, comment_created_time, unit, platform, platform_url,
                 platform_group_id=None, tags=(), parent_user=None, parent_external_user=None):
    if check_ifnotinlocallrs(unit, platform, share_id):
        lrs = LearningRecord(xapi=None, unit=unit, verb='shared', platform=platform,
                             platform_group_id=platform_group_id, user=user, platformid=share_id,
                             platformparentid=post_id, parent_user=parent_user,
                             parent_external_user=parent_external_user, message=comment_message,
                             datetimestamp=comment_created_time)
        lrs.save()

        sr = SocialRelationship(verb="shared", from_user=user, to_user=parent_user,
                                to_external_user=parent_external_user, platform=platform,
                                platform_group_id=platform_group_id, message=comment_message,
                                datetimestamp=comment_created_time, course_code=unit.code, platformid=share_id)
        sr.save()


def insert_bookmark(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmedia_builder(verb='created', platform=platform, account_name=from_uid, account_homepage=platform_url, object_type='Bookmark', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_name, course_code=course_code, tags=tags)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=get_username_fromsmid(from_uid, platform), platformid=post_id, message=message, datetimestamp=created_time)
        lrs.save()


def insert_commit(user, repo_id, commit_id, message, committed_time, unit, platform, committer=None):
    if check_ifnotinlocallrs(unit, platform, commit_id):
        verb = "created"

        lrs = LearningRecord(xapi=None, unit=unit, verb=verb, platform=platform, user=user, platformid=commit_id,
                             platformparentid=repo_id, message=message, datetimestamp=committed_time)
        lrs.save()


def insert_file(user, commit_id, file_id, message, committed_time, unit, platform, verb):
    if check_ifnotinlocallrs(unit, platform, file_id):
        lrs = LearningRecord(xapi=None, unit=unit, verb=verb, platform=platform, user=user, platformid=file_id,
                             platformparentid=commit_id, message=message, datetimestamp=committed_time)
        lrs.save()


def insert_issue(user, repo_id, issue_id, message, created_time, unit, platform):
    if check_ifnotinlocallrs(unit, platform, issue_id):
        verb = 'created'

        lrs = LearningRecord(xapi=None, unit=unit, verb=verb, platform=platform, platformid=issue_id, user=user,
                             platformparentid=repo_id, message=message, datetimestamp=created_time)
        lrs.save()
        """
        for tag in tags:
            if tag[0]=="@":
                socialrelationship = SocialRelationship(
                    verb = "mentioned", fromusername=get_username_fromsmid(from_uid,platform), 
                    tousername=get_username_fromsmid(tag[1:],platform), 
                    platform=platform, message=message, datetimestamp=created_time, 
                    course_code=course_code, platformid=platform_id)
                socialrelationship.save()
        """

def insert_task(usr_dict, task_id, task_name, task_from_uid, task_from_name, task_created_time, course_code, platform, platform_url, #labels=[],
                list_id=None, other_contexts = []):
    if check_ifnotinlocallrs(course_code, platform, task_id):
        stm = socialmedia_builder(verb='created', platform=platform, account_name=task_from_uid, account_homepage=platform_url,
                                  object_type='Task', object_id=task_id, message=task_name, timestamp=task_created_time,
                                  account_email=usr_dict['email'], user_name=task_from_name, course_code=course_code, 
                                  other_contexts = other_contexts)#, tags=labels)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=get_username_fromsmid(task_from_uid, platform),
                             platformid=task_id, message=task_name, datetimestamp=task_created_time)
        lrs.save()

        #maybe we can capture commenting behaviours between user/caard somehow?

def insert_added_object(usr_dict, target_id, object_id, object_text, obj_from_uid, obj_from_name, obj_created_time,
                        course_code, platform, platform_url, obj_type, shared_usrname=None, shared_displayname=None, 
                        other_contexts = []):
    if check_ifnotinlocallrs(course_code, platform, object_id):
        if shared_displayname is not None:
            stm = socialmedia_builder(verb='added', platform=platform, account_name=obj_from_uid, account_homepage=platform_url,
                                      object_type=obj_type, object_id=object_id, message=object_text, parent_id=target_id, 
                                      parent_object_type='Task', timestamp=obj_created_time, account_email=usr_dict['email'], 
                                      user_name=obj_from_name, course_code=course_code, other_contexts = other_contexts)
            jsn = ast.literal_eval(stm.to_json())
            stm_jsn = pretty_print_json(jsn)
            lrs = LearningRecord(xapi=stm_jsn, course_code=course_code, verb='added', platform=platform,
                                 username=get_username_fromsmid(obj_from_uid, platform), 
                                 platformid=object_id, platformparentid=target_id, 
                                 parentusername=get_username_fromsmid(shared_displayname,platform), 
                                 parentdisplayname=shared_displayname, message=object_text, 
                                 datetimestamp=obj_created_time)
            lrs.save()

            '''Maybe social relationship stuff...
            '''

def insert_updated_object(usr_dict, object_id, object_text, obj_updater_uid, obj_updater_name, obj_update_time,
                          course_code, platform, platform_url, obj_type, obj_parent=None, obj_parent_type=None, 
                          other_contexts = []):
    if check_ifnotinlocallrs(course_code, platform, object_id):
        if obj_parent is not None:
            stm = socialmedia_builder(verb='updated', platform=platform, account_name=obj_updater_uid, account_homepage=platform_url,
                                      object_type=obj_type, object_id=object_id, message=object_text, parent_id=obj_parent,
                                      parent_object_type=obj_parent_type, timestamp=obj_update_time, account_email=usr_dict['email'],
                                      user_name=obj_updater_name, course_code=course_code, other_contexts = other_contexts)
            jsn = ast.literal_eval(stm.to_json())
            stm_jsn = pretty_print_json(jsn)
            lrs = LearningRecord(xapi=stm_jsn, course_code=course_code, verb='updated', platform=platform,
                                 username=get_username_fromsmid(obj_updater_uid, platform), 
                                 platformid=object_id, platformparentid=obj_parent, 
                                 message=object_text, datetimestamp=obj_update_time)
            lrs.save()

def insert_closedopen_object(usr_dict, object_id, object_text, obj_updater_uid, obj_updater_name, obj_update_time,
                          course_code, platform, platform_url, obj_type, verb, obj_parent=None, obj_parent_type=None, 
                          other_contexts = []):
    if check_ifnotinlocallrs(course_code, platform, object_id):
        if obj_parent is not None:
            stm = socialmedia_builder(verb=verb, platform=platform, account_name=obj_updater_uid, account_homepage=platform_url,
                                      object_type=obj_type, object_id=object_id, message=object_text, parent_id=obj_parent,
                                      parent_object_type=obj_parent_type, timestamp=obj_update_time, account_email=usr_dict['email'],
                                      user_name=obj_updater_name, course_code=course_code, other_contexts = other_contexts)
            jsn = ast.literal_eval(stm.to_json())
            stm_jsn = pretty_print_json(jsn)
            lrs = LearningRecord(xapi=stm_jsn, course_code=course_code, verb=verb, platform=platform,
                                 username=get_username_fromsmid(obj_updater_uid, platform), 
                                 platformid=object_id, platformparentid=obj_parent, message=object_text, 
                                 datetimestamp=obj_update_time)
            lrs.save()


def insert_relationship(from_user, to_user, relationship_type, unit, platform, platform_group_id=None,
                        directional=True):
    search_args = {
        "from_user": from_user,
        "to_user": to_user,
        "type": relationship_type,
        "unit": unit,
        "platform": platform
    }

    if platform_group_id:
        search_args["platform_group_id"] = platform_group_id

    # Check if it exists
    exists = True if SocialRelationship.relationship_exists(**search_args) else False

    # If the relationship is not direction check if the opposite exists
    if not directional:
        search_args["from_user"] = to_user
        search_args["to_user"] = from_user

        exists = True if SocialRelationship.relationship_exists(**search_args) else False

    # Create the relationship if it doesn't already exist
    if not exists:
        sr = SocialRelationship(unit=unit, platform=platform, platform_group_id=platform_group_id,
                                type=relationship_type, from_user=from_user, to_user=to_user)
        sr.save()


"""def insert_comment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time,
course_code, platform, platform_url, shared_username=None, shared_displayname=None):
    print "Insert comment -  from %s to %s" % (comment_from_uid,shared_displayname)
    if check_ifnotinlocallrs(course_code, platform, comment_id):
        if shared_displayname is not None:
            stm = socialmedia_builder(verb='commented', platform=platform, account_name=comment_from_uid, account_homepage=platform_url,
            object_type='Note', object_id=comment_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code )
            jsn = ast.literal_eval(stm.to_json())
            stm_json = pretty_print_json(jsn)
            lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='commented', platform=platform, username=get_username_fromsmid(comment_from_name, platform), platformid=comment_id, platformparentid=post_id, parentusername=get_username_fromsmid(shared_displayname,platform), parentdisplayname=shared_displayname, message=comment_message, datetimestamp=comment_created_time)
            lrs.save()
            print "COMMENT SAVED!"
            socialrelationship = SocialRelationship(verb = "commented", fromusername=get_username_fromsmid(comment_from_uid,platform), tousername=get_username_fromsmid(shared_username,platform), platform=platform, message=comment_message, datetimestamp=comment_created_time, course_code=course_code, platformid=comment_id)
            socialrelationship.save()"""

