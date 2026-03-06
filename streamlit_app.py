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


def inject_styles() -> None:
    """Apply a Quint-inspired editorial theme to the Streamlit app."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Manrope:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f6f1e8;
            --paper: rgba(255, 252, 247, 0.82);
            --paper-strong: #fffdf8;
            --ink: #1f1b16;
            --muted: #6c6258;
            --line: rgba(31, 27, 22, 0.14);
            --accent: #b85c38;
            --accent-soft: rgba(184, 92, 56, 0.12);
            --shadow: 0 24px 70px rgba(49, 37, 24, 0.08);
            --radius: 24px;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(184, 92, 56, 0.16), transparent 28%),
                radial-gradient(circle at 85% 15%, rgba(82, 107, 91, 0.12), transparent 24%),
                linear-gradient(180deg, #f8f3ea 0%, #f4ede3 100%);
            color: var(--ink);
        }

        .main .block-container {
            max-width: 1120px;
            padding-top: 3rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 {
            font-family: "Fraunces", Georgia, serif !important;
            color: var(--ink);
            letter-spacing: -0.03em;
        }

        p, li, label, div[data-testid="stMarkdownContainer"] {
            font-family: "Manrope", sans-serif !important;
        }

        .quint-shell {
            display: grid;
            gap: 1.4rem;
        }

        .quint-hero {
            background: linear-gradient(135deg, rgba(255, 252, 247, 0.84), rgba(255, 248, 240, 0.72));
            border: 1px solid var(--line);
            border-radius: 32px;
            box-shadow: var(--shadow);
            overflow: hidden;
            position: relative;
            padding: 3rem;
        }

        .quint-hero::after {
            content: "";
            position: absolute;
            inset: auto -6% -30% auto;
            width: 22rem;
            height: 22rem;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(184, 92, 56, 0.2), transparent 68%);
            pointer-events: none;
        }

        .quint-kicker {
            color: var(--accent);
            font: 700 0.8rem/1 "Manrope", sans-serif;
            letter-spacing: 0.24em;
            margin-bottom: 1rem;
            text-transform: uppercase;
        }

        .quint-hero h1 {
            font-size: clamp(3rem, 7vw, 5.8rem);
            line-height: 0.92;
            margin: 0;
            max-width: 9ch;
        }

        .quint-lead {
            color: var(--muted);
            font-size: 1.1rem;
            line-height: 1.75;
            margin-top: 1.25rem;
            max-width: 42rem;
        }

        .quint-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
        }

        .quint-card {
            backdrop-filter: blur(10px);
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            padding: 1.4rem;
        }

        .quint-card h3,
        .quint-card h4 {
            margin: 0 0 0.6rem 0;
        }

        .quint-card p,
        .quint-card li {
            color: var(--muted);
            line-height: 1.7;
            margin: 0;
        }

        .quint-card ul {
            margin: 0.7rem 0 0 1rem;
            padding: 0;
        }

        .quint-section-title {
            font-size: 2rem;
            margin-bottom: 0.35rem;
        }

        .quint-section-copy {
            color: var(--muted);
            margin-bottom: 1rem;
            max-width: 44rem;
        }

        .quint-metrics {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin: 1rem 0 1.25rem 0;
        }

        .quint-metric {
            background: var(--paper-strong);
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 1.1rem 1.2rem;
        }

        .quint-metric-label {
            color: var(--muted);
            font: 600 0.82rem/1.3 "Manrope", sans-serif;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .quint-metric-value {
            color: var(--ink);
            font: 700 clamp(1.8rem, 4vw, 2.6rem)/1 "Fraunces", Georgia, serif;
            margin-top: 0.55rem;
        }

        div[data-testid="stFileUploader"] {
            background: rgba(255, 252, 247, 0.7);
            border: 1.5px dashed rgba(31, 27, 22, 0.18);
            border-radius: 20px;
            padding: 0.5rem;
        }

        div[data-testid="stFileUploader"] section {
            padding: 1.4rem 1rem;
        }

        .stButton button,
        .stDownloadButton button,
        div[data-testid="stBaseButton-secondary"] {
            background: var(--ink);
            border: 1px solid var(--ink);
            border-radius: 999px;
            color: #fffaf3;
            font-family: "Manrope", sans-serif;
            font-weight: 700;
            min-height: 2.8rem;
            padding: 0.5rem 1.1rem;
            transition: all 120ms ease;
        }

        .stButton button:hover,
        .stDownloadButton button:hover,
        div[data-testid="stBaseButton-secondary"]:hover {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }

        .stSelectbox label,
        .stFileUploader label {
            color: var(--ink);
            font-weight: 700;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 22px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        div[data-testid="stAlert"] {
            border-radius: 18px;
            border: 1px solid var(--line);
        }

        div[data-testid="stPopover"] button {
            align-items: center;
            color: var(--accent);
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
            color: #8e482d;
        }

        div[data-testid="stPopover"] button p {
            margin: 0;
            text-decoration: underline;
        }

        @media (max-width: 900px) {
            .quint-grid,
            .quint-metrics {
                grid-template-columns: 1fr;
            }

            .quint-hero {
                padding: 2rem 1.4rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric(label: str, value: str) -> None:
    """Render a styled metric card."""
    st.markdown(
        f"""
        <div class="quint-metric">
            <div class="quint-metric-label">{label}</div>
            <div class="quint-metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Streamlit app entry point."""
    st.set_page_config(page_title="GTM Auto-Auditor", layout="wide")
    inject_styles()

    st.markdown(
        """
        <section class="quint-hero">
            <div class="quint-kicker">Analytics Audit</div>
            <h1>Read your GTM container like an editor.</h1>
            <p class="quint-lead">
                Upload a Google Tag Manager export and turn a noisy container into a clean
                inventory of GA4 and Universal Analytics tags, firing logic, and event details.
            </p>
        </section>
        """
        ,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <section class="quint-grid">
            <article class="quint-card">
                <h3>What it pulls</h3>
                <p>Tag names, analytics type, firing triggers, event fields, and remaining parameters.</p>
            </article>
            <article class="quint-card">
                <h3>What it skips</h3>
                <p>Non-analytics tags stay out of the report so the output remains useful for audits and handoff docs.</p>
            </article>
            <article class="quint-card">
                <h3>What you get</h3>
                <p>An on-screen inventory you can filter, review, and export as CSV for cleanup or migration work.</p>
            </article>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="quint-card">
            <h2 class="quint-section-title">Upload a container export</h2>
            <p class="quint-section-copy">
                Use a workspace or container version export from GTM. The parser will normalize the structure and surface analytics tags only.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Upload GTM container JSON", type=["json"], accept_multiple_files=False
    )
    help_text = (
        "In GTM, go to Admin > Export Container, select a workspace or version, "
        "and click Download to save a .json file."
    )
    if hasattr(st, "popover"):
        with st.popover("how do I get my GTM container?"):
            st.write(help_text)
    else:
        st.caption(help_text)
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
                st.markdown(
                    """
                    <div class="quint-card">
                        <h2 class="quint-section-title">Tag inventory</h2>
                        <p class="quint-section-copy">
                            Review the extracted analytics implementation below, then download the filtered result set if you need a shareable audit artifact.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                metric_columns = st.columns(3)
                with metric_columns[0]:
                    render_metric("Analytics Tags", str(len(filtered_df)))
                with metric_columns[1]:
                    render_metric("Tag Types", str(filtered_df["Tag Type"].nunique()))
                with metric_columns[2]:
                    trigger_count = (
                        filtered_df["Triggers"]
                        .fillna("")
                        .map(lambda value: len([item for item in value.split(", ") if item]))
                        .sum()
                    )
                    render_metric("Trigger Links", str(trigger_count))
                st.dataframe(filtered_df, use_container_width=True)
                # Download button for CSV export.
                csv_data = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download audit CSV",
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
