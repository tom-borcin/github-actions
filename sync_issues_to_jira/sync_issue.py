#!/usr/bin/env python3
#
# Copyright 2019 Espressif Systems (Shanghai) PTE LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from jira import JIRA
from github import Github
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time

class _JIRA(JIRA):
    def applicationlinks(self):
        return [] # disable this function as we don't need it and it makes add_remote_links() slow

def main():
    with open(os.environ['GITHUB_EVENT_PATH'], 'r') as f:
        event = json.load(f)
        json.dump(event, sys.stdout, indent=4)

    print('Connecting to JIRA...')
    jira = _JIRA(os.environ['JIRA_URL'],
                basic_auth=(os.environ['JIRA_USER'],
                            os.environ['JIRA_PASS']))

    event_name = os.environ['GITHUB_EVENT_NAME']
    action = event["action"]

    action_handlers = {
        'issues': {
            'opened': handle_issue_opened,
            'edited': handle_issue_edited,
            'closed': handle_issue_closed,
            'deleted': handle_issue_deleted,
            'reopened': handle_issue_reopened,
            'labeled': handle_issue_label_change,
            'unlabeled': handle_issue_label_change,
        },
        'issue_comment': {
            'created': handle_comment_created,
            'edited': handle_comment_edited,
            'deleted': handle_comment_deleted,
        },
    }

    if event_name not in action_handlers:
        print("No handler for event '%s'. Skipping." % event_name)
    elif action not in action_handlers[event_name]:
        print("No handler '%s' action '%s'. Skipping." % (event_name, action))
    else:
        action_handlers[event_name][action](jira, event)


def handle_issue_opened(jira, event):
    _create_jira_issue(jira, event["issue"])


def handle_issue_edited(jira, event):
    gh_issue = event["issue"]
    issue = _find_jira_issue(jira, gh_issue, True)

    issue.update(fields={
        "description": _get_description(gh_issue),
        "summary": _get_summary(gh_issue),
        "issuetype": _get_jira_issue_type(jira, gh_issue),
    })

    _update_link_resolved(jira, gh_issue, issue)

    _leave_jira_issue_comment(jira, event, "edited", True, jira_issue=issue)


def handle_issue_closed(jira, event):
    # note: Not auto-closing the synced JIRA issue because GitHub
    # issues often get closed for the wrong reasons - ie the user
    # found a workaround but the root cause still exists.
    issue = _leave_jira_issue_comment(jira, event, "closed", False)
    if issue is not None:
        _update_link_resolved(jira, event["issue"], issue)


def handle_issue_label_change(jira, event):
    gh_issue = event["issue"]
    issue = _find_jira_issue(jira, gh_issue, True)
    issue.update(fields={
        "issuetype": _get_jira_issue_type(jira, gh_issue),
    })


def handle_issue_deleted(jira, event):
    _leave_jira_issue_comment(jira, event, "deleted", False)


def handle_issue_reopened(jira, event):
    issue = _leave_jira_issue_comment(jira, event, "reopened", True)
    _update_link_resolved(jira, event["issue"], issue)


def handle_comment_created(jira, event):
    gh_comment = event["comment"]

    jira_issue = _find_jira_issue(jira, event["issue"], True)
    jira.add_comment(jira_issue.id, _get_jira_comment_body(gh_comment))


def handle_comment_edited(jira, event):
    gh_comment = event["comment"]
    old_gh_body = _markdown2wiki(event["changes"]["body"]["from"])

    jira_issue = _find_jira_issue(jira, event["issue"], True)

    # Look for the old comment and update it if we find it
    old_jira_body = _get_jira_comment_body(gh_comment, old_gh_body)
    found = False
    for comment in jira.comments(jira_issue.key):
        if comment.body == old_jira_body:
            comment.update(body=_get_jira_comment_body(gh_comment))
            found = True
            break

    if not found:  # if we didn't find the old comment, make a new comment about the edit
        jira.add_comment(jira_issue.id, _get_jira_comment_body(gh_comment))


def handle_comment_deleted(jira, event):
    gh_comment = event["comment"]
    jira_issue = _find_jira_issue(jira, event["issue"], True)
    jira.add_comment(jira_issue.id, "@%s deleted [GitHub issue comment|%s]" % (gh_comment["user"]["login"], gh_comment["html_url"]))


def _update_link_resolved(jira, gh_issue, jira_issue):
    """
    Update the 'resolved' status of the remote "synced from" link, based on the
    GitHub issue open/closed status.

    (A 'resolved' link is shown in strikethrough format in JIRA interface.)

    Also updates the link title, if GitHub issue title has changed.
    """
    resolved = gh_issue["state"] == "closed"
    for link in jira.remote_links(jira_issue):
        if hasattr(link, "globalId") and link.globalId == gh_issue["html_url"]:
            new_link = dict(link.raw["object"])  # RemoteLink update() requires all fields as a JSON object, it seems
            new_link["title"] = gh_issue["title"]
            new_link["status"]["resolved"] = resolved
            link.update(new_link)


def _markdown2wiki(markdown):
    """
    Convert markdown to JIRA wiki format. Uses https://github.com/chunpu/markdown2confluence
    """
    with tempfile.NamedTemporaryFile('w+') as mdf:  # note: this won't work on Windows
        mdf.write(markdown)
        if not markdown.endswith('\n'):
            mdf.write('\n')
        mdf.flush()
        try:
            wiki = subprocess.check_output(['markdown2confluence', mdf.name])
            return wiki.decode('utf-8', errors='ignore')
        except subprocess.CalledProcessError as e:
            print("Failed to run markdown2confluence: %s. JIRA issue will have raw Markdown contents." % e)
            return markdown


def _get_description(gh_issue):
    """
    Return the JIRA description text that corresponds to the provided GitHub issue.
    """
    return """[GitHub Issue|%(github_url)s] from user @%(github_user)s:

    %(github_description)s

    ---

    Notes:

    * Do not edit this description text, it may be updated automatically.
    * Please interact on GitHub where possible, changes will sync to here.
    * If closing this issue from a commit, please add
      {code}
      Closes %(github_url)s
      {code}
      in the commit message so the commit is closed on GitHub automatically.
    """ % {
        "github_url": gh_issue["html_url"],
        "github_user": gh_issue["user"]["login"],
        "github_description": _markdown2wiki(gh_issue["body"]),
    }


def _get_summary(gh_issue):
    """
    Return the JIRA summary corresponding to a given GitHub issue

    Format is: GH #<gh issue number>: <github title without any JIRA slug>
    """
    result = "GH #%d: %s" % (gh_issue["number"], gh_issue["title"])

    # don't mirror any existing JIRA slug-like pattern from GH title to JIRA summary
    # (note we don't look for a particular pattern as the JIRA issue may have moved)
    result = re.sub(r" \([\w]+-[\d]+\)", "", result)

    return result


def _create_jira_issue(jira, gh_issue):
    """
    Create a new JIRA issue from the provided GitHub issue, then return the JIRA issue.
    """
    issuetype = _get_jira_issue_type(jira, gh_issue)
    if issuetype is None:
        issuetype = os.environ.get('JIRA_ISSUE_TYPE', 'Task')

    fields = {
        "summary": _get_summary(gh_issue),
        "project": os.environ['JIRA_PROJECT'],
        "description": _get_description(gh_issue),
        "issuetype": issuetype,
    }
    issue = jira.create_issue(fields)

    _add_remote_link(jira, issue, gh_issue)
    _update_github_with_jira_key(gh_issue, issue)

    return issue


def _add_remote_link(jira, issue, gh_issue):
    """
    Add the JIRA "remote link" field that points to the issue
    """
    gh_url = gh_issue["html_url"]
    jira.add_remote_link(issue=issue,
                         destination={"url": gh_url,
                                      "title": gh_issue["title"],
                                      },
                         globalId=gh_url,  # globalId is always the GitHub URL
                         relationship="synced from")


def _update_github_with_jira_key(gh_issue, jira_issue):
    """ Append the new JIRA issue key to the GitHub issue
        (updates made by github actions don't trigger new actions)
    """
    github = Github(os.environ["GITHUB_TOKEN"])

    # extract the 'org/repo' canonical name from the repo URL
    #
    # note: github also gives us 'repository' JSON which has a 'full_name', but this is simpler
    # for the API structure.
    repo_name = re.search(r'[^/]+/[^/]+$', gh_issue["repository_url"]).group(0)
    repo = github.get_repo(repo_name)

    api_gh_issue = repo.get_issue(gh_issue["number"])
    api_gh_issue.edit(title="%s (%s)" % (api_gh_issue.title, jira_issue.key))


def _get_jira_issue_type(jira, gh_issue):
    """
    Try to map a GitHub label to a JIRA issue type. Matches will happen when the label
    matches the issue type (case insensitive) or when the label has the form "Type: <issuetype>"
    """
    gh_labels = [l["name"] for l in gh_issue["labels"]]

    issue_types = jira.issue_types()

    for gh_label in gh_labels:
        for issue_type in issue_types:
            type_name = issue_type.name.lower()
            if gh_label.lower() in [type_name, "type: %s" % (type_name,)]:
                # a match!
                print("Mapping GitHub label '%s' to JIRA issue type '%s'" % (gh_label, issue_type.name))
                return {"id": issue_type.id}  # JIRA API needs JSON here

    return None  # updating a field to None seems to cause 'no change' for JIRA


def _find_jira_issue(jira, gh_issue, make_new=False, second_try=False):
    """Look for a JIRA issue which has a remote link to the provided GitHub issue.

    Will also find "manually synced" issues that point to each other by name
    (see README), and create the remote link.

    If make_new is True, a new issue will be created if one is not found.

    second_try is an internal parameter used when make_new is set, to try and
    avoid races when creating issues (wait a random amount of time and then look
    again). This is useful because often events on a GitHub issue come in a
    flurry, and they're not always processed in order.
    """
    url = gh_issue["html_url"]
    jql_query = 'issue in issuesWithRemoteLinksByGlobalId("%s") order by updated desc' % url
    print("JQL query: %s" % jql_query)
    r = jira.search_issues(jql_query)
    if len(r) == 0:
        print("WARNING: No JIRA issues have a remote link with globalID '%s'" % url)

        # Check if the github title ends in (JIRA-KEY). If we can find that JIRA issue and the JIRA issue description contains the
        # GitHub URL, assume this item was manually synced over.
        m = re.search(r"\(([A-Z]+-\d+)\)\s*$", gh_issue["title"])
        if m is not None:
            try:
                issue = jira.issue(m.group(1))
                if gh_issue["html_url"] in issue.fields.description:
                    print("Looks like this JIRA issue %s was manually synced. Adding a remote link for future lookups." % issue.key)
                    _add_remote_link(jira, issue, gh_issue)
                    return issue
            except jira.exceptions.JIRAError:
                pass  # issue doesn't exist or unauthorized

            # note: not logging anything on failure to avoid
            # potential information leak about other JIRA IDs

        if not make_new:
            return None
        elif not second_try:
            # Wait a random amount of time to see if this JIRA issue is still being created by another
            # GitHub Action. This is a hacky way to try and avoid the case where a GitHub issue is created
            # and edited in a short window of time, and the two GitHub Actions race each other and produce
            # two JIRA issues. It may still happen sometimes, though.
            time.sleep(random.randrange(30, 90))
            return _find_jira_issue(jira, gh_issue, True, True)
        else:
            return _create_jira_issue(jira, gh_issue)
    if len(r) > 1:
        print("WARNING: Remote Link globalID '%s' returns multiple JIRA issues. Using last-updated only." % url)
    return r[0]


def _leave_jira_issue_comment(jira, event, verb, should_create,
                              jira_issue=None):
    """
    Leave a simple comment that the GitHub issue corresponding to this event was 'verb' by the GitHub user in question.

    If jira_issue is set then this JIRA issue will be updated, otherwise the function will find the corresponding synced issue.

    If should_create is set then a new JIRA issue will be opened if one can't be found.
    """
    gh_issue = event["issue"]
    if jira_issue is None:
        jira_issue = _find_jira_issue(jira, event["issue"], should_create)
        if jira_issue is None:
            return None
    try:
        user = event["sender"]["login"]
    except KeyError:
        user = gh_issue["user"]["login"]

    jira.add_comment(jira_issue.id, "The [GitHub issue|%s] has been %s by @%s" % (gh_issue["html_url"], verb, user))
    return jira_issue


def _get_jira_comment_body(gh_comment, body=None):
    """
    Return a JIRA-formatted comment body that corresponds to the provided github comment's text
    or on an existing comment body message (if set).
    """
    if body is None:
        body = _markdown2wiki(gh_comment["body"])
    return "[GitHub issue comment|%s] by @%s:\n\n%s" % (gh_comment["html_url"], gh_comment["user"]["login"], body)


if __name__ == "__main__":
    main()