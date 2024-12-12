from flask import Flask, request
import asyncio
import os
from telegram.ext import Application

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)
application = Application.builder().token(TELEGRAM_TOKEN).build()

@app.route("/")
def home():
    return "Telegram Bot is Running!"

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    json_data = request.get_json()
    asyncio.run(application.update_queue.put(json_data))
    return "OK", 200

async def set_webhook():
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL')}/{TELEGRAM_TOKEN}"
    print(f"Webhook URL: {webhook_url}")
    await application.bot.set_webhook(webhook_url)

if __name__ == "__main__":
    print(f"Starting Flask on port {PORT}")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_webhook())
    app.run(host="0.0.0.0", port=PORT)
