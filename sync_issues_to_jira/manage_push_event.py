from github import Github
import os

def check_push_event(event):
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])

    print("=================EVENT=====================")
    print(event)