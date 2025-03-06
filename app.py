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
    current_article = None
    
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
            except Exception as e:
                app.logger.error(f"Error fetching article: {str(e)}")
                session['article_id'] = None
    
    return render_template('index.html', 
                          projects=projects,
                          selected_project=selected_project,
                          articles=articles,
                          current_article=current_article,
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
                'article_brief': article['article_brief'],
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
    article_brief = request.form.get('article_brief', '')
    article_length = int(request.form.get('article_length', 1000))
    article_sections = int(request.form.get('article_sections', 5))
    
    try:
        # Get current article to preserve any fields not being updated
        article = db.get_article_content(article_id)
        
        # Only update content and metadata fields if they exist in the current article
        article_content = article['article_content'] if 'article_content' in article else ''
        meta_title = article['meta_title'] if 'meta_title' in article else ''
        meta_description = article['meta_description'] if 'meta_description' in article else ''
        
        # Save everything in one operation
        db.save_article_content(
            project_id=session.get('project_id'),
            article_title=article_title,
            article_brief=article_brief,
            article_length=article_length,
            article_sections=article_sections,
            article_content=article_content,
            article_schema=None,
            meta_title=meta_title,
            meta_description=meta_description,
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

    article_brief = ainfo["article_brief"]
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
{article_brief}

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
    """Save the generated title and outline to the current article."""
    article_id = session.get('article_id')
    if not article_id:
        return jsonify({'error': 'No article selected'}), 400
    
    article_title = request.form.get('article_title', '')
    article_brief = request.form.get('article_brief', '')
    
    if not article_title or not article_brief:
        return jsonify({'error': 'Title and outline are required'}), 400
    
    try:
        # Get current article data
        article = db.get_article_content(article_id)
        
        # Access properties directly using dictionary-style access (if article is a dict)
        # or using attribute access (if article is an object)
        try:
            article_length = article['article_length'] if 'article_length' in article else 1000
            article_sections = article['article_sections'] if 'article_sections' in article else 5
            article_content = article['article_content'] if 'article_content' in article else ''
            meta_title = article['meta_title'] if 'meta_title' in article else ''
            meta_description = article['meta_description'] if 'meta_description' in article else ''
        except (TypeError, KeyError):
            # Fallback if article doesn't have these attributes
            article_length = 1000
            article_sections = 5
            article_content = ''
            meta_title = ''
            meta_description = ''
        
        # Update title and brief
        db.save_article_content(
            project_id=session.get('project_id'),
            article_title=article_title,
            article_content=article_content,
            article_schema=None,
            meta_title=meta_title,
            meta_description=meta_description,
            article_id=article_id,
            article_brief=article_brief,
            article_length=article_length,
            article_sections=article_sections
        )
        
        return jsonify({
            'success': True,
            'message': 'Title and outline saved successfully'
        })
    except Exception as e:
        app.logger.error(f"Error saving article title and outline: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/articles/save', methods=['POST'])
def save_article_content():
    """Save the article content without changing the title or metadata."""
    project_id = session.get('project_id')
    article_id = session.get('article_id')
    if not project_id or not article_id:
        return jsonify({'error': 'No project or article selected'}), 400
    
    article_content = request.form.get('article_content', '')
    
    try:
        # Get current article data to preserve other fields
        article = db.get_article_content(article_id)
        
        # Update just the content
        saved_id = db.save_article_content(
            project_id=project_id,
            article_title=article.get('article_title', ''),
            article_content=article_content,
            article_schema=None,
            meta_title=article.get('meta_title', ''),
            meta_description=article.get('meta_description', ''),
            article_id=article_id
        )
        
        # Update drafts in session
        drafts = session.get('drafts_by_article', {})
        drafts[str(article_id)] = article_content
        session['drafts_by_article'] = drafts
        
        return jsonify({'success': True, 'article_id': saved_id})
    except Exception as e:
        app.logger.error(f"Error saving article content: {str(e)}")
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
    # costs = calculate_token_costs(token_usage)
    
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
    communities = [dict(c) for c in communities] if communities else []
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