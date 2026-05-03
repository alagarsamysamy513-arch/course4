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
        # Dynamic crypto tracking
        self.crypto_ids = ["bitcoin", "ethereum", "ripple"]

        genai.configure(api_key=gemini_key)
        # Using 1.5-flash which is stable and fast
        self.model = genai.GenerativeModel("gemini-1.5-flash") 
        self.bot = telebot.TeleBot(telegram_token)
        
        # Initialize Scheduler
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
        self.scheduler.start()
        self.current_job_id = "daily_briefing"

        print("Daily Briefer Bot initialized!")

    def fetch_topic_news(self):
        """Fetches latest news from Google News based on user interests"""
        try:
            import urllib.parse
            query = urllib.parse.quote(self.interests)
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, "xml")
            
            items = soup.find_all('item')
            news_items = [item.title.text for item in items[:10]]
            
            return news_items or [f"No recent news found for '{self.interests}'"]
        except Exception as e:
            print(f"News Search error: {e}")
            return [f"Could not fetch news right now"]

    def scrape_market_news(self):
        return self.fetch_topic_news()

    def get_crypto_prices(self):
        """Fetches dynamic crypto prices based on self.crypto_ids"""
        if not self.crypto_ids: return {}
        try:
            ids_str = ",".join(self.crypto_ids)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true"
            response = requests.get(url)
            data = response.json()

            results = {}
            for cid in self.crypto_ids:
                if cid in data:
                    results[cid.upper()] = {
                        "price": data[cid]["usd"],
                        "change": data[cid].get("usd_24h_change", 0),
                    }
            return results
        except Exception as e:
            print(f"Crypto error: {e}")
            return {}

    def generate_briefing(self, news, crypto):
        news_text = "\n".join([f"- {n}" for n in news])
        crypto_text = ""
        if crypto:
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
        1. Focus ONLY on: {self.interests}.
        2. Identify if it's Morning, Afternoon, or Evening session.
        3. Use a professional but engaging tone.
        """

        try:
            response = self.model.generate_content(prompt)
            
            # Check if response has text (handles safety filters)
            if response.candidates and response.candidates[0].content.parts:
                briefing = response.text
                today = datetime.now().strftime("%A, %B %d, %I:%M %p")
                return f"🔔 *LATEST MARKET UPDATE*\n_{today}_\n\n{briefing}\n\n- Powered by MarketBot"
            else:
                print("[AI] Response was blocked or empty.")
                return "Briefing unavailable (Content filtered)"
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
        news = self.scrape_market_news()
        crypto = self.get_crypto_prices()
        briefing = self.generate_briefing(news, crypto)
        return self.send_telegram(briefing)

    def set_daily_schedule(self, hour, minute):
        self.scheduler.remove_all_jobs()
        self.scheduler.add_job(self.run_daily_briefing, 'cron', hour=hour, minute=minute, id=self.current_job_id)
        return True

    def update_interests(self, new_interests):
        self.interests = new_interests
        return True

    def update_crypto_ids(self, new_ids):
        if isinstance(new_ids, str):
            self.crypto_ids = [i.strip().lower() for i in new_ids.split(",") if i.strip()]
        else:
            self.crypto_ids = [i.lower() for i in new_ids]
        return True

    def get_schedule_info(self):
        job = self.scheduler.get_job(self.current_job_id)
        schedule_data = {"active": False, "interests": self.interests, "crypto_ids": ",".join(self.crypto_ids), "time": "09:00"}
        if job:
            schedule_data["active"] = True
            schedule_data["next_run"] = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "N/A"
        return schedule_data

    def start_polling(self):
        @self.bot.message_handler(func=lambda message: True)
        def echo_all(message):
            if message.text.lower() == "hi":
                self.bot.reply_to(message, "Generating briefing... ⏳")
                self.run_daily_briefing()
        self.bot.infinity_polling()

if __name__ == "__main__":
    bot = DailyBrieferBot(os.getenv("GEMINI_KEY"), os.getenv("TELEGRAM_TOKEN"), os.getenv("CHAT_ID"))
    bot.run_daily_briefing()
