import requests
from requests.auth import HTTPBasicAuth


class JiraClient:
    def __init__(self, jira_url, email, token):
        self.jira_url = jira_url.rstrip("/")
        self.auth = HTTPBasicAuth(email, token)

        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _handle_response(self, response, operation):
        if response.ok:
            return

        message = response.text

        try:
            error_data = response.json()

            error_messages = error_data.get(
                "errorMessages",
                [],
            )

            field_errors = error_data.get(
                "errors",
                {},
            )

            message_parts = []

            message_parts.extend(error_messages)

            for field_id, error in field_errors.items():
                message_parts.append(
                    f"{field_id}: {error}"
                )

            if message_parts:
                message = " | ".join(message_parts)

        except ValueError:
            pass

        raise RuntimeError(
            f"{operation} failed. "
            f"HTTP {response.status_code}: {message}"
        )

    def get_issue(self, issue_key):
        issue_key = issue_key.strip().upper()

        url = (
            f"{self.jira_url}"
            f"/rest/api/3/issue/"
            f"{issue_key}"
        )

        params = {
            "expand": "names,schema",
        }

        response = requests.get(
            url,
            headers=self.headers,
            auth=self.auth,
            params=params,
            timeout=30,
        )

        self._handle_response(
            response,
            "Fetching Jira issue",
        )

        return response.json()

    def get_editable_fields(self, issue_key):
        issue_key = issue_key.strip().upper()

        url = (
            f"{self.jira_url}"
            f"/rest/api/3/issue/"
            f"{issue_key}/editmeta"
        )

        response = requests.get(
            url,
            headers=self.headers,
            auth=self.auth,
            timeout=30,
        )

        self._handle_response(
            response,
            "Fetching editable fields",
        )

        return response.json().get(
            "fields",
            {},
        )

    def load_ticket(self, issue_key):
        issue = self.get_issue(issue_key)

        editable_fields = self.get_editable_fields(
            issue_key
        )

        return {
            "issue": issue,
            "editable_fields": editable_fields,
        }