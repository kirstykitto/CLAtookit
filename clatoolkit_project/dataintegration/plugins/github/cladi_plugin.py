from dataintegration.core.plugins import registry
from dataintegration.core.plugins.base import DIBasePlugin, DIPluginDashboardMixin
from dataintegration.core.socialmediarecipebuilder import *
from dataintegration.core.recipepermissions import *
import json
import dateutil.parser
from github import Github
from dataintegration.plugins.github.githubLib import *
from django.contrib.auth.models import User
import os

class GithubPlugin(DIBasePlugin, DIPluginDashboardMixin):

    platform = "github"
    platform_url = "https://github.com/"

    xapi_verbs = ['created', 'added', 'removed', 'updated', 'commented']
    xapi_objects = ['Collection', 'file', 'comment']

    user_api_association_name = 'GitHub Username' # eg the username for a signed up user that will appear in data extracted via a social API
    unit_api_association_name = 'Repository URL' # eg hashtags or a group name

    config_json_keys = ['token']
    # The number of data (records) in a page.
    parPage = 100

    #from DIPluginDashboardMixin
    xapi_objects_to_includein_platformactivitywidget = ['Collection', 'file', 'comment']
    xapi_verbs_to_includein_verbactivitywidget = ['created', 'added', 'removed', 'updated', 'commented']

    def __init__(self):
        # Load api_config.json and convert to dict
        config_file = os.path.join(os.path.dirname(__file__), 'api_config.json')
        with open(config_file) as data_file:
            self.api_config_dict = json.load(data_file)



    def perform_import(self, retrieval_param, course_code):

        # Setup Twitter API Keys
        token = self.api_config_dict['token']
        urls = retrieval_param.split(os.linesep)

        for url in urls:
            print "GitHub data extraction URL: " + url
            # Instanciate PyGithub object
            repoFullName = url.lstrip(STR_PLATFORM_URL_GITHUB)
            gh = Github(token, per_page=self.parPage)
            # Use .rstrip() to eliminate line-change cord

            print "repo name = " + repoFullName.rstrip()

            repo = gh.get_repo(repoFullName.rstrip())
            self.importGitHubCommits(course_code, url, token, repo)
            self.importGitHubIssues(course_code, url, token, repo, gh)
            self.importGitHubCommitComments(course_code, url, token, repo)
            self.importGitHubIssueComments(course_code, url, token, repo)


    ###################################################################
    # Import GitHub commit comments data.
    #   A library PyGithub is used to interact with GitHub API.
    #   See @ http://pygithub.readthedocs.org/en/stable/index.html
    ###################################################################
    def importGitHubCommitComments(self, courseCode, url, token, repo):
        count = 0
        commitComments = repo.get_comments().get_page(count)

        # Retrieve issue data
        while True:
            for commitCom in commitComments:
                authorHomepage = commitCom.user.html_url
                author = commitCom.user.login
                commitComURL = commitCom.html_url
                date = commitCom.updated_at
                body = commitCom.body
                if body is None:
                    body = ""
                commit = repo.get_commit(commitCom.commit_id)
                commitURL = commit.html_url

                if username_exists(author, courseCode, self.platform):
                    usr_dict = get_userdetails(author, self.platform)
                    claUserName = get_username_fromsmid(author, self.platform)
                    insert_comment(usr_dict, commitURL, commitComURL, 
                        body, author, claUserName,
                        date, courseCode, self.platform, authorHomepage,
                        author, author)

            count = count + 1
            commitComments = repo.get_comments().get_page(count)
            temp = list(commitComments)
            if len(temp) == 0:
                #Break from while
                break;
        

    ###################################################################
    # Import GitHub issue comments data.
    #   A library PyGithub is used to interact with GitHub API.
    #   See @ http://pygithub.readthedocs.org/en/stable/index.html
    ###################################################################
    def importGitHubIssueComments(self, courseCode, url, token, repo):
        count = 0
        issueComments = repo.get_issues_comments().get_page(count)

        # Retrieve issue data
        while True:
            for issueCom in issueComments:
                authorHomepage = issueCom.user.html_url
                author = issueCom.user.login
                issueURL = issueCom.issue_url
                issueComURL = issueCom.html_url
                date = issueCom.updated_at
                body = issueCom.body
                if body is None:
                    body = ""

                if username_exists(author, courseCode, self.platform):
                    usr_dict = get_userdetails(author, self.platform)
                    claUserName = get_username_fromsmid(author, self.platform)
                    insert_comment(usr_dict, issueURL, issueComURL, 
                        body, author, claUserName,
                        date, courseCode, self.platform, authorHomepage,
                        author, author)

            count = count + 1
            issueComments = repo.get_issues_comments().get_page(count)
            temp = list(issueComments)
            if len(temp) == 0:
                #Break from while
                break;

    ###################################################################
    # Import GitHub all issues.
    # Note that issues include pull requests.
    # 
    #   A library PyGithub is used to interact with GitHub API.
    #   See @ http://pygithub.readthedocs.org/en/stable/index.html
    ###################################################################
    def importGitHubIssues(self, courseCode, repoUrl, token, repo, githubObj):
        # Search issues including pull requests using search method
        count = 0
        query = 'repo:kojiagile/testrepo'
        issueList = githubObj.search_issues(query, order = 'asc').get_page(count)

        # Retrieve issue data
        while True:
            for issue in issueList:
                assigneeHomepage = issue.user.html_url
                assignee = issue.user.login
                issueURL = issue.html_url
                date = issue.updated_at

                body = issue.body
                if body is None or body == "":
                    body = issue.title

                # TODO:
                # When pull request data is imported, verb needs to be shared (or sth better one).
                # 
                # Pull request data is retrieved only when it is open. 
                #  Closed pull requests are not included in the get_issues() method.
                #if issue.pull_request:
                #    # Verb for a pull request
                #    verb = 'shared'

                #TODO:
                # Tag object should ideally be passed to insert_issue() medthod,
                # if someone is mentioned (e.g. @kojiagile is working on this issue...)
                # 
                if username_exists(assignee, courseCode, self.platform):
                    usr_dict = get_userdetails(assignee, self.platform)
                    claUserName = get_username_fromsmid(assignee, self.platform)
                    insert_issue(usr_dict, issueURL, body, assignee, claUserName,
                        date, courseCode, repoUrl, self.platform, issueURL, 
                        assignee)

            count = count + 1
            issueList = githubObj.search_issues(query, order = 'asc').get_page(count)
            temp = list(issueList)
            #print "# of content in githubObj.search_issues.get_page(count) = " + str(len(temp))
            #If length is 0, it means that no commit data is left.
            if len(temp) == 0:
                #Break from while loop
                break;



    ###################################################################
    # Import GitHub commit data.
    #   A library PyGithub is used to interact with GitHub API.
    #   See @ http://pygithub.readthedocs.org/en/stable/index.html
    ###################################################################
    def importGitHubCommits(self, courseCode, repoUrl, token, repo):
        count = 0
        commitList = repo.get_commits().get_page(count)
        # Retrieve commit data
        while True:
            for commit in commitList:
                committerName = ""
                email = ""
                if commit.committer is None:
                    # 
                    # When committer's email address registered in his/her local repository does not match
                    # to GitHub account's email, commit.committer or commit.authoer will be null in GitHub API resposen.
                    # Thus, PyGithub object has None when that happens.
                    # https://api.github.com/repos/luantrongtran/7colours-DementiaWatch/commits/d420df8defc273fb9acf56aa4e334377d556ec3f
                    #print "commit.committer is null. This commit data " + commit.sha + " is ignored."
                    print "commit.committer is null. url = " + commit.html_url
                    #committerName = commit.author.name
                    #email = commit.author.email
                    continue
                else:
                    #committerName = commit.commit.committer.name
                    committerName = commit.committer.login
                    email = commit.commit.committer.email
                #commitID = commit.sha
                msg = commit.commit.message
                commitHtmlURL = commit.html_url
                date = commit.commit.committer.date
                committerHomepage = commit.committer.html_url

                # Import commit data
                usr_dict = None
                claUserName = None
                if username_exists(committerName, courseCode, self.platform):
                    usr_dict = get_userdetails(committerName, self.platform)
                    claUserName = get_username_fromsmid(committerName, self.platform)
                    insert_commit(usr_dict, commitHtmlURL, msg, committerName, claUserName,
                        date, courseCode, repoUrl, self.platform, commitHtmlURL, committerName)
                else:
                    #If a user does not exist, ignore the commit data
                    continue
            
                #importGitHubCommitsFiles(commit, repoUrl)
                # All committed files are inserted into DB
                for file in commit.files:
                    verb = "added"
                    if file.status == "modified":
                        verb = "updated"
                    elif file.status == "removed":
                        verb = "removed"

                    patch = file.patch
                    if file.patch is None:
                        patch = ""

                    if username_exists(committerName, courseCode, self.platform):
                        #usr_dict = get_userdetails(committerName, self.platform)
                        #claUserName = get_username_fromsmid(committerName, self.platform)
                        insert_file(usr_dict, file.blob_url, patch, committerName, claUserName,
                            date, courseCode, commitHtmlURL, self.platform, file.blob_url, 
                            commitHtmlURL, verb, repoUrl, file.additions, file.deletions, committerName)

            # End of for commit in commitList:

            # Pagination:
            # API response does not contain the number of pages left.
            # (It is included in HTTP header (link header).)
            # The content in next page needs to be retrieved
            # to know that there are still records to be imported.
            count = count + 1
            commitList = repo.get_commits().get_page(count)
            temp = list(commitList)
            #print "# of content in repo.get_commits().get_page(" + str(count) + ") = " + str(len(temp))
            #If length is 0, it means that no commit data is left.
            if len(temp) == 0:
                #Break from while
                break;

registry.register(GithubPlugin)