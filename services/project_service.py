from typing import Tuple, Optional
import streamlit as st
from database.database_manager import DatabaseManager
from services.state_service import StateService
from config.app_config import AppConfig

class ProjectService:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.state = StateService()

    def handle_project_selection(self, selected_project_str: str) -> None:
        """Handle project selection logic"""
        if selected_project_str == "Create New Project":
            self.state.set_state("project_id", None)
        else:
            proj_id = int(selected_project_str.split("ID:")[-1].replace(")", "").strip())
            if self.state.get_state("project_id") != proj_id:
                self.state.set_state("project_id", proj_id)

    def get_project_display_list(self) -> Tuple[list, list]:
        """Get projects for display in dropdown"""
        projects = self.db.get_all_projects()
        project_names = ["Create New Project"] + [
            f"{p['name']} (ID: {p['id']})" for p in projects
        ]
        return projects, project_names 