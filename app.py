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
def query_claude_api(message: str, conversation_history: list = None) -> str:
    """
    Calls Anthropic's /v1/messages endpoint with conversation history support.
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

    # Build messages array from conversation history
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({
        'role': 'user',
        'content': message
    })

    payload = {
        'model': 'claude-3-5-sonnet-20241022',
        'max_tokens': 5000,
        'messages': messages
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        
        if 'content' in response_data:
            content = response_data['content']
            if isinstance(content, list):
                text = ''.join(block.get('text', '') for block in content)
            else:
                text = str(content)
            
            # Add the response to conversation history if provided
            if conversation_history is not None:
                conversation_history.append({
                    'role': 'assistant',
                    'content': text
                })
            return text

        return "Could not extract content from Anthropic response."

    except requests.exceptions.RequestException as e:
        error_message = f"API request failed: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f"\nResponse: {e.response.text}"
        return error_message

def query_groq_api(message: str, conversation_history: list = None) -> str:
    """
    Calls Groq's API endpoint with conversation history support.
    Requires st.secrets['GROQ_API_KEY'] to be set.
    """
    url = 'https://api.groq.com/openai/v1/chat/completions'
    try:
        api_key = st.secrets['GROQ_API_KEY']
    except:
        return "Error: No GROQ_API_KEY found in st.secrets."

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    # Build messages array from conversation history
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({
        'role': 'user',
        'content': message
    })

    payload = {
        'model': 'llama-70b-v2',
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': 4096
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        
        if 'choices' in response_data and len(response_data['choices']) > 0:
            content = response_data['choices'][0]['message']['content']
            
            # Add the response to conversation history if provided
            if conversation_history is not None:
                conversation_history.append({
                    'role': 'assistant',
                    'content': content
                })
            return content

        return "Could not extract content from Groq response."

    except requests.exceptions.RequestException as e:
        error_message = f"API request failed: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f"\nResponse: {e.response.text}"
        return error_message


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
st.set_page_config(page_title="Grover (LLM's + SEMrush)", layout="wide")
st.title("Grover: LLM Based, with SEMrush Keyword Research")

debug_mode = st.sidebar.checkbox("Debug Mode", value=False)

# Add model selector
model_options = {
    "Claude": "claude-3-5-sonnet-20241022",
    "Groq (Llama-70B)": "llama-70b-v2"
}
st.session_state['selected_model'] = st.sidebar.selectbox("Select Model", list(model_options.keys()))

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

if "section_conversations" not in st.session_state:
    st.session_state.section_conversations = {}

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
            def_topic = existing_notes.get("topic", "")
            freeform_notes = existing_notes.get("freeform_notes", "")

            upd_name = st.text_input("Project Name", value=proj_data["name"])
            upd_journey = dynamic_selectbox("Consumer Journey Stage", journey_stage_options, proj_data.get("journey_stage", "Awareness"))
            upd_category = dynamic_selectbox("Article Category", article_category_options, proj_data.get("category", "Senior Living"))
            upd_care_areas = dynamic_multiselect("Care Area(s)", care_area_options, existing_care_areas)
            upd_format = dynamic_selectbox("Format Type", format_type_options, proj_data.get("format_type", "Blog"))
            upd_bizcat = dynamic_selectbox("Business Category", business_category_options, proj_data.get("business_category", "Senior Living"))
            upd_need = dynamic_selectbox("Consumer Need", consumer_need_options, def_need)
            upd_tone = dynamic_selectbox("Tone of Voice", tone_of_voice_options, def_tone)
            upd_audience = dynamic_selectbox("Target Audience", target_audience_options, def_audience)

            st.write("#### Topic & Freeform Notes")
            upd_topic = st.text_input("Topic (Optional)", value=def_topic)
            upd_notes_text = st.text_area("Additional Notes", value=freeform_notes)

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
                    upd_topic = chosen_suggestion
                    st.session_state["topic_suggestions"] = []
                    st.success(f"Topic set to: {chosen_suggestion}")

            if st.button("Update Project"):
                final_notes_json = {
                    "consumer_need": upd_need,
                    "tone_of_voice": upd_tone,
                    "target_audience": upd_audience,
                    "freeform_notes": upd_notes_text,
                    "topic": upd_topic,
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

        st.write("#### Topic & Freeform Notes")
        new_topic = st.text_input("Topic (Optional)")
        new_notes_text = st.text_area("Additional Notes (optional)")

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
                new_topic = chosen_suggestion
                st.success(f"Topic set to: {chosen_suggestion}")
                st.session_state["topic_suggestions"] = []

        if st.button("Create Project"):
            if new_name.strip():
                final_notes_json = {
                    "consumer_need": new_need,
                    "tone_of_voice": new_tone,
                    "target_audience": new_audience,
                    "freeform_notes": new_notes_text,
                    "topic": new_topic.strip(),
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


# --------------------------------------------------------------------
# 4) Generate & Refine (Claude)
# --------------------------------------------------------------------
def clean_article_text(content, debug_mode=False):
    """Remove word count markers and keyword markers from article text (if desired)."""
    if not content:
        return ""
    if debug_mode:
        # If debug mode, keep markers so we can see them
        return content
    # Remove the numeric markers like (1), (2), etc. but keep any real parentheses from text?
    # This might be a simple approach:
    cleaned = re.sub(r"\(\d+\)", "", content)
    # Keep (keyword) references or remove them?
    # If you want to remove (keyword) as well, uncomment:
    # cleaned = re.sub(r"\(keyword\)", "", cleaned)
    return cleaned

def generate_article_with_validation(prompt_msg, keywords, max_attempts=5, debug_mode=False):
    """
    Each attempt re-runs the SAME prompt from scratch.
    If at any attempt we pass certain validations (like including keywords),
    return that result. Otherwise, after max_attempts, return the final attempt's data.
    """
    final_attempt_output = ""
    final_attempt_parsed = {}

    for attempt in range(1, max_attempts + 1):
        with st.spinner(f"Generating article & meta from Claude (Attempt {attempt}/{max_attempts})..."):
            output = query_claude_api(prompt_msg)
            final_attempt_output = output  # Store for final usage

            # Try parsing the output as JSON
            try:
                start_idx = output.find('{')
                end_idx = output.rfind('}')
                if start_idx == -1 or end_idx == -1:
                    raise json.JSONDecodeError("No valid JSON object found", output, 0)

                json_str = output[start_idx:end_idx + 1]
                parsed = json.loads(json_str)
                final_attempt_parsed = parsed

                generated_article = parsed.get("article", "").strip()
                generated_title = parsed.get("meta_title", "").strip()
                generated_desc = parsed.get("meta_description", "").strip()

                # Basic checks
                if not generated_article or not generated_title or not generated_desc:
                    if debug_mode:
                        st.write(f"Attempt {attempt}: Missing required fields.")
                    continue

                # Check that all keywords appear
                lower_article = generated_article.lower()
                missing = [kw for kw in keywords if kw.lower() not in lower_article]
                if missing:
                    if debug_mode:
                        st.write(f"Attempt {attempt}: Missing keywords: {missing}")
                    continue

                # If all checks pass, return the article
                return generated_article, generated_title, generated_desc

            except json.JSONDecodeError:
                if debug_mode:
                    st.write(f"Attempt {attempt}: Could not parse JSON.")
                continue

    # If all attempts fail, return the final attempt's best-guess data
    st.error(f"Failed to produce a valid JSON after {max_attempts} attempts.")
    if final_attempt_parsed:
        article_text = final_attempt_parsed.get("article", "").strip()
        meta_title = final_attempt_parsed.get("meta_title", "").strip()
        meta_desc = final_attempt_parsed.get("meta_description", "").strip()
        st.info("Showing final attempt's partial output below (validation not passed):")
        return article_text, meta_title, meta_desc
    else:
        # Could not parse final attempt at all
        return final_attempt_output, "", ""

def generate_section(prompt_msg, section_num, total_sections, previous_sections="", words_so_far=0, target_words=1200, debug_mode=False):
    """Generate a single section of the article."""
    # Calculate words per section
    words_per_section = target_words // total_sections
    remaining_words = target_words - words_so_far
    
    # Get or create conversation history for this section
    if section_num not in st.session_state.section_conversations:
        st.session_state.section_conversations[section_num] = []
    
    conversation = st.session_state.section_conversations[section_num]
    
    section_prompt = f"""
You are writing a highly focused article based on these requirements:
{prompt_msg}

STRICT REQUIREMENTS:
1. Stay focused on the main topic and brief provided above
2. Follow the project details exactly as specified
3. Maintain consistent tone and style throughout
4. Include relevant keywords naturally

Current Progress:
- This is section {section_num} of {total_sections}
- Previous sections: 
{previous_sections}

For this section {section_num}:
- Target word count: ~{words_per_section} words
- Remaining total words: {remaining_words}
- Must continue logically from previous sections
- Must stay focused on the main topic

Format Requirements:
1. Start with '## ' followed by an appropriate section title
2. Mark all specified keywords with (keyword)
3. Mark all other words with sequential numbers: (1), (2), etc.
4. Ensure content flows naturally from previous sections

Return ONLY a JSON object with this structure:
{{
    "section_content": "The section content with markers",
    "section_title": "The title used for this section"
}}"""
    
    if debug_mode:
        st.write(f"### Debug: Full Prompt for Section {section_num}")
        st.code(section_prompt, language="text")
    
    response = query_claude_api(section_prompt, conversation)
    
    if debug_mode:
        st.write(f"### Debug: LLM Response for Section {section_num}")
        st.code(response, language="text")
    
    try:
        parsed = json.loads(response)
        
        if not all(k in parsed for k in ["section_content", "section_title"]):
            if debug_mode:
                st.error("Missing required fields in JSON response")
            return None
            
        word_count = len(parsed["section_content"].split())
        parsed["word_count"] = word_count
            
        return parsed
    except json.JSONDecodeError as e:
        if debug_mode:
            st.error(f"JSON parsing error: {str(e)}")
        return None
    except Exception as e:
        if debug_mode:
            st.error(f"Unexpected error: {str(e)}")
        return None

def generate_section_with_retries(prompt_msg, section_num, total_sections, previous_sections="", words_so_far=0, target_words=1000, debug_mode=False, max_attempts=50):
    """Generate a single section with multiple retry attempts."""
    last_response = None
    
    # Double the target words internally
    internal_target = target_words * 2
    words_per_section = internal_target // total_sections
    
    # Allow 50% less or more than the doubled target
    min_acceptable_words = int(words_per_section * 0.5)  # 50% of target
    max_acceptable_words = int(words_per_section * 1.5)  # 150% of target
    
    # Create a progress placeholder
    progress_text = st.empty()
    
    for attempt in range(max_attempts):
        # Always show progress, not just in debug mode
        progress_text.write(f"Section {section_num}: Attempt {attempt + 1}/{max_attempts}")
        
        if debug_mode:
            st.write(f"Target words: {words_per_section}, Acceptable range: {min_acceptable_words}-{max_acceptable_words}")
        
        section_data = generate_section(
            prompt_msg=prompt_msg,
            section_num=section_num,
            total_sections=total_sections,
            previous_sections=previous_sections,
            words_so_far=words_so_far,
            target_words=internal_target,
            debug_mode=debug_mode
        )
        
        # Store the last valid response
        if section_data and isinstance(section_data, dict) and "section_content" in section_data:
            last_response = section_data
            current_words = section_data["word_count"]
            
            if debug_mode:
                st.write(f"Generated {current_words} words")
            
            # If we have enough words within the acceptable range, return this response
            if min_acceptable_words <= current_words <= max_acceptable_words:
                if debug_mode:
                    st.success(f"Section {section_num} generated successfully with {current_words} words on attempt {attempt + 1}")
                return section_data
            elif debug_mode:
                if current_words < min_acceptable_words:
                    st.warning(f"Word count too low: {current_words} < {min_acceptable_words}, retrying...")
                else:
                    st.warning(f"Word count too high: {current_words} > {max_acceptable_words}, retrying...")
            
            # Overwrite prompt with word count instruction
            base_prompt = prompt_msg
            if current_words < min_acceptable_words:
                additional_words_needed = min_acceptable_words - current_words
                prompt_msg = f"{base_prompt}\n\nIMPORTANT: Your section must be between {min_acceptable_words} and {max_acceptable_words} words. Your previous response was {current_words} words. Add approximately {additional_words_needed} more words."
            else:
                words_to_reduce = current_words - max_acceptable_words
                prompt_msg = f"{base_prompt}\n\nIMPORTANT: Your section must be between {min_acceptable_words} and {max_acceptable_words} words. Your previous response was {current_words} words. Reduce the content by approximately {words_to_reduce} words."
    
    # If we get here, all attempts failed to meet word count
    if debug_mode:
        st.error(f"All {max_attempts} attempts failed to meet word count requirements for section {section_num}")
        if last_response:
            st.write(f"Using best attempt with {last_response.get('word_count', 0)} words")
    
    return last_response or {
        "section_content": f"## Section {section_num}\nFailed to generate content after {max_attempts} attempts.",
        "section_title": f"Section {section_num}",
        "word_count": 0
    }


if st.session_state["project_id"]:
    with st.expander("4) Generate & Refine Article (Claude)"):

        # Additional user inputs for how to structure the article
        desired_article_length = st.number_input(
            "Desired total word count for the article",
            min_value=200,
            max_value=20000,
            value=1000,
            step=100
        )
        number_of_sections = st.number_input(
            "Number of sections",
            min_value=1,
            max_value=20,
            value=5,
            step=1
        )

        # If there's NO article selected, let user give a custom new article name
        new_article_name = ""
        if not st.session_state["article_id"]:
            new_article_name = st.text_input("New Article Name (optional)", value="")

        if st.button("Generate Article from Brief"):
            brief_text = st.session_state.get("article_brief", "")
            db_kws = db.get_project_keywords(st.session_state["project_id"])
            keywords = [k["keyword"] for k in db_kws] if db_kws else []
            kw_str = ", ".join(keywords) if keywords else "(none)"

            # Get project details
            pinfo = db.get_project(st.session_state["project_id"])
            project_notes = {}
            if pinfo:
                pinfo_dict = dict(pinfo)
                try:
                    project_notes = json.loads(pinfo_dict.get("notes", "{}"))
                except:
                    project_notes = {}

                journey_stage = pinfo_dict.get("journey_stage", "")
                category = pinfo_dict.get("category", "")
                care_areas_list = json.loads(pinfo_dict.get("care_areas", "[]"))
                format_type = pinfo_dict.get("format_type", "")
                business_cat = pinfo_dict.get("business_category", "")
                consumer_need = project_notes.get("consumer_need", "")
                tone_of_voice = project_notes.get("tone_of_voice", "")
                target_audience = project_notes.get("target_audience", "")
                freeform_notes = project_notes.get("freeform_notes", "")
                topic_in_notes = project_notes.get("topic", "").strip()

            # Build the base context prompt
            context_msg = f"""
MAIN TOPIC: {topic_in_notes}

PROJECT BRIEF:
{brief_text}

REQUIRED KEYWORDS (must be used):
{kw_str}

PROJECT SPECIFICATIONS:
1. Journey Stage: {journey_stage}
2. Category: {category}
3. Care Areas: {', '.join(care_areas_list)}
4. Format Type: {format_type}
5. Business Category: {business_cat}
6. Consumer Need: {consumer_need}
7. Tone of Voice: {tone_of_voice}
8. Target Audience: {target_audience}

ADDITIONAL CONTEXT:
{freeform_notes}

CONTENT REQUIREMENTS:
- Total Word Count Target: {desired_article_length * 2}  # Doubled for internal target
- Number of Sections: {number_of_sections}
- Must stay focused on the main topic
"""

            full_article = ""
            total_words = 0
            section_titles = []

            for section_num in range(1, number_of_sections + 1):
                with st.spinner(f"Generating section {section_num} of {number_of_sections}..."):
                    section_data = generate_section_with_retries(
                        prompt_msg=context_msg,
                        section_num=section_num,
                        total_sections=number_of_sections,
                        previous_sections=full_article,
                        words_so_far=total_words,
                        target_words=desired_article_length,
                        debug_mode=debug_mode,
                        max_attempts=50
                    )

                    if section_data:
                        if isinstance(section_data, dict) and "section_content" in section_data:
                            full_article += "\n\n" + section_data["section_content"]
                            total_words += section_data.get("word_count", 0)
                            section_titles.append(section_data.get("section_title", f"Section {section_num}"))
                            
                            # Show progress
                            st.write(f"✓ Section {section_num}: {section_data.get('section_title')} ({section_data.get('word_count', 0)} words)")
                        else:
                            st.warning(f"Section {section_num} generated with incomplete data")
                            # Try to continue anyway with what we got
                            full_article += f"\n\n## Section {section_num}\n{str(section_data)}"
                    else:
                        st.error(f"Failed to generate section {section_num}")
                        break

            # Once sections are done, attempt meta generation (optional) only if we have some content
            meta_title = ""
            meta_desc = ""
            if full_article.strip():
                meta_prompt = f"""
Article sections:
{' -> '.join(section_titles)}

Total words so far: {total_words}.

Return ONLY a JSON object with exactly this structure and nothing else:
{{
    "meta_title": "A short SEO-friendly title (50-60 characters)",
    "meta_description": "A meta description around 150-160 characters"
}}
"""
                if debug_mode:
                    st.write("### Debug: Meta Information Prompt")
                    st.code(meta_prompt, language="text")

                meta_response = query_claude_api(meta_prompt)

                if debug_mode:
                    st.write("### Debug: Meta Information Response")
                    st.code(meta_response, language="text")

                try:
                    start_idx = meta_response.find('{')
                    end_idx = meta_response.rfind('}')
                    if start_idx == -1 or end_idx == -1:
                        meta_data = {}
                    else:
                        json_str = meta_response[start_idx:end_idx + 1]
                        meta_data = json.loads(json_str)
                    meta_title = meta_data.get("meta_title", "")
                    meta_desc = meta_data.get("meta_description", "")
                except:
                    meta_title = ""
                    meta_desc = ""

            # Create new article if needed
            if not st.session_state["article_id"]:
                final_title = new_article_name.strip() if new_article_name.strip() else "(Generated Draft)"
                new_art_id = db.save_article_content(
                    project_id=st.session_state["project_id"],
                    article_title=final_title,
                    article_content=full_article,
                    article_schema=None,
                    meta_title=meta_title,
                    meta_description=meta_desc,
                )
                st.session_state["article_id"] = new_art_id

            current_aid = st.session_state["article_id"]
            set_current_draft(current_aid, full_article or "")
            set_meta_title(current_aid, meta_title or "")
            set_meta_desc(current_aid, meta_desc or "")

            if full_article.strip():
                st.success("Article (with numeric markers) + meta fields have been set in the UI!")
            else:
                st.warning("No complete article content generated. Check errors above.")

        # Now show refine UI only if we have an article_id
        article_id = st.session_state["article_id"]
        if not article_id:
            st.info("No article selected/created yet. Generate an article first or create one above.")
        else:
            # Display the current article draft
            current_draft_text = get_current_draft(article_id)
            st.write("### Current Article Draft (with numeric markers)")
            new_draft = st.text_area(
                "Current Article Draft",
                value=clean_article_text(current_draft_text, debug_mode=debug_mode),
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

IMPORTANT: Return only the final text (article) with your modifications applied.
Retain the numeric word markers after each word or (keyword) for keywords.

Refine the article according to these instructions:
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
            updated_article_title = st.text_input("Give your article a clear title", value=existing_title)

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
                    article_id=article_id
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
            st.write(clean_article_text(article_row["article_content"], debug_mode=debug_mode))

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
    all_projects_debug = [dict(p) for p in projects]
    st.write("All Projects:", all_projects_debug)
