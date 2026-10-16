import json
import os
import sys

import requests
from requests.auth import HTTPBasicAuth


def read_required_environment_variable(name):
    value = os.environ.get(
        name,
        "",
    ).strip()

    if not value:
        raise RuntimeError(
            f"Required environment variable "
            f"{name} is missing."
        )

    return value


def print_jira_error(response):
    print("Jira response:")

    try:
        body = response.json()

        error_messages = body.get(
            "errorMessages",
            [],
        )

        field_errors = body.get(
            "errors",
            {},
        )

        for message in error_messages:
            print(f" - {message}")

        for field_id, message in (
            field_errors.items()
        ):
            print(
                f" - {field_id}: {message}"
            )

        if not error_messages and not field_errors:
            print(
                json.dumps(
                    body,
                    indent=2,
                )
            )

    except ValueError:
        print(response.text)


def main():
    jira_url = read_required_environment_variable(
        "JIRA_URL"
    ).rstrip("/")

    jira_email = (
        read_required_environment_variable(
            "JIRA_EMAIL"
        )
    )

    jira_token = (
        read_required_environment_variable(
            "JIRA_TOKEN"
        )
    )

    issue_key = (
        read_required_environment_variable(
            "ISSUE_KEY"
        ).upper()
    )

    fields_json = (
        read_required_environment_variable(
            "FIELDS_JSON"
        )
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
            "FIELDS_JSON must contain "
            "a JSON object."
        )

    if not fields:
        print(
            "No changed fields received."
        )

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
    print(f"Issue: {issue_key}")
    print()

    print("Requested fields:")

    for field_id in fields:
        print(f" - {field_id}")

    editmeta_url = (
        f"{jira_url}"
        f"/rest/api/3/issue/"
        f"{issue_key}/editmeta"
    )

    print()
    print(
        "Validating fields against "
        "current Jira edit metadata..."
    )

    editmeta_response = requests.get(
        editmeta_url,
        headers=headers,
        auth=auth,
        timeout=30,
    )

    if not editmeta_response.ok:
        print_jira_error(
            editmeta_response
        )

        raise RuntimeError(
            "Unable to retrieve current Jira "
            "edit metadata. "
            f"HTTP {editmeta_response.status_code}"
        )

    editable_fields = (
        editmeta_response.json().get(
            "fields",
            {},
        )
    )

    invalid_fields = []

    unsupported_operation_fields = []

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
            [],
        )

        if (
            operations
            and "set" not in operations
        ):
            unsupported_operation_fields.append(
                field_id
            )

    if invalid_fields:
        raise RuntimeError(
            "These fields are no longer "
            "editable for this issue: "
            + ", ".join(invalid_fields)
        )

    if unsupported_operation_fields:
        raise RuntimeError(
            "These fields do not support the "
            "set operation: "
            + ", ".join(
                unsupported_operation_fields
            )
        )

    update_url = (
        f"{jira_url}"
        f"/rest/api/3/issue/"
        f"{issue_key}"
    )

    payload = {
        "fields": fields,
    }

    print()
    print(
        "Editable-field validation passed."
    )

    print(
        "Sending changed fields to Jira..."
    )

    response = requests.put(
        update_url,
        headers=headers,
        auth=auth,
        json=payload,
        timeout=30,
    )

    print(
        f"Jira HTTP status: "
        f"{response.status_code}"
    )

    if response.status_code not in {
        200,
        204,
    }:
        print_jira_error(response)

        raise RuntimeError(
            "Jira update failed. "
            f"HTTP {response.status_code}"
        )

    print()
    print("=" * 70)
    print(
        f"SUCCESS: {issue_key} "
        "was updated."
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
