"""
Base classes for CLAToolkit Data Integration plugins:
 * DIBasePlugin: Create a cladi_plugin.py with a class that inherits from DIBasePlugin
 * DIPluginDashboardMixin: Include mixin to specify the xapi verbs and objects that must be included in core dashboard graphs
"""

class DIBasePlugin(object):
    """ Data Integration Plugins must inherit DIBasePlugin """
    # Mandatory
    platform = None
    platform_url = None
    xapi_verbs = []
    xapi_objects = []

    user_api_association_name = None # eg the username for a signed up user that will appear in data extracted via a social API
    unit_api_association_name = None # eg hashtags or a group name

    config_json_keys = []

    def perform_import(self, retrieval_param, unit):
        """Called to start the import from api for a plugin.


        Attributes:
            retrieval_param: parameter that that is used to filter data returned by the api (eg for Twitter this is a hashtag)
            course_code: course_code to associate the imported data with
        """
        pass

class DIPluginDashboardMixin(object):
    """ Data Integration Plugin mixin to specify the xapi verbs and objects that must be included in core dashboard graphs """
    xapi_objects_to_includein_platformactivitywidget = []
    xapi_verbs_to_includein_verbactivitywidget = []

class DIAuthomaticPluginMixin(object):
    """ Data Integration Plugin mixin to specify settings for the Authomatic library.
       Authomatic provides oauth and openid support
    """
    authomatic_config_json = {}
    authomatic_config_key = None
    authomatic_secretkey = None

    def perform_import(self, retrieval_param, course_code, authomatic_result):
        """Called to start the import from api for a plugin.


        Attributes:
            retrieval_param: parameter that that is used to filter data returned by the api (eg for Twitter this is a hashtag)
            course_code: course_code to associate the imported data with
            authomatic_result: result returned after authomatic login
        """
        pass

class DIGoogleOAuth2WebServerFlowPluginMixin(object):
    """ Data Integration Plugin mixin to specify settings for Google OAuth2WebServerFlow.
        Used by Google Drive and Youtube
    """
    scope = None

    def perform_import(self, retrieval_param, course_code, webserverflow_result):
        """Called to start the import from api for a plugin.


        Attributes:
            retrieval_param: parameter that that is used to filter data returned by the api (eg for Twitter this is a hashtag)
            course_code: course_code to associate the imported data with
            webserverflow_result: result returned after webserverflow login
        """
        pass
