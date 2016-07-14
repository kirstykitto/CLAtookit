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

def socialmedia_builder(verb, platform, account_name, account_homepage, object_type, object_id, message, tags=[], parent_object_type=None, parent_id=None, rating=None, instructor_name=None, instructor_email=None, team_name=None, course_code=None, account_email=None, user_name=None, timestamp=None, otherObjTypeName=None, grand_parent=None):
    verbmapper = {'created': 'http://activitystrea.ms/schema/1.0/create', 'shared': 'http://activitystrea.ms/schema/1.0/share', 'liked': 'http://activitystrea.ms/schema/1.0/like', 'rated': 'http://id.tincanapi.com/verb/rated', 'commented': 'http://adlnet.gov/expapi/verbs/commented', 'added': 'http://adlnet.gov/expapi/verbs/added', 'updated': 'http://adlnet.gov/expapi/verbs/updated', 'removed': 'http://adlnet.gov/expapi/verbs/removed'}
    objectmapper = {'Note': 'http://activitystrea.ms/schema/1.0/note', 'Tag': 'http://id.tincanapi.com/activitytype/tag', 'Article': 'http://activitystrea.ms/schema/1.0/article', 'Video': 'http://activitystrea.ms/schema/1.0/video', 'Bookmark': 'http://activitystrea.ms/schema/1.0/bookmark', 'Collection': 'http://activitystrea.ms/schema/1.0/collection', 'File': 'http://activitystrea.ms/schema/1.0/file'}

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

    if otherObjTypeName is not None:
        otherObject = Activity(
            id=object_id,
            object_type=object_type,
            definition=ActivityDefinition(
                name=LanguageMap({'en-US': otherObjTypeName}),
                type=objectmapper[object_type]
            ),
        )
        taglist.append(otherObject)
    if object_type == 'File':
        otherObject = Activity(
            id=grand_parent,
            object_type=object_type
        )
        taglist.append(otherObject)


    parentlist = []
    if (verb in ['liked','shared','commented','rated']):
        parentobject = Activity(
            id=parent_id,
            object_type=parent_object_type,
            )
        parentlist.append(parentobject)
    elif (platform == 'GitHub'):
        parentobject = Activity(
            id=parent_id,
            object_type=parent_object_type,
            )
        parentlist.append(parentobject)

    courselist = []
    if (course_code is not None):
        courseobject = Activity(
            id=course_code,
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


def insert_post(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmedia_builder(verb='created', platform=platform, account_name=from_uid, account_homepage=platform_url, object_type='Note', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_name, course_code=course_code, tags=tags)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=get_username_fromsmid(from_uid, platform), platformid=post_id, message=message, datetimestamp=created_time)
        lrs.save()
        for tag in tags:
            if tag[0]=="@":
                socialrelationship = SocialRelationship(verb = "mentioned", fromusername=get_username_fromsmid(from_uid,platform), tousername=get_username_fromsmid(tag[1:],platform), platform=platform, message=message, datetimestamp=created_time, course_code=course_code, platformid=post_id)
                socialrelationship.save()

def insert_blogpost(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmedia_builder(verb='created', platform=platform, account_name=from_uid, account_homepage=platform_url, object_type='Article', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_name, course_code=course_code, tags=tags)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=get_username_fromsmid(from_uid, platform), platformid=post_id, message=message, datetimestamp=created_time)
        lrs.save()
        for tag in tags:
            if tag[0]=="@":
                socialrelationship = SocialRelationship(verb = "mentioned", fromusername=get_username_fromsmid(from_uid,platform), tousername=get_username_fromsmid(tag[1:],platform), platform=platform, message=message, datetimestamp=created_time, course_code=course_code, platformid=post_id)
                socialrelationship.save()

def insert_like(usr_dict, post_id, like_uid, like_name, message, course_code, platform, platform_url, liked_username=None):
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmedia_builder(verb='liked', platform=platform, account_name=like_uid, account_homepage=platform_url, object_type='Note', object_id=post_id, message=message, account_email=usr_dict['email'], user_name=like_name, course_code=course_code)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='liked', platform=platform, username=get_username_fromsmid(like_uid, platform), platformid=post_id, message=message, platformparentid=post_id, parentusername=get_username_fromsmid(liked_username,platform), datetimestamp=created_time)
        lrs.save()
        socialrelationship = SocialRelationship(verb = "liked", fromusername=get_username_fromsmid(like_uid,platform), tousername=get_username_fromsmid(liked_username,platform), platform=platform, message=message, datetimestamp=created_time, course_code=course_code, platformid=post_id)
        socialrelationship.save()

def insert_comment(usr_dict, post_id, comment_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, shared_username=None, shared_displayname=None):
    if check_ifnotinlocallrs(course_code, platform, comment_id):
        if shared_displayname is not None:
            stm = socialmedia_builder(verb='commented', platform=platform, account_name=comment_from_uid, account_homepage=platform_url, object_type='Note', object_id=comment_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code )
            jsn = ast.literal_eval(stm.to_json())
            stm_json = pretty_print_json(jsn)
            lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='commented', platform=platform, username=get_username_fromsmid(comment_from_uid, platform), platformid=comment_id, platformparentid=post_id, parentusername=get_username_fromsmid(shared_username,platform), parentdisplayname=shared_displayname, message=comment_message, datetimestamp=comment_created_time)
            lrs.save()
            socialrelationship = SocialRelationship(verb = "commented", fromusername=get_username_fromsmid(comment_from_uid,platform), tousername=get_username_fromsmid(shared_username,platform), platform=platform, message=comment_message, datetimestamp=comment_created_time, course_code=course_code, platformid=comment_id)
            socialrelationship.save()

def insert_share(usr_dict, post_id, share_id, comment_message, comment_from_uid, comment_from_name, comment_created_time, course_code, platform, platform_url, tags=[], shared_username=None):
    if check_ifnotinlocallrs(course_code, platform, share_id):
        stm = socialmedia_builder(verb='shared', platform=platform, account_name=comment_from_uid, account_homepage=platform_url, object_type='Note', object_id=share_id, message=comment_message, parent_id=post_id, parent_object_type='Note', timestamp=comment_created_time, account_email=usr_dict['email'], user_name=comment_from_name, course_code=course_code, tags=tags )
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='shared', platform=platform, username=get_username_fromsmid(comment_from_uid, platform), platformid=share_id, platformparentid=post_id, parentusername=get_username_fromsmid(shared_username,platform), message=comment_message, datetimestamp=comment_created_time)
        lrs.save()
        socialrelationship = SocialRelationship(verb = "shared", fromusername=get_username_fromsmid(comment_from_uid,platform), tousername=get_username_fromsmid(shared_username,platform), platform=platform, message=comment_message, datetimestamp=comment_created_time, course_code=course_code, platformid=share_id)
        socialrelationship.save()

def insert_bookmark(usr_dict, post_id,message,from_name,from_uid, created_time, course_code, platform, platform_url, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, post_id):
        stm = socialmedia_builder(verb='created', platform=platform, account_name=from_uid, account_homepage=platform_url, object_type='Bookmark', object_id=post_id, message=message, timestamp=created_time, account_email=usr_dict['email'], user_name=from_name, course_code=course_code, tags=tags)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(xapi=stm_json, course_code=course_code, verb='created', platform=platform, username=get_username_fromsmid(from_uid, platform), platformid=post_id, message=message, datetimestamp=created_time)
        lrs.save()

def insert_commit(usr_dict, commit_id, message, from_uid, from_name, committed_time, course_code, parent_id, platform, platform_id, commit_username=None, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, commit_id):
        verb = "created"
        object = "Collection"
        parentObj = "Collection"
        otherObjTypeName = "commit"

        stm = socialmedia_builder(
            verb=verb, platform=platform, account_name=from_uid, 
            account_homepage=platform_id, object_type=object, object_id=commit_id, 
            message=message, tags=tags, parent_object_type=parentObj, parent_id=parent_id, 
            timestamp=committed_time, account_email=usr_dict['email'], 
            user_name=from_name, course_code=course_code, otherObjTypeName=otherObjTypeName)

        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(
            xapi=stm_json, course_code=course_code, verb=verb, 
            platform=platform, username=get_username_fromsmid(from_uid, platform), 
            platformid=platform_id, platformparentid=parent_id, 
            parentusername=get_username_fromsmid(commit_username, platform), 
            message=message, datetimestamp=committed_time)
        lrs.save()
        socialrelationship = SocialRelationship(
            verb = verb, 
            fromusername=get_username_fromsmid(from_uid, platform), 
            tousername=get_username_fromsmid(commit_username, platform), 
            platform=platform, message=message, datetimestamp=committed_time, 
            course_code=course_code, platformid=commit_id)
        socialrelationship.save()


def insert_file(usr_dict, file_id, message, from_uid, from_name, committed_time, course_code, parent_id, platform, platform_id, platform_parentid, verb, repoUrl, additions, deletions, commit_username=None, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, file_id):
        object = "File"
        parentObj = "Collection"

        stm = socialmedia_builder(
            verb=verb, platform=platform, account_name=from_uid, 
            account_homepage=platform_id, object_type=object, object_id=file_id, 
            message=message, tags=tags, parent_object_type=parentObj, parent_id=parent_id, 
            timestamp=committed_time, account_email=usr_dict['email'], 
            user_name=from_name, course_code=course_code, grand_parent=repoUrl)

        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(
            xapi=stm_json, course_code=course_code, verb=verb, 
            platform=platform, username=get_username_fromsmid(from_uid, platform), 
            platformid=platform_id, platformparentid=platform_parentid, 
            parentusername=get_username_fromsmid(commit_username, platform), 
            message=message, datetimestamp=committed_time, numofcontentadd=additions, numofcontentdel=deletions)
        lrs.save()
        socialrelationship = SocialRelationship(
            verb = verb, 
            fromusername=get_username_fromsmid(from_uid, platform), 
            tousername=get_username_fromsmid(commit_username, platform), 
            platform=platform, message=message, datetimestamp=committed_time, 
            course_code=course_code, platformid=file_id)
        socialrelationship.save()


def insert_issue(usr_dict, issue_id, message, from_name, from_uid, created_time, course_code, parent_id, platform, platform_id, assignee, tags=[]):
    if check_ifnotinlocallrs(course_code, platform, issue_id):
        verb = 'created'
        object = "Note"
        parentObj = "Collection"

        stm = socialmedia_builder(
            verb=verb, platform=platform, account_name=from_uid, 
            account_homepage=issue_id, object_type=object, object_id=issue_id, 
            message=message, parent_object_type=parentObj, parent_id=parent_id, 
            timestamp=created_time, account_email=usr_dict['email'], 
            user_name=from_name, course_code=course_code, tags=tags)
        jsn = ast.literal_eval(stm.to_json())
        stm_json = pretty_print_json(jsn)
        lrs = LearningRecord(
            xapi=stm_json, course_code=course_code, verb=verb, 
            platform=platform, username=get_username_fromsmid(from_uid, platform),
            platformid=platform_id, platformparentid=parent_id, message=message, datetimestamp=created_time,
            parentusername=get_username_fromsmid(assignee, platform))
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