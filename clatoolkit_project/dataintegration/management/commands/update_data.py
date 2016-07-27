from django.core.management.base import BaseCommand, CommandError
from clatoolkit.models import *
from dashboard.utils import classify

#urllib2 to send update requests
import requests

def base_URI():
    return 'http://localhost:8000/dataintegration/'

def get_new_course_settings():
    return {
        'facebook' : None,
        'twitter' : None,
        'google' : None,
        'forum' : None,
        'youtube' : None,
        'blog' : None,
        'diigo' : None,
        'coi' : False,
        'coi_platforms' : []
    }

def get_new_course_config():
    return {'course' : None, 'settings': get_new_course_settings()}

class Command(BaseCommand):
    help = 'Fetches and Updates all data for all courses using CLAToolkit'

    def add_arguments(self, parser):
        #parser.add_argument('course_code', nargs='+', help='Update specified course_code')

        parser.add_argument(
            '--all',
            action='store_true',
            dest='all',
            default=False,
            help='Update All courses in Toolkit',
        )

    def handle(self, *args, **kwargs):

        if kwargs['all']:
            try:
                courses = UnitOffering.objects.all()
            except UnitOffering.DoesNotExist:
                raise CommandError('Unit Error.... does not exist.')

            for course in courses:
                COURSE_SETTINGS = get_new_course_settings()
                course_code = course.code
                #Check unitoffering for attached SM
                if len(course.twitter_hashtags_as_list()) > 0:
                    #TODO: Fix Twitter AuthFlow?
                    COURSE_SETTINGS['twitter'] = False
                if len(course.google_groups) > 0:
                    COURSE_SETTINGS['google'] = True
                if len(course.facebook_groups_as_list()) > 0:
                    COURSE_SETTINGS['facebook'] = True
                if len(course.forum_urls_as_list()) > 0:
                    COURSE_SETTINGS['forum'] = True
                if len(course.youtube_channelIds_as_list()) > 0:
                    #TODO: Test Youtube Flow works as intended
                    COURSE_SETTINGS['youtube'] = False
                if len(course.diigo_tags_as_list()) > 0:
                    COURSE_SETTINGS['diigo'] = True
                if len(course.blogmember_urls_as_list()) > 0:
                    COURSE_SETTINGS['blog'] = True
                if course.enable_coi_classifier is True:
                    COURSE_SETTINGS['coi'] = True

                    #TODO: Update to retreive platforms from course.coi_platforms once new roll-out is on production
                    COURSE_SETTINGS['coi_platforms'].append('Blog')


                #Refresh data for SM used in Unit
                if COURSE_SETTINGS['twitter']:
                    hashtag_list = ",".join(course.twitter_hashtags_as_list())
                    url_str = base_URI()+'refreshtwitter/?course_code='+course_code+'&hashtags='+hashtag_list
                    r = requests.get(url_str)
                    if r.status_code is not 200:
                        raise CommandError('Error encountered during twitter update. HTTP Status Code: %s' % r.status_code)

                if COURSE_SETTINGS['google']:
                    raise NotImplementedError

                if COURSE_SETTINGS['facebook']:
                    context = '{ "platform" : "facebook", "course_code" : "'+course_code+'", "group" : "'+course.facebook_groups_as_list()[0]+'" }'
                    url_str = base_URI()+'dipluginauthomaticlogin/?context='+context
                    r = requests.get(url_str)
                    if r.status_code is not 200:
                        raise CommandError('Error encountered during facebook update. HTTP Status Code: %s' % r.status_code)

                if COURSE_SETTINGS['blog']:
                    #TODO: Modularize urls
                    url_str = base_URI()+'refreshblog/?course_code='+course_code+'&urls=http://2016.socialtechnologi.es/student-blogs/'
                    r = requests.get(url_str)
                    if r.status_code is not 200:
                        raise CommandError('Error encountered during blog update. HTTP Status Code: %s' % r.status_code)

                if COURSE_SETTINGS['diigo']:
                    raise NotImplementedError

                if COURSE_SETTINGS['youtube']:
                    raise NotImplementedError

                if COURSE_SETTINGS['forum']:
                    raise NotImplementedError

                if COURSE_SETTINGS['coi']:
                    for platform in COURSE_SETTINGS['coi_platforms']:
                        classify(course_code, platform)





