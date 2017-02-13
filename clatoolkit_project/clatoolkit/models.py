import os
from django.db import models
from django.contrib.auth.models import User
from django_pgjson.fields import JsonField
from django.core.exceptions import ObjectDoesNotExist
from xapi.statement.xapi_settings import xapi_settings
from xapi.models import ClientApp
#from dashboard.models import al2_classifier

class UserProfile(models.Model):
    '''
    Custom user for data integration, uses Django's User class.
    '''
    user = models.OneToOneField(User)

    # Simple role as an alternative to django groups and permissions
    STAFF = 'Staff'
    STUDENT = 'Student'
    VISITOR = 'Visitor'
    ROLETYPE_OPTIONS = (
        (STAFF, STAFF),
        (STUDENT, STUDENT),
        (VISITOR, VISITOR)
    )
    role = models.CharField(max_length=100, choices=ROLETYPE_OPTIONS, default=STUDENT)

    # LRS Integration - to send users data to personal LRS
    #ll_endpoint = models.CharField(max_length=60)
    #ll_username = models.CharField(max_length=60)
    #ll_password = models.CharField(max_length=60)

    # Facebook Integration - users facebook id is required
    fb_id = models.CharField(max_length=30, blank=True)

    # Twitter Integration - users Twitter handle (username) is required
    twitter_id = models.CharField(max_length=30, blank=True)

    # Forum Scraping - users Forum handle (username) is required
    forum_id = models.CharField(max_length=500, blank=True)

    # Google Integration - users Google xxx is required for Youtube, etc...
    # Todo - Add Google API user credential requirements below
    # YouTube 26/08/2015
    google_account_name = models.CharField(max_length=255, blank=True)

    #Diigo userName
    diigo_username = models.CharField(max_length=255, blank=True)

    #blog userName
    blog_id = models.CharField(max_length=255, blank=True)

    #GitHub user account
    github_account_name = models.CharField(max_length=255, blank=True)

    #Trello user ID
    trello_account_name = models.CharField(max_length=255, blank=True)

    def get_username_for_platform(self,platform):
        platform_map = {
            'twitter':self.twitter_id,
            'facebook':self.fb_id,
            'forum':self.forum_id,
            'youtube':self.google_account_name,
            'blog':self.blog_id,
            'github':self.github_account_name,
            'trello':self.trello_account_name
        }

        return platform_map[platform.lower()]

class OfflinePlatformAuthToken(models.Model):
    user_smid = models.CharField(max_length=1000, blank=False)
    token = models.CharField(max_length=1000, blank=False)
    platform = models.CharField(max_length=1000, blank=False)

class UnitOffering(models.Model):
    code = models.CharField(max_length=5000, blank=False, verbose_name="Unit Code", unique=True)
    name = models.CharField(max_length=5000, blank=False, verbose_name="Unit Name")
    semester = models.CharField(max_length=5000, blank=False)
    description = models.TextField(blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(User, related_name='usersinunitoffering', through='UnitOfferingMembership')
    # determines whether unit should be displayed on Register form and on dashboard
    enabled = models.BooleanField(blank=False, default=True)
    # determines whether unit should be displayed on EventRegistration Form
    event = models.BooleanField(blank=False, default=False)
    # determines whether COI Classifier link should be diplayed for staff and student in a unit
    enable_coi_classifier = models.BooleanField(default=False)
    #enable_group_coi_classifier = models.BooleanField(default=False)

    #al_classifiers = models.CharField(max_length=255, blank=True)

    #def get_al_classifiers():
    #    return self.al_classifiers.split(',')

    # Twitter Unit Integration Requirements
    twitter_hashtags = models.TextField(blank=False,verbose_name="Twitter Hashtags")

    # Google Unit Integration Requirements
    google_groups = models.TextField(blank=True, verbose_name="Google Groups")

    # Facebook Unit Integration Requirements
    facebook_groups = models.TextField(blank=True, verbose_name="Facebook Groups")

    # Unit External Forums
    forum_urls = models.TextField(blank=True, verbose_name="Forum URLs")

    # YouTube 26/08/2015
    youtube_channelIds = models.TextField(blank=True, verbose_name="Youtube Channels")

    # Diigo Tags
    diigo_tags = models.TextField(blank=True, verbose_name="Diigo Tags")

    # Blog Members (for blogrss plugin)
    blogmember_urls = models.TextField(blank=True, verbose_name="Blog Member URLs")

    # GitHub Repository URLs
    github_urls = models.TextField(blank=True, verbose_name="GitHub Repos")

    # Trello board IDs
    attached_trello_boards = models.TextField(blank=True, verbose_name="Trello Boards")

    # Determines which platforms should be utilized by COI classifier
    coi_platforms = models.TextField(blank=True)
    # Unit start date
    start_date = models.DateField(auto_now=False, auto_now_add=False, blank=False)
    # Unit end date
    end_date = models.DateField(auto_now=False, auto_now_add=False, blank=False)

    # Content Analysis on/off
    co_analysis = models.BooleanField(default=True, blank=False)
    # Social Network Analysis on/off
    sn_analysis = models.BooleanField(default=True, blank=False)

    # LRS Integration - to send users data to unit LRS
    #ll_endpoint = models.CharField(max_length=60, blank=True)
    #ll_username = models.CharField(max_length=60, blank=True)
    #ll_password = models.CharField(max_length=60, blank=True)

    lrs_provider = models.ForeignKey(ClientApp)

    def get_lrs(self):
        #lrs  = ClientApp.objects.get(self.lrs_provider)

        return self.lrs_provider

    def __unicode__(self):
        return self.code + " " + self.name

    def trello_boards_as_list(self):
        if self.attached_trello_boards:
            return self.attached_trello_boards.split(',')
        else:
            return []

    def twitter_hashtags_as_list(self):
        if self.twitter_hashtags:
            return self.twitter_hashtags.split(',')
        else:
            return []

    def facebook_groups_as_list(self):
        if self.facebook_groups:
            return self.facebook_groups.split(',')
        else:
            return []

    def forum_urls_as_list(self):
        if self.forum_urls:
            return self.forum_urls.split(',')
        else:
            return []

    def youtube_channelIds_as_list(self):
        if self.youtube_channelIds:
            return self.youtube_channelIds.split(',')
        else:
            return []

    def diigo_tags_as_list(self):
        if self.diigo_tags:
            return self.diigo_tags.split(',')
        else:
            return []

    def blogmember_urls_as_list(self):
        if self.blogmember_urls:
            return self.blogmember_urls.split(',')
        else:
            return []

    def github_urls_as_list(self):
        if self.github_urls:
            return self.github_urls.split(os.linesep)
        else:
            return []

    def github_member_count(self):
        # Count the number of GitHub users in the course
        resources = UserPlatformResourceMap.objects.filter(unit=self.id, platform=xapi_settings.PLATFORM_GITHUB)
        return len(resources)

    def coi_platforms_as_list(self):
        if self.coi_platforms:
            return self.coi_platforms.split(',')
        else:
            return []

    def get_required_platforms(self):
        platforms = []

        if len(self.twitter_hashtags_as_list()):
            platforms.append('twitter')
        if len(self.facebook_groups_as_list()):
            platforms.append('facebook')
        if len(self.forum_urls_as_list()):
            platforms.append('forum')
        if len(self.youtube_channelIds_as_list()):
            platforms.append('youtube')
        if len(self.diigo_tags_as_list()):
            platforms.append('diigo')
        if len(self.blogmember_urls_as_list()):
            platforms.append('blog')
        if len(self.github_urls_as_list()):
            platforms.append('github')
        if len(self.trello_boards_as_list()):
            platforms.append('trello')

        return platforms

    def get_lrs_id(self):
        return self.lrs_provider.id

    def get_lrs_key(self):
        return self.lrs_provider.get_key()

    def get_lrs_secret(self):
        return self.lrs_provider.get_secret()

    def get_lrs_access_token_url(self):
        return self.lrs_provider.get_access_token_url()

    def get_cca_dashboard_params(self):
        params = []
        if self.github_member_count() > 0:
            params.append(xapi_settings.PLATFORM_GITHUB)
        if len(self.trello_boards_as_list()) > 0:
            params.append(xapi_settings.PLATFORM_TRELLO)

        return ','.join(params)


class OauthFlowTemp(models.Model):
    googleid = models.CharField(max_length=1000, blank=False)
    platform = models.CharField(max_length=1000, blank=True)
    transferdata = models.CharField(max_length=1000, blank=True)
    unit = models.ForeignKey(UnitOffering)
    user = models.ForeignKey(User)


class UnitOfferingMembership(models.Model):
    user = models.ForeignKey(User)
    unit = models.ForeignKey(UnitOffering)
    admin = models.BooleanField(default=False)

    @classmethod
    def is_admin(cls, user, unit):
        try:
            return cls.objects.get(user=user, unit=unit).admin
        except ObjectDoesNotExist:
            return False


class LearningRecord(models.Model):
    statement_id = models.CharField(max_length=256, blank=False)
    platformid = models.CharField(max_length=5000, blank=True)
    verb = models.CharField(max_length=50, blank=False)
    platform = models.CharField(max_length=100, blank=False)
    unit = models.ForeignKey(UnitOffering)
    user = models.ForeignKey(User)
    # xapi = JsonField()
    # TODO - Use foreign key to link to parent learning record
    #        Store parent xAPI statement ID here?
    platformparentid = models.CharField(max_length=5000, blank=True)
    parent_user = models.ForeignKey(User, null=True, related_name="parent_user")
    # parent_user_external = models.CharField(max_length=5000, blank=True, null=True)
    # message = models.TextField(blank=True)
    datetimestamp = models.DateTimeField(auto_now_add=False, null=False)
    # senttolrs = models.CharField(max_length=5000, blank=True)


class SocialRelationship(models.Model):
    unit = models.ForeignKey(UnitOffering)
    platform = models.CharField(max_length=5000, blank=False)
    verb = models.CharField(max_length=5000, blank=False)
    from_user = models.ForeignKey(User)
    to_user = models.ForeignKey(User, null=True, related_name="to_user")
    to_external_user = models.CharField(max_length=5000, blank=True, null=True)
    platformid = models.CharField(max_length=5000, blank=True)
    message = models.TextField(blank=False)
    datetimestamp = models.DateTimeField(blank=True)


class CachedContent(models.Model):
    htmltable = models.TextField(blank=False)
    activitytable = models.TextField(blank=True)
    unit = models.ForeignKey(UnitOffering)
    platform = models.CharField(max_length=5000, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

class AccessLog(models.Model):
    url = models.CharField(max_length=10000, blank=False)
    userid = models.CharField(max_length=5000, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Classification(models.Model):
    xapistatement = models.ForeignKey(LearningRecord)
    classification = models.CharField(max_length=1000, blank=False)
    classifier = models.CharField(max_length=1000, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    #classifier_model = models.CharField(max_length=1000, blank=False)


class UserClassification(models.Model):
    classification = models.ForeignKey(Classification)
    username = models.CharField(max_length=5000, blank=False)
    isclassificationcorrect = models.BooleanField(blank=False)
    userreclassification = models.CharField(max_length=1000, blank=False)
    feedback = models.TextField(blank=True)
    feature = models.TextField(blank=True)
    trained = models.BooleanField(blank=False, default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class UserPlatformResourceMap(models.Model):
    user = models.ForeignKey(User)
    unit = models.ForeignKey(UnitOffering)
    resource_id = models.CharField(max_length=5000, blank=False)
    platform = models.CharField(max_length=100, blank=False)

class ApiCredentials(models.Model):
    platform_uid = models.CharField(max_length=5000, blank=False)
    credentials_json = JsonField()

class DashboardReflection(models.Model):
    user = models.ForeignKey(User)
    strategy = models.TextField(blank=False)

    HAPPY = 'Happy'
    SATISFIED = 'Satisfied'
    UNHAPPY = 'Unhappy'
    RATING_OPTIONS = (
        (HAPPY, HAPPY),
        (SATISFIED, SATISFIED),
        (UNHAPPY, UNHAPPY)
    )
    rating = models.CharField(max_length=50, choices=RATING_OPTIONS, default=SATISFIED)
    created_at = models.DateTimeField(auto_now_add=True)
    unit = models.ForeignKey(UnitOffering)

    def __unicode__(self):
        return self.id + ": " + self.username

class GroupMap(models.Model):
    userId = models.ForeignKey(User)
    course_code = models.CharField(max_length=5000, blank=False)
    groupId = models.IntegerField(blank=False)
