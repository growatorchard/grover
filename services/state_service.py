from typing import Any, Optional
from config.app_config import AppConfig

class StateService:
    @staticmethod
    def initialize_session_state() -> None:
        """Initialize all session state variables"""
        for key, value in AppConfig.DEFAULT_SESSION_STATE.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @staticmethod
    def get_state(key: str, default: Any = None) -> Any:
        """Get a value from session state with default"""
        return st.session_state.get(key, default)

    @staticmethod
    def set_state(key: str, value: Any) -> None:
        """Safely set a session state value"""
        st.session_state[key] = value

    @staticmethod
    def update_article_state(article_id: int, content: str) -> None:
        """Update article-related session state"""
        if "drafts_by_article" not in st.session_state:
            st.session_state["drafts_by_article"] = {}
        st.session_state["drafts_by_article"][article_id] = content 