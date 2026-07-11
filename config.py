import os
from pathlib import Path

from dotenv import load_dotenv


# Load local environment variables regardless of the current working directory.
load_dotenv(Path(__file__).resolve().parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
