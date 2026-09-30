import os
from dotenv import load_dotenv

load_dotenv()

# Base Configuration
MIN_PRICE = int(os.getenv("MIN_PRICE", 200))

# RSI Limits
RSI_MIN = int(os.getenv("RSI_MIN", 50))
RSI_MAX = int(os.getenv("RSI_MAX", 70))

# Volume & Value
MIN_VOLUME = int(os.getenv("MIN_VOLUME", 1_000_000))
MIN_VALUE = int(os.getenv("MIN_VALUE", 10_000_000_000))
MIN_VOLUME_RATIO = float(os.getenv("MIN_VOLUME_RATIO", 1.5))

# EMA
EMA_FAST = int(os.getenv("EMA_FAST", 9))
EMA_SLOW = int(os.getenv("EMA_SLOW", 21))

# Signals
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", 75))
MIN_RISK_REWARD = float(os.getenv("MIN_RISK_REWARD", 1.5))
SIGNAL_FRESH_MINUTES = int(os.getenv("SIGNAL_FRESH_MINUTES", 60))
SIGNAL_AGING_MINUTES = int(os.getenv("SIGNAL_AGING_MINUTES", 180))

# Database — supports PostgreSQL or SQLite via DATABASE_URL
DEFAULT_DB_URL = "sqlite:////tmp/stock_signal.db" if os.getenv("VERCEL") else "sqlite:///./data/stock_signal.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# AI / Google Gemini API (Free Tier)
# Get your free key at: https://aistudio.google.com/app/apikey
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
