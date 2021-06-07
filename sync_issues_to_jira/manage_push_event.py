from jira import JIRA
from github import Github
import os
import sys
import json
from sync_to_jira import *

def check_push_event(event):
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])
