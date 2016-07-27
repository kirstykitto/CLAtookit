from django import forms
from django.contrib.auth.models import User
import django_filters
from django.core.exceptions import ValidationError
from clatoolkit.models import UserProfile, UnitOffering, LearningRecord, SocialRelationship, Classification, UserClassification

class UserForm(forms.ModelForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    email = forms.CharField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    units = forms.ModelMultipleChoiceField(queryset=UnitOffering.objects.filter(enabled=True), widget=forms.SelectMultiple(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'units')

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

            print 'FACEBOOK ID: %s' % (self.cleaned_data.get('fb_id'))
            print self.cleaned_data.get('fb_id') == ''
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
        fields = ('id', 'course_code', 'platform', 'verb', 'username', 'platformid', 'platformparentid', 'parentusername', 'message', 'datetimestamp', 'senttolrs', 'datetimestamp_min', 'datetimestamp_max')

class SocialRelationshipFilter(django_filters.FilterSet):
    datetimestamp_min = django_filters.DateFilter(name='datetimestamp', lookup_type='gte')
    datetimestamp_max = django_filters.DateFilter(name='datetimestamp', lookup_type='lte')

    class Meta:
        model = SocialRelationship
        fields = ('id', 'course_code', 'platform', 'verb', 'fromusername', 'tousername', 'platformid', 'message', 'datetimestamp', 'datetimestamp_min', 'datetimestamp_max')

class ClassificationFilter(django_filters.FilterSet):

    class Meta:
        model = Classification
        fields = ('id', 'xapistatement', 'classification', 'classifier')

class UserClassificationFilter(django_filters.FilterSet):

    class Meta:
        model = UserClassification
        fields = ('id', 'classification', 'username', 'isclassificationcorrect', 'userreclassification', 'feedback', 'feature')
