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
    """Parse the semicolon-delimited response from SEMrush API."""
    lines = response_text.strip().split("\n")
    
    if len(lines) <= 1:
        return []
    
    headers = [h.strip() for h in lines[0].split(";")]
    result = []
    for i in range(1, len(lines)):
        values = lines[i].split(";")
        if len(values) == len(headers):
            item = {}
            for j in range(len(headers)):
                # Map the header to the shortened format used in the API
                header_key = headers[j]
                if header_key == "Keyword":
                    item["Ph"] = values[j]
                elif header_key == "Search Volume":
                    item["Nq"] = values[j]
                elif header_key == "Keyword Difficulty Index":
                    item["Kd"] = values[j]
                elif header_key == "Intent":
                    item["In"] = values[j].strip()
                else:
                    # Keep any other headers as they are
                    item[header_key] = values[j]
            result.append(item)
    
    return result

def get_keyword_suggestions(keyword, database="us", debug_mode=False):
    """Get keyword suggestions from SEMrush."""
    result = query_semrush_api(keyword, database, debug_mode)
    if result.get("error"):
        return result
    
    return {
        "main_keyword": result.get("overview"),
        "related_keywords": result.get("related_keywords", []),
        "error": result.get("error"),
    }

def query_semrush_api(keyword, database="us", debug_mode=False):
    """Query SEMrush API using the new related keyword research route."""
    api_key = os.getenv("SEMRUSH_API_KEY", "")
    if not api_key:
        return {"error": "No SEMRUSH_API_KEY found in .env"}
    try:
        # Build the new URL using the correct export columns
        new_url = (
            f"https://api.semrush.com/?type=phrase_related"
            f"&key={api_key}"
            f"&phrase={keyword}"
            f"&export_columns=Ph,Nq,Kd,In"
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
        main_keyword = data[0] if data else {}
        overview_obj = {
            "Ph": main_keyword.get("Ph", keyword),
            "Nq": main_keyword.get("Nq", "0"),
            "Kd": main_keyword.get("Kd", "0"),
            "In": main_keyword.get("In", ""),
        }

        # Process the full list as related keywords
        related_list = []
        for item in data:
            item = {k: v.strip() for k, v in item.items()}
            related_list.append({
                "Ph": item.get("Ph", ""),
                "Nq": item.get("Nq", "0"),
                "Kd": item.get("Kd", "0"),
                "In": item.get("In", ""),
            })
            print(related_list)

        return {"overview": overview_obj, "related_keywords": related_list, "error": None}
    except Exception as e:
        if debug_mode:
            st.error(f"SEMrush API error: {str(e)}")
        return {"overview": None, "related_keywords": [], "error": str(e)}

def format_keyword_report(keyword_data):
    """Format keyword data into a readable report."""
    if not keyword_data or keyword_data.get("error"):
        return "No keyword data available"
    
    # Intent mapping for human-readable display
    intent_map = {
        "0": "Commercial (specific page, site, or physical location)",
        "1": "Informational (investigate brands or services)",
        "2": "Navigational (complete an action)",
        "3": "Transactional (find an answer to a specific question)",
    }
    
    short_intent_map = {
        "0": "Commercial",
        "1": "Informational",
        "2": "Navigational",
        "3": "Transactional",
    }
    
    lines = ["Keyword Research Report:\n"]
    main = keyword_data.get("main_keyword")
    if main:
        lines.append(f"**Main Keyword**: {main.get('Ph', 'N/A')}")
        lines.append(f"- Volume: {main.get('Nq', 'N/A')}")
        lines.append(f"- Difficulty: {main.get('Kd', 'N/A')}")
        
        # Get intent with full description for main keyword
        intent_value = main.get("In", "N/A")
        intent_desc = intent_map.get(intent_value, "N/A")
        lines.append(f"- Intent: {intent_desc}")
        lines.append("")
    
    related = keyword_data.get("related_keywords", [])
    if related:
        lines.append("**Related Keywords**:")
        for rk in related:
            # Get short intent for related keywords
            intent_value = rk.get("In", "N/A")
            intent_desc = short_intent_map.get(intent_value, "N/A")
            lines.append(f" - {rk.get('Ph', 'N/A')} (Vol={rk.get('Nq', 'N/A')}, Diff={rk.get('Kd', 'N/A')}, Intent={intent_desc})")
    
    return "\n".join(lines)