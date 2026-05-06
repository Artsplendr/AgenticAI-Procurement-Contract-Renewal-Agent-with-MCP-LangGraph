"""Central configuration — loads from .env"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Use the directory this file lives in so .env is found regardless of cwd
load_dotenv(Path(__file__).parent / ".env", override=True)

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = "claude-sonnet-4-6"

# Paths
DB_PATH = os.getenv("DB_PATH", "data/contracts.db")
CONTRACTS_DIR = os.getenv("CONTRACTS_DIR", "data/contracts")
OUTPUTS_DIR = "outputs"

# Renewal thresholds (days)
RENEWAL_THRESHOLDS = [90, 60, 30]

# Notifications
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "procurement@company.com")

# Search
SERP_API_KEY = os.getenv("SERP_API_KEY")
