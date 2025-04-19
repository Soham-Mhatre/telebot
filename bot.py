# ----------------------------------
# bot.py
# ----------------------------------
import os
from datetime import datetime, timezone
import requests
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, db as admin_db
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# --- Load environment variables ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL")

# --- Initialize Gemini ---
genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "models/gemini-1.5-pro-latest"

# --- Initialize Firebase Admin SDK ---
try:
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DATABASE_URL
    })
    root_ref = admin_db.reference('/')
    firebase_initialized = True
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Firebase initialization error: {str(e)}")
    print("Running without Firebase logging")
    firebase_initialized = False

# --- Helper to log interactions ---
def log_interaction(user_id: int, action: str, data: dict = None):
    if not firebase_initialized:
        print(f"Log: User {user_id} - {action} - {data or {}}")
        return

    try:
        entry = {
            'user_id': user_id,
            'action': action,
            'data': data or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        root_ref.child('interactions').push(entry)
    except Exception as e:
        print(f"Logging error: {str(e)}")

# --- Gemini FAQ helper ---
async def ask_gemini(question: str, topic: str = None) -> str:
    try:
        model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        if topic:
            prompt = f"Please answer this question about {topic} laws and regulations in India:\n\n{question}"
        else:
            prompt = question
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini failed: {e}")
        return f"❗️ Sorry, FAQ service is temporarily unavailable. Error: {str(e)[:100]}..."

# --- Main Menu ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("📚 FAQs",    callback_data='menu_faq')],
        [InlineKeyboardButton("🛠️ Tools",   callback_data='menu_tools')],
        [InlineKeyboardButton("🚨 Emergency", callback_data='menu_emergency')],
    ]
    kb = InlineKeyboardMarkup(buttons)
    text = "👮 *Crime Assist Bot*\nSelect an option:"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=kb
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=kb
        )

# --- Start command handler ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_interaction(user_id, 'start')
    await show_main_menu(update, context)

# --- Button handler ---
async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice = query.data
    log_interaction(user_id, 'button_click', {'choice': choice})

    if choice == 'menu_faq':
        buttons = [
            [InlineKeyboardButton("Cybercrime", callback_data='faq_cyber')],
            [InlineKeyboardButton("Fraud",      callback_data='faq_fraud')],
            [InlineKeyboardButton("IPC",        callback_data='faq_ipc')],
            [InlineKeyboardButton("◀️ Back",    callback_data='back_to_main')],
        ]
        await query.edit_message_text(
            "❓ *FAQs Menu*\nChoose a topic:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif choice.startswith('faq_'):
        topic = choice.split('_',1)[1]
        context.user_data['faq_topic'] = topic
        await query.edit_message_text(
            f"💬 *{topic.title()} FAQ*\nPlease type your question:",
            parse_mode="Markdown"
        )

    elif choice == 'menu_tools':
        buttons = [
            [InlineKeyboardButton("IP Lookup", callback_data='tool_ip')],
            [InlineKeyboardButton("Hash Check", callback_data='tool_hash')],
            [InlineKeyboardButton("◀️ Back",   callback_data='back_to_main')],
        ]
        await query.edit_message_text(
            "🛠️ *Tools Menu*\nChoose a tool:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif choice == 'tool_ip':
        context.user_data['awaiting_ip'] = True
        await query.edit_message_text("🔎 Please send an IP address:")

    elif choice == 'tool_hash':
        context.user_data['awaiting_hash'] = True
        await query.edit_message_text("🔑 Please send a file hash:")

    elif choice == 'menu_emergency':
        buttons = [
            [InlineKeyboardButton("◀️ Back to Main Menu", callback_data='back_to_main')],
        ]
        await query.edit_message_text(
            "🚨 *Emergency Contacts*\n"
            "• Police: 100\n"
            "• Women's Helpline: 1091\n"
            "• Cyber Crime: 1930\n"
            "• Ambulance: 102",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif choice == 'back_to_main':
        await show_main_menu(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    await update.message.chat.send_action('typing')

    if 'faq_topic' in context.user_data:
        topic = context.user_data.pop('faq_topic')
        log_interaction(user_id, 'faq_question', {'topic': topic, 'question': text})

        await update.message.reply_text("🔍 Searching for answer...")
        answer = await ask_gemini(text, topic)

        log_interaction(user_id, 'faq_answer', {'topic': topic, 'answer': answer})
        buttons = [[InlineKeyboardButton("📚 Back to FAQs", callback_data='menu_faq')]]
        await update.message.reply_text(answer, reply_markup=InlineKeyboardMarkup(buttons))
        return

    if context.user_data.pop('awaiting_ip', False):
        log_interaction(user_id, 'ip_query', {'ip': text})

        try:
            ip_api = f"http://ip-api.com/json/{text}"
            res = requests.get(ip_api).json()
            if res['status'] == 'success':
                result = f"🌐 IP: {res['query']}\nCity: {res['city']}\nRegion: {res['regionName']}\nCountry: {res['country']}\nISP: {res['isp']}"
            else:
                result = f"⚠️ Error: {res['message']}"
        except Exception as e:
            result = f"❌ Failed to fetch IP info: {e}"

        log_interaction(user_id, 'ip_result', {'result': result})
        buttons = [[InlineKeyboardButton("🛠️ Back to Tools", callback_data='menu_tools')]]
        await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(buttons))
        return

    if context.user_data.pop('awaiting_hash', False):
        log_interaction(user_id, 'hash_query', {'hash': text})
        result = "File hash check: No known threats found (dummy)."
        log_interaction(user_id, 'hash_result', {'result': result})
        buttons = [[InlineKeyboardButton("🛠️ Back to Tools", callback_data='menu_tools')]]
        await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(buttons))
        return

    log_interaction(user_id, 'general_question', {'question': text})
    await update.message.reply_text("🔍 Looking for an answer...")
    answer = await ask_gemini(text)
    log_interaction(user_id, 'general_answer', {'answer': answer})
    buttons = [[InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]]
    await update.message.reply_text(answer, reply_markup=InlineKeyboardMarkup(buttons))

async def error_handler(update, context):
    print(f"Error: {context.error}")
    if update and update.effective_user:
        user_id = update.effective_user.id
        log_interaction(user_id, 'error', {'error_message': str(context.error)})

def main():
    try:
        model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        test_response = model.generate_content("Test message")
        print(f"✅ Gemini API validated successfully with model: {GEMINI_MODEL}")
    except Exception as e:
        print(f"❌ Gemini API key validation failed: {e}")
        print("Please check your GEMINI_API_KEY environment variable")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()