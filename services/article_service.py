from typing import Tuple
from database.database_manager import DatabaseManager
from services.state_service import StateService
from services.llm_service import generate_meta_content

class ArticleService:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.state = StateService()

    def handle_article_selection(self, selected_article_str: str) -> None:
        """Handle article selection logic"""
        if selected_article_str == "Create New Article":
            self.state.set_state("article_id", None)
        else:
            article_id = int(selected_article_str.split("ID:")[-1].replace(")", "").strip())
            self.state.set_state("article_id", article_id)
    
    def get_article_display_list(self, project_id: int) -> Tuple[list, list]:
        """Get articles for display in dropdown"""
        articles = self.db.get_all_articles_for_project(project_id)
        article_names = ["Create New Article"] + [
            f"{a['article_title']} (ID: {a['id']})" for a in articles
        ]
        return articles, article_names
    
    def generate_article_meta_content(self, project_id: int, article_id: int, article_content: str, article_title: str) -> bool:
        """Generate and save meta content for an article"""
        try:
            # Generate meta content
            generated_title, generated_desc = generate_meta_content(article_content)
            
            if not generated_title or not generated_desc:
                return False
                
            # Save to database
            saved_id = self.db.save_article_content(
                project_id=project_id,
                article_title=article_title,
                article_content=article_content,
                article_schema=None,
                meta_title=generated_title,
                meta_description=generated_desc,
                article_id=article_id
            )
            
            # Update session state
            if "meta_title_by_article" not in st.session_state:
                st.session_state["meta_title_by_article"] = {}
            if "meta_desc_by_article" not in st.session_state:
                st.session_state["meta_desc_by_article"] = {}
            
            # Ensure article remains selected after rerun
            st.session_state["article_id"] = saved_id
            st.session_state["meta_title_by_article"][saved_id] = generated_title
            st.session_state["meta_desc_by_article"][saved_id] = generated_desc
            
            return True
        except Exception as e:
            st.error(f"Error generating meta content: {str(e)}")
            return False 
        

    def autosave_final_article():
        """Automatically save article content to database when changes are made."""
        article_id = st.session_state.get("article_id")
        project_id = st.session_state.get("project_id")
        
        if article_id and project_id:
            updated_title = st.session_state.get("final_title", "")
            updated_text = st.session_state.get("final_article", "")
            updated_meta_title = st.session_state.get("final_meta_title", "")
            updated_meta_desc = st.session_state.get("final_meta_desc", "")
            
            try:
                saved_id = db.save_article_content(
                    project_id=project_id,
                    article_title=updated_title or "Auto-Generated Title",
                    article_content=updated_text,
                    article_schema=None,
                    meta_title=updated_meta_title,
                    meta_description=updated_meta_desc,
                    article_id=article_id,
                )
                st.session_state["article_id"] = saved_id
                
                # Update the drafts in session state
                if "drafts_by_article" not in st.session_state:
                    st.session_state["drafts_by_article"] = {}
                st.session_state["drafts_by_article"][article_id] = updated_text
                
            except Exception as e:
                st.error(f"Error saving article: {str(e)}")