import json

def clean_json_response(response: str) -> str:
    """Clean and extract article content from various JSON response formats."""
    # Remove any triple quotes and markdown formatting
    response = response.replace("```json", "").replace("```", "")

    # Check if response starts with a markdown header or plain text
    if response.strip().startswith("##") or not response.strip().startswith("{"):
        return response

    try:
        # First attempt: Try to parse the entire response as JSON
        data = json.loads(response)

        # Handle different JSON structures we might receive
        if isinstance(data, dict):
            if "article" in data:
                return data["article"]
            elif "content" in data:
                if isinstance(data["content"], str):
                    return data["content"]
                try:
                    nested_content = json.loads(data["content"])
                    if isinstance(nested_content, dict):
                        if "article" in nested_content:
                            return nested_content["article"]
                        elif "content" in nested_content:
                            return nested_content["content"]
                except Exception:
                    return data["content"]
            elif "role" in data and "content" in data:
                return data["content"]
            elif "article_content" in data:
                return data["article_content"]
            elif all(key in data for key in ["article_content", "section_titles", "meta_title", "meta_description"]):
                return data["article_content"]

        return response

    except json.JSONDecodeError:
        if not response.strip().startswith("{"):
            return response

        start_idx = response.find("{")
        end_idx = response.rfind("}")

        if start_idx == -1 or end_idx == -1:
            return response

        json_str = response[start_idx : end_idx + 1].strip()
        try:
            data = json.loads(json_str)
            return clean_json_response(json.dumps(data))
        except Exception:
            return response

def extract_article_content(response_text):
    try:
        json_str = clean_json_response(response_text)
        response_data = json.loads(json_str)
        if isinstance(response_data, dict) and "article" in response_data:
            return response_data["article"]
        return response_text
    except Exception:
        return response_text 