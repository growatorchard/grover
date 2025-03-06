from flask import Flask, request, render_template, jsonify, session, redirect, url_for
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from config.settings import TARGET_AUDIENCES, MODEL_OPTIONS, CARE_AREAS, JOURNEY_STAGES, ARTICLE_CATEGORIES, FORMAT_TYPES, BUSINESS_CATEGORIES, CONSUMER_NEEDS, TONE_OF_VOICE
from database.database_manager import DatabaseManager
from database.community_manager import CommunityManager
from services.llm_service import query_llm_api
from services.semrush_service import get_keyword_suggestions
from services.community_service import get_care_area_details
from services.article_service import ArticleService
from services.project_service import ProjectService
from utils.token_calculator import calculate_token_costs
from utils.json_cleaner import clean_json_response

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# Custom Jinja filters
@app.template_filter('from_json')
def from_json_filter(value):
    """Convert a JSON string to a Python object."""
    try:
        if value:
            return json.loads(value)
        return []
    except:
        return []

@app.template_filter('tojson')
def to_json_filter(value, indent=None):
    """Convert a Python object to a JSON string."""
    return json.dumps(value, indent=indent)


# Initialize database managers
db = DatabaseManager()
comm_manager = CommunityManager()

# Initialize services
project_service = ProjectService(db)
article_service = ArticleService(db)

# Helper function to initialize session if needed
def init_session():
    if 'selected_model' not in session:
        session['selected_model'] = list(MODEL_OPTIONS.keys())[0]
    if 'project_id' not in session:
        session['project_id'] = None
    if 'article_id' not in session:
        session['article_id'] = None
    if 'is_creating_article_settings' not in session:
        session['is_creating_article_settings'] = False
    if 'is_editing_article' not in session:
        session['is_editing_article'] = False
    if 'token_usage_history' not in session:
        session['token_usage_history'] = []
    if 'drafts_by_article' not in session:
        session['drafts_by_article'] = {}

@app.route('/')
def index():
    init_session()
    
    # Get data needed for the main page
    projects = db.get_all_projects()
    selected_project = None
    articles = []
    
    if session.get('project_id'):
        selected_project = db.get_project(session['project_id'])
        articles = article_service.get_article_display_list(session['project_id'])
    
    return render_template('index.html', 
                          projects=projects,
                          selected_project=selected_project,
                          articles=articles,
                          models=MODEL_OPTIONS,
                          selected_model=session.get('selected_model'),
                          target_audiences=TARGET_AUDIENCES,
                          journey_stages=JOURNEY_STAGES,
                          article_categories=ARTICLE_CATEGORIES,
                          care_areas=CARE_AREAS,
                          format_types=FORMAT_TYPES,
                          business_categories=BUSINESS_CATEGORIES,
                          consumer_needs=CONSUMER_NEEDS,
                          tone_of_voice=TONE_OF_VOICE)

@app.route('/set_model', methods=['POST'])
def set_model():
    model = request.form.get('model')
    if model in MODEL_OPTIONS:
        session['selected_model'] = model
    return redirect(url_for('index'))

@app.route('/toggle_debug', methods=['POST'])
def toggle_debug():
    session['debug_mode'] = not session.get('debug_mode', False)
    return jsonify({'debug_mode': session.get('debug_mode')})

# Project Routes
@app.route('/projects/select', methods=['POST'])
def select_project():
    project_id = request.form.get('project_id')
    if project_id == 'new':
        session['project_id'] = None
    else:
        session['project_id'] = int(project_id) if project_id else None
    session['article_id'] = None  # Reset article selection
    return redirect(url_for('index'))

@app.route('/projects/create', methods=['POST'])
def create_project():
    project_data = {
        'name': request.form.get('project_name'),
        'care_areas': request.form.getlist('care_areas'),
        'journey_stage': request.form.get('journey_stage'),
        'category': request.form.get('category'),
        'format_type': request.form.get('format_type'),
        'consumer_need': request.form.get('consumer_need'),
        'tone_of_voice': request.form.get('tone_of_voice'),
        'target_audiences': request.form.getlist('target_audiences'),
        'business_category': request.form.get('business_category'),
        'topic': request.form.get('topic'),
    }
    
    new_id = db.create_project(project_data)
    if new_id:
        session['project_id'] = new_id
    
    return redirect(url_for('index'))

@app.route('/projects/update', methods=['POST'])
def update_project():
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    project_data = {
        'name': request.form.get('project_name'),
        'care_areas': request.form.getlist('care_areas'),
        'journey_stage': request.form.get('journey_stage'),
        'category': request.form.get('category'),
        'format_type': request.form.get('format_type'),
        'business_category': request.form.get('business_category'),
        'consumer_need': request.form.get('consumer_need'),
        'tone_of_voice': request.form.get('tone_of_voice'),
        'target_audiences': request.form.getlist('target_audiences'),
        'topic': request.form.get('topic'),
    }
    
    updated_id = db.update_project_state(project_id, project_data)
    return redirect(url_for('index'))

@app.route('/projects/delete', methods=['POST'])
def delete_project():
    project_id = session.get('project_id')
    if project_id:
        db.delete_project(project_id)
        session['project_id'] = None
        session['article_id'] = None
    return redirect(url_for('index'))

# Keyword Routes
@app.route('/keywords/list')
def list_keywords():
    project_id = session.get('project_id')
    print(project_id)
    if not project_id:
        return jsonify([])
    
    keywords = db.get_project_keywords(project_id)
    keywords = [dict(k) for k in keywords] if keywords else []

    return jsonify(keywords)

@app.route('/keywords/add', methods=['POST'])
def add_keyword():
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    keyword = request.form.get('keyword')
    search_volume = request.form.get('search_volume')
    kw_difficulty = request.form.get('keyword_difficulty')
    
    if keyword:
        db.add_keyword(project_id, keyword.strip(), search_volume, None, kw_difficulty)
        return jsonify({'success': True})
    return jsonify({'error': 'No keyword provided'}), 400

@app.route('/keywords/delete', methods=['POST'])
def delete_keyword():
    keyword_id = request.form.get('keyword_id')
    if keyword_id:
        db.delete_keyword(keyword_id)
        return jsonify({'success': True})
    return jsonify({'error': 'No keyword ID provided'}), 400

@app.route('/keywords/research', methods=['POST'])
def research_keywords():
    keyword = request.form.get('keyword')
    if not keyword:
        return jsonify({'error': 'No keyword provided'}), 400
    
    debug_mode = session.get('debug_mode', False)
    data = get_keyword_suggestions(keyword.strip(), debug_mode=debug_mode)
    return jsonify(data)

# Article Routes
@app.route('/articles/select', methods=['POST'])
def select_article():
    article_id = request.form.get('article_id')
    if article_id == 'new':
        session['article_id'] = None
        session['is_creating_article_settings'] = True
    else:
        session['article_id'] = int(article_id) if article_id else None
    return redirect(url_for('index'))

@app.route('/articles/create', methods=['POST'])
def create_article_settings():
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    article_brief = request.form.get('article_brief')
    article_length = int(request.form.get('article_length', 1000))
    article_sections = int(request.form.get('article_sections', 5))
    
    try:
        new_article_id = db.create_article_content(
            project_id=project_id,
            article_brief=article_brief,
            article_length=article_length,
            article_sections=article_sections,
        )
        session['article_id'] = new_article_id
        session['is_creating_article_settings'] = False
        session['is_editing_article'] = True
        return jsonify({'success': True, 'article_id': new_article_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/articles/update', methods=['POST'])
def update_article_settings():
    article_id = session.get('article_id')
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    article_brief = request.form.get('article_brief')
    article_length = int(request.form.get('article_length', 1000))
    article_sections = int(request.form.get('article_sections', 5))
    
    try:
        db.update_article_content(
            article_id=article_id,
            article_brief=article_brief,
            article_length=article_length,
            article_sections=article_sections,
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/articles/generate_title_outline', methods=['POST'])
def generate_article_title_outline():
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    # Get project details and keywords
    db_kws = db.get_project_keywords(project_id)
    keywords = [k["keyword"] for k in db_kws] if db_kws else []
    kw_str = ", ".join(keywords) if keywords else "(none)"
    pinfo = db.get_project(project_id)
    
    # Build context for LLM request
    article_brief = pinfo.get("article_brief", "")
    journey_stage = pinfo.get("journey_stage", "")
    category = pinfo.get("category", "")
    care_areas_list = json.loads(pinfo.get("care_areas", "[]"))
    format_type = pinfo.get("format_type", "")
    business_cat = pinfo.get("business_category", "")
    consumer_need = pinfo.get("consumer_need", "")
    tone_of_voice = pinfo.get("tone_of_voice", "")
    target_audiences = json.loads(pinfo.get("target_audiences", "[]"))
    topic = pinfo.get("topic", "")
    
    community_details_text = ""
    context_msg = f"""
MAIN TOPIC: {topic}
REQUIRED KEYWORDS (must be used):
{kw_str}
ARTICLE SPECIFICATIONS:
1. Journey Stage: {journey_stage}
2. Category: {category}
3. Care Areas: {', '.join(care_areas_list)}
4. Format Type: {format_type}
5. Business Category: {business_cat}
6. Consumer Need: {consumer_need}
7. Tone of Voice: {tone_of_voice}
8. Target Audiences: {', '.join(target_audiences)}
ADDITIONAL CONTEXT:

{community_details_text}
"""
    full_article_prompt = f"""
Generate a comprehensive article title and outline based on the following information:
ARTICLE BRIEF:
{context_msg}
Return ONLY a JSON object with this structure:
{{
    "article_title": "The catchy title for the article",
    "article_outline": "H1/Title, H2, H3, etc.",
}}
"""
    response, token_usage, raw_response = query_llm_api(full_article_prompt)
    
    # Track token usage
    token_usage_history = session.get('token_usage_history', [])
    token_usage_history.append({
        "iteration": 1,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "usage": token_usage,
    })
    session['token_usage_history'] = token_usage_history
    costs = calculate_token_costs(token_usage)
    
    # Parse response
    try:
        response_data = clean_json_response(response)
        article_title = response_data.get("article_title", "")
        article_outline = response_data.get("article_outline", "")
        
        return jsonify({
            'article_title': article_title,
            'article_outline': article_outline,
            'token_usage': token_usage,
            'costs': costs,
            'raw_response': raw_response if session.get('debug_mode') else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/articles/save', methods=['POST'])
def save_article_content():
    project_id = session.get('project_id')
    article_id = session.get('article_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    article_title = request.form.get('article_title', '')
    article_content = request.form.get('article_content', '')
    meta_title = request.form.get('meta_title', '')
    meta_description = request.form.get('meta_description', '')
    
    try:
        if article_id:
            # Update existing article
            saved_id = db.save_article_content(
                project_id=project_id,
                article_title=article_title,
                article_content=article_content,
                article_schema=None,
                meta_title=meta_title,
                meta_description=meta_description,
                article_id=article_id
            )
        else:
            # Create new article
            saved_id = db.save_article_content(
                project_id=project_id,
                article_title=article_title,
                article_content=article_content,
                article_schema=None,
                meta_title=meta_title,
                meta_description=meta_description
            )
            session['article_id'] = saved_id
        
        # Update drafts in session
        drafts = session.get('drafts_by_article', {})
        drafts[str(saved_id)] = article_content
        session['drafts_by_article'] = drafts
        
        return jsonify({'success': True, 'article_id': saved_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/articles/delete', methods=['POST'])
def delete_article():
    article_id = request.form.get('article_id') or session.get('article_id')
    if article_id:
        db.delete_article_content(article_id)
        session['article_id'] = None
        return jsonify({'success': True})
    return jsonify({'error': 'No article ID provided'}), 400

@app.route('/articles/refine', methods=['POST'])
def refine_article():
    article_id = session.get('article_id')
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    refine_instructions = request.form.get('refine_instructions', '')
    article_content = request.form.get('article_content', '')
    
    if not refine_instructions:
        return jsonify({'error': 'No refine instructions provided'}), 400
    
    refine_prompt = f"""
Refine the following article according to these instructions:

INSTRUCTIONS:
{refine_instructions}

ORIGINAL ARTICLE:
{article_content}

Return the complete refined article with all improvements applied.
"""
    refined_text, token_usage, raw_response = query_llm_api(refine_prompt)
    
    # Track token usage
    token_usage_history = session.get('token_usage_history', [])
    token_usage_history.append({
        "iteration": 1,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "usage": token_usage,
    })
    session['token_usage_history'] = token_usage_history
    costs = calculate_token_costs(token_usage)
    
    # Update drafts in session
    drafts = session.get('drafts_by_article', {})
    drafts[str(article_id)] = refined_text
    session['drafts_by_article'] = drafts
    
    return jsonify({
        'refined_text': refined_text,
        'token_usage': token_usage,
        'costs': costs,
        'raw_response': raw_response if session.get('debug_mode') else None
    })

@app.route('/articles/fix_format', methods=['POST'])
def fix_article_format():
    article_id = session.get('article_id')
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    article_content = request.form.get('article_content', '')
    
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
    
    # Track token usage
    token_usage_history = session.get('token_usage_history', [])
    token_usage_history.append({
        "iteration": 1,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "usage": token_usage,
    })
    session['token_usage_history'] = token_usage_history
    
    # Update drafts in session
    drafts = session.get('drafts_by_article', {})
    drafts[str(article_id)] = fixed_text
    session['drafts_by_article'] = drafts
    
    # Save to database
    try:
        article_row = db.get_article_content(article_id)
        if article_row:
            db.save_article_content(
                project_id=session.get('project_id'),
                article_title=article_row.get('article_title', ''),
                article_content=fixed_text,
                article_schema=None,
                meta_title=article_row.get('meta_title', ''),
                meta_description=article_row.get('meta_description', ''),
                article_id=article_id
            )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({
        'fixed_text': fixed_text,
        'token_usage': token_usage,
        'raw_response': raw_response if session.get('debug_mode') else None
    })

@app.route('/articles/generate_meta', methods=['POST'])
def generate_meta_content():
    article_id = session.get('article_id')
    project_id = session.get('project_id')
    if not article_id or not project_id:
        return jsonify({'error': 'No article or project selected'}), 400
    
    article_content = request.form.get('article_content', '')
    article_title = request.form.get('article_title', '')
    
    success = article_service.generate_article_meta_content(
        project_id=project_id,
        article_id=article_id,
        article_content=article_content,
        article_title=article_title
    )
    
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to generate meta content'}), 500

@app.route('/articles/community_revision', methods=['POST'])
def generate_community_revision():
    article_id = session.get('article_id')
    project_id = session.get('project_id')
    if not article_id or not project_id:
        return jsonify({'error': 'No article or project selected'}), 400
    
    community_id = request.form.get('community_id')
    if not community_id:
        return jsonify({'error': 'No community selected'}), 400
    
    article_row = db.get_article_content(article_id)
    if not article_row:
        return jsonify({'error': 'Article not found'}), 404
    
    original_article = article_row['article_content']
    community = comm_manager.get_community(int(community_id))
    
    aliases = comm_manager.get_aliases(int(community_id))
    alias_list = [alias["alias"] for alias in aliases] if aliases else []
    aliases_text = ", ".join(alias_list) if alias_list else "None"
    care_area_details_text = get_care_area_details(comm_manager, int(community_id))
    
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
- Project Details: {json.loads(db.get_project(project_id)['notes'])}

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
    
    revised_article_text, token_usage, raw_response = query_llm_api(revision_prompt)
    costs = calculate_token_costs(token_usage)
    
    new_rev_title = f"{article_row['article_title']} - Community Revision for {community['community_name']}"
    
    try:
        new_article_id = db.save_article_content(
            project_id=project_id,
            article_title=new_rev_title,
            article_content=revised_article_text,
            article_schema=None,
            meta_title=article_row.get("meta_title", ""),
            meta_description=article_row.get("meta_description", ""),
        )
        
        # Update session
        session['article_id'] = new_article_id
        
        # Update drafts in session
        drafts = session.get('drafts_by_article', {})
        drafts[str(new_article_id)] = revised_article_text
        session['drafts_by_article'] = drafts
        
        return jsonify({
            'success': True,
            'article_id': new_article_id,
            'revised_text': revised_article_text,
            'token_usage': token_usage,
            'costs': costs,
            'raw_response': raw_response if session.get('debug_mode') else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/communities/list')
def list_communities():
    communities = comm_manager.get_communities()
    return jsonify(communities)

@app.route('/communities/<int:community_id>')
def get_community_details(community_id):
    community = comm_manager.get_community(community_id)
    aliases = comm_manager.get_aliases(community_id)
    care_area_details = get_care_area_details(comm_manager, community_id)
    
    return jsonify({
        'community': community,
        'aliases': aliases,
        'care_area_details': care_area_details
    })

if __name__ == '__main__':
    app.run(debug=True)