from django import forms
from django.contrib.auth.models import User
import django_filters
from django.core.exceptions import ValidationError
from clatoolkit.models import UserProfile, UnitOffering, LearningRecord, SocialRelationship, Classification, UserClassification, ClientApp
import re

class UserForm(forms.ModelForm):
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    email = forms.CharField(widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password')


class SignUpForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    email = forms.CharField(widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "password")

class RegisterClientAppForm(forms.ModelForm):
    i = forms.CharField(label='OAuth client apps key', widget=forms.TextInput(attrs={'class': 'form-control'}))
    s = forms.CharField(label='OAuth client apps secret', widget=forms.TextInput(attrs={'class': 'form-control'}))
    provider = forms.CharField(label='LRS name (e.g. mylrs)', widget=forms.TextInput(attrs={'class': 'form-control'}))
    app_name = forms.CharField(label='Client application name registered on your LRS', widget=forms.TextInput(attrs={'class': 'form-control'}))
    domain = forms.CharField(label='Domain (e.g. my.lrsdomain.com)', widget=forms.TextInput(attrs={'class': 'form-control'}))
    port = forms.IntegerField(label='Port number', widget=forms.TextInput(attrs={'class': 'form-control'}))
    auth_request_path = forms.CharField(label='Auth request path (e.g. /OAuth/initiate)',
        widget=forms.TextInput(attrs={'class': 'form-control'}))
    access_token_path = forms.CharField(label='Access token path (e.g. /OAuth/token)',
        widget=forms.TextInput(attrs={'class': 'form-control'}))
    authorization_path = forms.CharField(label='Authorization path (e.g. /OAuth/authorize)',
        widget=forms.TextInput(attrs={'class': 'form-control'}))
    xapi_statement_path = forms.CharField(label='xAPI statement path (e.g. /xapi/statements)',
        widget=forms.TextInput(attrs={'class': 'form-control'}))
    reg_lrs_account_path = forms.CharField(label='LRS account registeration path (e.g. /regclatoolkitu/)',
        widget=forms.TextInput(attrs={'class': 'form-control'}))

    protocol_choice = (
        ('http', 'http'),
        ('https', 'https')
    )
    protocol = forms.ChoiceField(label='Protocol', choices=protocol_choice)

    class Meta:
        model = ClientApp
        fields = ("provider", "app_name", "i", "s", "protocol", "domain", "port",
                    "auth_request_path", "access_token_path", "authorization_path",
                    "xapi_statement_path", "reg_lrs_account_path")

class CreateOfferingForm(forms.ModelForm):
    code = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    semester = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    provider = forms.CharField(label='LRS', widget=forms.TextInput(attrs={'class': 'form-control'}))
    start_date = forms.DateField(label='Start Date',
        widget=forms.DateInput(attrs={'class': 'form-control'}), input_formats=['%d / %m / %Y'])
    end_date = forms.DateField(label='End Date',
        widget=forms.DateInput(attrs={'class': 'form-control'}), input_formats=['%d / %m / %Y'])
    co_analysis = forms.BooleanField(label='Content Analysis Dashboard ON/OFF', required=False, initial={'co_analysis':True})
    sn_analysis = forms.BooleanField(label='Social Network Analysis Dashboard ON/OFF', required=False, initial={'sn_analysis':True})
    enable_coi_classifier = forms.BooleanField(label='Community of Inquiry Classifications Dashboard ON/OFF', 
                                               required=False, initial={'enable_coi_classifier':True})

    class Meta:
        model = UnitOffering
        fields = ("code", "name", "semester", "description", "twitter_hashtags", "google_groups", 
            "facebook_groups", "forum_urls", "youtube_channelIds", "diigo_tags", "blogmember_urls", 
            "github_urls", "attached_trello_boards", "provider", "start_date", "end_date",
            "co_analysis", "sn_analysis", "enable_coi_classifier")

    def clean(self):
        code = self.cleaned_data.get('code')
        if not re.match(r'^[a-zA-Z0-9_-]+$', code):
            self._errors['code'] = self.error_class(['Alphabet, number, hyphen and under score are available.'])

        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        if start_date and end_date and start_date >= end_date:
            self._errors['start_date'] = self.error_class(['Start date must be earlier than end date.'])

        return self.cleaned_data

class SocialMediaUpdateForm(forms.ModelForm):
    fb_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    twitter_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    forum_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    google_account_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    diigo_username = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    blog_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    github_account_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    trello_account_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def clean(self):
        if not ((self.cleaned_data.get('fb_id'))
            or (self.cleaned_data.get('twitter_id')) or (self.cleaned_data.get('forum_id'))
            or (self.cleaned_data.get('blog_id')) or (self.cleaned_data.get('google_account_name'))
            or (self.cleaned_data.get('diigo_username')) or (self.cleaned_data.get('github_account_name'))
            or (self.cleaned_data.get('trello_account_name'))
            ):

            raise ValidationError("At least one social media account must be added.")
        return self.cleaned_data

    class Meta:
        model = UserProfile
        fields = ('fb_id', 'twitter_id', 'forum_id', 'google_account_name', 'diigo_username', 'blog_id', 'github_account_name', 'trello_account_name')

class UserProfileForm(forms.ModelForm):
    fb_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    twitter_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    forum_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    google_account_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    diigo_username = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    blog_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    github_account_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    trello_account_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def clean(self):
        if not ((self.cleaned_data.get('fb_id'))
            or (self.cleaned_data.get('twitter_id')) or (self.cleaned_data.get('forum_id'))
            or (self.cleaned_data.get('blog_id')) or (self.cleaned_data.get('google_account_name'))
            or (self.cleaned_data.get('diigo_username')) or (self.cleaned_data.get('github_account_name'))
            or (self.cleaned_data.get('trello_account_name'))
            ):

            raise ValidationError("At least one social media account must be added.")
        else:
            #Not blank so now check if the platform ids are already registeres to a User
            fb_registered = UserProfile.objects.filter(fb_id__iexact=self.cleaned_data.get('fb_id'))
            tw_registered = UserProfile.objects.filter(twitter_id__iexact=self.cleaned_data.get('twitter_id'))
            gg_registered = UserProfile.objects.filter(google_account_name__iexact=self.cleaned_data.get('google_account_name'))
            fr_registered = UserProfile.objects.filter(forum_id__iexact=self.cleaned_data.get('forum_id'))
            bl_registered = UserProfile.objects.filter(blog_id__iexact=self.cleaned_data.get('blog_id'))
            gh_registered = UserProfile.objects.filter(forum_id__iexact=self.cleaned_data.get('github_account_name'))
            tl_registered = UserProfile.objects.filter(trello_account_name__iexact=self.cleaned_data.get('trello_account_name'))

           #print 'FACEBOOK ID: %s' % (self.cleaned_data.get('fb_id'))
#           print self.cleaned_data.get('fb_id') == ''
           # print self.cleaned_data.get('fb_id') is None
           # print self.cleaned_data.get('fb_id') is True
           # print self.cleaned_data.get('fb_id') is False

            if len(fb_registered)>0 and not self.cleaned_data.get('fb_id')  == '' or None:
                raise ValidationError("The specified Facebook Account is already registered.")
            elif len(tw_registered)>0 and not self.cleaned_data.get('twitter_id') == '' or None:
                raise ValidationError("The specified Twitter Account is already registered.")
            elif len(gg_registered)>0 and not self.cleaned_data.get('google_account_name') == '' or None:
                raise ValidationError("The specified YouTube Account is already registered.")
            elif len(fr_registered)>0 and not self.cleaned_data.get('course.code') == 'IFN614' and not self.cleaned_data.get('forum_id') == '' or None:
                raise ValidationError("The specified Wordpress Forum ID is already registered.")
            elif len(bl_registered)>0 and not self.cleaned_data.get('blog_id') == '' or None:
                raise ValidationError("The specified Wordpress Blog username is already registered.")
            elif len(gh_registered)>0 and not self.cleaned_data.get('github_account_name') == '' or None:
                raise ValidationError("The specified GitHub Account ID is already registered.")
            elif len(tl_registered)>0 and not self.cleaned_data.get('trello_account_name') == '' or None:
                raise ValidationError("The specified Trello account ID is alreayd registered.")

        return self.cleaned_data

    class Meta:
        model = UserProfile
        fields = ('fb_id', 'twitter_id', 'forum_id', 'google_account_name', 'diigo_username', 'blog_id', 'github_account_name', 'trello_account_name')


class LearningRecordFilter(django_filters.FilterSet):
    datetimestamp_min = django_filters.DateFilter(name='datetimestamp', lookup_type='gte')
    datetimestamp_max = django_filters.DateFilter(name='datetimestamp', lookup_type='lte')

    class Meta:
        model = LearningRecord
        fields = ('id', 'unit', 'platform', 'verb', 'user', 'platformid', 'platformparentid')


class SocialRelationshipFilter(django_filters.FilterSet):
    datetimestamp_min = django_filters.DateFilter(name='datetimestamp', lookup_type='gte')
    datetimestamp_max = django_filters.DateFilter(name='datetimestamp', lookup_type='lte')

    class Meta:
        model = SocialRelationship
        fields = ('id', 'unit', 'platform', 'verb', 'from_user', 'to_user', 'to_external_user', 'platformid', 'message',
                  'datetimestamp', 'datetimestamp_min', 'datetimestamp_max')


class ClassificationFilter(django_filters.FilterSet):

    class Meta:
        model = Classification
        fields = ('id', 'xapistatement', 'classification', 'classifier')

class UserClassificationFilter(django_filters.FilterSet):

    class Meta:
        model = UserClassification
        fields = ('id', 'classification', 'username', 'isclassificationcorrect', 'userreclassification', 'feedback', 'feature')
