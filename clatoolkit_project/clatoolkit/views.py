from django.shortcuts import render, render_to_response
from django.shortcuts import redirect
from django.core.urlresolvers import reverse

from django.contrib.auth import authenticate, login
from django.http import HttpResponseRedirect, HttpResponse, Http404

from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from django.contrib.auth.models import User
from clatoolkit.forms import CreateOfferingForm, SignUpForm, UserForm, UserProfileForm

from django.template import RequestContext

from django.core.exceptions import PermissionDenied

from clatoolkit.models import UnitOffering, UnitOfferingMembership, DashboardReflection, LearningRecord, SocialRelationship, Classification, UserClassification, AccessLog

from rest_framework import authentication, permissions, viewsets, filters
from .serializers import LearningRecordSerializer, SocialRelationshipSerializer, ClassificationSerializer, UserClassificationSerializer

from .forms import SocialMediaUpdateForm, LearningRecordFilter, SocialRelationshipFilter, ClassificationFilter, UserClassificationFilter


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from dashboard.utils import *
import json

# from fb_data.models import

def home(request):
    context = RequestContext(request)
    return render_to_response('clatoolkit/home.html', {}, context)


def userlogin(request):
    context = RequestContext(request)

    message = None
    next_page = "/dashboard/myunits"

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        next_page = request.POST['next_page']

        user = authenticate(username=username, password=password)

        if user:
            # Is the account active? It could have been disabled.
            if user.is_active:
                # If the account is valid and active, we can log the user in.
                # We'll send the user back to the homepage.
                login(request, user)
                #print "sending to myunits"
                return HttpResponseRedirect(next_page)
            else:
                message = "Your CLAToolkit account is disabled."
        else:
            message = "Invalid login details supplied."

    # The request is not a HTTP POST, so display the login form.
    # This scenario would most likely be a HTTP GET.

    if "next" in request.GET:
        next_page = request.GET["next"]

    if request.user.is_authenticated():
        return redirect(next_page)

    else:
        return render_to_response('clatoolkit/login.html', {"message": message, "next_page": next_page}, context)


#Unit management integration for staff - 13/05/16
@login_required
def unitmanagement(request):
    context = RequestContext(request)

    role = request.user.userprofile.role
    user = request.user
    action = None
    unit_form = None
    #coi_platforms_form = None
    units = None
    hidden_ucode = None

    #User has submitted something
    if request.method == 'POST':

        print 'Got POST data: %s' % (request.POST)

        #Copy post req data because we're removing some elements
        post_data = request.POST.copy()

        #Get the action context of submitted form
        post_action = post_data.pop("action")[0]

        #Getting the form to be displayed
        if (post_action == 'edit'):
            #If user is editing/updating a unit offering, fetch the details
            course_code = post_data.pop('ucode')[0]

            unitoffering_id = UnitOffering.objects.get(code=course_code)
            unit_form = UnitOfferingForm(data=request.POST, instance=unitoffering_id)

        else:
            #otherwise we'll fill the form with submitted data
            unit_form = UnitOfferingForm(data=request.POST)

        #Validate and submit form data
        if unit_form.is_valid():

            #print 'Got valid form: %s' % (unit_form)

            if post_action == 'edit':
                #Updating db entry
                unit = unit_form.save(commit=False)
                unit.save(force_update=True)
            else:
                #Creating new unit offering
                unit_form.save()


            return redirect('/dashboard/myunits')
        else:
            print unit_form.errors
            HttpResponse("ERROR: %s" % (unit_form.errors))
    elif request.method == "GET":

        action = request.GET.get('action')
        course_code = request.GET.get('course_code')

        if action == 'edit' and role == 'Staff':
            unitoffering_id = UnitOffering.objects.get(code=course_code)
            unit_form = UnitOfferingForm(instance=unitoffering_id)
            hidden_ucode = course_code

        if action == 'new' and role == 'Staff':
            unit_form = UnitOfferingForm()

        #staff member deletes unit offering
        if action == 'delete' and role == 'Staff':
            unit = UnitOffering.objects.get(code=course_code)
            unit.delete()
            return redirect('/dashboard/myunits')

        #student removing their attached account to this course
        if action == 'unenrol':
            unit = UnitOffering.objects.filter(code=course_code)
            user.usersinunitoffering.remove(unit)
            return redirect('/dashboard/myunits')

        if role == "Staff":
            units = UnitOffering.objects.filter()

        else:
            units = UnitOffering.objects.filter(users=user, enabled=True)

    context_dict = {'action' : action, 'unit_form' : unit_form, 'units' : units, 'role' : role, 'ucode' : hidden_ucode}
    return render_to_response(
        'clatoolkit/unitmanagement.html',
        context_dict, context
    )


def register(request, unit_id):
    # Like before, get the request's context.
    context = RequestContext(request)

    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False

    try:
        unit = UnitOffering.objects.get(id=unit_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    platforms = unit.get_required_platforms()

    u = None

    if request.user.is_authenticated():
        u = request.user

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
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

            user.save()

            m = UnitOfferingMembership(user=user, unit=unit, admin=False)
            m.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.role = "Student"

            # Now we save the UserProfile model instance.
            profile.save()

            # Log in as the newly signed up user
            u = authenticate(username=user_form.cleaned_data["username"], password=user_form.cleaned_data["password"])
            login(request, u)

            return HttpResponseRedirect("/")

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserForm()
        profile_form = UserProfileForm()

    # Render the template depending on the context.
    return render_to_response(
        'clatoolkit/register.html',
            {'user_form': user_form, 'profile_form': profile_form, 'registered': registered, "course": unit, "req_platforms": platforms, "user": u}, context)


@login_required
def register_existing(request, unit_id):
    try:
        unit = UnitOffering.objects.get(id=unit_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    if not unit.users.filter(user=request.user).exists():
        membership = UnitOfferingMembership(user=request.user, unit=unit, admin=False)
        membership.save()

    return redirect("myunits")


@login_required
def socialmediaaccounts(request):
    context = RequestContext(request)
    user_id = request.user.id
    usr_profile = UserProfile.objects.get(user_id=user_id)

    if request.method == 'POST':
        profile_form = SocialMediaUpdateForm(data=request.POST,instance=usr_profile)
        units  = UnitOffering.objects.filter(users=user_id)

        if profile_form.is_valid():
            profile_form.save()
            return redirect('/dashboard/myunits')
        # Invalid form or forms - mistakes or something else?
        else:

            print profile_form.errors


    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        profile_form = SocialMediaUpdateForm(instance=usr_profile)
        units = UnitOffering.objects.filter(users=user_id)

    # Render the template depending on the context.
    return render_to_response(
        'clatoolkit/socialmediaaccounts.html',
            {'profile_form': profile_form, 'units': units}, context)


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


def signup(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = SignUpForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # Create user from form data
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()

            # Create blank user profile
            user_profile = UserProfile(user=user)
            user_profile.save()

            # Log in as the newly signed up user
            user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password'])
            login(request, user)

            return HttpResponseRedirect("/clatoolkit/unitofferings/new")

    # if a GET (or any other method) we'll create a blank form
    else:
        form = SignUpForm()

    return render(request, 'clatoolkit/signup.html', {'form': form})


@login_required
def create_offering(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = CreateOfferingForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            unit = form.save(commit=False)
            unit.save()

            m = UnitOfferingMembership(user=request.user, unit=unit, admin=True)
            m.save()

            return render(request, 'clatoolkit/createoffering_success.html', {'verb': 'created', 'unit': unit})

    # if a GET (or any other method) we'll create a blank form
    else:
        form = CreateOfferingForm()

    return render(request, 'clatoolkit/createoffering.html', {'verb': 'Create', 'form': form})


@login_required
def update_offering(request, unit_id):
    try:
        unit = UnitOffering.objects.get(id=unit_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    if UnitOfferingMembership.is_admin(request.user, unit):
        if request.method == "POST":
            form = CreateOfferingForm(request.POST, instance=unit)
            if form.is_valid():
                unit = form.save()
                return render(request, 'clatoolkit/createoffering_success.html', {'verb': 'updated', 'unit': unit})

        else:
            form = CreateOfferingForm(instance=unit)

            all_plugins = settings.DATAINTEGRATION_PLUGINS
            excluded = ["Blog", "Diigo", "Forum", "GitHub", "Twitter", "YouTube", "facebook", "trello"]

            plugins = []
            for plugin in all_plugins:
                if plugin not in excluded:
                    plugins.append({
                        "a": reverse("{}_config".format(plugin)),
                        "label": "Configure {}".format(plugin)
                    })

            return render(request, "clatoolkit/createoffering.html", {'verb': 'Update', 'form': form, 'unit': unit, "plugins":plugins})
    else:
        raise PermissionDenied()


@login_required
def offering_members(request, unit_id):
    try:
        unit = UnitOffering.objects.get(id=unit_id)
    except UnitOffering.DoesNotExist:
        raise Http404

    if UnitOfferingMembership.is_admin(request.user, unit):
        members = unit.users.all()
        return render(request, "clatoolkit/offering_members.html", {"unit": unit, "members": members})
    else:
        raise PermissionDenied()


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
