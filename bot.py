import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime
import dotenv
import telebot
import os
import pytz
from apscheduler.schedulers.background import BackgroundScheduler


dotenv.load_dotenv()

class DailyBrieferBot:
    def __init__(self, gemini_key, telegram_token, chat_id):
        self.gemini_key = gemini_key
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.interests = "Market news, Crypto, Business"


        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash") # Official stable model
        self.bot = telebot.TeleBot(telegram_token)
        
        # Initialize Scheduler
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
        self.scheduler.start()
        self.current_job_id = "daily_briefing"

        print("Daily Briefer Bot initialized with Scheduler!")


    def fetch_topic_news(self):
        """Fetches latest news from Google News based on user interests"""
        try:
            import urllib.parse
            query = urllib.parse.quote(self.interests)
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, "xml") # RSS is XML
            
            items = soup.find_all('item')
            news_items = []
            for item in items[:10]: # Get top 10 results
                title = item.title.text
                news_items.append(title)
            
            if not news_items:
                return [f"No recent news found for '{self.interests}'"]
            
            return news_items

        except Exception as e:
            print(f"News Search error: {e}")
            return [f"Could not fetch news for '{self.interests}' right now"]

    # Keeping the old scraper as a fallback or removing if not needed
    def scrape_market_news(self):
        return self.fetch_topic_news()


    def get_crypto_prices(self):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,ripple&vs_currencies=usd&include_24hr_change=true"
            response = requests.get(url)
            data = response.json()

            return {
                "BTC": {
                    "price": data["bitcoin"]["usd"],
                    "change": data["bitcoin"]["usd_24h_change"],
                },
                "ETH": {
                    "price": data["ethereum"]["usd"],
                    "change": data["ethereum"]["usd_24h_change"],
                },
                "XRP": {
                    "price": data["ripple"]["usd"],
                    "change": data["ripple"]["usd_24h_change"],
                }
            }
        except Exception:
            return {}


    def generate_briefing(self, news, crypto):
        news_text = "\n".join([f"- {n}" for n in news])
        
        if crypto:
            crypto_text = ""
            for coin, d in crypto.items():
                emoji = "📈" if d["change"] > 0 else "📉"
                crypto_text += f"{coin}: ${d['price']:,.2f} {emoji} {d['change']:.2f}%\n"
        else:
            crypto_text = "Crypto data unavailable"

        prompt = f"""
        You are a financial market expert. 
        Analyze these latest headlines and crypto prices:
        
        NEWS:
        {news_text}
        
        CRYPTO:
        {crypto_text}
        
        Write a concise, professional market briefing (max 150 words). 
        
        STRICT RULES:
        1. Focus ONLY on information related to: {self.interests}.
        2. If the news data contains other topics, IGNORE THEM.
        3. If no news is found for the interests, mention that specifically.
        4. Identify if it's currently Morning, Afternoon, or Evening session based on the provided data context.
        """



        try:
            response = self.model.generate_content(prompt)
            briefing = response.text
            today = datetime.now().strftime("%A, %B %d, %I:%M %p")
            return f"🔔 *LATEST MARKET UPDATE*\n_{today}_\n\n{briefing}\n\n- Powered by MarketBot"
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return "Error generating briefing"

    def send_telegram(self, message):
        try:
            self.bot.send_message(self.chat_id, message, parse_mode='Markdown')
            return True
        except Exception as e:
            print(f"Telegram error: {e}")
            return False

    def run_daily_briefing(self):
        print(f"[{datetime.now()}] Running scheduled daily briefing...")
        news = self.scrape_market_news()
        crypto = self.get_crypto_prices()
        briefing = self.generate_briefing(news, crypto)
        return self.send_telegram(briefing)

    def set_daily_schedule(self, hour, minute):
        """Sets or updates the daily briefing schedule"""
        # Remove existing job if any
        self.scheduler.remove_all_jobs()
        
        # Add new job
        self.scheduler.add_job(
            self.run_daily_briefing,
            'cron',
            hour=hour,
            minute=minute,
            id=self.current_job_id
        )
        print(f"Schedule set for {hour:02d}:{minute:02d} IST")
        return True

    def update_interests(self, new_interests):
        self.interests = new_interests
        print(f"Interests updated to: {self.interests}")
        return True

    def get_schedule_info(self):
        """Returns information about the current schedule"""
        job = self.scheduler.get_job(self.current_job_id)
        schedule_data = {
            "active": False,
            "interests": self.interests,
            "time": "09:00" # Default value
        }
        if job:
            next_run = job.next_run_time
            schedule_data.update({
                "active": True,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S %Z") if next_run else "N/A"
            })
            
            # Extract time safely from cron fields
            try:
                # Different versions of APScheduler might store this differently
                # We try to get hour and minute from the trigger fields
                trigger = job.trigger
                hour = str(trigger.fields[5]).zfill(2)
                minute = str(trigger.fields[6]).zfill(2)
                # Clean up if it's a CronField object string
                hour = ''.join(filter(str.isdigit, hour)) or "00"
                minute = ''.join(filter(str.isdigit, minute)) or "00"
                schedule_data["time"] = f"{hour.zfill(2)}:{minute.zfill(2)}"
            except Exception as e:
                print(f"Error parsing schedule time: {e}")
                schedule_data["time"] = "09:00"
        
        return schedule_data





    def setup_handlers(self):
        @self.bot.message_handler(func=lambda message: True)
        def echo_all(message):
            if message.text.lower() == "hi":
                self.bot.reply_to(message, "Generating your briefing... ⏳")
                news = self.scrape_market_news()
                crypto = self.get_crypto_prices()
                briefing = self.generate_briefing(news, crypto)
                self.bot.send_message(message.chat.id, briefing, parse_mode='Markdown')
            else:
                self.bot.reply_to(message, "I only react to 'hi' right now! Try sending 'hi' for latest market news.")

    def start_polling(self):
        self.setup_handlers()
        print("Bot is listening for messages...")
        self.bot.infinity_polling()

if __name__ == "__main__":
    GEMINI_KEY = os.getenv("GEMINI_KEY")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")

    bot = DailyBrieferBot(GEMINI_KEY, TELEGRAM_TOKEN, CHAT_ID)
    bot.run_daily_briefing()
