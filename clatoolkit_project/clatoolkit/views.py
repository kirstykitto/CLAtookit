from django.shortcuts import render_to_response
from django.shortcuts import redirect

from django.contrib.auth import authenticate, login
from django.http import HttpResponseRedirect, HttpResponse

from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from django.contrib.auth.models import User
from clatoolkit.forms import UserForm, UserProfileForm

from django.template import RequestContext

from clatoolkit.models import UnitOffering, DashboardReflection, LearningRecord, SocialRelationship, Classification, UserClassification, AccessLog

from rest_framework import authentication, permissions, viewsets, filters
from .serializers import LearningRecordSerializer, SocialRelationshipSerializer, ClassificationSerializer, UserClassificationSerializer
from .forms import LearningRecordFilter, SocialRelationshipFilter, ClassificationFilter, UserClassificationFilter

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from dashboard.utils import *
import json

# from fb_data.models import

def userlogin(request):
    context = RequestContext(request)

    if request.method == 'POST':
        print "posted"
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)

        if user:
            # Is the account active? It could have been disabled.
            if user.is_active:
                # If the account is valid and active, we can log the user in.
                # We'll send the user back to the homepage.
                login(request, user)
                #print "sending to myunits"
                return HttpResponseRedirect('/dashboard/myunits/')
            else:
                # An inactive account was used - no logging in!
                return HttpResponse("Your CLAToolkit account is disabled.")
        else:
            # Bad login details were provided. So we can't log the user in.
            #print "Invalid login details: {0}, {1}".format(username, password)
            return HttpResponse("Invalid login details supplied.")

    # The request is not a HTTP POST, so display the login form.
    # This scenario would most likely be a HTTP GET.
    else:
        #print "ordinary get"
        # No context variables to pass to the template system, hence the
        # blank dictionary object...
        return render_to_response('clatoolkit/login.html', {}, context)

def register(request):
    # Like before, get the request's context.
    context = RequestContext(request)

    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False

    # A boolean value used to determine if a unit should already be selected
    show_units = True
    selected_unit = 0
    course = None

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        #print request.POST
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST)

        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            # Save the user's form data to the database.
            user = user_form.save()

            # Now we hash the password with the set_password method.
            # Once hashed, we can update the user object.
            user.set_password(user.password)

            # Assign units to user
            selectedunit = request.GET.get('selectedunit', None)
            if selectedunit is not None:
                user.usersinunitoffering.add(selectedunit)
            else:
                for unit in user_form.cleaned_data['units']:
                    user.usersinunitoffering.add(unit)

            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.role = "Student"

            # Now we save the UserProfile model instance.
            profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            print user_form.errors, profile_form.errors
            course_code = request.POST.get('course_code', None)
            if course_code is not None:
                course = UnitOffering.objects.get(code=course_code)
                show_units = False
                selected_unit = course.id

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        print "loading forms"
        user_form = UserForm()
        profile_form = UserProfileForm()

        course_code = request.GET.get('course_code', None)
        if course_code is not None:
            course = UnitOffering.objects.get(code=course_code)
            show_units = False
            selected_unit = course.id

    # Render the template depending on the context.
    return render_to_response(
        'clatoolkit/register.html',
            {'user_form': user_form, 'profile_form': profile_form, 'registered': registered, 'show_units': show_units, 'selected_unit': selected_unit, "course": course}, context)

@login_required
def socialmediaaccounts(request):
    context = RequestContext(request)
    user_id = request.user.id
    usr_profile = UserProfile.objects.get(user_id=user_id)

    if request.method == 'POST':
        profile_form = UserProfileForm(data=request.POST,instance=usr_profile)

        if profile_form.is_valid():
            profile_form.save()
            return redirect('/dashboard/myunits')
        # Invalid form or forms - mistakes or something else?
        else:
            print user_form.errors, profile_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        profile_form = UserProfileForm(instance=usr_profile)

    # Render the template depending on the context.
    return render_to_response(
        'clatoolkit/socialmediaaccounts.html',
            {'profile_form': profile_form}, context)


def eventregistration(request):
    context = RequestContext(request)

    registered = False

    if request.method == 'POST':
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST)

        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            # Save the user's form data to the database.
            user = user_form.save()

            # Now we hash the password with the set_password method.
            # Once hashed, we can update the user object.
            user.set_password(user.password)

            # Assign units to user
            for unit in user_form.cleaned_data['units']:
                user.usersinunitoffering.add(unit)

            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.role = "Student"

            # Now we save the UserProfile model instance.
            profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            print user_form.errors, profile_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserForm()
        profile_form = UserProfileForm()

    # Render the template depending on the context.
    return render_to_response(
        'clatoolkit/eventregistration.html',
            {'user_form': user_form, 'profile_form': profile_form, 'registered': registered,}, context)

class DefaultsMixin(object):
    """Default settings for view authentication, permissions,
    filtering and pagination."""

    authentication_classes = (
        authentication.SessionAuthentication,
    )

    permission_classes = (
        permissions.IsAuthenticated,
    )
    paginate_by = 300
    paginate_by_param = 'page_size'
    max_paginate_by = 1000

    filter_backends = (
        filters.SearchFilter,
        filters.DjangoFilterBackend,
        filters.OrderingFilter
    )

class LearningRecordViewSet(DefaultsMixin, viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing Learning Records."""

    queryset = LearningRecord.objects.order_by('datetimestamp')
    serializer_class = LearningRecordSerializer
    filter_class = LearningRecordFilter
    search_fields = ('message',)
    ordering_fields = ('datetimestamp')

class SocialRelationshipViewSet(DefaultsMixin, viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing Social Relationships."""

    queryset = SocialRelationship.objects.order_by('datetimestamp')
    serializer_class = SocialRelationshipSerializer
    filter_class = SocialRelationshipFilter
    search_fields = ('message',)
    ordering_fields = ('datetimestamp')

class ClassificationViewSet(DefaultsMixin, viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing Classifications."""

    queryset = Classification.objects.order_by('created_at')
    serializer_class = ClassificationSerializer
    filter_class = ClassificationFilter
    ordering_fields = ('created_at')

class UserClassificationViewSet(DefaultsMixin, viewsets.ModelViewSet):
    """API endpoint for listing and inserting user classifications."""

    queryset = UserClassification.objects.order_by('created_at')
    serializer_class = UserClassificationSerializer
    filter_class = UserClassificationFilter
    ordering_fields = ('created_at')

class SNARESTView(DefaultsMixin, APIView):

    def get(self, request, *args, **kw):

        course_code = request.GET.get('course_code', None)
        platform = request.GET.get('platform', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        username = request.GET.get('username', None)
        relationshipstoinclude = request.GET.get('relationshipstoinclude', None)

        # Any URL parameters get passed in **kw
        #myClass = CalcClass(get_arg1, get_arg2, *args, **kw)
        #print sna_buildjson(platform, course_code)
        result = json.loads(sna_buildjson(platform, course_code, username=username, start_date=start_date, end_date=end_date, relationshipstoinclude=relationshipstoinclude))
        result["neighbours"] = json.loads(getNeighbours(json.dumps(result)))
        #{'nodes':["test sna","2nd test"]} #myClass.do_work()
        response = Response(result, status=status.HTTP_200_OK)
        return response

class WORDCLOUDView(DefaultsMixin, APIView):

    def get(self, request, *args, **kw):

        course_code = request.GET.get('course_code', None)
        platform = request.GET.get('platform', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        username = request.GET.get('username', None)

        result = json.loads(get_wordcloud(platform, course_code, username=username, start_date=start_date, end_date=end_date))
        response = Response(result, status=status.HTTP_200_OK)
        return response

class CLASSIFICATIONPieView(DefaultsMixin, APIView):

    def get(self, request, *args, **kw):

        course_code = request.GET.get('course_code', None)
        platform = request.GET.get('platform', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        username = request.GET.get('username', None)
        classifier = request.GET.get('classifier', None)

        result = json.loads(getClassifiedCounts(platform, course_code, username=username, start_date=start_date, end_date=end_date, classifier=classifier))
        response = Response(result, status=status.HTTP_200_OK)
        return response

class TOPICMODELView(DefaultsMixin, APIView):

    def get(self, request, *args, **kw):

        course_code = request.GET.get('course_code', None)
        platform = request.GET.get('platform', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        num_topics = int(request.GET.get('num_topics', None))

        result = json.loads(get_LDAVis_JSON(platform, num_topics, course_code, start_date=start_date, end_date=end_date))
        response = Response(result, status=status.HTTP_200_OK)
        return response

class MLCLASSIFY(DefaultsMixin, APIView):

    def get(self, request, *args, **kw):

        course_code = request.GET.get('course_code', None)
        platform = request.GET.get('platform', None)

        result = classify(course_code,platform)
        response = Response(result, status=status.HTTP_200_OK)
        return response

class MLTRAIN(DefaultsMixin, APIView):

    def get(self, request, *args, **kw):

        course_code = request.GET.get('course_code', None)
        platform = request.GET.get('platform', None)

        result = train(course_code,platform)
        response = Response(result, status=status.HTTP_200_OK)
        return response


class EXTERNALLINKLOGView(DefaultsMixin, APIView):

    def get(self, request, *args, **kw):

        url = "https://coi.athabascau.ca/coi-model/"
        userid = request.GET.get('userid', None)

        entry = AccessLog(url=url, userid=userid)
        entry.save()
        response = Response("Logged External Link Click", status=status.HTTP_200_OK)
        return response
