

from django.db import connection
from django.contrib.auth.models import User
from clatoolkit.models import UserProfile, UnitOffering, UnitOfferingMembership, DashboardReflection, LearningRecord, SocialRelationship, CachedContent, Classification
from django.db.models import Q, Count
import uuid
from common.util import Utility


def get_user_from_screen_name(screen_name, platform):
    platform_name = platform.lower()
    platform_param_name = None
    if platform_name == 'youtube':
        platform_param_name = "google_account_name__iexact"
    elif platform_name == 'github':
        platform_param_name = "github_account_name__iexact"
    elif platform_name == 'trello':
        platform_param_name = "trello_account_name__iexact"
    elif platform_name == 'facebook':
        platform_param_name = "fb_id__iexact"
    else:
        platform_param_name = "%s_id__iexact" % platform_name

    kwargs = {platform_param_name: screen_name}

    user = None
    try:
        user = UserProfile.objects.get(**kwargs).user
    except UserProfile.DoesNotExist:
        # print 'screen_name %s does not exist. Platform: %s' % (screen_name, platform)
        pass
        
    return user


def get_smid(user, platform):
    profile = user.userprofile

    platform_name = platform.lower()

    if platform_name == 'youtube':
        platform_param_name = "google_account_name"
    elif platform_name == 'github':
        platform_param_name = "github_account_name"
    elif platform_name == 'trello':
        platform_param_name = "trello_account_name"
    elif platform_name == 'facebook':
        platform_param_name = "fb_id"
    else:
        platform_param_name = "{}_id".format(platform_name)

    return getattr(profile, platform_param_name)


def check_ifuserincourse(user, course_id):
    if UnitOffering.objects.filter(code=course_id, users=user).count() > 0:
        return True
    else:
        return False


# TODO - update all usages to unit
def check_ifnotinlocallrs(unit, platform, platform_id, user=None, verb=None):
    try:
        if user and verb:
            LearningRecord.objects.get(unit=unit, platform=platform, platformid=platform_id, user=user, verb=verb)
        elif user:
            LearningRecord.objects.get(unit=unit, platform=platform, platformid=platform_id, user=user)
        elif verb:
            LearningRecord.objects.get(unit=unit, platform=platform, platformid=platform_id, verb=verb)
        else:
            LearningRecord.objects.get(unit=unit, platform=platform, platformid=platform_id)
    except LearningRecord.DoesNotExist:
        return True

    return False


# TODO - remove test data
def get_userdetails(screen_name, platform):
    usr_dict = {'screen_name':screen_name}
    platform_param_name = None
    #usr = None

    try:
        if platform.lower()=='youtube':
            platform_param_name = "google_account_name__iexact"
        elif platform == 'github':
            platform_param_name = "github_account_name__iexact"
        elif platform == 'facebook':
            platform_param_name = "fb_id__iexact"
        elif platform == 'trello':
            platform_param_name = "trello_account_name__iexact"
        else:
            platform_param_name = "%s_id__iexact" % (platform.lower())
        kwargs = {platform_param_name:screen_name}
        usrs = UserProfile.objects.filter(**kwargs)
        usr = usrs[0]
    except UserProfile.DoesNotExist:
        usr = None

    if usr is not None:
        if usr.user.email != "":
            usr_dict['email'] = usr.user.email
        else:
            usr_dict['email'] = None
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


# TODO - Update all usages to use unit instead
def username_exists(screen_name, unit, platform):
    try:
        user = get_user_from_screen_name(screen_name, platform)
        membership = UnitOfferingMembership.objects.get(user=user, unit=unit)
    except (UserProfile.DoesNotExist, UnitOfferingMembership.DoesNotExist):
        return False

    return True


def get_uid_fromsmid(username, platform):
    userprofile = None
    if platform == "twitter":
        userprofile = UserProfile.objects.filter(twitter_id__iexact=username)
    elif platform == "facebook":
        userprofile = UserProfile.objects.filter(fb_id__iexact=username)
    elif platform == "forum":
        userprofile = UserProfile.objects.filter(forum_id__iexact=username)
    elif platform == "youtube":
        userprofile = UserProfile.objects.filter(google_account_name__iexact=username)
    elif platform == "github":
        userprofile = UserProfile.objects.filter(github_account_name__iexact=username)
    elif platform == "trello":
        userprofile = UserProfile.objects.filter(trello_account_name__iexact=username)
    elif platform == "blog":
        userprofile = UserProfile.objects.filter(blog_id__iexact=username)
    else:
        #platform must be = all
        userprofile = UserProfile.objects.filter(Q(twitter_id__iexact=username) | Q(fb_id__iexact=username) | Q(forum_id__iexact=username) | Q(google_account_name__iexact=username))

    id = userprofile[0].user.id
    return id

def get_username_fromsmid(sm_id, platform):
    #print "sm_id", sm_id
    userprofile = None
    if platform == "twitter":
        userprofile = UserProfile.objects.filter(twitter_id__iexact=sm_id)
    elif platform == "facebook":
        userprofile = UserProfile.objects.filter(fb_id__iexact=sm_id)
    elif platform == "forum":
        userprofile = UserProfile.objects.filter(forum_id__iexact=sm_id)
    elif platform == "youtube":
            userprofile = UserProfile.objects.filter(google_account_name__iexact=sm_id)
    elif platform == "github":
        userprofile = UserProfile.objects.filter(github_account_name__iexact=sm_id)
    elif platform == 'trello':
        userprofile = UserProfile.objects.filter(trello_account_name__iexact=sm_id)
    elif platform.lower() == 'blog':
        userprofile = UserProfile.objects.filter(blog_id__iexact=sm_id)

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
    blog_id = user.userprofile.blog_id
    google_id = user.userprofile.google_account_name
    github_id = user.userprofile.github_account_name
    trello_id = user.userprofile.trello_account_name
    return twitter_id, fb_id, forum_id, blog_id, google_id, github_id, trello_id

def get_smids_fromusername(username):
    user = User.objects.get(username=username)
    twitter_id = user.userprofile.twitter_id
    fb_id = user.userprofile.fb_id
    forum_id = user.userprofile.forum_id
    google_id = user.userprofile.google_account_name
    github_id = user.userprofile.github_account_name
    return twitter_id, fb_id, forum_id, google_id, github_id

def get_uuid4():
    return str(uuid.uuid4())


def get_youtube_callback_url(request):
    return Utility.get_site_url(request) + '/dataintegration/ytAuthCallback'


def get_youtube_user_channel_url(request):
    return Utility.get_site_url(request) + '/dataintegration/showyoutubechannel'