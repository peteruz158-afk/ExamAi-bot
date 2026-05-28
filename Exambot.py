import os
import io
import re
import base64
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
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# ─── Brand colours ────────────────────────────────────────────────────────────
BRAND_BG     = (10,  20,  50)
BRAND_ACCENT = (0,  200, 160)
BRAND_TEXT   = (240, 245, 255)
BRAND_SUBTEXT= (160, 180, 210)
BRAND_LINE   = (0,  160, 130)
BRAND_NAME   = "Learnly"

# ─── Font sizes (increased for readability) ───────────────────────────────────
FONT_BODY    = 34
FONT_HEADER  = 44
FONT_BRAND   = 28
FONT_MONO    = 34

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
- Reference the WAEC, NECO or JAMB syllabus where relevant
- For casual greetings and non-academic messages: respond naturally and warmly as a friendly tutor, NOT as a study session"""

SUBJECTS = [
    "Mathematics", "Physics", "Chemistry", "Biology",
    "English Language", "Economics", "Government",
    "Literature in English", "Geography", "Commerce",
    "Civic Education", "Agricultural Science", "Further Mathematics"
]

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


# ─── Intent detection ─────────────────────────────────────────────────────────

CASUAL_PATTERNS = [
    r"^(hi|hello|hey|howdy|sup|yo|hiya|good\s*(morning|afternoon|evening|night))\b",
    r"^(how are you|how r u|how are u|hows it going|how do you do)\b",
    r"^(thanks|thank you|thx|ty|thank u)\b",
    r"^(ok|okay|alright|cool|got it|understood|nice)\b",
    r"^(bye|goodbye|see you|cya|later)\b",
    r"^(lol|lmao|haha|😂|😊|🙏)\b",
    r"^(who are you|what are you|what can you do)\b",
]

NOTES_TRIGGER_PATTERNS = [
    r"\b(explain|describe|what is|what are|tell me about|teach me|summarize|overview|notes on|study notes)\b",
    r"\b(definition of|meaning of|concept of|introduction to|basics of)\b",
    r"\b(how does|how do|how is|how are)\b.*(work|function|happen|occur|form|develop)",
]

def is_casual_message(text: str) -> bool:
    text_lower = text.lower().strip()
    for pat in CASUAL_PATTERNS:
        if re.search(pat, text_lower):
            return True
    # Very short messages with no academic keywords
    if len(text_lower.split()) <= 3 and not any(
        kw in text_lower for kw in ["solve", "calculate", "find", "what", "how", "why", "explain"]
    ):
        return True
    return False

def is_notes_request(text: str) -> bool:
    text_lower = text.lower()
    for pat in NOTES_TRIGGER_PATTERNS:
        if re.search(pat, text_lower):
            return True
    return False

def extract_topic_from_message(text: str) -> str:
    """Try to extract the topic from a notes-trigger message."""
    text_lower = text.lower()
    patterns = [
        r"explain\s+(.+)",
        r"what is\s+(.+)",
        r"what are\s+(.+)",
        r"tell me about\s+(.+)",
        r"teach me\s+(?:about\s+)?(.+)",
        r"notes on\s+(.+)",
        r"describe\s+(.+)",
        r"definition of\s+(.+)",
        r"meaning of\s+(.+)",
        r"concept of\s+(.+)",
        r"summarize\s+(.+)",
        r"how does\s+(.+)",
        r"how do\s+(.+)",
        r"overview of\s+(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, text_lower)
        if m:
            topic = m.group(1).strip().rstrip("?.")
            return topic
    return text.strip()

def contains_calculation(text: str) -> bool:
    calc_patterns = [
        r"=\s*[-\d]",
        r"\d+\s*[×x\*\/\+\-]\s*\d+",
        r"Step\s*\d",
        r"∴|therefore|hence",
        r"[A-Za-z]\s*=\s*\d",
        r"\d+\s*[²³]",
        r"√\d",
        r"mol|pH|mole|Newton|Joule|Watt|Pascal|kg|m/s|km/h",
    ]
    for pat in calc_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

def detect_subject_from_message(message: str) -> str | None:
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


# ─── Image renderer ───────────────────────────────────────────────────────────

def render_solution_image(text: str, subject: str = "") -> io.BytesIO:
    PADDING   = 52
    LINE_SP   = 12
    MAX_WIDTH = 1000
    WRAP_CHARS= 58

    try:
        font_body  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      FONT_BODY)
        font_bold  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_HEADER)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_BRAND)
        font_mono  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",  FONT_MONO)
    except Exception:
        font_body = font_bold = font_brand = font_mono = ImageFont.load_default()

    raw_lines = text.split("\n")
    wrapped   = []
    for line in raw_lines:
        if len(line) > WRAP_CHARS:
            for chunk in textwrap.wrap(line, WRAP_CHARS):
                wrapped.append(chunk)
        else:
            wrapped.append(line)

    line_h   = FONT_BODY + LINE_SP
    header_h = FONT_HEADER + 18
    brand_h  = FONT_BRAND + 10

    total_h = PADDING + header_h + 16 + len(wrapped) * line_h + PADDING + brand_h + 20
    total_h = max(total_h, 250)

    img  = Image.new("RGB", (MAX_WIDTH, total_h), BRAND_BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (MAX_WIDTH, header_h + PADDING)], fill=(15, 30, 70))
    label = (subject + " — Solution") if subject else "Solution"
    draw.text((PADDING, PADDING // 2 + 4), label, font=font_bold, fill=BRAND_ACCENT)

    y = PADDING + header_h
    draw.rectangle([(PADDING, y), (MAX_WIDTH - PADDING, y + 4)], fill=BRAND_LINE)
    y += 20

    for line in wrapped:
        is_answer = bool(re.match(
            r"^\s*(∴|Therefore|Hence|Final answer|Answer)[:\s]", line, re.IGNORECASE
        ))
        color = BRAND_ACCENT if is_answer else BRAND_TEXT
        f = font_mono if re.search(r"[=\+\-\*\/\d]{4,}", line) else font_body
        draw.text((PADDING, y), line, font=f, fill=color)
        y += line_h

    footer_y = total_h - brand_h - 16
    draw.rectangle([(0, footer_y - 10), (MAX_WIDTH, total_h)], fill=(8, 16, 40))
    draw.text((PADDING, footer_y), BRAND_NAME + " · AI Exam Tutor",
              font=font_brand, fill=BRAND_SUBTEXT)
    draw.ellipse([(PADDING - 16, footer_y + 6), (PADDING - 4, footer_y + 18)],
                 fill=BRAND_ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─── Notes generator (shared logic) ──────────────────────────────────────────

async def generate_and_send_notes(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   topic: str, subject: str = "", exam: str = "WAEC"):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    notes_prompt = (
        f"Create comprehensive, exam-focused {exam} study notes on: **{topic}**"
        + (f" (subject: {subject})" if subject else "") +
        "\n\nYour notes must be detailed, rich and genuinely useful for a student sitting the exam. "
        "Follow this structure exactly:\n\n"
        f"📌 TOPIC: {topic}\n\n"
        "🔑 KEY CONCEPTS\n"
        "List 4-6 core ideas, each explained in 2-3 sentences of clear, plain language. "
        "No jargon without explanation.\n\n"
        "📖 FULL EXPLANATION\n"
        "Write 3-5 paragraphs explaining the topic conversationally, as if sitting beside the student. "
        "Use analogies, real-world examples from Nigeria where possible. "
        "Build from basics to depth. Never use robotic headers inside this section.\n\n"
        "💡 WORKED EXAMPLES\n"
        "Give 2-3 fully worked examples with complete step-by-step solutions. "
        "For calculations, show every line of working. "
        "For theory topics, give model answers with examiner-level detail.\n\n"
        "⚠️ EXAMINER TRAPS\n"
        "List 3-4 specific mistakes students make on this topic in exams, "
        "why they make them, and exactly how to avoid each one.\n\n"
        "✅ EXAM SUMMARY\n"
        "5-6 bullet points the student must remember walking into the exam hall. "
        "Be specific, not generic.\n\n"
        "Keep language encouraging, direct and mobile-friendly."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": notes_prompt}
            ],
            max_tokens=2000
        )
        notes_text = response.choices[0].message.content

        if contains_calculation(notes_text) and subject in CALC_SUBJECTS:
            img_buf = render_solution_image(notes_text, subject or topic)
            await update.message.reply_photo(
                photo=img_buf,
                caption=f"📝 *{BRAND_NAME} Notes — {topic}*",
                parse_mode="Markdown"
            )
        else:
            # Split long notes into chunks if needed
            if len(notes_text) > 4000:
                chunks = [notes_text[i:i+4000] for i in range(0, len(notes_text), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(notes_text)

    except Exception as e:
        logging.error(f"NOTES ERROR: {e}")
        await update.message.reply_text("Could not generate notes. Please try again.")


# ─── Keyboard helpers ─────────────────────────────────────────────────────────

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
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("WAEC", callback_data="exam_WAEC"),
        InlineKeyboardButton("NECO", callback_data="exam_NECO"),
        InlineKeyboardButton("JAMB", callback_data="exam_JAMB"),
    ]])

def next_quiz_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Next Question ➡️", callback_data="quiz_next")
    ]])


# ─── Command handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Welcome, {first_name}! 👋\n\n"
        "I'm *Learnly* — your personal AI tutor for WAEC, NECO and JAMB.\n\n"
        "📚 Explain any topic\n"
        "🔍 Solve past questions with full workings\n"
        "📝 Generate structured study notes\n"
        "✏️ Exam-standard practice questions\n"
        "💡 Exam tips & strategies\n"
        "⚠️ Common examiner traps\n"
        "📅 Study timetable\n"
        "🖼️ Send me a photo of a question!\n\n"
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
        "/notes [topic] — Study notes on any topic\n"
        "/quiz — Practice question\n"
        "/syllabus — Topic list\n"
        "/tips — Exam technique\n"
        "/traps — Common mistakes\n"
        "/timetable — Study plan\n\n"
        "💬 Or just type any question or topic directly!\n"
        "📸 Send a photo of a question and I'll solve it.",
        parse_mode="Markdown"
    )

async def exam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Which exam are you preparing for?",
                                     reply_markup=exam_keyboard())

async def subject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Select your subject:", reply_markup=subject_keyboard())

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
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id, "")
    exam    = USER_EXAMS.get(user_id, "WAEC")
    args    = context.args
    topic   = " ".join(args).strip() if args else ""

    if not topic and not subject:
        await update.message.reply_text(
            "What topic would you like notes on?\n\n"
            "Example: `/notes Quadratic Equations`\n"
            "Or: `/notes Photosynthesis`\n"
            "Or: `/notes Supply and Demand`",
            parse_mode="Markdown"
        )
        return

    display_topic = topic if topic else subject
    await generate_and_send_notes(update, context, display_topic, subject, exam)

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subject = USER_SUBJECTS.get(user_id)
    exam    = USER_EXAMS.get(user_id, "WAEC")
    if not subject:
        await update.message.reply_text("Please select a subject first using /subject")
        return
    await send_quiz(update, context, user_id, subject, exam)

async def send_quiz(update_or_query, context, user_id, subject, exam):
    """Generate and send a quiz question. Works from both command and callback."""
    # Get the chat_id and send typing action
    if hasattr(update_or_query, 'message') and update_or_query.message:
        chat_id = update_or_query.effective_chat.id
        reply_fn = update_or_query.message.reply_text
    else:
        # Called from callback query
        chat_id = update_or_query.message.chat_id
        reply_fn = update_or_query.message.reply_text

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    quiz_prompt = (
        f"Generate one authentic {exam} past-question standard multiple choice question on {subject}.\n\n"
        "CRITICAL REQUIREMENTS:\n"
        f"- This must match the EXACT difficulty, language style and phrasing of real {exam} past questions\n"
        "- Do NOT create easy or simplified questions. The question must be genuinely challenging\n"
        "- Test deep understanding, application and analysis — NOT simple recall\n"
        "- Include calculation, interpretation or multi-step reasoning where appropriate\n"
        "- Use the precise academic terminology found in official past papers\n"
        f"- Draw strictly from the {exam} {subject} syllabus\n"
        "- All four options must be plausible — distractors should represent common student errors\n"
        "- Verify the correct answer and explanation are 100% accurate before responding\n"
        "- For Mathematics/Physics/Chemistry: include numerical values and units as in real exams\n\n"
        "Format EXACTLY as:\n"
        "QUESTION: [full question text as it would appear in the exam]\n"
        "A) [option A]\n"
        "B) [option B]\n"
        "C) [option C]\n"
        "D) [option D]\n"
        "ANSWER: [correct letter only]\n"
        "EXPLANATION: [thorough explanation of why the answer is correct AND why each wrong option is wrong, "
        "as a tutor speaking directly to the student]"
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

        QUIZ_QUESTIONS[user_id] = {
            "answer": correct,
            "explanation": explanation,
            "subject": subject,
            "exam": exam
        }

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

        await reply_fn(
            f"📝 *{exam} Practice — {subject}*\n\n{question_text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logging.error(f"QUIZ ERROR: {e}")
        await reply_fn("Could not generate question. Please try again.")

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


# ─── Photo/image handler ──────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name
    subject    = USER_SUBJECTS.get(user_id, "")
    exam       = USER_EXAMS.get(user_id, "WAEC")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Get the highest resolution photo
    photo = update.message.photo[-1]
    file  = await context.bot.get_file(photo.file_id)

    # Download image bytes
    img_bytes = await file.download_as_bytearray()
    img_b64   = base64.b64encode(img_bytes).decode("utf-8")

    caption = update.message.caption or ""
    context_line = f"{first_name} is preparing for {exam}" + (f" in {subject}" if subject else "") + ". "

    prompt = (
        f"{context_line}"
        "The student has sent a photo of a question or problem. "
        "Identify what subject and topic this is from. "
        "Then solve it completely with full step-by-step workings, "
        "as a brilliant tutor sitting beside the student. "
        "Verify every calculation twice. "
        "End with the final answer clearly stated and one key exam tip."
        + (f"\n\nStudent's note: {caption}" if caption else "")
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # use vision-capable model if available
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}"
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        )
        reply_text = response.choices[0].message.content

        if contains_calculation(reply_text):
            img_buf = render_solution_image(reply_text, subject)
            await update.message.reply_photo(
                photo=img_buf,
                caption=f"📐 *{BRAND_NAME} — Solution*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(reply_text)

    except Exception as e:
        logging.error(f"PHOTO ERROR: {e}")
        # Fallback: ask user to type out the question
        await update.message.reply_text(
            "I can see your image! Unfortunately I couldn't process it fully right now.\n\n"
            "Could you type out the question for me? I'll solve it completely. 📝"
        )


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
            "• Send a photo of a question 📸\n"
            "/notes [topic] — Study notes\n"
            "/quiz — Practice question\n"
            "/syllabus — Topic list\n"
            "/tips — Exam technique\n"
            "/traps — Common mistakes\n"
            "/timetable — Study plan\n"
            "/exam — Change exam\n"
            "/subject — Change subject",
            parse_mode="Markdown"
        )

    elif query.data.startswith("quiz_") and query.data != "quiz_next":
        selected  = query.data.replace("quiz_", "")
        quiz_data = QUIZ_QUESTIONS.get(user_id)

        if not quiz_data:
            await query.edit_message_text("This quiz has expired. Use /quiz for a new question.")
            return

        correct     = quiz_data["answer"]
        explanation = quiz_data["explanation"]

        if selected == correct:
            result = f"✅ *Correct! Well done.*\n\n{explanation}"
        else:
            result = (
                f"❌ You selected *{selected}* but the correct answer is *{correct}*.\n\n"
                f"{explanation}"
            )

        await query.edit_message_text(
            result,
            parse_mode="Markdown",
            reply_markup=next_quiz_keyboard()
        )

    elif query.data == "quiz_next":
        subject = QUIZ_QUESTIONS.get(user_id, {}).get("subject") or USER_SUBJECTS.get(user_id)
        exam    = QUIZ_QUESTIONS.get(user_id, {}).get("exam") or USER_EXAMS.get(user_id, "WAEC")
        QUIZ_QUESTIONS.pop(user_id, None)
        if not subject:
            await query.message.reply_text("Please select a subject first using /subject")
            return
        await send_quiz(query, context, user_id, subject, exam)

    elif query.data == "switch_subject_yes":
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

    # ── Casual conversation ──
    if is_casual_message(student_message):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": (
                        f"{first_name} says: {student_message}\n\n"
                        "Respond naturally and warmly as a friendly tutor. "
                        "Keep it brief and conversational. "
                        "You can mention you're ready to help with their studies if appropriate."
                    )}
                ],
                max_tokens=200
            )
            await update.message.reply_text(response.choices[0].message.content)
        except Exception as e:
            logging.error(f"CASUAL ERROR: {e}")
            await update.message.reply_text(f"Hey {first_name}! 👋 How can I help with your studies today?")
        return

    # ── Auto-detect notes request ──
    if is_notes_request(student_message):
        topic = extract_topic_from_message(student_message)
        # Auto-detect subject if not set
        detected_subject = detect_subject_from_message(student_message) or subject
        await generate_and_send_notes(update, context, topic, detected_subject, exam)
        return

    # ── Auto-detect subject switch ──
    detected = detect_subject_from_message(student_message)
    if detected and detected != subject and subject:
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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"{BRAND_NAME} bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
