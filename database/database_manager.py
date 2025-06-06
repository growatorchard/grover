import sqlite3
import json
from datetime import datetime


class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect("/data/grover.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        # self.create_tables()

    def get_connection(self):
        return self.conn

    # Projects
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
                consumer_need,
                tone_of_voice,
                target_audiences,
                topic,
                is_base_project,
                is_duplicate,
                original_project_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_data["name"],
                json.dumps(project_data["care_areas"]),
                project_data["journey_stage"],
                project_data["category"],
                project_data["format_type"],
                project_data["business_category"],
                project_data["consumer_need"],
                project_data["tone_of_voice"],
                json.dumps(project_data["target_audiences"]),
                project_data["topic"],
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
                    consumer_need = ?,
                    tone_of_voice = ?,
                    target_audiences = ?,
                    topic = ?,
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
                    state_data.get("consumer_need"),
                    state_data.get("tone_of_voice"),
                    json.dumps(state_data.get("target_audiences", [])),
                    state_data.get("topic"),
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

    # Keywords
    def add_keyword(
        self, project_id, keyword, search_volume, search_intent, keyword_difficulty
    ):
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

    # Articles
    def create_article_content(
        self,
        project_id,
        article_outline='',
        article_length=None,
        article_sections=None,
        article_title='',
        article_content='',
    ):
        """Create base article content with improved error handling."""
        print("Creating article content...")
        print(f"DBBBProject ID: {project_id}")
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO base_articles (
                        project_id, article_outline, article_length, article_sections, article_title, article_content,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        project_id,
                        article_outline,
                        article_length,
                        article_sections,
                        article_title,
                        article_content
                    ),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                raise e

    def save_article_content(
        self,
        project_id,
        article_outline=None,
        article_length=None,
        article_sections=None,
        article_title=None,
        article_content=None,
        article_id=None,
    ):
        """Save or update article content with improved error handling and transaction management."""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN")
                cursor = conn.cursor()

                if article_id:
                    # First, get the current values to use as defaults for NULL values
                    cursor.execute(
                        "SELECT * FROM base_articles WHERE id = ?", 
                        (article_id,)
                    )
                    current = cursor.fetchone()
                    
                    if not current:
                        raise ValueError(
                            f"No article found with ID {article_id} for project {project_id}"
                        )
                    
                    # Use existing values for any NULL parameters
                    article_outline = article_outline if article_outline is not None else current['article_outline']
                    article_length = article_length if article_length is not None else current['article_length']
                    article_sections = article_sections if article_sections is not None else current['article_sections']
                    article_title = article_title if article_title is not None else current['article_title']
                    article_content = article_content if article_content is not None else current['article_content']
                    
                    # Now update with all fields populated
                    cursor.execute(
                        """
                        UPDATE base_articles
                        SET
                            article_outline = ?,
                            article_length = ?,
                            article_sections = ?,
                            article_title = ?,
                            article_content = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND project_id = ?
                        """,
                        (
                            article_outline,
                            article_length,
                            article_sections,
                            article_title,
                            article_content,
                            article_id,
                            project_id,
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise ValueError(
                            f"Update failed for article ID {article_id} for project {project_id}"
                        )
                    saved_id = article_id
                else:
                    # For new articles, insert with the values provided
                    cursor.execute(
                        """
                        INSERT INTO base_articles (
                            project_id, article_outline, article_length, article_sections, article_title, article_content,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (
                            project_id,
                            article_outline,
                            article_length,
                            article_sections,
                            article_title,
                            article_content,
                        ),
                    )
                    saved_id = cursor.lastrowid

                conn.commit()
                return saved_id

            except Exception as e:
                conn.rollback()
                print(f"Database error in save_article_content: {str(e)}")
                raise e

    def save_article_post_content(self, article_id, article_content):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE base_articles
                SET article_content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (article_content, article_id),
            )
            conn.commit()

    def save_article_title_outline(self, article_id, article_title, article_outline):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE base_articles
                SET article_title = ?, article_outline = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (article_title, article_outline, article_id),
            )
            conn.commit()

    def get_all_articles_for_project(self, project_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, article_title, article_content, article_outline, article_length, article_sections
                FROM base_articles
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (project_id,),
            )
            return cursor.fetchall()

    def get_article_content(self, article_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM base_articles WHERE id = ?", (article_id,)
            )
            return cursor.fetchone()

    def delete_article_content(self, article_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM base_articles WHERE id = ?", (article_id,)
            )
            conn.commit()

    # Community Articles

    def create_community_article(
        self,
        project_id,
        base_article_id,
        community_id,
        article_title='',
        article_content='',
        article_schema=None,
        meta_title='',
        meta_description='',
    ):
        """Create a new community article that's a copy of a base article."""
        with self.get_connection() as conn:
            try:
                # Begin transaction
                conn.execute("BEGIN")
                cursor = conn.cursor()
                
                # Get base article content if needed
                if not article_title:
                    base_article = self.get_article_content(base_article_id)
                    if base_article:
                        article_title = base_article.get('article_title', '')
                        article_content = base_article.get('article_content', '')
                        article_schema = base_article.get('article_schema')
                        meta_title = base_article.get('meta_title', '')
                        meta_description = base_article.get('meta_description', '')
                
                # Insert new community article
                cursor.execute(
                    """
                    INSERT INTO community_articles (
                        project_id, base_article_id, community_id, article_title, article_content, article_schema,
                        meta_title, meta_description,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        project_id,
                        base_article_id,
                        community_id,
                        article_title,
                        article_content,
                        (
                            json.dumps(article_schema)
                            if isinstance(article_schema, dict)
                            else article_schema
                        ),
                        meta_title,
                        meta_description,
                    ),
                )
                
                # Get the ID of the newly created article
                new_article_id = cursor.lastrowid
                
                # Commit transaction
                conn.commit()
                return new_article_id
                
            except Exception as e:
                # Rollback on error
                conn.rollback()
                print(f"Database error in create_community_article: {str(e)}")
                raise e

    def save_community_post_content(self, community_article_id, article_content):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE community_articles
                SET article_content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (article_content, community_article_id),
            )
            conn.commit()

    def get_community_articles_for_base_article(self, base_article_id):
        """Get all community articles for a base article."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Query without joining with communities table
            cursor.execute(
                """
                SELECT * FROM community_articles
                WHERE base_article_id = ?
                ORDER BY created_at DESC
                """,
                (base_article_id,)
            )
            articles = cursor.fetchall()
            
            # If we have articles, enrich them with community data
            if articles:
                # Convert to list of dicts for easier manipulation
                article_list = [dict(article) for article in articles]
                
                # Fetch community details from comm_manager
                from app import comm_manager  # Import here to avoid circular imports
                for article in article_list:
                    try:
                        community = comm_manager.get_community(article['community_id'])
                        if community:
                            article['community_name'] = community['community_name']
                        else:
                            article['community_name'] = f"Community {article['community_id']}"
                    except Exception as e:
                        print(f"Error getting community name: {str(e)}")
                        article['community_name'] = f"Community {article['community_id']}"
                
                return article_list
            
            return []

    def get_community_article(self, community_article_id):
        """Get a specific community article by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM community_articles
                WHERE id = ?
                """,
                (community_article_id,)
            )
            article = cursor.fetchone()
            
            if article:
                # Convert to dict for easier manipulation
                article_dict = dict(article)
                
                # Fetch community details from comm_manager
                from app import comm_manager  # Import here to avoid circular imports
                try:
                    community = comm_manager.get_community(article_dict['community_id'])
                    if community:
                        article_dict['community_name'] = community['community_name']
                    else:
                        article_dict['community_name'] = f"Community {article_dict['community_id']}"
                except Exception as e:
                    print(f"Error getting community name: {str(e)}")
                    article_dict['community_name'] = f"Community {article_dict['community_id']}"
                
                return article_dict
            
            return None

    def get_community_article_by_community(self, base_article_id, community_id):
        """Check if a community article exists for a specific base article and community."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM community_articles
                WHERE base_article_id = ? AND community_id = ?
                """,
                (base_article_id, community_id)
            )
            return cursor.fetchone()

    def save_community_article_content(self, community_article_id, article_title=None, article_content=None):
        """Save or update a community article's content."""
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # Get current values to use as defaults for NULL values
                cursor.execute(
                    "SELECT * FROM community_articles WHERE id = ?", 
                    (community_article_id,)
                )
                current = cursor.fetchone()
                
                if not current:
                    raise ValueError(f"No community article found with ID {community_article_id}")
                
                # Use existing values for any NULL parameters
                article_title = article_title if article_title is not None else current['article_title']
                article_content = article_content if article_content is not None else current['article_content']
                
                cursor.execute(
                    """
                    UPDATE community_articles
                    SET article_title = ?, article_content = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (article_title, article_content, community_article_id)
                )
                conn.commit()
                return True
                
            except Exception as e:
                conn.rollback()
                print(f"Database error in save_community_article_content: {str(e)}")
                raise e

    def delete_community_article(self, community_article_id):
        """Delete a community article."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM community_articles WHERE id = ?",
                (community_article_id,)
            )
            conn.commit()
            return cursor.rowcount > 0