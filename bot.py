import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime
import dotenv
dotenv.load_dotenv()

class DailyBrieferBot:
    def __init__(self, gemini_key, telegram_token, chat_id):
        self.gemini_key = gemini_key
        self.telegram_token = telegram_token
        self.chat_id = chat_id

        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

        print("Daily Briefer Bot initialized!")

    def scrape_news(self):
        try:
            url = "https://news.ycombinator.com/"
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")

            stories = []
            for item in soup.find_all("span", class_="titleline")[:5]:
                stories.append(item.text)

            return stories

        except Exception:
            return ["Could not fetch news today"]

    def get_crypto_prices(self):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
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
            }

        except Exception:
            return None

    def generate_briefing(self, news, crypto):
        news_text = "\n".join([f"- {n}" for n in news])

        if crypto:
            crypto_text = ""
            for coin, d in crypto.items():
                emoji = "📈" if d["change"] > 0 else "📉"
                crypto_text += f"{coin}: ${d['price']:,.0f} {emoji} {d['change']:.2f}%\n"
        else:
            crypto_text = "Crypto data unavailable"

        prompt = f"""
You are a witty morning briefer.

NEWS:
{news_text}

CRYPTO:
{crypto_text}

Write a short, interesting briefing (max 150 words).
"""

        try:
            response = self.model.generate_content(prompt)
            briefing = response.text

            today = datetime.now().strftime("%A, %B %d, %Y")

            return f"""
GOOD MORNING ☀️
{today}

{briefing}

- Daily Bot
"""

        except Exception:
            return "Error generating briefing"

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

        data = {
            "chat_id": self.chat_id,
            "text": message,
        }

        try:
            response = requests.post(url, data=data)
            return response.status_code == 200
        except Exception:
            return False

    def run_daily_briefing(self):
        news = self.scrape_news()
        crypto = self.get_crypto_prices()
        briefing = self.generate_briefing(news, crypto)
        return self.send_telegram(briefing)


if __name__ == "__main__":
    GEMINI_KEY = "your_gemini_api_key"
    TELEGRAM_TOKEN = "your_telegram_bot_token"
    CHAT_ID = "your_chat_id"

    bot = DailyBrieferBot(GEMINI_KEY, TELEGRAM_TOKEN, CHAT_ID)
    bot.run_daily_briefing()