#!/usr/bin/env python3
"""
TELEGRAM MULTI-BOT MANAGEMENT SYSTEM
4 Bots in 1 Script: Advertising, VIP, Group Management, AutoADV
"""

import asyncio
import sqlite3
import random
import time
import json
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatMemberStatus

# ==================== CONFIGURATION ====================
ADV_BOT_TOKEN = "8455931212:AAGOLICokhaKTmqEJKCzDa9gobYnywmlN4"
VIP_BOT_TOKEN = "8233798151:AAFHctdFHjHyJEgxPXGkDQoFRVusjLQMVtU"
GROUP_BOT_TOKEN = "8389675530:AAHJYSKo06qummgk4cm3sgZGj0G8zH1dVKg"
AUTOADV_BOT_TOKEN = "8418940396:AAEg2qqNOInwKfqoQSHQs4xgO4jOu7Qbh9I"

MAIN_GROUP_ID = -1003097566042
VIP_CHANNEL_ID = -1003075027543
COMPANY_RESOURCES_ID = -1003145253219
SCAMMER_EXPOSED_ID = -1002906057259

SUPER_ADMIN_ID = 7578682081
YOUR_USDT_ADDRESS = "TD1gmGWyWqFY5STqZW5PMRqMR46xJhj5rP"
TRONSCAN_API = "https://apilist.tronscan.org/api/transaction/info"

# Toggle this between "DUMMY" and "REAL"
PAYMENT_MODE = "DUMMY"  # Change to "REAL" when going live

# VIP trigger words
VIP_TRIGGERS = ["direct", "company", "sbi", "accounts", "account"]

# Prices
PRICES = {
    "ad": 188,
    "vip": 300,
    "scammer": 0
}

# ==================== DATABASE SETUP ====================
def init_database():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    c = conn.cursor()
    
    # Ads table
    c.execute('''CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        heading TEXT,
        type TEXT,
        description TEXT,
        contact TEXT,
        price_paid REAL,
        created_at TIMESTAMP,
        expires_at TIMESTAMP,
        post_count INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
    )''')
    
    # VIPs table
    c.execute('''CREATE TABLE IF NOT EXISTS vips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        name TEXT,
        phone TEXT,
        email TEXT,
        added_at TIMESTAMP,
        expires_at TIMESTAMP,
        active INTEGER DEFAULT 1
    )''')
    
    # Scammers table
    c.execute('''CREATE TABLE IF NOT EXISTS scammers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER,
        reporter_username TEXT,
        scammer_name TEXT,
        scammer_contact TEXT,
        incident_details TEXT,
        platform TEXT,
        victim_telegram TEXT,
        reported_at TIMESTAMP,
        approved INTEGER DEFAULT 0,
        posted INTEGER DEFAULT 0
    )''')
    
    # Transactions table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        product_type TEXT,
        amount REAL,
        tx_hash TEXT,
        verified INTEGER DEFAULT 0,
        created_at TIMESTAMP,
        verified_at TIMESTAMP
    )''')
    
    # Ban list
    c.execute('''CREATE TABLE IF NOT EXISTS ban_list (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        banned_at TIMESTAMP
    )''')
    
    # User warnings
    c.execute('''CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reason TEXT,
        warned_at TIMESTAMP
    )''')
    
    # Settings
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # Purchase attempts (rate limiting)
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_attempts (
        user_id INTEGER,
        attempt_time TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

init_database()

def get_db():
    return sqlite3.connect('bot_database.db', check_same_thread=False)

# ==================== HELPER FUNCTIONS ====================
def is_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID

async def check_rate_limit(user_id: int) -> bool:
    """Check if user exceeded 3 purchases per hour"""
    conn = get_db()
    c = conn.cursor()
    one_hour_ago = datetime.now() - timedelta(hours=1)
    c.execute('SELECT COUNT(*) FROM purchase_attempts WHERE user_id = ? AND attempt_time > ?',
              (user_id, one_hour_ago))
    count = c.fetchone()[0]
    conn.close()
    return count < 3

def log_purchase_attempt(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO purchase_attempts (user_id, attempt_time) VALUES (?, ?)',
              (user_id, datetime.now()))
    conn.commit()
    conn.close()

def is_banned(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT user_id FROM ban_list WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

async def verify_usdt_payment(tx_hash: str, expected_amount: float) -> bool:
    """Verify USDT payment on TronScan"""
    if PAYMENT_MODE == "DUMMY":
        return True
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{TRONSCAN_API}?hash={tx_hash}") as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                
                # Check if transaction exists and is to our address
                if 'toAddress' in data and data['toAddress'] == YOUR_USDT_ADDRESS:
                    # Check amount (TRC20 USDT has 6 decimals)
                    amount = int(data.get('amount', 0)) / 1_000_000
                    return amount >= expected_amount
    except Exception as e:
        print(f"Payment verification error: {e}")
        return False
    
    return False

def get_active_ads() -> List[Dict]:
    """Get active ads weighted by price"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now()
    c.execute('''SELECT id, user_id, username, heading, type, description, contact, price_paid, post_count 
                 FROM ads WHERE active = 1 AND expires_at > ?''', (now,))
    ads = []
    for row in c.fetchall():
        ads.append({
            'id': row[0],
            'user_id': row[1],
            'username': row[2],
            'heading': row[3],
            'type': row[4],
            'description': row[5],
            'contact': row[6],
            'price_paid': row[7],
            'post_count': row[8]
        })
    conn.close()
    return ads

def format_ad(ad: Dict) -> str:
    """Format ad for posting"""
    return f"""
🚀 **{ad['heading']}** 🚀

📌 **Type:** {ad['type']}
📝 **Description:**
{ad['description']}

📞 **Contact:** {ad['contact']}

✨ *Posted via Premium Ad Service*
"""

# ==================== BOT 1: ADVERTISING BOT ====================
class AdvertisingBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.is_running = False
        self.post_task = None
        
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🎯 **ADVERTISING BOT ACTIVATED!**\n\n"
            "I'm your premium advertising automation system! I post your ads with precision timing "
            "across Main Group and Company Resources.\n\n"
            "💎 **What I Do:**\n"
            "• Auto-post ads every 5-6 minutes\n"
            "• Pin important announcements\n"
            "• Prioritize high-paying advertisers\n"
            "• Track ad performance\n\n"
            "Use /help_ads to see all commands!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def adv_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        self.is_running = True
        await update.message.reply_text(
            "✅ **ADVERTISING ENGINE STARTED!**\n\n"
            "🔄 Auto-posting every 5-6 minutes\n"
            "📊 Weighted rotation active\n"
            "📌 Auto-pinning enabled\n\n"
            "Use /adv_stop to pause anytime.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        if not self.post_task or self.post_task.done():
            self.post_task = asyncio.create_task(self.auto_post_loop())
    
    async def adv_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        self.is_running = False
        await update.message.reply_text(
            "⏸️ **ADVERTISING ENGINE PAUSED**\n\n"
            "All auto-posting stopped. Use /adv_start to resume.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def auto_post_loop(self):
        """Main posting loop with weighted selection"""
        while self.is_running:
            try:
                ads = get_active_ads()
                if not ads:
                    await asyncio.sleep(300)
                    continue
                
                # Weighted random selection based on price_paid
                weights = [ad['price_paid'] for ad in ads]
                selected_ad = random.choices(ads, weights=weights, k=1)[0]
                
                # Post to Main Group
                keyboard = [[
                    InlineKeyboardButton("📢 Post Ads", url=f"https://t.me/YourAutoADVBot"),
                    InlineKeyboardButton("🚨 Scammer Exposed", url=f"https://t.me/YourAutoADVBot")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                msg = await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=format_ad(selected_ad),
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                await self.app.bot.pin_chat_message(MAIN_GROUP_ID, msg.message_id)
                
                # Post to Company Resources
                await self.app.bot.send_message(
                    chat_id=COMPANY_RESOURCES_ID,
                    text=format_ad(selected_ad),
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Update post count
                conn = get_db()
                c = conn.cursor()
                c.execute('UPDATE ads SET post_count = post_count + 1 WHERE id = ?', (selected_ad['id'],))
                conn.commit()
                conn.close()
                
                # Wait 5-6 minutes
                await asyncio.sleep(random.randint(300, 360))
                
            except Exception as e:
                print(f"Auto-post error: {e}")
                await asyncio.sleep(300)
    
    async def adv_post_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        ads = get_active_ads()
        if not ads:
            await update.message.reply_text("❌ No active ads to post!")
            return
        
        selected_ad = random.choice(ads)
        keyboard = [[
            InlineKeyboardButton("📢 Post Ads", url=f"https://t.me/YourAutoADVBot"),
            InlineKeyboardButton("🚨 Scammer Exposed", url=f"https://t.me/YourAutoADVBot")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.app.bot.send_message(
            chat_id=MAIN_GROUP_ID,
            text=format_ad(selected_ad),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        await update.message.reply_text("✅ Ad posted successfully!")
    
    async def adv_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        ads = get_active_ads()
        if not ads:
            await update.message.reply_text("📭 No active ads at the moment.")
            return
        
        msg = "📊 **ACTIVE ADVERTISEMENTS:**\n\n"
        for ad in ads:
            msg += f"🆔 ID: {ad['id']}\n"
            msg += f"👤 User: @{ad['username']}\n"
            msg += f"📌 Heading: {ad['heading']}\n"
            msg += f"💰 Paid: ${ad['price_paid']}\n"
            msg += f"📈 Posts: {ad['post_count']}\n"
            msg += "─────────────\n"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def adv_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*), SUM(post_count) FROM ads WHERE active = 1')
        total_ads, total_posts = c.fetchone()
        conn.close()
        
        msg = f"""
📊 **ADVERTISING STATISTICS**

📢 Active Ads: {total_ads or 0}
🔄 Total Posts: {total_posts or 0}
🎯 Status: {'Running ✅' if self.is_running else 'Paused ⏸️'}
💎 Mode: Weighted Rotation

Use /adv_list to see all active ads.
"""
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def help_ads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if is_admin(update.effective_user.id):
            msg = """
🎯 **ADVERTISING BOT - ADMIN COMMANDS**

**Control:**
/adv_start - Start auto-posting
/adv_stop - Stop auto-posting
/adv_post_now - Force post ad now
/adv_stats - View statistics
/adv_list - Show all active ads
/adv_delete <id> - Delete specific ad
/adv_set_interval <min> - Change interval

**Info:**
/help_ads - This help message
"""
        else:
            msg = """
🎯 **ADVERTISING BOT - USER COMMANDS**

/my_ads - View your active ads
/ad_status <id> - Check ad status
/help_ads - This help message

💡 Want to advertise? Contact @YourAutoADVBot
"""
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_handler))
        self.app.add_handler(CommandHandler("adv_start", self.adv_start))
        self.app.add_handler(CommandHandler("adv_stop", self.adv_stop))
        self.app.add_handler(CommandHandler("adv_post_now", self.adv_post_now))
        self.app.add_handler(CommandHandler("adv_list", self.adv_list))
        self.app.add_handler(CommandHandler("adv_stats", self.adv_stats))
        self.app.add_handler(CommandHandler("help_ads", self.help_ads))

# ==================== BOT 2: VIP BOT ====================
class VIPBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👑 **VIP VERIFICATION SYSTEM ONLINE!**\n\n"
            "I'm your elite membership guardian! I verify VIP status and manage exclusive access.\n\n"
            "💎 **What I Do:**\n"
            "• Auto-verify VIP members in chat\n"
            "• Grant VIP channel access\n"
            "• Monitor trigger words\n"
            "• Track membership expiry\n\n"
            "Use /vip_benefits to learn more!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def check_vip_status(self, user_id: int) -> Optional[Dict]:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM vips WHERE user_id = ? AND active = 1 AND expires_at > ?',
                  (user_id, datetime.now()))
        result = c.fetchone()
        conn.close()
        if result:
            return {
                'user_id': result[1],
                'username': result[2],
                'name': result[3],
                'expires_at': result[6]
            }
        return None
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check messages for VIP triggers"""
        if update.effective_chat.id != MAIN_GROUP_ID:
            return
        
        message = update.message.text
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        # Check if message is >100 chars or contains trigger words
        should_check = len(message) > 100 or any(trigger in message.lower() for trigger in VIP_TRIGGERS)
        
        if should_check:
            vip_info = await self.check_vip_status(user_id)
            if vip_info:
                await update.message.reply_text(
                    f"✅ **VIP VERIFIED**\n\n"
                    f"@{username} is a premium VIP member!\n"
                    f"👑 Status: Active\n"
                    f"⏰ Valid until: {vip_info['expires_at'][:10]}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"❌ **NOT VIP**\n\n"
                    f"@{username} is not a VIP member.\n\n"
                    f"💎 Want VIP access? Use /buy_vip",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    async def check_vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        vip_info = await self.check_vip_status(user_id)
        
        if vip_info:
            await update.message.reply_text(
                f"👑 **YOUR VIP STATUS**\n\n"
                f"✅ Active VIP Member\n"
                f"📛 Name: {vip_info['name']}\n"
                f"⏰ Valid until: {vip_info['expires_at'][:10]}\n\n"
                f"Enjoy your premium benefits!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ You are not a VIP member.\n\n"
                "💎 Upgrade to VIP for exclusive benefits!\n"
                "Use /vip_benefits to learn more.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def vip_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        if len(context.args) < 1:
            await update.message.reply_text("Usage: /vip_add <user_id>")
            return
        
        user_id = int(context.args[0])
        expires_at = datetime.now() + timedelta(days=60)
        
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO vips (user_id, username, name, phone, email, added_at, expires_at, active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)''',
                     (user_id, "Manual_Add", "Manual VIP", "N/A", "N/A", datetime.now(), expires_at))
            conn.commit()
            await update.message.reply_text(f"✅ User {user_id} added as VIP!")
        except sqlite3.IntegrityError:
            await update.message.reply_text("❌ User already exists as VIP!")
        finally:
            conn.close()
    
    async def vip_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT user_id, username, name, expires_at FROM vips WHERE active = 1 AND expires_at > ?',
                  (datetime.now(),))
        vips = c.fetchall()
        conn.close()
        
        if not vips:
            await update.message.reply_text("📭 No active VIPs at the moment.")
            return
        
        msg = "👑 **ACTIVE VIP MEMBERS:**\n\n"
        for vip in vips:
            msg += f"🆔 ID: {vip[0]}\n"
            msg += f"👤 @{vip[1]}\n"
            msg += f"📛 Name: {vip[2]}\n"
            msg += f"⏰ Expires: {vip[3][:10]}\n"
            msg += "─────────────\n"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def vip_benefits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = """
👑 **VIP MEMBERSHIP BENEFITS**

✨ **Exclusive Access:**
• Send messages in VIP-only channel
• Priority support
• Verified badge in main group
• Access to premium resources

💎 **Features:**
• 60-day validity
• Auto-verification in chats
• Special recognition
• Premium community access

💰 **Price:** 300 USDT
📞 **Get VIP:** /buy_vip

Join the elite today! 🚀
"""
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_handler))
        self.app.add_handler(CommandHandler("check_vip", self.check_vip))
        self.app.add_handler(CommandHandler("vip_add", self.vip_add))
        self.app.add_handler(CommandHandler("vip_list", self.vip_list))
        self.app.add_handler(CommandHandler("vip_benefits", self.vip_benefits))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))

# ==================== BOT 3: GROUP MANAGEMENT ====================
class GroupManagementBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🛡️ **GROUP MANAGEMENT SYSTEM ACTIVE!**\n\n"
            "I'm your automated guardian, keeping groups clean and organized!\n\n"
            "⚡ **What I Do:**\n"
            "• Remove long messages (>120 chars)\n"
            "• Verify new members\n"
            "• Enforce join requirements\n"
            "• Ban rule breakers\n\n"
            "Use /rules to see group guidelines!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Monitor messages for length violations"""
        if update.effective_chat.id != MAIN_GROUP_ID:
            return
        
        if update.message.text and len(update.message.text) > 120:
            await update.message.delete()
            await update.message.reply_text(
                f"⚠️ @{update.effective_user.username}, your message was too long!\n"
                f"📏 Limit: 120 characters\n"
                f"📝 Your message: {len(update.message.text)} characters\n\n"
                f"Please keep it concise!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new member joins"""
        for member in update.message.new_chat_members:
            user_id = member.id
            username = member.username or "Unknown"
            
            keyboard = [[
                InlineKeyboardButton("Main Group", url=f"https://t.me/YourMainGroup"),
                InlineKeyboardButton("VIP Channel", url=f"https://t.me/YourVIPChannel")
            ],[
                InlineKeyboardButton("Company Resources", url=f"https://t.me/YourCompanyResources"),
                InlineKeyboardButton("Scammer Exposed", url=f"https://t.me/YourScammerExposed")
            ],[
                InlineKeyboardButton("✅ I've Joined All", callback_data=f"verify_{user_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 Welcome @{username}!\n\n"
                f"🚨 **IMPORTANT:** You must join ALL 4 groups within 60 seconds:\n\n"
                f"1️⃣ Main Group\n"
                f"2️⃣ VIP Channel\n"
                f"3️⃣ Company Resources\n"
                f"4️⃣ Scammer Exposed\n\n"
                f"Click the buttons below to join, then verify!",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Set timer to kick if not verified
            context.job_queue.run_once(
                self.kick_unverified,
                60,
                data={'chat_id': update.effective_chat.id, 'user_id': user_id},
                name=f"kick_{user_id}"
            )
    
    async def kick_unverified(self, context: ContextTypes.DEFAULT_TYPE):
        """Kick users who didn't verify in time"""
        data = context.job.data
        try:
            await context.bot.ban_chat_member(data['chat_id'], data['user_id'])
            await context.bot.unban_chat_member(data['chat_id'], data['user_id'])
            print(f"Kicked unverified user {data['user_id']}")
        except Exception as e:
            print(f"Error kicking user: {e}")
    
    async def rules(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = """
📋 **GROUP RULES**

1️⃣ **Message Length:** Maximum 120 characters
2️⃣ **Join Requirement:** Must join all 4 groups
3️⃣ **No Spam:** Repeated messages will be removed
4️⃣ **Be Respectful:** No harassment or hate speech
5️⃣ **No Scams:** Report scammers to /report_scammer

⚠️ **Violations result in warnings or bans!**

🛡️ Questions? Contact admins.
"""
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def gm_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        if len(context.args) < 1:
            await update.message.reply_text("Usage: /gm_ban <user_id> [reason]")
            return
        
        user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Rule violation"
        
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO ban_list (user_id, reason, banned_at) VALUES (?, ?, ?)',
                  (user_id, reason, datetime.now()))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ User {user_id} has been banned!\nReason: {reason}")
    
    async def gm_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM ban_list')
        banned_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM warnings')
        warnings_count = c.fetchone()[0]
        conn.close()
        
        msg = f"""
📊 **GROUP MANAGEMENT STATISTICS**

🚫 Total Bans: {banned_count}
⚠️ Total Warnings: {warnings_count}
🛡️ Status: Active
📏 Char Limit: 120

Everything running smoothly! 💪
"""
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_handler))
        self.app.add_handler(CommandHandler("rules", self.rules))
        self.app.add_handler(CommandHandler("gm_ban", self.gm_ban))
        self.app.add_handler(CommandHandler("gm_stats", self.gm_stats))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))

# ==================== BOT 4: AutoADV (PAYMENT SYSTEM) ====================
class AutoADVBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.user_states = {}  # Track purchase flows
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[
            InlineKeyboardButton("📢 Buy Advertisement", callback_data="buy_ad"),
            InlineKeyboardButton("👑 Buy VIP", callback_data="buy_vip")
        ],[
            InlineKeyboardButton("🚨 Report Scammer (FREE)", callback_data="report_scammer")
        ],[
            InlineKeyboardButton("💰 View Prices", callback_data="prices"),
            InlineKeyboardButton("📜 My Purchases", callback_data="my_purchases")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🌟 **WELCOME TO AutoADV PAYMENT SYSTEM!** 🌟\n\n"
            "I'm your automated sales and verification assistant! I handle all purchases "
            "with military-grade security and lightning-fast processing.\n\n"
            "💎 **What I Offer:**\n"
            "• Premium Advertisements\n"
            "• VIP Memberships\n"
            "• Scammer Reporting (FREE)\n\n"
            "🔒 **100% Secure USDT Payments**\n"
            "⚡ **Instant Verification**\n"
            "🎯 **24/7 Automated Service**\n\n"
            "Select an option below to get started!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        chat_type = query.message.chat.type
        
        # If in group, redirect to DM
        if chat_type != "private":
            await query.message.reply_text(
                f"✅ Hey @{query.from_user.username}! I've sent you a DM to complete your purchase privately and securely! 🔒",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Delete the message after 1 minute
            context.job_queue.run_once(
                lambda ctx: query.message.delete(),
                60
            )
            
            # Send DM
            await context.bot.send_message(
                chat_id=user_id,
                text="👋 Let's continue here privately! What would you like to purchase?",
                reply_markup=query.message.reply_markup
            )
            return
        
        # Handle callbacks in DM
        if query.data == "buy_ad":
            await self.start_ad_purchase(query, context)
        elif query.data == "buy_vip":
            await self.start_vip_purchase(query, context)
        elif query.data == "report_scammer":
            await self.start_scammer_report(query, context)
        elif query.data == "prices":
            await self.show_prices(query)
        elif query.data == "my_purchases":
            await self.show_purchases(query)
        elif query.data.startswith("confirm_payment_"):
            await self.confirm_payment(query, context)
    
    async def show_prices(self, query):
        msg = f"""
💰 **PRICING INFORMATION**

📢 **Advertisement Package**
• Price: {PRICES['ad']} USDT
• Validity: 10 days
• Auto-posting every 5-6 minutes
• Pinned in Main Group
• Posted in Company Resources

👑 **VIP Membership**
• Price: {PRICES['vip']} USDT
• Validity: 60 days
• Exclusive channel access
• Verified badge
• Priority support

🚨 **Scammer Report**
• Price: FREE ✅
• Instant posting
• Public exposure
• Community protection

🔒 All payments in USDT (TRC20)
⚡ Current Mode: {PAYMENT_MODE}
"""
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def start_ad_purchase(self, query, context):
        user_id = query.from_user.id
        
        # Check rate limit
        if not await check_rate_limit(user_id):
            await query.edit_message_text(
                "⚠️ **RATE LIMIT EXCEEDED**\n\n"
                "You've made too many purchase attempts recently.\n"
                "Please wait 1 hour before trying again.\n\n"
                "This is for your security! 🔒"
            )
            return
        
        # Check if banned
        if is_banned(user_id):
            await query.edit_message_text(
                "🚫 **ACCESS DENIED**\n\n"
                "Your account has been banned from making purchases.\n"
                "Contact admins if you believe this is an error."
            )
            return
        
        log_purchase_attempt(user_id)
        
        self.user_states[user_id] = {'type': 'ad', 'step': 1}
        
        await query.edit_message_text(
            "📢 **ADVERTISEMENT PURCHASE** (Step 1 of 5)\n\n"
            "Let's create your premium advertisement!\n\n"
            "📝 Please send me the **HEADING** for your ad:\n"
            "(Keep it catchy and under 50 characters)\n\n"
            "💡 Example: 🔥 Premium Accounts Available!"
        )
    
    async def start_vip_purchase(self, query, context):
        user_id = query.from_user.id
        
        if not await check_rate_limit(user_id):
            await query.edit_message_text("⚠️ Rate limit exceeded! Wait 1 hour.")
            return
        
        if is_banned(user_id):
            await query.edit_message_text("🚫 You are banned from purchases.")
            return
        
        log_purchase_attempt(user_id)
        
        self.user_states[user_id] = {'type': 'vip', 'step': 1}
        
        await query.edit_message_text(
            "👑 **VIP MEMBERSHIP PURCHASE** (Step 1 of 4)\n\n"
            "Welcome to the elite club!\n\n"
            "📝 Please send me your **FULL NAME**:\n\n"
            "💡 This will be displayed in your VIP profile."
        )
    
    async def start_scammer_report(self, query, context):
        user_id = query.from_user.id
        self.user_states[user_id] = {'type': 'scammer', 'step': 1}
        
        await query.edit_message_text(
            "🚨 **SCAMMER REPORT** (Step 1 of 5)\n\n"
            "Help protect the community!\n\n"
            "📝 Please send me the **SCAMMER'S NAME**:\n\n"
            "💡 Use any name/alias they used."
        )
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle purchase flow messages"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        message_text = update.message.text
        
        # AD PURCHASE FLOW
        if state['type'] == 'ad':
            if state['step'] == 1:
                state['heading'] = message_text
                state['step'] = 2
                await update.message.reply_text(
                    "✅ Heading saved!\n\n"
                    "📢 **ADVERTISEMENT PURCHASE** (Step 2 of 5)\n\n"
                    "📝 Now send me the **TYPE** of your ad:\n\n"
                    "💡 Examples: Service, Product, Job Offer, Announcement"
                )
            
            elif state['step'] == 2:
                state['ad_type'] = message_text
                state['step'] = 3
                await update.message.reply_text(
                    "✅ Type saved!\n\n"
                    "📢 **ADVERTISEMENT PURCHASE** (Step 3 of 5)\n\n"
                    "📝 Send me a detailed **DESCRIPTION**:\n\n"
                    "💡 Explain what you're offering (max 300 characters)"
                )
            
            elif state['step'] == 3:
                state['description'] = message_text
                state['step'] = 4
                await update.message.reply_text(
                    "✅ Description saved!\n\n"
                    "📢 **ADVERTISEMENT PURCHASE** (Step 4 of 5)\n\n"
                    "📝 Send me your **CONTACT INFO**:\n\n"
                    "💡 Telegram username, phone, email, or link"
                )
            
            elif state['step'] == 4:
                state['contact'] = message_text
                state['step'] = 5
                
                preview = f"""
📢 **AD PREVIEW:**

🚀 **{state['heading']}** 🚀

📌 **Type:** {state['ad_type']}
📝 **Description:**
{state['description']}

📞 **Contact:** {state['contact']}
"""
                
                await update.message.reply_text(
                    preview +
                    f"\n\n💰 **Total: {PRICES['ad']} USDT**\n\n"
                    f"📢 **ADVERTISEMENT PURCHASE** (Step 5 of 5)\n\n"
                    f"🔒 **PAYMENT INSTRUCTIONS:**\n\n"
                    f"1️⃣ Send **{PRICES['ad']} USDT (TRC20)** to:\n"
                    f"`{YOUR_USDT_ADDRESS}`\n\n"
                    f"2️⃣ After payment, send me the **TRANSACTION HASH**\n\n"
                    f"⚡ I'll verify it instantly!\n"
                    f"📊 Mode: {PAYMENT_MODE}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif state['step'] == 5:
                tx_hash = message_text.strip()
                
                await update.message.reply_text(
                    "🔄 **VERIFYING PAYMENT...**\n\n"
                    "Please wait while I check the blockchain..."
                )
                
                # Verify payment
                verified = await verify_usdt_payment(tx_hash, PRICES['ad'])
                
                if verified or PAYMENT_MODE == "DUMMY":
                    # Save ad to database
                    conn = get_db()
                    c = conn.cursor()
                    expires_at = datetime.now() + timedelta(days=10)
                    c.execute('''INSERT INTO ads (user_id, username, heading, type, description, contact, 
                                price_paid, created_at, expires_at, active) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                             (user_id, update.effective_user.username, state['heading'], 
                              state['ad_type'], state['description'], state['contact'],
                              PRICES['ad'], datetime.now(), expires_at))
                    
                    # Save transaction
                    c.execute('''INSERT INTO transactions (user_id, username, product_type, amount, tx_hash, 
                                verified, created_at, verified_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)''',
                             (user_id, update.effective_user.username, 'ad', PRICES['ad'], 
                              tx_hash, datetime.now(), datetime.now()))
                    conn.commit()
                    conn.close()
                    
                    await update.message.reply_text(
                        "✅ **PAYMENT VERIFIED!**\n\n"
                        "🎉 Your advertisement is now ACTIVE!\n\n"
                        "📊 **Details:**\n"
                        f"• Validity: 10 days\n"
                        f"• Auto-posting every 5-6 minutes\n"
                        f"• Posted in Main Group + Company Resources\n\n"
                        "Thank you for your purchase! 🚀"
                    )
                    
                    # Announce in main group
                    await context.bot.send_message(
                        chat_id=MAIN_GROUP_ID,
                        text=f"🎉 @{update.effective_user.username} just purchased a Premium Advertisement! 🚀",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    del self.user_states[user_id]
                else:
                    await update.message.reply_text(
                        "❌ **PAYMENT VERIFICATION FAILED**\n\n"
                        "The transaction could not be verified. Possible reasons:\n"
                        "• Incorrect transaction hash\n"
                        "• Wrong amount sent\n"
                        "• Wrong address\n"
                        "• Payment not confirmed yet\n\n"
                        "Please double-check and send the correct transaction hash."
                    )
        
        # VIP PURCHASE FLOW
        elif state['type'] == 'vip':
            if state['step'] == 1:
                state['name'] = message_text
                state['step'] = 2
                await update.message.reply_text(
                    "✅ Name saved!\n\n"
                    "👑 **VIP MEMBERSHIP PURCHASE** (Step 2 of 4)\n\n"
                    "📝 Send me your **PHONE NUMBER**:"
                )
            
            elif state['step'] == 2:
                state['phone'] = message_text
                state['step'] = 3
                await update.message.reply_text(
                    "✅ Phone saved!\n\n"
                    "👑 **VIP MEMBERSHIP PURCHASE** (Step 3 of 4)\n\n"
                    "📝 Send me your **EMAIL ADDRESS**:"
                )
            
            elif state['step'] == 3:
                state['email'] = message_text
                state['step'] = 4
                
                await update.message.reply_text(
                    f"👑 **VIP MEMBERSHIP DETAILS:**\n\n"
                    f"📛 Name: {state['name']}\n"
                    f"📞 Phone: {state['phone']}\n"
                    f"📧 Email: {state['email']}\n\n"
                    f"💰 **Total: {PRICES['vip']} USDT**\n\n"
                    f"👑 **VIP MEMBERSHIP PURCHASE** (Step 4 of 4)\n\n"
                    f"🔒 **PAYMENT INSTRUCTIONS:**\n\n"
                    f"1️⃣ Send **{PRICES['vip']} USDT (TRC20)** to:\n"
                    f"`{YOUR_USDT_ADDRESS}`\n\n"
                    f"2️⃣ After payment, send me the **TRANSACTION HASH**\n\n"
                    f"⚡ I'll verify and activate your VIP immediately!\n"
                    f"📊 Mode: {PAYMENT_MODE}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif state['step'] == 4:
                tx_hash = message_text.strip()
                
                await update.message.reply_text("🔄 Verifying payment...")
                
                verified = await verify_usdt_payment(tx_hash, PRICES['vip'])
                
                if verified or PAYMENT_MODE == "DUMMY":
                    conn = get_db()
                    c = conn.cursor()
                    expires_at = datetime.now() + timedelta(days=60)
                    
                    try:
                        c.execute('''INSERT INTO vips (user_id, username, name, phone, email, 
                                    added_at, expires_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)''',
                                 (user_id, update.effective_user.username, state['name'],
                                  state['phone'], state['email'], datetime.now(), expires_at))
                        
                        c.execute('''INSERT INTO transactions (user_id, username, product_type, amount, 
                                    tx_hash, verified, created_at, verified_at) 
                                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)''',
                                 (user_id, update.effective_user.username, 'vip', PRICES['vip'],
                                  tx_hash, datetime.now(), datetime.now()))
                        conn.commit()
                        
                        await update.message.reply_text(
                            "✅ **PAYMENT VERIFIED!**\n\n"
                            "👑 **WELCOME TO VIP!**\n\n"
                            "🎉 You are now an elite member!\n\n"
                            "💎 **Your Benefits:**\n"
                            "• VIP Channel Access\n"
                            "• Verified Badge\n"
                            "• Priority Support\n"
                            "• 60 Days Validity\n\n"
                            "Enjoy your premium experience! 🌟"
                        )
                        
                        await context.bot.send_message(
                            chat_id=MAIN_GROUP_ID,
                            text=f"👑 @{update.effective_user.username} just became a VIP member! 🎉",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        del self.user_states[user_id]
                    except sqlite3.IntegrityError:
                        await update.message.reply_text(
                            "⚠️ You already have an active VIP membership!"
                        )
                    finally:
                        conn.close()
                else:
                    await update.message.reply_text(
                        "❌ Payment verification failed! Please check the transaction hash."
                    )
        
        # SCAMMER REPORT FLOW
        elif state['type'] == 'scammer':
            if state['step'] == 1:
                state['scammer_name'] = message_text
                state['step'] = 2
                await update.message.reply_text(
                    "✅ Scammer name saved!\n\n"
                    "🚨 **SCAMMER REPORT** (Step 2 of 5)\n\n"
                    "📝 Send me the **SCAMMER'S CONTACT**:\n"
                    "(Telegram, phone, email, or any ID)"
                )
            
            elif state['step'] == 2:
                state['scammer_contact'] = message_text
                state['step'] = 3
                await update.message.reply_text(
                    "✅ Contact saved!\n\n"
                    "🚨 **SCAMMER REPORT** (Step 3 of 5)\n\n"
                    "📝 Describe the **INCIDENT DETAILS**:\n"
                    "(What happened? How much was lost?)"
                )
            
            elif state['step'] == 3:
                state['incident'] = message_text
                state['step'] = 4
                await update.message.reply_text(
                    "✅ Incident details saved!\n\n"
                    "🚨 **SCAMMER REPORT** (Step 4 of 5)\n\n"
                    "📝 Where did the scam occur?\n"
                    "(Platform, group name, channel, website, etc.)"
                )
            
            elif state['step'] == 4:
                state['platform'] = message_text
                state['step'] = 5
                await update.message.reply_text(
                    "✅ Platform saved!\n\n"
                    "🚨 **SCAMMER REPORT** (Step 5 of 5)\n\n"
                    "📝 Send your **TELEGRAM USERNAME** (victim):\n"
                    "(For verification purposes)"
                )
            
            elif state['step'] == 5:
                state['victim_telegram'] = message_text
                
                # Save to database (pending admin approval)
                conn = get_db()
                c = conn.cursor()
                c.execute('''INSERT INTO scammers (reporter_id, reporter_username, scammer_name, 
                            scammer_contact, incident_details, platform, victim_telegram, reported_at) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (user_id, update.effective_user.username, state['scammer_name'],
                          state['scammer_contact'], state['incident'], state['platform'],
                          state['victim_telegram'], datetime.now()))
                report_id = c.lastrowid
                conn.commit()
                conn.close()
                
                await update.message.reply_text(
                    "✅ **REPORT SUBMITTED!**\n\n"
                    "🚨 Your scammer report is under review.\n\n"
                    f"📝 Report ID: {report_id}\n\n"
                    "Admins will verify and post it soon.\n"
                    "Thank you for protecting the community! 🛡️"
                )
                
                # Notify admin
                keyboard = [[
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_scammer_{report_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_scammer_{report_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=SUPER_ADMIN_ID,
                    text=f"""
🚨 **NEW SCAMMER REPORT** (ID: {report_id})

👤 Reporter: @{update.effective_user.username}
🎭 Scammer: {state['scammer_name']}
📞 Contact: {state['scammer_contact']}
📝 Details: {state['incident']}
🌐 Platform: {state['platform']}
👥 Victim: {state['victim_telegram']}

Approve or reject?
""",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                del self.user_states[user_id]
    
    async def show_purchases(self, query):
        user_id = query.from_user.id
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT product_type, amount, created_at FROM transactions WHERE user_id = ? AND verified = 1',
                  (user_id,))
        purchases = c.fetchall()
        conn.close()
        
        if not purchases:
            await query.edit_message_text(
                "📭 **NO PURCHASES YET**\n\n"
                "You haven't made any purchases.\n"
                "Check out our offerings with /start!"
            )
            return
        
        msg = "📜 **YOUR PURCHASE HISTORY:**\n\n"
        for purchase in purchases:
            msg += f"🛍️ {purchase[0].upper()}\n"
            msg += f"💰 Amount: ${purchase[1]} USDT\n"
            msg += f"📅 Date: {purchase[2][:10]}\n"
            msg += "─────────────\n"
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def auto_toggle_payment_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        global PAYMENT_MODE
        PAYMENT_MODE = "REAL" if PAYMENT_MODE == "DUMMY" else "DUMMY"
        
        await update.message.reply_text(
            f"🔄 **PAYMENT MODE CHANGED**\n\n"
            f"Current mode: **{PAYMENT_MODE}**\n\n"
            f"{'⚠️ All payments will be accepted without verification!' if PAYMENT_MODE == 'DUMMY' else '✅ Real blockchain verification enabled!'}"
        )
    
    async def auto_transactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT username, product_type, amount, tx_hash, created_at FROM transactions WHERE verified = 1 ORDER BY created_at DESC LIMIT 10')
        transactions = c.fetchall()
        conn.close()
        
        if not transactions:
            await update.message.reply_text("📭 No transactions yet.")
            return
        
        msg = "💳 **RECENT TRANSACTIONS:**\n\n"
        for tx in transactions:
            msg += f"👤 @{tx[0]}\n"
            msg += f"🛍️ {tx[1].upper()}\n"
            msg += f"💰 ${tx[2]} USDT\n"
            msg += f"🔗 {tx[3][:20]}...\n"
            msg += f"📅 {tx[4][:10]}\n"
            msg += "─────────────\n"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    async def buy_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct command to buy ad"""
        keyboard = [[InlineKeyboardButton("📢 Start Purchase", callback_data="buy_ad")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📢 **ADVERTISEMENT PACKAGE**\n\n"
            f"💰 Price: {PRICES['ad']} USDT\n"
            "⏰ Validity: 10 days\n"
            "📊 Auto-posting every 5-6 minutes\n\n"
            "Ready to boost your business?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def buy_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct command to buy VIP"""
        keyboard = [[InlineKeyboardButton("👑 Start Purchase", callback_data="buy_vip")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👑 **VIP MEMBERSHIP**\n\n"
            f"💰 Price: {PRICES['vip']} USDT\n"
            "⏰ Validity: 60 days\n"
            "💎 Exclusive benefits\n\n"
            "Join the elite today!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def report_scammer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct command to report scammer"""
        keyboard = [[InlineKeyboardButton("🚨 Start Report", callback_data="report_scammer")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🚨 **SCAMMER REPORT (FREE)**\n\n"
            "Help protect the community!\n"
            "Your report will be reviewed by admins.\n\n"
            "Ready to report?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_handler))
        self.app.add_handler(CommandHandler("buy_ad", self.buy_ad_command))
        self.app.add_handler(CommandHandler("buy_vip", self.buy_vip_command))
        self.app.add_handler(CommandHandler("report_scammer", self.report_scammer_command))
        self.app.add_handler(CommandHandler("auto_toggle_payment_mode", self.auto_toggle_payment_mode))
        self.app.add_handler(CommandHandler("auto_transactions", self.auto_transactions))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, self.message_handler))

# ==================== MAIN RUNNER ====================
async def main():
    print("🚀 Initializing Telegram Bot System...")
    print(f"📊 Payment Mode: {PAYMENT_MODE}")
    print("=" * 50)
    
    # Initialize all bots
    adv_bot = AdvertisingBot(ADV_BOT_TOKEN)
    vip_bot = VIPBot(VIP_BOT_TOKEN)
    group_bot = GroupManagementBot(GROUP_BOT_TOKEN)
    autoadv_bot = AutoADVBot(AUTOADV_BOT_TOKEN)
    
    # Setup handlers
    adv_bot.setup_handlers()
    vip_bot.setup_handlers()
    group_bot.setup_handlers()
    autoadv_bot.setup_handlers()
    
    print("✅ Bot 1: Advertising Bot - Ready")
    print("✅ Bot 2: VIP Bot - Ready")
    print("✅ Bot 3: Group Management Bot - Ready")
    print("✅ Bot 4: AutoADV Bot - Ready")
    print("=" * 50)
    print("🎯 All systems operational!")
    print("💎 Super Admin ID:", SUPER_ADMIN_ID)
    print("🔒 USDT Address:", YOUR_USDT_ADDRESS)
    print("=" * 50)
    
    # Initialize all applications
    async with adv_bot.app:
        await adv_bot.app.initialize()
        await adv_bot.app.start()
        
        async with vip_bot.app:
            await vip_bot.app.initialize()
            await vip_bot.app.start()
            
            async with group_bot.app:
                await group_bot.app.initialize()
                await group_bot.app.start()
                
                async with autoadv_bot.app:
                    await autoadv_bot.app.initialize()
                    await autoadv_bot.app.start()
                    
                    print("🌟 All bots are now LIVE!")
                    print("Press Ctrl+C to stop")
                    
                    # Run all bots concurrently
                    await asyncio.gather(
                        adv_bot.app.updater.start_polling(drop_pending_updates=True),
                        vip_bot.app.updater.start_polling(drop_pending_updates=True),
                        group_bot.app.updater.start_polling(drop_pending_updates=True),
                        autoadv_bot.app.updater.start_polling(drop_pending_updates=True)
                    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down all bots...")
        print("👋 Goodbye!")


# ==================== ADDITIONAL ADMIN COMMANDS ====================
# These are additional commands you can add to each bot class

"""
ADDITIONAL COMMANDS TO ADD:

BOT 1 (Advertising Bot) - Add these methods to AdvertisingBot class:

async def adv_delete(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /adv_delete <ad_id>")
        return
    
    ad_id = int(context.args[0])
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE ads SET active = 0 WHERE id = ?', (ad_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Ad {ad_id} deleted!")

async def adv_set_interval(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("⚙️ Interval setting feature coming soon!")

async def adv_pin_toggle(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("📌 Pin toggle feature coming soon!")

async def my_ads(self, update, context):
    user_id = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, heading, post_count, expires_at FROM ads WHERE user_id = ? AND active = 1',
              (user_id,))
    ads = c.fetchall()
    conn.close()
    
    if not ads:
        await update.message.reply_text("📭 You don't have any active ads.")
        return
    
    msg = "📊 **YOUR ACTIVE ADS:**\n\n"
    for ad in ads:
        msg += f"🆔 ID: {ad[0]}\n"
        msg += f"📌 {ad[1]}\n"
        msg += f"📈 Posts: {ad[2]}\n"
        msg += f"⏰ Expires: {ad[3][:10]}\n"
        msg += "─────────────\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# Add to setup_handlers:
# self.app.add_handler(CommandHandler("adv_delete", self.adv_delete))
# self.app.add_handler(CommandHandler("adv_set_interval", self.adv_set_interval))
# self.app.add_handler(CommandHandler("adv_pin_toggle", self.adv_pin_toggle))
# self.app.add_handler(CommandHandler("my_ads", self.my_ads))


BOT 2 (VIP Bot) - Add these methods to VIPBot class:

async def vip_remove(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /vip_remove <user_id>")
        return
    
    user_id = int(context.args[0])
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE vips SET active = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ VIP removed for user {user_id}")

async def vip_extend(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /vip_extend <user_id> <days>")
        return
    
    user_id = int(context.args[0])
    days = int(context.args[1])
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT expires_at FROM vips WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if result:
        current_expiry = datetime.fromisoformat(result[0])
        new_expiry = current_expiry + timedelta(days=days)
        c.execute('UPDATE vips SET expires_at = ? WHERE user_id = ?', (new_expiry, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ Extended VIP by {days} days!")
    else:
        await update.message.reply_text("❌ User not found in VIP database")
    
    conn.close()

async def vip_stats(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM vips WHERE active = 1 AND expires_at > ?', (datetime.now(),))
    active_vips = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM vips WHERE active = 1 AND expires_at <= ?', (datetime.now(),))
    expired_vips = c.fetchone()[0]
    conn.close()
    
    msg = f"""
📊 **VIP STATISTICS**

✅ Active VIPs: {active_vips}
⏰ Expired VIPs: {expired_vips}
💎 Total: {active_vips + expired_vips}

Use /vip_list to see all active VIPs.
"""
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def my_vip_expiry(self, update, context):
    user_id = update.effective_user.id
    vip_info = await self.check_vip_status(user_id)
    
    if vip_info:
        expiry_date = datetime.fromisoformat(vip_info['expires_at'])
        days_left = (expiry_date - datetime.now()).days
        
        await update.message.reply_text(
            f"⏰ **YOUR VIP EXPIRY**\n\n"
            f"📅 Expires on: {vip_info['expires_at'][:10]}\n"
            f"⏳ Days remaining: {days_left}\n\n"
            f"{'⚠️ Renew soon!' if days_left < 7 else '✅ All good!'}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("❌ You are not a VIP member.")

async def check_vip_user(self, update, context):
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /check_vip_user <username>")
        return
    
    username = context.args[0].replace("@", "")
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT user_id, expires_at FROM vips WHERE username = ? AND active = 1 AND expires_at > ?',
              (username, datetime.now()))
    result = c.fetchone()
    conn.close()
    
    if result:
        await update.message.reply_text(
            f"✅ @{username} is a VIP member!\n"
            f"⏰ Valid until: {result[1][:10]}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(f"❌ @{username} is not a VIP member.")

# Add to setup_handlers:
# self.app.add_handler(CommandHandler("vip_remove", self.vip_remove))
# self.app.add_handler(CommandHandler("vip_extend", self.vip_extend))
# self.app.add_handler(CommandHandler("vip_stats", self.vip_stats))
# self.app.add_handler(CommandHandler("my_vip_expiry", self.my_vip_expiry))
# self.app.add_handler(CommandHandler("check_vip_user", self.check_vip_user))


BOT 3 (Group Management) - Add these methods to GroupManagementBot class:

async def gm_unban(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /gm_unban <user_id>")
        return
    
    user_id = int(context.args[0])
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM ban_list WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ User {user_id} unbanned!")

async def gm_kick(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /gm_kick <user_id>")
        return
    
    user_id = int(context.args[0])
    try:
        await context.bot.ban_chat_member(MAIN_GROUP_ID, user_id)
        await context.bot.unban_chat_member(MAIN_GROUP_ID, user_id)
        await update.message.reply_text(f"✅ User {user_id} kicked!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def gm_warn(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /gm_warn <user_id> [reason]")
        return
    
    user_id = int(context.args[0])
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Rule violation"
    
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO warnings (user_id, reason, warned_at) VALUES (?, ?, ?)',
              (user_id, reason, datetime.now()))
    c.execute('SELECT COUNT(*) FROM warnings WHERE user_id = ?', (user_id,))
    warning_count = c.fetchone()[0]
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"⚠️ Warning issued to user {user_id}\n"
        f"📝 Reason: {reason}\n"
        f"🔢 Total warnings: {warning_count}"
    )

async def gm_warnings(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /gm_warnings <user_id>")
        return
    
    user_id = int(context.args[0])
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT reason, warned_at FROM warnings WHERE user_id = ? ORDER BY warned_at DESC',
              (user_id,))
    warnings = c.fetchall()
    conn.close()
    
    if not warnings:
        await update.message.reply_text(f"✅ User {user_id} has no warnings.")
        return
    
    msg = f"⚠️ **WARNINGS FOR USER {user_id}:**\n\n"
    for warning in warnings:
        msg += f"📝 {warning[0]}\n"
        msg += f"📅 {warning[1][:10]}\n"
        msg += "─────────────\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def verify(self, update, context):
    await update.message.reply_text(
        "✅ Manual verification feature coming soon!\n"
        "For now, please join all groups automatically."
    )

async def join_status(self, update, context):
    await update.message.reply_text(
        "📊 Join status check feature coming soon!"
    )

async def help_group(self, update, context):
    msg = """
🛡️ **GROUP MANAGEMENT HELP**

**User Commands:**
/rules - View group rules
/verify - Manual verification
/join_status - Check join status
/help_group - This help message

**Questions?** Contact admins!
"""
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# Add to setup_handlers:
# self.app.add_handler(CommandHandler("gm_unban", self.gm_unban))
# self.app.add_handler(CommandHandler("gm_kick", self.gm_kick))
# self.app.add_handler(CommandHandler("gm_warn", self.gm_warn))
# self.app.add_handler(CommandHandler("gm_warnings", self.gm_warnings))
# self.app.add_handler(CommandHandler("verify", self.verify))
# self.app.add_handler(CommandHandler("join_status", self.join_status))
# self.app.add_handler(CommandHandler("help_group", self.help_group))


BOT 4 (AutoADV) - Add these methods to AutoADVBot class:

async def auto_payment_mode(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    
    await update.message.reply_text(
        f"📊 **CURRENT PAYMENT MODE**\n\n"
        f"Mode: **{PAYMENT_MODE}**\n\n"
        f"{'⚠️ Dummy mode - no real verification' if PAYMENT_MODE == 'DUMMY' else '✅ Real mode - blockchain verification active'}\n\n"
        f"Use /auto_toggle_payment_mode to change."
    )

async def auto_pending(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT user_id, username, product_type, amount, tx_hash FROM transactions WHERE verified = 0')
    pending = c.fetchall()
    conn.close()
    
    if not pending:
        await update.message.reply_text("✅ No pending transactions!")
        return
    
    msg = "⏳ **PENDING TRANSACTIONS:**\n\n"
    for tx in pending:
        msg += f"👤 @{tx[1]}\n"
        msg += f"🛍️ {tx[2].upper()}\n"
        msg += f"💰 ${tx[3]} USDT\n"
        msg += f"🔗 {tx[4][:20]}...\n"
        msg += "─────────────\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def auto_stats(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*), SUM(amount) FROM transactions WHERE verified = 1 AND product_type = "ad"')
    ad_count, ad_revenue = c.fetchone()
    c.execute('SELECT COUNT(*), SUM(amount) FROM transactions WHERE verified = 1 AND product_type = "vip"')
    vip_count, vip_revenue = c.fetchone()
    conn.close()
    
    total_revenue = (ad_revenue or 0) + (vip_revenue or 0)
    
    msg = f"""
📊 **SALES STATISTICS**

📢 **Advertisements:**
• Sold: {ad_count or 0}
• Revenue: ${ad_revenue or 0} USDT

👑 **VIP Memberships:**
• Sold: {vip_count or 0}
• Revenue: ${vip_revenue or 0} USDT

💰 **Total Revenue:** ${total_revenue} USDT

📊 Payment Mode: {PAYMENT_MODE}
"""
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def auto_ban(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /auto_ban <user_id> [reason]")
        return
    
    user_id = int(context.args[0])
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Fraudulent activity"
    
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO ban_list (user_id, reason, banned_at) VALUES (?, ?, ?)',
              (user_id, reason, datetime.now()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ User {user_id} banned from purchases!\nReason: {reason}")

async def auto_unban(self, update, context):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /auto_unban <user_id>")
        return
    
    user_id = int(context.args[0])
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM ban_list WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ User {user_id} unbanned from purchases!")

async def my_purchases(self, update, context):
    user_id = update.effective_user.id
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT product_type, amount, created_at FROM transactions WHERE user_id = ? AND verified = 1 ORDER BY created_at DESC',
              (user_id,))
    purchases = c.fetchall()
    conn.close()
    
    if not purchases:
        await update.message.reply_text("📭 You haven't made any purchases yet.")
        return
    
    msg = "📜 **YOUR PURCHASE HISTORY:**\n\n"
    for purchase in purchases:
        msg += f"🛍️ {purchase[0].upper()}\n"
        msg += f"💰 ${purchase[1]} USDT\n"
        msg += f"📅 {purchase[2][:10]}\n"
        msg += "─────────────\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def prices_command(self, update, context):
    msg = f"""
💰 **PRICING INFORMATION**

📢 **Advertisement:** ${PRICES['ad']} USDT
⏰ Validity: 10 days

👑 **VIP Membership:** ${PRICES['vip']} USDT
⏰ Validity: 60 days

🚨 **Scammer Report:** FREE ✅

💳 Payment: USDT (TRC20)
🔒 Mode: {PAYMENT_MODE}
"""
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def help_buy(self, update, context):
    msg = """
💡 **PURCHASE GUIDE**

**How to Buy:**
1️⃣ Use /buy_ad, /buy_vip, or /report_scammer
2️⃣ Follow the step-by-step prompts
3️⃣ Send USDT to provided address
4️⃣ Submit transaction hash
5️⃣ Get instant verification!

**Payment Methods:**
• USDT (TRC20) only

**Security:**
• All conversations in private DM
• Blockchain verification
• 100% secure & automated

Questions? Just ask!
"""
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# Add to setup_handlers:
# self.app.add_handler(CommandHandler("auto_payment_mode", self.auto_payment_mode))
# self.app.add_handler(CommandHandler("auto_pending", self.auto_pending))
# self.app.add_handler(CommandHandler("auto_stats", self.auto_stats))
# self.app.add_handler(CommandHandler("auto_ban", self.auto_ban))
# self.app.add_handler(CommandHandler("auto_unban", self.auto_unban))
# self.app.add_handler(CommandHandler("my_purchases", self.my_purchases))
# self.app.add_handler(CommandHandler("prices", self.prices_command))
# self.app.add_handler(CommandHandler("help_buy", self.help_buy))
"""
