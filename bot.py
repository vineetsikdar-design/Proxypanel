# bot.py
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import re
import time
import duckdb
from datetime import datetime, timedelta
import threading

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = "7830833473:AAF8mB0Vw4QAlLMAtGi3VjNnRuD40sekRWI" # Replace with your bot token
ADMIN_ID = 7216116641
HF_BASE_URL = "https://huggingface.co/datasets/CutehackX/hitek-data-bucket/resolve/main"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
maintenance_mode = False

# Global DuckDB connection for efficiency
print("Initializing DuckDB Engine...")
duck_con = duckdb.connect(':memory:')
duck_con.execute("INSTALL httpfs; LOAD httpfs;")
print("DuckDB Engine Ready.")

# ==========================================
# DATABASE SETUP (SQLite)
# ==========================================
def init_db():
    with sqlite3.connect('zentrax_bot.sqlite') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (chat_id INTEGER PRIMARY KEY, username TEXT, user_type TEXT, 
                      valid_until DATETIME, searches_left INTEGER, total_searches INTEGER, is_banned INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS coupons
                     (code TEXT PRIMARY KEY, max_uses INTEGER, current_uses INTEGER, 
                      valid_until DATETIME, reward_type TEXT, reward_value INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS searches
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, number TEXT, timestamp DATETIME)''')
        conn.commit()

init_db()

def db_query(query, params=(), fetch=False, fetchall=False):
    with sqlite3.connect('zentrax_bot.sqlite') as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetch:
            return c.fetchone()
        if fetchall:
            return c.fetchall()
        conn.commit()
        return c.lastrowid

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_user(chat_id, username=None):
    user = db_query("SELECT * FROM users WHERE chat_id = ?", (chat_id,), fetch=True)
    if not user:
        db_query("INSERT INTO users (chat_id, username, user_type, searches_left, total_searches, is_banned) VALUES (?, ?, 'FREE', 0, 0, 0)", 
                 (chat_id, username))
        user = db_query("SELECT * FROM users WHERE chat_id = ?", (chat_id,), fetch=True)
    return user

def format_number(val):
    clean = re.sub(r'\D', '', val)
    if len(clean) == 12 and clean.startswith('91'):
        clean = clean[2:]
    if len(clean) > 10 and not clean.startswith('91'):
        clean = clean[:10]
    return clean

def is_authorized(user):
    # Check if banned
    if user[6] == 1:
        return False, "🚫 You are banned from using this bot."
    
    # Check validity (Date)
    if user[2] == 'PAID (Time)':
        if user[3] and datetime.strptime(user[3], '%Y-%m-%d %H:%M:%S') > datetime.now():
            return True, ""
        else:
            db_query("UPDATE users SET user_type = 'FREE' WHERE chat_id = ?", (user[0],))
            return False, "⏳ Your time-based subscription has expired."
    
    # Check validity (Searches)
    if user[2] == 'PAID (Searches)':
        if user[4] > 0:
            return True, ""
        else:
            db_query("UPDATE users SET user_type = 'FREE' WHERE chat_id = ?", (user[0],))
            return False, "🔍 Your search credits are exhausted."
            
    if user[0] == ADMIN_ID:
        return True, ""
        
    return False, "⚠️ You are a FREE user. Please redeem a code or contact admin to search."

# ==========================================
# START & MENUS
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    get_user(message.chat.id, message.from_user.username)
    text = """<pre>𝙳𝙰𝚁𝙺 𝙾𝚂𝙸𝙽𝚃 𝚂𝙴𝙰𝚁𝙲𝙷 𝙱𝙾𝚃 𝚟2.0</pre>

🤖 <b>𝚂𝚈𝚂𝚃𝙴𝙼 𝙾𝙽𝙻𝙸𝙽𝙴...</b>

Welcome to 𝙳𝙰𝚁𝙺 𝙾𝚂𝙸𝙽𝚃 Search Bot v2.0
Unlock the power of Open Source Intelligence.

📡 <b>𝙲𝙰𝙿𝙰𝙱𝙸𝙻𝙸𝚃𝙸𝙴𝚂:</b>
├ 🆔 Caller ID: Instant name retrieval
├ 🌍 Region Info: Circle & Operator details
├ 🛡️ Spam Check: Verify fraud history
└ 📊 HLR Lookup: Live network status

⚡ <b>𝚆𝙷𝚈 𝙲𝙷𝙾𝙾𝚂𝙴 𝚄𝚂?</b>
• Real-time Data Fetching
• Encrypted Search Logs
• 24/7 Server Uptime

⚠️ <b>𝙲𝙾𝙼𝙿𝙻𝙸𝙰𝙽𝙲𝙴:</b>
This tool is designed for educational and security research purposes only.

REGARDS – @zentraxios"""

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👇 𝐓𝐀𝐏 𝐇𝐄𝐑𝐄 𝐓𝐎 𝐂𝐎𝐍𝐓𝐈𝐍𝐔𝐄", callback_data="main_menu"))
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def main_menu(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 Search Number", callback_data="search_num"),
        InlineKeyboardButton("👤 Account Info", callback_data="my_account")
    )
    markup.add(
        InlineKeyboardButton("🎟️ Redeem Code", callback_data="redeem"),
        InlineKeyboardButton("📜 My History", callback_data="history")
    )
    if call.message.chat.id == ADMIN_ID:
        markup.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel"))
        
    bot.edit_message_text("<b>🎛️ MAIN MENU</b>\nSelect an operation below:", 
                          chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

# ==========================================
# ACCOUNT & REDEEM
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "my_account")
def account_info(call):
    user = get_user(call.message.chat.id)
    u_type = user[2]
    v_until = user[3] if user[3] else "N/A"
    s_left = user[4]
    t_searches = user[5]
    
    validity_display = f"⏰ USER VALIDITY: Valid until: {v_until}" if "Time" in u_type else f"💎 SEARCH CREDITS: {s_left}"
    if u_type == "FREE":
        validity_display = "❌ NO ACTIVE PLAN"

    text = f"""📊 <b>ACCOUNT INFORMATION</b>

👤 USER TYPE: {u_type}
{validity_display}
🔍 TOTAL SEARCHES: {t_searches}

📞 CONTACT ADMIN FOR SUBSCRIPTION: @zentraxios"""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "redeem")
def ask_redeem(call):
    msg = bot.send_message(call.message.chat.id, "🎟️ Send your Redeem Code:")
    bot.register_next_step_handler(msg, process_redeem)

def process_redeem(message):
    code = message.text.strip()
    coupon = db_query("SELECT * FROM coupons WHERE code = ?", (code,), fetch=True)
    
    if not coupon:
        bot.send_message(message.chat.id, "❌ Invalid Coupon Code.")
        return
        
    c_code, max_uses, current_uses, valid_until, r_type, r_val = coupon
    
    if current_uses >= max_uses:
        bot.send_message(message.chat.id, "❌ This coupon has reached its maximum uses.")
        return
        
    if datetime.strptime(valid_until, '%Y-%m-%d %H:%M:%S') < datetime.now():
        bot.send_message(message.chat.id, "❌ This coupon has expired.")
        return

    # Apply rewards
    db_query("UPDATE coupons SET current_uses = current_uses + 1 WHERE code = ?", (code,))
    
    if r_type == 'DAYS':
        expiry_date = (datetime.now() + timedelta(days=r_val)).strftime('%Y-%m-%d %H:%M:%S')
        db_query("UPDATE users SET user_type = 'PAID (Time)', valid_until = ? WHERE chat_id = ?", (expiry_date, message.chat.id))
        bot.send_message(message.chat.id, f"✅ Code Redeemed! You have unlimited searches until {expiry_date}.")
    elif r_type == 'SEARCHES':
        db_query("UPDATE users SET user_type = 'PAID (Searches)', searches_left = searches_left + ? WHERE chat_id = ?", (r_val, message.chat.id))
        bot.send_message(message.chat.id, f"✅ Code Redeemed! {r_val} searches added to your account.")

    # Notify Admin
    admin_msg = f"""🔔 <b>NEW COUPON REDEMPTION</b>
👤 User: @{message.from_user.username} (ID: {message.chat.id})
🎟️ Code: {code}
🎁 Reward: {r_val} {r_type}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    bot.send_message(ADMIN_ID, admin_msg)

# ==========================================
# SEARCH LOGIC (DUCKDB)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "search_num")
def ask_search(call):
    if maintenance_mode and call.message.chat.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "🛠️ System is under maintenance.", show_alert=True)
        return
        
    user = get_user(call.message.chat.id)
    auth, reason = is_authorized(user)
    if not auth:
        bot.answer_callback_query(call.id, reason, show_alert=True)
        return
        
    msg = bot.send_message(call.message.chat.id, "🔍 <b>Enter Target Number:</b>\n<i>(Formats like +91, spaces, hyphens are automatically fixed)</i>")
    bot.register_next_step_handler(msg, process_search)

def process_search(message):
    if maintenance_mode and message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠️ System is under maintenance.")
        return

    user = get_user(message.chat.id)
    auth, reason = is_authorized(user)
    if not auth:
        bot.send_message(message.chat.id, reason)
        return

    raw_num = message.text
    target_num = format_number(raw_num)

    if len(target_num) != 10:
        bot.send_message(message.chat.id, "❌ Invalid number format. Must resolve to 10 digits.")
        return

    wait_msg = bot.send_message(message.chat.id, "🔄 <i>Querying Remote Parquet Engine...</i>")

    try:
        last_digit = target_num[-1]
        primary_url = f"{HF_BASE_URL}/final_master_shard_{last_digit}.parquet"
        alt_url = f"{HF_BASE_URL}/alt_master_shard_{last_digit}.parquet"
        
        query = f"""
            SELECT *, 'Main' AS _record_type FROM read_parquet('{primary_url}') WHERE mobile = '{target_num}'
            UNION ALL
            SELECT *, 'Alt' AS _record_type FROM read_parquet('{alt_url}') WHERE alt = '{target_num}'
        """
        
        results = duck_con.execute(query).df().to_dict(orient="records")
        
        if not results:
            bot.edit_message_text("❌ No records found in Data Gateway.", chat_id=message.chat.id, message_id=wait_msg.message_id)
        else:
            response_text = f"🎯 <b>TARGET ACQUIRED: {target_num}</b>\n\n"
            for row in results:
                for k, v in row.items():
                    if pd.notna(v) and k != '_record_type':
                        response_text += f"▪️ <b>{str(k).upper()}</b>: <code>{v}</code>\n"
                response_text += "➖➖➖➖➖➖➖➖\n"
            
            bot.edit_message_text(response_text, chat_id=message.chat.id, message_id=wait_msg.message_id)

            # Deduct search if paid by searches
            if user[2] == 'PAID (Searches)' and message.chat.id != ADMIN_ID:
                db_query("UPDATE users SET searches_left = searches_left - 1 WHERE chat_id = ?", (message.chat.id,))
                
            # Log Search & Update Total
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db_query("INSERT INTO searches (chat_id, number, timestamp) VALUES (?, ?, ?)", (message.chat.id, target_num, timestamp))
            db_query("UPDATE users SET total_searches = total_searches + 1 WHERE chat_id = ?", (message.chat.id,))
            
            # Send live log to admin
            if message.chat.id != ADMIN_ID:
                bot.send_message(ADMIN_ID, f"📡 <b>LIVE SEARCH LOG</b>\nUser: @{message.from_user.username}\nQuery: {target_num}")

    except Exception as e:
        bot.edit_message_text(f"⚠️ Gateway Error: System busy or unreachable.", chat_id=message.chat.id, message_id=wait_msg.message_id)
        bot.send_message(ADMIN_ID, f"Error on query {target_num}: {str(e)}")

# ==========================================
# HISTORY & AUDIT
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "history")
def user_history(call):
    searches = db_query("SELECT number, timestamp FROM searches WHERE chat_id = ? ORDER BY id DESC LIMIT 10", (call.message.chat.id,), fetchall=True)
    if not searches:
        text = "📜 You have no search history."
    else:
        text = "📜 <b>YOUR LAST 10 SEARCHES:</b>\n\n"
        for s in searches:
            text += f"📱 <code>{s[0]}</code> | 🕒 {s[1]}\n"
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

# ==========================================
# ADMIN PANEL LOGIC
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel" and call.message.chat.id == ADMIN_ID)
def admin_panel(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Gen Coupon", callback_data="admin_gen_coup"),
        InlineKeyboardButton("🗑️ Manage Coupons", callback_data="admin_manage_coup"),
        InlineKeyboardButton("🔨 Ban/Unban User", callback_data="admin_ban"),
        InlineKeyboardButton("📋 System Audit", callback_data="admin_audit"),
        InlineKeyboardButton("⚙️ Toggle Maintenance", callback_data="admin_maint")
    )
    markup.add(InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
    status = "ON 🔴" if maintenance_mode else "OFF 🟢"
    bot.edit_message_text(f"👑 <b>ZENTRAX ADMIN PANEL</b>\nMaintenance: {status}", 
                          chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_") and call.message.chat.id == ADMIN_ID)
def handle_admin_callbacks(call):
    global maintenance_mode
    action = call.data
    
    if action == "admin_maint":
        maintenance_mode = not maintenance_mode
        bot.answer_callback_query(call.id, f"Maintenance is now {'ON' if maintenance_mode else 'OFF'}")
        admin_panel(call)
        
    elif action == "admin_audit":
        total_users = db_query("SELECT COUNT(*) FROM users", fetch=True)[0]
        total_searches = db_query("SELECT COUNT(*) FROM searches", fetch=True)[0]
        active_coupons = db_query("SELECT COUNT(*) FROM coupons WHERE current_uses < max_uses", fetch=True)[0]
        
        text = f"""📋 <b>SYSTEM AUDIT</b>
👥 Total Users: {total_users}
🔍 Total Searches: {total_searches}
🎟️ Active Coupons: {active_coupons}"""
        bot.send_message(call.message.chat.id, text)
        
    elif action == "admin_gen_coup":
        msg = bot.send_message(call.message.chat.id, "Send coupon params format:\n<code>CODE | MAX_USERS | COUPON_VALID_DAYS | BENEFIT_TYPE(DAYS/SEARCHES) | BENEFIT_AMOUNT</code>\n\nExample:\n<code>ZENTRAX50 | 5 | 2 | SEARCHES | 50</code>")
        bot.register_next_step_handler(msg, gen_coupon_step)

    elif action == "admin_ban":
        msg = bot.send_message(call.message.chat.id, "Send Chat ID to toggle Ban status:")
        bot.register_next_step_handler(msg, ban_step)
        
    elif action == "admin_manage_coup":
        msg = bot.send_message(call.message.chat.id, "Send the exact Coupon Code to revoke/delete:")
        bot.register_next_step_handler(msg, revoke_coupon_step)

def gen_coupon_step(message):
    try:
        parts = [p.strip() for p in message.text.split('|')]
        code, max_uses, valid_days, r_type, r_val = parts[0], int(parts[1]), int(parts[2]), parts[3].upper(), int(parts[4])
        valid_until = (datetime.now() + timedelta(days=valid_days)).strftime('%Y-%m-%d %H:%M:%S')
        
        db_query("INSERT INTO coupons (code, max_uses, current_uses, valid_until, reward_type, reward_value) VALUES (?, ?, 0, ?, ?, ?)",
                 (code, max_uses, valid_until, r_type, r_val))
                 
        bot.send_message(message.chat.id, f"✅ Coupon Created!\nCode: <code>{code}</code>\nMax Users: {max_uses}\nExpires: {valid_until}\nReward: {r_val} {r_type}")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Error creating coupon. Use exact format.")

def ban_step(message):
    try:
        target = int(message.text)
        user = db_query("SELECT is_banned FROM users WHERE chat_id = ?", (target,), fetch=True)
        if not user:
            bot.send_message(message.chat.id, "❌ User not found in DB.")
            return
            
        new_status = 0 if user[0] == 1 else 1
        db_query("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target))
        bot.send_message(message.chat.id, f"✅ User {target} ban status set to: {new_status}")
    except:
        bot.send_message(message.chat.id, "❌ Invalid input.")

def revoke_coupon_step(message):
    code = message.text.strip()
    res = db_query("DELETE FROM coupons WHERE code = ?", (code,))
    bot.send_message(message.chat.id, f"✅ Coupon {code} deleted/revoked. No one else can use it.")

# ==========================================
# LAUNCH BOT
# ==========================================
print("Bot started...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
