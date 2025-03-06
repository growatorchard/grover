# Grover Flask Application

This is a Flask-based implementation of the Grover application, which was originally built with Streamlit. The Flask implementation offers better state management for complex forms and user interactions.

## Project Structure

```
/grover-flask/
  ├── app.py                   # Main application file
  ├── config/                  # Configuration files
  ├── database/                # Database managers
  ├── services/                # Service modules
  ├── utils/                   # Utility functions
  ├── static/                  # Static files (CSS, JS)
  ├── templates/               # HTML templates
  └── requirements.txt         # Dependencies
```

## Getting Started

1. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following variables:
   ```
   SECRET_KEY=your_secure_random_string_here
   FLASK_APP=app.py
   FLASK_ENV=development
   LLM_API_KEY=your_llm_api_key
   SEMRUSH_API_KEY=your_semrush_api_key
   # Add any other environment variables your app needs
   ```

4. Run the application:
   ```bash
   flask run
   ```

5. Visit `http://127.0.0.1:5000/` in your browser.

## Key Features

- Project management with form-based creation and editing
- Keyword research and management with SEMrush integration
- Article generation using LLM services
- Community-specific content revision
- Automatic saving of article content
- Debug mode for development and troubleshooting

## Migrating from Streamlit

This Flask implementation maintains all the functionality of the original Streamlit app while improving:

1. State management - Using Flask sessions instead of Streamlit's st.session_state
2. UI responsiveness - Using AJAX for asynchronous updates without page reloads
3. Code organization - Better separation of concerns with modular templates and routes
4. User experience - More traditional web app interactions for forms and navigation

The backend services (database, LLM, SEMrush) remain largely unchanged, maintaining compatibility with existing data and services.

## Additional Notes

- The application uses Bootstrap 5 for styling and responsive design
- jQuery is used for AJAX requests and DOM manipulation
- Custom Jinja filters help with JSON data handling in templates