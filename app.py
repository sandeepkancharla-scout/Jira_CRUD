import json
from datetime import date

import streamlit as st

from field_utils import (
    adf_to_text,
    build_allowed_value_maps,
    date_to_jira,
    format_json_value,
    is_adf_field,
    option_label,
    option_payload,
    parse_date_value,
    parse_json_value,
    text_to_adf,
    value_to_display_text,
    values_are_equal,
)

from github_client import GitHubClient
from jira_client import JiraClient


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Jira Ticket Editor",
    page_icon="🎫",
    layout="wide",
)

st.title("Jira Ticket Editor")

st.caption(
    "Fetch Jira-editable fields, modify them, "
    "and submit changed fields through GitHub Actions."
)


# =====================================================
# CLIENTS
# =====================================================

jira_client = JiraClient(
    jira_url=st.secrets["JIRA_URL"],
    email=st.secrets["JIRA_EMAIL"],
    token=st.secrets["JIRA_TOKEN"],
)

github_client = GitHubClient(
    owner=st.secrets["GITHUB_OWNER"],
    repo=st.secrets["GITHUB_REPO"],
    token=st.secrets["GITHUB_TOKEN"],
    branch=st.secrets.get(
        "GITHUB_BRANCH",
        "main",
    ),
    workflow=st.secrets.get(
        "GITHUB_WORKFLOW",
        "update-jira.yml",
    ),
)


# =====================================================
# SESSION STATE
# =====================================================

DEFAULT_STATE = {
    "loaded_issue": None,
    "editable_fields": {},
    "original_values": {},
    "loaded_issue_key": "",
}

for key, default_value in (
    DEFAULT_STATE.items()
):
    if key not in st.session_state:
        st.session_state[key] = (
            default_value
        )


# =====================================================
# HELPERS
# =====================================================

def reset_ticket_state():
    st.session_state.loaded_issue = None
    st.session_state.editable_fields = {}
    st.session_state.original_values = {}
    st.session_state.loaded_issue_key = ""


def make_widget_key(field_id):
    return f"jira_field_{field_id}"


def find_original_option_label(
    original_value,
    labels,
    lookup,
):
    original_payload = option_payload(
        original_value
    )

    for label in labels:
        if values_are_equal(
            lookup[label],
            original_payload,
        ):
            return label

    original_label = option_label(
        original_value
    )

    if original_label:
        unique_label = original_label
        counter = 2

        while unique_label in lookup:
            unique_label = (
                f"{original_label} "
                f"({counter})"
            )
            counter += 1

        labels.insert(
            0,
            unique_label,
        )

        lookup[unique_label] = (
            original_payload
        )

        return unique_label

    return labels[0] if labels else ""


def render_single_select(
    field_id,
    field_name,
    original_value,
    allowed_values,
):
    labels, lookup = (
        build_allowed_value_maps(
            allowed_values
        )
    )

    if original_value is None:
        labels.insert(0, "<None>")
        lookup["<None>"] = None

    original_label = (
        find_original_option_label(
            original_value,
            labels,
            lookup,
        )
    )

    if not labels:
        return original_value

    selected_label = st.selectbox(
        field_name,
        options=labels,
        index=labels.index(
            original_label
        ),
        key=make_widget_key(
            field_id
        ),
    )

    return lookup[selected_label]


def render_multi_select(
    field_id,
    field_name,
    original_value,
    allowed_values,
):
    labels, lookup = (
        build_allowed_value_maps(
            allowed_values
        )
    )

    original_value = (
        original_value
        if isinstance(
            original_value,
            list,
        )
        else []
    )

    selected_defaults = []

    for original_item in original_value:
        matched_label = None

        for label in labels:
            if values_are_equal(
                lookup[label],
                option_payload(
                    original_item
                ),
            ):
                matched_label = label
                break

        if matched_label:
            selected_defaults.append(
                matched_label
            )

    selected_labels = st.multiselect(
        field_name,
        options=labels,
        default=selected_defaults,
        key=make_widget_key(
            field_id
        ),
    )

    return [
        lookup[label]
        for label in selected_labels
    ]


def render_field(
    field_id,
    metadata,
    original_value,
):
    field_name = metadata.get(
        "name",
        field_id,
    )

    schema = metadata.get(
        "schema",
        {},
    )

    field_type = schema.get(
        "type",
        "string",
    )

    field_items = schema.get(
        "items",
        "",
    )

    allowed_values = metadata.get(
        "allowedValues",
        [],
    )

    required = metadata.get(
        "required",
        False,
    )

    operations = metadata.get(
        "operations",
        [],
    )

    label = (
        f"{field_name} *"
        if required
        else field_name
    )

    if (
        operations
        and "set" not in operations
    ):
        st.warning(
            f"{field_name} is editable in Jira "
            "but does not support the SET operation. "
            f"Supported operations: {operations}"
        )

        st.json(original_value)

        return original_value

    if (
        field_type == "array"
        and allowed_values
    ):
        return render_multi_select(
            field_id,
            label,
            original_value,
            allowed_values,
        )

    if allowed_values:
        return render_single_select(
            field_id,
            label,
            original_value,
            allowed_values,
        )

    if is_adf_field(
        field_id,
        metadata,
        original_value,
    ):
        entered_text = st.text_area(
            label,
            value=adf_to_text(
                original_value
            ),
            height=180,
            key=make_widget_key(
                field_id
            ),
        )

        return text_to_adf(
            entered_text
        )

    if field_type == "boolean":
        return st.checkbox(
            label,
            value=bool(
                original_value
            ),
            key=make_widget_key(
                field_id
            ),
        )

    if field_type in {
        "number",
        "integer",
    }:
        default_value = (
            original_value
            if isinstance(
                original_value,
                (int, float),
            )
            else 0
        )

        value = st.number_input(
            label,
            value=default_value,
            key=make_widget_key(
                field_id
            ),
        )

        if field_type == "integer":
            return int(value)

        return value

    if field_type == "date":
        original_date = parse_date_value(
            original_value
        )

        clear_field = st.checkbox(
            f"Clear {field_name}",
            value=False,
            key=(
                f"{make_widget_key(field_id)}"
                "_clear"
            ),
        )

        if clear_field:
            return None

        selected_date = st.date_input(
            label,
            value=(
                original_date
                or date.today()
            ),
            key=make_widget_key(
                field_id
            ),
        )

        return date_to_jira(
            selected_date
        )

    if (
        field_type == "array"
        and field_items == "string"
    ):
        current_text = (
            ", ".join(
                str(item)
                for item in original_value
            )
            if isinstance(
                original_value,
                list,
            )
            else ""
        )

        entered_text = st.text_input(
            label,
            value=current_text,
            help=(
                "Enter multiple values "
                "separated by commas."
            ),
            key=make_widget_key(
                field_id
            ),
        )

        return [
            item.strip()
            for item in entered_text.split(",")
            if item.strip()
        ]

    if field_type == "string":
        custom_type = schema.get(
            "custom",
            "",
        )

        if "textarea" in custom_type:
            return st.text_area(
                label,
                value=(
                    original_value
                    if isinstance(
                        original_value,
                        str,
                    )
                    else ""
                ),
                height=160,
                key=make_widget_key(
                    field_id
                ),
            )

        return st.text_input(
            label,
            value=(
                original_value
                if isinstance(
                    original_value,
                    str,
                )
                else ""
            ),
            key=make_widget_key(
                field_id
            ),
        )

    if original_value is None:
        st.caption(
            f"{field_name} has no current "
            "value and Jira did not return "
            "allowed values."
        )

        raw_value = st.text_area(
            label,
            value="null",
            height=100,
            help=(
                "Enter a valid Jira JSON "
                "value for this field."
            ),
            key=make_widget_key(
                field_id
            ),
        )

        return parse_json_value(
            raw_value
        )

    if isinstance(
        original_value,
        (dict, list),
    ):
        st.caption(
            f"{field_name} is a complex Jira "
            "field. Edit its JSON carefully."
        )

        raw_value = st.text_area(
            label,
            value=format_json_value(
                original_value
            ),
            height=180,
            help=(
                "The JSON structure must match "
                "the value expected by Jira."
            ),
            key=make_widget_key(
                field_id
            ),
        )

        return parse_json_value(
            raw_value
        )

    return st.text_input(
        label,
        value=value_to_display_text(
            original_value
        ),
        key=make_widget_key(
            field_id
        ),
    )


# =====================================================
# FETCH TICKET
# =====================================================

st.subheader(
    "1. Load Jira ticket"
)

ticket_column, button_column = (
    st.columns([4, 1])
)

with ticket_column:
    entered_issue_key = st.text_input(
        "Jira ticket number",
        placeholder="SYSINT-15258",
    )

with button_column:
    st.write("")
    st.write("")

    fetch_button = st.button(
        "Fetch ticket",
        type="primary",
        use_container_width=True,
    )


if fetch_button:
    issue_key = (
        entered_issue_key
        .strip()
        .upper()
    )

    if not issue_key:
        st.warning(
            "Enter a Jira ticket number."
        )

    else:
        try:
            reset_ticket_state()

            with st.spinner(
                f"Fetching {issue_key}..."
            ):
                ticket_data = (
                    jira_client.load_ticket(
                        issue_key
                    )
                )

            issue = ticket_data[
                "issue"
            ]

            editable_fields = ticket_data[
                "editable_fields"
            ]

            issue_fields = issue.get(
                "fields",
                {},
            )

            original_values = {
                field_id: issue_fields.get(
                    field_id
                )
                for field_id
                in editable_fields
            }

            st.session_state.loaded_issue = (
                issue
            )

            st.session_state.editable_fields = (
                editable_fields
            )

            st.session_state.original_values = (
                original_values
            )

            st.session_state.loaded_issue_key = (
                issue["key"]
            )

            st.success(
                f"{issue['key']} loaded. "
                f"Jira returned "
                f"{len(editable_fields)} "
                "editable fields."
            )

        except Exception as exc:
            st.error(str(exc))


# =====================================================
# EDIT FORM
# =====================================================

issue = st.session_state.loaded_issue
editable_fields = (
    st.session_state.editable_fields
)
original_values = (
    st.session_state.original_values
)


if issue:
    st.divider()

    summary = (
        issue.get(
            "fields",
            {},
        ).get(
            "summary",
            "",
        )
    )

    st.subheader(
        f"2. Edit {issue['key']}"
    )

    if summary:
        st.write(
            f"**Current summary:** {summary}"
        )

    if not editable_fields:
        st.warning(
            "Jira returned no editable fields. "
            "Check the account's Edit Issues "
            "permission and the issue status."
        )

    else:
        field_values = {}
        field_errors = []

        with st.form(
            "jira_edit_form"
        ):
            for field_id, metadata in (
                editable_fields.items()
            ):
                try:
                    field_values[field_id] = (
                        render_field(
                            field_id,
                            metadata,
                            original_values.get(
                                field_id
                            ),
                        )
                    )

                except ValueError as exc:
                    field_errors.append(
                        f"{metadata.get('name', field_id)}: "
                        f"{exc}"
                    )

            st.divider()

            submitted = (
                st.form_submit_button(
                    "Update Jira ticket",
                    type="primary",
                    use_container_width=True,
                )
            )

        if submitted:
            if field_errors:
                for error in field_errors:
                    st.error(error)

            else:
                changed_fields = {}

                for field_id, new_value in (
                    field_values.items()
                ):
                    old_value = (
                        original_values.get(
                            field_id
                        )
                    )

                    if not values_are_equal(
                        old_value,
                        new_value,
                    ):
                        changed_fields[
                            field_id
                        ] = new_value

                if not changed_fields:
                    st.info(
                        "No changes detected. "
                        "Nothing was sent to "
                        "GitHub Actions."
                    )

                else:
                    st.subheader(
                        "Detected changes"
                    )

                    for field_id, new_value in (
                        changed_fields.items()
                    ):
                        metadata = (
                            editable_fields.get(
                                field_id,
                                {},
                            )
                        )

                        field_name = (
                            metadata.get(
                                "name",
                                field_id,
                            )
                        )

                        old_value = (
                            original_values.get(
                                field_id
                            )
                        )

                        with st.expander(
                            field_name,
                            expanded=False,
                        ):
                            st.write("Old value")

                            st.code(
                                format_json_value(
                                    old_value
                                ),
                                language="json",
                            )

                            st.write("New value")

                            st.code(
                                format_json_value(
                                    new_value
                                ),
                                language="json",
                            )

                    try:
                        with st.spinner(
                            "Triggering GitHub "
                            "Actions..."
                        ):
                            github_client.trigger_jira_update(
                                issue["key"],
                                changed_fields,
                            )

                        st.success(
                            "Update submitted to "
                            "GitHub Actions."
                        )

                        st.info(
                            "Open the repository's "
                            "Actions page to see the "
                            "workflow result. Fetch "
                            "the ticket again after "
                            "the workflow succeeds to "
                            "load Jira's latest values."
                        )

                    except Exception as exc:
                        st.error(str(exc))