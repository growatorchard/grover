from dotenv import load_dotenv

load_dotenv()

# Constants
TARGET_AUDIENCES = ["Seniors", "Adult Children", "Caregivers", "Health Professionals", "Other"]

MODEL_OPTIONS = {
    "ChatGPT (o1)": "o1-mini"
}

CARE_AREAS = [
    "Independent Living",
    "Assisted Living", 
    "Memory Care",
    "Skilled Nursing"
]

JOURNEY_STAGES = [
    "Awareness",
    "Consideration", 
    "Decision",
    "Retention",
    "Advocacy",
    "Other"
] 

ARTICLE_CATEGORIES = ["Senior Living", "Health/Wellness", "Lifestyle", "Financial", "Other"]

FORMAT_TYPES = ["Blog", "Case Study", "White Paper", "Guide", "Downloadable Guide", "Review", "Interactives", "Brand Content", "Infographic", "E-Book", "Email", "Social Media Posts", "User Generated Content", "Meme", "Checklist", "Video", "Podcast", "Other"]

BUSINESS_CATEGORIES = ["Healthcare", "Senior Living", "Housing", "Lifestyle", "Other"]

CONSUMER_NEEDS = ["Educational", "Financial Guidance", "Medical Info", "Lifestyle/Wellness", "Other"]

TONE_OF_VOICE = ["Professional", "Friendly", "Conversational", "Empathetic", "Other"]

# Token costs
INPUT_COST_PER_MILLION = 1.10
OUTPUT_COST_PER_MILLION = 4.40 