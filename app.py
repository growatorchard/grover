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

TARGET_AUDIENCES = ["Seniors", "Adult Children", "Caregivers", "Health Professionals", "Other"]

# --------------------------------------------------------------------
# 1) Database Manager (SQLite) for Grover Projects
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
# 2) Community Manager (SQLite) for Senior Living Communities
# --------------------------------------------------------------------
class CommunityManager:
    def __init__(self):
        # Connect to the communities database file
        self.conn = sqlite3.connect("senior_living.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_communities(self):
        self.cursor.execute("SELECT * FROM communities ORDER BY community_name")
        return self.cursor.fetchall()

    def get_community(self, community_id):
        self.cursor.execute("SELECT * FROM communities WHERE id = ?", (community_id,))
        return self.cursor.fetchone()

    def get_care_areas(self, community_id):
        self.cursor.execute("SELECT * FROM care_areas WHERE community_id = ?", (community_id,))
        return self.cursor.fetchall()

# --------------------------------------------------------------------
# 3) SEMrush Query Code
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
# 4) LLM Query Functions
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
        response = requests.post(url, headers=headers, json=payload, timeout=240)
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
        response = requests.post(url, headers=headers, json=payload, timeout=240)
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

def query_chatgpt_api(message: str, conversation_history: list = None) -> tuple[str, dict]:
    """
    Calls OpenAI's Chat Completion API (ChatGPT) with conversation history support.
    Requires st.secrets['OPENAI_API_KEY'] to be set.
    Returns a tuple of (response_content, token_usage)
    """
    url = "https://api.openai.com/v1/chat/completions"
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except:
        return "Error: No OPENAI_API_KEY found in st.secrets.", {}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({
        'role': 'user',
        'content': message
    })
    payload = {
        "model": "o1-mini",
        "messages": messages,
        "max_completion_tokens": 20000
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=240)
        response.raise_for_status()
        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            content = response_data["choices"][0]["message"]["content"]
            token_usage = response_data.get("usage", {})
            if conversation_history is not None:
                conversation_history.append({
                    'role': 'assistant',
                    'content': content
                })
            return content, token_usage
        return "Could not extract content from ChatGPT response.", {}
    except requests.exceptions.RequestException as e:
        error_message = f"API request failed: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f"\nResponse: {e.response.text}"
        return error_message, {}

def query_llm_api(message: str, conversation_history: list = None) -> str:
    """
    Dispatches the API call to the selected LLM based on the sidebar model selection.
    """
    model = st.session_state.get('selected_model', 'Claude')
    if model == "Claude":
        return query_claude_api(message, conversation_history)
    elif model == "Groq (Llama-70B)":
        return query_groq_api(message, conversation_history)
    elif model == "ChatGPT (o1)":
        return query_chatgpt_api(message, conversation_history)
    else:
        return "Selected model not supported."

# --------------------------------------------------------------------
# 5) Optional Website Scraping
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
# 6) Streamlit App Setup
# --------------------------------------------------------------------
db = DatabaseManager()
comm_manager = CommunityManager()

st.set_page_config(page_title="Grover (LLM's + SEMrush)", layout="wide")
st.title("Grover: LLM Based, with SEMrush Keyword Research")

# Initialize session state variables if they don't exist
if "drafts_by_article" not in st.session_state:
    st.session_state["drafts_by_article"] = {}
if "meta_title_by_article" not in st.session_state:
    st.session_state["meta_title_by_article"] = {}
if "meta_desc_by_article" not in st.session_state:
    st.session_state["meta_desc_by_article"] = {}
if "refine_instructions_by_article" not in st.session_state:
    st.session_state["refine_instructions_by_article"] = {}
if "topic_suggestions" not in st.session_state:
    st.session_state["topic_suggestions"] = []
if "selected_topic" not in st.session_state:
    st.session_state["selected_topic"] = ""
if "article_brief" not in st.session_state:
    st.session_state["article_brief"] = ""

# --------------------------------------------------------------------
# Sidebar: LLM Model Selector
# --------------------------------------------------------------------
debug_mode = st.sidebar.checkbox("Debug Mode", value=False)
model_options = {
    "Claude": "claude-3-5-sonnet-20241022",
    "Groq (Llama-70B)": "llama-70b-v2",
    "ChatGPT (o1)": "gpt-3.5-turbo"
}
st.session_state['selected_model'] = st.sidebar.selectbox("Select Model", list(model_options.keys()))

# --------------------------------------------------------------------
# Sidebar: Project Selection
# --------------------------------------------------------------------
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
if st.session_state["project_id"]:
    if st.sidebar.button("Delete Project"):
        db.delete_project(st.session_state["project_id"])
        st.session_state["project_id"] = None
        st.rerun()

# --------------------------------------------------------------------
# Sidebar: Article Selection (only if a project is chosen)
# --------------------------------------------------------------------
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
    if st.session_state["article_id"]:
        if st.sidebar.button("Delete Article"):
            db.delete_article_content(st.session_state["article_id"])
            st.success("Article content deleted.")
            st.session_state["article_id"] = None
            st.rerun()

# --------------------------------------------------------------------
# 1) Create / Update Project
# --------------------------------------------------------------------
with st.expander("1) Create or Update Project", expanded=(st.session_state["project_id"] is None)):
    if "topic_suggestions" not in st.session_state:
        st.session_state["topic_suggestions"] = []
    if "selected_topic" not in st.session_state:
        st.session_state["selected_topic"] = ""
    if st.session_state["project_id"]:
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
            upd_journey = st.selectbox("Consumer Journey Stage", ["Awareness", "Consideration", "Decision", "Retention", "Advocacy", "Other"], index=0)
            upd_category = st.selectbox("Article Category", ["Senior Living", "Health/Wellness", "Lifestyle", "Financial", "Other"], index=0)
            upd_care_areas = st.multiselect("Care Area(s)", ["Independent Living", "Assisted Living", "Memory Care", "Skilled Nursing"], default=existing_care_areas)
            upd_format = st.selectbox("Format Type", ["Blog", "Case Study", "White Paper", "Guide", "Downloadable Guide", "Review", "Interactives", "Brand Content", "Infographic", "E-Book", "Email", "Social Media Posts", "User Generated Content", "Meme", "Checklist", "Video", "Podcast", "Other"], index=0)
            upd_bizcat = st.selectbox("Business Category", ["Healthcare", "Senior Living", "Housing", "Lifestyle", "Other"], index=0)
            upd_need = st.selectbox("Consumer Need", ["Educational", "Financial Guidance", "Medical Info", "Lifestyle/Wellness", "Other"], index=0)
            upd_tone = st.selectbox("Tone of Voice", ["Professional", "Friendly", "Conversational", "Empathetic", "Other"], index=0)
            upd_audience = st.multiselect("Target Audience", TARGET_AUDIENCES, default=existing_notes.get("target_audience", []))
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
- Target Audience: {', '.join(upd_audience)}

Suggest 5 potential article topics.
"""
                with st.spinner("Generating topic suggestions..."):
                    suggestions_raw, token_usage = query_llm_api(prompt_for_topics)
                st.write(f"Token usage: {token_usage}")
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
        st.write("**Create a New Project**")
        new_name = st.text_input("Project Name")
        new_journey = st.selectbox("Consumer Journey Stage", ["Awareness", "Consideration", "Decision", "Retention", "Advocacy", "Other"], index=0)
        new_category = st.selectbox("Article Category", ["Senior Living", "Health/Wellness", "Lifestyle", "Financial", "Other"], index=0)
        new_care_areas = st.multiselect("Care Area(s)", ["Independent Living", "Assisted Living", "Memory Care", "Skilled Nursing"], default=[])
        new_format = st.selectbox("Format Type", ["Blog", "Case Study", "White Paper", "Guide", "Downloadable Guide", "Review", "Interactives", "Brand Content", "Infographic", "E-Book", "Email", "Social Media Posts", "User Generated Content", "Meme", "Checklist", "Video", "Podcast", "Other"], index=0)
        new_bizcat = st.selectbox("Business Category", ["Healthcare", "Senior Living", "Housing", "Lifestyle", "Other"], index=0)
        new_need = st.selectbox("Consumer Need", ["Educational", "Financial Guidance", "Medical Info", "Lifestyle/Wellness", "Other"], index=0)
        new_tone = st.selectbox("Tone of Voice", ["Professional", "Friendly", "Conversational", "Empathetic", "Other"], index=0)
        new_audience = st.multiselect("Target Audience", TARGET_AUDIENCES, default=[])
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
- Target Audience: {', '.join(new_audience)}

Suggest 5 potential article topics.
"""
            with st.spinner("Generating topic suggestions..."):
                suggestions_raw, token_usage = query_llm_api(prompt_for_topics)
            st.write(f"Token usage: {token_usage}")
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

# --------------------------------------------------------------------
# 2) Manage Keywords (SEMrush)
# --------------------------------------------------------------------
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
                            None,
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
                                None,
                                rk['Kd']
                            )
                            st.rerun()

# --------------------------------------------------------------------
# 3) Article Brief
# --------------------------------------------------------------------
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
# 4) Generate & Refine Article (LLM)
# --------------------------------------------------------------------
if st.session_state["project_id"]:
    with st.expander("4) Generate & Refine Article (LLM)"):
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
        new_article_name = ""
        if not st.session_state["article_id"]:
            new_article_name = st.text_input("New Article Name (optional)", value="")
        if st.button("Generate Article from Brief"):
            brief_text = st.session_state.get("article_brief", "")
            db_kws = db.get_project_keywords(st.session_state["project_id"])
            keywords = [k["keyword"] for k in db_kws] if db_kws else []
            kw_str = ", ".join(keywords) if keywords else "(none)"
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
                target_audience = project_notes.get("target_audience", [])
                freeform_notes = project_notes.get("freeform_notes", "")
                topic_in_notes = project_notes.get("topic", "").strip()
            # COMMUNITY DETAILS are no longer included at article-generation time.
            community_details_text = ""
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
8. Target Audience: {', '.join(target_audience)}

ADDITIONAL CONTEXT:
{freeform_notes}

{community_details_text}
"""
            full_article_prompt = f"""
You are writing a highly focused article based on the following requirements:

{context_msg}

CONTENT REQUIREMENTS:
- The article must be strictly AT LEAST: {desired_article_length} words.
- Number of Sections: {number_of_sections}.
- Each section should start with "## " followed by an appropriate section title.

Ensure that the article flows naturally, stays focused on the main topic, and adheres to the project specifications.

Return ONLY a JSON object with exactly this structure and nothing else:
{{
    "article_content": "The complete article content with section markers and numerical markers",
    "section_titles": ["Section Title 1", "Section Title 2", ..., "Section Title {number_of_sections}"],
    "meta_title": "A short SEO-friendly title (50-60 characters)",
    "meta_description": "A meta description around 150-160 characters"
}}
"""
            # Loop up to 5 iterations to ensure the word count is met
            max_iterations = 5
            iteration = 1
            final_response = None
            while iteration <= max_iterations:
                with st.spinner(f"Generating full article (Iteration {iteration}/{max_iterations})..."):
                    response, token_usage = query_llm_api(full_article_prompt)
                try:
                    start_idx = response.find('{')
                    end_idx = response.rfind('}')
                    if start_idx == -1 or end_idx == -1:
                        raise json.JSONDecodeError("No valid JSON found", response, 0)
                    json_str = response[start_idx:end_idx+1]
                    full_response = json.loads(json_str)
                    full_article = full_response.get("article_content", "")
                    meta_title = full_response.get("meta_title", "")
                    meta_desc = full_response.get("meta_description", "")
                    section_titles = full_response.get("section_titles", [])
                    word_count = len(full_article.split())
                    if word_count >= desired_article_length:
                        final_response = full_response
                        break
                    else:
                        additional_needed = desired_article_length - word_count
                        st.info(f"Article only has {word_count} words. {additional_needed} more words needed. Retrying iteration {iteration + 1}...")
                        full_article_prompt = f"""
Your previous article content is below:
{full_article}

It currently has {word_count} words, which is less than the required {desired_article_length} words.
Please expand the article by adding approximately {additional_needed} more words, while preserving the structure and quality.
Return ONLY a JSON object with exactly the same structure as before:
{{
    "article_content": "The complete article content with section markers and numerical markers",
    "section_titles": ["Section Title 1", "Section Title 2", ..., "Section Title {number_of_sections}"],
    "meta_title": "A short SEO-friendly title (50-60 characters)",
    "meta_description": "A meta description around 150-160 characters"
}}
"""
                        iteration += 1
                except Exception as e:
                    st.error("Failed to parse article JSON: " + str(e))
                    final_response = {"article_content": response, "meta_title": "", "meta_description": "", "section_titles": []}
                    break
            if final_response is not None:
                full_article = final_response.get("article_content", "")
                meta_title = final_response.get("meta_title", "")
                meta_desc = final_response.get("meta_description", "")
                section_titles = final_response.get("section_titles", [])
                total_words = len(full_article.split())
            else:
                full_article = response
                meta_title = ""
                meta_desc = ""
                section_titles = []
                total_words = len(full_article.split())
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
            else:
                new_art_id = st.session_state["article_id"]
            if "drafts_by_article" not in st.session_state:
                st.session_state["drafts_by_article"] = {}
            st.session_state["drafts_by_article"][new_art_id] = full_article
            if "meta_title_by_article" not in st.session_state:
                st.session_state["meta_title_by_article"] = {}
            st.session_state["meta_title_by_article"][new_art_id] = meta_title
            if "meta_desc_by_article" not in st.session_state:
                st.session_state["meta_desc_by_article"] = {}
            st.session_state["meta_desc_by_article"][new_art_id] = meta_desc
            if full_article.strip():
                st.success(f"Article generated with {total_words} words and meta fields set in the UI!")
            else:
                st.warning("No complete article content generated. Check errors above.")
        article_id = st.session_state["article_id"]
        if not article_id:
            st.info("No article selected/created yet. Generate an article first or create one above.")
        else:
            current_draft_text = st.session_state["drafts_by_article"].get(article_id, "")
            st.write("### Current Article Draft (with numeric markers)")
            new_draft = st.text_area(
                "Current Article Draft",
                value=full_article if full_article.strip() else current_draft_text,
                height=300
            )
            if new_draft != current_draft_text:
                st.session_state["drafts_by_article"][article_id] = new_draft
            current_refine_instructions = st.session_state.get("refine_instructions_by_article", {}).get(article_id, "")
            st.write("---")
            st.write("**Optionally** refine the article with additional instructions below.")
            refine_instructions_text = st.text_area("Refine Instructions", value=current_refine_instructions)
            if "refine_instructions_by_article" not in st.session_state:
                st.session_state["refine_instructions_by_article"] = {}
            st.session_state["refine_instructions_by_article"][article_id] = refine_instructions_text
            if st.button("Refine Article"):
                if refine_instructions_text.strip():
                    refine_prompt = f"""
Current article:

{st.session_state["drafts_by_article"].get(article_id, "")}

IMPORTANT: Return only the final text (article) with your modifications applied.
Retain the numeric word markers after each word or (keyword) for keywords.

Refine the article according to these instructions:
{refine_instructions_text}
"""
                    with st.spinner("Refining..."):
                        refined, token_usage = query_llm_api(refine_prompt)
                    st.write(f"Token usage: {token_usage}")
                    st.session_state["drafts_by_article"][article_id] = refined
                    st.success("Refined successfully!")
                else:
                    st.warning("Please enter some instructions to refine the article.")

# --------------------------------------------------------------------
# 5) Save/Update Final Article
# --------------------------------------------------------------------
if st.session_state["project_id"]:
    with st.expander("5) Save/Update Final Article"):
        article_id = st.session_state["article_id"]
        if not article_id:
            st.info("No article selected. Generate or select one first.")
        else:
            draft_text = st.session_state["drafts_by_article"].get(article_id, "")
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
            default_meta_title = st.session_state.get("meta_title_by_article", {}).get(article_id, "") or existing_meta_title
            default_meta_desc = st.session_state.get("meta_desc_by_article", {}).get(article_id, "") or existing_meta_desc
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
                st.session_state["drafts_by_article"][saved_id] = final_text
                if "meta_title_by_article" not in st.session_state:
                    st.session_state["meta_title_by_article"] = {}
                st.session_state["meta_title_by_article"][saved_id] = meta_title
                if "meta_desc_by_article" not in st.session_state:
                    st.session_state["meta_desc_by_article"] = {}
                st.session_state["meta_desc_by_article"][saved_id] = meta_desc
                st.success("Article saved to DB!")
                st.session_state["article_id"] = saved_id

# --------------------------------------------------------------------
# 6) View Saved Article
# --------------------------------------------------------------------
if st.session_state.get("project_id") and st.session_state.get("article_id"):
    with st.expander("6) View Saved Article"):
        article_row = db.get_article_content(st.session_state["article_id"])
        if not article_row:
            st.info("No article has been saved yet for this selection.")
        else:
            st.write("### Article Title")
            st.write(article_row["article_title"])
            st.write("### Article Content")
            st.write(full_article if full_article.strip() else article_row["article_content"])
            if article_row["meta_title"] or article_row["meta_description"]:
                st.write("---")
                st.write("**Meta Title**:", article_row["meta_title"])
                st.write("**Meta Description**:", article_row["meta_description"])
            if st.button("Delete Saved Article", key="delete_saved_article"):
                db.delete_article_content(article_row["id"])
                st.success("Article content deleted.")
                st.session_state["article_id"] = None
                st.rerun()

# --------------------------------------------------------------------
# 7) Generate Community-Specific Revision
# --------------------------------------------------------------------
if st.session_state.get("project_id") and st.session_state.get("article_id"):
    with st.expander("7) Generate Community-Specific Revision"):
        article_row = db.get_article_content(st.session_state["article_id"])
        if not article_row:
            st.info("No saved article found. Please generate and save an article first.")
        else:
            original_article = article_row["article_content"]
            # Get the list of communities from the Community Manager
            communities = comm_manager.get_communities()
            community_names = ["None"] + [f"{c['community_name']} (ID: {c['id']})" for c in communities]
            selected_rev_comm = st.selectbox("Select Community for Revision", community_names, key="rev_comm")
            if selected_rev_comm != "None":
                rev_comm_id = int(selected_rev_comm.split("ID:")[-1].replace(")", "").strip())
                community = comm_manager.get_community(rev_comm_id)
                care_areas = comm_manager.get_care_areas(rev_comm_id)
                care_areas_names = [ca["care_area"] for ca in care_areas] if care_areas else []
                community_details_text = f"""
COMMUNITY DETAILS:
- Name: {community["community_name"]}
- Primary Domain: {community["community_primary_domain"]}
- Location: {community["city"]}, {community["state"]}, {community["address"]}, {community["zip_code"]}
- About Page: {community["about_page"]}
- Contact Page: {community["contact_page"]}
- Floor Plan Page: {community["floor_plan_page"]}
- Dining Page: {community["dining_page"]}
- Gallery Page: {community["gallery_page"]}
- Health & Wellness Page: {community["health_wellness_page"]}
- Care Areas: {', '.join(care_areas_names) if care_areas_names else 'None'}
"""
                default_rev_instructions = f"Revise the article below to be specifically tailored for the community with the following details: {community_details_text}"
                rev_instructions = st.text_area("Revision Instructions (optional)", value=default_rev_instructions, key="rev_instructions")
                if st.button("Generate Community Revision"):
                    revision_prompt = f"""
Here is the current article:
{original_article}

Please revise this article to be specifically tailored for the following community:
{community_details_text}

Ensure the revised article speaks directly to the community's audience and includes relevant details.

Return only the revised article text.
"""
                    with st.spinner("Generating community-specific revision..."):
                        revised_article_text, token_usage = query_llm_api(revision_prompt)
                    st.write(f"Token usage: {token_usage}")
                    new_rev_title = f"{article_row['article_title']} - Community Revision for {community['community_name']}"
                    new_article_id = db.save_article_content(
                        project_id = st.session_state["project_id"],
                        article_title = new_rev_title,
                        article_content = revised_article_text,
                        article_schema = None,
                        meta_title = article_row.get("meta_title", ""),
                        meta_description = article_row.get("meta_description", "")
                    )
                    st.success(f"Community revision saved as new article (ID: {new_article_id}).")
                    # Optionally, update the session to select the new article revision
                    st.session_state["article_id"] = new_article_id
            else:
                st.info("Please select a community for revision.")

# --------------------------------------------------------------------
# Debug Info
# --------------------------------------------------------------------
if debug_mode:
    st.write("## Debug Info")
    st.json({"project_id": st.session_state.get("project_id")})
    st.json({"article_id": st.session_state.get("article_id")})
    st.json({"article_brief": st.session_state.get("article_brief", "")})
    st.json({"drafts_by_article": st.session_state.get("drafts_by_article", {})})
    st.json({"refine_instructions_by_article": st.session_state.get("refine_instructions_by_article", {})})
    st.json({"meta_title_by_article": st.session_state.get("meta_title_by_article", {})})
    st.json({"meta_desc_by_article": st.session_state.get("meta_desc_by_article", {})})
    all_projects_debug = [dict(p) for p in projects]
    st.write("All Projects:", all_projects_debug)
