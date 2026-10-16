import json

import requests


class GitHubClient:
    def __init__(
        self,
        owner,
        repo,
        token,
        branch="main",
        workflow="update-jira.yml",
    ):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.branch = branch
        self.workflow = workflow

        self.headers = {
            "Accept": (
                "application/vnd.github+json"
            ),
            "Authorization": (
                f"Bearer {self.token}"
            ),
            "X-GitHub-Api-Version": (
                "2022-11-28"
            ),
        }

    def trigger_jira_update(
        self,
        issue_key,
        fields,
    ):
        if not fields:
            raise ValueError(
                "No changed Jira fields supplied."
            )

        url = (
            "https://api.github.com/repos/"
            f"{self.owner}/"
            f"{self.repo}/"
            "actions/workflows/"
            f"{self.workflow}/"
            "dispatches"
        )

        fields_json = json.dumps(
            fields,
            separators=(",", ":"),
        )

        payload = {
            "ref": self.branch,
            "inputs": {
                "issue_key": (
                    issue_key.strip().upper()
                ),
                "fields_json": fields_json,
            },
        }

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=30,
        )

        if response.status_code != 204:
            raise RuntimeError(
                "Unable to trigger GitHub Action. "
                f"HTTP {response.status_code}: "
                f"{response.text}"
            )

        return True