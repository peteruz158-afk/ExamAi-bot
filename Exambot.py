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

# Your keys — paste them here
TELEGRAM_TOKEN = "8987511434:AAHIWZUzQX68ZWi97Vf0Tz-4jDIiruwP8wU"
GROQ_API_KEY = "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"

# Setup Groq
client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are WaecAI, an AI tutor specifically for Nigerian WAEC and JAMB students.
Explain concepts simply using Nigerian examples and analogies students relate to.
Break down past questions step by step clearly.
Be encouraging, friendly and patient.
Keep responses concise and easy to read on a phone screen.
If a student seems frustrated, motivate them."""

logging.basicConfig(level=logging.INFO)

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Yo! I'm WaecAI — your personal WAEC and JAMB tutor.\n\n"
        "Ask me anything — past questions, topic explanations, "
        "whatever you need. I got you 💪\n\n"
        "Just type your question and let's go!"
    )

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Here's what you can do:\n\n"
        "📚 Ask any WAEC/JAMB question\n"
        "🔍 Paste a past question for step by step breakdown\n"
        "💡 Ask me to explain any topic simply\n"
        "🧪 Type /quiz followed by a subject for practice questions\n\n"
        "Just type and send — simple!"
    )

# Handle all messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_message = update.message.text

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": student_message}
            ]
        )
        ai_reply = response.choices[0].message.content
        await update.message.reply_text(ai_reply)

    except Exception as e:
        await update.message.reply_text(
            "My bad bruv, something went wrong. Try again in a sec 🙏"
        )

# Run the bot
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("WaecAI bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
