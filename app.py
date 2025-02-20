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
import pyperclip
from config.settings import TARGET_AUDIENCES
from database.database_manager import DatabaseManager
from database.community_manager import CommunityManager
from services.llm_service import query_chatgpt_api, query_llm_api, generate_meta_content
from services.semrush_service import get_keyword_suggestions, format_keyword_report
from services.scraping_service import scrape_website
from utils.token_calculator import calculate_token_costs
from utils.json_cleaner import clean_json_response, extract_article_content
from services.community_service import get_care_area_details

load_dotenv()  # This loads environment variables from .env

# Initialize database managers
db = DatabaseManager()
comm_manager = CommunityManager()

def autosave_final_article():
    article_id = st.session_state.get("article_id")
    if article_id:
        updated_title = st.session_state.get("final_title", "")
        updated_text = st.session_state.get("final_article", "")
        updated_meta_title = st.session_state.get("final_meta_title", "")
        updated_meta_desc = st.session_state.get("final_meta_desc", "")
        saved_id = db.save_article_content(
            project_id=st.session_state["project_id"],
            article_title=updated_title or "Auto-Generated Title",
            article_content=updated_text,
            article_schema=None,
            meta_title=updated_meta_title,
            meta_description=updated_meta_desc,
            article_id=article_id,
        )
        st.session_state["article_id"] = saved_id
        st.success("Document auto-saved!")

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
if "token_usage_history" not in st.session_state:
    st.session_state["token_usage_history"] = []

# --------------------------------------------------------------------
# Sidebar: LLM Model Selector
# --------------------------------------------------------------------
debug_mode = st.sidebar.checkbox("Debug Mode", value=False)
model_options = {"ChatGPT (o1)": "o1-mini"}
st.session_state["selected_model"] = st.sidebar.selectbox("Select Model", list(model_options.keys()))

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
            try:
                existing_notes = json.loads(proj_data.get("notes") or "{}")
            except Exception:
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
                    suggestions_raw, token_usage, raw_response = query_llm_api(prompt_for_topics)
                costs = calculate_token_costs(token_usage)
                st.write(f"""
**Token Usage & Costs:**
- Input: {costs['prompt_tokens']:,} tokens (${costs['input_cost']:.4f})
- Output: {costs['completion_tokens']:,} tokens (${costs['output_cost']:.4f})
- Total: {costs['total_tokens']:,} tokens (${costs['total_cost']:.4f})
""")
                if debug_mode:
                    st.write("**Raw API Response:**")
                    st.code(raw_response, language="json")
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
                suggestions_raw, token_usage, raw_response = query_llm_api(prompt_for_topics)
            costs = calculate_token_costs(token_usage)
            st.write(f"""
**Token Usage & Costs:**
- Input: {costs['prompt_tokens']:,} tokens (${costs['input_cost']:.4f})
- Output: {costs['completion_tokens']:,} tokens (${costs['output_cost']:.4f})
- Total: {costs['total_tokens']:,} tokens (${costs['total_cost']:.4f})
""")
            if debug_mode:
                st.write("**Raw API Response:**")
                st.code(raw_response, language="json")
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
                col1, col2 = st.columns([1, 1])
                col1.success("Project created successfully! Please select it from the drop down menu on the left to begin working.")
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
                col1, col2 = st.columns([8, 1])
                col1.write(
                    f"- **{kw['keyword']}** (Vol={kw['search_volume']}, Diff={kw['keyword_difficulty']})"
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
                    col1, col2 = st.columns([8, 1])
                    col1.markdown(
                        f"**Main Keyword**: {main_kw.get('Ph', 'N/A')} (Volume={main_kw.get('Nq', 'N/A')}, Diff={main_kw.get('Kd', 'N/A')})"
                    )
                    if col2.button("➕", key=f"add_main_{main_kw.get('Ph', '')}"):
                        db.add_keyword(
                            st.session_state["project_id"],
                            main_kw.get("Ph", ""),
                            main_kw.get("Nq", 0),
                            None,
                            main_kw.get("Kd", 0),
                        )
                        st.rerun()
                if related_kws:
                    st.write("**Related Keywords**:")
                    for idx, rk in enumerate(related_kws):
                        col1, col2 = st.columns([8, 1])
                        col1.write(f"- {rk.get('Ph', 'N/A')} (Vol={rk.get('Nq', 'N/A')}, Diff={rk.get('Kd', 'N/A')}, Intent={rk.get('In', 'N/A')})")
                        if col2.button("➕", key=f"add_rel_{rk.get('Ph', '')}_{idx}"):
                            db.add_keyword(
                                st.session_state["project_id"],
                                rk.get("Ph", ""),
                                rk.get("Nq", 0),
                                None,
                                rk.get("Kd", 0),
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
            height=150,
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
            step=100,
        )
        number_of_sections = st.number_input(
            "Number of sections",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
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
                except Exception:
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
Generate a comprehensive article that MUST be AT LEAST {desired_article_length} words (this is a strict minimum).

STRUCTURE:
- Create exactly {number_of_sections} sections
- Each section must start with "## " followed by a descriptive title
- Maintain consistent depth and detail across all sections

CONTEXT:
Topic: {topic_in_notes}
Keywords to Include: {kw_str}
Target Audience: {', '.join(target_audience)}
Tone: {tone_of_voice}

Return ONLY a JSON object with this structure:
{{
    "article_content": "The complete article with section markers",
    "section_titles": ["Title 1", "Title 2", ...],
}}
"""
            max_iterations = 5
            iteration = 1
            final_response = None
            while iteration <= max_iterations:
                with st.spinner(f"Generating full article (Iteration {iteration}/{max_iterations})..."):
                    response, token_usage, raw_response = query_llm_api(full_article_prompt)
                    st.session_state["token_usage_history"].append({
                        "iteration": iteration,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "usage": token_usage,
                    })
                    costs = calculate_token_costs(token_usage)
                    st.write(f"""
**Token Usage & Costs:**
- Input: {costs['prompt_tokens']:,} tokens (${costs['input_cost']:.4f})
- Output: {costs['completion_tokens']:,} tokens (${costs['output_cost']:.4f})
- Total: {costs['total_tokens']:,} tokens (${costs['total_cost']:.4f})
""")
                    if debug_mode:
                        st.write("**Raw API Response:**")
                        st.code(raw_response, language="json")
                try:
                    article_text = clean_json_response(response)
                    word_count = len(article_text.split())
                    if word_count == 0:
                        st.warning("Generated article appears to be empty. Retrying...")
                        iteration = 1
                        continue
                    if word_count >= desired_article_length:
                        final_response = {"article_content": article_text, "section_titles": []}
                        break
                    else:
                        additional_needed = desired_article_length - word_count
                        st.info(f"Article only has {word_count} words. {additional_needed} more words needed. Retrying iteration {iteration + 1}...")
                        full_article_prompt = f"""
IMPORTANT: The previous article was {word_count} words, which is BELOW the required {desired_article_length} words.

Add approximately {additional_needed} more words to reach the minimum requirement while maintaining quality and relevance.

Previous content:
{article_text}

Return the complete expanded article in the same JSON format as before.
"""
                        iteration += 1
                except Exception as e:
                    st.error("Failed to parse article JSON: " + str(e))
                    if not response.strip() or len(response.strip().split()) == 0:
                        st.warning("Empty response received. Restarting generation process...")
                        iteration = 1
                        full_article_prompt = f"""
Generate a comprehensive article that MUST be AT LEAST {desired_article_length} words (this is a strict minimum).

STRUCTURE:
- Create exactly {number_of_sections} sections
- Each section must start with "## " followed by a descriptive title
- Maintain consistent depth and detail across all sections

CONTEXT:
Topic: {topic_in_notes}
Keywords to Include: {kw_str}
Target Audience: {', '.join(target_audience)}
Tone: {tone_of_voice}

Return ONLY a JSON object with this structure:
{{
    "article_content": "The complete article with section markers",
    "section_titles": ["Title 1", "Title 2", ...],
}}
"""
                        continue
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
            new_draft = st.text_area("Current Article Draft", value=current_draft_text, height=300)
            if new_draft != current_draft_text:
                st.session_state["drafts_by_article"][article_id] = new_draft

            # Get current refine instructions from session state
            refine_instructions = st.session_state.get("refine_instructions_by_article", {}).get(article_id, "")
            new_refine_instructions = st.text_area(
                "Refine Instructions",
                value=refine_instructions,
                help="Enter instructions for refining the article",
            )
            if new_refine_instructions != refine_instructions:
                if "refine_instructions_by_article" not in st.session_state:
                    st.session_state["refine_instructions_by_article"] = {}
                st.session_state["refine_instructions_by_article"][article_id] = new_refine_instructions

            if new_refine_instructions:
                col1, col2, col3 = st.columns([3, 2, 2])
                if col2.button("Refine Article", use_container_width=True):
                    with st.spinner("Refining article..."):
                        refined_text, token_usage, raw_response = query_llm_api(
                            f"Refine the article according to these instructions: {new_refine_instructions}"
                        )
                        st.session_state["drafts_by_article"][article_id] = refined_text
                        st.success("Article refined.")
                if col3.button("Fix Format", use_container_width=True):
                    with st.spinner("Fixing format..."):
                        current_draft = st.session_state["drafts_by_article"].get(article_id, "")
                        fix_format_prompt = f"""Please reformat the following JSON so that it is properly formatted. Remove any extra characters or markdown formatting, and return only the valid JSON object in the following structure:
{{
    "article_content": "The complete article with section markers",
    "section_titles": ["Title 1", "Title 2", ...]
}}

JSON to fix:
{current_draft}
"""
                        fixed_text, token_usage, raw_response = query_llm_api(fix_format_prompt)
                        st.session_state["drafts_by_article"][article_id] = fixed_text
                        st.success("Article format fixed.")

# --------------------------------------------------------------------
# 5) Save/Update Final Article (Auto-Saved)
# --------------------------------------------------------------------
if st.session_state["project_id"]:
    with st.expander("5) Final Article (Auto-Saved)"):
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
            default_meta_title = st.session_state.get("meta_title_by_article", {}).get(article_id, "") or existing_meta_title
            default_meta_desc = st.session_state.get("meta_desc_by_article", {}).get(article_id, "") or existing_meta_desc
            st.write("### Article Title")
            updated_article_title = st.text_input("Give your article a clear title", key="final_title", value=existing_title, on_change=autosave_final_article)
            final_text = st.text_area("Final Article", key="final_article", value=draft_text, height=300, on_change=autosave_final_article)
            if st.button("Generate Meta Content"):
                generated_title, generated_desc = generate_meta_content(st.session_state.get("final_article", ""))
                if generated_title and generated_desc:
                    st.session_state["final_meta_title"] = generated_title
                    st.session_state["final_meta_desc"] = generated_desc
                    st.success("Meta content generated!")
                else:
                    st.error("Failed to generate meta content.")
            meta_title = st.text_area(
                "Meta Title",
                value=st.session_state.get("final_meta_title", ""),
                key="final_meta_title",
                height=100,
            )
            meta_desc = st.text_area(
                "Meta Description",
                value=st.session_state.get("final_meta_desc", ""),
                key="final_meta_desc",
                height=100,
            )
            col1, col2 = st.columns([1, 1])
            if col1.button("Update Final Article"):
                final_notes_json = {
                    "consumer_need": existing_notes.get("consumer_need", ""),
                    "tone_of_voice": existing_notes.get("tone_of_voice", ""),
                    "target_audience": existing_notes.get("target_audience", []),
                    "freeform_notes": existing_notes.get("freeform_notes", ""),
                    "topic": existing_notes.get("topic", ""),
                }
                patch = {
                    "name": existing_name,
                    "care_areas": existing_care_areas,
                    "journey_stage": existing_journey,
                    "category": existing_category,
                    "format_type": existing_format,
                    "business_category": existing_bizcat,
                    "notes": json.dumps(final_notes_json),
                }
                db.update_project_state(existing_id, patch)
                st.success("Project updated.")
            st.info("All changes are auto-saved as you edit.")

# --------------------------------------------------------------------
# 6) View Saved Article
# --------------------------------------------------------------------
if st.session_state.get("project_id") and st.session_state.get("article_id"):
    with st.expander("6) View Saved Article"):
        article_row = db.get_article_content(st.session_state["article_id"])
        if not article_row:
            st.info("No saved article found. Please generate and save an article first.")
        else:
            st.write(f"**Title**: {article_row['article_title']}")
            st.write(f"**Meta Title**: {article_row['meta_title']}")
            st.write(f"**Meta Description**: {article_row['meta_description']}")
            st.markdown("**Article Content**:")
            st.markdown(article_row["article_content"])
            if st.button("Copy Raw Markdown"):
                pyperclip.copy(article_row["article_content"])
                st.toast("Article content copied to clipboard!")
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
            communities = comm_manager.get_communities()
            community_names = ["None"] + [f"{c['community_name']} (ID: {c['id']})" for c in communities]
            selected_rev_comm = st.selectbox("Select Community for Revision", community_names, key=f"rev_comm_{st.session_state['article_id']}")
            if selected_rev_comm != "None":
                rev_comm_id = int(selected_rev_comm.split("ID:")[-1].replace(")", "").strip())
                community = comm_manager.get_community(rev_comm_id)
                if st.button("Generate Community Revision", key=f"gen_rev_{rev_comm_id}"):
                    aliases = comm_manager.get_aliases(rev_comm_id)
                    alias_list = [alias["alias"] for alias in aliases] if aliases else []
                    aliases_text = ", ".join(alias_list) if alias_list else "None"
                    care_area_details_text = get_care_area_details(comm_manager, rev_comm_id)
                    community_details_text = f"""
COMMUNITY DETAILS:
- Name: {community["community_name"]}
- Primary Domain: {community["community_primary_domain"]}
- Location: {community["city"]}, {community["state"]}, {community["address"]}, {community["zip_code"]}
- Aliases: {aliases_text}

Detailed Care Areas:
{care_area_details_text}
"""
                    revision_prompt = f"""
ORIGINAL ARTICLE CONTEXT:
- Article Type: {article_row['article_title']}
- Project Details: {json.loads(db.get_project(st.session_state["project_id"])['notes'])}

ORIGINAL ARTICLE:
{original_article}

COMMUNITY CUSTOMIZATION REQUEST:
Please update this article to be specifically tailored for the following senior living community while maintaining the original article's core message and structure.

COMMUNITY DETAILS:
{community_details_text}

REVISION REQUIREMENTS:
1. Incorporate community-specific details naturally throughout the article
2. Include relevant internal links to optimize keyword SEO; include each link a maximum of once in the article. YOU MAY NOT USE EACH LINK MORE THAN ONCE EVER
   - About Page: {community["about_page"]}
   - Contact Page: {community["contact_page"]}
   - Floor Plan Page: {community["floor_plan_page"]}
   - Dining Page: {community["dining_page"]}
   - Gallery Page: {community["gallery_page"]}
   - Health & Wellness Page: {community["health_wellness_page"]}

3. Reference specific care areas, amenities, and services available at this community
4. Maintain the original article's SEO focus and keyword strategy
5. Keep the same general structure but with community-specific examples and details

FORMATTING INSTRUCTIONS:
- Preserve any existing headers (## format)
- Include internal links using markdown format [text](url)
- Maintain professional tone while speaking directly to the community's specific audience

Return only the revised article text with all formatting preserved.
"""
                    with st.spinner("Generating community-specific revision..."):
                        revised_article_text, token_usage, raw_response = query_llm_api(revision_prompt)
                        costs = calculate_token_costs(token_usage)
                        st.write(f"""
**Token Usage & Costs:**
- Input: {costs['prompt_tokens']:,} tokens (${costs['input_cost']:.4f})
- Output: {costs['completion_tokens']:,} tokens (${costs['output_cost']:.4f})
- Total: {costs['total_tokens']:,} tokens (${costs['total_cost']:.4f})
""")
                        if debug_mode:
                            st.write("**Raw API Response:**")
                            st.code(raw_response, language="json")
                        new_rev_title = f"{article_row['article_title']} - Community Revision for {community['community_name']}"
                        article_dict = dict(article_row)
                        
                        # Update the drafts and session state before saving to DB
                        if "drafts_by_article" not in st.session_state:
                            st.session_state["drafts_by_article"] = {}
                        st.session_state["drafts_by_article"][st.session_state["article_id"]] = revised_article_text
                        
                        new_article_id = db.save_article_content(
                            project_id=st.session_state["project_id"],
                            article_title=new_rev_title,
                            article_content=revised_article_text,
                            article_schema=None,
                            meta_title=article_dict.get("meta_title", ""),
                            meta_description=article_dict.get("meta_description", ""),
                        )
                        
                        # Update session state with new article ID and its content
                        st.session_state["article_id"] = new_article_id
                        st.session_state["drafts_by_article"][new_article_id] = revised_article_text
                        
                        # Preserve meta information
                        if "meta_title_by_article" not in st.session_state:
                            st.session_state["meta_title_by_article"] = {}
                        if "meta_desc_by_article" not in st.session_state:
                            st.session_state["meta_desc_by_article"] = {}
                        st.session_state["meta_title_by_article"][new_article_id] = article_dict.get("meta_title", "")
                        st.session_state["meta_desc_by_article"][new_article_id] = article_dict.get("meta_description", "")
                        
                        st.success(f"Community revision saved as new article (ID: {new_article_id}).")
                        st.rerun()
            else:
                st.info("Please select a community for revision.")

# --------------------------------------------------------------------
# Debug Info
# --------------------------------------------------------------------
if debug_mode:
    st.write("## Debug Info")
    st.json({
        "project_id": st.session_state.get("project_id"),
        "article_id": st.session_state.get("article_id"),
        "article_brief": st.session_state.get("article_brief", ""),
        "drafts_by_article": st.session_state.get("drafts_by_article", {}),
        "refine_instructions_by_article": st.session_state.get("refine_instructions_by_article", {}),
        "meta_title_by_article": st.session_state.get("meta_title_by_article", {}),
        "meta_desc_by_article": st.session_state.get("meta_desc_by_article", {}),
        "token_usage_history": st.session_state.get("token_usage_history", []),
    })
    all_projects_debug = [dict(p) for p in projects]
    st.write("All Projects:", all_projects_debug)
