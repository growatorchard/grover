import os
import requests
import streamlit as st
def build_semrush_url(api_type, phrase, api_key, database="us", export_columns="", display_limit=None, debug_mode=False):
    """Build the Semrush API URL with the required parameters."""
    base_url = "https://api.semrush.com"
    params = {
        "type": api_type,
        "key": api_key,
        "phrase": phrase,
        "database": database,
    }
    if export_columns:
        params["export_columns"] = export_columns
    if display_limit is not None:
        params["display_limit"] = display_limit

    query_str = "&".join([f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()])
    full_url = f"{base_url}/?{query_str}"
    return full_url

def parse_semrush_response(response_text, debug_mode=False):
    """Utility to parse SEMrush CSV-like response text."""
    # Check if there are newline characters; if not, assume one single line response.
    lines = response_text.strip().split("\n")
    if len(lines) == 1:
        parts = lines[0].split(";")
        if len(parts) < 4:
            return []
        # First 4 parts are headers.
        headers = parts[:4]
        # Map headers to desired keys.
        header_map = {
            "Keyword": "Ph",
            "Search Volume": "Nq",
            "Keyword Difficulty Index": "Kd",
            "Intent 3rd stage ckd": "In"
        }
        mapped_headers = [header_map.get(h.strip(), h.strip()) for h in headers]
        data_rows = []
        # Group subsequent parts in groups of 4.
        for i in range(4, len(parts), 4):
            row = parts[i:i+4]
            if len(row) == 4:
                row_dict = {mapped_headers[j]: row[j].strip() for j in range(4)}
                data_rows.append(row_dict)
        return data_rows
    else:
        # If multiple lines, assume first line is header.
        headers = lines[0].split(";")
        header_map = {
            "Keyword": "Ph",
            "Search Volume": "Nq",
            "Keyword Difficulty Index": "Kd",
            "Intent 3rd stage ckd": "In"
        }
        mapped_headers = [header_map.get(h.strip(), h.strip()) for h in headers]
        data = []
        for line in lines[1:]:
            row_values = line.split(";")
            if len(row_values) != len(mapped_headers):
                continue
            row_dict = {mapped_headers[i]: row_values[i].strip() for i in range(len(mapped_headers))}
            data.append(row_dict)
        return data

def query_semrush_api(keyword, database="us", debug_mode=False):
    """Query SEMrush API using the new related keyword research route."""
    api_key = os.getenv("SEMRUSH_API_KEY", "")
    if not api_key:
        return {"error": "No SEMRUSH_API_KEY found in .env"}
    try:
        # Build the new URL using the updated parameters
        new_url = (
            f"https://api.semrush.com/?type=phrase_related"
            f"&key={api_key}"
            f"&phrase={keyword}"
            f"&export_columns=Keyword,Search Volume,Keyword Difficulty Index,Intent 3rd stage ckd"
            f"&database={database}"
            f"&display_limit=25"
            f"&display_sort=kd_desc"
            f"&display_filter=%2B|Nq|Gt|99|%2B|Nq|Lt|1501|%2B|Kd|Lt|41|%2B|Kd|Gt|9"
        )
        response = requests.get(new_url)
        if debug_mode:
            st.write("Raw SEMrush API response:")
            st.write(response.text)
        if response.status_code != 200:
            raise ValueError(f"Request error (HTTP {response.status_code}): {response.text}")

        data = parse_semrush_response(response.text, debug_mode=debug_mode)
        if not data:
            return {"overview": None, "related_keywords": [], "error": "No data returned"}

        # Use the first result as the main overview
        main_keyword = data[0]
        overview_obj = {
            "Ph": main_keyword.get("Ph", keyword),
            "Nq": main_keyword.get("Nq", "0"),
            "Kd": main_keyword.get("Kd", "0"),
            "In": main_keyword.get("In", ""),
        }

        # Process the full list as related keywords
        related_list = []
        for item in data:
            related_list.append({
                "Ph": item.get("Ph", ""),
                "Nq": item.get("Nq", "0"),
                "Kd": item.get("Kd", "0"),
                "In": item.get("In", ""),
            })

        return {"overview": overview_obj, "related_keywords": related_list, "error": None}
    except Exception as e:
        return {"overview": None, "related_keywords": [], "error": f"Exception: {str(e)}"}

def get_keyword_suggestions(topic, debug_mode=False):
    """Returns a dict with main_keyword, related_keywords, error."""
    results = query_semrush_api(topic, debug_mode=debug_mode)
    if results.get("error"):
        return results
    return {"main_keyword": results["overview"], "related_keywords": results["related_keywords"], "error": None}

def format_keyword_report(keyword_data):
    """Format keyword data into a readable report."""
    if not keyword_data or keyword_data.get("error"):
        return "No keyword data available"
    lines = ["Keyword Research Report:\n"]
    main = keyword_data.get("main_keyword")
    if main:
        lines.append(f"**Main Keyword**: {main.get('Ph', 'N/A')}")
        lines.append(f"- Volume: {main.get('Nq', 'N/A')}")
        lines.append(f"- Difficulty: {main.get('Kd', 'N/A')}")
        lines.append("")
    related = keyword_data.get("related_keywords", [])
    if related:
        lines.append("**Related Keywords**:")
        for rk in related:
            lines.append(f" - {rk.get('Ph', 'N/A')} (Vol={rk.get('Nq', 'N/A')}, Diff={rk.get('Kd', 'N/A')}, Intent={rk.get('In', 'N/A')})")
    return "\n".join(lines)