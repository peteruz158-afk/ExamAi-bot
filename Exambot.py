import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    import,
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

SYSTEM_PROMPT = """You are ExamAI, a highly specialised academic tutor for Nigerian secondary school students preparing for WAEC, NECO and JAMB examinations.

Your teaching standards:
- All explanations must follow this structure: Definition, Key Principles, Step by Step Workings or Analysis, Summary and Exam Tips
- For Mathematics and Sciences: always show complete workings with every step clearly numbered
- For Arts and Social Sciences: use structured paragraphs with clear topic sentences
- Reference the WAEC, NECO or JAMB syllabus where relevant
- Point out common examiner traps and mistakes students make
- End every explanation with one key point the student must remember
- Be encouraging but academic in tone
- Keep responses concise enough to read on a mobile phone
- For JAMB specifically: note that it is CBT and time management is critical"""

SUBJECTS = [
    "Mathematics", "Physics", "Chemistry", "Biology",
    "English Language", "Economics", "Government",
    "Literature in English", "Geography", "Commerce",
    "Civic Education", "Agricultural Science", "Further Mathematics"
]

EXAMS = ["WAEC", "NECO", "JAMB"]

SYLLABUS = {
    "Mathematics": [
        "Number and Numeration", "Algebraic Processes", "Mensuration",
        "Plane Geometry", "Trigonometry", "Statistics and Probability",
        "Vectors and Transformation", "Calculus (JAMB)", "Sets"
    ],
    "Physics": [
        "Measurements and Units", "Motion", "Forces", "Work, Energy and Power",
        "Waves", "Optics", "Electricity", "Magnetism",
        "Atomic and Nuclear Physics", "Electronics"
    ],
    "Chemistry": [
        "Separation of Mixtures", "Atomic Structure", "Chemical Bonding",
        "Acids, Bases and Salts", "Redox Reactions", "Organic Chemistry",
        "Electrochemistry", "Rates of Reaction", "Equilibrium", "Metals"
    ],
    "Biology": [
        "Cell Biology", "Classification of Living Things", "Nutrition",
        "Respiration", "Excretion", "Reproduction", "Genetics and Heredity",
        "Evolution", "Ecology", "Support and Transport Systems"
    ],
    "English Language": [
        "Comprehension", "Summary Writing", "Lexis and Structure",
        "Essay Writing", "Oral English", "Register and Usage"
    ],
    "Economics": [
        "Introduction to Economics", "Demand and Supply", "National Income",
        "Money and Banking", "International Trade", "Agriculture",
        "Public Finance", "Population", "Economic Development"
    ],
    "Government": [
        "Political Concepts", "Forms of Government", "Constitution",
        "Legislature", "Executive", "Judiciary", "Federalism",
        "Nigerian Government History", "International Relations"
    ],
    "Literature in English": [
        "Drama", "Poetry", "Prose", "Literary Devices", "Oral Literature"
    ],
    "Geography": [
        "Map Reading", "Atmosphere", "Hydrosphere", "Rocks and Minerals",
        "Population Geography", "Agriculture", "Industry", "Transport"
    ],
    "Commerce": [
        "Trade", "Banking", "Insurance", "Transport", "Communication",
        "Warehousing", "Business Finance", "Commercial Documents"
    ],
    "Civic Education": [
        "Citizenship", "Human Rights", "Democracy", "Rule of Law",
        "Constitutional Development", "Government Agencies"
    ],
    "Agricultural Science": [
        "Crop Production", "Animal Production", "Soil Science",
        "Farm Machinery", "Agricultural Economics", "Fishery"
    ],
    "Further Mathematics": [
        "Polynomials", "Rational Functions", "Matrices",
        "Differentiation", "Integration", "Vectors", "Statistics"
    ]
}

QUIZ_QUESTIONS = {}
USER_SUBJECTS = {}
USER_EXAMS = {}

logging.basicConfig(level=logging.INFO)


def subject_keyboard():
    keyboard = []
    row = []
    for i, subject in enumerate(SUBJECTS):
        row.append(InlineKeyboardButton(subject, callback_data="sub_" + subject))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


def exam_keyboard():
    keyboard = [[
        InlineKeyboardButton("WAEC", callback_data="exam_WAEC"),
        InlineKeyboardButton("NECO", callback_data="exam_NECO"),
        InlineKeyboardButton("JAMB", callback_data="exam_JAMB"),
    ]]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_name = update.effective_user.first_name
    await update.message.reply_text(
        "Welcome, " + first_name + "!\n\n"
        "I am ExamAI — your dedicated tutor for WAEC, NECO and JAMB examinations.\n\n"
        "What I can do for you:\n"
        "📚 Step by step topic explanations\n"
        "🔍 Full past question solutions with workings\n"
        "✏️ Exam standard practice questions\n"
        "📋 Complete syllabus breakdown per subject\n"
        "💡 Exam tips and time management strategies\n"
        "⚠️ Common examiner traps to avoid\n\n"
        "First, which exam are you preparing for?",
        reply_markup=exam_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ExamAI Commands\n\n"
        "/start — Set your exam and subject\n"
        "/subject — Change subject\n"
        "/exam — Change exam type\n"
        "/quiz — Practice question with marking\n"
        "/syllabus — Full topic list for your subject\n"
        "/tips — Exam tips and technique\n"
        "/traps — Common mistakes to avoid\n"
        "/timetable — How to build a study timetable\n\n"
        "Or type any question directly."
    )


async def exam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Which exam are you preparing for?",
        reply_markup=exam_keyboard()
    )


async def subject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Select your subject:",
        reply_markup=subject_keyboard()
    )


async def syllabus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id)
    exam = USER_EXAMS.get(user_id, "WAEC")

    if not subject:
        await update.message.reply_text("Please select a subject first using /subject")
        return

    topics = SYLLABUS.get(subject, [])
    topic_list = "\n".join(["- " + t for t in topics])

    await update.message.reply_text(
        exam + " " + subject + " — Key Syllabus Topics\n\n" +
        topic_list +
        "\n\nAsk me about any of these topics for a full explanation."
    )


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id)
    exam = USER_EXAMS.get(user_id, "WAEC")

    if not subject:
        await update.message.reply_text("Please select a subject first using /subject")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    quiz_prompt = (
        "Generate one authentic " + exam + " standard multiple choice question on " + subject + ".\n\n"
        "Requirements:\n"
        "- Match the exact difficulty, style and language of real " + exam + " past questions\n"
        "- Test application and understanding, not just recall\n"
        "- Use precise academic terminology\n"
        "- Draw strictly from the official " + exam + " " + subject + " syllabus\n"
        "- Include one clearly correct answer and three plausible distractors\n\n"
        "Format exactly as follows with no extra text:\n"
        "QUESTION: [full question text]\n"
        "A) [option A]\n"
        "B) [option B]\n"
        "C) [option C]\n"
        "D) [option D]\n"
        "ANSWER: [correct letter only, e.g. B]\n"
        "EXPLANATION: [step by step explanation of why the answer is correct and why others are wrong]"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": quiz_prompt}
            ]
        )
        quiz_text = response.choices[0].message.content
        lines = quiz_text.strip().split("\n")

        answer_line = next((l for l in lines if l.startswith("ANSWER:")), None)
        explanation_line = next((l for l in lines if l.startswith("EXPLANATION:")), None)

        correct = answer_line.replace("ANSWER:", "").strip() if answer_line else "A"
        explanation = explanation_line.replace("EXPLANATION:", "").strip() if explanation_line else ""

        QUIZ_QUESTIONS[user_id] = {"answer": correct, "explanation": explanation}

        question_text = "\n".join([
            l for l in lines
            if not l.startswith("ANSWER:") and not l.startswith("EXPLANATION:")
        ])

        keyboard = [[
            InlineKeyboardButton("A", callback_data="quiz_A"),
            InlineKeyboardButton("B", callback_data="quiz_B"),
            InlineKeyboardButton("C", callback_data="quiz_C"),
            InlineKeyboardButton("D", callback_data="quiz_D"),
        ]]

        await update.message.reply_text(
            "📝 " + exam + " Practice — " + subject + "\n\n" + question_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        print("QUIZ ERROR: " + str(e))
        await update.message.reply_text("Could not generate question. Please try again.")


async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id, "all subjects")
    exam = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    "Give 6 highly specific and practical exam tips for scoring A or B in "
                    + exam + " " + subject + ". "
                    "Focus on: time management in the exam hall, question selection strategy, "
                    "how to structure answers, and how to avoid losing marks unnecessarily. "
                    "Be direct and specific, not generic."
                )}
            ]
        )
        await update.message.reply_text(
            "💡 " + exam + " Exam Tips — " + subject + "\n\n" +
            response.choices[0].message.content
        )
    except Exception as e:
        print("TIPS ERROR: " + str(e))
        await update.message.reply_text("Could not load tips. Please try again.")


async def traps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id, "all subjects")
    exam = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    "List the 5 most common mistakes students make in " + exam + " " + subject +
                    " that cost them marks. For each mistake explain what it is, "
                    "why students make it, and exactly how to avoid it. Be specific and practical."
                )}
            ]
        )
        await update.message.reply_text(
            "⚠️ Common Mistakes — " + exam + " " + subject + "\n\n" +
            response.choices[0].message.content
        )
    except Exception as e:
        print("TRAPS ERROR: " + str(e))
        await update.message.reply_text("Could not load this. Please try again.")


async def timetable_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exam = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    "Create a practical and realistic study timetable template for a Nigerian student "
                    "preparing for " + exam + " with 8 subjects over 8 weeks. "
                    "Consider that students may have school during the day and limited electricity at night. "
                    "Include time for rest and revision. Make it structured and easy to follow."
                )}
            ]
        )
        await update.message.reply_text(
            "📅 " + exam + " Study Timetable Guide\n\n" +
            response.choices[0].message.content
        )
    except Exception as e:
        print("TIMETABLE ERROR: " + str(e))
        await update.message.reply_text("Could not generate timetable. Please try again.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    first_name = query.from_user.first_name

    if query.data.startswith("exam_"):
        exam = query.data.replace("exam_", "")
        USER_EXAMS[user_id] = exam
        await query.edit_message_text(
            "Exam set to " + exam + ".\n\n"
            "Now select your subject, " + first_name + ":",
            reply_markup=subject_keyboard()
        )

    elif query.data.startswith("sub_"):
        subject = query.data.replace("sub_", "")
        USER_SUBJECTS[user_id] = subject
        exam = USER_EXAMS.get(user_id, "WAEC")
        await query.edit_message_text(
            "Ready. Exam: " + exam + " | Subject: " + subject + "\n\n"
            "You can now:\n"
            "- Type any question or topic\n"
            "/quiz — Practice question\n"
            "/syllabus — Topic list\n"
            "/tips — Exam technique\n"
            "/traps — Common mistakes\n"
            "/timetable — Study plan\n"
            "/exam — Change exam type"
        )

    elif query.data.startswith("quiz_"):
        selected = query.data.replace("quiz_", "")
        quiz_data = QUIZ_QUESTIONS.get(user_id)

        if not quiz_data:
            await query.edit_message_text("This quiz has expired. Use /quiz for a new question.")
            return

        correct = quiz_data["answer"]
        explanation = quiz_data["explanation"]

        if selected == correct:
            result = (
                "Correct! Well done.\n\n"
                "Explanation:\n" + explanation +
                "\n\nUse /quiz for another question."
            )
        else:
            result = (
                "Incorrect. You selected " + selected + ". The correct answer is " + correct + ".\n\n"
                "Explanation:\n" + explanation +
                "\n\nStudy this carefully then use /quiz to try again."
            )

        await query.edit_message_text(result)
        QUIZ_QUESTIONS.pop(user_id, None)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_message = update.message.text
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    subject = USER_SUBJECTS.get(user_id, "")
    exam = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    context_line = ""
    if subject and exam:
        context_line = first_name + " is preparing for " + exam + " and is currently studying " + subject + ". "

    message_prompt = (
        context_line + first_name + " asks: " + student_message + "\n\n"
        "Respond with:\n"
        "1. A clear definition or introduction\n"
        "2. Key principles or theory\n"
        "3. Step by step working or detailed explanation\n"
        "4. A worked example if applicable\n"
        "5. A summary and one key exam point to remember\n"
        "Keep the response clear and easy to read on a mobile phone."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message_prompt}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        print("GROQ ERROR: " + str(e))
        await update.message.reply_text("An error occurred. Please try again.")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subject", subject_command))
    app.add_handler(CommandHandler("exam", exam_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("tips", tips_command))
    app.add_handler(CommandHandler("syllabus", syllabus_command))
    app.add_handler(CommandHandler("traps", traps_command))
    app.add_handler(CommandHandler("timetable", timetable_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ExamAI bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
