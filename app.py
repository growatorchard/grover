import json
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
import pyperclip
from config.settings import TARGET_AUDIENCES, MODEL_OPTIONS, CARE_AREAS, JOURNEY_STAGES, ARTICLE_CATEGORIES, FORMAT_TYPES, BUSINESS_CATEGORIES, CONSUMER_NEEDS, TONE_OF_VOICE
from database.database_manager import DatabaseManager
from database.community_manager import CommunityManager
from services.llm_service import query_chatgpt_api, query_llm_api, generate_meta_content
from services.semrush_service import get_keyword_suggestions, format_keyword_report
from utils.token_calculator import calculate_token_costs
from utils.json_cleaner import clean_json_response, extract_article_content
from services.community_service import get_care_area_details
from services.article_service import ArticleService
from services.state_service import StateService
from services.project_service import ProjectService

load_dotenv()  # This loads environment variables from .env

# Initialize database managers
db = DatabaseManager()
comm_manager = CommunityManager()

# Add this near the top of the file with other session state initializations
if "show_project_success" not in st.session_state:
    st.session_state["show_project_success"] = False

st.set_page_config(page_title="Grover (LLM's + SEMrush)", layout="wide")
st.title("Grover: LLM Based, with SEMrush Keyword Research")

# Initialize services
state_service = StateService()
project_service = ProjectService(db)

# Initialize article service
article_service = ArticleService(db)

# Initialize session state
state_service.initialize_session_state()

# --------------------------------------------------------------------
# Sidebar: LLM Model Selector
# --------------------------------------------------------------------
debug_mode = st.sidebar.checkbox("Debug Mode", value=False)
st.session_state["selected_model"] = st.sidebar.selectbox("Select Model", list(MODEL_OPTIONS.keys()))

# --------------------------------------------------------------------
# Sidebar: Project Selection
# --------------------------------------------------------------------
# 1) Create a boolean flag to indicate that a new project was just created
if "just_created_project" not in st.session_state:
    st.session_state["just_created_project"] = False

# Build project_names
project_names = ["Create New Project"]
project_list = db.get_all_projects()
if project_list:
    project_names += [f"{p['name']} (ID: {p['id']})" for p in project_list]

# Use a helper function to find the label
def find_project_label(pid):
    for p in project_list:
        if p["id"] == pid:
            return f"{p['name']} (ID: {p['id']})"
    return "Create New Project"

# 2) Figure out which project should be *initially* selected
default_index = 0  # fallback is "Create New Project"

# ONLY force the default_index if we just created a project
if st.session_state["just_created_project"]:
    label_for_pid = find_project_label(st.session_state["project_id"])
    if label_for_pid in project_names:
        default_index = project_names.index(label_for_pid)
    # After we set this once, we turn the flag off so the user can freely select next time
    st.session_state["just_created_project"] = False
    # Notice: we *do not* keep forcing the same default_index on subsequent runs

project_select_label = st.sidebar.selectbox(
    "Select Project",
    project_names,
    index=default_index
)

# 3) Update `project_id` if the user picks something new
if project_select_label == "Create New Project":
    st.session_state["project_id"] = None
else:
    proj_id = int(
        project_select_label.split("ID:")[-1].replace(")", "").strip()
    )
    st.session_state["project_id"] = proj_id

# Now the user will NOT have to click twice, because:
# - Right after creation, we do forcibly set the default once
# - On subsequent runs, if the user chooses something else, we won't force `default_index` again

# --------------------------------------------------------------------
# Sidebar: Article Selection (only if a project is chosen)
# --------------------------------------------------------------------
if "article_id" not in st.session_state:
    st.session_state["article_id"] = None
if st.session_state["project_id"]:
    articles, article_names = article_service.get_article_display_list(st.session_state["project_id"])
    
    # Find the current index for the selected article
    selected_index = 0
    for i, article_name in enumerate(article_names):
        if article_name != "Create New Article" and st.session_state.get("article_id") is not None:
            article_id = int(article_name.split("ID:")[-1].replace(")", "").strip())
            if article_id == st.session_state["article_id"]:
                selected_index = i
                break
    
    selected_article_str = st.sidebar.selectbox(
        "Select Article (within Project)", 
        article_names,
        index=selected_index
    )
    
    article_service.handle_article_selection(selected_article_str)
    
    if st.session_state["article_id"]:
        if st.sidebar.button("Delete Article"):
            db.delete_article_content(st.session_state["article_id"])
            st.success("Article content deleted.")
            st.session_state["article_id"] = None
            st.rerun()



# --------------------------------------------------------------------
# 1) Create / Update Project
# --------------------------------------------------------------------
if st.session_state["project_id"] is None:
    with st.expander("1) Create Project", expanded=True):

        # Show success message if flag is set
        if st.session_state.get("show_project_success", False):
            st.success("Project created successfully! You may select this project from the 'Select Project' dropdown on the top left.")

        # Project creation form
        project_name = st.text_input("Project Name")
        journey_stage = st.selectbox("Consumer Journey Stage", JOURNEY_STAGES)
        category = st.selectbox("Article Category", ARTICLE_CATEGORIES)
        care_areas = st.multiselect("Care Area(s)", CARE_AREAS)
        format_type = st.selectbox("Format Type", FORMAT_TYPES)
        business_category = st.selectbox("Business Category", BUSINESS_CATEGORIES)
        consumer_need = st.selectbox("Consumer Need", CONSUMER_NEEDS)
        tone_of_voice = st.selectbox("Tone of Voice", TONE_OF_VOICE)
        target_audiences = st.multiselect("Target Audience(s)", TARGET_AUDIENCES)
        topic = st.text_input("Topic (Required!)")
        notes = st.text_area("Additional Notes")

        # Create project button and handling
        if st.button("Create Project"):
            notes_json = {
                "freeform_notes": notes,
                "topic": topic
            }
            
            project_data = {
                "name": project_name,
                "care_areas": care_areas,
                "journey_stage": journey_stage,
                "category": category,
                "format_type": format_type,
                "consumer_need": consumer_need,
                "tone_of_voice": tone_of_voice,
                "target_audiences": target_audiences,
                "business_category": business_category,
                "notes": json.dumps(notes_json)
            }
            
            # Create the project and store its ID
            project_id = db.create_project(project_data)
            if project_id:
                st.session_state["project_id"] = project_id
                st.session_state["show_project_success"] = True
                st.session_state["just_created_project"] = True
                st.rerun()

        # Only reset the success flag when a different project is selected
        if st.session_state.get("project_id") and not st.session_state.get("show_project_success", False):
            st.session_state["show_project_success"] = False
    
else:
    with st.expander("1) Update Project", expanded=False):

        selected_project = db.get_project(st.session_state["project_id"])
        selected_project_name = selected_project["name"]
        selected_journey_stage = selected_project["journey_stage"]
        selected_category = selected_project["category"]
        selected_care_areas = json.loads(selected_project["care_areas"])
        selected_consumer_need = selected_project["consumer_need"]
        selected_tone_of_voice = selected_project["tone_of_voice"]
        selected_target_audiences = json.loads(selected_project["target_audiences"])
        selected_format_type = selected_project["format_type"]
        selected_business_category = selected_project["business_category"]
        selected_notes = json.loads(selected_project["notes"])

        # Project creation form
        project_name = st.text_input("Project Name", value=selected_project_name)
        journey_stage = st.selectbox("Consumer Journey Stage", JOURNEY_STAGES, index=JOURNEY_STAGES.index(selected_journey_stage))
        category = st.selectbox("Article Category", ARTICLE_CATEGORIES, index=ARTICLE_CATEGORIES.index(selected_category))
        care_areas = st.multiselect("Care Area(s)", CARE_AREAS, default=selected_care_areas)
        format_type = st.selectbox("Format Type", FORMAT_TYPES, index=FORMAT_TYPES.index(selected_format_type))
        business_category = st.selectbox("Business Category", BUSINESS_CATEGORIES)
        consumer_need = st.selectbox("Consumer Need", CONSUMER_NEEDS, index=CONSUMER_NEEDS.index(selected_consumer_need))
        tone_of_voice = st.selectbox("Tone of Voice", TONE_OF_VOICE, index=TONE_OF_VOICE.index(selected_tone_of_voice))
        target_audiences = st.multiselect("Target Audience(s)", TARGET_AUDIENCES, default=selected_target_audiences)
        topic = st.text_input("Topic (Required!)")
        notes = st.text_area("Additional Notes")

        # Create project button and handling
        if st.button("Update Project"):
            notes_json = {
                "freeform_notes": notes,
                "topic": topic
            }
            
            project_data = {
                "name": project_name,
                "care_areas": care_areas,
                "journey_stage": journey_stage,
                "category": category,
                "format_type": format_type,
                "business_category": business_category,
                "consumer_need": consumer_need,
                "tone_of_voice": tone_of_voice,
                "target_audiences": target_audiences,
                "notes": json.dumps(notes_json)
            }
            
            # Create the project and store its ID
            project_id = db.create_project(project_data)
            st.session_state["project_id"] = project_id
            st.session_state["show_project_success"] = True
            st.rerun()

        # Only reset the success flag when a different project is selected
        if st.session_state.get("project_id") and not st.session_state.get("show_project_success", False):
            st.session_state["show_project_success"] = False


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
                    intent_map = {
                        "0": "Commercial",
                        "1": "Informational",
                        "2": "Navigational",
                        "3": "Transactional",
                    }
                    
                    for idx, rk in enumerate(related_kws):
                        col1, col2 = st.columns([8, 1])
                        intent_value = rk.get("In", "N/A")
                        
                        # Handle multiple intents
                        if intent_value and "," in intent_value:
                            # Split multiple intents and map each one
                            intent_values = intent_value.split(",")
                            intent_descriptions = []
                            for val in intent_values:
                                val = val.strip()
                                intent_descriptions.append(intent_map.get(val, "Unknown"))
                            intent_desc = ", ".join(intent_descriptions)
                        else:
                            # Handle single intent as before
                            intent_desc = intent_map.get(intent_value, "N/A")
                            
                        col1.write(f"- {rk.get('Ph', 'N/A')} (Vol={rk.get('Nq', 'N/A')}, Diff={rk.get('Kd', 'N/A')}, Intent={intent_desc})")
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
Generate a comprehensive article, the article MUST be AT LEAST {desired_article_length} words (this is a strict minimum).

STRUCTURE:
- Create exactly {number_of_sections} sections
- Please use a markdown format when creating the article. This article should be formatted perfectly.
- Maintain consistent depth and detail across all sections. The goal is to create an SEO optimized article that is engaging and informative.
- If there is any missing information, please infer it from context and proceed with generation

CONTEXT:
Topic: {topic_in_notes}
Project Brief: {brief_text}
Keywords to Include (must be used): {kw_str}
1. Journey Stage: {journey_stage}
2. Category: {category}
3. Care Areas: {', '.join(care_areas_list)}
4. Format Type: {format_type}
5. Business Category: {business_cat}
6. Consumer Need: {consumer_need}
7. Tone of Voice: {tone_of_voice}
8. Target Audience: {', '.join(target_audience)}

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

            # Create columns for buttons
            col1, col2 = st.columns([1, 1])

            # Check if there's article content
            article_content = st.session_state.get("drafts_by_article", {}).get(article_id, "")
            if article_content:
                # Always display Refine button if there's article content
                if col1.button("Refine Article"):
                    with st.spinner("Refining article..."):
                        if new_refine_instructions:
                            refine_prompt = f"""
Refine the following article according to these instructions:

INSTRUCTIONS:
{new_refine_instructions}

ORIGINAL ARTICLE:
{article_content}

Return the complete refined article with all improvements applied.
"""
                            refined_text, token_usage, raw_response = query_llm_api(refine_prompt)
                            st.session_state["drafts_by_article"][article_id] = refined_text
                            st.success("Article refined.")
                        else:
                            st.warning("Please enter refine instructions before clicking 'Refine Article'.")

                # Always display Fix Format button if there's article content
                if col2.button("Fix Article Format"):
                    with st.spinner("Fixing article format..."):
                        # Use a simple prompt to fix markdown formatting
                        fix_prompt = """
Fix any markdown formatting issues in the following article. Ensure:
1. Headers use ## and ### format properly
2. Lists are properly formatted
3. No excessive line breaks
4. Consistent spacing and indentation
5. Preserve all content and links

Article:
""" + article_content
                        
                        fixed_text, token_usage, raw_response = query_llm_api(fix_prompt)
                        # Update the article content in session state
                        st.session_state["drafts_by_article"][article_id] = fixed_text
                        
                        # Also update in the database to ensure changes persist
                        try:
                            article_row = db.get_article_content(article_id)
                            if article_row:
                                db.save_article_content(
                                    project_id=st.session_state["project_id"],
                                    article_title=article_row.get("article_title", ""),
                                    article_content=fixed_text,
                                    article_schema=None,
                                    meta_title=article_row.get("meta_title", ""),
                                    meta_description=article_row.get("meta_description", ""),
                                    article_id=article_id
                                )
                        except Exception as e:
                            st.error(f"Error saving formatted article: {str(e)}")
                            
                        st.success("Article format fixed.")
                        st.rerun()  # Force a rerun to show the updated content

# --------------------------------------------------------------------
# 5) Save/Update Final Article (Auto-Saved)
# --------------------------------------------------------------------
if st.session_state["project_id"]:
    with st.expander("5) Final Article (Auto-Saved)"):
        article_id = st.session_state["article_id"]
        if not article_id:
            st.info("No article selected. Generate or select one first.")
        else:
            article_db_row = db.get_article_content(article_id)
            if article_db_row:
                existing_title = article_db_row["article_title"] or ""
                existing_meta_title = article_db_row["meta_title"] or ""
                existing_meta_desc = article_db_row["meta_description"] or ""
                existing_content = article_db_row["article_content"] or ""
                
                # Update session state with database content if not already present
                if "drafts_by_article" not in st.session_state:
                    st.session_state["drafts_by_article"] = {}
                if article_id not in st.session_state["drafts_by_article"]:
                    st.session_state["drafts_by_article"][article_id] = existing_content

                st.write("### Article Title")
                updated_article_title = st.text_input(
                    "Give your article a clear title", 
                    key="final_title", 
                    value=existing_title, 
                    on_change=autosave_final_article
                )

                st.write("### Article Content")
                updated_article_content = st.text_area(
                    "Edit your article content",
                    value=st.session_state["drafts_by_article"][article_id],
                    key="final_article",
                    height=500,
                    on_change=autosave_final_article
                )

                meta_title = st.text_area(
                    "Meta Title",
                    value=existing_meta_title,
                    key="final_meta_title",
                    height=100,
                    on_change=autosave_final_article
                )

                meta_desc = st.text_area(
                    "Meta Description",
                    value=existing_meta_desc,
                    key="final_meta_desc",
                    height=100,
                    on_change=autosave_final_article
                )

                if st.button("Generate Meta Content"):
                    with st.spinner("Generating meta content..."):
                        article_id = st.session_state.get("article_id")
                        article_content = st.session_state.get("final_article", "")
                        article_title = st.session_state.get("final_title", "")
                        
                        success = article_service.generate_article_meta_content(
                            project_id=st.session_state["project_id"],
                            article_id=article_id,
                            article_content=article_content,
                            article_title=article_title
                        )
                        
                        if success:
                            st.success("Meta content generated and saved!")
                            st.rerun()
                        else:
                            st.error("Failed to generate meta content.")

                col1, col2 = st.columns([1, 1])
                if col1.button("Update Final Article"):
                    final_notes_json = {
                        "consumer_need": consumer_need,
                        "tone_of_voice": tone_of_voice,
                        "target_audience": target_audience,
                        "freeform_notes": notes,
                        "topic": topic
                    }
                    patch = {
                        "name": project_name,
                        "care_areas": care_areas,
                        "journey_stage": journey_stage,
                        "category": category,
                        "format_type": format_type,
                        "business_category": business_category,
                        "notes": json.dumps(final_notes_json),
                    }
                    db.update_project_state(st.session_state["project_id"], patch)
                    st.success("Project updated successfully!")
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
                    # print community details
                    print(dict(community))
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
   - Home Page: {community["community_primary_domain"]}
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
