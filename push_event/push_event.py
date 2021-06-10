from github import Github
import os
import re
from util.util import check_repo, get_event
from github.GithubException import GithubException

def handle_push_event(event):
    issue_numbers = []
    for commit in event['commits']:
        commit_message = commit['message']
        issue_numbers += parse_commit_message(commit_message)
    
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])
    for issue in issue_numbers:
        gh_issue = repo.get_issue(int(issue))
        if gh_issue.pull_request:
            update_pull_request(gh_issue.as_pull_request())

def update_pull_request(pull_request):
    # TODO: 
    # Sometimes we actually do "close" a PR by doing something different to what the author originally intended,
    # and with a totally different commit. We try to avoid this, but it's necessary sometimes.
    # Ideally this action would check if the commit author is the same as the author of any of the commits in the PR branch,
    # and only continue if it is. However this is probably a rare enough occasion that you can consider it a "nice to have". :)
    
    print("Updating %s" % pull_request)
    original_title = pull_request.title
    # Check if original title already starts with [Merged] keyword. If yes, skip updating pull request.
    if original_title.startswith('[Merged]'):
        print('Pull request title suggests it was already merged. Skipping...')
        return
    # Prepend [Merged] to the pull request title
    new_title = '[Merged] ' + original_title
    pull_request.edit(title=new_title)
    # Thank contributor for opening pull request. Let them know we didn't throw it away
    pull_request.create_issue_comment('The pull request has been cherry-picked, the commit is linked above.\
        Thank you for your contribution!')


def parse_commit_message(commit_message):
    # First regex matches numbers that come after Fix, fix, Fixed, fixed, Fixes, fixes keyword followed by any
    # combination of spaces and colons, followed by exactly one hashtag. The same applies for Close and Resolve
    # keywords and their combinations. Note: fixing, closing and resolving don't work. Only first number is picked.
    # To match multiple numbers you have to add fix or close or resolve keyword for each of them.
    # 
    # Second regex matches pull request numbers from pull reques url.
    # 
    # Example:
    #
    # fixed: #1 #2 #3
    # resolved   ::: ::: :: #4
    # closes: ##5
    # fix: # 6
    # asdfresolves #7
    # closeasdf: #8
    # closes #9 <any sting in between> fixed #10
    # fixing #11
    # https://github.com/espressif/esp-idf/pull/12\
    # https://github.com/espressif/esp-idf/pull/ 13\
    # https://github.com/espressif/esp-idf/pull/#14\
    # https://github.com/ESPRESSIF/esp-idf/pull/15
    #
    # Above example matches: [1, 4, 9, 10, 12, 15]
    
    #
    reference_pattern = re.compile(r'(?:closes?|closed|fixes|fix|fixed|resolves?|resolved)(?:\s|:)+#(\d+)', re.IGNORECASE)
    url_pattern = re.compile(r'(?:https://github.com/espressif/esp-idf/pull/)(\d+)', re.IGNORECASE)
    matches = []
    matches += reference_pattern.findall(commit_message)
    matches += url_pattern.findall(commit_message)
    return matches

def main():
    
    try:
        check_repo()
    except GithubException:
        return

    event = get_event()
    
    # Check if it's a push event
    if os.environ['GITHUB_EVENT_NAME'] == 'push':
        handle_push_event(event)
        return

if __name__ == "__main__":
    main()