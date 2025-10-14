"""
🚀 INTERLINK MULTI-BOT SYSTEM
Complete bot ecosystem for group management, VIP verification, advertising, and payment processing.

Author: Claude
Version: 1.0.0
"""

import asyncio
import aiosqlite
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ============================
# 🔧 CONFIGURATION
# ============================

# PAYMENT MODE: "dummy" or "real"
PAYMENT_MODE = "dummy"  # Change to "real" for production

# Bot Tokens
ADV_BOT_TOKEN = "8455931212:AAGOLICokhaKTmqEJKKCzDa9gobYnywmlN4"
VIP_BOT_TOKEN = "8233798151:AAFHctdFHjHyJEgxPXGkDQoFRVusjLQMVtU"
GROUP_BOT_TOKEN = "8389675530:AAHJYSKo06qummgk4cm3sgZGj0G8zH1dVKg"
AUTOADV_BOT_TOKEN = "8418940396:AAEg2qqNOInwKfqoQSHQs4xgO4jOu7Qbh9I"

# Group IDs
MAIN_GROUP_ID = -1003097566042
VIP_CHANNEL_ID = -1003075027543
COMPANY_RESOURCES_ID = -1003145253219
SCAMMER_EXPOSED_ID = -1002906057259

# Payment Config
TRONSCAN_API = "https://apilist.tronscan.org/api/transaction/info"
YOUR_USDT_ADDRESS = "TD1gmGWyWqFY5STqZW5PMRqMR46xJhj5rP"

# Admin User IDs (Add your admin IDs here)
ADMIN_IDS = [123456789]  # Replace with actual admin user IDs

# Database
DB_NAME = "interlink_bots.db"

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================
# 🗄️ DATABASE INITIALIZATION
# ============================

async def init_database():
    """Initialize all database tables"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Advertising Bot Tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ads_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                heading TEXT,
                type TEXT,
                description TEXT,
                contact TEXT,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                post_count INTEGER DEFAULT 0
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ad_config (
                id INTEGER PRIMARY KEY,
                last_post_time TIMESTAMP,
                is_paused INTEGER DEFAULT 0
            )
        """)
        
        # VIP Bot Tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vip_members (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                phone TEXT,
                email TEXT,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Group Management Tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS new_members (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                join_time TIMESTAMP,
                verified INTEGER DEFAULT 0
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                violation_type TEXT,
                timestamp TIMESTAMP,
                warning_count INTEGER DEFAULT 1
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS exempted_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_at TIMESTAMP
            )
        """)
        
        # AutoADV Bot Tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                product_type TEXT,
                amount REAL,
                tx_hash TEXT,
                status TEXT,
                created_at TIMESTAMP,
                data TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                user_id INTEGER PRIMARY KEY,
                product TEXT,
                amount REAL,
                data TEXT,
                created_at TIMESTAMP,
                payment_id TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                user_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP,
                count INTEGER DEFAULT 1
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transaction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tx_hash TEXT,
                verified INTEGER,
                timestamp TIMESTAMP,
                details TEXT
            )
        """)
        
        await db.commit()
        logger.info("✅ Database initialized successfully")

# ============================
# 🤖 1. ADVERTISING BOT
# ============================

class AdvertisingBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.scheduler = AsyncIOScheduler()
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with godly welcome"""
        await update.message.reply_text(
            "🌟 *GREETINGS, MASTER OF ADVERTISING!* 🌟\n\n"
            "I am the *Advertising Bot*, your divine servant in the realm of promotions! "
            "I exist to spread your message across the sacred grounds of your groups.\n\n"
            "✨ *MY DIVINE POWERS:* ✨\n"
            "📢 Auto-posting ads every 5-6 minutes\n"
            "📌 Auto-pinning in Main Group\n"
            "🎯 Showcasing platform upgrades\n"
            "🔄 Rotating purchased advertisements\n\n"
            "⚡ *COMMANDS AT YOUR DISPOSAL:* ⚡\n"
            "/help - View all my divine commands\n"
            "/stats - See advertising statistics\n"
            "/viewqueue - Check pending ads\n\n"
            "Your wish is my command, O Great One! 🙇",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive help with all commands"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        user_commands = """
🌟 *ADVERTISING BOT - COMMAND BIBLE* 🌟

📱 *GENERAL COMMANDS:*
/start - Awaken the advertising god
/help - Divine command reference
/about - Learn about my existence
/status - Current bot status
/stats - Advertising statistics
/viewqueue - See all pending ads
/myads - Your active advertisements
/contact - Contact support

🎯 *AD MANAGEMENT:*
/viewqueue - All ads in queue
/checkad [id] - Check specific ad
/adstats - Detailed ad analytics
/topads - Most viewed ads
"""
        
        admin_commands = """
👑 *ADMIN COMMANDS:*
/pause - Pause all advertising
/resume - Resume advertising
/clearqueue - Clear ad queue
/removead [id] - Remove specific ad
/editad [id] - Edit advertisement
/setinterval [min] - Set post interval
/forcead - Force post next ad
/skipnext - Skip next scheduled ad
/broadcast [msg] - Broadcast message
/adlogs - View posting logs
/resetstats - Reset statistics
/backup - Backup ad database
/restore - Restore from backup
/maintenance - Toggle maintenance mode
/adpreview [id] - Preview ad before posting
/schedulepost [time] - Schedule specific post
/analytics - Deep analytics dashboard
/exportads - Export ads to CSV
/importads - Import ads from file
/pinnext - Pin next ad manually
/unpinlast - Unpin last ad
/setemergency [msg] - Set emergency broadcast
/testpost - Test ad posting
"""
        
        help_text = user_commands
        if is_admin:
            help_text += admin_commands
        
        help_text += "\n💫 *Your command is my sacred duty!* 💫"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show advertising statistics"""
        async with aiosqlite.connect(DB_NAME) as db:
            # Total ads
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue WHERE status='active'")
            active_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue")
            total_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(post_count) FROM ads_queue")
            result = await cursor.fetchone()
            total_posts = result[0] if result[0] else 0
            
            cursor = await db.execute("SELECT last_post_time FROM ad_config WHERE id=1")
            result = await cursor.fetchone()
            last_post = result[0] if result else "Never"
        
        stats_text = f"""
📊 *ADVERTISING EMPIRE STATISTICS* 📊

🎯 *ADVERTISEMENT METRICS:*
▫️ Active Ads: {active_ads}
▫️ Total Ads (All Time): {total_ads}
▫️ Total Posts Delivered: {total_posts}
▫️ Last Posted: {last_post}

🔥 *CURRENT STATUS:*
▫️ Auto-Posting: ✅ ACTIVE
▫️ Interval: 5-6 minutes
▫️ Target Groups: Main + Company Resources

💪 *Your advertising empire grows stronger, Master!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def view_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all ads in queue"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT id, heading, type, expires_at, post_count 
                FROM ads_queue WHERE status='active' 
                ORDER BY created_at DESC LIMIT 10
            """)
            ads = await cursor.fetchall()
        
        if not ads:
            await update.message.reply_text(
                "📭 *The queue is empty, Master!*\n\n"
                "No advertisements await their glorious debut. "
                "The stage is set for new promotions! 🎭",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        queue_text = "📋 *ADVERTISEMENT QUEUE* 📋\n\n"
        for ad in ads:
            queue_text += f"🎯 *ID:* {ad[0]}\n"
            queue_text += f"📌 *Heading:* {ad[1]}\n"
            queue_text += f"🏷️ *Type:* {ad[2]}\n"
            queue_text += f"⏰ *Expires:* {ad[3]}\n"
            queue_text += f"📊 *Posted:* {ad[4]} times\n"
            queue_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(queue_text, parse_mode=ParseMode.MARKDOWN)
    
    async def pause_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause advertising (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE ad_config SET is_paused=1 WHERE id=1")
            await db.commit()
        
        await update.message.reply_text(
            "⏸️ *ADVERTISING PAUSED* ⏸️\n\n"
            "The advertising machine slumbers, O Master! "
            "Use /resume to awaken it once more. 💤",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def resume_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume advertising (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE ad_config SET is_paused=0 WHERE id=1")
            await db.commit()
        
        await update.message.reply_text(
            "▶️ *ADVERTISING RESUMED* ▶️\n\n"
            "The advertising machine roars back to life! "
            "Your promotions shall flow like rivers! 🌊",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def post_advertisement(self):
        """Background task to post advertisements"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                # Check if paused
                cursor = await db.execute("SELECT is_paused FROM ad_config WHERE id=1")
                result = await cursor.fetchone()
                if result and result[0] == 1:
                    return
                
                # Get next ad or use default
                cursor = await db.execute("""
                    SELECT id, heading, type, description, contact 
                    FROM ads_queue 
                    WHERE status='active' AND expires_at > ? 
                    ORDER BY post_count ASC, created_at ASC 
                    LIMIT 1
                """, (datetime.now().isoformat(),))
                ad = await cursor.fetchone()
                
                if ad:
                    # Post purchased ad
                    ad_text = f"""
🎯 *{ad[1]}*

🏷️ *Type:* {ad[2]}
📝 *Description:*
{ad[3]}

📞 *Contact:* {ad[4]}

━━━━━━━━━━━━━━━━
✨ _Posted by Advertising Bot_
"""
                    keyboard = [
                        [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/{AUTOADV_BOT_TOKEN.split(':')[0]}?start=buy_ad")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{AUTOADV_BOT_TOKEN.split(':')[0]}?start=report_scammer")]
                    ]
                    
                    # Update post count
                    await db.execute("UPDATE ads_queue SET post_count=post_count+1 WHERE id=?", (ad[0],))
                else:
                    # Post default ad
                    ad_text = """
🚀 *PLATFORM UPGRADED!* 🚀

🌟 Find genuine companies and opportunities!

🎯 Premium features now available:
✅ Verified companies
✅ Direct contacts
✅ Scammer protection
✅ VIP benefits

━━━━━━━━━━━━━━━━
💎 *Upgrade Your Experience Today!*
"""
                    keyboard = [
                        [InlineKeyboardButton("💎 Join VIP", url=f"https://t.me/{VIP_CHANNEL_ID}")],
                        [InlineKeyboardButton("🏢 Company Resources", url=f"https://t.me/{COMPANY_RESOURCES_ID}")],
                        [InlineKeyboardButton("📢 Post Ad", url=f"https://t.me/{AUTOADV_BOT_TOKEN.split(':')[0]}?start=buy_ad")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{AUTOADV_BOT_TOKEN.split(':')[0]}?start=report_scammer")]
                    ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Post to Main Group and pin
                msg = await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=ad_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                await self.app.bot.pin_chat_message(chat_id=MAIN_GROUP_ID, message_id=msg.message_id)
                
                # Post to Company Resources
                await self.app.bot.send_message(
                    chat_id=COMPANY_RESOURCES_ID,
                    text=ad_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                
                # Update last post time
                await db.execute(
                    "INSERT OR REPLACE INTO ad_config (id, last_post_time) VALUES (1, ?)",
                    (datetime.now().isoformat(),)
                )
                await db.commit()
                
                logger.info("✅ Advertisement posted successfully")
        
        except Exception as e:
            logger.error(f"❌ Error posting advertisement: {e}")
    
    async def setup_scheduler(self):
        """Setup background scheduler for ad posting"""
        self.scheduler.add_job(
            self.post_advertisement,
            'interval',
            minutes=5,
            jitter=60  # Random 0-60 second delay
        )
        self.scheduler.start()
        logger.info("✅ Ad scheduler started")
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("viewqueue", self.view_queue_command))
        self.app.add_handler(CommandHandler("pause", self.pause_ads_command))
        self.app.add_handler(CommandHandler("resume", self.resume_ads_command))
    
    async def run(self):
        """Run the advertising bot"""
        self.setup_handlers()
        await self.setup_scheduler()
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

# ============================
# 🤖 2. VIP BOT
# ============================

class VIPBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.trigger_words = ["direct", "company", "sbi", "accounts", "account"]
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        await update.message.reply_text(
            "👑 *WELCOME TO THE VIP VERIFICATION SYSTEM!* 👑\n\n"
            "I am the *VIP Bot*, guardian of premium status and verifier of excellence!\n\n"
            "✨ *MY DIVINE ABILITIES:* ✨\n"
            "🔍 Instant VIP verification\n"
            "✅ Real-time status checking\n"
            "👥 Member authenticity validation\n"
            "🎫 Exclusive access management\n\n"
            "⚡ *COMMANDS FOR YOUR USE:* ⚡\n"
            "/checkvip @username - Verify anyone's VIP status\n"
            "/myvip - Check your own VIP status\n"
            "/help - All available commands\n\n"
            "Your premium status awaits, O Distinguished One! 🌟",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = """
👑 *VIP BOT - COMMAND SANCTUARY* 👑

🎯 *VERIFICATION COMMANDS:*
/start - Begin your VIP journey
/help - Divine guidance
/checkvip @user - Verify any member
/myvip - Your VIP status
/vipstats - VIP statistics
/viplist - All VIP members (DM only)
/vipbenefits - Learn VIP perks
/renewvip - Renew your VIP status
"""
        
        if is_admin:
            help_text += """
👑 *ADMIN COMMANDS (DM ONLY):*
/addvip [user_id] - Manually add VIP
/removevip [user_id] - Remove VIP status
/extendevip [user_id] [days] - Extend VIP
/vipanalytics - Detailed analytics
/exportvips - Export VIP database
/viprevenue - Revenue statistics
/bulkvip - Bulk VIP operations
/viplogs - Activity logs
/searchvip [query] - Search VIPs
/expiringsoon - VIPs expiring soon
/renewalreminder - Send renewal reminders
/vipbackup - Backup VIP database
/viprestore - Restore VIP database
"""
        
        help_text += "\n💎 *Excellence recognized, premium delivered!* 💎"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def check_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check VIP status of mentioned user"""
        if not context.args:
            await update.message.reply_text(
                "📝 *Usage:* `/checkvip @username`\n\n"
                "Or reply to someone's message with `/checkvip`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Extract user ID (simplified - in production, use proper username resolution)
        username = context.args[0].replace("@", "")
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT name, expires_at, is_active 
                FROM vip_members 
                WHERE username=? AND is_active=1
            """, (username,))
            vip = await cursor.fetchone()
        
        if vip:
            expires = datetime.fromisoformat(vip[1])
            if expires > datetime.now():
                await update.message.reply_text(
                    f"✅ *VIP STATUS CONFIRMED!* ✅\n\n"
                    f"👤 *User:* @{username}\n"
                    f"💎 *Status:* PREMIUM VIP\n"
                    f"📅 *Valid Until:* {expires.strftime('%d/%m/%Y')}\n\n"
                    f"🌟 *This member is verified and trusted!*",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"⚠️ *VIP EXPIRED* ⚠️\n\n"
                    f"@{username} was a VIP member but their subscription has expired.\n\n"
                    f"🔄 They can renew anytime!",
                    parse_mode=ParseMode.MARKDOWN
                )
        else:
            await update.message.reply_text(
                f"❌ *NOT A VIP MEMBER* ❌\n\n"
                f"@{username} is not currently a VIP member.\n\n"
                f"💎 Want VIP benefits? Contact our AutoADV bot!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def my_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check own VIP status"""
        user_id = update.effective_user.id
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT name, phone, email, created_at, expires_at 
                FROM vip_members 
                WHERE user_id=? AND is_active=1
            """, (user_id,))
            vip = await cursor.fetchone()
        
        if vip:
            created = datetime.fromisoformat(vip[3])
            expires = datetime.fromisoformat(vip[4])
            days_left = (expires - datetime.now()).days
            
            status_text = f"""
👑 *YOUR VIP STATUS* 👑

✅ *STATUS:* ACTIVE PREMIUM VIP

📋 *PROFILE:*
▫️ Name: {vip[0]}
▫️ Phone: {vip[1]}
▫️ Email: {vip[2]}

📅 *MEMBERSHIP:*
▫️ Member Since: {created.strftime('%d/%m/%Y')}
▫️ Expires: {expires.strftime('%d/%m/%Y')}
▫️ Days Remaining: {days_left} days

💎 *ACTIVE BENEFITS:*
✅ Verified status badge
✅ Priority support
✅ Exclusive access
✅ No character limits
✅ Direct company contacts

🌟 *You are a valued premium member!*
"""
            await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                "❌ *NO ACTIVE VIP STATUS* ❌\n\n"
                "You are not currently a VIP member.\n\n"
                "💎 *VIP BENEFITS:*\n"
                "✅ Verified badge\n"
                "✅ Priority support\n"
                "✅ Exclusive content\n"
                "✅ No restrictions\n\n"
                "🚀 Upgrade now via our AutoADV bot!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def vip_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all VIP members (Admin only, DM only)"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 This command works in DM only! Send me a private message.")
            return
        
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can access the VIP roster!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT username, name, expires_at 
                FROM vip_members 
                WHERE is_active=1 
                ORDER BY expires_at DESC 
                LIMIT 50
            """)
            vips = await cursor.fetchall()
        
        if not vips:
            await update.message.reply_text("📭 No VIP members found!")
            return
        
        list_text = "👑 *VIP MEMBER ROSTER* 👑\n\n"
        for vip in vips:
            expires = datetime.fromisoformat(vip[2])
            days_left = (expires - datetime.now()).days
            list_text += f"👤 @{vip[0]} ({vip[1]})\n"
            list_text += f"   ⏰ {days_left} days remaining\n\n"
        
        await update.message.reply_text(list_text, parse_mode=ParseMode.MARKDOWN)
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Monitor messages for trigger words and verify VIP status"""
        if update.effective_chat.id != MAIN_GROUP_ID:
            return
        
        message_text = update.message.text.lower() if update.message.text else ""
        
        # Check if message contains trigger words or is long
        triggered = any(word in message_text for word in self.trigger_words)
        is_long = len(message_text) > 100
        
        if not (triggered or is_long):
            return
        
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        # Check VIP status
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT expires_at FROM vip_members 
                WHERE user_id=? AND is_active=1
            """, (user_id,))
            vip = await cursor.fetchone()
        
        if vip:
            expires = datetime.fromisoformat(vip[0])
            if expires > datetime.now():
                # Verified VIP
                await update.message.reply_text(
                    f"✅ *VERIFIED VIP MEMBER* ✅\n\n"
                    f"@{username} is a premium VIP member.\n"
                    f"Valid until: {expires.strftime('%d/%m/%Y')}\n\n"
                    f"🌟 _Trusted and verified!_",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        
        # Not VIP
        await update.message.reply_text(
            f"⚠️ *NOT A VIP MEMBER* ⚠️\n\n"
            f"@{username} is not a VIP member.\n\n"
            f"💎 Upgrade to VIP for:\n"
            f"✅ Verified badge\n"
            f"✅ Priority support\n"
            f"✅ Exclusive access\n\n"
            f"🚀 Contact @AutoADVBot to upgrade!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def setup_handlers(self):
        """Setup all handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("checkvip", self.check_vip_command))
        self.app.add_handler(CommandHandler("myvip", self.my_vip_command))
        self.app.add_handler(CommandHandler("viplist", self.vip_list_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
    
    async def run(self):
        """Run the VIP bot"""
        self.setup_handlers()
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

# ============================
# 🤖 3. GROUP MANAGEMENT BOT
# ============================

class GroupManagementBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.pending_verifications = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        await update.message.reply_text(
            "🛡️ *GUARDIAN OF THE REALM AWAKENS!* 🛡️\n\n"
            "I am the *Group Management Bot*, protector of order and enforcer of harmony!\n\n"
            "⚔️ *MY SACRED DUTIES:* ⚔️\n"
            "🚫 Spam elimination\n"
            "✅ Member verification\n"
            "📏 Message length control\n"
            "👥 Access management\n\n"
            "⚡ *COMMANDS TO COMMAND ME:* ⚡\n"
            "/help - View all commands\n"
            "/verify - Verify your membership\n"
            "/rules - See group rules\n\n"
            "Order shall be maintained, Noble One! 🗡️",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = """
🛡️ *GROUP MANAGEMENT BOT - COMMAND FORTRESS* 🛡️

👥 *USER COMMANDS:*
/start - Awaken the guardian
/help - Command reference
/verify - Verify your membership
/rules - View group rules
/status - Your membership status
/appeal - Appeal a warning
/mywarnings - Check your warnings
/groupinfo - Group information
"""
        
        if is_admin:
            help_text += """
⚔️ *ADMIN COMMANDS (GROUP):*
/kick @user - Remove member
/ban @user [reason] - Ban member
/unban [user_id] - Unban member
/mute @user [duration] - Mute member
/unmute @user - Unmute member
/warn @user [reason] - Warn member
/warnings @user - Check user warnings
/clearwarnings @user - Clear warnings
/exempt @user - Exempt from restrictions
/unexempt @user - Remove exemption
/setmaxlength [chars] - Set max message length
/lockgroup - Lock group (admins only)
/unlockgroup - Unlock group
/announce [message] - Make announcement
/purge [count] - Delete messages
/slowmode [seconds] - Enable slow mode
/rules_set [rules] - Update rules
/memberstats - Member statistics
/activemembers - Most active members
/recentjoins - Recent joins
/massban - Mass ban operations
/exportlogs - Export moderation logs
"""
        
        help_text += "\n⚔️ *Order and harmony preserved!* ⚔️"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new member joins"""
        for member in update.message.new_chat_members:
            if member.is_bot:
                continue
            
            user_id = member.id
            username = member.username or member.first_name
            
            # Store in database
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO new_members (user_id, username, join_time, verified)
                    VALUES (?, ?, ?, 0)
                """, (user_id, username, datetime.now().isoformat()))
                await db.commit()
            
            # Create verification keyboard
            keyboard = [
                [InlineKeyboardButton("✅ Main Group", url=f"https://t.me/{MAIN_GROUP_ID}")],
                [InlineKeyboardButton("💎 VIP Channel", url=f"https://t.me/{VIP_CHANNEL_ID}")],
                [InlineKeyboardButton("🏢 Company Resources", url=f"https://t.me/{COMPANY_RESOURCES_ID}")],
                [InlineKeyboardButton("⚠️ Scammer Exposed", url=f"https://t.me/{SCAMMER_EXPOSED_ID}")],
                [InlineKeyboardButton("✅ I Joined All!", callback_data=f"verify_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_msg = await update.message.reply_text(
                f"🎉 *WELCOME, {username}!* 🎉\n\n"
                f"To unlock messaging, please join ALL our channels:\n\n"
                f"1️⃣ Main Group\n"
                f"2️⃣ VIP Channel\n"
                f"3️⃣ Company Resources\n"
                f"4️⃣ Scammer Exposed\n\n"
                f"⏰ *You have 60 seconds!*\n"
                f"Click the buttons above to join, then click 'I Joined All!'\n\n"
                f"⚠️ *Failure to join = Auto-removal*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # Schedule removal after 60 seconds
            context.job_queue.run_once(
                self.check_verification,
                60,
                data={'user_id': user_id, 'chat_id': update.effective_chat.id, 'msg_id': welcome_msg.message_id}
            )
    
    async def check_verification(self, context: ContextTypes.DEFAULT_TYPE):
        """Check if user verified within time limit"""
        user_id = context.job.data['user_id']
        chat_id = context.job.data['chat_id']
        msg_id = context.job.data['msg_id']
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(
                "SELECT verified FROM new_members WHERE user_id=?",
                (user_id,)
            )
            result = await cursor.fetchone()
        
        if result and result[0] == 0:
            # Not verified, kick user
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.unban_chat_member(chat_id, user_id)  # Kick without ban
                await context.bot.delete_message(chat_id, msg_id)
                await context.bot.send_message(
                    chat_id,
                    f"⏰ User {user_id} was removed for not joining all channels in time."
                )
            except Exception as e:
                logger.error(f"Error kicking user: {e}")
    
    async def verify_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle verification button"""
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.split("_")[1])
        
        if query.from_user.id != user_id:
            await query.answer("⛔ This button is not for you!", show_alert=True)
            return
        
        # Check membership in all channels
        all_joined = True
        channels = [MAIN_GROUP_ID, VIP_CHANNEL_ID, COMPANY_RESOURCES_ID, SCAMMER_EXPOSED_ID]
        
        for channel_id in channels:
            try:
                member = await context.bot.get_chat_member(channel_id, user_id)
                if member.status in ['left', 'kicked']:
                    all_joined = False
                    break
            except:
                all_joined = False
                break
        
        if all_joined:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "UPDATE new_members SET verified=1 WHERE user_id=?",
                    (user_id,)
                )
                await db.commit()
            
            await query.edit_message_text(
                f"✅ *VERIFICATION SUCCESSFUL!* ✅\n\n"
                f"Welcome aboard! You can now send messages freely.\n\n"
                f"🎯 Remember: Max 120 characters per message\n"
                f"⚠️ Break rules = Warnings/Removal\n\n"
                f"Enjoy your stay! 🎉",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.answer(
                "❌ You haven't joined all channels yet! Please join all and try again.",
                show_alert=True
            )
    
    async def message_length_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle message length violations"""
        if update.effective_chat.id != MAIN_GROUP_ID:
            return
        
        user_id = update.effective_user.id
        
        # Check if exempted or admin
        if user_id in ADMIN_IDS:
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT user_id FROM exempted_users WHERE user_id=?", (user_id,))
            if await cursor.fetchone():
                return
            
            # Check if VIP
            cursor = await db.execute("""
                SELECT expires_at FROM vip_members 
                WHERE user_id=? AND is_active=1
            """, (user_id,))
            vip = await cursor.fetchone()
            if vip:
                expires = datetime.fromisoformat(vip[0])
                if expires > datetime.now():
                    return
        
        message_text = update.message.text or ""
        if len(message_text) > 120:
            try:
                await update.message.delete()
                
                # Add violation
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("""
                        INSERT INTO violations (user_id, username, violation_type, timestamp)
                        VALUES (?, ?, 'long_message', ?)
                    """, (user_id, update.effective_user.username, datetime.now().isoformat()))
                    
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM violations 
                        WHERE user_id=? AND violation_type='long_message'
                    """, (user_id,))
                    warning_count = (await cursor.fetchone())[0]
                    await db.commit()
                
                warning_msg = await update.message.reply_text(
                    f"⚠️ *MESSAGE TOO LONG!* ⚠️\n\n"
                    f"@{update.effective_user.username}, your message exceeded 120 characters.\n\n"
                    f"📊 *Warning {warning_count}/3*\n"
                    f"⚡ 3 warnings = Auto-ban\n\n"
                    f"💎 VIP members have no limits!",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Auto-delete warning after 10 seconds
                context.job_queue.run_once(
                    lambda ctx: warning_msg.delete(),
                    10
                )
                
                if warning_count >= 3:
                    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
                    await update.message.reply_text(
                        f"🔨 @{update.effective_user.username} has been banned for repeated violations."
                    )
            
            except Exception as e:
                logger.error(f"Error handling message length: {e}")
    
    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kick user (Admin only, Group only)"""
        if update.effective_chat.type == "private":
            await update.message.reply_text("⚔️ This command works in groups only!")
            return
        
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Guardians can wield this power!")
            return
        
        if not context.args and not update.message.reply_to_message:
            await update.message.reply_text("📝 Usage: `/kick @user` or reply to user's message")
            return
        
        # Get target user
        target_user = None
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
        
        if target_user:
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
                await context.bot.unban_chat_member(update.effective_chat.id, target_user.id)
                await update.message.reply_text(
                    f"👢 *KICKED!*\n\n"
                    f"@{target_user.username} has been removed from the realm!",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban user (Admin only, Group only)"""
        if update.effective_chat.type == "private":
            await update.message.reply_text("⚔️ This command works in groups only!")
            return
        
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Guardians can wield this power!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("📝 Reply to user's message to ban them")
            return
        
        target_user = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "No reason provided"
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
            await update.message.reply_text(
                f"🔨 *BANNED!*\n\n"
                f"@{target_user.username} has been permanently banished!\n"
                f"📋 Reason: {reason}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    
    def setup_handlers(self):
        """Setup all handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("kick", self.kick_command))
        self.app.add_handler(CommandHandler("ban", self.ban_command))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_length_handler))
        self.app.add_handler(CallbackQueryHandler(self.verify_callback, pattern="^verify_"))
    
    async def run(self):
        """Run the group management bot"""
        self.setup_handlers()
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

# ============================
# 🤖 4. AUTO ADV BOT
# ============================

class AutoADVBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.user_states = {}  # Track conversation states
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with product selection"""
        if update.effective_chat.type != "private":
            # In group, send DM notification
            await update.message.reply_text(
                "✅ *I've sent you a DM!*\n\n"
                "Please check your private messages to continue securely! 🔒",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Delete messages after 60 seconds
            context.job_queue.run_once(
                lambda ctx: update.message.delete(),
                60
            )
            
            # Send DM
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=self.get_start_message()
            )
            return
        
        await update.message.reply_text(self.get_start_message())
    
    def get_start_message(self):
        """Get start message with product selection"""
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement (188 USDT)", callback_data="product_ad")],
            [InlineKeyboardButton("💎 Buy VIP (300 USDT)", callback_data="product_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer (FREE)", callback_data="product_scammer")],
            [InlineKeyboardButton("📊 My Purchases", callback_data="my_purchases")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        return {
            'text': """
🌟 *WELCOME TO AUTO ADV BOT!* 🌟

Your divine marketplace for premium services!

🛍️ *AVAILABLE PRODUCTS:*

📢 *Advertisement Package*
   💰 Price: 188 USDT
   ⏰ Validity: 10 days
   📊 Auto-posting every 5-6 minutes

💎 *VIP Membership*
   💰 Price: 300 USDT
   ⏰ Validity: 60 days
   ✨ Verified badge + Premium perks

⚠️ *Scammer Report*
   💰 Price: FREE
   🚨 Instant posting to exposure channel

━━━━━━━━━━━━━━━━
🔒 *100% Secure Payments via USDT (TRC20)*

Select a product below to begin! 👇
""",
            'reply_markup': reply_markup,
            'parse_mode': ParseMode.MARKDOWN
        }
    
    async def product_selection_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle product selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        product = query.data.split("_")[1]
        
        if product == "ad":
            await self.start_ad_purchase(query, context, user_id)
        elif product == "vip":
            await self.start_vip_purchase(query, context, user_id)
        elif product == "scammer":
            await self.start_scammer_report(query, context, user_id)
    
    async def start_ad_purchase(self, query, context, user_id):
        """Start advertisement purchase flow"""
        self.user_states[user_id] = {'product': 'ad', 'step': 1, 'data': {}}
        
        await query.edit_message_text(
            "📢 *ADVERTISEMENT PURCHASE* 📢\n\n"
            "💰 Price: 188 USDT\n"
            "⏰ Validity: 10 days\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📝 *Step 1 of 5: Enter Heading*\n\n"
            "Please provide a catchy heading for your advertisement:\n"
            "_(Max 100 characters)_",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_vip_purchase(self, query, context, user_id):
        """Start VIP purchase flow"""
        self.user_states[user_id] = {'product': 'vip', 'step': 1, 'data': {}}
        
        await query.edit_message_text(
            "💎 *VIP MEMBERSHIP PURCHASE* 💎\n\n"
            "💰 Price: 300 USDT\n"
            "⏰ Validity: 60 days\n\n"
            "✨ *VIP Benefits:*\n"
            "✅ Verified badge\n"
            "✅ No character limits\n"
            "✅ Priority support\n"
            "✅ Exclusive access\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📝 *Step 1 of 4: Enter Your Name*\n\n"
            "Please provide your full name:",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def start_scammer_report(self, query, context, user_id):
        """Start scammer report flow"""
        self.user_states[user_id] = {'product': 'scammer', 'step': 1, 'data': {}}
        
        await query.edit_message_text(
            "⚠️ *SCAMMER REPORT* ⚠️\n\n"
            "💰 Price: FREE\n"
            "🚨 Help protect our community!\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📝 *Step 1 of 5: Scammer Name*\n\n"
            "Please provide the scammer's name or username:",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages based on conversation state"""
        if update.effective_chat.type != "private":
            return
        
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        product = state['product']
        step = state['step']
        
        user_input = update.message.text
        
        if product == 'ad':
            await self.handle_ad_flow(update, context, user_id, step, user_input)
        elif product == 'vip':
            await self.handle_vip_flow(update, context, user_id, step, user_input)
        elif product == 'scammer':
            await self.handle_scammer_flow(update, context, user_id, step, user_input)
    
    async def handle_ad_flow(self, update, context, user_id, step, user_input):
        """Handle advertisement purchase flow"""
        state = self.user_states[user_id]
        
        if step == 1:  # Heading
            state['data']['heading'] = user_input
            state['step'] = 2
            await update.message.reply_text(
                "✅ Heading saved!\n\n"
                "📝 *Step 2 of 5: Enter Type*\n\n"
                "What type of service/product is this?\n"
                "_(e.g., Business, Service, Product, etc.)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 2:  # Type
            state['data']['type'] = user_input
            state['step'] = 3
            await update.message.reply_text(
                "✅ Type saved!\n\n"
                "📝 *Step 3 of 5: Enter Description*\n\n"
                "Provide a detailed description:\n"
                "_(Max 500 characters)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 3:  # Description
            state['data']['description'] = user_input
            state['step'] = 4
            await update.message.reply_text(
                "✅ Description saved!\n\n"
                "📝 *Step 4 of 5: Enter Contact*\n\n"
                "How should people contact you?\n"
                "_(Phone, Email, Telegram, etc.)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 4:  # Contact
            state['data']['contact'] = user_input
            state['step'] = 5
            
            if PAYMENT_MODE == "dummy":
                await self.process_dummy_payment(update, context, user_id, 'ad', state['data'])
            else:
                await self.initiate_real_payment(update, context, user_id, 188, 'ad', state['data'])
    
    async def handle_vip_flow(self, update, context, user_id, step, user_input):
        """Handle VIP purchase flow"""
        state = self.user_states[user_id]
        
        if step == 1:  # Name
            state['data']['name'] = user_input
            state['step'] = 2
            await update.message.reply_text(
                "✅ Name saved!\n\n"
                "📝 *Step 2 of 4: Enter Phone Number*\n\n"
                "Provide your phone number:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 2:  # Phone
            state['data']['phone'] = user_input
            state['step'] = 3
            await update.message.reply_text(
                "✅ Phone saved!\n\n"
                "📝 *Step 3 of 4: Enter Email*\n\n"
                "Provide your email address:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 3:  # Email
            state['data']['email'] = user_input
            state['step'] = 4
            
            if PAYMENT_MODE == "dummy":
                await self.process_dummy_payment(update, context, user_id, 'vip', state['data'])
            else:
                await self.initiate_real_payment(update, context, user_id, 300, 'vip', state['data'])
    
    async def handle_scammer_flow(self, update, context, user_id, step, user_input):
        """Handle scammer report flow"""
        state = self.user_states[user_id]
        
        if step == 1:  # Scammer Name
            state['data']['scammer_name'] = user_input
            state['step'] = 2
            await update.message.reply_text(
                "✅ Name saved!\n\n"
                "📝 *Step 2 of 5: Scammer Contact*\n\n"
                "Provide scammer's contact info:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 2:  # Contact
            state['data']['scammer_contact'] = user_input
            state['step'] = 3
            await update.message.reply_text(
                "✅ Contact saved!\n\n"
                "📝 *Step 3 of 5: Incident Details*\n\n"
                "Describe what happened:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 3:  # Details
            state['data']['details'] = user_input
            state['step'] = 4
            await update.message.reply_text(
                "✅ Details saved!\n\n"
                "📝 *Step 4 of 5: Platform/Location*\n\n"
                "Where did this scam occur?",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 4:  # Platform
            state['data']['platform'] = user_input
            state['step'] = 5
            await update.message.reply_text(
                "✅ Platform saved!\n\n"
                "📝 *Step 5 of 5: Victim Telegram*\n\n"
                "Your Telegram username:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif step == 5:  # Victim contact
            state['data']['victim_telegram'] = user_input
            await self.post_scammer_report(update, context, user_id, state['data'])
    
    async def process_dummy_payment(self, update, context, user_id, product, data):
        """Process dummy payment (testing mode)"""
        await update.message.reply_text(
            "💳 *DUMMY PAYMENT MODE*\n\n"
            "⚠️ Testing mode active!\n"
            "Type 'paid' to simulate payment completion.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        self.user_states[user_id]['step'] = 'awaiting_dummy_confirm'
        self.user_states[user_id]['awaiting_payment'] = True
    
    async def initiate_real_payment(self, update, context, user_id, amount, product, data):
        """Initiate real USDT payment"""
        payment_id = f"PAY{user_id}{int(datetime.now().timestamp())}"
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO pending_payments (user_id, product, amount, data, created_at, payment_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, product, amount, str(data), datetime.now().isoformat(), payment_id))
            await db.commit()
        
        await update.message.reply_text(
            f"💳 *PAYMENT INSTRUCTIONS* 💳\n\n"
            f"💰 Amount: {amount} USDT (TRC20)\n"
            f"📍 Address:\n`{YOUR_USDT_ADDRESS}`\n\n"
            f"🆔 Payment ID: `{payment_id}`\n\n"
            f"📝 *Steps:*\n"
            f"1️⃣ Send exactly {amount} USDT to the address above\n"
            f"2️⃣ Copy your transaction hash from TronScan\n"
            f"3️⃣ Send the transaction hash here\n\n"
            f"⏰ Verification takes 1-2 minutes!\n"
            f"🔒 Your payment is 100% secure!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        self.user_states[user_id]['step'] = 'awaiting_tx'
        self.user_states[user_id]['payment_id'] = payment_id
        self.user_states[user_id]['amount'] = amount
    
    async def verify_transaction(self, tx_hash: str, expected_amount: float) -> bool:
        """Verify USDT transaction via TronScan API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{TRONSCAN_API}?hash={tx_hash}") as response:
                    if response.status != 200:
                        return False
                    
                    data = await response.json()
                    
                    # Verify transaction details
                    if 'contractData' not in data:
                        return False
                    
                    contract_data = data['contractData']
                    
                    # Check recipient address
                    to_address = contract_data.get('to_address')
                    if to_address != YOUR_USDT_ADDRESS:
                        return False
                    
                    # Check amount (USDT has 6 decimals)
                    amount = int(contract_data.get('amount', 0)) / 1000000
                    if abs(amount - expected_amount) > 0.01:  # Allow small difference
                        return False
                    
                    # Check confirmation
                    confirmed = data.get('confirmed', False)
                    if not confirmed:
                        return False
                    
                    return True
        
        except Exception as e:
            logger.error(f"Transaction verification error: {e}")
            return False
    
    async def handle_payment_confirmation(self, update, context, user_id, user_input):
        """Handle payment confirmation based on mode"""
        state = self.user_states[user_id]
        
        if state.get('awaiting_payment'):
            if PAYMENT_MODE == "dummy":
                if user_input.lower() == "paid":
                    await self.finalize_purchase(update, context, user_id)
                else:
                    await update.message.reply_text("Type 'paid' to confirm dummy payment.")
            else:
                # Real payment verification
                tx_hash = user_input.strip()
                amount = state.get('amount', 0)
                
                await update.message.reply_text("🔄 Verifying transaction... Please wait!")
                
                # Check rate limiting
                if not await self.check_rate_limit(user_id, 'payment_attempt'):
                    await update.message.reply_text(
                        "⚠️ *RATE LIMIT EXCEEDED*\n\n"
                        "Too many payment attempts. Please wait 1 hour.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                # Verify transaction
                is_valid = await self.verify_transaction(tx_hash, amount)
                
                # Log transaction
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("""
                        INSERT INTO transaction_logs (user_id, tx_hash, verified, timestamp, details)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, tx_hash, 1 if is_valid else 0, datetime.now().isoformat(), 
                          f"Amount: {amount}"))
                    await db.commit()
                
                if is_valid:
                    await self.finalize_purchase(update, context, user_id, tx_hash)
                else:
                    # Track failed attempts
                    failed_count = await self.increment_failed_attempts(user_id)
                    
                    if failed_count >= 3:
                        await update.message.reply_text(
                            "🚫 *ACCOUNT SUSPENDED*\n\n"
                            "Too many failed verification attempts.\n"
                            "Contact admin for support.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        # TODO: Ban user
                    else:
                        await update.message.reply_text(
                            f"❌ *VERIFICATION FAILED*\n\n"
                            f"Transaction could not be verified.\n\n"
                            f"⚠️ Attempt {failed_count}/3\n\n"
                            f"Possible reasons:\n"
                            f"• Wrong transaction hash\n"
                            f"• Incorrect amount sent\n"
                            f"• Wrong recipient address\n"
                            f"• Transaction not confirmed yet\n\n"
                            f"Please try again or contact support.",
                            parse_mode=ParseMode.MARKDOWN
                        )
    
    async def check_rate_limit(self, user_id: int, action: str) -> bool:
        """Check if user has exceeded rate limits"""
        async with aiosqlite.connect(DB_NAME) as db:
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            cursor = await db.execute("""
                SELECT COUNT(*) FROM rate_limits 
                WHERE user_id=? AND action=? AND timestamp > ?
            """, (user_id, action, one_hour_ago))
            count = (await cursor.fetchone())[0]
            
            if count >= 3:
                return False
            
            await db.execute("""
                INSERT INTO rate_limits (user_id, action, timestamp)
                VALUES (?, ?, ?)
            """, (user_id, action, datetime.now().isoformat()))
            await db.commit()
            
            return True
    
    async def increment_failed_attempts(self, user_id: int) -> int:
        """Track failed payment attempts"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM transaction_logs 
                WHERE user_id=? AND verified=0
            """, (user_id,))
            return (await cursor.fetchone())[0]
    
    async def finalize_purchase(self, update, context, user_id, tx_hash=None):
        """Complete the purchase and update databases"""
        state = self.user_states[user_id]
        product = state['product']
        data = state['data']
        username = update.effective_user.username or "Unknown"
        
        # Store purchase record
        async with aiosqlite.connect(DB_NAME) as db:
            if product == 'ad':
                # Add to ads queue
                expires_at = (datetime.now() + timedelta(days=10)).isoformat()
                await db.execute("""
                    INSERT INTO ads_queue (user_id, username, heading, type, description, contact, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, username, data['heading'], data['type'], data['description'], 
                      data['contact'], datetime.now().isoformat(), expires_at))
                
                success_msg = """
✅ *ADVERTISEMENT PURCHASED!* ✅

🎯 Your ad has been added to the queue!
📢 Will be posted every 5-6 minutes
⏰ Valid for 10 days

📊 *Your Ad Details:*
▫️ Heading: {heading}
▫️ Type: {type}
▫️ Contact: {contact}

🎉 Thank you for your purchase, Master!
""".format(**data)
            
            elif product == 'vip':
                # Add to VIP members
                expires_at = (datetime.now() + timedelta(days=60)).isoformat()
                await db.execute("""
                    INSERT OR REPLACE INTO vip_members (user_id, username, name, phone, email, created_at, expires_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (user_id, username, data['name'], data['phone'], data['email'], 
                      datetime.now().isoformat(), expires_at))
                
                success_msg = """
💎 *VIP MEMBERSHIP ACTIVATED!* 💎

🌟 Welcome to the premium club!
⏰ Valid for 60 days

👤 *Your VIP Profile:*
▫️ Name: {name}
▫️ Phone: {phone}
▫️ Email: {email}

✨ *Active Benefits:*
✅ Verified badge in groups
✅ No character limits
✅ Priority support
✅ Exclusive access

🎉 Enjoy your premium experience!
""".format(**data)
                
                # Post announcement in Main Group
                try:
                    await context.bot.send_message(
                        chat_id=MAIN_GROUP_ID,
                        text=f"🎉 @{username} just upgraded to VIP! 💎\n\nWelcome to the premium club! 🌟",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            # Store purchase record
            await db.execute("""
                INSERT INTO purchases (user_id, username, product_type, amount, tx_hash, status, created_at, data)
                VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
            """, (user_id, username, product, 
                  188 if product == 'ad' else 300, 
                  tx_hash or 'DUMMY', 
                  datetime.now().isoformat(), 
                  str(data)))
            
            # Clear pending payment
            await db.execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))
            await db.commit()
        
        # Clear user state
        del self.user_states[user_id]
        
        await update.message.reply_text(success_msg, parse_mode=ParseMode.MARKDOWN)
    
    async def post_scammer_report(self, update, context, user_id, data):
        """Post scammer report to exposure channel"""
        report_text = f"""
⚠️ *SCAMMER ALERT!* ⚠️

🚨 *Scammer Information:*
▫️ Name: {data['scammer_name']}
▫️ Contact: {data['scammer_contact']}

📋 *Incident Details:*
{data['details']}

🌐 *Platform/Location:*
{data['platform']}

👤 *Reported By:*
@{data['victim_telegram']}

━━━━━━━━━━━━━━━━
⚡ Stay safe! Report scammers to protect our community.
"""
        
        try:
            # Post to Scammer Exposed channel
            await context.bot.send_message(
                chat_id=SCAMMER_EXPOSED_ID,
                text=report_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Notify reporter
            await update.message.reply_text(
                "✅ *SCAMMER REPORT SUBMITTED!* ✅\n\n"
                "Your report has been posted to the Scammer Exposed channel.\n\n"
                "🛡️ Thank you for helping protect our community!\n\n"
                "⚠️ All members have been notified.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Store in database
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    INSERT INTO purchases (user_id, username, product_type, amount, status, created_at, data)
                    VALUES (?, ?, 'scammer_report', 0, 'completed', ?, ?)
                """, (user_id, update.effective_user.username or "Unknown", 
                      datetime.now().isoformat(), str(data)))
                await db.commit()
            
            # Clear user state
            if user_id in self.user_states:
                del self.user_states[user_id]
        
        except Exception as e:
            logger.error(f"Error posting scammer report: {e}")
            await update.message.reply_text(
                "❌ Error posting report. Please try again or contact support."
            )
    
    async def my_purchases_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's purchase history"""
        user_id = update.effective_user.id
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT product_type, amount, status, created_at 
                FROM purchases 
                WHERE user_id=? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (user_id,))
            purchases = await cursor.fetchall()
        
        if not purchases:
            await update.message.reply_text(
                "📭 *NO PURCHASES YET*\n\n"
                "You haven't made any purchases yet.\n\n"
                "🛍️ Start shopping now!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        history_text = "🛍️ *YOUR PURCHASE HISTORY* 🛍️\n\n"
        
        for purchase in purchases:
            product_name = {
                'ad': '📢 Advertisement',
                'vip': '💎 VIP Membership',
                'scammer_report': '⚠️ Scammer Report'
            }.get(purchase[0], purchase[0])
            
            history_text += f"🎯 *{product_name}*\n"
            history_text += f"   💰 Amount: {purchase[1]} USDT\n"
            history_text += f"   ✅ Status: {purchase[2].upper()}\n"
            history_text += f"   📅 Date: {purchase[3]}\n"
            history_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(history_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive help command"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = """
🌟 *AUTO ADV BOT - DIVINE MARKETPLACE* 🌟

💰 *AVAILABLE PRODUCTS:*

📢 *Advertisement (188 USDT)*
/buy_ad - Purchase ad space
10 days validity, auto-posting

💎 *VIP Membership (300 USDT)*
/buy_vip - Become VIP
60 days validity, premium perks

⚠️ *Scammer Report (FREE)*
/report_scammer - Report scammer
Instant posting, help community

📊 *USER COMMANDS:*
/start - Main menu
/help - This help message
/mypurchases - Purchase history
/status - Check order status
/cancel - Cancel current order
/support - Contact support
/terms - Terms and conditions
/refund - Refund policy
"""
        
        if is_admin:
            help_text += """
👑 *ADMIN COMMANDS (DM ONLY):*
/pending - View pending payments
/verify_payment [user_id] - Manual verification
/reject_payment [user_id] - Reject payment
/refund [user_id] - Process refund
/sales_report - Sales statistics
/revenue - Revenue analytics
/topbuyers - Top customers
/exportdata - Export all data
/broadcast_buyers [msg] - Message all buyers
/suspension [user_id] - Suspend user
/unsuspend [user_id] - Unsuspend user
/fraud_check [user_id] - Check fraud history
/payment_logs - All payment logs
/analytics_dashboard - Full analytics
"""
        
        help_text += "\n💫 *Your wish is my command, Master!* 💫"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def buy_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct command to buy ad"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "✅ Check your DM to purchase securely! 🔒",
                parse_mode=ParseMode.MARKDOWN
            )
            # Delete after 60 seconds
            context.job_queue.run_once(lambda ctx: update.message.delete(), 60)
        
        await self.start_ad_purchase(
            type('obj', (object,), {
                'edit_message_text': update.message.reply_text
            })(), 
            context, 
            update.effective_user.id
        )
    
    async def buy_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct command to buy VIP"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "✅ Check your DM to purchase securely! 🔒",
                parse_mode=ParseMode.MARKDOWN
            )
            context.job_queue.run_once(lambda ctx: update.message.delete(), 60)
        
        await self.start_vip_purchase(
            type('obj', (object,), {
                'edit_message_text': update.message.reply_text
            })(),
            context,
            update.effective_user.id
        )
    
    async def report_scammer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct command to report scammer"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "✅ Check your DM to report securely! 🔒",
                parse_mode=ParseMode.MARKDOWN
            )
            context.job_queue.run_once(lambda ctx: update.message.delete(), 60)
        
        await self.start_scammer_report(
            type('obj', (object,), {
                'edit_message_text': update.message.reply_text
            })(),
            context,
            update.effective_user.id
        )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current purchase"""
        user_id = update.effective_user.id
        
        if user_id in self.user_states:
            del self.user_states[user_id]
            await update.message.reply_text(
                "❌ *ORDER CANCELLED*\n\n"
                "Your current order has been cancelled.\n\n"
                "💫 Ready to start fresh? Use /start",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("No active order to cancel!")
    
    async def text_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        if update.effective_chat.type != "private":
            # Delete any TX hash or sensitive info posted in groups
            if re.match(r^[a-fA-F0-9]{64}, update.message.text or ""):
                try:
                    await update.message.delete()
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="⚠️ *SECURITY ALERT*\n\nNever share transaction hashes in public groups!\nUse DM only!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            return
        
        user_id = update.effective_user.id
        
        # Check if user is in purchase flow
        if user_id in self.user_states:
            state = self.user_states[user_id]
            if state.get('awaiting_payment'):
                await self.handle_payment_confirmation(update, context, user_id, update.message.text)
            else:
                await self.message_handler(update, context)
    
    def setup_handlers(self):
        """Setup all handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("buy_ad", self.buy_ad_command))
        self.app.add_handler(CommandHandler("buy_vip", self.buy_vip_command))
        self.app.add_handler(CommandHandler("report_scammer", self.report_scammer_command))
        self.app.add_handler(CommandHandler("mypurchases", self.my_purchases_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        self.app.add_handler(CallbackQueryHandler(self.product_selection_callback, pattern="^product_"))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message_handler))
    
    async def run(self):
        """Run the auto ADV bot"""
        self.setup_handlers()
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

# ============================
# 🚀 MAIN EXECUTION
# ============================

async def main():
    """Initialize and run all bots concurrently"""
    logger.info("🚀 Starting Interlink Multi-Bot System...")
    
    # Initialize database
    await init_database()
    
    # Create bot instances
    adv_bot = AdvertisingBot(ADV_BOT_TOKEN)
    vip_bot = VIPBot(VIP_BOT_TOKEN)
    group_bot = GroupManagementBot(GROUP_BOT_TOKEN)
    autoadv_bot = AutoADVBot(AUTOADV_BOT_TOKEN)
    
    logger.info("✅ All bots initialized successfully!")
    logger.info(f"💳 Payment Mode: {PAYMENT_MODE.upper()}")
    logger.info("🎯 Starting all bots...")
    
    # Run all bots concurrently
    try:
        await asyncio.gather(
            adv_bot.run(),
            vip_bot.run(),
            group_bot.run(),
            autoadv_bot.run()
        )
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down bots...")
    except Exception as e:
        logger.error(f"❌ Error running bots: {e}")

if __name__ == "__main__":
    """Entry point"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║        🌟 INTERLINK MULTI-BOT SYSTEM 🌟                  ║
    ║                                                           ║
    ║  📢 Advertising Bot      - Auto-posting & promotion      ║
    ║  💎 VIP Bot              - Member verification           ║
    ║  🛡️ Group Management Bot - Spam control & moderation     ║
    ║  💰 Auto ADV Bot         - Payment processing            ║
    ║                                                           ║
    ║  Version: 1.0.0                                          ║
    ║  Payment Mode: {mode}                                 ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """.format(mode=PAYMENT_MODE.upper()))
    
    asyncio.run(main())
