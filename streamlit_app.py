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
import base64
from typing import Any, Dict, List, Optional

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
    # Build a lookup for trigger names by ID for quick reference.
    trigger_map: Dict[str, str] = {t.get("triggerId"): t.get("name") for t in triggers}
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
        # Resolve trigger IDs to names.
        firing_ids = tag.get("firingTriggerId", [])
        trigger_names = [trigger_map.get(i, f"ID:{i}") for i in firing_ids]
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
        rows.append(
            {
                "Tag Name": tag_name,
                "Tag Type": type_label,
                "Triggers": ", ".join(trigger_names),
                "Event Name": event_name,
                "Event Category": event_category,
                "Event Action": event_action,
                "Event Label": event_label,
                "Parameters": other_params_str,
            }
        )
    return pd.DataFrame(rows)


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
        """
    )

    uploaded_file = st.file_uploader(
        "Upload GTM container JSON", type=["json"], accept_multiple_files=False
    )
    st.markdown(
        """
        <style>
        .gtm-help {
            margin-top: -0.5rem;
            margin-bottom: 1rem;
        }
        .gtm-help details {
            display: inline-block;
            position: relative;
        }
        .gtm-help summary {
            color: #1d4ed8;
            cursor: pointer;
            text-decoration: underline;
            list-style: none;
        }
        .gtm-help summary::-webkit-details-marker {
            display: none;
        }
        .gtm-help .tooltip {
            background: #111827;
            border-radius: 0.5rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
            color: #ffffff;
            font-size: 0.9rem;
            line-height: 1.4;
            margin-top: 0.5rem;
            max-width: 24rem;
            padding: 0.75rem 0.9rem;
            position: absolute;
            width: max-content;
            z-index: 1000;
        }
        @media (hover: hover) and (pointer: fine) {
            .gtm-help details .tooltip {
                display: none;
            }
            .gtm-help details:hover .tooltip,
            .gtm-help details:focus-within .tooltip,
            .gtm-help details[open] .tooltip {
                display: block;
            }
        }
        </style>
        <div class="gtm-help">
            <details>
                <summary>how do I get my GTM container?</summary>
                <div class="tooltip">
                    In GTM, go to Admin &gt; Export Container, select a workspace or
                    version, and click Download to save a .json file.
                </div>
            </details>
        </div>
        """,
        unsafe_allow_html=True,
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


if __name__ == "__main__":
    main()
    
