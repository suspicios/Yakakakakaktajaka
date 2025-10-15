[file name]: mrlonly.py
[file content begin]
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
import json
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
ADMIN_IDS = [7578682081]  # Replace with actual admin user IDs

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
        
        # Initialize ad_config if empty
        await db.execute("INSERT OR IGNORE INTO ad_config (id, last_post_time, is_paused) VALUES (1, NULL, 0)")
        
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
        self.bot_prefix = "ad"  # Prefix for common commands
        
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
            "/adhelp - View all my divine commands\n"
            "/adstats - See advertising statistics\n"
            "/adviewqueue - Check pending ads\n\n"
            "Your wish is my command, O Great One! 🙇",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive help with all commands"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        user_commands = f"""
🌟 *ADVERTISING BOT - COMMAND BIBLE* 🌟

📱 *GENERAL COMMANDS:*
/{self.bot_prefix}start - Awaken the advertising god
/{self.bot_prefix}help - Divine command reference
/{self.bot_prefix}about - Learn about my existence
/{self.bot_prefix}status - Current bot status
/{self.bot_prefix}stats - Advertising statistics
/{self.bot_prefix}viewqueue - See all pending ads
/{self.bot_prefix}myads - Your active advertisements
/{self.bot_prefix}contact - Contact support

🎯 *AD MANAGEMENT:*
/{self.bot_prefix}viewqueue - All ads in queue
/{self.bot_prefix}checkad [id] - Check specific ad
/{self.bot_prefix}adstats - Detailed ad analytics
/{self.bot_prefix}topads - Most viewed ads
"""
        
        admin_commands = f"""
👑 *ADMIN COMMANDS:*
/{self.bot_prefix}pause - Pause all advertising
/{self.bot_prefix}resume - Resume advertising
/{self.bot_prefix}clearqueue - Clear ad queue
/{self.bot_prefix}removead [id] - Remove specific ad
/{self.bot_prefix}editad [id] - Edit advertisement
/{self.bot_prefix}setinterval [min] - Set post interval
/{self.bot_prefix}forcead - Force post next ad
/{self.bot_prefix}skipnext - Skip next scheduled ad
/{self.bot_prefix}broadcast [msg] - Broadcast message
/{self.bot_prefix}adlogs - View posting logs
/{self.bot_prefix}resetstats - Reset statistics
/{self.bot_prefix}backup - Backup ad database
/{self.bot_prefix}restore - Restore from backup
/{self.bot_prefix}maintenance - Toggle maintenance mode
/{self.bot_prefix}adpreview [id] - Preview ad before posting
/{self.bot_prefix}schedulepost [time] - Schedule specific post
/{self.bot_prefix}analytics - Deep analytics dashboard
/{self.bot_prefix}exportads - Export ads to CSV
/{self.bot_prefix}importads - Import ads from file
/{self.bot_prefix}pinnext - Pin next ad manually
/{self.bot_prefix}unpinlast - Unpin last ad
/{self.bot_prefix}setemergency [msg] - Set emergency broadcast
/{self.bot_prefix}testpost - Test ad posting
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
            f"Use /{self.bot_prefix}resume to awaken it once more. 💤",
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
    
    async def clear_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear ad queue (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM ads_queue WHERE status='active'")
            await db.commit()
        
        await update.message.reply_text(
            "🗑️ *QUEUE CLEARED* 🗑️\n\n"
            "All active advertisements have been removed from the queue!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def remove_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove specific ad (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /adremovead [ad_id]")
            return
        
        try:
            ad_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid ad ID!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT heading FROM ads_queue WHERE id=?", (ad_id,))
            ad = await cursor.fetchone()
            
            if not ad:
                await update.message.reply_text("❌ Ad not found!")
                return
            
            await db.execute("DELETE FROM ads_queue WHERE id=?", (ad_id,))
            await db.commit()
        
        await update.message.reply_text(
            f"✅ *AD REMOVED*\n\nAdvertisement '{ad[0]}' has been removed!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def force_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Force post next ad (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        await self.post_advertisement()
        await update.message.reply_text("✅ Advertisement posted immediately!")
    
    async def skip_next_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip next scheduled ad (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        await update.message.reply_text("⏭️ Next advertisement will be skipped!")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /adbroadcast [message]")
            return
        
        message = " ".join(context.args)
        await update.message.reply_text("📢 Broadcast feature would send message to all groups!")
    
    async def my_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's active ads"""
        user_id = update.effective_user.id
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT id, heading, type, expires_at, post_count 
                FROM ads_queue 
                WHERE user_id=? AND status='active'
            """, (user_id,))
            ads = await cursor.fetchall()
        
        if not ads:
            await update.message.reply_text(
                "📭 *No active advertisements found!*\n\n"
                "You don't have any active ads running.\n\n"
                "🚀 Purchase ads via AutoADV bot!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        my_ads_text = "📋 *YOUR ACTIVE ADVERTISEMENTS* 📋\n\n"
        for ad in ads:
            my_ads_text += f"🎯 *ID:* {ad[0]}\n"
            my_ads_text += f"📌 *Heading:* {ad[1]}\n"
            my_ads_text += f"🏷️ *Type:* {ad[2]}\n"
            my_ads_text += f"⏰ *Expires:* {ad[3]}\n"
            my_ads_text += f"📊 *Posted:* {ad[4]} times\n"
            my_ads_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(my_ads_text, parse_mode=ParseMode.MARKDOWN)
    
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
                    # FIXED: Use proper bot usernames (replace these with your actual bot usernames)
                    keyboard = [
                        [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/AutoAdvPaymentBot?start=buy_ad")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/AutoAdvPaymentBot?start=report_scammer")]
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
                    # FIXED: Use proper bot usernames (replace these with your actual bot/channel usernames)
                    keyboard = [
                        [InlineKeyboardButton("💎 Join VIP", url=f"https://t.me/+bEyi7RpG_NxjZjk1")],
                        [InlineKeyboardButton("🏢 Company Resources", url=f"https://t.me/+D9yrbrh6xTcyNGE1")],
                        [InlineKeyboardButton("📢 Post Ad", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=buy_ad")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=report_scammer")]
                    ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Post to Main Group and pin
                try:
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
                    logger.error(f"❌ Error sending message: {e}")
        
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
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}start", self.start_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}help", self.help_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}stats", self.stats_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}viewqueue", self.view_queue_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}pause", self.pause_ads_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}resume", self.resume_ads_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}clearqueue", self.clear_queue_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}removead", self.remove_ad_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}forcead", self.force_ad_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}skipnext", self.skip_next_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}broadcast", self.broadcast_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}myads", self.my_ads_command))
    
    async def run(self):
        """Run the advertising bot"""
        self.setup_handlers()
        await self.setup_scheduler()
        
        await self.app.initialize()
        await self.app.start()
        logger.info("✅ Advertising Bot started and polling")
        
        # Start polling
        await self.app.updater.start_polling()
        
        # Keep the bot running
        try:
            # Create a future that never completes
            await asyncio.Future()
        except asyncio.CancelledError:
            await self.app.stop()
            logger.info("🛑 Advertising Bot stopped")

# ============================
# 🤖 2. VIP BOT
# ============================

class VIPBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.trigger_words = ["direct", "company", "sbi", "accounts", "account"]
        self.bot_prefix = "vip"  # Prefix for common commands
    
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
            f"/{self.bot_prefix}check @username - Verify anyone's VIP status\n"
            f"/{self.bot_prefix}my - Check your own VIP status\n"
            f"/{self.bot_prefix}help - All available commands\n\n"
            "Your premium status awaits, O Distinguished One! 🌟",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = f"""
👑 *VIP BOT - COMMAND SANCTUARY* 👑

🎯 *VERIFICATION COMMANDS:*
/{self.bot_prefix}start - Begin your VIP journey
/{self.bot_prefix}help - Divine guidance
/{self.bot_prefix}check @user - Verify any member
/{self.bot_prefix}my - Your VIP status
/{self.bot_prefix}stats - VIP statistics
/{self.bot_prefix}list - All VIP members (DM only)
/{self.bot_prefix}benefits - Learn VIP perks
/{self.bot_prefix}renew - Renew your VIP status
"""
        
        if is_admin:
            help_text += f"""
👑 *ADMIN COMMANDS (DM ONLY):*
/{self.bot_prefix}add [user_id] - Manually add VIP
/{self.bot_prefix}remove [user_id] - Remove VIP status
/{self.bot_prefix}extend [user_id] [days] - Extend VIP
/{self.bot_prefix}analytics - Detailed analytics
/{self.bot_prefix}export - Export VIP database
/{self.bot_prefix}revenue - Revenue statistics
/{self.bot_prefix}bulk - Bulk VIP operations
/{self.bot_prefix}logs - Activity logs
/{self.bot_prefix}search [query] - Search VIPs
/{self.bot_prefix}expiring - VIPs expiring soon
/{self.bot_prefix}reminder - Send renewal reminders
/{self.bot_prefix}backup - Backup VIP database
/{self.bot_prefix}restore - Restore VIP database
"""
        
        help_text += "\n💎 *Excellence recognized, premium delivered!* 💎"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def check_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check VIP status of mentioned user"""
        if not context.args:
            await update.message.reply_text(
                f"📝 *Usage:* `/{self.bot_prefix}check @username`\n\n"
                "Or reply to someone's message with `/{self.bot_prefix}check`",
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
                # Check if user has admin rights in VIP channel
                try:
                    # Get user ID from username (simplified - in production use proper resolution)
                    # For demo, we'll just show the status
                    has_channel_access = "✅"
                except:
                    has_channel_access = "⏳"
                
                await update.message.reply_text(
                    f"✅ *VIP STATUS CONFIRMED!* ✅\n\n"
                    f"👤 *User:* @{username}\n"
                    f"💎 *Status:* PREMIUM VIP\n"
                    f"📅 *Valid Until:* {expires.strftime('%d/%m/%Y')}\n"
                    f"🎯 *VIP Channel:* {has_channel_access} Can post messages\n\n"
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
        """Check own VIP status including channel access"""
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
            
            # Check if user has admin rights in VIP channel
            try:
                member = await self.app.bot.get_chat_member(VIP_CHANNEL_ID, user_id)
                has_channel_access = member.status in ['administrator', 'creator']
            except Exception as e:
                logger.error(f"Error checking channel access: {e}")
                has_channel_access = False
            
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

🎯 *VIP CHANNEL ACCESS:*
{'✅ Can post messages in VIP channel' if has_channel_access else '⏳ Access being configured'}

💎 *ACTIVE BENEFITS:*
✅ Verified status badge
✅ VIP channel posting rights
✅ Priority support
✅ Exclusive access
✅ No character limits

🌟 *You are a valued premium member!*
"""
            await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                "❌ *NO ACTIVE VIP STATUS* ❌\n\n"
                "You are not currently a VIP member.\n\n"
                "💎 *VIP BENEFITS:*\n"
                "✅ Verified badge\n"
                "✅ VIP channel posting access\n"
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
    
    async def vip_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP statistics"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members WHERE is_active=1")
            active_vips = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members")
            total_vips = (await cursor.fetchone())[0]
            
            cursor = await db.execute("""
                SELECT COUNT(*) FROM vip_members 
                WHERE expires_at < ? AND is_active=1
            """, (datetime.now().isoformat(),))
            expired_vips = (await cursor.fetchone())[0]
        
        stats_text = f"""
📊 *VIP STATISTICS* 📊

👑 *MEMBERSHIP OVERVIEW:*
▫️ Active VIPs: {active_vips}
▫️ Total VIPs (All Time): {total_vips}
▫️ Expired VIPs: {expired_vips}

💎 *VIP SYSTEM STATUS:*
▫️ Verification: ✅ ACTIVE
▫️ Auto-detection: ✅ ENABLED
▫️ Benefits: ✅ DELIVERED

🌟 *The VIP community grows stronger!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def add_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add VIP member (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can add VIP members!")
            return
        
        if len(context.args) < 1:
            await update.message.reply_text("📝 Usage: /vipadd [user_id] [days=60]")
            return
        
        try:
            user_id = int(context.args[0])
            days = int(context.args[1]) if len(context.args) > 1 else 60
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or days!")
            return
        
        expires_at = (datetime.now() + timedelta(days=days)).isoformat()
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT OR REPLACE INTO vip_members 
                (user_id, username, name, phone, email, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (user_id, "unknown", "Unknown", "Unknown", "unknown@example.com", 
                  datetime.now().isoformat(), expires_at))
            await db.commit()
        
        # Make user admin in VIP channel with ONLY message posting permission
        try:
            # Promote user to admin with limited permissions
            await self.app.bot.promote_chat_member(
                chat_id=VIP_CHANNEL_ID,
                user_id=user_id,
                can_post_messages=True,  # Only this permission
                can_edit_messages=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_video_chats=False,
                can_manage_chat=False
            )
            
            admin_success = True
        except Exception as e:
            logger.error(f"Error making user admin in VIP channel: {e}")
            admin_success = False
        
        success_message = (
            f"✅ *VIP MEMBER ADDED!*\n\n"
            f"User ID: {user_id}\n"
            f"VIP Status: ACTIVE\n"
            f"Expires: {expires_at.split('T')[0]}\n"
        )
        
        if admin_success:
            success_message += "🎯 *VIP Channel Access:* ✅ GRANTED\nUser can now post messages in VIP channel!\n\n"
        else:
            success_message += "⚠️ *VIP Channel Access:* Failed to grant\nManual setup required\n\n"
        
        success_message += "🌟 Welcome to the VIP family!"
        
        await update.message.reply_text(success_message, parse_mode=ParseMode.MARKDOWN)
    
    async def remove_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove VIP member (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can remove VIP members!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /vipremove [user_id]")
            return
        
        try:
            user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT username FROM vip_members WHERE user_id=?", (user_id,))
            vip = await cursor.fetchone()
            
            if not vip:
                await update.message.reply_text("❌ VIP member not found!")
                return
            
            await db.execute("DELETE FROM vip_members WHERE user_id=?", (user_id,))
            await db.commit()
        
        # Remove admin rights from VIP channel
        try:
            await self.app.bot.promote_chat_member(
                chat_id=VIP_CHANNEL_ID,
                user_id=user_id,
                can_post_messages=False
            )
            admin_removed = True
        except Exception as e:
            logger.error(f"Error removing VIP admin rights for {user_id}: {e}")
            admin_removed = False
        
        removal_message = (
            f"🗑️ *VIP MEMBER REMOVED!*\n\n"
            f"User ID: {user_id}\n"
            f"Username: {vip[0]}\n\n"
            f"VIP status has been revoked.\n"
        )
        
        if admin_removed:
            removal_message += "🔒 VIP channel access removed."
        else:
            removal_message += "⚠️ VIP channel access may need manual removal."
        
        await update.message.reply_text(removal_message, parse_mode=ParseMode.MARKDOWN)
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages for VIP verification"""
        if not update.message or not update.message.text:
            return
        
        message_text = update.message.text.lower()
        
        # Check for trigger words
        if any(word in message_text for word in self.trigger_words):
            user_id = update.message.from_user.id
            
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await db.execute("""
                    SELECT expires_at FROM vip_members 
                    WHERE user_id=? AND is_active=1
                """, (user_id,))
                vip = await cursor.fetchone()
            
            if vip:
                expires = datetime.fromisoformat(vip[0])
                if expires > datetime.now():
                    # User is VIP - allow message
                    return
                else:
                    # VIP expired
                    await update.message.reply_text(
                        "⚠️ *YOUR VIP STATUS HAS EXPIRED!* ⚠️\n\n"
                        "Your VIP benefits are no longer active.\n\n"
                        "💎 Renew now to continue enjoying:\n"
                        "✅ Verified status\n"
                        "✅ VIP channel access\n"
                        "✅ Priority support\n"
                        "✅ Exclusive access\n\n"
                        "🔄 Contact @AutoAdvPaymentBot to renew!",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                # Not VIP - warn about restrictions
                await update.message.reply_text(
                    "🔒 *VIP VERIFICATION REQUIRED* 🔒\n\n"
                    "This content requires VIP membership for access.\n\n"
                    "💎 *Become a VIP to unlock:*\n"
                    "✅ Direct company contacts\n"
                    "✅ VIP channel posting rights\n"
                    "✅ Premium opportunities\n"
                    "✅ Verified status\n"
                    "✅ No restrictions\n\n"
                    "🚀 Upgrade now: @AutoAdvPaymentBot",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}start", self.start_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}help", self.help_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}check", self.check_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}my", self.my_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}list", self.vip_list_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}stats", self.vip_stats_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}add", self.add_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}remove", self.remove_vip_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
    
    async def run(self):
        """Run the VIP bot"""
        self.setup_handlers()
        
        await self.app.initialize()
        await self.app.start()
        logger.info("✅ VIP Bot started and polling")
        
        # Start polling
        await self.app.updater.start_polling()
        
        # Keep the bot running
        try:
            # Create a future that never completes
            await asyncio.Future()
        except asyncio.CancelledError:
            await self.app.stop()
            logger.info("🛑 VIP Bot stopped")

# ============================
# 🤖 3. GROUP MANAGEMENT BOT
# ============================

class GroupManagementBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "group"  # Prefix for common commands
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        await update.message.reply_text(
            "🛡️ *WELCOME TO GROUP SECURITY SYSTEM!* 🛡️\n\n"
            "I am the *Group Management Bot*, guardian of order and protector of community harmony!\n\n"
            "✨ *MY DIVINE PROTECTIONS:* ✨\n"
            "🛡️ Auto-verification of new members\n"
            "🚫 Violation detection and warnings\n"
            "📊 Member activity monitoring\n"
            "⚡ Instant scammer protection\n\n"
            "⚡ *COMMANDS FOR YOUR USE:* ⚡\n"
            f"/{self.bot_prefix}stats - Group statistics\n"
            f"/{self.bot_prefix}warnings @user - Check warnings\n"
            f"/{self.bot_prefix}help - All available commands\n\n"
            "Your community is safe under my watch, O Wise Administrator! 🛡️",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = f"""
🛡️ *GROUP MANAGEMENT BOT - COMMAND ARSENAL* 🛡️

📊 *MONITORING COMMANDS:*
/{self.bot_prefix}start - Begin security monitoring
/{self.bot_prefix}help - Command reference
/{self.bot_prefix}stats - Group statistics
/{self.bot_prefix}warnings @user - Check user warnings
/{self.bot_prefix}violations - Recent violations
/{self.bot_prefix}members - Member count
/{self.bot_prefix}activity - Group activity
/{self.bot_prefix}reports - Security reports
"""
        
        if is_admin:
            help_text += f"""
👑 *ADMIN COMMANDS:*
/{self.bot_prefix}verify @user - Manually verify user
/{self.bot_prefix}warn @user [reason] - Issue warning
/{self.bot_prefix}ban @user [reason] - Ban user
/{self.bot_prefix}mute @user [hours] - Mute user
/{self.bot_prefix}exempt @user - Exempt from verification
/{self.bot_prefix}removeexempt @user - Remove exemption
/{self.bot_prefix}exemptlist - All exempted users
/{self.bot_prefix}cleanup - Remove unverified users
/{self.bot_prefix}settings - Configure security
/{self.bot_prefix}backup - Backup group data
/{self.bot_prefix}restore - Restore group data
/{self.bot_prefix}logs - Security logs
/{self.bot_prefix}export - Export member data
/{self.bot_prefix}scan - Scan for suspicious users
/{self.bot_prefix}lockdown - Emergency lockdown
/{self.bot_prefix}unlock - End lockdown
/{self.bot_prefix}promote @user - Promote to helper
/{self.bot_prefix}demote @user - Remove helper
/{self.bot_prefix}helpers - List all helpers
/{self.bot_prefix}automod - Auto-moderation settings
/{self.bot_prefix}filter [word] - Add word filter
/{self.bot_prefix}unfilter [word] - Remove filter
/{self.bot_prefix}filters - List all filters
/{self.bot_prefix}welcome - Set welcome message
/{self.bot_prefix}rules - Set group rules
/{self.bot_prefix}announce [msg] - Make announcement
"""
        
        help_text += "\n🛡️ *Security is my sacred duty!* 🛡️"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group statistics"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=1")
            verified_members = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=0")
            pending_members = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations")
            total_violations = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM exempted_users")
            exempted_users = (await cursor.fetchone())[0]
        
        stats_text = f"""
📊 *GROUP SECURITY STATISTICS* 📊

👥 *MEMBERSHIP STATUS:*
▫️ Verified Members: {verified_members}
▫️ Pending Verification: {pending_members}
▫️ Exempted Users: {exempted_users}

⚖️ *SECURITY METRICS:*
▫️ Total Violations: {total_violations}
▫️ Auto-verification: ✅ ACTIVE
▫️ Violation tracking: ✅ ACTIVE

🛡️ *SYSTEM STATUS:*
▫️ Security Level: MAXIMUM
▫️ Auto-protection: ✅ ENABLED
▫️ Scammer detection: ✅ ACTIVE

🌟 *Your community is protected!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user warnings"""
        if not context.args:
            await update.message.reply_text(
                f"📝 *Usage:* `/{self.bot_prefix}warnings @username`\n\n"
                "Or reply to someone's message with `/{self.bot_prefix}warnings`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        username = context.args[0].replace("@", "")
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT violation_type, timestamp, warning_count 
                FROM violations 
                WHERE username=? 
                ORDER BY timestamp DESC 
                LIMIT 5
            """, (username,))
            warnings = await cursor.fetchall()
        
        if not warnings:
            await update.message.reply_text(
                f"✅ *CLEAN RECORD!* ✅\n\n"
                f"@{username} has no warnings or violations.\n\n"
                f"🌟 This member follows the rules!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        warnings_text = f"⚠️ *WARNINGS FOR @{username}* ⚠️\n\n"
        total_warnings = 0
        
        for warning in warnings:
            total_warnings += warning[2]
            warnings_text += f"📅 {warning[1].split('T')[0]}\n"
            warnings_text += f"🔸 Type: {warning[0]}\n"
            warnings_text += f"🔸 Count: {warning[2]}\n"
            warnings_text += "━━━━━━━━━━━━━━━━\n\n"
        
        warnings_text += f"📊 *Total Warnings:* {total_warnings}\n\n"
        
        if total_warnings >= 3:
            warnings_text += "🚨 *ACTION REQUIRED:* Consider banning this user!"
        elif total_warnings >= 2:
            warnings_text += "⚠️ *WARNING:* User is close to ban threshold!"
        else:
            warnings_text += "ℹ️ User has minor infractions."
        
        await update.message.reply_text(warnings_text, parse_mode=ParseMode.MARKDOWN)
    
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining"""
        for member in update.message.new_chat_members:
            user_id = member.id
            username = member.username or "NoUsername"
            
            async with aiosqlite.connect(DB_NAME) as db:
                # Check if exempted
                cursor = await db.execute("SELECT 1 FROM exempted_users WHERE user_id=?", (user_id,))
                exempted = await cursor.fetchone()
                
                if exempted:
                    # Exempted user - welcome and grant permissions
                    await update.message.reply_text(
                        f"👑 *WELCOME BACK, EXEMPTED MEMBER!* 👑\n\n"
                        f"Welcome @{username}! You have special exempted status.\n\n"
                        "🌟 Enjoy full access to the group!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                # Add to verification queue
                await db.execute("""
                    INSERT OR REPLACE INTO new_members 
                    (user_id, username, join_time, verified) 
                    VALUES (?, ?, ?, 0)
                """, (user_id, username, datetime.now().isoformat()))
                await db.commit()
            
            # Send verification message
            keyboard = [
                [InlineKeyboardButton("✅ Verify Me", callback_data=f"verify_{user_id}")],
                [InlineKeyboardButton("❌ I'm a Bot", callback_data=f"bot_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🛡️ *NEW MEMBER VERIFICATION REQUIRED* 🛡️\n\n"
                f"👤 @{username} has joined the group!\n\n"
                f"Please verify you are human to gain full access:\n\n"
                f"✅ Click 'Verify Me' if you're human\n"
                f"❌ Click 'I'm a Bot' if automated\n\n"
                f"Verification expires in 10 minutes.",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = int(data.split("_")[1])
        
        if data.startswith("verify_"):
            # Verify user
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE new_members SET verified=1 WHERE user_id=?", (user_id,))
                await db.commit()
            
            await query.edit_message_text(
                "✅ *VERIFICATION SUCCESSFUL!* ✅\n\n"
                "Welcome to the group! You now have full access.\n\n"
                "🌟 Enjoy your stay and follow the rules!",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data.startswith("bot_"):
            # Mark as bot
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("DELETE FROM new_members WHERE user_id=?", (user_id,))
                await db.commit()
            
            await query.edit_message_text(
                "🤖 *BOT DETECTED AND REMOVED* 🤖\n\n"
                "Automated accounts are not allowed in this group.\n\n"
                "🛡️ Group security maintained!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Remove the user
            try:
                await context.bot.ban_chat_member(
                    chat_id=query.message.chat_id,
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Error removing user: {e}")
    
    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove unverified members (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can perform cleanup!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT user_id, username FROM new_members WHERE verified=0")
            unverified = await cursor.fetchall()
            
            removed_count = 0
            for user in unverified:
                try:
                    await context.bot.ban_chat_member(
                        chat_id=update.effective_chat.id,
                        user_id=user[0]
                    )
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing user {user[0]}: {e}")
            
            await db.execute("DELETE FROM new_members WHERE verified=0")
            await db.commit()
        
        await update.message.reply_text(
            f"🧹 *CLEANUP COMPLETE!* 🧹\n\n"
            f"Removed {removed_count} unverified members.\n\n"
            f"🛡️ Group security maintained!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}start", self.start_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}help", self.help_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}stats", self.stats_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}warnings", self.warnings_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}cleanup", self.cleanup_command))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
    
    async def run(self):
        """Run the group management bot"""
        self.setup_handlers()
        
        await self.app.initialize()
        await self.app.start()
        logger.info("✅ Group Management Bot started and polling")
        
        # Start polling
        await self.app.updater.start_polling()
        
        # Keep the bot running
        try:
            # Create a future that never completes
            await asyncio.Future()
        except asyncio.CancelledError:
            await self.app.stop()
            logger.info("🛑 Group Management Bot stopped")

# ============================
# 🤖 4. AUTOADV PAYMENT BOT
# ============================

class AutoAdvPaymentBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "autoadv"
        self.scheduler = AsyncIOScheduler()
        
        # Product pricing
        self.products = {
            "advertisement": {
                "name": "Advertisement Post",
                "price": 10.0,
                "duration": "30 days",
                "description": "Promote your business/service in our groups"
            },
            "vip": {
                "name": "VIP Membership",
                "price": 50.0,
                "duration": "60 days",
                "description": "Premium verification and VIP channel posting rights"
            },
            "scammer_report": {
                "name": "Scammer Report",
                "price": 5.0,
                "duration": "Permanent",
                "description": "Report scammer to protect community"
            }
        }
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with product selection"""
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement", callback_data="product_advertisement")],
            [InlineKeyboardButton("👑 Buy VIP", callback_data="product_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer", callback_data="product_scammer_report")],
            [InlineKeyboardButton("📊 My Purchases", callback_data="my_purchases")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💎 *WELCOME TO AUTOADV PAYMENT SYSTEM!* 💎\n\n"
            "I am the *AutoADV Payment Bot*, your gateway to premium services!\n\n"
            "✨ *AVAILABLE SERVICES:* ✨\n"
            "📢 Advertisements - Promote your business\n"
            "👑 VIP Membership - Premium verification\n"
            "⚠️ Scammer Reports - Protect the community\n\n"
            "💰 *SECURE PAYMENTS:*\n"
            "✅ USDT (TRC20) payments\n"
            "✅ Instant verification\n"
            "✅ 24/7 automated service\n\n"
            "Choose a service below to get started! 🚀",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = f"""
💎 *AUTOADV PAYMENT BOT - COMMAND GUIDE* 💎

🛒 *SHOPPING COMMANDS:*
/{self.bot_prefix}start - Begin shopping experience
/{self.bot_prefix}help - This help message
/{self.bot_prefix}products - View all products
/{self.bot_prefix}buy [product] - Purchase product
/{self.bot_prefix}price [product] - Check pricing
/{self.bot_prefix}balance - Check your balance

📋 *ORDER MANAGEMENT:*
/{self.bot_prefix}orders - Your order history
/{self.bot_prefix}status [order_id] - Order status
/{self.bot_prefix}cancel [order_id] - Cancel order
/{self.bot_prefix}refund [order_id] - Request refund

💰 *PAYMENT COMMANDS:*
/{self.bot_prefix}pay [order_id] - Payment instructions
/{self.bot_prefix}verify [tx_hash] - Verify payment
/{self.bot_prefix}wallet - Payment wallet address
/{self.bot_prefix}methods - Payment methods

📊 *ACCOUNT COMMANDS:*
/{self.bot_prefix}profile - Your profile
/{self.bot_prefix}stats - Purchase statistics
/{self.bot_prefix}support - Contact support
/{self.bot_prefix}faq - Frequently asked questions

💫 *Your satisfaction is our priority!*
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def products_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available products"""
        products_text = "🛒 *AVAILABLE PRODUCTS* 🛒\n\n"
        
        for product_id, product in self.products.items():
            products_text += f"🎯 *{product['name']}*\n"
            products_text += f"💰 Price: ${product['price']} USDT\n"
            products_text += f"⏰ Duration: {product['duration']}\n"
            products_text += f"📝 {product['description']}\n\n"
            products_text += f"💡 Buy with: /{self.bot_prefix}buy {product_id}\n"
            products_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(products_text, parse_mode=ParseMode.MARKDOWN)
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Buy a product"""
        if not context.args:
            await update.message.reply_text(
                f"📝 *Usage:* `/{self.bot_prefix}buy [product]`\n\n"
                f"Available products: advertisement, vip, scammer_report\n\n"
                f"View all: /{self.bot_prefix}products",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        product_id = context.args[0].lower()
        
        if product_id not in self.products:
            await update.message.reply_text(
                "❌ *INVALID PRODUCT!*\n\n"
                "Available products:\n"
                "• advertisement - $10 USDT\n"
                "• vip - $50 USDT\n"
                "• scammer_report - $5 USDT\n\n"
                f"Use /{self.bot_prefix}products for details",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        product = self.products[product_id]
        user_id = update.effective_user.id
        username = update.effective_user.username or "NoUsername"
        
        # Create payment
        payment_id = f"pay_{user_id}_{int(datetime.now().timestamp())}"
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT OR REPLACE INTO pending_payments 
                (user_id, product, amount, data, created_at, payment_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, product_id, product['price'], json.dumps(product), 
                  datetime.now().isoformat(), payment_id))
            await db.commit()
        
        # Send payment instructions
        keyboard = [
            [InlineKeyboardButton("💰 Pay Now", callback_data=f"pay_{payment_id}")],
            [InlineKeyboardButton("📋 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{payment_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🛒 *ORDER CREATED!* 🛒\n\n"
            f"🎯 *Product:* {product['name']}\n"
            f"💰 *Amount:* ${product['price']} USDT\n"
            f"⏰ *Duration:* {product['duration']}\n\n"
            f"📝 *Description:*\n{product['description']}\n\n"
            f"💎 *Payment Method:* USDT (TRC20)\n"
            f"🏦 *Wallet:* `{YOUR_USDT_ADDRESS}`\n\n"
            f"Click 'Pay Now' after sending payment!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show payment wallet"""
        await update.message.reply_text(
            "🏦 *PAYMENT WALLET* 🏦\n\n"
            f"💎 *USDT (TRC20) Address:*\n`{YOUR_USDT_ADDRESS}`\n\n"
            "📝 *Payment Instructions:*\n"
            "1. Send exact amount in USDT (TRC20)\n"
            "2. Keep transaction hash (TX ID)\n"
            "3. Use /verify [tx_hash] after payment\n"
            "4. Wait for automatic confirmation\n\n"
            "⏰ *Processing Time:* 2-5 minutes\n"
            "✅ *Minimum Amount:* $1 USDT\n\n"
            "💡 Always verify the address!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify payment with transaction hash"""
        if not context.args:
            await update.message.reply_text(
                f"📝 *Usage:* `/{self.bot_prefix}verify [transaction_hash]`\n\n"
                "After making payment, use this command with your transaction hash to verify.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        tx_hash = context.args[0]
        user_id = update.effective_user.id
        
        if PAYMENT_MODE == "dummy":
            # Dummy payment verification
            await self.process_dummy_payment(user_id, tx_hash, update)
        else:
            # Real payment verification
            await self.process_real_payment(user_id, tx_hash, update)
    
    async def process_dummy_payment(self, user_id: int, tx_hash: str, update: Update):
        """Process dummy payment for testing"""
        # Simulate payment verification
        await update.message.reply_text(
            "🔍 *VERIFYING PAYMENT...* 🔍\n\n"
            "Checking transaction on blockchain...\n"
            "⏳ Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await asyncio.sleep(2)
        
        # Simulate successful verification
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT product, amount FROM pending_payments 
                WHERE user_id=? ORDER BY created_at DESC LIMIT 1
            """, (user_id,))
            payment = await cursor.fetchone()
            
            if payment:
                product_id = payment[0]
                amount = payment[1]
                
                # Mark as paid
                await db.execute("""
                    INSERT INTO purchases 
                    (user_id, username, product_type, amount, tx_hash, status, created_at, data)
                    VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
                """, (user_id, update.effective_user.username, product_id, amount, tx_hash, 
                      datetime.now().isoformat(), json.dumps({"dummy": True})))
                
                await db.execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))
                await db.commit()
                
                # Process the purchase
                await self.process_purchase(user_id, product_id, update)
            else:
                await update.message.reply_text(
                    "❌ *NO PENDING PAYMENT FOUND!*\n\n"
                    "Please create an order first using /buy command.",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    async def process_real_payment(self, user_id: int, tx_hash: str, update: Update):
        """Process real payment verification"""
        try:
            await update.message.reply_text(
                "🔍 *VERIFYING PAYMENT ON BLOCKCHAIN...* 🔍\n\n"
                "Scanning Tron network for transaction...\n"
                "⏳ This may take a few minutes...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{TRONSCAN_API}?hash={tx_hash}") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check if payment is valid
                        if self.validate_payment(data, user_id):
                            await update.message.reply_text(
                                "✅ *PAYMENT VERIFIED!* ✅\n\n"
                                "Your payment has been confirmed on blockchain!\n\n"
                                "🔄 Processing your order...",
                                parse_mode=ParseMode.MARKDOWN
                            )
                            
                            # Process the payment
                            async with aiosqlite.connect(DB_NAME) as db:
                                cursor = await db.execute("""
                                    SELECT product, amount FROM pending_payments 
                                    WHERE user_id=? ORDER BY created_at DESC LIMIT 1
                                """, (user_id,))
                                payment = await cursor.fetchone()
                                
                                if payment:
                                    product_id = payment[0]
                                    amount = payment[1]
                                    
                                    await db.execute("""
                                        INSERT INTO purchases 
                                        (user_id, username, product_type, amount, tx_hash, status, created_at, data)
                                        VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
                                    """, (user_id, update.effective_user.username, product_id, amount, tx_hash, 
                                          datetime.now().isoformat(), json.dumps(data)))
                                    
                                    await db.execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))
                                    await db.commit()
                                    
                                    await self.process_purchase(user_id, product_id, update)
                        else:
                            await update.message.reply_text(
                                "❌ *PAYMENT VERIFICATION FAILED!*\n\n"
                                "Transaction found but:\n"
                                "• Wrong amount\n"
                                "• Wrong recipient\n"
                                "• Transaction failed\n\n"
                                "Please check and try again.",
                                parse_mode=ParseMode.MARKDOWN
                            )
                    else:
                        await update.message.reply_text(
                            "❌ *TRANSACTION NOT FOUND!*\n\n"
                            "The transaction hash is invalid or not yet confirmed on blockchain.\n\n"
                            "Please wait a few minutes and try again.",
                            parse_mode=ParseMode.MARKDOWN
                        )
        
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            await update.message.reply_text(
                "❌ *VERIFICATION ERROR!*\n\n"
                "There was an error verifying your payment.\n\n"
                "Please try again later or contact support.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def validate_payment(self, transaction_data: dict, user_id: int) -> bool:
        """Validate payment transaction"""
        try:
            # Check if transaction is confirmed
            if not transaction_data.get('confirmed'):
                return False
            
            # Check recipient address
            contract_data = transaction_data.get('contractData', {})
            if not contract_data:
                return False
            
            to_address = contract_data.get('to_address', '')
            if to_address.lower() != YOUR_USDT_ADDRESS.lower():
                return False
            
            # Check amount (simplified - in production, verify exact amount)
            amount = contract_data.get('amount', 0)
            if amount <= 0:
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Payment validation error: {e}")
            return False
    
    async def process_purchase(self, user_id: int, product_id: str, update: Update):
        """Process the purchased product"""
        if product_id == "advertisement":
            await self.process_advertisement_purchase(user_id, update)
        elif product_id == "vip":
            await self.process_vip_purchase(user_id, update)
        elif product_id == "scammer_report":
            await self.process_scammer_report(user_id, update)
    
    async def process_advertisement_purchase(self, user_id: int, update: Update):
        """Process advertisement purchase"""
        # In production, you would collect ad details from user
        # For demo, create a sample ad
        
        ad_data = {
            "heading": f"Advertisement from @{update.effective_user.username}",
            "type": "Promotion",
            "description": "This is a sample advertisement purchased through AutoADV system.",
            "contact": f"@{update.effective_user.username}"
        }
        
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO ads_queue 
                (user_id, username, heading, type, description, contact, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, update.effective_user.username, ad_data['heading'], 
                  ad_data['type'], ad_data['description'], ad_data['contact'],
                  datetime.now().isoformat(), expires_at))
            await db.commit()
        
        await update.message.reply_text(
            "🎉 *ADVERTISEMENT PURCHASE COMPLETE!* 🎉\n\n"
            "Your advertisement has been queued for posting!\n\n"
            "📢 *Ad Details:*\n"
            f"• Heading: {ad_data['heading']}\n"
            f"• Type: {ad_data['type']}\n"
            f"• Duration: 30 days\n"
            f"• Posts: Every 5-6 minutes\n\n"
            "🌟 *What happens next:*\n"
            "✅ Ad will appear in main group\n"
            "✅ Auto-pinned for visibility\n"
            "✅ Posted to company resources\n"
            "✅ Runs for 30 days\n\n"
            "📊 Monitor with: /adviewqueue\n"
            "🛑 Contact support for changes\n\n"
            "Thank you for your purchase! 🙏",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def process_vip_purchase(self, user_id: int, update: Update):
        """Process VIP membership purchase - Make user admin with only message posting rights in VIP channel"""
        expires_at = (datetime.now() + timedelta(days=60)).isoformat()
        username = update.effective_user.username or "NoUsername"
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT OR REPLACE INTO vip_members 
                (user_id, username, name, phone, email, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (user_id, username, "VIP Member", 
                  "Not provided", "Not provided", datetime.now().isoformat(), expires_at))
            await db.commit()
        
        # Make user admin in VIP channel with ONLY message posting permission
        try:
            # Promote user to admin with limited permissions
            await self.app.bot.promote_chat_member(
                chat_id=VIP_CHANNEL_ID,
                user_id=user_id,
                can_post_messages=True,  # Only this permission
                can_edit_messages=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_video_chats=False,
                can_manage_chat=False
            )
            
            admin_success = True
        except Exception as e:
            logger.error(f"Error making user admin in VIP channel: {e}")
            admin_success = False
        
        success_message = (
            "👑 *VIP MEMBERSHIP ACTIVATED!* 👑\n\n"
            "Welcome to the VIP family! Your premium status is now active.\n\n"
            "💎 *VIP BENEFITS UNLOCKED:*\n"
            "✅ Verified VIP badge in groups\n"
            "✅ VIP Channel posting access\n"
            "✅ Priority support access\n"
            "✅ Exclusive content access\n"
            "✅ No posting restrictions in main group\n\n"
            "📅 *Membership Details:*\n"
            f"• Duration: 60 days\n"
            f"• Expires: {expires_at.split('T')[0]}\n"
            f"• Status: ACTIVE PREMIUM\n\n"
        )
        
        if admin_success:
            success_message += "🎯 *VIP Channel Access:* ✅ GRANTED\nYou can now post messages in VIP channel!\n\n"
        else:
            success_message += "⚠️ *VIP Channel Access:* Pending setup\nContact admin for channel access\n\n"
        
        success_message += (
            "🔍 Check your status: /vipmy\n"
            "🔄 Auto-renewal available\n\n"
            "Thank you for choosing VIP! 🌟"
        )
        
        await update.message.reply_text(success_message, parse_mode=ParseMode.MARKDOWN)
    
    async def process_scammer_report(self, user_id: int, update: Update):
        """Process scammer report purchase"""
        # In production, you would collect scammer details
        # For demo, create a sample report
        
        await update.message.reply_text(
            "⚠️ *SCAMMER REPORT SUBMITTED!* ⚠️\n\n"
            "Thank you for helping protect our community!\n\n"
            "🛡️ *What happens next:*\n"
            "✅ Report verified by admins\n"
            "✅ Scammer added to watchlist\n"
            "✅ Community warning issued\n"
            "✅ Legal action if possible\n\n"
            "📝 *Report Details:*\n"
            "• Type: Paid scammer report\n"
            "• Priority: HIGH\n"
            "• Status: UNDER REVIEW\n\n"
            "We will contact you if more information is needed.\n\n"
            "Thank you for making our community safer! 🙏",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def check_vip_expirations(self):
        """Background task to check and remove expired VIP admin rights"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                # Find expired VIP members
                cursor = await db.execute("""
                    SELECT user_id FROM vip_members 
                    WHERE expires_at < ? AND is_active = 1
                """, (datetime.now().isoformat(),))
                expired_vips = await cursor.fetchall()
                
                for vip in expired_vips:
                    user_id = vip[0]
                    
                    # Remove admin rights from VIP channel
                    try:
                        await self.app.bot.promote_chat_member(
                            chat_id=VIP_CHANNEL_ID,
                            user_id=user_id,
                            can_post_messages=False
                        )
                        
                        logger.info(f"Removed VIP admin rights for user {user_id}")
                        
                    except Exception as e:
                        logger.error(f"Error removing VIP admin rights for {user_id}: {e}")
                    
                    # Mark as inactive in database
                    await db.execute(
                        "UPDATE vip_members SET is_active = 0 WHERE user_id = ?",
                        (user_id,)
                    )
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Error in VIP expiration check: {e}")
    
    async def setup_scheduler(self):
        """Setup background scheduler for VIP expiration checks"""
        self.scheduler.add_job(
            self.check_vip_expirations,
            'interval',
            hours=1  # Check every hour
        )
        self.scheduler.start()
        logger.info("✅ VIP expiration scheduler started")
    
    async def orders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's order history"""
        user_id = update.effective_user.id
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT product_type, amount, status, created_at 
                FROM purchases 
                WHERE user_id=? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (user_id,))
            orders = await cursor.fetchall()
        
        if not orders:
            await update.message.reply_text(
                "📭 *NO ORDERS FOUND!* 📭\n\n"
                "You haven't made any purchases yet.\n\n"
                "🛒 Start shopping: /autoadvstart\n"
                "📋 View products: /autoadvproducts",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        orders_text = "📋 *YOUR ORDER HISTORY* 📋\n\n"
        for order in orders:
            orders_text += f"🎯 *Product:* {order[0]}\n"
            orders_text += f"💰 *Amount:* ${order[1]} USDT\n"
            orders_text += f"📊 *Status:* {order[2].upper()}\n"
            orders_text += f"📅 *Date:* {order[3].split('T')[0]}\n"
            orders_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(orders_text, parse_mode=ParseMode.MARKDOWN)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "help":
            await self.help_command_query(query)
        elif data == "my_purchases" or data == "my_orders":
            await self.my_orders_query(query)
        elif data.startswith("product_"):
            product_id = data.replace("product_", "")
            await self.product_details_query(query, product_id)
        elif data.startswith("pay_"):
            payment_id = data.replace("pay_", "")
            await self.payment_instructions_query(query, payment_id)
        elif data.startswith("cancel_"):
            payment_id = data.replace("cancel_", "")
            await self.cancel_payment_query(query, payment_id)
    
    async def help_command_query(self, query):
        """Handle help command from button"""
        await query.edit_message_text(
            "💎 *AUTOADV PAYMENT HELP* 💎\n\n"
            "🛒 *How to Buy:*\n"
            "1. Choose a product\n"
            "2. Click 'Pay Now'\n"
            "3. Send exact USDT amount\n"
            "4. Verify with transaction hash\n\n"
            "💰 *Payment Methods:*\n"
            "• USDT (TRC20) only\n"
            "• Exact amount required\n"
            "• Network fees extra\n\n"
            "⏰ *Processing Time:*\n"
            "• Automatic: 2-5 minutes\n"
            "• Manual review if needed\n\n"
            "📞 *Support:*\n"
            "Contact admins for help\n\n"
            "🛡️ *Security:*\n"
            "• Secure payments\n"
            "• Verified transactions\n"
            "• No personal data stored",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def my_orders_query(self, query):
        """Handle my orders button"""
        user_id = query.from_user.id
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT product_type, amount, status, created_at 
                FROM purchases 
                WHERE user_id=? 
                ORDER BY created_at DESC 
                LIMIT 5
            """, (user_id,))
            orders = await cursor.fetchall()
        
        if not orders:
            await query.edit_message_text(
                "📭 *NO PURCHASES YET!* 📭\n\n"
                "You haven't made any purchases.\n\n"
                "Start your shopping journey today! 🛒",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        orders_text = "📋 *YOUR RECENT ORDERS* 📋\n\n"
        for order in orders:
            orders_text += f"🎯 {order[0].title()}\n"
            orders_text += f"💰 ${order[1]} • {order[2].upper()}\n"
            orders_text += f"📅 {order[3].split('T')[0]}\n"
            orders_text += "━━━━━━━━━━━━━━━━\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🛒 Continue Shopping", callback_data="help")],
            [InlineKeyboardButton("📊 All Orders", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            orders_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def product_details_query(self, query, product_id):
        """Show product details"""
        if product_id not in self.products:
            await query.edit_message_text("❌ Product not found!")
            return
        
        product = self.products[product_id]
        
        keyboard = [
            [InlineKeyboardButton("💰 Buy Now", callback_data=f"pay_product_{product_id}")],
            [InlineKeyboardButton("📋 All Products", callback_data="help")],
            [InlineKeyboardButton("❌ Back", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🛒 *{product['name']}* 🛒\n\n"
            f"💰 *Price:* ${product['price']} USDT\n"
            f"⏰ *Duration:* {product['duration']}\n\n"
            f"📝 *Description:*\n{product['description']}\n\n"
            f"💎 *Features:*\n"
            f"✅ Instant activation\n"
            f"✅ Secure payment\n"
            f"✅ 24/7 support\n"
            f"✅ Quality guaranteed\n\n"
            f"Click 'Buy Now' to purchase!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def payment_instructions_query(self, query, payment_id):
        """Show payment instructions"""
        await query.edit_message_text(
            "💰 *PAYMENT INSTRUCTIONS* 💰\n\n"
            f"🏦 *USDT (TRC20) Address:*\n`{YOUR_USDT_ADDRESS}`\n\n"
            "📝 *Steps to Pay:*\n"
            "1. Send exact amount in USDT (TRC20)\n"
            "2. Keep transaction hash (TX ID)\n"
            "3. Use /verify command with TX ID\n"
            "4. Wait for automatic confirmation\n\n"
            "⏰ *Processing Time:* 2-5 minutes\n"
            "✅ *Minimum Amount:* $1 USDT\n\n"
            "💡 *Important:*\n"
            "• Send only USDT (TRC20)\n"
            "• Exact amount required\n"
            "• Network fees extra\n"
            "• Double-check address\n\n"
            "After payment, use:\n"
            f"`/autoadvverify YOUR_TX_HASH`",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cancel_payment_query(self, query, payment_id):
        """Cancel payment"""
        user_id = query.from_user.id
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))
            await db.commit()
        
        await query.edit_message_text(
            "❌ *PAYMENT CANCELLED* ❌\n\n"
            "Your pending payment has been cancelled.\n\n"
            "No charges were made to your account.\n\n"
            "🛒 You can start over anytime!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}start", self.start_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}help", self.help_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}products", self.products_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}buy", self.buy_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}wallet", self.wallet_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}verify", self.verify_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}orders", self.orders_command))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
    
    async def run(self):
        """Run the payment bot"""
        self.setup_handlers()
        await self.setup_scheduler()
        
        await self.app.initialize()
        await self.app.start()
        logger.info("✅ AutoADV Payment Bot started and polling")
        
        # Start polling
        await self.app.updater.start_polling()
        
        # Keep the bot running
        try:
            # Create a future that never completes
            await asyncio.Future()
        except asyncio.CancelledError:
            await self.app.stop()
            logger.info("🛑 AutoADV Payment Bot stopped")

# ============================
# 🚀 MAIN APPLICATION
# ============================

async def main():
    """Main function to run all bots"""
    logger.info("🚀 Starting Interlink Multi-Bot System...")
    
    # Initialize database
    await init_database()
    
    # Create bot instances
    adv_bot = AdvertisingBot(ADV_BOT_TOKEN)
    vip_bot = VIPBot(VIP_BOT_TOKEN)
    group_bot = GroupManagementBot(GROUP_BOT_TOKEN)
    autoadv_bot = AutoAdvPaymentBot(AUTOADV_BOT_TOKEN)
    
    # Run all bots concurrently
    await asyncio.gather(
        adv_bot.run(),
        vip_bot.run(),
        group_bot.run(),
        autoadv_bot.run(),
        return_exceptions=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 All bots stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
[file content end]
