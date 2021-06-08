from github import Github, GithubException, UnknownObjectException
import os
import re

pattern = re.compile('(?:[Ff]ix(?:e[sd]?|ing)(?:\ |:)+|(?:[Cc]los(?:e[sd]?|ing)(?:\ |:)+)|(?:[Rr]esolv(?:e[sd]?|ing)(?:\ |:)+)|(?:[Ii]mplement(?:s|ed|ing)(?:\ |:)+))#(\d+)')

def check_push_event(event):
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])
    commit_messages = []
    issue_numbers = []
    for commit in event['commits']:
        print('commit: ' + str(commit))
        commit_message = commit['message']
        commit_messages += commit_message
        print('comit message: ' + str(commit_message))
        issue_numbers += parse_commit_message(commit_message)
    
    for issue in issue_numbers:
        print('issue: ' + issue)
        print('repo: ' + str(repo.get_issue(int(issue))))
        print('state: ' + str(repo.get_issue(int(issue)).state))
        print('pull_request: ' + str(repo.get_issue(int(issue)).pull_request))
        print('as_pull_request: ' + str(repo.get_issue(int(issue)).as_pull_request()))
        try:
            if repo.get_issue(int(issue)).as_pull_request():
                print('=======UPDATE=======')
                update_pull_request(repo.get_issue(int(issue)).as_pull_request())
        except GithubException:
            print("Cannot find issue '%s'. Skipping." % issue)
        except UnknownObjectException:
            print("Cannot find issue '%s'. Skipping. UnknownObjectException" % issue)

def update_pull_request(pull_request):
    if pull_request.state == 'open':
        print('Pull request is open, nothing to update.')
        return
    original_title = pull_request.title
    new_title = '[Merged] ' + original_title
    print('new_title: ' + new_title)
    pull_request.edit(title=new_title)
    pull_request.create_issue_comment('This pull request was cherry-picked. Thank you for your contribution!')


def parse_commit_message(commit_message):
    # Regex matches numbers that come after Fix, fix, Fixed, fixed, Fixes, fixes keyword followed by any
    # combination of spaces and colons, followed by exactly one hashtag. The same applies for Close and Resolve
    # keywords and their combinations. Note: fixing, closing and resolving don't work.
    # Only first number is picked. To match multiple numbers you have to add fix or close or resolve or implement keyword
    # for each of them.
    # Example:
    # fixed: #1 #2 #3
    # resolved   ::: ::: :: #4
    # closes: ##5
    # fix: # 6
    # asdfresolves #7
    # closeasdf: #8
    # closes #9 <any sting in between> fixed #10
    # fixing #11
    # Matches: [1, 4, 7, 9, 10]
    return pattern.findall(commit_message)