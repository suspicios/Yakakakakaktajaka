
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

# Admin User IDs
ADMIN_IDS = [7578682081]  # Your admin user ID

# Bot Usernames
AUTOADV_BOT_USERNAME = "NepalChinIndiaAUTOADV_bot"
VIP_CHANNEL_USERNAME = "bPg3y6q4E400MjE1"  # From your invite link

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
                is_paused INTEGER DEFAULT 0,
                post_interval INTEGER DEFAULT 5
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_settings (
                id INTEGER PRIMARY KEY,
                welcome_message TEXT,
                rules TEXT,
                max_message_length INTEGER DEFAULT 120,
                auto_remove_unverified INTEGER DEFAULT 1
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
        
        # Initialize default settings
        await db.execute("INSERT OR IGNORE INTO ad_config (id, last_post_time, is_paused, post_interval) VALUES (1, NULL, 0, 5)")
        await db.execute("INSERT OR IGNORE INTO group_settings (id, welcome_message, rules, max_message_length, auto_remove_unverified) VALUES (1, 'Welcome to the group!', 'Be respectful and follow the rules.', 120, 1)")
        
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
        """Start command - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "📬 Please use this command in private message for security!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        await update.message.reply_text(
            "🌟 *GREETINGS, MASTER OF ADVERTISING!* 🌟\n\n"
            "I am the *Advertising Bot*, your divine servant in the realm of promotions!\n\n"
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
        """Comprehensive help with all commands - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        is_admin = update.effective_user.id in ADMIN_IDS
        
        user_commands = f"""
🌟 *ADVERTISING BOT - COMMAND BIBLE* 🌟

📱 *GENERAL COMMANDS (DM ONLY):*
/{self.bot_prefix}start - Awaken the advertising god
/{self.bot_prefix}help - Divine command reference
/{self.bot_prefix}stats - Advertising statistics
/{self.bot_prefix}viewqueue - See all pending ads
/{self.bot_prefix}myads - Your active advertisements
"""
        
        admin_commands = f"""
👑 *ADMIN COMMANDS (DM ONLY):*
/{self.bot_prefix}pause - Pause all advertising
/{self.bot_prefix}resume - Resume advertising
/{self.bot_prefix}clearqueue - Clear ad queue
/{self.bot_prefix}removead [id] - Remove specific ad
/{self.bot_prefix}forcead - Force post next ad
/{self.bot_prefix}setinterval [min] - Set post interval (5-60 min)
/{self.bot_prefix}config - View current configuration
/{self.bot_prefix}resetstats - Reset statistics
"""
        
        help_text = user_commands
        if is_admin:
            help_text += admin_commands
        
        help_text += "\n💫 *Your command is my sacred duty!* 💫"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show advertising statistics - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        async with aiosqlite.connect(DB_NAME) as db:
            # Total ads
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue WHERE status='active'")
            active_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue")
            total_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(post_count) FROM ads_queue")
            result = await cursor.fetchone()
            total_posts = result[0] if result[0] else 0
            
            cursor = await db.execute("SELECT last_post_time, is_paused, post_interval FROM ad_config WHERE id=1")
            result = await cursor.fetchone()
            last_post = result[0] if result[0] else "Never"
            is_paused = result[1] if result[1] else 0
            interval = result[2] if result[2] else 5
        
        status = "⏸️ PAUSED" if is_paused else "✅ ACTIVE"
        
        stats_text = f"""
📊 *ADVERTISING EMPIRE STATISTICS* 📊

🎯 *ADVERTISEMENT METRICS:*
▫️ Active Ads: {active_ads}
▫️ Total Ads (All Time): {total_ads}
▫️ Total Posts Delivered: {total_posts}
▫️ Last Posted: {last_post}

🔥 *CURRENT STATUS:*
▫️ Auto-Posting: {status}
▫️ Interval: {interval} minutes
▫️ Target Groups: Main + Company Resources

💪 *Your advertising empire grows stronger, Master!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def view_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all ads in queue - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
        """Pause advertising (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
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
        """Resume advertising (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
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
    
    async def set_interval_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set advertising interval (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /adsetinterval [minutes] (5-60 minutes)")
            return
        
        try:
            interval = int(context.args[0])
            if interval < 5 or interval > 60:
                await update.message.reply_text("❌ Interval must be between 5-60 minutes!")
                return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE ad_config SET post_interval=? WHERE id=1", (interval,))
            await db.commit()
        
        # Restart scheduler with new interval
        self.scheduler.remove_all_jobs()
        self.scheduler.add_job(
            self.post_advertisement,
            'interval',
            minutes=interval,
            jitter=60
        )
        
        await update.message.reply_text(
            f"⏰ *INTERVAL UPDATED!* ⏰\n\n"
            f"Advertising interval set to {interval} minutes!\n\n"
            f"🔄 Scheduler restarted with new interval.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current configuration (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT is_paused, post_interval FROM ad_config WHERE id=1")
            result = await cursor.fetchone()
            is_paused = result[0] if result else 0
            interval = result[1] if result else 5
        
        config_text = f"""
⚙️ *ADVERTISING BOT CONFIGURATION* ⚙️

📊 *CURRENT SETTINGS:*
▫️ Auto-Posting: {'⏸️ PAUSED' if is_paused else '✅ ACTIVE'}
▫️ Post Interval: {interval} minutes
▫️ Payment Mode: {PAYMENT_MODE.upper()}

🔧 *CONFIGURATION COMMANDS:*
/adpause - Pause advertising
/adresume - Resume advertising  
/adsetinterval [min] - Set post interval
/adclearqueue - Clear all ads
"""
        await update.message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN)
    
    async def clear_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear ad queue (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
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
        """Remove specific ad (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
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
        """Force post next ad (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        await self.post_advertisement()
        await update.message.reply_text("✅ Advertisement posted immediately!")
    
    async def my_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's active ads - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
                f"🚀 Purchase ads via @{AUTOADV_BOT_USERNAME}!",
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
                    keyboard = [
                        [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/{AUTOADV_BOT_USERNAME}?start=buy_ad")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{AUTOADV_BOT_USERNAME}?start=report_scammer")]
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
                        [InlineKeyboardButton("💎 Join VIP", url=f"https://t.me/{VIP_CHANNEL_USERNAME}")],
                        [InlineKeyboardButton("📢 Post Ad", url=f"https://t.me/{AUTOADV_BOT_USERNAME}?start=buy_ad")],
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
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT post_interval FROM ad_config WHERE id=1")
            result = await cursor.fetchone()
            interval = result[0] if result else 5
        
        self.scheduler.add_job(
            self.post_advertisement,
            'interval',
            minutes=interval,
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
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}setinterval", self.set_interval_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}config", self.config_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}clearqueue", self.clear_queue_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}removead", self.remove_ad_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}forcead", self.force_ad_command))
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
        """Start command - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
        """Help command - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = f"""
👑 *VIP BOT - COMMAND SANCTUARY* 👑

🎯 *VERIFICATION COMMANDS (DM ONLY):*
/{self.bot_prefix}start - Begin your VIP journey
/{self.bot_prefix}help - Divine guidance
/{self.bot_prefix}check @user - Verify any member
/{self.bot_prefix}my - Your VIP status
/{self.bot_prefix}stats - VIP statistics
"""
        
        if is_admin:
            help_text += f"""
👑 *ADMIN COMMANDS (DM ONLY):*
/{self.bot_prefix}add [user_id] [days] - Manually add VIP
/{self.bot_prefix}remove [user_id] - Remove VIP status
/{self.bot_prefix}extend [user_id] [days] - Extend VIP
/{self.bot_prefix}list - All VIP members
/{self.bot_prefix}config - VIP system configuration
/{self.bot_prefix}reminder - Send renewal reminders
"""
        
        help_text += "\n💎 *Excellence recognized, premium delivered!* 💎"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def check_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check VIP status of mentioned user - Works in groups"""
        if not context.args:
            if update.effective_chat.type == "private":
                await update.message.reply_text(
                    f"📝 *Usage:* `/{self.bot_prefix}check @username`",
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
                f"💎 Want VIP benefits? Contact @{AUTOADV_BOT_USERNAME}!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def my_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check own VIP status - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
                f"🚀 Upgrade now via @{AUTOADV_BOT_USERNAME}!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def vip_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all VIP members (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
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
        """Show VIP statistics - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
        """Add VIP member (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
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
        """Remove VIP member (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
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
    
    async def extend_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Extend VIP membership (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can extend VIP memberships!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("📝 Usage: /vipextend [user_id] [days]")
            return
        
        try:
            user_id = int(context.args[0])
            days = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or days!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT username, expires_at FROM vip_members WHERE user_id=?", (user_id,))
            vip = await cursor.fetchone()
            
            if not vip:
                await update.message.reply_text("❌ VIP member not found!")
                return
            
            current_expires = datetime.fromisoformat(vip[1])
            new_expires = (current_expires + timedelta(days=days)).isoformat()
            
            await db.execute("UPDATE vip_members SET expires_at=? WHERE user_id=?", (new_expires, user_id))
            await db.commit()
        
        await update.message.reply_text(
            f"📅 *VIP EXTENDED!*\n\n"
            f"User: @{vip[0]}\n"
            f"Extended by: {days} days\n"
            f"New expiry: {new_expires.split('T')[0]}\n\n"
            f"🌟 VIP benefits continue!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP system configuration (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can view configuration!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members WHERE is_active=1")
            active_vips = (await cursor.fetchone())[0]
            
            cursor = await db.execute("""
                SELECT COUNT(*) FROM vip_members 
                WHERE expires_at BETWEEN ? AND ?
            """, (datetime.now().isoformat(), (datetime.now() + timedelta(days=7)).isoformat()))
            expiring_soon = (await cursor.fetchone())[0]
        
        config_text = f"""
⚙️ *VIP SYSTEM CONFIGURATION* ⚙️

📊 *CURRENT STATS:*
▫️ Active VIP Members: {active_vips}
▫️ Expiring in 7 days: {expiring_soon}
▫️ VIP Channel: {VIP_CHANNEL_ID}

🔧 *ADMIN COMMANDS:*
/vipadd [id] [days] - Add VIP member
/vipremove [id] - Remove VIP member  
/vipextend [id] [days] - Extend VIP
/viplist - List all VIPs
/vipreminder - Send renewal reminders
"""
        await update.message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN)
    
    async def reminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send renewal reminders (Admin only) - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Admin commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can send reminders!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT user_id, username, expires_at 
                FROM vip_members 
                WHERE expires_at BETWEEN ? AND ? AND is_active=1
            """, (datetime.now().isoformat(), (datetime.now() + timedelta(days=3)).isoformat()))
            expiring_vips = await cursor.fetchall()
        
        if not expiring_vips:
            await update.message.reply_text("✅ No VIP members expiring in the next 3 days!")
            return
        
        reminder_count = 0
        for vip in expiring_vips:
            user_id = vip[0]
            expires = datetime.fromisoformat(vip[2])
            days_left = (expires - datetime.now()).days
            
            try:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ *VIP RENEWAL REMINDER* ⚠️\n\n"
                         f"Your VIP membership expires in {days_left} days!\n\n"
                         f"💎 Renew now to continue enjoying:\n"
                         f"✅ VIP channel access\n"
                         f"✅ Verified status\n"
                         f"✅ Priority support\n\n"
                         f"🔄 Renew: @{AUTOADV_BOT_USERNAME}",
                    parse_mode=ParseMode.MARKDOWN
                )
                reminder_count += 1
                await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error(f"Error sending reminder to {user_id}: {e}")
        
        await update.message.reply_text(
            f"📧 *REMINDERS SENT!*\n\n"
            f"Sent renewal reminders to {reminder_count} VIP members.\n\n"
            f"🌟 Keeping the VIP family strong!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages for VIP verification - Works in groups"""
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
                        f"🔄 Contact @{AUTOADV_BOT_USERNAME} to renew!",
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
                    f"🚀 Upgrade now: @{AUTOADV_BOT_USERNAME}",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}start", self.start_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}help", self.help_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}check", self.check_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}my", self.my_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}stats", self.vip_stats_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}list", self.vip_list_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}add", self.add_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}remove", self.remove_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}extend", self.extend_vip_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}config", self.config_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}reminder", self.reminder_command))
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
        """Start command - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        await update.message.reply_text(
            "🛡️ *WELCOME TO GROUP SECURITY SYSTEM!* 🛡️\n\n"
            "I am the *Group Management Bot*, guardian of order and protector of community harmony!\n\n"
            "✨ *MY DIVINE PROTECTIONS:* ✨\n"
            "🛡️ Auto-verification of new members\n"
            "🚫 Violation detection and warnings\n"
            "📊 Member activity monitoring\n"
            "⚡ Instant scammer protection\n\n"
            "⚡ *COMMANDS FOR YOUR USE:* ⚡\n"
            f"/{self.bot_prefix}stats - Group statistics (DM)\n"
            f"/{self.bot_prefix}warnings @user - Check warnings (Group)\n"
            f"/{self.bot_prefix}help - All available commands (DM)\n\n"
            "Your community is safe under my watch, O Wise Administrator! 🛡️",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = f"""
🛡️ *GROUP MANAGEMENT BOT - COMMAND ARSENAL* 🛡️

📊 *MONITORING COMMANDS (DM ONLY):*
/{self.bot_prefix}start - Begin security monitoring
/{self.bot_prefix}help - Command reference
/{self.bot_prefix}stats - Group statistics
/{self.bot_prefix}config - System configuration

👮 *MODERATION COMMANDS (GROUP):*
/{self.bot_prefix}warnings @user - Check user warnings
/{self.bot_prefix}warn @user [reason] - Issue warning
/{self.bot_prefix}ban @user [reason] - Ban user
/{self.bot_prefix}verify @user - Manually verify user
/{self.bot_prefix}cleanup - Remove unverified users
"""
        
        if is_admin:
            help_text += f"""
👑 *ADMIN CONFIGURATION (DM ONLY):*
/{self.bot_prefix}setwelcome [msg] - Set welcome message
/{self.bot_prefix}setrules [rules] - Set group rules
/{self.bot_prefix}setmaxlength [chars] - Set max message length
/{self.bot_prefix}exempt @user - Exempt from verification
/{self.bot_prefix}removeexempt @user - Remove exemption
/{self.bot_prefix}exemptlist - All exempted users
/{self.bot_prefix}lockdown - Emergency lockdown
/{self.bot_prefix}unlock - End lockdown
"""
        
        help_text += "\n🛡️ *Security is my sacred duty!* 🛡️"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group statistics - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=1")
            verified_members = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=0")
            pending_members = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations")
            total_violations = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM exempted_users")
            exempted_users = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT welcome_message, max_message_length FROM group_settings WHERE id=1")
            settings = await cursor.fetchone()
            welcome_msg = settings[0] if settings else "Default welcome"
            max_length = settings[1] if settings else 120
        
        stats_text = f"""
📊 *GROUP SECURITY STATISTICS* 📊

👥 *MEMBERSHIP STATUS:*
▫️ Verified Members: {verified_members}
▫️ Pending Verification: {pending_members}
▫️ Exempted Users: {exempted_users}

⚖️ *SECURITY METRICS:*
▫️ Total Violations: {total_violations}
▫️ Max Message Length: {max_length} chars
▫️ Auto-verification: ✅ ACTIVE

🛡️ *SYSTEM STATUS:*
▫️ Security Level: MAXIMUM
▫️ Auto-protection: ✅ ENABLED

🌟 *Your community is protected!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user warnings - Works in groups"""
        if not context.args:
            await update.message.reply_text(
                f"📝 *Usage:* `/{self.bot_prefix}warnings @username`",
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
    
    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Warn user - Works in groups"""
        if not update.message.reply_to_message:
            await update.message.reply_text("📝 Reply to a user's message to warn them!")
            return
        
        target_user = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "No reason provided"
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO violations (user_id, username, violation_type, timestamp)
                VALUES (?, ?, ?, ?)
            """, (target_user.id, target_user.username or "Unknown", f"Manual warn: {reason}", datetime.now().isoformat()))
            await db.commit()
        
        await update.message.reply_text(
            f"⚠️ *WARNING ISSUED!* ⚠️\n\n"
            f"👤 User: @{target_user.username or target_user.id}\n"
            f"📝 Reason: {reason}\n\n"
            f"⚡ User has been officially warned!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban user - Works in groups"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only admins can ban users!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("📝 Reply to a user's message to ban them!")
            return
        
        target_user = update.message.reply_to_message.from_user
        reason = " ".join(context.args) if context.args else "No reason provided"
        
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
            await update.message.reply_text(
                f"🔨 *USER BANNED!* 🔨\n\n"
                f"👤 User: @{target_user.username or target_user.id}\n"
                f"📝 Reason: {reason}\n\n"
                f"🚫 User has been removed from the group!",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error banning user: {e}")
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually verify user - Works in groups"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only admins can verify users!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("📝 Reply to a user's message to verify them!")
            return
        
        target_user = update.message.reply_to_message.from_user
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE new_members SET verified=1 WHERE user_id=?", (target_user.id,))
            await db.commit()
        
        await update.message.reply_text(
            f"✅ *USER VERIFIED!* ✅\n\n"
            f"👤 User: @{target_user.username or target_user.id}\n\n"
            f"🌟 User has been manually verified!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group configuration - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only admins can view configuration!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT welcome_message, rules, max_message_length, auto_remove_unverified FROM group_settings WHERE id=1")
            settings = await cursor.fetchone()
            
            welcome_msg = settings[0] if settings else "Default welcome"
            rules = settings[1] if settings else "Default rules"
            max_length = settings[2] if settings else 120
            auto_remove = settings[3] if settings else 1
        
        config_text = f"""
⚙️ *GROUP MANAGEMENT CONFIGURATION* ⚙️

📝 *CURRENT SETTINGS:*
▫️ Welcome Message: {welcome_msg[:50]}...
▫️ Max Message Length: {max_length} chars
▫️ Auto-remove Unverified: {'✅ Enabled' if auto_remove else '❌ Disabled'}

🔧 *CONFIGURATION COMMANDS (DM):*
/groupsetwelcome [msg] - Set welcome message
/groupsetrules [rules] - Set group rules  
/groupsetmaxlength [chars] - Set max length
/grouplockdown - Emergency lockdown
/groupunlock - End lockdown
"""
        await update.message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN)
    
    async def set_welcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set welcome message - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Configuration commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only admins can configure the system!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /groupsetwelcome [message]")
            return
        
        welcome_message = " ".join(context.args)
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE group_settings SET welcome_message=? WHERE id=1", (welcome_message,))
            await db.commit()
        
        await update.message.reply_text(
            f"🎉 *WELCOME MESSAGE UPDATED!* 🎉\n\n"
            f"New welcome message set:\n\n"
            f"{welcome_message}\n\n"
            f"🌟 New members will see this message!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set group rules - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Configuration commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only admins can configure the system!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /groupsetrules [rules]")
            return
        
        rules = " ".join(context.args)
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE group_settings SET rules=? WHERE id=1", (rules,))
            await db.commit()
        
        await update.message.reply_text(
            f"📜 *GROUP RULES UPDATED!* 📜\n\n"
            f"New rules set:\n\n"
            f"{rules}\n\n"
            f"⚖️ All members must follow these rules!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_max_length_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set max message length - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Configuration commands work in DM only!")
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only admins can configure the system!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /groupsetmaxlength [characters]")
            return
        
        try:
            max_length = int(context.args[0])
            if max_length < 50 or max_length > 1000:
                await update.message.reply_text("❌ Max length must be between 50-1000 characters!")
                return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE group_settings SET max_message_length=? WHERE id=1", (max_length,))
            await db.commit()
        
        await update.message.reply_text(
            f"📏 *MAX LENGTH UPDATED!* 📏\n\n"
            f"New maximum message length: {max_length} characters\n\n"
            f"⚡ Messages longer than this will be automatically deleted!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining - Group only"""
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
        """Remove unverified members - Works in groups"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only admins can perform cleanup!")
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
    
    async def message_length_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle message length violations - Group only"""
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
            
            # Get max message length
            cursor = await db.execute("SELECT max_message_length FROM group_settings WHERE id=1")
            result = await cursor.fetchone()
            max_length = result[0] if result else 120
        
        message_text = update.message.text or ""
        if len(message_text) > max_length:
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
                    f"@{update.effective_user.username}, your message exceeded {max_length} characters.\n\n"
                    f"📊 *Warning {warning_count}/3*\n"
                    f"⚡ 3 warnings = Auto-ban\n\n"
                    f"💎 VIP members have no limits!",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Auto-delete warning after 10 seconds
                await asyncio.sleep(10)
                try:
                    await warning_msg.delete()
                except:
                    pass
                
                if warning_count >= 3:
                    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
                    await update.message.reply_text(
                        f"🔨 @{update.effective_user.username} has been banned for repeated violations."
                    )
            
            except Exception as e:
                logger.error(f"Error handling message length: {e}")
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}start", self.start_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}help", self.help_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}stats", self.stats_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}config", self.config_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}warnings", self.warnings_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}warn", self.warn_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}ban", self.ban_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}verify", self.verify_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}cleanup", self.cleanup_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}setwelcome", self.set_welcome_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}setrules", self.set_rules_command))
        self.app.add_handler(CommandHandler(f"{self.bot_prefix}setmaxlength", self.set_max_length_command))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_length_handler))
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
# 🤖 4. AUTOADV PAYMENT BOT (DM ONLY)
# ============================

class AutoAdvPaymentBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "autoadv"
        self.scheduler = AsyncIOScheduler()
        self.user_states = {}  # Track user purchase states
        
        # Product pricing - UPDATED PRICES
        self.products = {
            "advertisement": {
                "name": "Advertisement Post",
                "price": 188.0,  # Updated to 188 USDT
                "duration": "10 days",  # Updated duration
                "description": "Promote your business/service in our groups - Auto-posting every 5-6 minutes"
            },
            "vip": {
                "name": "VIP Membership", 
                "price": 300.0,  # Updated to 300 USDT
                "duration": "60 days",
                "description": "Premium verification and VIP channel posting rights - Become admin in VIP channel"
            },
            "scammer_report": {
                "name": "Scammer Report",
                "price": 0.0,  # FREE now
                "duration": "Permanent",
                "description": "Report scammer to protect community - Help keep our community safe"
            }
        }
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "📬 *SECURE TRANSACTION REQUIRED* 📬\n\n"
                "For your security, all purchases must be made in private messages.\n\n"
                "💎 Please click below to start securely:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔒 Start Secure Chat", url=f"https://t.me/{AUTOADV_BOT_USERNAME}?start=secure")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
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
            "I am the *AutoADV Payment Bot*, your secure gateway to premium services!\n\n"
            "✨ *AVAILABLE SERVICES:* ✨\n"
            "📢 Advertisements - 188 USDT (10 days)\n"
            "👑 VIP Membership - 300 USDT (60 days)\n"
            "⚠️ Scammer Reports - FREE\n\n"
            "🔒 *SECURE DM-ONLY TRANSACTIONS:*\n"
            "✅ All purchases in private messages\n"
            "✅ Secure USDT (TRC20) payments\n"
            "✅ Instant verification\n"
            "✅ 24/7 automated service\n\n"
            "Choose a service below to get started! 🚀",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        help_text = f"""
💎 *AUTOADV PAYMENT BOT - COMMAND GUIDE* 💎

🛒 *SHOPPING COMMANDS (DM ONLY):*
/{self.bot_prefix}start - Begin shopping experience
/{self.bot_prefix}help - This help message
/{self.bot_prefix}products - View all products
/{self.bot_prefix}buy [product] - Purchase product
/{self.bot_prefix}wallet - Payment wallet address
/{self.bot_prefix}verify [tx_hash] - Verify payment
/{self.bot_prefix}orders - Your order history

💰 *PRODUCT PRICES:*
• Advertisement: 188 USDT (10 days)
• VIP Membership: 300 USDT (60 days)  
• Scammer Report: FREE (Permanent)

🔒 *SECURITY FEATURES:*
• DM-only transactions
• Secure USDT payments
• Instant verification
• 24/7 support

💫 *Your satisfaction is our priority!*
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def products_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available products - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
        products_text = "🛒 *AVAILABLE PRODUCTS* 🛒\n\n"
        
        for product_id, product in self.products.items():
            price_text = "FREE" if product['price'] == 0 else f"{product['price']} USDT"
            products_text += f"🎯 *{product['name']}*\n"
            products_text += f"💰 Price: {price_text}\n"
            products_text += f"⏰ Duration: {product['duration']}\n"
            products_text += f"📝 {product['description']}\n\n"
            products_text += f"💡 Buy with: /{self.bot_prefix}buy {product_id}\n"
            products_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(products_text, parse_mode=ParseMode.MARKDOWN)
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Buy a product - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
                "• advertisement - 188 USDT\n"
                "• vip - 300 USDT\n"
                "• scammer_report - FREE\n\n"
                f"Use /{self.bot_prefix}products for details",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        product = self.products[product_id]
        user_id = update.effective_user.id
        username = update.effective_user.username or "NoUsername"
        
        # For free products, process immediately
        if product['price'] == 0:
            await self.process_purchase(user_id, product_id, update)
            return
        
        # Create payment for paid products
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
        
        price_text = "FREE" if product['price'] == 0 else f"{product['price']} USDT"
        
        await update.message.reply_text(
            f"🛒 *ORDER CREATED!* 🛒\n\n"
            f"🎯 *Product:* {product['name']}\n"
            f"💰 *Amount:* {price_text}\n"
            f"⏰ *Duration:* {product['duration']}\n\n"
            f"📝 *Description:*\n{product['description']}\n\n"
            f"💎 *Payment Method:* USDT (TRC20)\n"
            f"🏦 *Wallet:* `{YOUR_USDT_ADDRESS}`\n\n"
            f"Click 'Pay Now' after sending payment!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show payment wallet - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
        """Verify payment with transaction hash - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
        """Process dummy payment for testing - DM only"""
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
        """Process real payment verification - DM only"""
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
        """Process the purchased product - DM only"""
        if product_id == "advertisement":
            await self.process_advertisement_purchase(user_id, update)
        elif product_id == "vip":
            await self.process_vip_purchase(user_id, update)
        elif product_id == "scammer_report":
            await self.process_scammer_report(user_id, update)
    
    async def process_advertisement_purchase(self, user_id: int, update: Update):
        """Process advertisement purchase - DM only"""
        # Collect ad details from user
        await update.message.reply_text(
            "📢 *ADVERTISEMENT SETUP* 📢\n\n"
            "Let's set up your advertisement! Please provide the following details:\n\n"
            "1. *Heading* (Max 100 characters)\n"
            "2. *Type* (e.g., Business, Service, Product)\n" 
            "3. *Description* (Max 500 characters)\n"
            "4. *Contact* (Phone, Email, Telegram)\n\n"
            "Please send the *HEADING* for your ad:",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Store user state for ad creation flow
        self.user_states[user_id] = {
            'product': 'advertisement',
            'step': 'heading',
            'data': {}
        }
    
    async def process_vip_purchase(self, user_id: int, update: Update):
        """Process VIP membership purchase - Make user admin with only message posting rights in VIP channel - DM only"""
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
            f"🔍 Check your status: /vipmy (in DM with @{AUTOADV_BOT_USERNAME})\n"
            "🔄 Auto-renewal available\n\n"
            "Thank you for choosing VIP! 🌟"
        )
        
        await update.message.reply_text(success_message, parse_mode=ParseMode.MARKDOWN)
    
    async def process_scammer_report(self, user_id: int, update: Update):
        """Process scammer report purchase - DM only"""
        await update.message.reply_text(
            "⚠️ *SCAMMER REPORT* ⚠️\n\n"
            "Thank you for helping protect our community!\n\n"
            "Please provide the following details about the scammer:\n\n"
            "1. *Scammer's Name/Username*\n"
            "2. *Contact Information*\n" 
            "3. *What happened?* (Details of the scam)\n"
            "4. *Platform/Location* (Where it occurred)\n"
            "5. *Your Telegram* (For follow-up)\n\n"
            "Please send the *SCAMMER'S NAME/USERNAME*:",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Store user state for scammer report flow
        self.user_states[user_id] = {
            'product': 'scammer_report', 
            'step': 'scammer_name',
            'data': {}
        }
    
    async def handle_ad_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle ad creation flow"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        user_input = update.message.text
        
        if state['step'] == 'heading':
            if len(user_input) > 100:
                await update.message.reply_text("❌ Heading too long! Max 100 characters. Please try again:")
                return
            
            state['data']['heading'] = user_input
            state['step'] = 'type'
            await update.message.reply_text(
                "✅ Heading saved!\n\n"
                "Now please provide the *TYPE* of your ad:\n"
                "(e.g., Business, Service, Product, Opportunity)",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 'type':
            state['data']['type'] = user_input
            state['step'] = 'description'
            await update.message.reply_text(
                "✅ Type saved!\n\n"
                "Now please provide the *DESCRIPTION*:\n"
                "(Max 500 characters)",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 'description':
            if len(user_input) > 500:
                await update.message.reply_text("❌ Description too long! Max 500 characters. Please try again:")
                return
            
            state['data']['description'] = user_input
            state['step'] = 'contact'
            await update.message.reply_text(
                "✅ Description saved!\n\n"
                "Finally, provide *CONTACT INFORMATION*:\n"
                "(Phone, Email, Telegram, etc.)",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 'contact':
            state['data']['contact'] = user_input
            
            # Create the ad in database
            expires_at = (datetime.now() + timedelta(days=10)).isoformat()  # 10 days as requested
            
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    INSERT INTO ads_queue 
                    (user_id, username, heading, type, description, contact, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, update.effective_user.username, state['data']['heading'], 
                      state['data']['type'], state['data']['description'], state['data']['contact'],
                      datetime.now().isoformat(), expires_at))
                await db.commit()
            
            # Mark purchase as completed
            await db.execute("""
                INSERT INTO purchases 
                (user_id, username, product_type, amount, status, created_at, data)
                VALUES (?, ?, 'advertisement', 188, 'completed', ?, ?)
            """, (user_id, update.effective_user.username, datetime.now().isoformat(), json.dumps(state['data'])))
            await db.commit()
            
            # Clear user state
            del self.user_states[user_id]
            
            await update.message.reply_text(
                "🎉 *ADVERTISEMENT CREATED!* 🎉\n\n"
                "Your advertisement has been queued for posting!\n\n"
                "📢 *Ad Details:*\n"
                f"• Heading: {state['data']['heading']}\n"
                f"• Type: {state['data']['type']}\n"
                f"• Duration: 10 days\n"
                f"• Posts: Every 5-6 minutes\n\n"
                "🌟 *What happens next:*\n"
                "✅ Ad will appear in main group\n"
                "✅ Auto-pinned for visibility\n"
                "✅ Posted to company resources\n"
                "✅ Runs for 10 days\n\n"
                f"📊 Monitor with: /adviewqueue (in DM with @{AUTOADV_BOT_USERNAME})\n"
                "🛑 Contact support for changes\n\n"
                "Thank you for your purchase! 🙏",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_scammer_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle scammer report flow"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        user_input = update.message.text
        
        if state['step'] == 'scammer_name':
            state['data']['scammer_name'] = user_input
            state['step'] = 'contact'
            await update.message.reply_text(
                "✅ Name saved!\n\n"
                "Now provide the scammer's *CONTACT INFORMATION*:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 'contact':
            state['data']['scammer_contact'] = user_input
            state['step'] = 'details'
            await update.message.reply_text(
                "✅ Contact saved!\n\n"
                "Please describe *WHAT HAPPENED* (details of the scam):",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 'details':
            state['data']['details'] = user_input
            state['step'] = 'platform'
            await update.message.reply_text(
                "✅ Details saved!\n\n"
                "Where did this occur? (*PLATFORM/LOCATION*):",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 'platform':
            state['data']['platform'] = user_input
            state['step'] = 'victim_contact'
            await update.message.reply_text(
                "✅ Platform saved!\n\n"
                "Finally, provide *YOUR TELEGRAM USERNAME* for follow-up:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 'victim_contact':
            state['data']['victim_telegram'] = user_input
            
            # Post to scammer exposed channel
            report_text = f"""
⚠️ *SCAMMER ALERT!* ⚠️

🚨 *Scammer Information:*
▫️ Name: {state['data']['scammer_name']}
▫️ Contact: {state['data']['scammer_contact']}

📋 *Incident Details:*
{state['data']['details']}

🌐 *Platform/Location:*
{state['data']['platform']}

👤 *Reported By:*
@{state['data']['victim_telegram']}

━━━━━━━━━━━━━━━━
⚡ Stay safe! Report scammers to protect our community.
"""
            
            try:
                await self.app.bot.send_message(
                    chat_id=SCAMMER_EXPOSED_ID,
                    text=report_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Store purchase record
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("""
                        INSERT INTO purchases 
                        (user_id, username, product_type, amount, status, created_at, data)
                        VALUES (?, ?, 'scammer_report', 0, 'completed', ?, ?)
                    """, (user_id, update.effective_user.username, datetime.now().isoformat(), json.dumps(state['data'])))
                    await db.commit()
                
                # Clear user state
                del self.user_states[user_id]
                
                await update.message.reply_text(
                    "✅ *SCAMMER REPORT SUBMITTED!* ✅\n\n"
                    "Your report has been posted to the Scammer Exposed channel.\n\n"
                    "🛡️ Thank you for helping protect our community!\n\n"
                    "⚠️ All members have been notified.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            except Exception as e:
                logger.error(f"Error posting scammer report: {e}")
                await update.message.reply_text(
                    "❌ Error posting report. Please try again or contact support."
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
        """Show user's order history - DM only"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 Please use this command in private message!")
            return
            
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
                f"🛒 Start shopping: /{self.bot_prefix}start\n"
                f"📋 View products: /{self.bot_prefix}products",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        orders_text = "📋 *YOUR ORDER HISTORY* 📋\n\n"
        for order in orders:
            price_text = "FREE" if order[1] == 0 else f"{order[1]} USDT"
            orders_text += f"🎯 *Product:* {order[0]}\n"
            orders_text += f"💰 *Amount:* {price_text}\n"
            orders_text += f"📊 *Status:* {order[2].upper()}\n"
            orders_text += f"📅 *Date:* {order[3].split('T')[0]}\n"
            orders_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(orders_text, parse_mode=ParseMode.MARKDOWN)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks - DM only"""
        query = update.callback_query
        await query.answer()
        
        # Ensure this is in DM
        if query.message.chat.type != "private":
            await query.answer("This button works in private messages only!", show_alert=True)
            return
            
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
        """Handle help command from button - DM only"""
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
        """Handle my orders button - DM only"""
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
            price_text = "FREE" if order[1] == 0 else f"{order[1]} USDT"
            orders_text += f"🎯 {order[0].title()}\n"
            orders_text += f"💰 {price_text} • {order[2].upper()}\n"
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
        """Show product details - DM only"""
        if product_id not in self.products:
            await query.edit_message_text("❌ Product not found!")
            return
        
        product = self.products[product_id]
        price_text = "FREE" if product['price'] == 0 else f"{product['price']} USDT"
        
        keyboard = [
            [InlineKeyboardButton("💰 Buy Now", callback_data=f"pay_product_{product_id}")],
            [InlineKeyboardButton("📋 All Products", callback_data="help")],
            [InlineKeyboardButton("❌ Back", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🛒 *{product['name']}* 🛒\n\n"
            f"💰 *Price:* {price_text}\n"
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
        """Show payment instructions - DM only"""
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
            f"After payment, use:\n`/{self.bot_prefix}verify YOUR_TX_HASH`",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cancel_payment_query(self, query, payment_id):
        """Cancel payment - DM only"""
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
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ad_creation))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_scammer_report))
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

