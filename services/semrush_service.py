import os
import requests

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

def query_semrush_api(keyword, database="us", lookup_type="phrase_related", debug_mode=False):
    """Query SEMrush API using the new related keyword research route."""
    api_key = os.getenv("SEMRUSH_API_KEY", "")
    if not api_key:
        return {"error": "No SEMRUSH_API_KEY found in .env"}
    try:
        # Build the new URL using the correct export columns
        new_url = (
            f"https://api.semrush.com/?type={lookup_type}"
            f"&key={api_key}"
            f"&phrase={keyword}"
            f"&export_columns=Ph,Nq,Kd,In"
            f"&database={database}"
            f"&display_limit=30"
            f"&display_sort=kd_desc"
            f"&display_filter=%2B|Nq|Gt|99|%2B|Nq|Lt|1501|%2B|Kd|Lt|41|%2B|Kd|Gt|9"
        )
        response = requests.get(new_url)
        if response.status_code != 200:
            raise ValueError(f"Request error (HTTP {response.status_code}): {response.text}")

        data = parse_semrush_response(response.text, debug_mode=debug_mode)

        if not data:
            return {"overview": None, "lookup_results": [], "error": "No data returned"}

        results_list = []
        for item in data:
            item = {k: v.strip() for k, v in item.items()}
            results_list.append({
                "Ph": item.get("Ph", ""),
                "Nq": item.get("Nq", "0"),
                "Kd": item.get("Kd", "0"),
                "In": item.get("In", ""),
            })

        seed_phrase_url = (
            f"https://api.semrush.com/?type=phrase_all"
            f"&key={api_key}"
            f"&phrase={keyword}"
            f"&export_columns=Ph,Nq,Kd,In"
            f"&database={database}"
        )

        seed_phrase_response = requests.get(seed_phrase_url)
        if seed_phrase_response.status_code != 200:
            raise ValueError(f"Request error (HTTP {seed_phrase_response.status_code}): {seed_phrase_response.text}")

        seed_phrase_data = parse_semrush_response(seed_phrase_response.text, debug_mode=debug_mode)

        return {"lookup_results": results_list, "seed_phrase_results": seed_phrase_data, "error": None}
    except Exception as e:
        return {"overview": None, "lookup_results": [], "seed_phrase_results": [], "error": str(e)}
    
def get_keyword_suggestions(keyword, database="us", lookup_type="phrase_related", debug_mode=False):
    """Get keyword suggestions from SEMrush."""
    result = query_semrush_api(keyword, database, lookup_type, debug_mode)
    if result.get("error"):
        return result
    
    return {
        "lookup_results": result.get("lookup_results", []),
        "seed_phrase_results": result.get("seed_phrase_results", []),
        "error": result.get("error"),
    }
