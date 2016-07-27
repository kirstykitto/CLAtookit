from django.db import connection
from django.contrib.auth.models import User
from clatoolkit.models import UserProfile, UnitOffering, DashboardReflection, LearningRecord, SocialRelationship, CachedContent, Classification
from django.db.models import Q, Count

def check_ifuserincourse(user, course_id):
    if UnitOffering.objects.filter(code=course_id, users=user).count() > 0:
        return True
    else:
        return False

def check_ifnotinlocallrs(course_code, platform, platform_id):
    lrs_matchingstatements = LearningRecord.objects.filter(course_code=course_code, platform=platform, platformid=platform_id)
    if len(lrs_matchingstatements)==0:
        return True
    else:
        return False


#TODO?
def get_userdetails(screen_name, platform):
    usr_dict = {'screen_name':screen_name}
    platform_param_name = None
    #usr = None

    try:
        if platform=='youtube':
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

def username_exists(screen_name, course_code, platform):
    tw_id_exists = False
    platform_param_name = None
    if platform=='youtube':
        platform_param_name = "google_account_name__iexact"
    elif platform == 'github':
        platform_param_name = "github_account_name__iexact"
    elif platform == 'trello':
        platform_param_name = "trello_account_name__iexact"
    elif platform == 'facebook':
        platform_param_name = "fb_id__iexact"
    else:
        platform_param_name = "%s_id__iexact" % (platform.lower())

    kwargs = {platform_param_name:screen_name}
    usrs = UserProfile.objects.filter(**kwargs)
    if len(usrs) > 0:
        usr_prof = usrs[0]
        usr = usr_prof.user
        user_in_course = check_ifuserincourse(usr, course_code)
        if user_in_course:
            tw_id_exists = True
        else:
            tw_id_exists = False
    return tw_id_exists

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
    google_id = user.userprofile.google_account_name
    github_id = user.userprofile.github_account_name
    trello_id = user.userprofile.trello_account_name
    return twitter_id, fb_id, forum_id, google_id, github_id, trello_id

def get_smids_fromusername(username):
    user = User.objects.get(username=username)
    twitter_id = user.userprofile.twitter_id
    fb_id = user.userprofile.fb_id
    forum_id = user.userprofile.forum_id
    google_id = user.userprofile.google_account_name
    github_id = user.userprofile.github_account_name
    return twitter_id, fb_id, forum_id, google_id, github_id



