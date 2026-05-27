import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from groq import Groq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are WaecAI, a professional academic tutor specialising in WAEC and JAMB examinations.

Your responsibilities:
- Explain concepts clearly and academically with proper structure
- Solve past questions with full working and step by step methodology
- Use correct academic terminology at all times
- Be encouraging, patient and supportive
- Format answers clearly with numbered steps where necessary
- For calculations always show full workings
- For theory questions give concise but complete answers
- Always relate answers back to the WAEC and JAMB syllabus"""

SUBJECTS = [
    "Mathematics", "Physics", "Chemistry",
    "Biology", "English Language", "Economics",
    "Government", "Literature", "Geography", "Commerce"
]

QUIZ_QUESTIONS = {}
USER_SUBJECTS = {}

logging.basicConfig(level=logging.INFO)

def subject_keyboard():
    keyboard = []
    row = []
    for i, subject in enumerate(SUBJECTS):
        row.append(InlineKeyboardButton(subject, callback_data=f"subject_{subject}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Welcome, {first_name}!\n\n"
        f"I am WaecAI — your dedicated WAEC and JAMB examination tutor.\n\n"
        f"I can help you with:\n"
        f"📚 Topic explanations\n"
        f"🔍 Past question solutions\n"
        f"✏️ Practice quizzes\n"
        f"💡 Exam tips and techniques\n\n"
        f"Please select your subject to get started:",
        reply_markup=subject_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *WaecAI Commands*\n\n"
        "/start — Welcome message and subject selection\n"
        "/subject — Change your current subject\n"
        "/quiz — Get a practice question on your subject\n"
        "/tips — Get WAEC exam tips and techniques\n"
        "/syllabus — View key topics for your subject\n\n"
        "Or simply type any question and I will answer it.",
        parse_mode="Markdown"
    )

async def subject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please select a subject:",
        reply_markup=subject_keyboard()
    )

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    subject = USER_SUBJECTS.get(user_id, None)

    if not subject:
        await update.message.reply_text(
            "Please select a subject first using /subject"
        )
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate one WAEC standard multiple choice question on {subject}. Format it exactly like this:\nQUESTION: [question text]\nA) [option]\nB) [option]\nC) [option]\nD) [option]\nANSWER: [correct letter]\nEXPLANATION: [brief explanation]"}
            ]
        )
        quiz_text = response.choices[0].message.content

        lines = quiz_text.strip().split('\n')
        answer_line = [l for l in lines if l.startswith("ANSWER:")]
        explanation_line = [l for l in lines if l.startswith("EXPLANATION:")]

        if answer_line:
            correct = answer_line[0].replace("ANSWER:", "").strip()
            QUIZ_QUESTIONS[user_id] = {
                "answer": correct,
                "explanation": explanation_line[0].replace("EXPLANATION:", "").strip() if explanation_line else ""
            }

        question_text = '\n'.join([l for l in lines if not l.startswith("ANSWER:") and not l.startswith("EXPLANATION:")])

        keyboard = [
            [
                InlineKeyboardButton("A", callback_data="quiz_A"),
                InlineKeyboardButton("B", callback_data="quiz_B"),
                InlineKeyboardButton("C", callback_data="quiz_C"),
                InlineKeyboardButton("D", callback_data="quiz_D"),
            ]
        ]

        await update.message.reply_text(
            f"📝 *{subject} Quiz*\n\n{question_text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        print(f"QUIZ ERROR: {e}")
        await update.message.reply_text("Unable to generate quiz question. Please try again.")

async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id, "general WAEC")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Give 5 specific professional exam tips for scoring high in WAEC {subject}. Be concise and practical."}
            ]
        )
        await update.message.reply_text(
            f"💡 *Exam Tips — {subject}*\n\n{response.choices[0].message.content}",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"TIPS ERROR: {e}")
        await update.message.reply_text("Unable to load tips. Please try again.")

async def syllabus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id, None)

    if not subject:
        await update.message.reply_text("Please select a subject first using /subject")
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"List the key topics in the WAEC {subject} syllabus that students must study. Be concise and well structured."}
            ]
        )
        await update.message.reply_text(
            f"📋 *{subject} — Key Syllabus Topics*\n\n{response.choices[0].message.content}",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"SYLLABUS ERROR: {e}")
        await update.message.reply_text("Unable to load syllabus. Please try again.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    first_name = query.from_user.first_name

    if query.data.startswith("subject_"):
        subject = query.data.replace("subject_", "")
        USER_SUBJECTS[user_id] = subject
        await query.edit_message_text(
            f"✅ Subject set to *{subject}*\n\n"
            f"You are now ready, {first_name}.\n\n"
            f"Ask me any question, or use:\n"
            f"/quiz — Practice question\n"
            f"/tips — Exam tips\n"
            f"/syllabus — Key topics",
            parse_mode="Markdown"
        )

    elif query.data.startswith("quiz_"):
        selected = query.data.replace("quiz_", "")
        quiz_data = QUIZ_QUESTIONS.get(user_id)

        if not quiz_data:
            await query.edit_message_text("Quiz expired. Use /quiz to get a new question.")
            return

        correct = quiz_data["answer"]
        explanation = quiz_data["explanation"]

        if selected == correct:
            result = f"✅ *Correct! Well done.*\n\n📖 *Explanation:*\n{explanation}\n\nUse /quiz for another question."
        else:
            result = f"❌ *Incorrect.*\nThe correct answer is *{correct}*.\n\n📖 *Explanation:*\n{explanation}\n\nUse /quiz to try again."

        await query.edit_message_text(result, parse_mode="Markdown")
        QUIZ_QUESTIONS.pop(user_id, None)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_message = update.message.text
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    subject = USER_SUBJECTS.get(user_id, "")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        subject_context = f"The student is currently studying {subject}. " if subject else ""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{subject_context}{first_name} asks: {student_message}"}
            ]
        )
        ai_reply = response.choices[0].message.content
        await update.message.reply_text(ai_reply)
    except Exception as e:
        print(f"GROQ ERROR: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subject", subject_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("tips", tips_command))
    app.add_handler(CommandHandler("syllabus", syllabus_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("WaecAI bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
