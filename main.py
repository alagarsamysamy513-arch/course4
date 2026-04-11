import schedule
import time
from bot import DailyBrieferBot
import os
from dotenv import load_dotenv
load_dotenv()
# Get credentials from environment variables
GEMINI_KEY = os.environ.get('GEMINI_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
# Create bot
bot = DailyBrieferBot(GEMINI_KEY, TELEGRAM_TOKEN, CHAT_ID)
# Schedule for 8 AM every day
schedule.every().day.at("14:57").do(bot.run_daily_briefing)
print("🤖 Daily Briefer Bot is now running!")
print("📅 Scheduled for 2:57 PM daily")
print("Press Ctrl+C to stop")
print(bot.send_telegram("Hello from bot 🚀"))
# Keep running
while True:
 schedule.run_pending()
 time.sleep(60) # Check every minute
