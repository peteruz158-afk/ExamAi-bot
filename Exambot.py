import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from groq import Groq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are WaecAI, an AI tutor for Nigerian WAEC and JAMB students.
Explain concepts using Nigerian examples students relate to.
Break down past questions step by step.
Be encouraging, friendly and patient."""

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Yo! I'm WaecAI — your personal WAEC and JAMB tutor.\n\nJust type your question and let's go 💪"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_message = update.message.text
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": student_message}
            ]
        )
        ai_reply = response.choices[0].message.content
        await update.message.reply_text(ai_reply)
    except Exception as e:
        print(f"GROQ ERROR: {e}")
        await update.message.reply_text(f"Error: {str(e)}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("WaecAI bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
