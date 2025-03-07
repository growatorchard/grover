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
    if 'community_article_id' not in session:
        session['community_article_id'] = None
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
    current_article = None
    community_articles = []
    current_community_article = None
    
    if session.get('project_id'):
        selected_project = db.get_project(session['project_id'])
        
        # Get all articles for the project
        try:
            articles = db.get_all_articles_for_project(session['project_id'])
        except Exception as e:
            app.logger.error(f"Error fetching articles: {str(e)}")
            articles = []
        
        # Get the current article if one is selected
        if session.get('article_id'):
            try:
                current_article = db.get_article_content(session['article_id'])
                
                # Get community articles for this base article
                try:
                    community_articles = db.get_community_articles_for_base_article(session['article_id'])
                except Exception as e:
                    app.logger.error(f"Error fetching community articles: {str(e)}")
                    community_articles = []
                
                # Get current community article if one is selected
                if session.get('community_article_id'):
                    try:
                        current_community_article = db.get_community_article(session['community_article_id'])
                    except Exception as e:
                        app.logger.error(f"Error fetching community article: {str(e)}")
                        session['community_article_id'] = None
            except Exception as e:
                app.logger.error(f"Error fetching article: {str(e)}")
                session['article_id'] = None
    
    return render_template('index.html', 
                          projects=projects,
                          selected_project=selected_project,
                          articles=articles,
                          current_article=current_article,
                          community_articles=community_articles,
                          current_community_article=current_community_article,
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
        session['article_id'] = None
        session['community_article_id'] = None
    
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
        # Clear article selection to show the creation form
        session['article_id'] = None
    else:
        # Select existing article
        try:
            article_id = int(article_id) if article_id else None
            session['article_id'] = article_id
        except (ValueError, TypeError):
            session['article_id'] = None
    
    return redirect(url_for('index'))

@app.route('/articles/create', methods=['POST'])
def create_article_settings():
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    session['article_id'] = None
    session['community_article_id'] = None
    
    article_length = int(request.form.get('article_length', 1000))
    article_sections = int(request.form.get('article_sections', 5))
    
    try:
        # Create the article content entry
        new_article_id = db.create_article_content(
            project_id=project_id,
            article_length=article_length,
            article_sections=article_sections,
        )
        
        # Set as current article
        session['article_id'] = new_article_id
        
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Error creating article: {str(e)}")
        return f"Error creating article: {str(e)}", 500
    
@app.route('/articles/list')
def list_articles():
    """Get all articles for the current project."""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify([])
    
    # ERROR in app: Error fetching articles: No item with that key
    print(project_id)
    
    try:
        articles = db.get_all_articles_for_project(project_id)
        
        # Format the articles for display
        formatted_articles = []
        for article in articles:
            formatted_articles.append({
                'id': article['id'],
                'article_title': article['article_title'],
                'article_outline': article['article_outline'],
                'article_length': article['article_length'],
                'article_sections': article['article_sections'],
                'created_at': article['created_at'].isoformat() if hasattr(article['created_at'], 'isoformat') else article['created_at'],
                'updated_at': article['updated_at'].isoformat() if hasattr(article['updated_at'], 'isoformat') else article['updated_at']
            })
        
        return jsonify(formatted_articles)
    except Exception as e:
        app.logger.error(f"Error fetching articles: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/articles/update', methods=['POST'])
def update_article_settings():
    """Update all article settings including title and brief."""
    article_id = session.get('article_id')
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    # Get all form data
    article_title = request.form.get('article_title', '')
    article_outline = request.form.get('article_outline', '')
    article_length = int(request.form.get('article_length', 1000))
    article_sections = int(request.form.get('article_sections', 5))
    
    try:
        db.save_article_content(
            project_id=session.get('project_id'),
            article_title=article_title,
            article_outline=article_outline,
            article_length=article_length,
            article_sections=article_sections,
            article_id=article_id
        )
        
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Error updating article: {str(e)}")
        return f"Error updating article: {str(e)}", 500
    
@app.route('/articles/get_current')
def get_current_article():
    """Get the currently selected article."""
    article_id = session.get('article_id')
    if not article_id:
        return jsonify(None)
    
    try:
        article = db.get_article_content(article_id)
        if not article:
            return jsonify(None)
        
        # Convert to dict if needed and format dates
        article_dict = dict(article)
        if 'created_at' in article_dict and hasattr(article_dict['created_at'], 'isoformat'):
            article_dict['created_at'] = article_dict['created_at'].isoformat()
        if 'updated_at' in article_dict and hasattr(article_dict['updated_at'], 'isoformat'):
            article_dict['updated_at'] = article_dict['updated_at'].isoformat()
            
        return jsonify(article_dict)
    except Exception as e:
        app.logger.error(f"Error fetching current article: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/articles/generate_title_outline', methods=['POST'])
def generate_article_title_outline():
    llm_model = session.get('selected_model')
    project_id = session.get('project_id')
    article_id = session.get('article_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    # Get project details and keywords
    db_kws = db.get_project_keywords(project_id)
    keywords = [k["keyword"] for k in db_kws] if db_kws else []
    kw_str = ", ".join(keywords) if keywords else "(none)"
    pinfo = db.get_project(project_id)
    ainfo = db.get_article_content(article_id)
    
    # Build context for LLM request
    journey_stage = pinfo["journey_stage"]
    category = pinfo["category"]
    care_areas_list = json.loads(pinfo["care_areas"])
    format_type = pinfo["format_type"]
    business_cat = pinfo["business_category"]
    consumer_need = pinfo["consumer_need"]
    tone_of_voice = pinfo["tone_of_voice"]
    target_audiences = json.loads(pinfo["target_audiences"])
    topic = pinfo["topic"]

    article_outline = ainfo["article_outline"]
    article_desired_word_count = ainfo["article_length"]
    article_desired_sections = ainfo["article_sections"]
    
    
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
ARTICLE BRIEF:
{article_outline}

DESIRED WORD COUNT: {article_desired_word_count}
DESIRED SECTIONS: {article_desired_sections}
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
    response, token_usage, raw_response = query_llm_api(llm_model, full_article_prompt)
    
    # Track token usage
    token_usage_history = session.get('token_usage_history', [])
    token_usage_history.append({
        "iteration": 1,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "usage": token_usage,
    })
    session['token_usage_history'] = token_usage_history
    # costs = calculate_token_costs(token_usage)
    costs = 1
    
    # Parse response
    try:
        # First check if response_data is a string and try to parse it
        response_data = clean_json_response(response)
        
        # Debug information
        print("Type of response_data:", type(response_data))
        print("Content of response_data:", response_data)
        
        # If response_data is a string, try to parse it as JSON
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError:
                raise ValueError("Failed to parse response as JSON")
        
        # Now access the fields
        article_title = response_data.get("article_title", "")
        article_outline = response_data.get("article_outline", "")
        
        if not article_title or not article_outline:
            raise ValueError("Response missing required fields: article_title and article_outline")
        
        return jsonify({
            'article_title': article_title,
            'article_outline': article_outline,
            'token_usage': token_usage,
            'costs': costs,
            'raw_response': raw_response if session.get('debug_mode') else None
        })
    except Exception as e:
        print("Error parsing response:", str(e))
        print("Raw response:", response)
        return jsonify({'error': str(e)}), 500

@app.route('/articles/save_title_outline', methods=['POST'])
def save_article_title_outline():
    """Save the article outline and title"""
    project_id = session.get('project_id')
    article_id = session.get('article_id')
    if not project_id or not article_id:
        return jsonify({'error': 'No project or article selected'}), 400

    article_title = request.form.get('article_title', '')
    article_outline = request.form.get('article_outline', '')

    try:
        saved_id = db.save_article_title_outline(
            article_title=article_title,
            article_outline=article_outline,
            article_id=article_id
        )
        
        return jsonify({'success': True, 'article_id': saved_id})
    except Exception as e:
        app.logger.error(f"Error saving article title and outline: {str(e)}")
        return jsonify({'error': str(e)}), 500

    
@app.route('/articles/save_article_post_content', methods=['POST'])
def save_article_post_content():
    """Save the article post content"""
    project_id = session.get('project_id')
    article_id = session.get('article_id')
    if not project_id or not article_id:
        return jsonify({'error': 'No project or article selected'}), 400

    article_content = request.form.get('article_content', '')
    
    try:
        saved_id = db.save_article_post_content(
            article_content=article_content,
            article_id=article_id
        )
        
        return jsonify({'success': True, 'article_id': saved_id})
    except Exception as e:
        app.logger.error(f"Error saving article: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/articles/delete', methods=['POST'])
def delete_article():
    article_id = request.form.get('article_id') or session.get('article_id')
    if article_id:
        db.delete_article_content(article_id)
        session['article_id'] = None
        return jsonify({'success': True})
    return jsonify({'error': 'No article ID provided'}), 400

@app.route('/articles/generate_content', methods=['POST'])
def generate_article_content():
    llm_model = session.get('selected_model')
    project_id = session.get('project_id')
    article_id = session.get('article_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    # Get project details and keywords
    db_kws = db.get_project_keywords(project_id)
    keywords = [k["keyword"] for k in db_kws] if db_kws else []
    kw_str = ", ".join(keywords) if keywords else "(none)"
    pinfo = db.get_project(project_id)
    ainfo = db.get_article_content(article_id)
    
    # Build context for LLM request
    journey_stage = pinfo["journey_stage"]
    category = pinfo["category"]
    care_areas_list = json.loads(pinfo["care_areas"])
    format_type = pinfo["format_type"]
    business_cat = pinfo["business_category"]
    consumer_need = pinfo["consumer_need"]
    tone_of_voice = pinfo["tone_of_voice"]
    target_audiences = json.loads(pinfo["target_audiences"])
    topic = pinfo["topic"]

    article_outline = ainfo["article_outline"]
    article_desired_word_count = ainfo["article_length"]
    article_title = ainfo["article_title"]
    
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

ARTICLE TITLE: {article_title}

ARTICLE OUTLINE: {article_outline}

DESIRED WORD COUNT: {article_desired_word_count}

Please generate a complete article based on the above information. The article should be well-structured, informative, and engaging, with a focus on the target audience and SEO keywords provided.

"""
    
    full_article_prompt = f"""
Generate a complete article based on the following information:
ARTICLE BRIEF:
{context_msg}
Return ONLY the article content text.
"""
    response, token_usage, raw_response = query_llm_api(llm_model, full_article_prompt)

    # Track token usage
    token_usage_history = session.get('token_usage_history', [])
    token_usage_history.append({
        "iteration": 1,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "usage": token_usage,
    })
    session['token_usage_history'] = token_usage_history
    # costs = calculate_token_costs(token_usage)
    costs = 1

    print("Response:", response)

    return jsonify({
        'article_content': response,
        'token_usage': token_usage,
        'costs': costs,
        'raw_response': raw_response if session.get('debug_mode') else None
    })

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
    # costs = calculate_token_costs(token_usage)
    costs = 1

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

# Community Articles
@app.route('/articles/community_revision', methods=['POST'])
def generate_community_revision():
    article_id = session.get('article_id')
    project_id = session.get('project_id')
    if not article_id or not project_id:
        return jsonify({'error': 'No article or project selected'}), 400
    
    community_id = request.form.get('community_id')
    if not community_id:
        return jsonify({'error': 'No community selected'}), 400
    
    pinfo = db.get_project(project_id)
    if not pinfo:
        return jsonify({'error': 'Project not found'}), 404

    ainfo = db.get_article_content(article_id)
    if not ainfo:
        return jsonify({'error': 'Article not found'}), 404
    
    db_kws = db.get_project_keywords(project_id)
    keywords = [k["keyword"] for k in db_kws] if db_kws else []
    kw_str = ", ".join(keywords) if keywords else "(none)"

    # Build context for LLM request
    journey_stage = pinfo["journey_stage"]
    category = pinfo["category"]
    care_areas_list = json.loads(pinfo["care_areas"])
    format_type = pinfo["format_type"]
    business_cat = pinfo["business_category"]
    consumer_need = pinfo["consumer_need"]
    tone_of_voice = pinfo["tone_of_voice"]
    target_audiences = json.loads(pinfo["target_audiences"])
    topic = pinfo["topic"]

    article_content = ainfo["article_content"]
    article_desired_word_count = ainfo["article_length"]
    article_title = ainfo["article_title"]

    community = comm_manager.get_community(int(community_id))
    
    aliases = comm_manager.get_aliases(int(community_id))
    alias_list = [alias["alias"] for alias in aliases] if aliases else []
    aliases_text = ", ".join(alias_list) if alias_list else "None"

    selected_care_area_names = []
    for area in care_areas_list:
        # Split by comma in case some items contain multiple care areas
        if ',' in area:
            selected_care_area_names.extend([a.strip() for a in area.split(',')])
        else:
            selected_care_area_names.append(area.strip())
    
    # Validate if the community has all the selected care areas
    community_care_areas = comm_manager.get_care_areas(int(community_id))
    community_care_area_names = [dict(area).get('care_area', '').lower() for area in community_care_areas]
    
    missing_care_areas = []
    for care_area in selected_care_area_names:
        if care_area.lower() not in community_care_area_names:
            missing_care_areas.append(care_area)
    
    if missing_care_areas:
        missing_areas_str = ", ".join(missing_care_areas)
        return jsonify({
            'error': f"One or more of the selected care areas for the project do not exist for the selected community: {missing_areas_str}. Please select a different community that offers these care areas or update your project settings."
        }), 400
    
    # Get details for only the selected care areas
    care_area_details_text = get_care_area_details(comm_manager, int(community_id), selected_care_area_names)
    
    community_details_text = f"""
- Name: {community["community_name"]}
- Primary Domain: {community["community_primary_domain"]}
- Location: {community["city"]}, {community["state"]}, {community["address"]}, {community["zip_code"]}
- Aliases: {aliases_text}
- Page URLs:
    - Home Page: {community["community_primary_domain"]}
    - About Page: {community["about_page"]}
    - Contact Page: {community["contact_page"]}
    - Floor Plan Page: {community["floor_plan_page"]}
    - Dining Page: {community["dining_page"]}
    - Gallery Page: {community["gallery_page"]}
    - Health & Wellness Page: {community["health_wellness_page"]}

Care areas, amenities, and services available at this community:
{care_area_details_text}
"""
    
    revision_prompt = f"""
Please help me update the following article to be tailored to the following senior living community while maintaining the original article's core message, structure, quality, and SEO optimization. When using examples of offerings/services/amenities ensure they are actually available at the community. If something is not explicitly listed in the community details, you should not imply or state that it is available.

MAIN TOPIC: {topic}
REQUIRED KEYWORDS (must be used):
{kw_str}
ARTICLE SPECIFICATIONS:
1. Journey Stage: {journey_stage}
2. Category: {category}
3. Care Areas: {', '.join(selected_care_area_names)}
4. Format Type: {format_type}
5. Business Category: {business_cat}
6. Consumer Need: {consumer_need}
7. Tone of Voice: {tone_of_voice}
8. Target Audiences: {', '.join(target_audiences)}
9. Desired Word Count: {article_desired_word_count}

Current Article Title: {article_title}
Current Article Content: {article_content}

Here are the details for the senior living community:
{community_details_text}

REVISION REQUIREMENTS:
1. Incorporate community-specific details naturally throughout the article. When using community-specific details, ensure they are accurate and from the details provided above. Do not imply or state any information not provided.
    Examples: community name, location, amenities, services, care areas, etc.
2. Ensure the article is relevant and engaging for the target audience of this community.
3. Include relevant internal/contextual links using markdown format [text](url).
    Example: [Learn more about our dining options](https://community.com/dining)
    Example: [Explore our floor plans](https://community.com/floor-plans)

Please return only the revised article text.
"""
    
    response, token_usage, raw_response = query_llm_api(session.get('selected_model'), revision_prompt)
    costs = 1
    
    print("Response:", response)

    return jsonify({
        'article_content': response,
        'token_usage': token_usage,
        'costs': costs,
        'raw_response': raw_response if session.get('debug_mode') else None
    })

@app.route('/communities/list')
def list_communities():
    communities = comm_manager.get_communities()
    communities = [dict(c) for c in communities] if communities else []
    return jsonify(communities)

@app.route('/communities/<int:community_id>')
def get_community_details(community_id):
    community = comm_manager.get_community(community_id)
    aliases = comm_manager.get_aliases(community_id)
    
    # Get project care areas from the current project if one is selected
    project_id = session.get('project_id')
    selected_care_area_names = []
    
    if project_id:
        try:
            pinfo = db.get_project(project_id)
            print(f"Project Info: {dict(pinfo)}")
            
            # CRITICAL FIX - Directly extract Skilled Nursing from the care_areas field
            care_areas_raw = pinfo.get("care_areas", "")
            print(f"Raw care_areas: {care_areas_raw!r}")
            
            # Try a very direct approach - using string searching instead of JSON parsing
            if "Skilled Nursing" in care_areas_raw:
                print("Found 'Skilled Nursing' in care_areas string!")
                selected_care_area_names.append("Skilled Nursing")
            
            # Also try JSON parsing as a backup
            try:
                parsed_list = json.loads(care_areas_raw)
                print(f"Parsed JSON: {parsed_list}")
                
                if isinstance(parsed_list, list):
                    for item in parsed_list:
                        if item not in selected_care_area_names:
                            selected_care_area_names.append(item)
                            print(f"Added {item} from JSON parsing")
            except Exception as e:
                print(f"JSON parsing error: {str(e)}")
        except Exception as e:
            print(f"Error getting project care areas: {str(e)}")
    
    print(f"Final selected_care_area_names: {selected_care_area_names}")
    
    # Get community care areas
    community_care_areas = comm_manager.get_care_areas(community_id)
    community_care_area_names = [dict(area).get('care_area', '') for area in community_care_areas]
    
    # Check for missing care areas
    missing_care_areas = []
    for project_area in selected_care_area_names:
        print(f"Checking care area: {project_area}")
        if not any(project_area.lower() == community_area.lower() for community_area in community_care_area_names):
            print(f"Missing care area: {project_area}")
            missing_care_areas.append(project_area)
    
    print(f"Community care area names: {community_care_area_names}")
    print(f"Missing care areas: {missing_care_areas}")
    
    # Get care area details
    care_area_details = get_care_area_details(comm_manager, community_id, selected_care_area_names)
    
    response_data = {
        'community': dict(community),
        'aliases': [dict(a) for a in aliases] if aliases else [],
        'care_area_details': care_area_details,
        'community_care_areas': community_care_area_names,
        'missing_care_areas': missing_care_areas,
        'selected_care_areas': selected_care_area_names
    }
    
    return jsonify(response_data)


@app.route('/articles/save_community_post_content', methods=['POST'])
def save_community_post_content():
    article_id = session.get('article_id')
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    community_id = request.form.get('community_id')
    if not community_id:
        return jsonify({'error': 'No community selected'}), 400
    
    article_content = request.form.get('article_content', '')
    
    try:
        db.save_community_post_content(article_id, community_id, article_content)
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error saving community article: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/community_articles/select', methods=['POST'])
def select_community_article():
    community_article_id = request.form.get('community_article_id')
    
    if community_article_id == 'new':
        # Clear community article selection to show the creation form
        session['community_article_id'] = None
        return redirect(url_for('index'))
    else:
        # Select existing community article
        try:
            community_article_id = int(community_article_id) if community_article_id else None
            session['community_article_id'] = community_article_id
        except (ValueError, TypeError):
            session['community_article_id'] = None
    
    return redirect(url_for('index'))

@app.route('/community_articles/list')
def list_community_articles():
    """Get all community articles for the current base article."""
    base_article_id = request.args.get('base_article_id') or session.get('article_id')
    if not base_article_id:
        return jsonify([])
    
    try:
        community_articles = db.get_community_articles_for_base_article(base_article_id)
        
        # Format the community articles for display
        formatted_articles = []
        for article in community_articles:
            formatted_articles.append({
                'id': article['id'],
                'community_id': article['community_id'],
                'community_name': article['community_name'],  # This will come from joining with the communities table
                'article_title': article['article_title'],
                'created_at': article['created_at'].isoformat() if hasattr(article['created_at'], 'isoformat') else article['created_at'],
                'updated_at': article['updated_at'].isoformat() if hasattr(article['updated_at'], 'isoformat') else article['updated_at']
            })
        
        return jsonify(formatted_articles)
    except Exception as e:
        app.logger.error(f"Error fetching community articles: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/community_articles/create', methods=['POST'])
def create_community_article():
    project_id = session.get('project_id')
    base_article_id = session.get('article_id')
    if not project_id or not base_article_id:
        return jsonify({'error': 'No project or base article selected'}), 400
    
    community_id = request.form.get('community_id')
    if not community_id:
        return jsonify({'error': 'No community selected'}), 400
    
    try:
        # Check if article exists for this community
        existing = db.get_community_article_by_community(base_article_id, community_id)
        if existing:
            session['community_article_id'] = existing['id']
            return jsonify({'success': True, 'article_id': existing['id'], 'message': 'Existing article selected'})
        
        # Get base article details
        base_article = db.get_article_content(base_article_id)
        
        # Create new community article
        new_article_id = db.create_community_article(
            project_id=project_id,
            base_article_id=base_article_id,
            community_id=community_id,
            article_title=base_article['article_title']
        )
        
        session['community_article_id'] = new_article_id
        return jsonify({'success': True, 'article_id': new_article_id})
    except Exception as e:
        app.logger.error(f"Error creating community article: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/community_articles/delete', methods=['POST'])
def delete_community_article():
    community_article_id = request.form.get('community_article_id') or session.get('community_article_id')
    if community_article_id:
        try:
            db.delete_community_article(community_article_id)
            session['community_article_id'] = None
            return jsonify({'success': True})
        except Exception as e:
            app.logger.error(f"Error deleting community article: {str(e)}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'No community article ID provided'}), 400

@app.route('/community_articles/get_current')
def get_current_community_article():
    """Get the currently selected community article."""
    community_article_id = session.get('community_article_id')
    if not community_article_id:
        return jsonify(None)
    
    try:
        article = db.get_community_article(community_article_id)
        if not article:
            return jsonify(None)
        
        # Convert to dict if needed and format dates
        article_dict = dict(article)
        if 'created_at' in article_dict and hasattr(article_dict['created_at'], 'isoformat'):
            article_dict['created_at'] = article_dict['created_at'].isoformat()
        if 'updated_at' in article_dict and hasattr(article_dict['updated_at'], 'isoformat'):
            article_dict['updated_at'] = article_dict['updated_at'].isoformat()
            
        return jsonify(article_dict)
    except Exception as e:
        app.logger.error(f"Error fetching current community article: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/community_articles/save_content', methods=['POST'])
def save_community_article_content():
    """Save the community article content"""
    community_article_id = session.get('community_article_id')
    if not community_article_id:
        return jsonify({'error': 'No community article selected'}), 400

    article_content = request.form.get('article_content', '')
    article_title = request.form.get('article_title', '')
    
    try:
        db.save_community_article_content(
            community_article_id=community_article_id,
            article_title=article_title,
            article_content=article_content
        )
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error saving community article: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)