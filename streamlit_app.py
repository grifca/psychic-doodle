"""
GTM Auto-Auditor - Streamlit Application
========================================

This Streamlit app provides a user-friendly interface for auditing Google Tag
Manager (GTM) container exports. It allows users to upload a GTM JSON file,
parses the file to identify Google Analytics tags (Universal Analytics and
Google Analytics 4) and their trigger logic, and then displays the results
in an interactive table. Users can filter by tag type, inspect event names
and parameters, and download the results as a CSV for sharing.

Usage
-----
Install the required dependencies (streamlit and pandas) in your Python
environment. Then run the app with the following command:

```
pip install streamlit pandas
streamlit run streamlit_app.py
```

Once running, open the provided URL in your browser and upload a GTM
container export (JSON file). The app will display a summary table of
analytics tags along with their triggers and parameters, and provide a
download button for exporting the data as CSV.

"""

import json
import re
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import streamlit as st


def parse_parameters(param_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Flatten a GTM tag's parameter list into a simple dictionary.

    GTM stores parameters for each tag as a list of objects with `key`,
    `value`, and optionally `list` or `map` attributes. This helper
    function converts that list into a dictionary mapping parameter keys
    to string representations of their values. For complex values (lists
    or dictionaries), the value is JSON-serialised.

    Args:
        param_list: The `parameter` list from a GTM tag.

    Returns:
        A dictionary with parameter keys and their values as strings.
    """
    param_dict: Dict[str, Any] = {}
    for param in param_list or []:
        key = param.get("key")
        # If the parameter contains a "list" or "map" structure, serialise it.
        if "list" in param:
            param_dict[key] = json.dumps(param.get("list"), ensure_ascii=False)
        elif "map" in param:
            param_dict[key] = json.dumps(param.get("map"), ensure_ascii=False)
        else:
            param_dict[key] = param.get("value")
    return param_dict


def extract_value(parameter: Dict[str, Any]) -> Any:
    """Recursively flatten a GTM parameter object into a readable value."""
    if "value" in parameter:
        return parameter.get("value")
    if "list" in parameter:
        return [extract_value(item) for item in parameter.get("list", [])]
    if "map" in parameter:
        return {
            item.get("key"): extract_value(item)
            for item in parameter.get("map", [])
            if item.get("key")
        }
    return None


def extract_variables_from_value(value: Any) -> Set[str]:
    """Collect GTM variable tokens like {{Page Path}} from nested values."""
    variables: Set[str] = set()
    if isinstance(value, str):
        variables.update(re.findall(r"\{\{([^}]+)\}\}", value))
    elif isinstance(value, list):
        for item in value:
            variables.update(extract_variables_from_value(item))
    elif isinstance(value, dict):
        for item in value.values():
            variables.update(extract_variables_from_value(item))
    return variables


def describe_trigger_type(trigger_type: Optional[str]) -> str:
    """Map GTM trigger type codes to readable labels."""
    trigger_type_labels = {
        "PAGEVIEW": "Page View",
        "DOM_READY": "DOM Ready",
        "WINDOW_LOADED": "Window Loaded",
        "CLICK": "Click",
        "LINK_CLICK": "Link Click",
        "JUST_LINKS": "Link Click",
        "FORM_SUBMISSION": "Form Submission",
        "TIMER": "Timer",
        "SCROLL_DEPTH": "Scroll Depth",
        "ELEMENT_VISIBILITY": "Element Visibility",
        "CUSTOM_EVENT": "Custom Event",
        "YOUTUBE_VIDEO": "YouTube Video",
        "HISTORY_CHANGE": "History Change",
        "TRIGGER_GROUP": "Trigger Group",
        "AMP_CLICK": "AMP Click",
    }
    if not trigger_type:
        return ""
    return trigger_type_labels.get(trigger_type, trigger_type.replace("_", " ").title())


def describe_filter(filter_obj: Dict[str, Any]) -> str:
    """Convert a GTM filter object into a readable condition string."""
    filter_type = filter_obj.get("type", "")
    values = parse_parameters(filter_obj.get("parameter", []))
    arg0 = values.get("arg0", "")
    arg1 = values.get("arg1", "")
    ignore_case = str(values.get("ignore_case", "")).lower() == "true"
    operators = {
        "equals": "=",
        "contains": "contains",
        "matchRegex": "matches regex",
        "startsWith": "starts with",
        "endsWith": "ends with",
        "greater": ">",
        "less": "<",
    }

    if filter_type == "hasOwnProperty":
        return f"{arg0} exists"
    if filter_type == "cssSelector":
        return f"{arg0} matches selector {arg1}"

    operator = operators.get(filter_type, filter_type or "condition")
    description = " ".join(str(part) for part in [arg0, operator, arg1] if part)
    if ignore_case and description:
        description += " (ignore case)"
    return description


def extract_trigger_metadata(trigger: Dict[str, Any]) -> Dict[str, str]:
    """Build reporting fields for a GTM trigger."""
    custom_event_filter = parse_parameters(trigger.get("customEventFilter", []))
    filter_descriptions = [describe_filter(f) for f in trigger.get("filter", [])]
    auto_event_descriptions = [describe_filter(f) for f in trigger.get("autoEventFilter", [])]

    trigger_conditions = " AND ".join(
        part
        for part in filter_descriptions + auto_event_descriptions
        if part
    )
    if custom_event_filter.get("arg0") or custom_event_filter.get("arg1"):
        event_match = " ".join(
            str(part)
            for part in [
                custom_event_filter.get("arg0"),
                "matches",
                custom_event_filter.get("arg1"),
            ]
            if part
        )
        trigger_conditions = " AND ".join(part for part in [event_match, trigger_conditions] if part)

    variables: Set[str] = set()
    for key in ("filter", "autoEventFilter", "customEventFilter", "parameter"):
        for item in trigger.get(key, []):
            variables.update(extract_variables_from_value(extract_value(item)))

    trigger_name = trigger.get("name", "")
    trigger_type = describe_trigger_type(trigger.get("type"))
    normalized_name = trigger_name.lower()
    all_pages = (
        "Yes"
        if "all pages" in normalized_name
        or (trigger.get("type") == "PAGEVIEW" and not trigger_conditions)
        else "No"
    )

    area_of_site = ""
    conditions_lower = trigger_conditions.lower()
    if "page path" in conditions_lower or "page url" in conditions_lower:
        area_of_site = trigger_conditions
    elif all_pages == "Yes":
        area_of_site = "Entire site"

    return {
        "Status (Live/Paused)": "Paused" if trigger.get("paused") else "Live",
        "Trigger Name": trigger_name,
        "Trigger Type": trigger_type,
        "Trigger Conditions": trigger_conditions,
        "Variables Used": ", ".join(sorted(variables)),
        "All Pages?": all_pages,
        "Area of Site": area_of_site,
    }


def parse_gtm_container(data: Dict[str, Any]) -> pd.DataFrame:
    """Parse a GTM container JSON to extract analytics tags and their metadata.

    A GTM export JSON may contain the actual container data under the key
    ``containerVersion`` (as part of the workspace export). This function
    normalises the structure and then iterates through all tags, selecting
    those that relate to Google Analytics (Universal Analytics or GA4). It
    builds a data frame containing the tag name, type, firing triggers,
    key event properties, and other parameters. Non-analytics tags are
    ignored.

    Args:
        data: The loaded JSON object from a GTM container export.

    Returns:
        A pandas DataFrame where each row corresponds to an analytics tag.
    """
    # If the export is a workspace export, the container data lives under
    # ``containerVersion``.
    if "containerVersion" in data:
        container = data["containerVersion"]
    else:
        container = data
    tags = container.get("tag", [])
    triggers = container.get("trigger", [])
    # Build a lookup for full trigger definitions by ID for quick reference.
    trigger_map: Dict[str, Dict[str, Any]] = {t.get("triggerId"): t for t in triggers}
    rows: List[Dict[str, Any]] = []

    # GTM tag type identifiers for analytics tags.
    analytics_types = {
        "gaawe": "GA4 Event",
        "googtag": "GA4 Configuration",
        "ua": "Universal Analytics",
    }

    for tag in tags:
        tag_type = tag.get("type")
        if tag_type not in analytics_types:
            # Skip non-analytics tags.
            continue
        tag_name = tag.get("name", "")
        type_label = analytics_types[tag_type]
        firing_ids = tag.get("firingTriggerId", [])
        # Parse parameters to extract event-related fields.
        param_dict = parse_parameters(tag.get("parameter", []))
        # Derive key fields for reporting.
        event_name = param_dict.get("eventName")
        event_category = param_dict.get("eventCategory") or param_dict.get("category")
        event_action = param_dict.get("eventAction") or param_dict.get("action")
        event_label = param_dict.get("eventLabel") or param_dict.get("label")
        # Exclude these fields from the generic parameters column.
        exclude_keys = {
            "eventName",
            "eventCategory",
            "category",
            "eventAction",
            "action",
            "eventLabel",
            "label",
        }
        other_params = {
            k: v
            for k, v in param_dict.items()
            if k not in exclude_keys and v not in (None, "")
        }
        other_params_str = "; ".join(f"{k}={v}" for k, v in other_params.items())
        variables_used = set(extract_variables_from_value(other_params))
        event_or_action = " | ".join(
            str(value)
            for value in [event_name, event_category, event_action, event_label]
            if value not in (None, "")
        )

        if not firing_ids:
            firing_ids = [None]

        for trigger_id in firing_ids:
            trigger = trigger_map.get(trigger_id, {})
            trigger_metadata = (
                extract_trigger_metadata(trigger)
                if trigger
                else {
                    "Status (Live/Paused)": "Live",
                    "Trigger Name": f"ID:{trigger_id}" if trigger_id else "",
                    "Trigger Type": "",
                    "Trigger Conditions": "",
                    "Variables Used": "",
                    "All Pages?": "No",
                    "Area of Site": "",
                }
            )
            combined_variables = sorted(
                {
                    *variables_used,
                    *(
                        set(trigger_metadata["Variables Used"].split(", "))
                        if trigger_metadata["Variables Used"]
                        else set()
                    ),
                }
            )
            rows.append(
                {
                    "Tag Name": tag_name,
                    "Tag Type": type_label,
                    "Status (Live/Paused)": "Paused" if tag.get("paused") else trigger_metadata["Status (Live/Paused)"],
                    "Trigger Name": trigger_metadata["Trigger Name"],
                    "Trigger Type": trigger_metadata["Trigger Type"],
                    "Trigger Conditions": trigger_metadata["Trigger Conditions"],
                    "Variables Used": ", ".join(v for v in combined_variables if v),
                    "Event Name / Action": event_or_action,
                    "All Pages?": trigger_metadata["All Pages?"],
                    "Area of Site": trigger_metadata["Area of Site"],
                    "Event Name": event_name,
                    "Event Category": event_category,
                    "Event Action": event_action,
                    "Event Label": event_label,
                    "Parameters": other_params_str,
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    preferred_columns = [
        "Status (Live/Paused)",
        "Trigger Name",
        "Trigger Type",
        "Trigger Conditions",
        "Variables Used",
        "Event Name / Action",
        "All Pages?",
        "Area of Site",
        "Tag Name",
        "Tag Type",
        "Event Name",
        "Event Category",
        "Event Action",
        "Event Label",
        "Parameters",
    ]
    available_columns = [column for column in preferred_columns if column in df.columns]
    return df[available_columns]


def main() -> None:
    """Streamlit app entry point."""
    st.set_page_config(page_title="GTM Auto-Auditor", layout="wide")
    st.title("GTM Auto-Auditor")
    st.markdown(
        """
        Upload a Google Tag Manager (GTM) container export to audit your current
        analytics tagging implementation. This tool will identify Google Analytics
        tags (Universal Analytics and GA4), display their firing triggers, event
        names, and parameters, and allow you to download the results as a CSV.
        """,
    )
    uploaded_file = st.file_uploader(
        "Upload GTM container JSON", type=["json"], accept_multiple_files=False
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap');

        .stFileUploader label,
        div[data-testid="stFileUploader"] label,
        div[data-testid="stFileUploaderDropzoneInstructions"] span {
            font-family: "Manrope", sans-serif !important;
        }

        div[data-testid="stPopover"] button {
            align-items: center;
            color: #8ec5ff;
            background: none;
            border: 0;
            display: inline-flex;
            gap: 0.25rem;
            justify-content: flex-start;
            padding: 0;
            font-size: 0.95rem;
            width: auto;
        }
        div[data-testid="stPopover"] button:hover {
            color: #8ec5ff;
        }
        div[data-testid="stPopover"] button p {
            margin: 0;
            text-decoration: underline;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    help_text = (
        "In GTM, go to Admin > Export Container, select a workspace or version, "
        "and click Download to save a .json file."
    )
    if uploaded_file is not None:
        try:
            # Load JSON data from the uploaded file.
            file_bytes = uploaded_file.read()
            container_data = json.loads(file_bytes)
            df = parse_gtm_container(container_data)
            if df.empty:
                st.warning(
                    "No Google Analytics tags were found in this container.\n"
                    "Please check that you exported the correct container and that it contains"
                    " Universal Analytics or GA4 tags."
                )
            else:
                # Provide a filter for tag types.
                tag_types = ["All"] + sorted(df["Tag Type"].unique().tolist())
                selected_type = st.selectbox("Filter by Tag Type", tag_types)
                if selected_type != "All":
                    filtered_df = df[df["Tag Type"] == selected_type]
                else:
                    filtered_df = df
                st.subheader("Tag Inventory")
                st.dataframe(filtered_df, use_container_width=True)
                # Download button for CSV export.
                csv_data = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name="gtm_analytics_inventory.csv",
                    mime="text/csv",
                )
        except json.JSONDecodeError:
            st.error("Unable to parse the uploaded file. Please ensure it is a valid JSON export from GTM.")
        except Exception as e:
            st.error(f"An error occurred while processing the file: {e}")
    else:
        st.info("Please upload a GTM container JSON file to get started.")

    if hasattr(st, "popover"):
        with st.popover("how do I get my GTM container?"):
            st.write(help_text)
    else:
        st.caption(help_text)


if __name__ == "__main__":
    main()
