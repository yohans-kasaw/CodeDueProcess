"""Configuration for sandbox - LangGraph testing environment.

Environment-based configuration system.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine the project root directory
# (three levels up: src/codedueprocess/config.py -> src/codedueprocess -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Configuration Constants
LLM_MODEL = os.getenv("LLM_MODEL", "")
APP_ENV = os.getenv("APP_ENV", "development")

# Database Path - stored in the project root
DB_PATH = str(PROJECT_ROOT / ".langchain.db")
