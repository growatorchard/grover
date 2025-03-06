import os
import json
import requests
from utils.json_cleaner import clean_json_response
from utils.token_calculator import calculate_token_costs

def query_chatgpt_api(message: str, conversation_history: list = None) -> tuple[str, dict, str]:
    """
    Calls OpenAI's Chat Completion API (ChatGPT) with conversation history support.
    Requires st.secrets['OPENAI_API_KEY'] to be set.
    Returns a tuple of (response_content, token_usage, raw_response)
    """
    url = "https://api.openai.com/v1/chat/completions"
    try:
        api_key = os.getenv("OPENAI_API_KEY")
    except Exception:
        return "Error: No OPENAI_API_KEY found in st.secrets.", {}, ""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": message})
    payload = {"model": "o1-mini", "messages": messages, "max_completion_tokens": 20000}
    # print entire prompt/message
    print(json.dumps(payload, indent=2))
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=240)
        response.raise_for_status()
        response_data = response.json()
        raw_response = json.dumps(response_data, indent=2)
        if "choices" in response_data and len(response_data["choices"]) > 0:
            content = response_data["choices"][0]["message"]["content"]
            token_usage = response_data.get("usage", {})
            if conversation_history is not None:
                conversation_history.append({"role": "assistant", "content": content})
            return content, token_usage, raw_response
        return "Could not extract content from ChatGPT response.", {}, raw_response
    except requests.exceptions.RequestException as e:
        error_message = f"API request failed: {str(e)}"
        if hasattr(e, "response") and e.response is not None:
            error_message += f"\nResponse: {e.response.text}"
            raw_error = e.response.text
        else:
            raw_error = str(e)
        return error_message, {}, raw_error
    except Exception as e:
        return f"Unexpected error: {str(e)}", {}, str(e)

def query_llm_api(message: str, conversation_history: list = None) -> tuple[str, dict, str]:
    """
    Dispatches the API call to the selected LLM based on the sidebar model selection.
    Returns: (processed_response, token_usage, raw_response)
    """
    model = st.session_state.get("selected_model", "ChatGPT (o1)")
    if model == "ChatGPT (o1)":
        return query_chatgpt_api(message, conversation_history)
    else:
        return "Selected model not supported.", {}, ""

def generate_meta_content(article_content):
    """Generate meta title and description for an article."""
    prompt = f"""Given the following article content, generate an SEO-optimized meta title and meta description.
    
Requirements:
- Meta title: 50-60 characters, compelling and keyword-rich
- Meta description: 150-160 characters, engaging summary with call-to-action
- If any critical information seems to be missing, infer it from context and proceed with generation
- Focus on the main topic and value proposition even if some details are unclear

Article Content:
{article_content}

Return the response in JSON format:
{{
    "meta_title": "your generated title",
    "meta_description": "your generated description"
}}
"""
    response_text, token_usage, raw_response = query_llm_api(prompt)
    try:
        response_data = json.loads(clean_json_response(response_text))
        return response_data.get("meta_title", ""), response_data.get("meta_description", "")
    except Exception:
        return "", ""
