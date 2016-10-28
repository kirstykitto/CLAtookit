from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.conf.urls import url
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from common.CLRecipe import CLRecipe
from dataintegration.core.plugins.base import DIBasePlugin, DIPluginDashboardMixin
from requests_oauthlib import OAuth1Session
from dataintegration.models import PlatformConfig
from dataintegration.core.socialmediarecipebuilder import *
from dataintegration.core.recipepermissions import *
from dataintegration.core.plugins import registry
from forms import ConnectForm


class WordPressPlugin(DIBasePlugin, DIPluginDashboardMixin):
    platform = CLRecipe.PLATFORM_WORDPRESS

    xapi_verbs = ['created', 'commented']
    xapi_objects = ['Note']

    user_api_association_name = "WP username"

    @classmethod
    def config_view(cls, request):
        unit = UnitOffering.from_get(request)
        if UnitOfferingMembership.is_admin(request.user, unit):
            instances = cls.get_intances(unit)

            return render(request, "wordpress/templates/config.html", {"unit": unit, "instances": instances})
        else:
            raise PermissionDenied

    @classmethod
    def delete_instance_view(cls, request):
        unit = UnitOffering.from_get(request)
        if UnitOfferingMembership.is_admin(request.user, unit):
            try:
                instance = request.GET["instance"]
            except:
                return HttpResponseBadRequest("Instance not specified")
            cls.delete_instance(unit, instance)
            return HttpResponseRedirect(reverse("{}_config".format(cls.platform)) + "?unit={}".format(unit.id))
        else:
            raise PermissionDenied

    @classmethod
    def connect_view(cls, request):
        if request.method == "POST":
            form = ConnectForm(request.POST)

            if form.is_valid():
                # Get the details the user entered into the form
                unit_id = form.cleaned_data["unit_id"]
                wp_root = form.cleaned_data["wp_root"]
                client_key = form.cleaned_data["client_key"]
                client_secret = form.cleaned_data["client_secret"]

                unit = UnitOffering.objects.get(id=unit_id)

                if UnitOfferingMembership.is_admin(request.user, unit):
                    # Save the WP instance details
                    cls.add_instance(unit, wp_root, client_key, client_secret)

                    # Setup URLs for use in the handshake process
                    request_token_url = "{}/oauth1/request".format(wp_root)
                    base_authorization_url = "{}/oauth1/authorize".format(wp_root)
                    callback_path = reverse("{}_authorize".format(cls.platform))
                    callback_uri = "{}://{}{}".format(request.scheme, request.get_host(), callback_path)

                    # Start the oauth flow and get temporary credentials
                    oauth = OAuth1Session(client_key, client_secret, callback_uri)
                    fetch_response = oauth.fetch_request_token(request_token_url)
                    temp_token = fetch_response.get('oauth_token')
                    temp_secret = fetch_response.get('oauth_token_secret')

                    # Save credentials to the session as they will need to be reused in the authorization step
                    request.session["wp_temp_token"] = temp_token
                    request.session["wp_temp_secret"] = temp_secret
                    request.session["wp_temp_unit"] = request.GET["unit"]
                    request.session["wp_temp_root"] = wp_root

                    # Redirect the user to authorize the toolkit
                    authorization_url = oauth.authorization_url(base_authorization_url, oauth_callback=callback_uri)
                    return HttpResponseRedirect(authorization_url)

        else:
            unit = UnitOffering.from_get(request)
            form = ConnectForm()

            return render(request, "wordpress/templates/connect.html", {"form": form, "unit": unit})

    @classmethod
    def authorize_view(cls, request):
        return cls().authorize(request)

    @classmethod
    def refresh_view(cls, request):
        unit = UnitOffering.objects.get(id=request.GET["unit"])
        if UnitOfferingMembership.is_admin(request.user, unit):
            cls().perform_import(request, unit)
            return HttpResponse("Done")
        else:
            raise PermissionDenied

    @classmethod
    def get_url_patterns(cls):
        """Returns the URL patterns used by the plugin"""
        return [
            url(r'^config/$', login_required(cls.config_view), name="{}_config".format(CLRecipe.PLATFORM_WORDPRESS)),
            url(r'^connect/$', login_required(cls.connect_view), name="{}_connect".format(CLRecipe.PLATFORM_WORDPRESS)),
            url(r'^delete/$', login_required(cls.delete_instance_view), name="{}_delete_instance".format(CLRecipe.PLATFORM_WORDPRESS)),
            url(r'^authorize/$', login_required(cls.authorize_view), name="{}_authorize".format(CLRecipe.PLATFORM_WORDPRESS)),
            url(r'^refresh/$', login_required(cls.refresh_view), name="{}_refresh".format(CLRecipe.PLATFORM_WORDPRESS)),
        ]

    def __init__(self):
        pass

    @classmethod
    def authorize(cls, request):
        unit_id = request.session["wp_temp_unit"]
        wp_root = request.session["wp_temp_root"]

        try:
            unit = UnitOffering.objects.get(id=unit_id)
        except UnitOffering.DoesNotExist:
            raise Http404

        if UnitOfferingMembership.is_admin(request.user, unit):
            access_token_url = "{}/oauth1/access".format(wp_root)

            verifier = request.GET['oauth_verifier']

            client_key, client_secret = cls.get_client_key(unit, wp_root)

            oauth = OAuth1Session(client_key, client_secret=client_secret,
                                  resource_owner_key=request.session["wp_temp_token"],
                                  resource_owner_secret=request.session["wp_temp_secret"], verifier=verifier)
            oauth_tokens = oauth.fetch_access_token(access_token_url)

            cls.save_access_token(unit, wp_root, oauth_tokens.get('oauth_token'), oauth_tokens.get('oauth_token_secret'))

            return HttpResponseRedirect(reverse("{}_config".format(cls.platform)) + "?unit={}".format(unit.id))

        else:
            raise PermissionDenied

    @classmethod
    def add_instance(cls, unit, wp_root, access_key, access_secret):
        """Add a connection to the platform config for a unit, overwrites existing entries for a non-unique wp_root"""
        try:
            pc = PlatformConfig.objects.get(unit=unit, platform=cls.platform)
            pc.config[wp_root] = {
                    "client_key": access_key,
                    "client_secret": access_secret
            }
        # If no existing config exists
        except PlatformConfig.DoesNotExist:
            config = {
                wp_root: {
                    "client_key": access_key,
                    "client_secret": access_secret
                }
            }
            pc = PlatformConfig(unit=unit, platform=cls.platform, config=config)
        pc.save()

    @classmethod
    def delete_instance(cls, unit, wp_root):
        try:
            pc = PlatformConfig.objects.get(unit=unit, platform=cls.platform)
            pc.config.pop(wp_root)
            pc.save()
        # If no existing config exists
        except PlatformConfig.DoesNotExist:
            pass

    @classmethod
    def get_platform_config(cls, unit):
        return PlatformConfig.objects.get(unit=unit, platform=cls.platform).config

    @classmethod
    def get_instance_config(cls, unit, wp_root):
        return PlatformConfig.objects.get(unit=unit, platform=cls.platform).config[wp_root]

    @classmethod
    def get_intances(cls, unit):
        config = cls.get_platform_config(unit)
        sites = [s for s in config]
        return sites

    @classmethod
    def get_groups(cls, unit):
        instances = cls.get_intances(unit)
        result = []
        for instance in instances:
            result.append({
                "label": instance,
                "a": instance
            })
        return result

    @classmethod
    def get_client_key(cls, unit, wp_root):
        config = cls.get_instance_config(unit, wp_root)

        return config["client_key"], config["client_secret"]

    @classmethod
    def save_access_token(cls, unit, wp_root, access_token_key, access_token_secret):
        """Save access token and secret to an existing entry in the PlatformConfig"""
        pc = PlatformConfig.objects.get(unit=unit, platform=cls.platform)

        pc.config[wp_root]["access_token_key"] = access_token_key
        pc.config[wp_root]["access_token_secret"] = access_token_secret

        pc.save()

    @classmethod
    def get_access_token(cls, unit, wp_root):
        config = cls.get_instance_config(unit, wp_root)

        return config["access_token_key"], config["access_token_secret"]

    @classmethod
    def perform_import(cls, retrieval_param, unit):
        config = cls.get_platform_config(unit)

        # For each WordPress instance connected
        for instance in config:

            oauth = OAuth1Session(client_key=config[instance]["client_key"],
                                  client_secret=config[instance]["client_secret"],
                                  resource_owner_key=config[instance]["access_token_key"],
                                  resource_owner_secret=config[instance]["access_token_secret"])

            cls.get_posts(unit, oauth, instance)
            cls.get_friendships(unit, oauth, instance)

    @classmethod
    def get_posts(cls, unit, oauth, instance):
        next_page = "{}/wp-json/clatoolkit-wp/v1/posts".format(instance)

        while next_page:
            r = oauth.get(next_page)
            result = r.json()

            for blog in result["posts"]:
                cls.add_blog_posts(blog, unit, instance)

            if "next_page" in result:
                next_page = result["next_page"]
            else:
                next_page = False

    @classmethod
    def add_blog_posts(cls, blog, unit, instance):

        for post in blog["posts"]:

            try:
                user = UserProfile.from_platform_identifier(cls.platform, post["author"]["email"]).user

                insert_post(user=user, post_id=post["guid"], message=post["post_content"],
                            created_time=post["post_date_gmt"], unit=unit, platform=cls.platform, platform_url="",
                            platform_group_id=instance)

                if "comments" in post:
                    for comment in post["comments"]:
                        try:
                            commenter = UserProfile.from_platform_identifier(cls.platform,
                                                                             comment["comment_author_email"]).user

                            insert_comment(user=commenter, post_id=post["guid"], comment_id=comment["comment_guid"],
                                           comment_message=comment["comment_content"],
                                           comment_created_time=comment["comment_date_gmt"], unit=unit,
                                           platform=cls.platform, platform_group_id=instance, platform_url="", parent_user=user)

                        except UserProfile.DoesNotExist:
                            # Don't store the comment if the author doesn't exist
                            pass

            except UserProfile.DoesNotExist:
                # Do nothing if the post author doesn't exist
                pass

    @classmethod
    def get_friendships(cls, unit, oauth, instance):
        friendship_endpoint = "{}/wp-json/clatoolkit-wp/v1/friendships".format(instance)
        relationship_type = "friendship"

        r = oauth.get(friendship_endpoint)

        j = r.json()

        for user_id in j["friendships"]:
            user_email = j["entities"][user_id]["email"]
            try:
                user = UserProfile.from_platform_identifier(platform=cls.platform, identifier=user_email).user
                for friend_id in j["friendships"][user_id]:
                    friend_user_email = j["entities"][friend_id]["email"]

                    try:
                        friend = UserProfile.from_platform_identifier(cls.platform, friend_user_email).user

                        insert_relationship(from_user=user, to_user=friend, relationship_type=relationship_type,
                                            unit=unit, platform=cls.platform, platform_group_id=instance,
                                            directional=False)

                    except UserProfile.DoesNotExist:
                        pass
            except UserProfile.DoesNotExist:
                pass

registry.register(WordPressPlugin)
