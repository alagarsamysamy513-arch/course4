import os
import threading
from flask import Flask, render_template, request, jsonify

from bot import DailyBrieferBot
from dotenv import load_dotenv
from datetime import datetime
import json


load_dotenv()

# Credentials
GEMINI_KEY = os.environ.get('GEMINI_KEY')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Initialize Bot
bot_instance = DailyBrieferBot(GEMINI_KEY, TELEGRAM_TOKEN, CHAT_ID)

# Persistence Helper
CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Apply interests
                bot_instance.update_interests(config.get('interests', 'Market news, Crypto, Business'))
                # Apply schedule if exists
                time_str = config.get('schedule_time')
                if time_str:
                    hour, minute = map(int, time_str.split(':'))
                    bot_instance.set_daily_schedule(hour, minute)
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
    return {}

def save_config(schedule_time=None, interests=None):
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    
    if schedule_time is not None:
        config['schedule_time'] = schedule_time
    if interests is not None:
        config['interests'] = interests
        
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Load saved settings
load_config()

# Flask Setup

app = Flask(__name__)

# Global cache for briefing
cache = {
    "briefing": None,
    "last_updated": None
}

@app.route('/')
def dashboard():
    global cache
    now = datetime.now()
    
    news = bot_instance.scrape_market_news()
    crypto = bot_instance.get_crypto_prices()
    
    # Cache logic: refresh every 15 minutes to save quota
    if cache["briefing"] is None or (now - cache["last_updated"]).seconds > 900:
        print("[AI] Refreshing briefing cache...")
        new_briefing = bot_instance.generate_briefing(news, crypto)
        
        # Only cache if it's NOT an error message
        if "Error generating briefing" not in new_briefing:
            cache["briefing"] = new_briefing
            cache["last_updated"] = now
            print("[AI] New briefing cached.")
        else:
            print("[AI] API Error detected, not caching.")
            briefing = new_briefing # Still show the error to user once
    else:
        print("[AI] Using cached briefing")
        briefing = cache["briefing"]

    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")


    schedule = bot_instance.get_schedule_info()
    
    return render_template('index.html', 
                           news=news, 
                           crypto=crypto, 
                           briefing=briefing, 
                           timestamp=timestamp,
                           schedule=schedule)

@app.route('/set-schedule', methods=['POST'])
def set_schedule():
    data = request.json
    time_str = data.get('time') # Expected format "HH:MM"
    if time_str:
        try:
            hour, minute = map(int, time_str.split(':'))
            bot_instance.set_daily_schedule(hour, minute)
            save_config(schedule_time=time_str)
            return jsonify({"status": "success", "message": f"Schedule set for {time_str} IST"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "error", "message": "No time provided"}), 400

@app.route('/set-interests', methods=['POST'])
def set_interests():
    data = request.json
    interests = data.get('interests')
    if interests:
        try:
            bot_instance.update_interests(interests)
            save_config(interests=interests)
            return jsonify({"status": "success", "message": "Interests updated successfully!"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "error", "message": "No interests provided"}), 400

@app.route('/send-now', methods=['POST'])

def send_now():
    try:
        success = bot_instance.run_daily_briefing()
        if success:
            return jsonify({"status": "success", "message": "Briefing sent to Telegram!"})
        else:
            return jsonify({"status": "error", "message": "Failed to send to Telegram"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get-schedule')
def get_schedule():
    return jsonify(bot_instance.get_schedule_info())


def run_bot():
    print("[BOT] Starting Telegram Bot...")
    bot_instance.start_polling()

if __name__ == "__main__":
    # Start bot in a separate thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Start Flask server
    print("[WEB] Starting Web Dashboard...")
    # Using 0.0.0.0 to be accessible on the network
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
