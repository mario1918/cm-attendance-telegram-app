import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set. Please create a .env file with BOT_TOKEN=your_token")

DB_PATH = os.getenv("DB_PATH", "attendance.db")
