import os
import sqlite3
import json
import requests
import streamlit as st
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv

load_dotenv()  # This loads environment variables from .env

# --------------------------------------------------------------------
# 1) Database Manager (SQLite)
# --------------------------------------------------------------------
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

            /* Removed UNIQUE from project_id here to allow multiple articles per project */
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

    # ------------- Projects -------------
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
        """Update basic fields in 'projects' table."""
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
        """Delete the project, which cascades to keywords and base_article_content."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    # ------------- Keywords -------------
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
            return cursor.lastrowid

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

    # ------------- Articles -------------
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
        """
        Insert or update an article. If article_id is given, update that record.
        Otherwise, insert a new row.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if article_id:
                # Update existing article
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
                    WHERE id = ?
                    """,
                    (
                        article_title,
                        article_content,
                        json.dumps(article_schema) if isinstance(article_schema, dict) else article_schema,
                        meta_title,
                        meta_description,
                        article_id,
                    ),
                )
                return article_id
            else:
                # Create new article
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
                return cursor.lastrowid

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
            return cursor.rowcount > 0


# --------------------------------------------------------------------
# 2) SEMrush Query Code
# --------------------------------------------------------------------
def build_semrush_url(api_type, phrase, api_key, database='us',
                      export_columns='', display_limit=None, debug_mode=False):
    """Build the Semrush API URL with the required parameters."""
    base_url = 'https://api.semrush.com'
    params = {
        'type': api_type,
        'key': api_key,
        'phrase': phrase,
        'database': database
    }
    if export_columns:
        params['export_columns'] = export_columns
    if display_limit is not None:
        params['display_limit'] = display_limit

    query_str = '&'.join([f"{k}={requests.utils.quote(str(v))}" for k,v in params.items()])
    full_url = f"{base_url}/?{query_str}"

    return full_url

def parse_semrush_response(response_text, debug_mode=False):
    """Utility to parse SEMrush CSV-like response text."""
    if "ERROR" in response_text:
        return []

    lines = response_text.strip().split('\n')
    if len(lines) < 2:
        return []

    headers = lines[0].split(';')
    raw_rows = [line.split(';') for line in lines[1:]]

    data = []
    for row_values in raw_rows:
        if len(row_values) != len(headers):
            continue
        row_dict = {}
        for h, val in zip(headers, row_values):
            row_dict[h] = val
        data.append(row_dict)

    return data

def query_semrush_api(keyword, database='us', debug_mode=False):
    """Query Semrush API for keyword data (overview + related)."""
    api_key = os.getenv("SEMRUSH_API_KEY", "")
    if not api_key:
        return {'error': "No SEMRUSH_API_KEY found in .env"}

    try:
        # 1) Overview
        overview_url = build_semrush_url(
            api_type='phrase_these',
            phrase=keyword,
            api_key=api_key,
            database=database,
            export_columns='Ph,Vo,Kd,CpC,Co,Nr,Td',
            debug_mode=debug_mode
        )
        overview_resp = requests.get(overview_url)
        if overview_resp.status_code != 200:
            raise ValueError(
                f"Overview request error (HTTP {overview_resp.status_code}): {overview_resp.text}"
            )

        overview_data = parse_semrush_response(overview_resp.text, debug_mode=debug_mode)
        if not overview_data:
            return {
                'overview': None,
                'related_keywords': [],
                'error': "No overview data"
            }

        main_raw = overview_data[0]
        overview_obj = {
            'Ph':  main_raw.get('Keyword', keyword),
            'Vo':  "0",
            'Kd':  main_raw.get('Keyword Difficulty Index', "0"),
            'CpC': "0",
            'Co':  main_raw.get('Competition', "0"),
            'Nr':  main_raw.get('Number of Results', "0"),
            'Td':  main_raw.get('Trends', "0"),
        }

        # 2) Related
        related_url = build_semrush_url(
            api_type='phrase_related',
            phrase=keyword,
            api_key=api_key,
            database=database,
            export_columns='Ph,Vo,Kd,CpC,Co,Nr,Td',
            display_limit=10,
            debug_mode=debug_mode
        )
        related_resp = requests.get(related_url)
        if related_resp.status_code != 200:
            raise ValueError(
                f"Related request error (HTTP {related_resp.status_code}): {related_resp.text}"
            )

        related_data = parse_semrush_response(related_resp.text, debug_mode=debug_mode)
        related_list = []
        for rd in related_data:
            related_list.append({
                'Ph':  rd.get('Keyword', ""),
                'Vo':  "0",
                'Kd':  rd.get('Keyword Difficulty Index', "0"),
                'CpC': "0",
                'Co':  rd.get('Competition', "0"),
                'Nr':  rd.get('Number of Results', "0"),
                'Td':  rd.get('Trends', "0")
            })

        return {
            'overview': overview_obj,
            'related_keywords': related_list,
            'error': None
        }

    except Exception as e:
        return {
            'overview': None,
            'related_keywords': [],
            'error': f"Exception: {str(e)}"
        }

def get_keyword_suggestions(topic, debug_mode=False):
    """Returns a dict with main_keyword, related_keywords, error."""
    results = query_semrush_api(topic, debug_mode=debug_mode)
    if results.get('error'):
        return results

    return {
        'main_keyword': results['overview'],
        'related_keywords': results['related_keywords'],
        'error': None
    }

def format_keyword_report(keyword_data):
    """Format keyword data into a readable report."""
    if not keyword_data or keyword_data.get('error'):
        return "No keyword data available"

    lines = ["Keyword Research Report:\n"]
    main = keyword_data.get('main_keyword')
    if main:
        lines.append(f"**Main Keyword**: {main['Ph']}")
        lines.append(f"- Volume: {main['Vo']}")
        lines.append(f"- Difficulty: {main['Kd']}")
        lines.append(f"- CPC: {main['CpC']}")
        lines.append("")

    related = keyword_data.get('related_keywords', [])
    if related:
        lines.append("**Related Keywords**:")
        for kw in related:
            lines.append(f" - {kw['Ph']} (Vol={kw['Vo']}, Diff={kw['Kd']})")
    return "\n".join(lines)


# --------------------------------------------------------------------
# 3) Anthropic's Claude Query
# --------------------------------------------------------------------
def query_claude_api(message: str) -> str:
    """
    Calls Anthropic's /v1/messages endpoint with a user message.
    Requires st.secrets['ANTHROPIC_API_KEY'] to be set.
    """
    url = 'https://api.anthropic.com/v1/messages'
    try:
        api_key = st.secrets['ANTHROPIC_API_KEY']
    except:
        return "Error: No ANTHROPIC_API_KEY found in st.secrets."

    headers = {
        'anthropic-version': '2023-06-01',
        'x-api-key': api_key,
        'content-type': 'application/json',
    }

    payload = {
        'model': 'claude-3-5-sonnet-20241022',  # or whichever model version you have access to
        'max_tokens': 5000,
        'messages': [
            {
                'role': 'user',
                'content': message
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        response_data = response.json()

        if 'content' in response_data:
            # Some Anthropic responses might return 'content' as a single string
            # or as a list of segments. We handle both.
            if isinstance(response_data['content'], list):
                return ''.join(block.get('text', '') for block in response_data['content'])
            return response_data['content']

        if 'message' in response_data:
            content = response_data['message'].get('content', [])
            if isinstance(content, list):
                return ''.join(block.get('text', '') for block in content)
            return str(content)

        return "Could not extract content from Anthropic response."

    except requests.exceptions.RequestException as e:
        error_message = f"API request failed: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f"\nResponse: {e.response.text}"
        return error_message
    except (KeyError, ValueError) as e:
        return f"Error parsing response: {str(e)}"


# --------------------------------------------------------------------
# 4) Optional Website Scraping
# --------------------------------------------------------------------
def scrape_website(url):
    """Scrape textual content from a single webpage."""
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return "Invalid URL"
        # Quick check of robots.txt
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        r_robots = requests.get(robots_url, timeout=5)
        if r_robots.status_code == 200 and "Disallow: /" in r_robots.text:
            return "Website disallows scraping (robots.txt)."

        r_page = requests.get(url, timeout=10)
        if r_page.status_code != 200:
            return f"Failed to retrieve page (HTTP {r_page.status_code})."

        soup = BeautifulSoup(r_page.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = " ".join(soup.stripped_strings)
        return text
    except Exception as e:
        return f"Error scraping site: {e}"


# --------------------------------------------------------------------
# 5) Streamlit App
# --------------------------------------------------------------------

db = DatabaseManager()
st.set_page_config(page_title="Grover (Claude + SEMrush)", layout="wide")
st.title("Grover: Claude-based, with SEMrush Keyword Research")

debug_mode = st.sidebar.checkbox("Debug Mode", value=False)

# Predefined dropdown options
journey_stage_options = ["Awareness", "Consideration", "Decision", "Retention", "Advocacy", "Other"]
article_category_options = ["Senior Living", "Health/Wellness", "Lifestyle", "Financial", "Other"]
business_category_options = ["Healthcare", "Senior Living", "Housing", "Lifestyle", "Other"]
format_type_options = [
    "Blog", "Case Study", "White Paper", "Guide", "Downloadable Guide", "Review",
    "Interactives", "Brand Content", "Infographic", "E-Book", "Email", "Social Media Posts",
    "User Generated Content", "Meme", "Checklist", "Video", "Podcast", "Other"
]
care_area_options = ["Independent Living", "Assisted Living", "Memory Care", "Skilled Nursing"]
tone_of_voice_options = ["Professional", "Friendly", "Conversational", "Empathetic", "Other"]
target_audience_options = ["Seniors", "Adult Children", "Caregivers", "Health Professionals", "Other"]
consumer_need_options = ["Educational", "Financial Guidance", "Medical Info", "Lifestyle/Wellness", "Other"]


def dynamic_selectbox(label, options, default_val):
    """
    Show a selectbox with an "Other" option.
    If the user picks "Other", show a text input to override.
    Returns final chosen string.
    """
    if default_val and default_val not in options and default_val.strip():
        options = options + [default_val]

    choice = st.selectbox(label, options, index=options.index(default_val) if default_val in options else 0)
    if choice == "Other":
        choice = st.text_input(f"{label} - custom value", value="" if default_val in options else default_val)
    return choice or ""

def dynamic_multiselect(label, options, default_vals):
    """
    For care_areas.
    If user has any values not in options, add them.
    """
    extra_vals = [v for v in default_vals if v not in options]
    final_options = options + extra_vals if extra_vals else options
    selection = st.multiselect(label, final_options, default=default_vals)
    return selection

# --------------------------------------------------------------------
# Store article data in session by article_id
# --------------------------------------------------------------------
if "drafts_by_article" not in st.session_state:
    st.session_state["drafts_by_article"] = {}

if "refine_instructions_by_article" not in st.session_state:
    st.session_state["refine_instructions_by_article"] = {}

if "meta_title_by_article" not in st.session_state:
    st.session_state["meta_title_by_article"] = {}

if "meta_desc_by_article" not in st.session_state:
    st.session_state["meta_desc_by_article"] = {}

def get_current_draft(aid):
    return st.session_state["drafts_by_article"].get(aid, "")

def set_current_draft(aid, text):
    st.session_state["drafts_by_article"][aid] = text

def get_refine_instructions(aid):
    return st.session_state["refine_instructions_by_article"].get(aid, "")

def set_refine_instructions(aid, text):
    st.session_state["refine_instructions_by_article"][aid] = text

def get_meta_title(aid):
    return st.session_state["meta_title_by_article"].get(aid, "")

def set_meta_title(aid, text):
    st.session_state["meta_title_by_article"][aid] = text

def get_meta_desc(aid):
    return st.session_state["meta_desc_by_article"].get(aid, "")

def set_meta_desc(aid, text):
    st.session_state["meta_desc_by_article"][aid] = text


# -- Sidebar: Project Selection --
projects = db.get_all_projects()
project_names = ["Create New Project"] + [f"{p['name']} (ID: {p['id']})" for p in projects]
selected_project_str = st.sidebar.selectbox("Select Project", project_names)

if "project_id" not in st.session_state:
    st.session_state["project_id"] = None

if selected_project_str == "Create New Project":
    st.session_state["project_id"] = None
else:
    proj_id = int(selected_project_str.split("ID:")[-1].replace(")", "").strip())
    if st.session_state["project_id"] != proj_id:
        st.session_state["project_id"] = proj_id

# -- Delete project button --
if st.session_state["project_id"]:
    if st.sidebar.button("Delete Project"):
        db.delete_project(st.session_state["project_id"])
        st.session_state["project_id"] = None
        st.rerun()

# -- Sidebar: Article Selection (only if a project is chosen) --
if "article_id" not in st.session_state:
    st.session_state["article_id"] = None

if st.session_state["project_id"]:
    articles = db.get_all_articles_for_project(st.session_state["project_id"])
    article_names = ["Create New Article"] + [f"{a['article_title']} (ID: {a['id']})" for a in articles]
    selected_article_str = st.sidebar.selectbox("Select Article (within Project)", article_names)

    if selected_article_str == "Create New Article":
        st.session_state["article_id"] = None
    else:
        article_id = int(selected_article_str.split("ID:")[-1].replace(")", "").strip())
        st.session_state["article_id"] = article_id

    # Delete article button
    if st.session_state["article_id"]:
        if st.sidebar.button("Delete Article"):
            db.delete_article_content(st.session_state["article_id"])
            st.success("Article content deleted.")
            st.session_state["article_id"] = None
            st.rerun()


# 1) Create / Update Project
with st.expander("1) Create or Update Project", expanded=(st.session_state["project_id"] is None)):
    if "topic_suggestions" not in st.session_state:
        st.session_state["topic_suggestions"] = []
    if "selected_topic" not in st.session_state:
        st.session_state["selected_topic"] = ""

    if st.session_state["project_id"]:
        # Existing project
        proj_data = db.get_project(st.session_state["project_id"])
        if proj_data:
            proj_data = dict(proj_data)
            st.write(f"**Loaded Project**: {proj_data['name']} (ID: {proj_data['id']})")

            existing_care_areas = json.loads(proj_data.get("care_areas", "[]")) if proj_data.get("care_areas") else []
            existing_notes = {}
            try:
                existing_notes = json.loads(proj_data.get("notes") or "{}")
            except:
                existing_notes = {}

            def_need = existing_notes.get("consumer_need", "")
            def_tone = existing_notes.get("tone_of_voice", "")
            def_audience = existing_notes.get("target_audience", "")

            upd_name = st.text_input("Project Name", value=proj_data["name"])

            upd_journey = dynamic_selectbox("Consumer Journey Stage", journey_stage_options, proj_data.get("journey_stage", "Awareness"))
            upd_category = dynamic_selectbox("Article Category", article_category_options, proj_data.get("category", "Senior Living"))
            upd_care_areas = dynamic_multiselect("Care Area(s)", care_area_options, existing_care_areas)
            upd_format = dynamic_selectbox("Format Type", format_type_options, proj_data.get("format_type", "Blog"))
            upd_bizcat = dynamic_selectbox("Business Category", business_category_options, proj_data.get("business_category", "Senior Living"))

            upd_need = dynamic_selectbox("Consumer Need", consumer_need_options, def_need)
            upd_tone = dynamic_selectbox("Tone of Voice", tone_of_voice_options, def_tone)
            upd_audience = dynamic_selectbox("Target Audience", target_audience_options, def_audience)

            freeform_notes = existing_notes.get("freeform_notes", "")
            upd_notes_text = st.text_area("Additional Notes", value=freeform_notes)

            st.write("#### Project Topic")
            def_topic = existing_notes.get("topic", "")
            user_topic_input = st.text_input("Enter a Topic", value=def_topic)

            if st.button("Generate 5 Topics"):
                prompt_for_topics = f"""
Given the following details:
- Journey Stage: {upd_journey}
- Category: {upd_category}
- Care Areas: {', '.join(upd_care_areas)}
- Format: {upd_format}
- Business Category: {upd_bizcat}
- Consumer Need: {upd_need}
- Tone of Voice: {upd_tone}
- Target Audience: {upd_audience}

Suggest 5 potential article topics.
"""
                with st.spinner("Generating topic suggestions..."):
                    suggestions_raw = query_claude_api(prompt_for_topics)

                st.session_state["topic_suggestions"] = suggestions_raw.split("\n")
                st.success("See suggested topics below.")

            if st.session_state["topic_suggestions"]:
                chosen_suggestion = st.selectbox("Choose a generated topic:", st.session_state["topic_suggestions"])
                if st.button("Use Selected Topic"):
                    user_topic_input = chosen_suggestion
                    st.session_state["topic_suggestions"] = []
                    st.success(f"Topic set to: {chosen_suggestion}")

            if st.button("Update Project"):
                final_notes_json = {
                    "consumer_need": upd_need,
                    "tone_of_voice": upd_tone,
                    "target_audience": upd_audience,
                    "freeform_notes": upd_notes_text,
                    "topic": user_topic_input,
                }

                patch = {
                    "name": upd_name,
                    "care_areas": upd_care_areas,
                    "journey_stage": upd_journey,
                    "category": upd_category,
                    "format_type": upd_format,
                    "business_category": upd_bizcat,
                    "notes": json.dumps(final_notes_json),
                }

                db.update_project_state(proj_data["id"], patch)
                st.success("Project updated.")

    else:
        # Create a new project
        st.write("**Create a New Project**")

        new_name = st.text_input("Project Name")
        new_journey = dynamic_selectbox("Consumer Journey Stage", journey_stage_options, "Awareness")
        new_category = dynamic_selectbox("Article Category", article_category_options, "Senior Living")
        new_care_areas = dynamic_multiselect("Care Area(s)", care_area_options, [])
        new_format = dynamic_selectbox("Format Type", format_type_options, "Blog")
        new_bizcat = dynamic_selectbox("Business Category", business_category_options, "Senior Living")

        new_need = dynamic_selectbox("Consumer Need", consumer_need_options, "Educational")
        new_tone = dynamic_selectbox("Tone of Voice", tone_of_voice_options, "Professional")
        new_audience = dynamic_selectbox("Target Audience", target_audience_options, "Seniors")
        new_notes_text = st.text_area("Additional Notes (optional)")

        st.write("#### Project Topic")
        topic_input = st.text_input("Enter a Topic (optional)")

        if "topic_suggestions" not in st.session_state:
            st.session_state["topic_suggestions"] = []

        if st.button("Generate 5 Topics"):
            prompt_for_topics = f"""
We have these details for a new article:
- Journey Stage: {new_journey}
- Category: {new_category}
- Care Areas: {', '.join(new_care_areas)}
- Format: {new_format}
- Business Category: {new_bizcat}
- Consumer Need: {new_need}
- Tone of Voice: {new_tone}
- Target Audience: {new_audience}

Suggest 5 potential article topics.
"""
            with st.spinner("Generating topic suggestions..."):
                suggestions_raw = query_claude_api(prompt_for_topics)
            st.session_state["topic_suggestions"] = suggestions_raw.split("\n")
            st.success("See suggested topics below.")

        if st.session_state["topic_suggestions"]:
            chosen_suggestion = st.selectbox("Choose a generated topic:", st.session_state["topic_suggestions"])
            if st.button("Use Selected Topic"):
                topic_input = chosen_suggestion
                st.success(f"Topic set to: {chosen_suggestion}")
                st.session_state["topic_suggestions"] = []

        if st.button("Create Project"):
            if new_name.strip():
                final_notes_json = {
                    "consumer_need": new_need,
                    "tone_of_voice": new_tone,
                    "target_audience": new_audience,
                    "freeform_notes": new_notes_text,
                    "topic": topic_input.strip(),
                }
                p_data = {
                    "name": new_name.strip(),
                    "care_areas": new_care_areas,
                    "journey_stage": new_journey,
                    "category": new_category,
                    "format_type": new_format,
                    "business_category": new_bizcat,
                    "notes": json.dumps(final_notes_json),
                }
                new_id = db.create_project(p_data)
                st.session_state["project_id"] = new_id
                st.success(f"Created project '{new_name}' (ID={new_id}).")
                st.rerun()
            else:
                st.error("Please enter a project name.")


# 2) Manage Keywords (SEMrush)
if st.session_state["project_id"]:
    with st.expander("2) Manage Keywords (SEMrush)"):
        kws = db.get_project_keywords(st.session_state["project_id"])
        st.write("### Existing Keywords")
        if kws:
            for kw in kws:
                col1, col2 = st.columns([8,1])
                col1.write(
                    f"- **{kw['keyword']}**"
                    f" (Vol={kw['search_volume']}, Diff={kw['keyword_difficulty']})"
                )
                if col2.button("X", key=f"kwdel_{kw['id']}"):
                    db.delete_keyword(kw["id"])
                    st.rerun()
        else:
            st.info("No keywords yet.")

        st.write("---")
        st.write("### Add Keywords Manually")
        primary_kw = st.text_input("Primary Keyword")
        additional_kw = st.text_area("Additional Keywords (one per line)")
        if st.button("Save Keywords"):
            if primary_kw.strip():
                db.add_keyword(st.session_state["project_id"], primary_kw.strip(), None, None, None)
            if additional_kw.strip():
                for line in additional_kw.split("\n"):
                    line = line.strip()
                    if line:
                        db.add_keyword(st.session_state["project_id"], line, None, None, None)
            st.success("Keywords saved!")
            st.rerun()

        st.write("---")
        st.write("### Research with SEMrush")
        if "semrush_results" not in st.session_state:
            st.session_state["semrush_results"] = None

        sem_kw = st.text_input("Enter a keyword to research")

        if st.button("Research"):
            if not sem_kw.strip():
                st.warning("Please enter a keyword to research.")
            else:
                data = get_keyword_suggestions(sem_kw.strip(), debug_mode=debug_mode)
                st.session_state["semrush_results"] = data

        # Display SEMrush results if present in session state
        if st.session_state["semrush_results"]:
            data = st.session_state["semrush_results"]
            if data.get("error"):
                st.error(data["error"])
            else:
                st.write("#### SEMrush Results")
                main_kw = data["main_keyword"]
                related_kws = data["related_keywords"]
                if main_kw:
                    col1, col2 = st.columns([8,1])
                    col1.markdown(
                        f"**Main Keyword**: {main_kw['Ph']} "
                        f"(Volume={main_kw['Vo']}, Diff={main_kw['Kd']})"
                    )
                    if col2.button("➕", key=f"add_main_{main_kw['Ph']}"):
                        db.add_keyword(
                            st.session_state["project_id"],
                            main_kw['Ph'],
                            main_kw['Vo'],
                            None,  # search_intent
                            main_kw['Kd']
                        )
                        st.rerun()
                if related_kws:
                    st.write("**Related Keywords**:")
                    for rk in related_kws:
                        col1, col2 = st.columns([8,1])
                        col1.write(f"- {rk['Ph']} (Vol={rk['Vo']}, Diff={rk['Kd']})")
                        if col2.button("➕", key=f"add_rel_{rk['Ph']}"):
                            db.add_keyword(
                                st.session_state["project_id"],
                                rk['Ph'],
                                rk['Vo'],
                                None,  # search_intent
                                rk['Kd']
                            )
                            st.rerun()


# 3) Article Brief
if st.session_state["project_id"]:
    with st.expander("3) Article Brief"):
        if "article_brief" not in st.session_state:
            st.session_state["article_brief"] = ""
        st.session_state["article_brief"] = st.text_area(
            "Enter your article brief/outlines",
            value=st.session_state["article_brief"],
            height=150
        )
        if st.button("Save Brief"):
            st.success("Brief saved (in session).")


# 4) Generate & Refine (Claude)
if st.session_state["project_id"]:
    with st.expander("4) Generate & Refine Article (Claude)"):

        # If there's NO article selected, let user give a custom new article name
        new_article_name = ""
        if not st.session_state["article_id"]:
            new_article_name = st.text_input("New Article Name (optional)", value="")

        if st.button("Generate Article from Brief"):
            brief_text = st.session_state.get("article_brief", "")
            db_kws = db.get_project_keywords(st.session_state["project_id"])
            keywords = [k["keyword"] for k in db_kws] if db_kws else []
            kw_str = ", ".join(keywords)

            pinfo = db.get_project(st.session_state["project_id"])
            project_notes = {}
            if pinfo and pinfo["notes"]:
                try:
                    project_notes = json.loads(pinfo["notes"])
                except:
                    project_notes = {}
            topic_in_notes = project_notes.get("topic", "").strip()

            prompt_msg = f"""
IMPORTANT: You must return a valid JSON object with exactly this structure:
{{
  "article": "Your article text here",
  "meta_title": "Your SEO title here",
  "meta_description": "Your meta description here"
}}

The article MUST:
1. Be super super extremely long, many thousands of words
2. Include ALL of these keywords: {kw_str}

Write an article on:
Topic: {topic_in_notes}
Brief: {brief_text}

Format the article with:
1. Clear section headings
2. Double line breaks between paragraphs
3. Proper bullet points where appropriate
4. Well-structured sections
5. Clear introduction and conclusion

The meta title should be 50-60 characters.
The meta description should be 150-160 characters.

REMEMBER: Return ONLY the JSON object. No other text or explanations.
"""

            def generate_article_with_validation(prompt_msg, keywords, max_attempts=10, debug_mode=False):
                """Generate article content with validation and retry logic"""
                attempt = 1
                current_article = ""
                
                while attempt <= max_attempts:
                    with st.spinner(f"Generating article & meta from Claude (Attempt {attempt}/{max_attempts})..."):
                        # If we have a partial article, modify the prompt to continue it
                        if current_article:
                            continuation_prompt = f"""
IMPORTANT: You must return a valid JSON object with exactly this structure:
{{
  "article": "Your article text here",
  "meta_title": "Your SEO title here",
  "meta_description": "Your meta description here"
}}

The previous generated article was too short ({len(current_article.split())} words).
Please continue and expand this article to reach at least 1000 words.

Current article content:
{current_article}

Requirements:
1. Keep the existing content
2. Add more detailed sections
3. Maintain consistent style and formatting
4. Include all keywords: {keywords}
5. Return ONLY the JSON object with the complete expanded article

The meta title should be 50-60 characters.
The meta description should be 150-160 characters.

REMEMBER: Return ONLY the JSON object. No other text or explanations.
"""
                            output = query_claude_api(continuation_prompt)
                        else:
                            output = query_claude_api(prompt_msg)
                        
                        try:
                            # Find JSON content between first { and last }
                            start_idx = output.find('{')
                            end_idx = output.rfind('}')
                            if start_idx != -1 and end_idx != -1:
                                json_str = output[start_idx:end_idx + 1]
                                parsed = json.loads(json_str)
                            
                            # Extract and clean the components
                            generated_article = parsed.get("article", "").strip()
                            generated_title = parsed.get("meta_title", "").strip()
                            generated_desc = parsed.get("meta_description", "").strip()
                            
                            # Update current article if we're continuing
                            if current_article:
                                generated_article = current_article + "\n\n" + generated_article
                            
                            # Basic validation
                            if not generated_article or not generated_title or not generated_desc:
                                if debug_mode:
                                    st.write(f"Attempt {attempt}: Missing required fields")
                                attempt += 1
                                continue
                            
                            # Word count check
                            word_count = len(generated_article.split())
                            if word_count < 1000:
                                if debug_mode:
                                    st.write(f"Attempt {attempt}: Word count too low ({word_count})")
                                current_article = generated_article  # Save the current content
                                attempt += 1
                                continue
                            
                            # Case-insensitive keyword check
                            article_lower = generated_article.lower()
                            missing_keywords = [
                                kw for kw in keywords 
                                if kw.lower().strip() not in article_lower
                            ]
                            
                            if missing_keywords:
                                if debug_mode:
                                    st.write(f"Attempt {attempt}: Missing keywords: {', '.join(missing_keywords)}")
                                attempt += 1
                                continue
                            
                            return generated_article, generated_title, generated_desc
                            
                        except json.JSONDecodeError as e:
                            if debug_mode:
                                st.write(f"Attempt {attempt}: JSON parsing error: {str(e)}")
                            attempt += 1
                            continue
                    
                    if attempt > max_attempts:
                        st.error(f"Failed to generate valid content after {max_attempts} attempts")
                        return None, None, None
                
                return None, None, None

            result = generate_article_with_validation(prompt_msg, keywords, max_attempts=10, debug_mode=debug_mode)
            if result != (None, None, None):
                generated_article, generated_title, generated_desc = result
                # Create new article if needed
                if not st.session_state["article_id"]:
                    final_title = new_article_name.strip() if new_article_name.strip() else "(Generated Draft)"
                    new_art_id = db.save_article_content(
                        project_id=st.session_state["project_id"],
                        article_title=final_title,
                        article_content=""
                    )
                    st.session_state["article_id"] = new_art_id

                # Store in session state
                current_aid = st.session_state["article_id"]
                set_current_draft(current_aid, generated_article)
                set_meta_title(current_aid, generated_title)
                set_meta_desc(current_aid, generated_desc)

                st.success("Article, meta title, and meta description generated successfully!")

        # Now show refine UI only if we have an article_id
        article_id = st.session_state["article_id"]
        if not article_id:
            st.info("No article selected/created yet. Generate an article first or create one above.")
        else:
            # Display the current article draft
            current_draft_text = get_current_draft(article_id)
            st.write("### Current Article Draft")
            new_draft = st.text_area(
                "Current Article Draft",
                value=current_draft_text,
                height=300
            )
            if new_draft != current_draft_text:
                set_current_draft(article_id, new_draft)

            # Article-specific refine instructions
            current_refine_instructions = get_refine_instructions(article_id)
            st.write("---")
            st.write("**Optionally** refine the article with additional instructions below.")
            refine_instructions_text = st.text_area("Refine Instructions", value=current_refine_instructions)

            if refine_instructions_text != current_refine_instructions:
                set_refine_instructions(article_id, refine_instructions_text)

            if st.button("Refine Article"):
                if refine_instructions_text.strip():
                    refine_prompt = f"""
Current article:

{get_current_draft(article_id)}

IMPORTANT: Return only the final text (article).
Do not include disclaimers or commentary.
Please refine the article according to these instructions:
{refine_instructions_text}
"""
                    with st.spinner("Refining..."):
                        refined = query_claude_api(refine_prompt)
                    set_current_draft(article_id, refined)
                    st.success("Refined successfully!")
                else:
                    st.warning("Please enter some instructions to refine the article.")


# 5) Save/Update Final Article
if st.session_state["project_id"]:
    with st.expander("5) Save/Update Final Article"):
        article_id = st.session_state["article_id"]
        if not article_id:
            st.info("No article selected. Generate or select one first.")
        else:
            draft_text = get_current_draft(article_id)

            article_db_row = db.get_article_content(article_id)
            existing_title = ""
            existing_meta_title = ""
            existing_meta_desc = ""
            if article_db_row:
                existing_title = article_db_row["article_title"] or ""
                existing_meta_title = article_db_row["meta_title"] or ""
                existing_meta_desc = article_db_row["meta_description"] or ""

            st.write("### Article Title")
            # This is the 'visible' title (not the meta_title)
            updated_article_title = st.text_input("Give your article a clear title", value=existing_title)

            # default meta from the session
            default_meta_title = get_meta_title(article_id) or existing_meta_title
            default_meta_desc = get_meta_desc(article_id) or existing_meta_desc

            final_text = st.text_area("Final Article", draft_text, height=300)
            meta_title = st.text_input("Meta Title", value=default_meta_title)
            meta_desc = st.text_area("Meta Description", value=default_meta_desc, height=68)

            if st.button("Save Article to DB"):
                saved_id = db.save_article_content(
                    project_id=st.session_state["project_id"],
                    article_title=updated_article_title or "Auto-Generated Title",
                    article_content=final_text,
                    article_schema=None,
                    meta_title=meta_title,
                    meta_description=meta_desc,
                    article_id=article_id  # if updating existing
                )

                # Update session data
                set_current_draft(saved_id, final_text)
                set_meta_title(saved_id, meta_title)
                set_meta_desc(saved_id, meta_desc)

                st.success("Article saved to DB!")
                st.session_state["article_id"] = saved_id


# 6) View Saved Article
if st.session_state.get("project_id") and st.session_state.get("article_id"):
    with st.expander("6) View Saved Article"):
        article_row = db.get_article_content(st.session_state["article_id"])
        if not article_row:
            st.info("No article has been saved yet for this selection.")
        else:
            st.write("### Article Title")
            st.write(article_row["article_title"])

            st.write("### Article Content")
            st.write(article_row["article_content"])

            if article_row["meta_title"] or article_row["meta_description"]:
                st.write("---")
                st.write("**Meta Title**:", article_row["meta_title"])
                st.write("**Meta Description**:", article_row["meta_description"])

            if st.button("Delete Saved Article", key="delete_saved_article"):
                db.delete_article_content(article_row["id"])
                st.success("Article content deleted.")
                st.session_state["article_id"] = None
                st.rerun()

# Debug info
if debug_mode:
    st.write("## Debug Info")
    st.json({"project_id": st.session_state.get("project_id")})
    st.json({"article_id": st.session_state.get("article_id")})
    st.json({"article_brief": st.session_state.get("article_brief", "")})
    st.json({"drafts_by_article": st.session_state["drafts_by_article"]})
    st.json({"refine_instructions_by_article": st.session_state["refine_instructions_by_article"]})
    st.json({"meta_title_by_article": st.session_state["meta_title_by_article"]})
    st.json({"meta_desc_by_article": st.session_state["meta_desc_by_article"]})
    st.write("All Projects:", [dict(p) for p in projects])


# --------------------------------------------------------------------
# 7) Community Feature (NEW)
# --------------------------------------------------------------------

# In a real scenario, you'd create/structure your Community DB similarly to 'grover.db'.
# For now, we just try to connect to 'community_details.db' and handle the failure gracefully.

def connect_to_community_db(db_path="community_details.db"):
    """
    Attempt to connect to the community_details.db database.
    If connection fails, show an error message.
    """
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        return conn
    except Exception as e:
        st.error(f"Cannot connect to community database: {e}")
        return None

def get_communities(conn):
    """
    Retrieve a list of (id, name) from the 'communities' table.
    This table and DB won't exist yet, so it will fail initially.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM communities")
        return cur.fetchall()
    except Exception as e:
        st.warning(f"Could not fetch community list: {e}")
        return []

def get_community_details(conn, community_id):
    """
    Retrieve 'details' for the selected community from the 'communities' table.
    Assumes a column named 'details' in that table.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT details FROM communities WHERE id = ?", (community_id,))
        row = cur.fetchone()
        return row[0] if row else "No details available."
    except Exception as e:
        return f"Error retrieving details: {e}"

with st.expander("7) Select a Community to Feature"):
    community_conn = connect_to_community_db()
    if community_conn:
        communities_data = get_communities(community_conn)
        if communities_data:
            # Create a selectbox for all community names
            community_dict = {name: cid for cid, name in communities_data}
            selected_comm_name = st.selectbox("Available Communities", list(community_dict.keys()))

            if selected_comm_name:
                selected_comm_id = community_dict[selected_comm_name]
                details = get_community_details(community_conn, selected_comm_id)
                st.write(f"**Details for '{selected_comm_name}':**")
                st.write(details)
        else:
            st.info("No communities found (or the table doesn't exist yet).")

        community_conn.close()
    else:
        st.warning("Community DB connection failed (this is expected until 'community_details.db' is created).")

def validate_article_requirements(text: str, required_keywords: list, min_words: int = 1000) -> tuple[bool, str]:
    """
    Validates if the article meets all requirements.
    Returns (is_valid, failure_reason)
    """
    # Check word count
    word_count = len(text.split())
    if word_count < min_words:
        return False, f"Word count too low: {word_count}/{min_words}"
    
    # Check keywords
    text_lower = text.lower()
    missing_keywords = []
    for kw in required_keywords:
        if kw.lower().strip() not in text_lower:
            missing_keywords.append(kw)
    
    if missing_keywords:
        return False, f"Missing keywords: {', '.join(missing_keywords)}"
        
    return True, "All requirements met"
