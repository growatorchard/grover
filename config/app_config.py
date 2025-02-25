from typing import Dict, List, Any

class AppConfig:
    DEFAULT_SESSION_STATE = {
        "drafts_by_article": {},
        "meta_title_by_article": {},
        "meta_desc_by_article": {},
        "refine_instructions_by_article": {},
        "topic_suggestions": [],
        "selected_topic": "",
        "article_brief": "",
        "token_usage_history": [],
        "show_project_success": False,
        "project_id": None,
        "article_id": None
    }

    TARGET_AUDIENCES = [
        "Adult Children",
        "Seniors",
        "Healthcare Professionals",
        "Family Caregivers"
    ]

    MODEL_OPTIONS = {
        "ChatGPT (o1)": "o1-mini"
    }

    CARE_AREAS = [
        "Independent Living",
        "Assisted Living", 
        "Memory Care",
        "Skilled Nursing"
    ]

    JOURNEY_STAGES = [
        "Awareness",
        "Consideration", 
        "Decision",
        "Retention",
        "Advocacy",
        "Other"
    ] 