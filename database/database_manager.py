import sqlite3
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect("grover.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()

    def get_connection(self):
        return self.conn

    def create_tables(self):
        """Create all required tables if they don't exist."""
        self.cursor.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                care_areas JSON NOT NULL,
                journey_stage TEXT,
                category TEXT,
                format_type TEXT,
                business_category TEXT,
                notes TEXT,
                is_base_project BOOLEAN DEFAULT TRUE,
                is_duplicate BOOLEAN DEFAULT FALSE,
                original_project_id INTEGER,
                changes_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (original_project_id) 
                    REFERENCES projects(id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                search_volume INTEGER,
                search_intent TEXT,
                keyword_difficulty INTEGER,
                is_primary BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) 
                    REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS base_article_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                article_title TEXT NOT NULL,
                article_content TEXT NOT NULL,
                article_schema TEXT,
                meta_title TEXT,
                meta_description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()

    def create_project(self, project_data):
        current_time = datetime.now().isoformat()
        self.cursor.execute(
            """
            INSERT INTO projects (
                name,
                care_areas,
                journey_stage,
                category,
                format_type,
                business_category,
                notes,
                is_base_project,
                is_duplicate,
                original_project_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_data["name"],
                json.dumps(project_data["care_areas"]),
                project_data["journey_stage"],
                project_data["category"],
                project_data["format_type"],
                project_data["business_category"],
                project_data.get("notes", ""),
                project_data.get("is_base_project", True),
                project_data.get("is_duplicate", False),
                project_data.get("original_project_id", None),
                current_time,
                current_time,
            ),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_projects(self):
        self.cursor.execute(
            """
            SELECT id, name, created_at
            FROM projects
            ORDER BY created_at DESC
            """
        )
        return self.cursor.fetchall()

    def get_project(self, project_id):
        self.cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return self.cursor.fetchone()

    def update_project_state(self, project_id, state_data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE projects SET
                    name = ?,
                    care_areas = ?,
                    journey_stage = ?,
                    category = ?,
                    format_type = ?,
                    business_category = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    state_data.get("name"),
                    json.dumps(state_data.get("care_areas", [])),
                    state_data.get("journey_stage"),
                    state_data.get("category"),
                    state_data.get("format_type"),
                    state_data.get("business_category"),
                    state_data.get("notes"),
                    project_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_project(self, project_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    def add_keyword(self, project_id, keyword, search_volume, search_intent, keyword_difficulty):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO keywords
                (project_id, keyword, search_volume, search_intent, keyword_difficulty)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, keyword, search_volume, search_intent, keyword_difficulty),
            )
            conn.commit()

    def get_project_keywords(self, project_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM keywords WHERE project_id = ?", (project_id,))
            return cursor.fetchall()

    def delete_keyword(self, keyword_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
            return cursor.rowcount > 0

    def save_article_content(
        self,
        project_id,
        article_title,
        article_content,
        article_schema=None,
        meta_title=None,
        meta_description=None,
        article_id=None,
    ):
        """Save or update article content with improved error handling and transaction management."""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN")
                cursor = conn.cursor()
                
                if article_id:
                    cursor.execute(
                        """
                        UPDATE base_article_content
                        SET
                            article_title = ?,
                            article_content = ?,
                            article_schema = ?,
                            meta_title = ?,
                            meta_description = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND project_id = ?
                        """,
                        (
                            article_title,
                            article_content,
                            json.dumps(article_schema) if isinstance(article_schema, dict) else article_schema,
                            meta_title,
                            meta_description,
                            article_id,
                            project_id
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError(f"No article found with ID {article_id} for project {project_id}")
                    saved_id = article_id
                else:
                    cursor.execute(
                        """
                        INSERT INTO base_article_content (
                            project_id, article_title, article_content, article_schema,
                            meta_title, meta_description,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (
                            project_id,
                            article_title,
                            article_content,
                            json.dumps(article_schema) if isinstance(article_schema, dict) else article_schema,
                            meta_title,
                            meta_description,
                        ),
                    )
                    saved_id = cursor.lastrowid
                
                conn.commit()
                return saved_id
                
            except Exception as e:
                conn.rollback()
                raise e

    def get_all_articles_for_project(self, project_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, article_title, meta_title, meta_description, article_content 
                FROM base_article_content
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (project_id,),
            )
            return cursor.fetchall()

    def get_article_content(self, article_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM base_article_content WHERE id = ?", (article_id,))
            return cursor.fetchone()

    def delete_article_content(self, article_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM base_article_content WHERE id = ?", (article_id,))
            conn.commit() 