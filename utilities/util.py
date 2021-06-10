import os
import json
from github.GithubException import GithubException

def check_repo():
    if 'GITHUB_REPOSITORY' not in os.environ:
        print('Not running in GitHub action context, nothing to do')
        raise GithubException('Not running in GitHub action context, nothing to do')

    if not os.environ['GITHUB_REPOSITORY'].startswith('espressif/'):
        print('Not an Espressif repo, nothing to sync to JIRA')
        raise GithubException('Not an Espressif repo, nothing to sync to JIRA')

# The path of the file with the complete webhook event payload. For example, /github/workflow/event.json.
def get_event():
    with open(os.environ['GITHUB_EVENT_PATH'], 'r') as f:
        event = json.load(f)
        print(json.dumps(event, indent=4))
    return event