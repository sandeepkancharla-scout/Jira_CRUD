import json
import os
import sys

import requests
from requests.auth import HTTPBasicAuth


def get_required_env(name):
    """
    Read a required environment variable.
    """

    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value


def print_response(response):
    """
    Print Jira error response safely.
    """

    print(f"HTTP Status: {response.status_code}")

    try:
        data = response.json()

        print(
            json.dumps(
                data,
                indent=2
            )
        )

    except ValueError:

        if response.text:
            print(response.text)


def jira_request(
    method,
    url,
    auth,
    headers,
    operation,
    **kwargs
):
    """
    Execute Jira REST API request and
    show useful diagnostics on failure.
    """

    try:

        response = requests.request(
            method=method,
            url=url,
            auth=auth,
            headers=headers,
            timeout=30,
            **kwargs
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            f"{operation} failed because Jira "
            f"could not be reached: {exc}"
        ) from exc

    if not response.ok:

        print()
        print("=" * 70)
        print(f"FAILED: {operation}")
        print("=" * 70)

        print(f"URL: {url}")

        print_response(response)

        raise RuntimeError(
            f"{operation} failed with "
            f"HTTP {response.status_code}"
        )

    return response


def main():

    # =====================================================
    # ENVIRONMENT VARIABLES
    # =====================================================

    jira_url = get_required_env(
        "JIRA_URL"
    ).rstrip("/")

    jira_email = get_required_env(
        "JIRA_EMAIL"
    )

    jira_token = get_required_env(
        "JIRA_TOKEN"
    )

    issue_key = get_required_env(
        "ISSUE_KEY"
    ).upper()

    fields_json = get_required_env(
        "FIELDS_JSON"
    )


    # =====================================================
    # PARSE UPDATE FIELDS
    # =====================================================

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
            "FIELDS_JSON must contain "
            "a JSON object."
        )


    if not fields:

        print(
            "No changed fields received."
        )

        sys.exit(0)


    # =====================================================
    # AUTHENTICATION
    # =====================================================

    auth = HTTPBasicAuth(
        jira_email,
        jira_token
    )


    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


    print("=" * 70)
    print("JIRA UPDATE THROUGH GITHUB ACTIONS")
    print("=" * 70)

    print()

    print(
        f"Jira Site   : {jira_url}"
    )

    print(
        f"Jira Account: {jira_email}"
    )

    print(
        f"Issue       : {issue_key}"
    )


    print()

    print("Requested fields:")

    for field_id in fields:

        print(
            f" - {field_id}"
        )


    # =====================================================
    # STEP 1
    # VERIFY JIRA AUTHENTICATION
    # =====================================================

    print()
    print("=" * 70)
    print(
        "STEP 1: Validating Jira authentication"
    )
    print("=" * 70)


    myself_url = (
        f"{jira_url}"
        f"/rest/api/3/myself"
    )


    myself_response = jira_request(
        method="GET",
        url=myself_url,
        auth=auth,
        headers=headers,
        operation=(
            "Jira authentication validation"
        )
    )


    myself = myself_response.json()


    print(
        "Authentication successful."
    )


    print(
        "Authenticated as: "
        f"{myself.get('displayName', 'Unknown')}"
    )


    print(
        "Account ID: "
        f"{myself.get('accountId', 'Unknown')}"
    )


    # =====================================================
    # STEP 2
    # VERIFY TICKET ACCESS
    # =====================================================

    print()
    print("=" * 70)
    print(
        "STEP 2: Checking Jira issue access"
    )
    print("=" * 70)


    issue_url = (
        f"{jira_url}"
        f"/rest/api/3/issue/"
        f"{issue_key}"
    )


    issue_response = jira_request(
        method="GET",
        url=issue_url,
        auth=auth,
        headers=headers,
        operation=(
            "Jira issue visibility check"
        ),
        params={
            "fields": (
                "summary,status,issuetype,"
                "priority,assignee"
            )
        }
    )


    issue = issue_response.json()

    issue_fields = issue.get(
        "fields",
        {}
    )


    print(
        f"Issue found: "
        f"{issue.get('key', issue_key)}"
    )


    print(
        "Current Summary: "
        f"{issue_fields.get('summary', '')}"
    )


    status = issue_fields.get(
        "status"
    )

    if isinstance(status, dict):

        print(
            "Current Status: "
            f"{status.get('name', '')}"
        )


    # =====================================================
    # STEP 3
    # GET EDITABLE FIELDS
    # =====================================================

    print()
    print("=" * 70)
    print(
        "STEP 3: Retrieving editable fields"
    )
    print("=" * 70)


    editmeta_url = (
        f"{jira_url}"
        f"/rest/api/3/issue/"
        f"{issue_key}/editmeta"
    )


    editmeta_response = jira_request(
        method="GET",
        url=editmeta_url,
        auth=auth,
        headers=headers,
        operation=(
            "Retrieving Jira editable fields"
        )
    )


    editmeta = (
        editmeta_response.json()
    )


    editable_fields = (
        editmeta.get(
            "fields",
            {}
        )
    )


    print(
        f"Editable fields returned: "
        f"{len(editable_fields)}"
    )


    print()

    print("Editable fields:")


    for field_id, metadata in (
        editable_fields.items()
    ):

        field_name = metadata.get(
            "name",
            field_id
        )

        operations = metadata.get(
            "operations",
            []
        )

        print(
            f" - {field_name} "
            f"({field_id}) "
            f"operations={operations}"
        )


    # =====================================================
    # STEP 4
    # VALIDATE REQUESTED FIELDS
    # =====================================================

    print()
    print("=" * 70)
    print(
        "STEP 4: Validating requested fields"
    )
    print("=" * 70)


    invalid_fields = []

    unsupported_fields = []


    for field_id in fields:

        metadata = editable_fields.get(
            field_id
        )


        if metadata is None:

            invalid_fields.append(
                field_id
            )

            continue


        operations = metadata.get(
            "operations",
            []
        )


        if (
            operations
            and "set" not in operations
        ):

            unsupported_fields.append(
                field_id
            )


    if invalid_fields:

        raise RuntimeError(
            "These fields are not currently "
            "editable in Jira: "
            + ", ".join(
                invalid_fields
            )
        )


    if unsupported_fields:

        raise RuntimeError(
            "These fields do not support "
            "the SET operation: "
            + ", ".join(
                unsupported_fields
            )
        )


    print(
        "Requested fields passed validation."
    )


    # =====================================================
    # STEP 5
    # UPDATE JIRA
    # =====================================================

    print()
    print("=" * 70)
    print(
        "STEP 5: Updating Jira"
    )
    print("=" * 70)


    payload = {
        "fields": fields
    }


    print(
        "Sending fields:"
    )


    print(
        json.dumps(
            payload,
            indent=2
        )
    )


    try:

        update_response = requests.put(
            issue_url,
            auth=auth,
            headers=headers,
            json=payload,
            timeout=30
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            "Unable to send update to Jira: "
            f"{exc}"
        ) from exc


    print(
        f"Jira HTTP status: "
        f"{update_response.status_code}"
    )


    if update_response.status_code not in (
        200,
        204
    ):

        print()
        print("JIRA UPDATE FAILED")

        print_response(
            update_response
        )

        raise RuntimeError(
            "Jira update failed with "
            f"HTTP {update_response.status_code}"
        )


    # =====================================================
    # STEP 6
    # VERIFY UPDATE
    # =====================================================

    print()
    print("=" * 70)
    print(
        "STEP 6: Verifying Jira update"
    )
    print("=" * 70)


    verify_response = jira_request(
        method="GET",
        url=issue_url,
        auth=auth,
        headers=headers,
        operation=(
            "Jira update verification"
        )
    )


    updated_issue = (
        verify_response.json()
    )


    updated_fields = (
        updated_issue.get(
            "fields",
            {}
        )
    )


    print(
        "Update verification completed."
    )


    print()

    print("Updated values:")


    for field_id in fields:

        value = updated_fields.get(
            field_id
        )

        print(
            f"{field_id}: "
            f"{json.dumps(value, default=str)}"
        )


    # =====================================================
    # SUCCESS
    # =====================================================

    print()
    print("=" * 70)

    print(
        f"SUCCESS: {issue_key} "
        "was updated successfully."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()