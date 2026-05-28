import os
import io
import re
import logging
import textwrap
from PIL import Image, ImageDraw, ImageFont
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

# ─── Brand colours ───────────────────────────────────────────────────────────
BRAND_BG        = (10,  20,  50)   # deep navy
BRAND_ACCENT    = (0,  200, 160)   # teal/green
BRAND_TEXT      = (240, 245, 255)  # near-white
BRAND_SUBTEXT   = (160, 180, 210)  # muted blue-grey
BRAND_LINE      = (0,  160, 130)   # slightly darker teal for dividers
BRAND_NAME      = "Learnly"

# ─── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Learnly, a highly experienced and engaging academic tutor for Nigerian secondary school students preparing for WAEC, NECO and JAMB examinations.

Your teaching personality:
- Speak like a brilliant, encouraging teacher who genuinely wants the student to understand
- NEVER use robotic labels like "Definition:", "Key Principles:", "Step by Step Working:" — these are cold and disconnected
- Instead use natural conversational teaching language like:
  "Let's break this down...", "First, let's understand what's happening here...",
  "Now here's where it gets interesting...", "The key thing to notice is...",
  "Let's solve this together...", "Watch what happens when we...",
  "A lot of students miss this part — pay attention here...",
  "Before we calculate, let's think about what the question is really asking..."
- Guide the student through the problem as if you are sitting beside them
- For calculations: work through every single step clearly with correct mathematics — double check every calculation before responding
- Call out examiner traps naturally: "This is exactly where most students lose marks..."
- End naturally: "So the final answer is... and that's what the examiner wants to see."
- Be warm, confident and precise
- Keep responses readable on a mobile phone screen
- For JAMB: remind students about time management naturally within your explanation
- Always verify your mathematical workings twice before sending
- Reference the WAEC, NECO or JAMB syllabus where relevant"""

SUBJECTS = [
    "Mathematics", "Physics", "Chemistry", "Biology",
    "English Language", "Economics", "Government",
    "Literature in English", "Geography", "Commerce",
    "Civic Education", "Agricultural Science", "Further Mathematics"
]

# Subjects that are likely to involve heavy calculations
CALC_SUBJECTS = {
    "Mathematics", "Physics", "Chemistry", "Further Mathematics",
    "Economics", "Agricultural Science"
}

SYLLABUS = {
    "Mathematics": [
        "Number and Numeration", "Algebraic Processes", "Mensuration",
        "Plane Geometry", "Trigonometry", "Statistics and Probability",
        "Vectors and Transformation", "Calculus (JAMB)", "Sets"
    ],
    "Physics": [
        "Measurements and Units", "Motion", "Forces", "Work Energy and Power",
        "Waves", "Optics", "Electricity", "Magnetism",
        "Atomic and Nuclear Physics", "Electronics"
    ],
    "Chemistry": [
        "Separation of Mixtures", "Atomic Structure", "Chemical Bonding",
        "Acids Bases and Salts", "Redox Reactions", "Organic Chemistry",
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
USER_SUBJECTS  = {}
USER_EXAMS     = {}

logging.basicConfig(level=logging.INFO)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def subject_keyboard():
    keyboard, row = [], []
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


def contains_calculation(text: str) -> bool:
    """Return True if the text has step-by-step workings or numeric computation."""
    calc_patterns = [
        r"=\s*[-\d]",          # equations with results  e.g.  = 45
        r"\d+\s*[×x\*\/\+\-]\s*\d+",  # arithmetic ops
        r"Step\s*\d",           # Step 1, Step 2 …
        r"∴|therefore|hence",
        r"[A-Za-z]\s*=\s*\d",  # variable assignment  v = 20
        r"\d+\s*[²³]",         # powers
        r"√\d",                 # square roots
        r"mol|pH|mole|Newton|Joule|Watt|Pascal|kg|m/s|km/h",  # units
    ]
    for pat in calc_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def render_solution_image(text: str, subject: str = "") -> io.BytesIO:
    """
    Render a solution as a branded Learnly image and return a BytesIO PNG.
    """
    FONT_SIZE_BODY   = 28
    FONT_SIZE_HEADER = 36
    FONT_SIZE_BRAND  = 22
    PADDING          = 48
    LINE_SPACING     = 10
    MAX_WIDTH        = 900   # pixels wide
    WRAP_CHARS       = 62    # characters per line before wrapping

    # ── Load fonts (fall back to default if not available) ──
    try:
        font_body   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       FONT_SIZE_BODY)
        font_bold   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  FONT_SIZE_HEADER)
        font_brand  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  FONT_SIZE_BRAND)
        font_mono   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",   FONT_SIZE_BODY)
    except Exception:
        font_body = font_bold = font_brand = font_mono = ImageFont.load_default()

    # ── Prepare lines ──
    raw_lines = text.split("\n")
    wrapped   = []
    for line in raw_lines:
        if len(line) > WRAP_CHARS:
            for chunk in textwrap.wrap(line, WRAP_CHARS):
                wrapped.append(chunk)
        else:
            wrapped.append(line)

    line_h    = FONT_SIZE_BODY + LINE_SPACING
    header_h  = FONT_SIZE_HEADER + 16
    brand_h   = FONT_SIZE_BRAND + 8
    divider_h = 4

    total_h = (
        PADDING               # top pad
        + header_h            # subject header
        + divider_h + 12      # divider + gap
        + len(wrapped) * line_h
        + PADDING             # bottom pad
        + brand_h + 20        # brand footer
    )
    total_h = max(total_h, 200)

    # ── Draw ──
    img  = Image.new("RGB", (MAX_WIDTH, total_h), BRAND_BG)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (MAX_WIDTH, header_h + PADDING)], fill=(15, 30, 70))

    # Subject label
    label = (subject + " — Solution") if subject else "Solution"
    draw.text((PADDING, PADDING // 2 + 4), label, font=font_bold, fill=BRAND_ACCENT)

    y = PADDING + header_h

    # Teal divider
    draw.rectangle([(PADDING, y), (MAX_WIDTH - PADDING, y + divider_h)], fill=BRAND_LINE)
    y += divider_h + 16

    # Body lines
    for line in wrapped:
        # Highlight lines that look like final answers
        is_answer = bool(re.match(r"^\s*(∴|Therefore|Hence|Final answer|Answer)[:\s]", line, re.IGNORECASE))
        color = BRAND_ACCENT if is_answer else BRAND_TEXT
        # Use monospace for lines that are purely calculations
        f = font_mono if re.search(r"[=\+\-\*\/\d]{4,}", line) else font_body
        draw.text((PADDING, y), line, font=f, fill=color)
        y += line_h

    # Brand footer
    footer_y = total_h - brand_h - 16
    draw.rectangle([(0, footer_y - 10), (MAX_WIDTH, total_h)], fill=(8, 16, 40))
    draw.text(
        (PADDING, footer_y),
        BRAND_NAME + " · AI Exam Tutor",
        font=font_brand,
        fill=BRAND_SUBTEXT
    )
    # Accent dot before brand name
    draw.ellipse(
        [(PADDING - 14, footer_y + 6), (PADDING - 4, footer_y + 16)],
        fill=BRAND_ACCENT
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def detect_subject_from_message(message: str) -> str | None:
    """
    Heuristically detect which subject a free-text message belongs to.
    Returns a subject name or None.
    """
    message_lower = message.lower()
    keywords = {
        "Mathematics":        ["equation", "solve", "algebra", "geometry", "trigonometry",
                                "calculus", "matrix", "sets", "logarithm", "quadratic",
                                "factori", "differentiat", "integrat", "probability"],
        "Physics":            ["velocity", "acceleration", "force", "newton", "momentum",
                                "energy", "power", "wave", "optics", "lens", "circuit",
                                "electric", "magnetic", "nuclear", "electron", "proton"],
        "Chemistry":          ["element", "compound", "mole", "atom", "bond", "acid",
                                "base", "salt", "oxidation", "reduction", "organic",
                                "alkane", "alkene", "periodic table", "titration",
                                "equilibrium", "reaction", "pH"],
        "Biology":            ["cell", "photosynthesis", "respiration", "dna", "gene",
                                "chromosome", "evolution", "ecology", "organism",
                                "excretion", "nutrition", "reproduction", "osmosis"],
        "Economics":          ["demand", "supply", "gdp", "inflation", "market",
                                "elasticity", "budget", "trade", "monopoly", "price"],
        "Government":         ["constitution", "democracy", "legislature", "executive",
                                "judiciary", "federalism", "sovereignty", "election"],
        "Further Mathematics":["polynomial", "matrix", "determinant", "vector",
                                "differentiation", "integration", "binomial theorem"],
        "Geography":          ["latitude", "longitude", "erosion", "climate", "rainfall",
                                "population", "map", "contour", "river", "vegetation"],
        "English Language":   ["comprehension", "essay", "grammar", "vocabulary",
                                "synonym", "antonym", "tense", "pronoun", "clause"],
        "Literature in English": ["poem", "stanza", "metaphor", "prose", "drama",
                                   "character", "theme", "plot", "imagery", "novel"],
        "Commerce":           ["trade", "banking", "insurance", "invoice", "receipt",
                                "warehouse", "retailer", "wholesaler"],
        "Civic Education":    ["citizenship", "human rights", "rule of law", "constitution",
                                "democracy", "civic"],
        "Agricultural Science": ["crop", "soil", "fertilizer", "irrigation", "livestock",
                                   "poultry", "farm", "pest", "harvest"],
    }
    scores = {}
    for subject, kws in keywords.items():
        score = sum(1 for kw in kws if kw in message_lower)
        if score > 0:
            scores[subject] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


# ─── Command handlers ────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Welcome, {first_name}! 👋\n\n"
        "I'm *Learnly* — your personal AI tutor for WAEC, NECO and JAMB.\n\n"
        "Here's what I can do:\n"
        "📚 Explain any topic naturally and clearly\n"
        "🔍 Solve past questions with full workings\n"
        "✏️ Give exam-standard practice questions\n"
        "📋 Break down your full subject syllabus\n"
        "📝 Generate structured study notes\n"
        "💡 Share proven exam tips & strategies\n"
        "⚠️ Warn you about common examiner traps\n"
        "📅 Help you build a study timetable\n\n"
        "Which exam are you preparing for?",
        parse_mode="Markdown",
        reply_markup=exam_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Learnly Commands*\n\n"
        "/start — Set your exam and subject\n"
        "/subject — Change subject\n"
        "/exam — Change exam type\n"
        "/notes — Generate structured notes on a topic\n"
        "/quiz — Practice question with marking\n"
        "/syllabus — Full topic list for your subject\n"
        "/tips — Exam tips and technique\n"
        "/traps — Common mistakes to avoid\n"
        "/timetable — Build your study plan\n\n"
        "Or simply type any question directly — I'll detect the subject automatically.",
        parse_mode="Markdown"
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
    exam    = USER_EXAMS.get(user_id, "WAEC")

    if not subject:
        await update.message.reply_text("Please select a subject first using /subject")
        return

    topics     = SYLLABUS.get(subject, [])
    topic_list = "\n".join(["• " + t for t in topics])

    await update.message.reply_text(
        f"*{exam} {subject} — Syllabus Topics*\n\n{topic_list}\n\n"
        "Ask me about any of these topics for a full explanation.",
        parse_mode="Markdown"
    )


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate structured, saveable notes for a topic."""
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id)
    exam    = USER_EXAMS.get(user_id, "WAEC")

    # Allow inline topic: /notes Quadratic Equations
    args  = context.args
    topic = " ".join(args).strip() if args else ""

    if not subject and not topic:
        await update.message.reply_text(
            "Please select a subject first with /subject, "
            "or specify a topic directly:\n\n"
            "Example: `/notes Quadratic Equations`",
            parse_mode="Markdown"
        )
        return

    display_topic = topic if topic else subject

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    notes_prompt = (
        f"Create comprehensive {exam} study notes on: *{display_topic}*"
        + (f" (subject: {subject})" if subject else "") +
        "\n\nFormat the notes EXACTLY like this — use these exact section headers:\n\n"
        "📌 TOPIC: [topic name]\n\n"
        "🔑 KEY CONCEPTS\n"
        "[3-5 core concepts explained in plain language, one per line]\n\n"
        "📖 DETAILED EXPLANATION\n"
        "[Clear, natural explanation as if talking to the student. No robotic labels.]\n\n"
        "💡 WORKED EXAMPLES\n"
        "[1-2 worked examples with full step-by-step solutions]\n\n"
        "⚠️ COMMON MISTAKES\n"
        "[2-3 mistakes students make in exams on this topic]\n\n"
        "✅ QUICK SUMMARY\n"
        "[3-5 bullet points the student should remember walking into the exam]\n\n"
        "Keep language clear, direct and encouraging. Mobile-friendly length."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": notes_prompt}
            ]
        )
        notes_text = response.choices[0].message.content

        # If the notes contain worked examples with calculations, render as image
        if contains_calculation(notes_text) and subject in CALC_SUBJECTS:
            await update.message.reply_text(
                f"📝 *Notes: {display_topic}*\n\nGenerating your notes image...",
                parse_mode="Markdown"
            )
            img_buf = render_solution_image(notes_text, subject or display_topic)
            await update.message.reply_photo(
                photo=img_buf,
                caption=f"📝 *{BRAND_NAME} Notes — {display_topic}*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(notes_text)

    except Exception as e:
        logging.error(f"NOTES ERROR: {e}")
        await update.message.reply_text("Could not generate notes. Please try again.")


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id)
    exam    = USER_EXAMS.get(user_id, "WAEC")

    if not subject:
        await update.message.reply_text("Please select a subject first using /subject")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    quiz_prompt = (
        f"Generate one authentic {exam} standard multiple choice question on {subject}.\n\n"
        "Requirements:\n"
        f"- Match the exact difficulty, style and language of real {exam} past questions\n"
        "- Test application and deep understanding, not just recall\n"
        "- Use precise academic terminology\n"
        f"- Draw strictly from the official {exam} {subject} syllabus\n"
        "- Include one clearly correct answer and three plausible distractors\n"
        "- Double check that your answer and explanation are mathematically correct\n\n"
        "Format exactly as follows:\n"
        "QUESTION: [full question text]\n"
        "A) [option A]\n"
        "B) [option B]\n"
        "C) [option C]\n"
        "D) [option D]\n"
        "ANSWER: [correct letter only]\n"
        "EXPLANATION: [natural conversational explanation]"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": quiz_prompt}
            ]
        )
        quiz_text = response.choices[0].message.content
        lines     = quiz_text.strip().split("\n")

        answer_line      = next((l for l in lines if l.startswith("ANSWER:")),      None)
        explanation_line = next((l for l in lines if l.startswith("EXPLANATION:")), None)

        correct     = answer_line.replace("ANSWER:", "").strip()      if answer_line      else "A"
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
            f"📝 *{exam} Practice — {subject}*\n\n{question_text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logging.error(f"QUIZ ERROR: {e}")
        await update.message.reply_text("Could not generate question. Please try again.")


async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id, "all subjects")
    exam    = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": (
                    f"Give 6 highly specific and practical exam tips for scoring A or B in "
                    f"{exam} {subject}. Focus on time management, question selection strategy, "
                    "how to structure answers, and avoiding unnecessary mark loss. "
                    "Speak directly to the student in a natural encouraging tone."
                )}
            ]
        )
        await update.message.reply_text(
            f"💡 *{exam} Exam Tips — {subject}*\n\n{response.choices[0].message.content}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"TIPS ERROR: {e}")
        await update.message.reply_text("Could not load tips. Please try again.")


async def traps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id, "all subjects")
    exam    = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": (
                    f"List the 5 most common mistakes students make in {exam} {subject} "
                    "that cost them marks. For each mistake explain what it is, why students "
                    "make it, and exactly how to avoid it. Be direct and conversational."
                )}
            ]
        )
        await update.message.reply_text(
            f"⚠️ *Watch Out — {exam} {subject}*\n\n{response.choices[0].message.content}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"TRAPS ERROR: {e}")
        await update.message.reply_text("Could not load this. Please try again.")


async def timetable_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exam    = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": (
                    f"Create a practical 8-week study timetable for a Nigerian student "
                    f"preparing for {exam} with 8 subjects. "
                    "Consider school hours and limited electricity at night. "
                    "Include rest and revision time. Make it feel achievable and encouraging."
                )}
            ]
        )
        await update.message.reply_text(
            f"📅 *Your {exam} Study Plan*\n\n{response.choices[0].message.content}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"TIMETABLE ERROR: {e}")
        await update.message.reply_text("Could not generate timetable. Please try again.")


# ─── Button handler ───────────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    user_id    = query.from_user.id
    first_name = query.from_user.first_name

    if query.data.startswith("exam_"):
        exam = query.data.replace("exam_", "")
        USER_EXAMS[user_id] = exam
        await query.edit_message_text(
            f"Exam set to *{exam}*.\n\nNow select your subject, {first_name}:",
            parse_mode="Markdown",
            reply_markup=subject_keyboard()
        )

    elif query.data.startswith("sub_"):
        subject = query.data.replace("sub_", "")
        USER_SUBJECTS[user_id] = subject
        exam = USER_EXAMS.get(user_id, "WAEC")
        await query.edit_message_text(
            f"All set! *{exam}* | *{subject}*\n\n"
            "You can now:\n"
            "• Type any question directly\n"
            "/notes — Structured topic notes\n"
            "/quiz — Practice question\n"
            "/syllabus — Topic list\n"
            "/tips — Exam technique\n"
            "/traps — Common mistakes\n"
            "/timetable — Study plan\n"
            "/exam — Change exam type\n"
            "/subject — Change subject",
            parse_mode="Markdown"
        )

    elif query.data.startswith("quiz_"):
        selected  = query.data.replace("quiz_", "")
        quiz_data = QUIZ_QUESTIONS.get(user_id)

        if not quiz_data:
            await query.edit_message_text("This quiz has expired. Use /quiz for a new question.")
            return

        correct     = quiz_data["answer"]
        explanation = quiz_data["explanation"]

        if selected == correct:
            result = f"✅ *Correct! Well done.*\n\n{explanation}\n\nUse /quiz for another question."
        else:
            result = (
                f"❌ You selected *{selected}* but the correct answer is *{correct}*.\n\n"
                f"{explanation}\n\nStudy this carefully, then use /quiz to try again."
            )

        await query.edit_message_text(result, parse_mode="Markdown")
        QUIZ_QUESTIONS.pop(user_id, None)

    elif query.data == "switch_subject_yes":
        # Confirm auto-detected subject switch
        pending = context.user_data.get("pending_subject")
        if pending:
            USER_SUBJECTS[user_id] = pending
            context.user_data.pop("pending_subject", None)
            await query.edit_message_text(
                f"Subject switched to *{pending}*. Ask away!",
                parse_mode="Markdown"
            )

    elif query.data == "switch_subject_no":
        context.user_data.pop("pending_subject", None)
        await query.edit_message_text("No problem — subject unchanged.")


# ─── Message handler ──────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_message = update.message.text
    user_id         = update.effective_user.id
    first_name      = update.effective_user.first_name
    subject         = USER_SUBJECTS.get(user_id, "")
    exam            = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # ── Auto-detect subject switch ──
    detected = detect_subject_from_message(student_message)
    if detected and detected != subject and subject:
        # Offer to switch — store pending subject
        context.user_data["pending_subject"] = detected
        keyboard = [[
            InlineKeyboardButton(f"Yes, switch to {detected}", callback_data="switch_subject_yes"),
            InlineKeyboardButton("No, keep current",           callback_data="switch_subject_no"),
        ]]
        await update.message.reply_text(
            f"This looks like a *{detected}* question.\n"
            f"You're currently set to *{subject}*.\n\n"
            "Would you like to switch?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        # Answer the question anyway, under the detected subject
        subject = detected

    context_line = (
        f"{first_name} is preparing for {exam} and is currently studying {subject}. "
        if subject and exam else ""
    )

    message_prompt = (
        f"{context_line}{first_name} asks: {student_message}\n\n"
        "Teach this naturally as a brilliant tutor sitting beside the student. "
        "Walk them through the problem conversationally. "
        "For calculations verify every step twice before responding. "
        "End with the final answer clearly stated and one key exam point."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": message_prompt}
            ]
        )
        reply_text = response.choices[0].message.content

        # ── Render as image if the reply contains calculations ──
        if contains_calculation(reply_text):
            img_buf = render_solution_image(reply_text, subject)
            await update.message.reply_photo(
                photo=img_buf,
                caption=f"📐 *{BRAND_NAME} — {subject} Solution*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(reply_text)

    except Exception as e:
        logging.error(f"GROQ ERROR: {e}")
        await update.message.reply_text("An error occurred. Please try again.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("help",      help_command))
    app.add_handler(CommandHandler("subject",   subject_command))
    app.add_handler(CommandHandler("exam",      exam_command))
    app.add_handler(CommandHandler("notes",     notes_command))
    app.add_handler(CommandHandler("quiz",      quiz_command))
    app.add_handler(CommandHandler("tips",      tips_command))
    app.add_handler(CommandHandler("syllabus",  syllabus_command))
    app.add_handler(CommandHandler("traps",     traps_command))
    app.add_handler(CommandHandler("timetable", timetable_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"{BRAND_NAME} bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
