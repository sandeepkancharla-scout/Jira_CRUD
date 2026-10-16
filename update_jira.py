import json
import os
import sys

import requests
from requests.auth import HTTPBasicAuth


def required_env(name):
    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing GitHub secret or environment variable: {name}"
        )

    return value


def print_response(response):
    print(f"HTTP status: {response.status_code}")

    try:
        print(
            json.dumps(
                response.json(),
                indent=2,
            )
        )
    except ValueError:
        if response.text:
            print(response.text)


def request_or_fail(
    method,
    url,
    auth,
    headers,
    operation,
    **kwargs,
):
    response = requests.request(
        method=method,
        url=url,
        auth=auth,
        headers=headers,
        timeout=30,
        **kwargs,
    )

    if not response.ok:
        print()
        print(f"FAILED: {operation}")
        print(f"Request URL: {url}")
        print_response(response)

        raise RuntimeError(
            f"{operation} failed with "
            f"HTTP {response.status_code}"
        )

    return response


def main():
    jira_url = required_env(
        "JIRA_URL"
    ).rstrip("/")

    jira_email = required_env(
        "JIRA_EMAIL"
    )

    jira_token = required_env(
        "JIRA_TOKEN"
    )

    issue_key = required_env(
        "ISSUE_KEY"
    ).upper()

    fields_json = required_env(
        "FIELDS_JSON"
    )

    try:
        fields = json.loads(
            fields_json
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "FIELDS_JSON is not valid JSON."
        ) from exc

    if not isinstance(fields, dict):
        raise RuntimeError(
            "FIELDS_JSON must be a JSON object."
        )

    if not fields:
        print("No changed fields received.")
        sys.exit(0)

    auth = HTTPBasicAuth(
        jira_email,
        jira_token,
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    print("=" * 70)
    print("JIRA UPDATE THROUGH GITHUB ACTIONS")
    print("=" * 70)

    print(f"Jira site: {jira_url}")
    print(f"Jira account: {jira_email}")
    print(f"Issue: {issue_key}")

    print()
    print("Requested fields:")

    for field_id in fields:
        print(f" - {field_id}")

    # -------------------------------------------------
    # Step 1: Validate authentication
    # -------------------------------------------------

    print()
    print("Step 1: Validating Jira authentication...")

    myself_url = (
        f"{jira_url}/rest/api/3/myself"
    )

    myself_response = request_or_fail(
        method="GET",
        url=myself_url,
        auth=auth,
        headers=headers,
        operation="Jira authentication validation",
    )

    myself = myself_response.json()

    print(
        "Authenticated as: "
        f"{myself.get('displayName', 'Unknown')}"
    )

    print(
        "Account ID: "
        f"{myself.get('accountId', 'Unknown')}"
    )

    # -------------------------------------------------
    # Step 2: Validate issue visibility
    # -------------------------------------------------

    print()
    print(
        "Step 2: Checking whether the account "
        "can view the Jira issue..."
    )

    issue_url = (
        f"{jira_url}"
        f"/rest/api/3/issue/"
        f"{issue_key}"
    )

    issue_response = request_or_fail(
        method="GET",
        url=issue_url,
        auth=auth,
        headers=headers,
        operation="Jira issue visibility check",
        params={
            "fields": "summary,status",
        },
    )

    issue = issue_response.json()

    print(
        "Issue found: "
        f"{issue.get('key')}"
    )

    print(
        "Summary: "
        f"{issue.get('fields', {}).get('summary')}"
    )

    # ------------------------------------
