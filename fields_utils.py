import json
from datetime import date, datetime


def normalize_for_comparison(value):
    return json.dumps(
        value,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def values_are_equal(old_value, new_value):
    return (
        normalize_for_comparison(old_value)
        == normalize_for_comparison(new_value)
    )


def option_label(option):
    if option is None:
        return ""

    if not isinstance(option, dict):
        return str(option)

    return str(
        option.get("displayName")
        or option.get("name")
        or option.get("value")
        or option.get("key")
        or option.get("id")
        or option.get("accountId")
        or json.dumps(option, sort_keys=True)
    )


def option_payload(option):
    if option is None:
        return None

    if not isinstance(option, dict):
        return option

    if option.get("accountId"):
        return {
            "accountId": option["accountId"],
        }

    if option.get("id"):
        return {
            "id": option["id"],
        }

    if option.get("value"):
        return {
            "value": option["value"],
        }

    if option.get("key"):
        return {
            "key": option["key"],
        }

    if option.get("name"):
        return {
            "name": option["name"],
        }

    return option


def value_to_display_text(value):
    if value is None:
        return ""

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, (str, int, float)):
        return str(value)

    if isinstance(value, dict):
        return option_label(value)

    if isinstance(value, list):
        return ", ".join(
            option_label(item)
            for item in value
        )

    return str(value)


def adf_to_text(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if not isinstance(value, dict):
        return value_to_display_text(value)

    collected = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return

        if not isinstance(node, dict):
            return

        node_type = node.get("type")

        if node_type == "text":
            collected.append(
                node.get("text", "")
            )

        elif node_type == "hardBreak":
            collected.append("\n")

        for child in node.get(
            "content",
            [],
        ):
            walk(child)

        if node_type in {
            "paragraph",
            "heading",
            "blockquote",
            "listItem",
        }:
            collected.append("\n")

    walk(value)

    return "".join(collected).strip()


def text_to_adf(text):
    text = text or ""

    paragraphs = text.splitlines()

    if not paragraphs:
        paragraphs = [""]

    content = []

    for paragraph in paragraphs:
        paragraph_content = []

        if paragraph:
            paragraph_content.append(
                {
                    "type": "text",
                    "text": paragraph,
                }
            )

        content.append(
            {
                "type": "paragraph",
                "content": paragraph_content,
            }
        )

    return {
        "version": 1,
        "type": "doc",
        "content": content,
    }


def is_adf_field(field_id, metadata, current_value):
    schema = metadata.get(
        "schema",
        {},
    )

    custom_type = schema.get(
        "custom",
        "",
    )

    if isinstance(current_value, dict):
        if (
            current_value.get("type") == "doc"
            and current_value.get("version") == 1
        ):
            return True

    if field_id in {
        "description",
        "environment",
    }:
        return True

    return (
        "textarea" in custom_type
        or "richtext" in custom_type
    )


def parse_date_value(value):
    if not value:
        return None

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(
            str(value)[:10]
        )

    except ValueError:
        return None


def parse_datetime_value(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).replace(
        "Z",
        "+00:00",
    )

    try:
        return datetime.fromisoformat(text)

    except ValueError:
        return None


def date_to_jira(value):
    if value is None:
        return None

    return value.isoformat()


def datetime_to_jira(value):
    if value is None:
        return None

    return value.isoformat()


def build_allowed_value_maps(allowed_values):
    labels = []
    lookup = {}

    for option in allowed_values:
        label = option_label(option)

        if not label:
            continue

        unique_label = label
        counter = 2

        while unique_label in lookup:
            unique_label = (
                f"{label} ({counter})"
            )
            counter += 1

        labels.append(unique_label)

        lookup[unique_label] = (
            option_payload(option)
        )

    return labels, lookup


def parse_json_value(raw_text):
    try:
        return json.loads(raw_text)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON: {exc}"
        ) from exc


def format_json_value(value):
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        default=str,
    )