import os
import time
import sqlite3
import requests
import telebot
from flask import Flask
from threading import Thread
from telebot import types

# --- إعداد الخادم لإبقاء البوت حياً ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Running ✅"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- الإعدادات ---
API_TOKEN = os.getenv('BOT_TOKEN')
SMM_API_KEY = os.getenv('SMM_API_KEY')
CH_ID = os.getenv('CHANNEL_USERNAME') 
ADMIN_ID = os.getenv('ADMIN_ID')
API_URL = os.getenv('API_URL')

bot = telebot.TeleBot(API_TOKEN, parse_mode="Markdown")

# --- إدارة قاعدة البيانات ---
def get_db_connection():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    return conn

# تهيئة القاعدة
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, 
                       last_sub REAL DEFAULT 0, 
                       last_view REAL DEFAULT 0, 
                       last_react REAL DEFAULT 0)''')
    conn.commit()

def get_total_users():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return 8746 + cursor.fetchone()[0]

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CH_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def main_inline_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 اكسبلور الفيديو", callback_data="ser_sub_16021"),
        types.InlineKeyboardButton("👀 زيادة مشاهدات", callback_data="ser_view_13372"),
        types.InlineKeyboardButton("❤️ لايكات", callback_data="ser_react_16805"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="my_account")
    )
    return markup

# --- لوحة تحكم بسيطة (Admin Panel) ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        total = get_total_users()
        bot.send_message(message.chat.id, f"📊 *إحصائيات البوت:*\n\n• عدد المستخدمين الكلي: `{total}`")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    # حل مشكلة التفاعل (Reactions)
    try:
        bot.set_message_reaction(message.chat.id, message.message_id, [types.ReactionTypeEmoji("🔥")])
    except: pass

    # التحقق من المستخدم وتسجيله
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id=?', (user_id,))
        if cursor.fetchone() is None:
            cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            conn.commit()
            
            # إشعار دخول مستخدم جديد (بالتنسيق المطلوب)
            total = get_total_users()
            admin_msg = (f"👤 *دخول مستخدم جديد لبوتك*\n\n"
                         f"• الاسم: {message.from_user.first_name}\n"
                         f"• المعرف: @{message.from_user.username if message.from_user.username else 'لا يوجد'}\n"
                         f"• الايدي: `{user_id}`\n"
                         f"• الإجمالي: {total} مشترك 🚀")
            try: bot.send_message(ADMIN_ID, admin_msg)
            except: pass

    # التحقق من الاشتراك الإجباري
    if not is_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("مَـدار 📢", url=f"https://t.me/{CH_ID.replace('@','')}"))
        return bot.send_message(message.chat.id, "⚠️ *يجب الاشتراك بالقناة أولاً لتتمكن من استخدام البوت!*", reply_markup=markup)

    # رسالة الترحيب الجديدة
    welcome_text = (f"✨ *أهلاً بك في بوت الخدمات المجانية* ✨\n\n"
                    f"🚀 *يمكنك من خلال البوت زيادة:*\n"
                    f"• تفاعل حسابك التيك توك مجاناً 🆓\n"
                    f"• ارسله لصاحبك يستفاد مثلك\n"
                    f"• 𝚍𝚎𝚟: @E2E12")
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_inline_menu())

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    
    if call.data == "my_account":
        return bot.send_message(call.message.chat.id, f"👤 *بيانات حسابك:*\n• ايدي: `{user_id}`\n• الإجمالي: {get_total_users()} مستخدم")

    if call.data.startswith("ser_"):
        data = call.data.split("_")
        service_type = data[1]
        service_id = data[2]
        column_name = f"last_{service_type}"
        
        # التأكد من عدم تجاوز الوقت
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {column_name} FROM users WHERE user_id=?", (user_id,))
            last_time = cursor.fetchone()[0]
        
        current_time = time.time()
        cooldown = 12 * 3600 # 12 ساعة بالثواني
        
        if (current_time - last_time) < cooldown:
            remaining = int(cooldown - (current_time - last_time))
            bot.answer_callback_query(call.id, f"⏳ متبقي لك: {remaining//3600} ساعة و {(remaining%3600)//60} دقيقة", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "✅ *ارسل الآن رابط الفيديو المطلوبه خدمته:*")
        bot.register_next_step_handler(msg, process_api_request, service_id, column_name)

def process_api_request(message, service_id, column_name):
    if not message.text or not message.text.startswith("http"):
        return bot.send_message(message.chat.id, "❌ *الرابط الذي أرسلته غير صحيح!*")

    payload = {'key': SMM_API_KEY, 'action': 'add', 'service': service_id, 'link': message.text, 'quantity': 100}

    try:
        response = requests.post(API_URL, data=payload, timeout=15)
        res = response.json()
        if "order" in res:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE users SET {column_name}=? WHERE user_id=?", (time.time(), message.from_user.id))
                conn.commit()
            bot.send_message(message.chat.id, f"✅ *تم استلام طلبك بنجاح!*\n• رقم الطلب: `{res['order']}`\n• انتظر اكتمال الطلب خلال دقائق.")
        else:
            bot.send_message(message.chat.id, f"❌ *خطأ من المصدر:* {res.get('error', 'غير معروف')}")
    except:
        bot.send_message(message.chat.id, "⚙️ *هناك مشكلة في الاتصال بالمزود، جرب لاحقاً.*")

if __name__ == "__main__":
    keep_alive()
    # تم تقليل timeout لزيادة استقرار البوت
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
