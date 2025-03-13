from typing import Dict, List, Any

class AppConfig:
    DEFAULT_SESSION_STATE = {
        "drafts_by_article": {},
        "meta_title_by_article": {},
        "meta_desc_by_article": {},
        "refine_instructions_by_article": {},
        "topic_suggestions": [],
        "selected_topic": "",
        "article_outline": "",
        "token_usage_history": [],
        "show_project_success": False,
        "project_id": None,
        "article_id": None
    }