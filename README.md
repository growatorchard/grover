# Grover: LLM-based Content Generation Tool

An AI-powered content generation application with SEMrush keyword research integration and multi-audience targeting capabilities.

## Prerequisites

- Python 3.8 or higher
- OpenAI API key
- SEMrush API key (optional, for keyword research functionality)

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

4. Set up configuration:

Create a `.streamlit` directory in the project root:
```bash
mkdir .streamlit
```

Create a `secrets.toml` file inside `.streamlit` directory with your API keys:
```toml
# .streamlit/secrets.toml

OPENAI_API_KEY = "your-openai-api-key"
SEMRUSH_API_KEY = "your-semrush-api-key"  # Optional
```

## Running the Application

1. Ensure your virtual environment is activated
2. Run the Streamlit application:
```bash
streamlit run app.py
```
3. The applicaiton should open in your web browser automatically, if it does not,
 then you should open your web browser and navigate to `http://localhost:8501`

## Features

- Multi-audience content targeting
- AI-powered topic generation
- SEMrush keyword research integration
- Content refinement and revision
- Token usage tracking for API calls
- Project management capabilities

## Usage Tips

1. **Project Creation**:
   - Create a new project with basic details
   - Select multiple target audiences
   - Define content parameters

2. **Topic Generation**:
   - Use the "Generate 5 Topics" feature for content ideas
   - Topics are tailored to your selected parameters

3. **Content Generation**:
   - Generate initial drafts
   - Refine content with specific instructions
   - Track token usage for each API call

4. **Keyword Research** (requires SEMrush API key):
   - Access keyword metrics
   - Analyze search volume
   - View keyword difficulty scores

## Troubleshooting

- If you encounter API errors, verify your API keys in `.streamlit/secrets.toml`
- Ensure all dependencies are installed correctly
- Check your Python version compatibility
- Verify your internet connection for API calls

## Security Notes

- Never commit your `secrets.toml` file to version control
- Keep your API keys secure and rotate them periodically
- Add `.streamlit/secrets.toml` to your `.gitignore` file