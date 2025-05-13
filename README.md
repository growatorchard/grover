# Grover: Senior Living Content Generation Platform

A Flask-based content generation platform specifically designed for senior living communities. The application helps create and manage content across different communities while maintaining SEO optimization and brand consistency.

## Features

- **Project Management**
  - Create and manage content projects
  - Define target audiences, care areas, and content parameters
  - Track multiple articles per project

- **Content Generation**
  - AI-powered article generation
  - SEO-optimized content creation
  - Customizable article length and sections
  - Support for multiple content formats

- **Community-Specific Content**
  - Generate community-specific versions of base articles
  - Maintain consistent messaging across communities
  - Automatic integration of community-specific details

- **Keyword Research**
  - SEMrush integration for keyword research
  - Keyword difficulty and search volume analysis
  - Keyword management within projects

## Prerequisites

- Python 3.9 or higher
- SQLite3
- OpenAI API key
- SEMrush API key (optional, for keyword research)

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd grover
```

2. Create and activate a virtual environment:
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with the following variables:
```env
SECRET_KEY=your_secure_random_string_here
FLASK_APP=app.py
FLASK_ENV=development
LLM_API_KEY=your_llm_api_key
SEMRUSH_API_KEY=your_semrush_api_key  # Optional
```

5. Initialize the database:
```bash
python database/setup_database.py
```

## Running the Application

### Option 1: Local Development
1. Ensure your virtual environment is activated
2. Start the Flask application:
```bash
python app.py
```
3. Access the application at `http://localhost:5000`

### Option 2: Using Docker Compose (Recommended)
1. Build and start the containers:
```bash
docker compose build
docker compose up -d
```
2. Access the application at `http://localhost:5000`

To stop the application:
```bash
docker compose down
```

## Application Structure

```
/grover/
├── app.py                   # Main application file
├── config/                  # Configuration files
├── database/               # Database managers
├── services/               # Service modules
├── utils/                  # Utility functions
├── static/                 # Static files (CSS, JS)
├── templates/              # HTML templates
├── data/                   # Database files
└── requirements.txt        # Dependencies
```

## Usage Guide

1. **Creating a Project**
   - Click "New Project" in the sidebar
   - Fill in project details (name, care areas, target audience, etc.)
   - Save the project

2. **Adding Keywords**
   - Select your project
   - Use the keyword research tool to find relevant keywords
   - Add keywords to your project

3. **Creating Content**
   - Select your project
   - Click "New Article"
   - Set article parameters (length, sections, etc.)
   - Generate content using AI
   - Edit and refine as needed

4. **Creating Community-Specific Versions**
   - Select your base article
   - Choose a community
   - Generate a community-specific version
   - Review and edit the content

## Development

- The application uses Flask for the backend
- Bootstrap 5 for the frontend
- SQLite for data storage
- OpenAI API for content generation
- SEMrush API for keyword research

## Security Notes

- Never commit your `.env` file
- Keep your API keys secure
- Add `.env` to your `.gitignore` file
- Regularly update dependencies

## Troubleshooting

1. **Database Issues**
   - Ensure the `/data` directory exists and is writable
   - Check database permissions
   - Run database setup script if needed

2. **API Issues**
   - Verify API keys in `.env` file
   - Check API rate limits
   - Ensure internet connectivity

3. **Application Errors**
   - Check Flask debug output
   - Verify all dependencies are installed
   - Check file permissions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[License Here]