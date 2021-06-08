from github import Github
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
        print('repo:' + str(repo.get_issue(int(issue))))
        print('state:' + str(repo.get_issue(int(issue).state())))
        print('pull_request:' + str(repo.get_issue(int(issue).pull_request())))
        print('as_pull_request:' + str(repo.get_issue(int(issue).as_pull_request())))

def parse_commit_message(commit_message):
    # Regex matches numbers that come after Fix, fix, Fixed, fixed, Fixes, fixes, Fixing, fixing keyword followed by any
    # combination of spaces and colons, followed by exactly one hashtag. The same applies for Close, Resolve and Implement
    # keywords and their combinations.
    # Only first number is picked. To match multiple numbers you have to add fix or close or resolve or implement keyword
    # for each of them.
    # Example:
    # fixed: #1 #2 #3
    # implements   ::: ::: :: #4
    # closing: ##5
    # resolves: # 6
    # asdffixes #7
    # closeasdf: #8
    # closes #9 <any sting in between> fixed #10 implementing #11
    # Matches: [1, 4, 7, 9, 10, 11]
    return pattern.findall(commit_message)