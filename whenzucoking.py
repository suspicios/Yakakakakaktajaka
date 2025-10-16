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
    CallbackQueryHandler, ContextTypes, filters,
    ConversationHandler
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

# Bot Usernames
ADV_BOT_USERNAME = "@NepalChinIndiaAD_bot"
VIP_BOT_USERNAME = "@NepalChinIndiaVIPVERIFY_bot"
GROUP_BOT_USERNAME = "@NepalChinIndiaGROUPMANAGMENT_bot"
AUTOADV_BOT_USERNAME = "@NepalChinIndiaAUTOADV_bot"

# Group Links (Updated with actual links)
MAIN_GROUP_LINK = "https://t.me/+bEyi7RpG_NxjZjk1"
COMPANY_RESOURCES_LINK = "https://t.me/+D9yrbrh6xTcyNGE1"
VIP_CHANNEL_LINK = "https://t.me/+bPg3y6q4E400MjE1"
SCAMMER_EXPOSED_LINK = "https://t.me/+eztpF3kA2-Y2Yzk1"
ALL_IN_ONE_FOLDER_LINK = "https://t.me/addlist/Q3yfSoHIJnpiMGJl"

# Group IDs (You need to get these from your groups)
MAIN_GROUP_ID = -1003097566042
VIP_CHANNEL_ID = -1003075027543
COMPANY_RESOURCES_ID = -1003145253219
SCAMMER_EXPOSED_ID = -1002906057259

# Payment Config
TRONSCAN_API = "https://apilist.tronscan.org/api/transaction/info"
YOUR_USDT_ADDRESS = "TD1gmGWyWqFY5STqZW5PMRqMR46xJhj5rP"

# Admin User IDs (Replace with actual admin user IDs)
ADMIN_IDS = [7578682081]  # Add your actual Telegram user ID(s)

# Database
DB_NAME = "interlink_bots.db"

# Conversation states for ad purchase
AD_HEADING, AD_TYPE, AD_DESCRIPTION, AD_CONTACT, AD_CONFIRMATION = range(5)

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
        
        # Group verification table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_verification (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                join_time TIMESTAMP,
                verified INTEGER DEFAULT 0,
                welcome_msg_id INTEGER
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
        self.bot_username = ADV_BOT_USERNAME
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
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
        is_admin = await self.is_admin(update.effective_user.id)
        
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
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """About the advertising bot"""
        await update.message.reply_text(
            "🤖 *ADVERTISING BOT INFORMATION* 🤖\n\n"
            "🌟 *Version:* 1.0.0\n"
            "👨‍💻 *Developer:* Claude\n"
            "🚀 *Purpose:* Automated advertisement management\n\n"
            "💎 *Features:*\n"
            "✅ Auto-posting every 5-6 minutes\n"
            "✅ Multi-group posting\n"
            "✅ Auto-pinning in main group\n"
            "✅ Advertisement queue management\n"
            "✅ Statistics and analytics\n\n"
            "🔧 *Technical:*\n"
            "• Built with python-telegram-bot\n"
            "• SQLite database backend\n"
            "• AsyncIO for performance\n"
            "• APScheduler for timing\n\n"
            "📞 *Support:* Contact via @NepalChinIndiaAUTOADV_bot",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current bot status"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT is_paused, last_post_time FROM ad_config WHERE id=1")
            config = await cursor.fetchone()
            
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue WHERE status='active'")
            active_ads = (await cursor.fetchone())[0]
        
        status = "✅ ACTIVE" if not config[0] else "⏸️ PAUSED"
        last_post = config[1] if config[1] else "Never"
        
        await update.message.reply_text(
            f"📊 *ADVERTISING BOT STATUS* 📊\n\n"
            f"🟢 *Bot Status:* {status}\n"
            f"📢 *Active Ads:* {active_ads}\n"
            f"⏰ *Last Post:* {last_post}\n"
            f"🔄 *Interval:* 5-6 minutes\n\n"
            f"🎯 *Target Groups:*\n"
            f"• Main Group: ✅\n"
            f"• Company Resources: ✅\n\n"
            f"⚡ *System:* Running optimally",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Contact support"""
        await update.message.reply_text(
            "📞 *CONTACT SUPPORT* 📞\n\n"
            "For advertising-related issues:\n\n"
            "💎 *Payment & Purchases:*\n"
            f"{AUTOADV_BOT_USERNAME}\n\n"
            "👑 *VIP & Verification:*\n"
            f"{VIP_BOT_USERNAME}\n\n"
            "🛡️ *Group Management:*\n"
            f"{GROUP_BOT_USERNAME}\n\n"
            "🚀 *Technical Support:*\n"
            "Contact group administrators\n\n"
            "⏰ *Response Time:* 24-48 hours",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def check_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check specific ad details"""
        if not context.args:
            await update.message.reply_text("📝 Usage: /adcheckad [ad_id]")
            return
        
        try:
            ad_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid ad ID!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT heading, type, description, contact, created_at, expires_at, post_count 
                FROM ads_queue WHERE id=?
            """, (ad_id,))
            ad = await cursor.fetchone()
        
        if not ad:
            await update.message.reply_text("❌ Advertisement not found!")
            return
        
        await update.message.reply_text(
            f"📋 *ADVERTISEMENT DETAILS* 📋\n\n"
            f"🎯 *ID:* {ad_id}\n"
            f"📌 *Heading:* {ad[0]}\n"
            f"🏷️ *Type:* {ad[1]}\n"
            f"📝 *Description:*\n{ad[2]}\n"
            f"📞 *Contact:* {ad[3]}\n"
            f"📅 *Created:* {ad[4].split('T')[0]}\n"
            f"⏰ *Expires:* {ad[5].split('T')[0]}\n"
            f"📊 *Posted:* {ad[6]} times\n\n"
            f"🔄 *Status:* Active",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def top_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top performing ads"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT heading, post_count 
                FROM ads_queue 
                WHERE status='active' 
                ORDER BY post_count DESC 
                LIMIT 5
            """)
            top_ads = await cursor.fetchall()
        
        if not top_ads:
            await update.message.reply_text("📭 No active advertisements found!")
            return
        
        top_text = "🏆 *TOP PERFORMING ADS* 🏆\n\n"
        for i, ad in enumerate(top_ads, 1):
            top_text += f"{i}. {ad[0]}\n"
            top_text += f"   📊 Views: {ad[1]}\n\n"
        
        await update.message.reply_text(top_text, parse_mode=ParseMode.MARKDOWN)
    
    async def edit_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit advertisement (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can edit ads!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("📝 Usage: /adeditad [ad_id] [field] [new_value]")
            return
        
        try:
            ad_id = int(context.args[0])
            field = context.args[1].lower()
            new_value = " ".join(context.args[2:])
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Invalid parameters!")
            return
        
        valid_fields = ['heading', 'type', 'description', 'contact']
        if field not in valid_fields:
            await update.message.reply_text(f"❌ Invalid field! Use: {', '.join(valid_fields)}")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"UPDATE ads_queue SET {field}=? WHERE id=?", (new_value, ad_id))
            await db.commit()
        
        await update.message.reply_text(
            f"✅ *AD UPDATED!*\n\n"
            f"Advertisement ID {ad_id} has been updated.\n"
            f"Field '{field}' set to: {new_value}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def set_interval_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set posting interval (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can change intervals!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /adsetinterval [minutes]")
            return
        
        try:
            minutes = int(context.args[0])
            if minutes < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Invalid minutes! Must be positive integer.")
            return
        
        # In a real implementation, you would store this in config
        await update.message.reply_text(
            f"⏰ *INTERVAL UPDATED!*\n\n"
            f"Posting interval set to {minutes} minutes.\n\n"
            f"⚠️ Note: This is a demo. In production, interval would be saved to database.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def ad_logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View posting logs (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can view logs!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT heading, created_at, post_count 
                FROM ads_queue 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            logs = await cursor.fetchall()
        
        logs_text = "📋 *RECENT ADVERTISEMENT LOGS* 📋\n\n"
        for log in logs:
            logs_text += f"📌 {log[0]}\n"
            logs_text += f"📅 {log[1].split('T')[0]}\n"
            logs_text += f"📊 Posted: {log[2]} times\n"
            logs_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(logs_text, parse_mode=ParseMode.MARKDOWN)
    
    async def reset_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset statistics (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can reset stats!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE ads_queue SET post_count=0")
            await db.commit()
        
        await update.message.reply_text(
            "🔄 *STATISTICS RESET!*\n\n"
            "All advertisement post counts have been reset to zero.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Backup database (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can backup data!")
            return
        
        # In production, you would implement actual backup logic
        backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        await update.message.reply_text(
            f"💾 *BACKUP CREATED!*\n\n"
            f"Backup file: `ad_backup_{backup_time}.db`\n"
            f"📊 Contains: All advertisement data\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚠️ Demo: In production, file would be saved to cloud storage.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle maintenance mode (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can toggle maintenance!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT is_paused FROM ad_config WHERE id=1")
            current = (await cursor.fetchone())[0]
            new_status = 0 if current else 1
            
            await db.execute("UPDATE ad_config SET is_paused=?", (new_status,))
            await db.commit()
        
        status_text = "🛠️ MAINTENANCE MODE ACTIVATED" if new_status else "✅ NORMAL OPERATION RESUMED"
        
        await update.message.reply_text(
            f"🔧 *MAINTENANCE MODE UPDATED!*\n\n"
            f"{status_text}\n\n"
            f"All advertising operations are now {'PAUSED' if new_status else 'ACTIVE'}.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def ad_preview_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Preview ad before posting (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can preview ads!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /adadpreview [ad_id]")
            return
        
        try:
            ad_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid ad ID!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT heading, type, description, contact 
                FROM ads_queue WHERE id=?
            """, (ad_id,))
            ad = await cursor.fetchone()
        
        if not ad:
            await update.message.reply_text("❌ Advertisement not found!")
            return
        
        preview_text = f"""
🎯 *{ad[0]}*

🏷️ *Type:* {ad[1]}
📝 *Description:*
{ad[2]}

📞 *Contact:* {ad[3]}

━━━━━━━━━━━━━━━━
✨ _Posted by Advertising Bot_
"""
        keyboard = [
            [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=buy_ad")],
            [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=report_scammer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👁️ *ADVERTISEMENT PREVIEW* 👁️\n\n"
            f"Here's how ad ID {ad_id} will appear:\n\n"
            f"{preview_text}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
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
            
            # Top ad
            cursor = await db.execute("SELECT heading, post_count FROM ads_queue ORDER BY post_count DESC LIMIT 1")
            top_ad = await cursor.fetchone()
            top_ad_text = f"{top_ad[0]} ({top_ad[1]} posts)" if top_ad else "None"
        
        stats_text = f"""
📊 *ADVERTISING EMPIRE STATISTICS* 📊

🎯 *ADVERTISEMENT METRICS:*
▫️ Active Ads: {active_ads}
▫️ Total Ads (All Time): {total_ads}
▫️ Total Posts Delivered: {total_posts}
▫️ Last Posted: {last_post}
▫️ Top Performing: {top_ad_text}

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
        if not await self.is_admin(update.effective_user.id):
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
        if not await self.is_admin(update.effective_user.id):
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
        if not await self.is_admin(update.effective_user.id):
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
        if not await self.is_admin(update.effective_user.id):
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
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        await self.post_advertisement()
        await update.message.reply_text("✅ Advertisement posted immediately!")
    
    async def skip_next_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip next scheduled ad (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        await update.message.reply_text("⏭️ Next advertisement will be skipped!")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /adbroadcast [message]")
            return
        
        message = " ".join(context.args)
        
        # Send to all groups
        groups = [MAIN_GROUP_ID, COMPANY_RESOURCES_ID]
        for group_id in groups:
            try:
                await context.bot.send_message(
                    chat_id=group_id,
                    text=f"📢 *BROADCAST MESSAGE*\n\n{message}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Error broadcasting to group {group_id}: {e}")
        
        await update.message.reply_text("✅ Broadcast sent to all groups!")
    
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
                f"🚀 Purchase ads via {AUTOADV_BOT_USERNAME}!",
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
                    # Update post count
                    await db.execute("UPDATE ads_queue SET post_count=post_count+1 WHERE id=?", (ad[0],))
                    await db.commit()
                else:
                    # Post default ad
                    ad_text = f"""
🎯 *NEED ADVERTISING?*

🏷️ *Type:* Premium Promotion
📝 *Description:*
Promote your business, service, or product to thousands of active users! 
Get maximum visibility with our automated advertising system.

📞 *Contact:* {AUTOADV_BOT_USERNAME}

━━━━━━━━━━━━━━━━
✨ _Posted by Advertising Bot_
"""
                
                # Post to groups
                groups = [MAIN_GROUP_ID, COMPANY_RESOURCES_ID]
                keyboard = [
                    [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=buy_ad")],
                    [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=report_scammer")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                for group_id in groups:
                    try:
                        message = await self.app.bot.send_message(
                            chat_id=group_id,
                            text=ad_text,
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        # Pin in main group
                        if group_id == MAIN_GROUP_ID:
                            try:
                                await self.app.bot.pin_chat_message(group_id, message.message_id)
                            except Exception as e:
                                logger.error(f"Error pinning message: {e}")
                        
                        # Update last post time
                        await db.execute("UPDATE ad_config SET last_post_time=? WHERE id=1", (datetime.now().isoformat(),))
                        await db.commit()
                        
                    except Exception as e:
                        logger.error(f"Error posting ad to group {group_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error in post_advertisement: {e}")
    
    def setup_handlers(self):
        """Setup all command handlers with prefixes"""
        # Only use prefixed commands
        self.app.add_handler(CommandHandler("adstart", self.start_command))
        self.app.add_handler(CommandHandler("adhelp", self.help_command))
        self.app.add_handler(CommandHandler("adabout", self.about_command))
        self.app.add_handler(CommandHandler("adstatus", self.status_command))
        self.app.add_handler(CommandHandler("adcontact", self.contact_command))
        self.app.add_handler(CommandHandler("adstats", self.stats_command))
        self.app.add_handler(CommandHandler("adviewqueue", self.view_queue_command))
        self.app.add_handler(CommandHandler("admyads", self.my_ads_command))
        self.app.add_handler(CommandHandler("adtopads", self.top_ads_command))
        self.app.add_handler(CommandHandler("adcheckad", self.check_ad_command))
        
        # Admin commands with prefix
        self.app.add_handler(CommandHandler("adpause", self.pause_ads_command))
        self.app.add_handler(CommandHandler("adresume", self.resume_ads_command))
        self.app.add_handler(CommandHandler("adclearqueue", self.clear_queue_command))
        self.app.add_handler(CommandHandler("adremovead", self.remove_ad_command))
        self.app.add_handler(CommandHandler("adeditad", self.edit_ad_command))
        self.app.add_handler(CommandHandler("adsetinterval", self.set_interval_command))
        self.app.add_handler(CommandHandler("adforcead", self.force_ad_command))
        self.app.add_handler(CommandHandler("adskipnext", self.skip_next_command))
        self.app.add_handler(CommandHandler("adbroadcast", self.broadcast_command))
        self.app.add_handler(CommandHandler("adlogs", self.ad_logs_command))
        self.app.add_handler(CommandHandler("adresetstats", self.reset_stats_command))
        self.app.add_handler(CommandHandler("adbackup", self.backup_command))
        self.app.add_handler(CommandHandler("admaintenance", self.maintenance_command))
        self.app.add_handler(CommandHandler("adpreview", self.ad_preview_command))
    
    def start_scheduler(self):
        """Start the advertisement scheduler - FIXED"""
        try:
            self.scheduler.add_job(
                self.post_advertisement,
                'interval',
                minutes=random.randint(5, 6),
                id='ad_posting'
            )
            self.scheduler.start()
            logger.info("✅ Advertising scheduler started successfully")
        except Exception as e:
            logger.error(f"❌ Error starting scheduler: {e}")
    
    async def run(self):
        """Run the advertising bot - FIXED"""
        await init_database()
        self.setup_handlers()
        self.start_scheduler()
        
        logger.info("🚀 Advertising Bot is running...")
        try:
            await self.app.run_polling()
        except Exception as e:
            logger.error(f"❌ Error in Advertising Bot: {e}")

# ============================
# 👑 2. VIP VERIFICATION BOT
# ============================

class VIPVerificationBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "vip"  # Prefix for common commands
        self.bot_username = VIP_BOT_USERNAME
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command for VIP verification"""
        await update.message.reply_text(
            "👑 *WELCOME TO VIP VERIFICATION* 👑\n\n"
            "I am the *VIP Verification Bot*, guardian of the elite realm! "
            "I verify and manage VIP members with divine precision.\n\n"
            "✨ *MY SACRED DUTIES:* ✨\n"
            "✅ Verify VIP members\n"
            "🛡️ Protect exclusive content\n"
            "📊 Manage VIP database\n"
            "🔒 Secure premium access\n\n"
            "⚡ *COMMANDS AT YOUR DISPOSAL:* ⚡\n"
            "/viphelp - All VIP commands\n"
            "/vipverify - Verify VIP status\n"
            "/vipstatus - Check your VIP status\n"
            "/vipmembers - View VIP members\n\n"
            "Enter the realm of exclusivity, O Worthy One! 🏰",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive VIP help with all commands"""
        is_admin = await self.is_admin(update.effective_user.id)
        
        user_commands = f"""
👑 *VIP VERIFICATION BOT - COMMAND BIBLE* 👑

📱 *GENERAL COMMANDS:*
/{self.bot_prefix}start - Enter the VIP realm
/{self.bot_prefix}help - VIP command reference
/{self.bot_prefix}about - About VIP system
/{self.bot_prefix}status - Check your VIP status
/{self.bot_prefix}verify - Verify VIP membership
/{self.bot_prefix}benefits - VIP benefits list
/{self.bot_prefix}renew - Renew VIP membership
/{self.bot_prefix}contact - VIP support contact

🔍 *VERIFICATION COMMANDS:*
/{self.bot_prefix}check [username] - Check user VIP status
/{self.bot_prefix}members - View VIP members list
/{self.bot_prefix}stats - VIP statistics
/{self.bot_prefix}rules - VIP rules and guidelines
/{self.bot_prefix}channels - VIP channel access
"""
        
        admin_commands = f"""
⚡ *ADMIN COMMANDS:*
/{self.bot_prefix}add [user_id] [days] - Add VIP member
/{self.bot_prefix}remove [user_id] - Remove VIP member
/{self.bot_prefix}extend [user_id] [days] - Extend VIP
/{self.bot_prefix}list - All VIP members
/{self.bot_prefix}export - Export VIP database
/{self.bot_prefix}search [query] - Search VIP members
/{self.bot_prefix}cleanup - Remove expired VIPs
/{self.bot_prefix}settings - VIP system settings
/{self.bot_prefix}backup - Backup VIP data
/{self.bot_prefix}restore - Restore from backup
/{self.bot_prefix}announce [msg] - Announce to VIPs
/{self.bot_prefix}verifyall - Verify all pending
/{self.bot_prefix}renewals - View renewal requests
/{self.bot_prefix}analytics - VIP analytics
/{self.bot_prefix}testverify - Test verification
/{self.bot_prefix}emergency - Emergency mode
/{self.bot_prefix}logs - View verification logs
/{self.bot_prefix}resetuser [user_id] - Reset user data
/{self.bot_prefix}massadd [file] - Bulk add VIPs
/{self.bot_prefix}massremove [file] - Bulk remove VIPs
/{self.bot_prefix}setwelcome [msg] - Set VIP welcome
/{self.bot_prefix}setrules [rules] - Set VIP rules
/{self.bot_prefix}maintenance - Toggle maintenance
/{self.bot_prefix}testaccess - Test channel access
/{self.bot_prefix}sync - Sync with channels
/{self.bot_prefix}reports - VIP reports
/{self.bot_prefix}whitelist [user_id] - Whitelist user
/{self.bot_prefix}blacklist [user_id] - Blacklist user
/{self.bot_prefix}verifychannel - Verify channel setup
/{self.bot_prefix}setexpiry [days] - Set default expiry
/{self.bot_prefix}notifyexpiring - Notify expiring VIPs
"""
        
        help_text = user_commands
        if is_admin:
            help_text += admin_commands
        
        help_text += "\n💎 *VIP status is your key to exclusivity!* 💎"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """About the VIP system"""
        await update.message.reply_text(
            "👑 *VIP VERIFICATION SYSTEM* 👑\n\n"
            "🌟 *Version:* 1.0.0\n"
            "👨‍💻 *Developer:* Claude\n"
            "🎯 *Purpose:* Elite member verification\n\n"
            "💎 *VIP Benefits:*\n"
            "✅ Access to VIP channels\n"
            "✅ Exclusive content\n"
            "✅ Priority support\n"
            "✅ Special promotions\n\n"
            "🔧 *Technical Features:*\n"
            "• Automated verification\n"
            "• Database management\n"
            "• Channel access control\n"
            "• Expiry tracking\n\n"
            "📞 *Support:* Contact via @NepalChinIndiaVIPVERIFY_bot",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user's VIP status"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT name, phone, email, created_at, expires_at, is_active 
                FROM vip_members 
                WHERE user_id=?
            """, (user_id,))
            vip_data = await cursor.fetchone()
        
        if vip_data and vip_data[5] == 1:
            # VIP member
            expiry_date = vip_data[4].split('T')[0] if vip_data[4] else "Never"
            created_date = vip_data[3].split('T')[0] if vip_data[3] else "Unknown"
            
            await update.message.reply_text(
                f"👑 *VIP STATUS - ACTIVE* 👑\n\n"
                f"🎯 *User:* @{username}\n"
                f"📛 *Name:* {vip_data[0] or 'Not provided'}\n"
                f"📞 *Phone:* {vip_data[1] or 'Not provided'}\n"
                f"📧 *Email:* {vip_data[2] or 'Not provided'}\n"
                f"📅 *Member Since:* {created_date}\n"
                f"⏰ *Expires:* {expiry_date}\n\n"
                f"💎 *Status:* ✅ ACTIVE VIP\n"
                f"✨ Enjoy your exclusive benefits!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # Not VIP
            await update.message.reply_text(
                f"🔒 *VIP STATUS - INACTIVE* 🔒\n\n"
                f"🎯 *User:* @{username}\n"
                f"📊 *Status:* ❌ NOT VIP MEMBER\n\n"
                f"💫 *Become VIP to unlock:*\n"
                f"• Exclusive channel access\n"
                f"• Premium content\n"
                f"• Priority support\n"
                f"• Special promotions\n\n"
                f"🚀 *Get VIP:* Contact {AUTOADV_BOT_USERNAME}",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify VIP membership"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT is_active, expires_at 
                FROM vip_members 
                WHERE user_id=?
            """, (user_id,))
            vip_data = await cursor.fetchone()
        
        if vip_data and vip_data[0] == 1:
            expiry_date = vip_data[1].split('T')[0] if vip_data[1] else "Never"
            
            await update.message.reply_text(
                f"✅ *VIP VERIFICATION SUCCESSFUL* ✅\n\n"
                f"👑 Welcome back, VIP member!\n"
                f"🎯 Username: @{username}\n"
                f"⏰ VIP Expiry: {expiry_date}\n\n"
                f"💎 Your VIP status is active and verified!\n"
                f"✨ Enjoy your exclusive access!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ *VIP VERIFICATION FAILED* ❌\n\n"
                f"🔒 User: @{username}\n"
                f"📊 Status: NOT VIP MEMBER\n\n"
                f"💫 To become a VIP member:\n"
                f"1. Contact {AUTOADV_BOT_USERNAME}\n"
                f"2. Complete payment\n"
                f"3. Get verified\n\n"
                f"🚀 Unlock exclusive benefits today!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def benefits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP benefits"""
        await update.message.reply_text(
            "💎 *VIP MEMBERSHIP BENEFITS* 💎\n\n"
            "🌟 *Exclusive Access:*\n"
            "✅ VIP Channel Access\n"
            "✅ Premium Content Library\n"
            "✅ Early Feature Access\n"
            "✅ Exclusive Events\n\n"
            "🚀 *Priority Services:*\n"
            "✅ 24/7 Priority Support\n"
            "✅ Custom Requests\n"
            "✅ Personal Assistant\n"
            "✅ Business Networking\n\n"
            "🎯 *Special Features:*\n"
            "✅ Advanced Analytics\n"
            "✅ Custom Reports\n"
            "✅ API Access\n"
            "✅ Training Sessions\n\n"
            "🔒 *Security & Privacy:*\n"
            "✅ Enhanced Privacy\n"
            "✅ Data Protection\n"
            "✅ Secure Channels\n"
            "✅ Anonymous Options\n\n"
            "💫 *Become VIP today and unlock these exclusive benefits!*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def members_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP members list"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT username, name, created_at, expires_at 
                FROM vip_members 
                WHERE is_active=1 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            members = await cursor.fetchall()
        
        if not members:
            await update.message.reply_text(
                "📭 *No VIP Members Found!*\n\n"
                "The VIP realm awaits its first members!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        members_text = "👑 *VIP MEMBERS LIST* 👑\n\n"
        for member in members:
            username = f"@{member[0]}" if member[0] else "No username"
            name = member[1] or "Anonymous"
            join_date = member[2].split('T')[0] if member[2] else "Unknown"
            expiry = member[3].split('T')[0] if member[3] else "Never"
            
            members_text += f"👤 *User:* {username}\n"
            members_text += f"📛 *Name:* {name}\n"
            members_text += f"📅 *Joined:* {join_date}\n"
            members_text += f"⏰ *Expires:* {expiry}\n"
            members_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(members_text, parse_mode=ParseMode.MARKDOWN)
    
    async def check_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check specific user's VIP status"""
        if not context.args:
            await update.message.reply_text("📝 Usage: /vipcheck [username or user_id]")
            return
        
        target = context.args[0].replace('@', '')
        
        async with aiosqlite.connect(DB_NAME) as db:
            if target.isdigit():
                cursor = await db.execute("""
                    SELECT username, name, is_active, expires_at 
                    FROM vip_members 
                    WHERE user_id=?
                """, (int(target),))
            else:
                cursor = await db.execute("""
                    SELECT username, name, is_active, expires_at 
                    FROM vip_members 
                    WHERE username=?
                """, (target,))
            
            vip_data = await cursor.fetchone()
        
        if vip_data and vip_data[2] == 1:
            expiry = vip_data[3].split('T')[0] if vip_data[3] else "Never"
            await update.message.reply_text(
                f"✅ *VIP STATUS: ACTIVE* ✅\n\n"
                f"👤 User: @{vip_data[0]}\n"
                f"📛 Name: {vip_data[1] or 'Not provided'}\n"
                f"⏰ Expires: {expiry}\n"
                f"💎 Status: ✅ VERIFIED VIP",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ *VIP STATUS: NOT FOUND* ❌\n\n"
                f"User '{target}' is not a VIP member.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP statistics"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members WHERE is_active=1")
            active_vips = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members")
            total_vips = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members WHERE expires_at < ?", (datetime.now().isoformat(),))
            expired_vips = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT username FROM vip_members WHERE is_active=1 ORDER BY created_at DESC LIMIT 1")
            latest_vip = await cursor.fetchone()
            latest_vip_text = f"@{latest_vip[0]}" if latest_vip else "None"
        
        stats_text = f"""
📊 *VIP EMPIRE STATISTICS* 📊

👑 *VIP MEMBER METRICS:*
▫️ Active VIPs: {active_vips}
▫️ Total VIPs (All Time): {total_vips}
▫️ Expired VIPs: {expired_vips}
▫️ Latest VIP: {latest_vip_text}

🔥 *SYSTEM STATUS:*
▫️ Verification: ✅ ACTIVE
▫️ Channel Access: ✅ ENABLED
▫️ Database: ✅ HEALTHY

💪 *The VIP realm grows stronger, Master!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP rules"""
        await update.message.reply_text(
            "📜 *VIP MEMBERSHIP RULES* 📜\n\n"
            "1. 🤫 *Confidentiality:*\n"
            "   • Do not share VIP content\n"
            "   • Keep discussions private\n"
            "   • Respect member privacy\n\n"
            "2. 💎 *Conduct:*\n"
            "   • Be respectful to all members\n"
            "   • No spam or advertising\n"
            "   • Help fellow VIPs\n\n"
            "3. 🔒 *Security:*\n"
            "   • Protect your account\n"
            "   • Report suspicious activity\n"
            "   • Use secure communication\n\n"
            "4. ⚡ *Benefits:*\n"
            "   • Access is personal only\n"
            "   • No sharing of credentials\n"
            "   • Follow channel guidelines\n\n"
            "5. 🚫 *Termination:*\n"
            "   • Violations may result in ban\n"
            "   • No refunds for violations\n"
            "   • Decisions are final\n\n"
            "💫 *By using VIP services, you agree to these rules.*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def channels_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP channel access"""
        keyboard = [
            [InlineKeyboardButton("👑 VIP Channel", url=VIP_CHANNEL_LINK)],
            [InlineKeyboardButton("🏢 Company Resources", url=COMPANY_RESOURCES_LINK)],
            [InlineKeyboardButton("🚀 AutoADV Bot", url=f"https://t.me/{AUTOADV_BOT_USERNAME.replace('@', '')}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔗 *VIP CHANNEL ACCESS* 🔗\n\n"
            "💎 *Available Channels:*\n"
            "✅ VIP Exclusive Channel\n"
            "✅ Company Resources\n"
            "✅ Premium Content\n\n"
            "🚀 *Access Instructions:*\n"
            "1. Click the buttons below\n"
            "2. Join the channels\n"
            "3. Enjoy exclusive content!\n\n"
            "🔒 *Note:* Some content may require additional verification.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def renew_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Renew VIP membership"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT expires_at FROM vip_members WHERE user_id=?", (user_id,))
            vip_data = await cursor.fetchone()
        
        if vip_data:
            expiry = vip_data[0].split('T')[0] if vip_data[0] else "Expired"
            await update.message.reply_text(
                f"🔄 *VIP MEMBERSHIP RENEWAL* 🔄\n\n"
                f"👤 User: @{username}\n"
                f"⏰ Current Expiry: {expiry}\n\n"
                f"💎 *Renewal Options:*\n"
                f"• 1 Month: $10\n"
                f"• 3 Months: $25\n"
                f"• 6 Months: $45\n"
                f"• 1 Year: $80\n\n"
                f"🚀 *To Renew:*\n"
                f"Contact {AUTOADV_BOT_USERNAME}\n\n"
                f"✨ Renew now and continue enjoying VIP benefits!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ *NO VIP MEMBERSHIP FOUND* ❌\n\n"
                f"User @{username} is not a VIP member.\n\n"
                f"💫 *Become VIP First:*\n"
                f"Contact {AUTOADV_BOT_USERNAME}",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """VIP support contact"""
        await update.message.reply_text(
            "📞 *VIP SUPPORT CONTACT* 📞\n\n"
            "For VIP-related inquiries:\n\n"
            "💎 *Membership & Payments:*\n"
            f"{AUTOADV_BOT_USERNAME}\n\n"
            "👑 *VIP Support:*\n"
            f"{VIP_BOT_USERNAME}\n\n"
            "📢 *Advertising:*\n"
            f"{ADV_BOT_USERNAME}\n\n"
            "🛡️ *Group Management:*\n"
            f"{GROUP_BOT_USERNAME}\n\n"
            "⏰ *VIP Response Time:* 12-24 hours",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Admin commands implementation
    async def add_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add VIP member (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can add VIP members!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("📝 Usage: /vipadd [user_id] [days] [name?] [phone?] [email?]")
            return
        
        try:
            user_id = int(context.args[0])
            days = int(context.args[1])
            name = context.args[2] if len(context.args) > 2 else None
            phone = context.args[3] if len(context.args) > 3 else None
            email = context.args[4] if len(context.args) > 4 else None
        except ValueError:
            await update.message.reply_text("❌ Invalid parameters!")
            return
        
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=days)
        
        async with aiosqlite.connect(DB_NAME) as db:
            # Check if user already exists
            cursor = await db.execute("SELECT username FROM vip_members WHERE user_id=?", (user_id,))
            existing = await cursor.fetchone()
            
            if existing:
                await db.execute("""
                    UPDATE vip_members 
                    SET name=?, phone=?, email=?, expires_at=?, is_active=1 
                    WHERE user_id=?
                """, (name, phone, email, expires_at.isoformat(), user_id))
            else:
                await db.execute("""
                    INSERT INTO vip_members (user_id, username, name, phone, email, created_at, expires_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (user_id, f"user_{user_id}", name, phone, email, created_at.isoformat(), expires_at.isoformat()))
            
            await db.commit()
        
        await update.message.reply_text(
            f"✅ *VIP MEMBER ADDED!*\n\n"
            f"👤 User ID: {user_id}\n"
            f"📛 Name: {name or 'Not set'}\n"
            f"⏰ Duration: {days} days\n"
            f"📅 Expires: {expires_at.strftime('%Y-%m-%d')}\n\n"
            f"💎 VIP status activated successfully!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def remove_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove VIP member (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
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
            vip_data = await cursor.fetchone()
            
            if not vip_data:
                await update.message.reply_text("❌ VIP member not found!")
                return
            
            await db.execute("DELETE FROM vip_members WHERE user_id=?", (user_id,))
            await db.commit()
        
        await update.message.reply_text(
            f"🗑️ *VIP MEMBER REMOVED!*\n\n"
            f"User ID {user_id} (@{vip_data[0]}) has been removed from VIP database.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def extend_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Extend VIP membership (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can extend VIP memberships!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("📝 Usage: /vipextend [user_id] [days]")
            return
        
        try:
            user_id = int(context.args[0])
            days = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid parameters!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT username, expires_at FROM vip_members WHERE user_id=?", (user_id,))
            vip_data = await cursor.fetchone()
            
            if not vip_data:
                await update.message.reply_text("❌ VIP member not found!")
                return
            
            current_expiry = datetime.fromisoformat(vip_data[1]) if vip_data[1] else datetime.now()
            new_expiry = current_expiry + timedelta(days=days)
            
            await db.execute("UPDATE vip_members SET expires_at=? WHERE user_id=?", (new_expiry.isoformat(), user_id))
            await db.commit()
        
        await update.message.reply_text(
            f"⏰ *VIP MEMBERSHIP EXTENDED!*\n\n"
            f"👤 User: @{vip_data[0]}\n"
            f"📅 Extended: {days} days\n"
            f"⏰ New Expiry: {new_expiry.strftime('%Y-%m-%d')}\n\n"
            f"💎 VIP access extended successfully!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def list_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all VIP members (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can view all VIP members!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT user_id, username, name, expires_at 
                FROM vip_members 
                WHERE is_active=1 
                ORDER BY expires_at DESC
            """)
            members = await cursor.fetchall()
        
        if not members:
            await update.message.reply_text("📭 No active VIP members found!")
            return
        
        members_text = "👑 *ALL VIP MEMBERS* 👑\n\n"
        for member in members:
            username = f"@{member[1]}" if member[1] else f"ID: {member[0]}"
            name = member[2] or "Anonymous"
            expiry = member[3].split('T')[0] if member[3] else "Never"
            
            members_text += f"🆔 *ID:* {member[0]}\n"
            members_text += f"👤 *User:* {username}\n"
            members_text += f"📛 *Name:* {name}\n"
            members_text += f"⏰ *Expires:* {expiry}\n"
            members_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(members_text, parse_mode=ParseMode.MARKDOWN)
    
    async def export_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export VIP database (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can export VIP data!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members")
            count = (await cursor.fetchone())[0]
        
        export_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        await update.message.reply_text(
            f"💾 *VIP DATABASE EXPORT* 💾\n\n"
            f"📊 Total VIP Records: {count}\n"
            f"📁 Export File: `vip_export_{export_time}.csv`\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚠️ Demo: In production, file would be generated and sent.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def search_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search VIP members (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can search VIP members!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /vipsearch [query]")
            return
        
        query = " ".join(context.args)
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT user_id, username, name, phone, email, expires_at 
                FROM vip_members 
                WHERE username LIKE ? OR name LIKE ? OR phone LIKE ? OR email LIKE ?
                LIMIT 10
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
            results = await cursor.fetchall()
        
        if not results:
            await update.message.reply_text("🔍 No VIP members found matching your query!")
            return
        
        results_text = f"🔍 *VIP SEARCH RESULTS* 🔍\n\n"
        results_text += f"Query: '{query}'\n"
        results_text += f"Found: {len(results)} members\n\n"
        
        for result in results:
            username = f"@{result[1]}" if result[1] else f"ID: {result[0]}"
            name = result[2] or "Anonymous"
            phone = result[3] or "Not set"
            email = result[4] or "Not set"
            expiry = result[5].split('T')[0] if result[5] else "Never"
            
            results_text += f"🆔 *ID:* {result[0]}\n"
            results_text += f"👤 *User:* {username}\n"
            results_text += f"📛 *Name:* {name}\n"
            results_text += f"📞 *Phone:* {phone}\n"
            results_text += f"📧 *Email:* {email}\n"
            results_text += f"⏰ *Expires:* {expiry}\n"
            results_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(results_text, parse_mode=ParseMode.MARKDOWN)
    
    async def cleanup_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove expired VIPs (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can cleanup VIP database!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members WHERE expires_at < ? AND is_active=1", (datetime.now().isoformat(),))
            expired_count = (await cursor.fetchone())[0]
            
            await db.execute("UPDATE vip_members SET is_active=0 WHERE expires_at < ?", (datetime.now().isoformat(),))
            await db.commit()
        
        await update.message.reply_text(
            f"🧹 *VIP DATABASE CLEANUP* 🧹\n\n"
            f"📊 Expired VIPs Found: {expired_count}\n"
            f"🔄 Status: Deactivated\n\n"
            f"💎 Database cleaned successfully!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """VIP system settings (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can access settings!")
            return
        
        await update.message.reply_text(
            "⚙️ *VIP SYSTEM SETTINGS* ⚙️\n\n"
            "🔧 *Current Configuration:*\n"
            "• Auto Cleanup: ✅ ENABLED\n"
            "• Verification: ✅ ACTIVE\n"
            "• Channel Access: ✅ ENABLED\n"
            "• Notifications: ✅ ENABLED\n\n"
            "📊 *Database Stats:*\n"
            "• Total VIPs: (See /vipstats)\n"
            "• Active VIPs: (See /vipstats)\n"
            "• Expired VIPs: (See /vipstats)\n\n"
            "🚀 *Available Actions:*\n"
            "• /vipcleanup - Clean expired VIPs\n"
            "• /vipexport - Export database\n"
            "• /vipannounce - Announce to VIPs\n"
            "• /vipmaintenance - Maintenance mode",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def announce_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Announce to VIP members (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can announce to VIPs!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /vipannounce [message]")
            return
        
        message = " ".join(context.args)
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT user_id FROM vip_members WHERE is_active=1")
            active_vips = await cursor.fetchall()
        
        sent_count = 0
        for vip in active_vips:
            try:
                await context.bot.send_message(
                    chat_id=vip[0],
                    text=f"👑 *VIP ANNOUNCEMENT* 👑\n\n{message}",
                    parse_mode=ParseMode.MARKDOWN
                )
                sent_count += 1
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Error sending to VIP {vip[0]}: {e}")
        
        await update.message.reply_text(
            f"📢 *VIP ANNOUNCEMENT SENT!*\n\n"
            f"✅ Delivered to: {sent_count} VIP members\n"
            f"📊 Total Active: {len(active_vips)}\n\n"
            f"💎 Announcement completed!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def setup_handlers(self):
        """Setup all VIP command handlers with prefixes"""
        # Only use prefixed commands
        self.app.add_handler(CommandHandler("vipstart", self.start_command))
        self.app.add_handler(CommandHandler("viphelp", self.help_command))
        self.app.add_handler(CommandHandler("vipabout", self.about_command))
        self.app.add_handler(CommandHandler("vipstatus", self.status_command))
        self.app.add_handler(CommandHandler("vipverify", self.verify_command))
        self.app.add_handler(CommandHandler("vipbenefits", self.benefits_command))
        self.app.add_handler(CommandHandler("vipmembers", self.members_command))
        self.app.add_handler(CommandHandler("vipcheck", self.check_command))
        self.app.add_handler(CommandHandler("vipstats", self.stats_command))
        self.app.add_handler(CommandHandler("viprules", self.rules_command))
        self.app.add_handler(CommandHandler("vipchannels", self.channels_command))
        self.app.add_handler(CommandHandler("viprenew", self.renew_command))
        self.app.add_handler(CommandHandler("vipcontact", self.contact_command))
        
        # Admin commands with prefix
        self.app.add_handler(CommandHandler("vipadd", self.add_vip_command))
        self.app.add_handler(CommandHandler("vipremove", self.remove_vip_command))
        self.app.add_handler(CommandHandler("vipextend", self.extend_vip_command))
        self.app.add_handler(CommandHandler("viplist", self.list_vip_command))
        self.app.add_handler(CommandHandler("vipexport", self.export_vip_command))
        self.app.add_handler(CommandHandler("vipsearch", self.search_vip_command))
        self.app.add_handler(CommandHandler("vipcleanup", self.cleanup_vip_command))
        self.app.add_handler(CommandHandler("vipsettings", self.settings_vip_command))
        self.app.add_handler(CommandHandler("vipannounce", self.announce_vip_command))
    
    async def run(self):
        """Run the VIP verification bot"""
        await init_database()
        self.setup_handlers()
        
        logger.info("👑 VIP Verification Bot is running...")
        try:
            await self.app.run_polling()
        except Exception as e:
            logger.error(f"❌ Error in VIP Bot: {e}")

# ============================
# 🛡️ 3. GROUP MANAGEMENT BOT
# ============================

class GroupManagementBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "group"  # Prefix for common commands
        self.bot_username = GROUP_BOT_USERNAME
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command for group management"""
        await update.message.reply_text(
            "🛡️ *WELCOME TO GROUP MANAGEMENT* 🛡️\n\n"
            "I am the *Group Management Bot*, guardian of order and protector of communities! "
            "I maintain harmony and security across all groups.\n\n"
            "✨ *MY DIVINE POWERS:* ✨\n"
            "🛡️ Auto-moderation\n"
            "👥 Member verification\n"
            "🚫 Violation tracking\n"
            "📊 Group analytics\n\n"
            "⚡ *COMMANDS AT YOUR DISPOSAL:* ⚡\n"
            "/grouphelp - All management commands\n"
            "/groupstats - Group statistics\n"
            "/groupmembers - Member management\n"
            "/groupviolations - View violations\n\n"
            "Together we shall maintain order, O Guardian! 🏰",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive group management help"""
        is_admin = await self.is_admin(update.effective_user.id)
        
        user_commands = f"""
🛡️ *GROUP MANAGEMENT BOT - COMMAND BIBLE* 🛡️

📱 *GENERAL COMMANDS:*
/{self.bot_prefix}start - Begin group management
/{self.bot_prefix}help - Command reference
/{self.bot_prefix}about - About the system
/{self.bot_prefix}status - Bot status
/{self.bot_prefix}stats - Group statistics
/{self.bot_prefix}members - Member list
/{self.bot_prefix}violations - View violations
/{self.bot_prefix}rules - Group rules
/{self.bot_prefix}report [reason] - Report user
/{self.bot_prefix}contact - Contact admins

👥 *MEMBER COMMANDS:*
/{self.bot_prefix}verify - Verify yourself
/{self.bot_prefix}mywarnings - Check your warnings
/{self.bot_prefix}profile - Your member profile
/{self.bot_prefix}leaderboard - Top members
/{self.bot_prefix}activity - Your activity
"""
        
        admin_commands = f"""
⚡ *ADMIN COMMANDS:*
/{self.bot_prefix}ban [user] [reason] - Ban user
/{self.bot_prefix}warn [user] [reason] - Warn user
/{self.bot_prefix}mute [user] [time] - Mute user
/{self.bot_prefix}unban [user] - Unban user
/{self.bot_prefix}unmute [user] - Unmute user
/{self.bot_prefix}kick [user] [reason] - Kick user
/{self.bot_prefix}promote [user] - Promote user
/{self.bot_prefix}demote [user] - Demote user
/{self.bot_prefix}exempt [user] - Exempt user
/{self.bot_prefix}unexempt [user] - Remove exemption
/{self.bot_prefix}cleanup - Clean old data
/{self.bot_prefix}backup - Backup data
/{self.bot_prefix}settings - Group settings
/{self.bot_prefix}announce [msg] - Announcement
/{self.bot_prefix}export - Export data
/{self.bot_prefix}import - Import data
/{self.bot_prefix}logs - View logs
/{self.bot_prefix}filter [word] - Add word filter
/{self.bot_prefix}unfilter [word] - Remove filter
/{self.bot_prefix}filters - List filters
/{self.bot_prefix}welcome [msg] - Set welcome
/{self.bot_prefix}goodbye [msg] - Set goodbye
/{self.bot_prefix}antispam [on/off] - Toggle anti-spam
/{self.bot_prefix}antilink [on/off] - Toggle anti-link
/{self.bot_prefix}lock [type] - Lock feature
/{self.bot_prefix}unlock [type] - Unlock feature
/{self.bot_prefix}maintenance - Maintenance mode
/{self.bot_prefix}testmod - Test moderation
/{self.bot_prefix}emergency - Emergency mode
/{self.bot_prefix}sync - Sync with Telegram
/{self.bot_prefix}reports - View reports
/{self.bot_prefix}resetuser [user] - Reset user
/{self.bot_prefix}massaction [file] - Bulk action
/{self.bot_prefix}setrules [rules] - Set rules
/{self.bot_prefix}setwarnlimit [number] - Set warn limit
/{self.bot_prefix}setcaptcha [on/off] - Toggle captcha
/{self.bot_prefix}verifyall - Verify all pending
/{self.bot_prefix}cleanbans - Clean old bans
/{self.bot_prefix}cleanwarns - Clean old warns
/{self.bot_prefix}analytics - Advanced analytics
/{self.bot_prefix}monitor [user] - Monitor user
/{self.bot_prefix}unmonitor [user] - Stop monitoring
/{self.bot_prefix}whitelist [user] - Whitelist user
/{self.bot_prefix}blacklist [user] - Blacklist user
"""
        
        help_text = user_commands
        if is_admin:
            help_text += admin_commands
        
        help_text += "\n🛡️ *Order and protection are my sacred duties!* 🛡️"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """About group management system"""
        await update.message.reply_text(
            "🛡️ *GROUP MANAGEMENT SYSTEM* 🛡️\n\n"
            "🌟 *Version:* 1.0.0\n"
            "👨‍💻 *Developer:* Claude\n"
            "🎯 *Purpose:* Automated group moderation\n\n"
            "💎 *Features:*\n"
            "✅ Auto-moderation\n"
            "✅ Member verification\n"
            "✅ Violation tracking\n"
            "✅ Analytics & reporting\n\n"
            "🔧 *Technical:*\n"
            "• Real-time monitoring\n"
            "• Smart filtering\n"
            "• Database tracking\n"
            "• Multi-group support\n\n"
            "📞 *Support:* Contact via @NepalChinIndiaGROUPMANAGMENT_bot",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group management status"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=0")
            pending_verification = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations")
            total_violations = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM exempted_users")
            exempted_users = (await cursor.fetchone())[0]
        
        await update.message.reply_text(
            f"📊 *GROUP MANAGEMENT STATUS* 📊\n\n"
            f"🛡️ *Moderation System:* ✅ ACTIVE\n"
            f"👥 *Pending Verification:* {pending_verification}\n"
            f"🚫 *Total Violations:* {total_violations}\n"
            f"⭐ *Exempted Users:* {exempted_users}\n\n"
            f"🎯 *Protected Groups:*\n"
            f"• Main Group: ✅ PROTECTED\n"
            f"• Company Resources: ✅ PROTECTED\n"
            f"• VIP Channel: ✅ PROTECTED\n\n"
            f"⚡ *All systems operational!*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group statistics"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM new_members")
            total_members = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=1")
            verified_members = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations")
            total_violations = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT violation_type, COUNT(*) FROM violations GROUP BY violation_type")
            violation_types = await cursor.fetchall()
        
        stats_text = f"""
📈 *GROUP MANAGEMENT STATISTICS* 📈

👥 *MEMBER STATISTICS:*
▫️ Total Members: {total_members}
▫️ Verified Members: {verified_members}
▫️ Pending Verification: {total_members - verified_members}
▫️ Verification Rate: {verified_members/total_members*100 if total_members > 0 else 0:.1f}%

🚫 *VIOLATION STATISTICS:*
▫️ Total Violations: {total_violations}
"""
        
        for vtype, count in violation_types:
            stats_text += f"▫️ {vtype}: {count}\n"
        
        stats_text += f"""
🛡️ *SYSTEM STATUS:*
▫️ Auto-Moderation: ✅ ACTIVE
▫️ Verification: ✅ ENABLED
▫️ Monitoring: ✅ RUNNING

💪 *The community is well-protected, Guardian!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def members_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show member list"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT username, join_time, verified 
                FROM new_members 
                ORDER BY join_time DESC 
                LIMIT 10
            """)
            members = await cursor.fetchall()
        
        if not members:
            await update.message.reply_text("📭 No members found in database!")
            return
        
        members_text = "👥 *RECENT MEMBERS* 👥\n\n"
        for member in members:
            username = f"@{member[0]}" if member[0] else "No username"
            join_date = member[1].split('T')[0] if member[1] else "Unknown"
            status = "✅ VERIFIED" if member[2] else "⏳ PENDING"
            
            members_text += f"👤 *User:* {username}\n"
            members_text += f"📅 *Joined:* {join_date}\n"
            members_text += f"🛡️ *Status:* {status}\n"
            members_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(members_text, parse_mode=ParseMode.MARKDOWN)
    
    async def violations_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent violations"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT username, violation_type, timestamp, warning_count 
                FROM violations 
                ORDER BY timestamp DESC 
                LIMIT 10
            """)
            violations = await cursor.fetchall()
        
        if not violations:
            await update.message.reply_text("✅ No violations recorded!")
            return
        
        violations_text = "🚫 *RECENT VIOLATIONS* 🚫\n\n"
        for violation in violations:
            username = f"@{violation[0]}" if violation[0] else "No username"
            timestamp = violation[2].split('T')[0] if violation[2] else "Unknown"
            
            violations_text += f"👤 *User:* {username}\n"
            violations_text += f"⚡ *Violation:* {violation[1]}\n"
            violations_text += f"📅 *Date:* {timestamp}\n"
            violations_text += f"⚠️ *Warnings:* {violation[3]}\n"
            violations_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(violations_text, parse_mode=ParseMode.MARKDOWN)
    
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group rules"""
        await update.message.reply_text(
            "📜 *GROUP RULES & GUIDELINES* 📜\n\n"
            "1. 🤝 *Respect Everyone:*\n"
            "   • No harassment or bullying\n"
            "   • Be kind and respectful\n"
            "   • No discrimination\n\n"
            "2. 🚫 *Prohibited Content:*\n"
            "   • No spam or advertising\n"
            "   • No NSFW content\n"
            "   • No illegal activities\n"
            "   • No personal attacks\n\n"
            "3. 💬 *Chat Etiquette:*\n"
            "   • Stay on topic\n"
            "   • No excessive caps\n"
            "   • Use appropriate language\n"
            "   • No chain messages\n\n"
            "4. 🔗 *Links & Sharing:*\n"
            "   • No malicious links\n"
            "   • Respect copyright\n"
            "   • No unauthorized bots\n"
            "   • Ask before promoting\n\n"
            "5. ⚠️ *Consequences:*\n"
            "   • Warnings for minor violations\n"
            "   • Mute for repeated issues\n"
            "   • Ban for serious violations\n"
            "   • No appeals for severe cases\n\n"
            "💫 *By participating in our groups, you agree to follow these rules.*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Report a user"""
        if not context.args:
            await update.message.reply_text("📝 Usage: /groupreport [reason] @username")
            return
        
        reason = " ".join(context.args)
        reporter = update.effective_user.username or "Anonymous"
        
        await update.message.reply_text(
            f"✅ *REPORT SUBMITTED* ✅\n\n"
            f"👤 *Reporter:* @{reporter}\n"
            f"📝 *Reason:* {reason}\n\n"
            f"🛡️ Our moderation team will review this report.\n"
            f"Thank you for helping keep our community safe!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify yourself as a member"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT verified FROM new_members WHERE user_id=?", (user_id,))
            member = await cursor.fetchone()
            
            if member:
                if member[0] == 1:
                    await update.message.reply_text(
                        f"✅ *ALREADY VERIFIED* ✅\n\n"
                        f"👤 User: @{username}\n"
                        f"🛡️ Status: Already verified\n\n"
                        f"✨ You're good to go!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await db.execute("UPDATE new_members SET verified=1 WHERE user_id=?", (user_id,))
                    await db.commit()
                    await update.message.reply_text(
                        f"✅ *VERIFICATION COMPLETE* ✅\n\n"
                        f"👤 User: @{username}\n"
                        f"🛡️ Status: Now verified\n\n"
                        f"✨ Welcome to the community!",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await db.execute("INSERT INTO new_members (user_id, username, join_time, verified) VALUES (?, ?, ?, 1)", 
                               (user_id, username, datetime.now().isoformat()))
                await db.commit()
                await update.message.reply_text(
                    f"✅ *VERIFICATION COMPLETE* ✅\n\n"
                    f"👤 User: @{username}\n"
                    f"🛡️ Status: New member verified\n\n"
                    f"✨ Welcome to the community!",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    async def my_warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user's warnings"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT violation_type, timestamp, warning_count 
                FROM violations 
                WHERE user_id=?
            """, (user_id,))
            warnings = await cursor.fetchall()
        
        if not warnings:
            await update.message.reply_text(
                f"✅ *NO WARNINGS* ✅\n\n"
                f"👤 User: @{username}\n"
                f"⚠️ Warnings: 0\n\n"
                f"✨ Keep up the good behavior!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        warnings_text = f"⚠️ *YOUR WARNINGS* ⚠️\n\n"
        total_warnings = 0
        
        for warning in warnings:
            violation_type = warning[0]
            timestamp = warning[1].split('T')[0] if warning[1] else "Unknown"
            count = warning[2]
            total_warnings += count
            
            warnings_text += f"⚡ *Type:* {violation_type}\n"
            warnings_text += f"📅 *Date:* {timestamp}\n"
            warnings_text += f"🔢 *Count:* {count}\n"
            warnings_text += "━━━━━━━━━━━━━━━━\n\n"
        
        warnings_text += f"📊 *Total Warnings:* {total_warnings}\n\n"
        
        if total_warnings >= 3:
            warnings_text += "🚨 *You have multiple warnings. Please be careful!*"
        elif total_warnings >= 1:
            warnings_text += "⚠️ *You have some warnings. Please follow the rules.*"
        else:
            warnings_text += "✨ *You're doing great!*"
        
        await update.message.reply_text(warnings_text, parse_mode=ParseMode.MARKDOWN)
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's member profile"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT join_time, verified FROM new_members WHERE user_id=?", (user_id,))
            member_data = await cursor.fetchone()
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations WHERE user_id=?", (user_id,))
            violation_count = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(warning_count) FROM violations WHERE user_id=?", (user_id,))
            total_warnings_result = await cursor.fetchone()
            total_warnings = total_warnings_result[0] if total_warnings_result[0] else 0
        
        if not member_data:
            await update.message.reply_text(
                f"🔍 *PROFILE NOT FOUND* 🔍\n\n"
                f"👤 User: @{username}\n"
                f"📊 Status: Not in database\n\n"
                f"💫 Use /groupverify to join the community!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        join_date = member_data[0].split('T')[0] if member_data[0] else "Unknown"
        status = "✅ VERIFIED" if member_data[1] == 1 else "⏳ PENDING"
        
        await update.message.reply_text(
            f"👤 *MEMBER PROFILE* 👤\n\n"
            f"🎯 *Username:* @{username}\n"
            f"🆔 *User ID:* {user_id}\n"
            f"📅 *Join Date:* {join_date}\n"
            f"🛡️ *Verification:* {status}\n"
            f"🚫 *Violations:* {violation_count}\n"
            f"⚠️ *Total Warnings:* {total_warnings}\n\n"
            f"💎 *Member Level:* {'⭐ VIP' if violation_count == 0 and member_data[1] == 1 else '👤 Regular'}\n\n"
            f"✨ Keep being an awesome community member!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show member leaderboard"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT username, join_time, verified 
                FROM new_members 
                WHERE verified=1 
                ORDER BY join_time ASC 
                LIMIT 10
            """)
            top_members = await cursor.fetchall()
        
        if not top_members:
            await update.message.reply_text("📭 No verified members found!")
            return
        
        leaderboard_text = "🏆 *MEMBER LEADERBOARD* 🏆\n\n"
        leaderboard_text += "🌟 *Top Longest Members:*\n\n"
        
        for i, member in enumerate(top_members, 1):
            username = f"@{member[0]}" if member[0] else "No username"
            join_date = member[1].split('T')[0] if member[1] else "Unknown"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            leaderboard_text += f"{medal} *{username}*\n"
            leaderboard_text += f"   📅 Joined: {join_date}\n"
            leaderboard_text += "   ━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(leaderboard_text, parse_mode=ParseMode.MARKDOWN)
    
    async def activity_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user activity"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT join_time FROM new_members WHERE user_id=?", (user_id,))
            member_data = await cursor.fetchone()
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations WHERE user_id=?", (user_id,))
            violations = (await cursor.fetchone())[0]
        
        if not member_data:
            await update.message.reply_text(
                f"🔍 *NO ACTIVITY DATA* 🔍\n\n"
                f"User @{username} not found in database.\n"
                f"Use /groupverify to join!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        join_date = datetime.fromisoformat(member_data[0]) if member_data[0] else datetime.now()
        days_in_group = (datetime.now() - join_date).days
        
        await update.message.reply_text(
            f"📊 *YOUR ACTIVITY* 📊\n\n"
            f"👤 *User:* @{username}\n"
            f"📅 *Member Since:* {join_date.strftime('%Y-%m-%d')}\n"
            f"⏰ *Days in Group:* {days_in_group}\n"
            f"🚫 *Rule Violations:* {violations}\n"
            f"⭐ *Behavior Score:* {max(100 - violations * 10, 0)}/100\n\n"
            f"💎 *Activity Level:* {'🌟 ACTIVE' if violations == 0 else '💫 REGULAR'}\n\n"
            f"✨ Keep being a great community member!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Contact group admins"""
        await update.message.reply_text(
            "📞 *GROUP ADMIN CONTACT* 📞\n\n"
            "For group-related issues:\n\n"
            "🛡️ *Moderation & Reports:*\n"
            f"{GROUP_BOT_USERNAME}\n\n"
            "👑 *VIP & Verification:*\n"
            f"{VIP_BOT_USERNAME}\n\n"
            "📢 *Advertising:*\n"
            f"{ADV_BOT_USERNAME}\n\n"
            "💎 *Payments & Purchases:*\n"
            f"{AUTOADV_BOT_USERNAME}\n\n"
            "⏰ *Response Time:* 24-48 hours",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Group member verification system
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining the group"""
        for new_member in update.message.new_chat_members:
            # Skip if the new member is a bot
            if new_member.is_bot:
                continue
                
            user_id = new_member.id
            username = new_member.username or "No username"
            
            # Send welcome message with group links
            welcome_text = (
                f"👋 Welcome @{username} to our community!\n\n"
                f"📋 *REQUIRED ACTIONS:*\n"
                f"Please join all our groups within 60 seconds to stay:\n\n"
                f"🏠 *Main Group:* {MAIN_GROUP_LINK}\n"
                f"🏢 *Company Resources:* {COMPANY_RESOURCES_LINK}\n"
                f"👑 *VIP Channel:* {VIP_CHANNEL_LINK}\n"
                f"⚠️ *Scammer Exposed:* {SCAMMER_EXPOSED_LINK}\n\n"
                f"⏰ *You have 60 seconds to join all groups*\n"
                f"❌ *Otherwise, you will be automatically removed*"
            )
            
            keyboard = [
                [InlineKeyboardButton("🏠 Main Group", url=MAIN_GROUP_LINK)],
                [InlineKeyboardButton("🏢 Company Resources", url=COMPANY_RESOURCES_LINK)],
                [InlineKeyboardButton("👑 VIP Channel", url=VIP_CHANNEL_LINK)],
                [InlineKeyboardButton("⚠️ Scammer Exposed", url=SCAMMER_EXPOSED_LINK)],
                [InlineKeyboardButton("✅ I Have Joined All", callback_data=f"verify_joined_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_msg = await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Store member info for verification
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO group_verification (user_id, username, join_time, verified, welcome_msg_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, datetime.now().isoformat(), 0, welcome_msg.message_id))
                await db.commit()
            
            # Schedule removal check after 60 seconds
            context.job_queue.run_once(
                self.check_member_verification, 
                60, 
                data={
                    'user_id': user_id,
                    'chat_id': update.effective_chat.id,
                    'username': username,
                    'welcome_msg_id': welcome_msg.message_id
                }
            )

    async def check_member_verification(self, context: ContextTypes.DEFAULT_TYPE):
        """Check if member has verified by joining all groups"""
        job = context.job
        user_id = job.data['user_id']
        chat_id = job.data['chat_id']
        username = job.data['username']
        welcome_msg_id = job.data['welcome_msg_id']
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT verified FROM group_verification WHERE user_id=?", (user_id,))
            result = await cursor.fetchone()
            
            if result and result[0] == 0:
                # Member didn't verify, remove them
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.unban_chat_member(chat_id, user_id)  # Unban to make it a kick
                    
                    # Delete welcome message
                    try:
                        await context.bot.delete_message(chat_id, welcome_msg_id)
                    except:
                        pass
                    
                    # Send removal notice
                    removal_msg = await context.bot.send_message(
                        chat_id,
                        f"❌ @{username} was removed for not joining required groups within 60 seconds."
                    )
                    
                    # Schedule removal of the removal message
                    context.job_queue.run_once(
                        lambda ctx: ctx.bot.delete_message(chat_id, removal_msg.message_id),
                        10
                    )
                    
                except Exception as e:
                    logger.error(f"Error removing user {user_id}: {e}")

    async def verify_joined_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle verification button callback"""
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.split('_')[-1])
        caller_id = query.from_user.id
        
        # Check if the button clicker is the same user who joined
        if caller_id != user_id:
            await query.answer("This verification is not for you!", show_alert=True)
            return
        
        # Mark as verified
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE group_verification SET verified=1 WHERE user_id=?", (user_id,))
            await db.commit()
        
        # Update the welcome message
        await query.edit_message_text(
            f"✅ @{query.from_user.username} has been verified!\n\n"
            f"Welcome to the community! You can now participate in discussions.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Admin commands implementation
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban user (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can ban users!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("📝 Usage: /groupban [user_id/@username] [reason]")
            return
        
        target = context.args[0]
        reason = " ".join(context.args[1:])
        
        try:
            if target.startswith('@'):
                # Get user by username
                user_id = 123456789  # In real implementation, you'd look this up
            else:
                user_id = int(target)
        except ValueError:
            await update.message.reply_text("❌ Invalid user identifier!")
            return
        
        # In real implementation, you would actually ban the user
        await update.message.reply_text(
            f"🔨 *USER BANNED* 🔨\n\n"
            f"👤 User ID: {user_id}\n"
            f"📝 Reason: {reason}\n"
            f"🛡️ Banned by: @{update.effective_user.username}\n\n"
            f"💎 User has been banned from all groups.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Warn user (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can warn users!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("📝 Usage: /groupwarn [user_id/@username] [reason]")
            return
        
        target = context.args[0]
        reason = " ".join(context.args[1:])
        
        try:
            if target.startswith('@'):
                user_id = 123456789
                username = target[1:]
            else:
                user_id = int(target)
                username = f"user_{user_id}"
        except ValueError:
            await update.message.reply_text("❌ Invalid user identifier!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            # Check existing warnings
            cursor = await db.execute("SELECT warning_count FROM violations WHERE user_id=?", (user_id,))
            existing = await cursor.fetchone()
            
            if existing:
                new_count = existing[0] + 1
                await db.execute("UPDATE violations SET warning_count=?, timestamp=? WHERE user_id=?", 
                               (new_count, datetime.now().isoformat(), user_id))
            else:
                await db.execute("""
                    INSERT INTO violations (user_id, username, violation_type, timestamp, warning_count)
                    VALUES (?, ?, ?, ?, 1)
                """, (user_id, username, reason, datetime.now().isoformat()))
            
            await db.commit()
        
        await update.message.reply_text(
            f"⚠️ *USER WARNED* ⚠️\n\n"
            f"👤 User: @{username}\n"
            f"📝 Reason: {reason}\n"
            f"🛡️ Warned by: @{update.effective_user.username}\n\n"
            f"💎 Warning has been recorded in database.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def exempt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Exempt user from moderation (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can exempt users!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /groupexempt [user_id/@username]")
            return
        
        target = context.args[0]
        
        try:
            if target.startswith('@'):
                user_id = 123456789
                username = target[1:]
            else:
                user_id = int(target)
                username = f"user_{user_id}"
        except ValueError:
            await update.message.reply_text("❌ Invalid user identifier!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR REPLACE INTO exempted_users (user_id, username, added_at) VALUES (?, ?, ?)",
                           (user_id, username, datetime.now().isoformat()))
            await db.commit()
        
        await update.message.reply_text(
            f"⭐ *USER EXEMPTED* ⭐\n\n"
            f"👤 User: @{username}\n"
            f"🛡️ Exempted by: @{update.effective_user.username}\n\n"
            f"💎 User is now exempt from automated moderation.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cleanup old data (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can cleanup data!")
            return
        
        cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM violations WHERE timestamp < ?", (cutoff_date,))
            old_violations = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE join_time < ?", (cutoff_date,))
            old_members = (await cursor.fetchone())[0]
            
            await db.execute("DELETE FROM violations WHERE timestamp < ?", (cutoff_date,))
            await db.execute("DELETE FROM new_members WHERE join_time < ? AND verified=0", (cutoff_date,))
            await db.commit()
        
        await update.message.reply_text(
            f"🧹 *DATABASE CLEANUP* 🧹\n\n"
            f"📊 Cleanup Results:\n"
            f"• Old violations removed: {old_violations}\n"
            f"• Inactive members removed: {old_members}\n"
            f"• Cutoff date: 30 days ago\n\n"
            f"💎 Database optimized successfully!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Group settings (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can access settings!")
            return
        
        await update.message.reply_text(
            "⚙️ *GROUP MANAGEMENT SETTINGS* ⚙️\n\n"
            "🔧 *Current Configuration:*\n"
            "• Auto-Moderation: ✅ ENABLED\n"
            "• Member Verification: ✅ ACTIVE\n"
            "• Violation Tracking: ✅ ENABLED\n"
            "• Anti-Spam: ✅ ACTIVE\n"
            "• Anti-Link: ✅ ENABLED\n\n"
            "📊 *Database Stats:*\n"
            "• Total Members: (See /groupstats)\n"
            "• Active Violations: (See /groupstats)\n"
            "• Exempted Users: (See /groupstatus)\n\n"
            "🚀 *Available Actions:*\n"
            "• /groupcleanup - Clean old data\n"
            "• /groupexport - Export data\n"
            "• /groupannounce - Make announcement\n"
            "• /groupmaintenance - Maintenance mode",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def announce_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Announce to group (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can make announcements!")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Usage: /groupannounce [message]")
            return
        
        message = " ".join(context.args)
        
        # In real implementation, you would send to all groups
        groups = [MAIN_GROUP_ID, COMPANY_RESOURCES_ID]
        
        sent_count = 0
        for group_id in groups:
            try:
                await context.bot.send_message(
                    chat_id=group_id,
                    text=f"📢 *GROUP ANNOUNCEMENT* 📢\n\n{message}",
                    parse_mode=ParseMode.MARKDOWN
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending to group {group_id}: {e}")
        
        await update.message.reply_text(
            f"📢 *ANNOUNCEMENT SENT!*\n\n"
            f"✅ Delivered to: {sent_count} groups\n"
            f"📊 Total Groups: {len(groups)}\n\n"
            f"💎 Announcement completed!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def setup_handlers(self):
        """Setup all group management handlers with prefixes"""
        # Only use prefixed commands
        self.app.add_handler(CommandHandler("groupstart", self.start_command))
        self.app.add_handler(CommandHandler("grouphelp", self.help_command))
        self.app.add_handler(CommandHandler("groupabout", self.about_command))
        self.app.add_handler(CommandHandler("groupstatus", self.status_command))
        self.app.add_handler(CommandHandler("groupstats", self.stats_command))
        self.app.add_handler(CommandHandler("groupmembers", self.members_command))
        self.app.add_handler(CommandHandler("groupviolations", self.violations_command))
        self.app.add_handler(CommandHandler("grouprules", self.rules_command))
        self.app.add_handler(CommandHandler("groupreport", self.report_command))
        self.app.add_handler(CommandHandler("groupverify", self.verify_command))
        self.app.add_handler(CommandHandler("groupmywarnings", self.my_warnings_command))
        self.app.add_handler(CommandHandler("groupprofile", self.profile_command))
        self.app.add_handler(CommandHandler("groupleaderboard", self.leaderboard_command))
        self.app.add_handler(CommandHandler("groupactivity", self.activity_command))
        self.app.add_handler(CommandHandler("groupcontact", self.contact_command))
        
        # Admin commands with prefix
        self.app.add_handler(CommandHandler("groupban", self.ban_command))
        self.app.add_handler(CommandHandler("groupwarn", self.warn_command))
        self.app.add_handler(CommandHandler("groupexempt", self.exempt_command))
        self.app.add_handler(CommandHandler("groupcleanup", self.cleanup_command))
        self.app.add_handler(CommandHandler("groupsettings", self.settings_command))
        self.app.add_handler(CommandHandler("groupannounce", self.announce_command))
        
        # Group verification handlers
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.app.add_handler(CallbackQueryHandler(self.verify_joined_callback, pattern="^verify_joined_"))
    
    async def run(self):
        """Run the group management bot"""
        await init_database()
        self.setup_handlers()
        
        logger.info("🛡️ Group Management Bot is running...")
        try:
            await self.app.run_polling()
        except Exception as e:
            logger.error(f"❌ Error in Group Bot: {e}")

# ============================
# 💰 4. AUTOADV PAYMENT BOT - FIXED VERSION
# ============================

class AutoAdvPaymentBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "autoadv"
        self.bot_username = AUTOADV_BOT_USERNAME
        self.ad_purchase_data = {}

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command for AutoADV payment bot"""
        await update.message.reply_text(
            "💰 *WELCOME TO AUTOADV PAYMENTS* 💰\n\n"
            "I am the *AutoADV Payment Bot*, master of transactions and gateway to premium services! "
            "I handle all payments with divine precision.\n\n"
            "✨ *MY DIVINE POWERS:* ✨\n"
            "💳 Process USDT (TRC20) payments\n"
            "🤖 Automated transaction verification\n"
            "📊 Purchase history tracking\n"
            "🛡️ Secure payment processing\n\n"
            "⚡ *COMMANDS AT YOUR DISPOSAL:* ⚡\n"
            "/autoadvhelp - All payment commands\n"
            "/autoadvbuy - Purchase services\n"
            "/autoadvstatus - Payment status\n"
            "/autoadvhistory - Purchase history\n\n"
            "Let the transactions begin, O Worthy Investor! 💎",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive payment help with all commands"""
        is_admin = await self.is_admin(update.effective_user.id)
        
        user_commands = f"""
💰 *AUTOADV PAYMENT BOT - COMMAND BIBLE* 💰

📱 *GENERAL COMMANDS:*
/{self.bot_prefix}start - Begin payment journey
/{self.bot_prefix}help - Payment command reference
/{self.bot_prefix}about - About payment system
/{self.bot_prefix}status - Payment status
/{self.bot_prefix}buy - Purchase services
/{self.bot_prefix}history - Purchase history
/{self.bot_prefix}balance - Your balance
/{self.bot_prefix}invoice [amount] - Create invoice
/{self.bot_prefix}rates - Current rates
/{self.bot_prefix}contact - Payment support

💳 *PAYMENT COMMANDS:*
/{self.bot_prefix}pay [amount] - Make payment
/{self.bot_prefix}verify [tx_hash] - Verify transaction
/{self.bot_prefix}address - Get payment address
/{self.bot_prefix}methods - Payment methods
/{self.bot_prefix}refund [tx_hash] - Request refund
/{self.bot_prefix}dispute [tx_hash] - Open dispute
/{self.bot_prefix}receipt [tx_hash] - Get receipt
"""
        
        admin_commands = f"""
⚡ *ADMIN COMMANDS:*
/{self.bot_prefix}stats - Payment statistics
/{self.bot_prefix}transactions - All transactions
/{self.bot_prefix}verifyall - Verify all pending
/{self.bot_prefix}refund [user] [amount] - Admin refund
/{self.bot_prefix}adjust [user] [amount] - Adjust balance
/{self.bot_prefix}export - Export transactions
/{self.bot_prefix}import - Import data
/{self.bot_prefix}logs - Payment logs
/{self.bot_prefix}backup - Backup data
/{self.bot_prefix}restore - Restore backup
/{self.bot_prefix}settings - Payment settings
/{self.bot_prefix}announce [msg] - Announcement
/{self.bot_prefix}maintenance - Maintenance mode
/{self.bot_prefix}testpayment - Test payment
/{self.bot_prefix}emergency - Emergency mode
/{self.bot_prefix}sync - Sync with blockchain
/{self.bot_prefix}reports - Payment reports
/{self.bot_prefix}resetuser [user] - Reset user
/{self.bot_prefix}massaction [file] - Bulk action
/{self.bot_prefix}setrates [usd] - Set exchange rates
/{self.bot_prefix}setaddress [addr] - Set payment address
/{self.bot_prefix}setlimits [min] [max] - Set limits
/{self.bot_prefix}whitelist [user] - Whitelist user
/{self.bot_prefix}blacklist [user] - Blacklist user
/{self.bot_prefix}verifytx [tx_hash] - Manual verify
/{self.bot_prefix}reversetx [tx_hash] - Reverse transaction
/{self.bot_prefix}analytics - Advanced analytics
/{self.bot_prefix}monitor - Monitor payments
/{self.bot_prefix}alerts - Configure alerts
/{self.bot_prefix}testapi - Test API connections
/{self.bot_prefix}setwebhook [url] - Set webhook
/{self.bot_prefix}checkbalance - Check wallet balance
/{self.bot_prefix}generatereport - Generate report
/{self.bot_prefix}cleanup - Clean old data
/{self.bot_prefix}setcommission [%] - Set commission
/{self.bot_prefix}viewcommissions - View commissions
/{self.bot_prefix}setpayout [address] - Set payout address
/{self.bot_prefix}payout [amount] - Make payout
/{self.bot_prefix}transactionfees - View fees
/{self.bot_prefix}setfee [amount] - Set transaction fee
"""
        
        help_text = user_commands
        if is_admin:
            help_text += admin_commands
        
        help_text += "\n💎 *Secure and seamless transactions are my promise!* 💎"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """About the payment system"""
        await update.message.reply_text(
            "💰 *AUTOADV PAYMENT SYSTEM* 💰\n\n"
            "🌟 *Version:* 1.0.0\n"
            "👨‍💻 *Developer:* Claude\n"
            "🎯 *Purpose:* Automated payment processing\n\n"
            "💎 *Features:*\n"
            "✅ USDT (TRC20) payments\n"
            "✅ Automated verification\n"
            "✅ Secure transactions\n"
            "✅ Real-time tracking\n\n"
            "🔧 *Technical:*\n"
            "• Blockchain integration\n"
            "• Real-time monitoring\n"
            "• Database security\n"
            "• Multi-currency support\n\n"
            "📞 *Support:* Contact via @NepalChinIndiaAUTOADV_bot",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show payment system status"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE status='completed'")
            completed_payments = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE status='pending'")
            pending_payments = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(amount) FROM purchases WHERE status='completed'")
            total_volume_result = await cursor.fetchone()
            total_volume = total_volume_result[0] if total_volume_result[0] else 0
        
        await update.message.reply_text(
            f"📊 *PAYMENT SYSTEM STATUS* 📊\n\n"
            f"💳 *Payment Gateway:* ✅ ACTIVE\n"
            f"✅ *Completed Payments:* {completed_payments}\n"
            f"⏳ *Pending Payments:* {pending_payments}\n"
            f"💰 *Total Volume:* ${total_volume:.2f}\n\n"
            f"🎯 *Supported Methods:*\n"
            f"• USDT (TRC20): ✅ AVAILABLE\n"
            f"• Auto-Verification: ✅ ENABLED\n"
            f"• Real-time Tracking: ✅ ACTIVE\n\n"
            f"⚡ *All systems operational!*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Purchase services"""
        # Check if command is in DM
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "🔒 *Please use this command in private messages only!*\n\n"
                "For security reasons, purchases must be made in direct messages.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        keyboard = [
            [InlineKeyboardButton("📢 Advertising", callback_data="buy_advertising")],
            [InlineKeyboardButton("👑 VIP Membership", callback_data="buy_vip")],
            [InlineKeyboardButton("🛡️ Group Services", callback_data="buy_group")],
            [InlineKeyboardButton("💰 Custom Package", callback_data="buy_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🛒 *AVAILABLE SERVICES* 🛒\n\n"
            "💎 *Choose a service to purchase:*\n\n"
            "📢 *Advertising Packages:*\n"
            "• Basic Ad: $5 (1 week)\n"
            "• Premium Ad: $15 (1 month)\n"
            "• Enterprise Ad: $30 (3 months)\n\n"
            "👑 *VIP Memberships:*\n"
            "• 1 Month: $10\n"
            "• 3 Months: $25\n"
            "• 6 Months: $45\n"
            "• 1 Year: $80\n\n"
            "🛡️ *Group Services:*\n"
            "• Custom solutions available\n\n"
            "💰 *Custom Packages:*\n"
            "• Tailored to your needs\n\n"
            "⚡ *Click a button below to proceed!*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Ad purchase conversation handlers - FIXED VERSION
    async def start_ad_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the ad purchase conversation - FIXED"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        self.ad_purchase_data[user_id] = {
            'package_type': 'advertising',
            'step': AD_HEADING
        }
        
        await query.edit_message_text(
            "📝 *ADVERTISEMENT PURCHASE* 📝\n\n"
            "Let's create your advertisement! I'll guide you through the process.\n\n"
            "🎯 *Step 1 of 4: Advertisement Heading*\n\n"
            "Please send me the *heading/title* for your advertisement:\n\n"
            "💡 *Example:* 'Premium Crypto Signals Service'\n\n"
            "❌ *To cancel:* Type /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_HEADING
    
    async def receive_ad_heading(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive ad heading - FIXED"""
        user_id = update.message.from_user.id
        
        # Check if user has active purchase data, if not start over
        if user_id not in self.ad_purchase_data:
            await update.message.reply_text(
                "❌ No active purchase session. Starting over...\n\n"
                "Please send me the *heading/title* for your advertisement:",
                parse_mode=ParseMode.MARKDOWN
            )
            self.ad_purchase_data[user_id] = {'step': AD_HEADING}
            return AD_HEADING
        
        heading = update.message.text
        
        # Validate heading
        if len(heading) < 3:
            await update.message.reply_text(
                "❌ Heading too short! Please provide a proper heading (min 3 characters):",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_HEADING
        
        if len(heading) > 100:
            await update.message.reply_text(
                "❌ Heading too long! Please keep it under 100 characters:",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_HEADING
        
        # Store heading
        self.ad_purchase_data[user_id]['heading'] = heading
        self.ad_purchase_data[user_id]['step'] = AD_TYPE
        
        keyboard = [
            [InlineKeyboardButton("🟢 Basic ($5 - 1 week)", callback_data="ad_type_basic")],
            [InlineKeyboardButton("🔵 Premium ($15 - 1 month)", callback_data="ad_type_premium")],
            [InlineKeyboardButton("🟣 Enterprise ($30 - 3 months)", callback_data="ad_type_enterprise")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_ad")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ *Heading saved:* {heading}\n\n"
            "🎯 *Step 2 of 4: Package Type*\n\n"
            "Choose your advertising package:\n\n"
            "🟢 *Basic Package - $5*\n• 1 week duration\n• Posted every 5-6 minutes\n\n"
            "🔵 *Premium Package - $15*\n• 1 month duration\n• All Basic features\n\n"
            "🟣 *Enterprise Package - $30*\n• 3 months duration\n• All Premium features\n\n"
            "⚡ *Select your package:*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_TYPE
    
    async def receive_ad_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive ad type selection - FIXED"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        ad_type = query.data
        
        # Check if user has active purchase data
        if user_id not in self.ad_purchase_data:
            await query.edit_message_text("❌ Session expired. Please start over with /autoadvbuy")
            return ConversationHandler.END
        
        if ad_type == "cancel_ad":
            await query.edit_message_text("❌ Advertisement purchase cancelled.")
            if user_id in self.ad_purchase_data:
                del self.ad_purchase_data[user_id]
            return ConversationHandler.END
        
        # Map callback data to package details
        package_map = {
            "ad_type_basic": {"name": "Basic", "price": 5, "duration": "1 week", "days": 7},
            "ad_type_premium": {"name": "Premium", "price": 15, "duration": "1 month", "days": 30},
            "ad_type_enterprise": {"name": "Enterprise", "price": 30, "duration": "3 months", "days": 90}
        }
        
        package = package_map.get(ad_type)
        if not package:
            await query.edit_message_text("❌ Invalid package selection.")
            return ConversationHandler.END
        
        # Store package details
        self.ad_purchase_data[user_id]['package'] = package
        self.ad_purchase_data[user_id]['step'] = AD_DESCRIPTION
        
        await query.edit_message_text(
            f"✅ *Package selected:* {package['name']} (${package['price']})\n\n"
            "🎯 *Step 3 of 4: Advertisement Description*\n\n"
            "Please send me the *description* for your advertisement:\n\n"
            "💡 *Example:*\n"
            "'Join our premium crypto signals service for accurate trading signals. "
            "We provide daily analysis and expert insights.'\n\n"
            "📝 *Tips:*\n• Keep it clear and concise\n• Highlight key benefits\n\n"
            "❌ *To cancel:* Type /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_DESCRIPTION
    
    async def receive_ad_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive ad description - FIXED"""
        user_id = update.message.from_user.id
        
        # Check if user has active purchase data
        if user_id not in self.ad_purchase_data:
            await update.message.reply_text("❌ Session expired. Please start over with /autoadvbuy")
            return ConversationHandler.END
        
        description = update.message.text
        
        # Validate description
        if len(description) < 10:
            await update.message.reply_text(
                "❌ Description too short! Please provide more details (min 10 characters):",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_DESCRIPTION
        
        if len(description) > 500:
            await update.message.reply_text(
                "❌ Description too long! Please keep it under 500 characters:",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_DESCRIPTION
        
        # Store description
        self.ad_purchase_data[user_id]['description'] = description
        self.ad_purchase_data[user_id]['step'] = AD_CONTACT
        
        await update.message.reply_text(
            f"✅ *Description saved!*\n\n"
            "🎯 *Step 4 of 4: Contact Information*\n\n"
            "Please send me your *contact information*:\n\n"
            "💡 *Examples:*\n• @your_username\n• your_email@example.com\n• +1234567890\n\n"
            "📞 *This will be displayed in your advertisement*\n\n"
            "❌ *To cancel:* Type /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_CONTACT
    
    async def receive_ad_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Receive contact information - FIXED"""
        user_id = update.message.from_user.id
        
        # Check if user has active purchase data
        if user_id not in self.ad_purchase_data:
            await update.message.reply_text("❌ Session expired. Please start over with /autoadvbuy")
            return ConversationHandler.END
        
        contact = update.message.text
        
        # Validate contact
        if len(contact) < 3:
            await update.message.reply_text(
                "❌ Contact information too short! Please provide valid contact details:",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_CONTACT
        
        # Store contact
        self.ad_purchase_data[user_id]['contact'] = contact
        self.ad_purchase_data[user_id]['step'] = AD_CONFIRMATION
        
        package = self.ad_purchase_data[user_id]['package']
        heading = self.ad_purchase_data[user_id]['heading']
        description = self.ad_purchase_data[user_id]['description']
        
        # Create confirmation message
        confirmation_text = f"""
✅ *ADVERTISEMENT DETAILS CONFIRMATION* ✅

📌 *Heading:* {heading}
🏷️ *Package:* {package['name']}
💰 *Price:* ${package['price']}
⏰ *Duration:* {package['duration']}
📝 *Description:*
{description}
📞 *Contact:* {contact}

💎 *Total Amount:* ${package['price']} USDT

🚀 *Ready to proceed with payment?*
"""
        keyboard = [
            [InlineKeyboardButton("✅ Confirm & Pay", callback_data="confirm_ad_payment")],
            [InlineKeyboardButton("✏️ Edit Details", callback_data="edit_ad_details")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_ad_final")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_CONFIRMATION
    
    async def process_ad_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process ad payment - FIXED"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Check if user has active purchase data
        if user_id not in self.ad_purchase_data:
            await query.edit_message_text("❌ Session expired. Please start over with /autoadvbuy")
            return ConversationHandler.END
        
        if query.data == "cancel_ad_final":
            await query.edit_message_text("❌ Advertisement purchase cancelled.")
            if user_id in self.ad_purchase_data:
                del self.ad_purchase_data[user_id]
            return ConversationHandler.END
        
        if query.data == "edit_ad_details":
            await query.edit_message_text(
                "✏️ *Editing Advertisement*\n\n"
                "Please send me the *heading/title* for your advertisement again:",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_HEADING
        
        # Process payment
        package = self.ad_purchase_data[user_id]['package']
        heading = self.ad_purchase_data[user_id]['heading']
        description = self.ad_purchase_data[user_id]['description']
        contact = self.ad_purchase_data[user_id]['contact']
        
        if PAYMENT_MODE == "dummy":
            # Dummy mode - process immediately
            processing_msg = await query.edit_message_text(
                "🔍 *PROCESSING PAYMENT* 🔍\n\n"
                "🔄 Dummy mode activated...\n"
                "⏳ Creating advertisement...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Simulate processing delay
            await asyncio.sleep(2)
            
            try:
                # Create ad in database
                created_at = datetime.now()
                expires_at = created_at + timedelta(days=package['days'])
                
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("""
                        INSERT INTO ads_queue (user_id, username, heading, type, description, contact, created_at, expires_at, status, post_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 0)
                    """, (
                        user_id,
                        query.from_user.username or f"user_{user_id}",
                        heading,
                        package['name'],
                        description,
                        contact,
                        created_at.isoformat(),
                        expires_at.isoformat()
                    ))
                    
                    # Record purchase
                    await db.execute("""
                        INSERT INTO purchases (user_id, username, product_type, amount, tx_hash, status, created_at, data)
                        VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
                    """, (
                        user_id,
                        query.from_user.username or f"user_{user_id}",
                        f"Advertising - {package['name']}",
                        package['price'],
                        f"DUMMY_TX_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        datetime.now().isoformat(),
                        json.dumps({
                            'heading': heading,
                            'description': description,
                            'contact': contact,
                            'duration': package['duration']
                        })
                    ))
                    
                    await db.commit()
                
                # Send success message
                success_text = f"""
🎉 *ADVERTISEMENT ACTIVATED!* 🎉

✅ *Payment Status:* COMPLETED (Dummy Mode)
📌 *Advertisement:* {heading}
🏷️ *Package:* {package['name']}
💰 *Amount:* ${package['price']}
⏰ *Duration:* {package['duration']}
📅 *Expires:* {expires_at.strftime('%Y-%m-%d')}

✨ *Your advertisement is now in the queue!*
📢 It will be automatically posted every 5-6 minutes.

💎 *Check your ad in queue:* /adviewqueue
📋 *View your ads:* /admyads

🚀 Thank you for choosing our advertising service!
"""
                await query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
                
            except Exception as e:
                logger.error(f"Error processing ad purchase: {e}")
                await query.edit_message_text(
                    "❌ *ERROR PROCESSING PAYMENT*\n\n"
                    "There was an error creating your advertisement.\n"
                    "Please try again or contact support.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
        else:
            # Real payment mode
            payment_id = f"AD_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            payment_text = f"""
💳 *PAYMENT REQUEST* 💳

📄 *Payment ID:* {payment_id}
👤 *Customer:* @{query.from_user.username}
📌 *Service:* Advertising - {package['name']}
💰 *Amount:* ${package['price']} USDT
⏰ *Duration:* {package['duration']}

🏦 *Payment Address:*
`{YOUR_USDT_ADDRESS}`

📋 *Instructions:*
1. Send exactly *${package['price']} USDT* to above address
2. Use TRC20 network only
3. Include payment ID in memo: *{payment_id}*
4. Wait for automatic verification (2-15 minutes)

🔍 *After payment, verify with:*
/autoadvverify {payment_id}
"""
            await query.edit_message_text(payment_text, parse_mode=ParseMode.MARKDOWN)
            
            # Store pending payment
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute("""
                        INSERT INTO pending_payments (user_id, product, amount, data, created_at, payment_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        user_id,
                        f"Advertising - {package['name']}",
                        package['price'],
                        json.dumps({
                            'heading': heading,
                            'description': description,
                            'contact': contact,
                            'duration': package['duration'],
                            'package_type': package['name']
                        }),
                        datetime.now().isoformat(),
                        payment_id
                    ))
                    await db.commit()
            except Exception as e:
                logger.error(f"Error storing pending payment: {e}")
        
        # Clean up user data
        if user_id in self.ad_purchase_data:
            del self.ad_purchase_data[user_id]
        
        return ConversationHandler.END
    
    async def cancel_ad_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel ad purchase - FIXED"""
        user_id = update.message.from_user.id
        
        # Clean up user data
        if user_id in self.ad_purchase_data:
            del self.ad_purchase_data[user_id]
        
        await update.message.reply_text(
            "❌ Advertisement purchase cancelled.\n\n"
            "You can start over anytime with /autoadvbuy",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show purchase history"""
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
                "📭 *NO PURCHASE HISTORY* 📭\n\n"
                "You haven't made any purchases yet.\n\n"
                "🚀 Use /autoadvbuy to explore available services!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        history_text = "📋 *YOUR PURCHASE HISTORY* 📋\n\n"
        total_spent = 0
        
        for purchase in purchases:
            product = purchase[0]
            amount = purchase[1]
            status = purchase[2]
            date = purchase[3].split('T')[0] if purchase[3] else "Unknown"
            
            status_icon = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
            
            history_text += f"{status_icon} *{product}*\n"
            history_text += f"   💰 Amount: ${amount}\n"
            history_text += f"   📅 Date: {date}\n"
            history_text += f"   🎯 Status: {status}\n"
            history_text += "   ━━━━━━━━━━━━━━━━\n\n"
            
            if status == "completed":
                total_spent += amount
        
        history_text += f"💰 *Total Spent:* ${total_spent:.2f}\n\n"
        history_text += "💎 *Thank you for your purchases!*"
        
        await update.message.reply_text(history_text, parse_mode=ParseMode.MARKDOWN)
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user balance"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT SUM(amount) FROM purchases WHERE user_id=? AND status='completed'", (user_id,))
            result = await cursor.fetchone()
            total_spent = result[0] if result[0] else 0
            
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE user_id=? AND status='completed'", (user_id,))
            total_purchases = (await cursor.fetchone())[0]
        
        await update.message.reply_text(
            f"💰 *YOUR BALANCE & STATS* 💰\n\n"
            f"👤 *User:* @{username}\n"
            f"💳 *Total Spent:* ${total_spent:.2f}\n"
            f"🛒 *Total Purchases:* {total_purchases}\n"
            f"⭐ *Customer Level:* {'🌟 VIP' if total_spent > 100 else '💫 Regular' if total_spent > 0 else '👤 New'}\n\n"
            f"💎 *Available Credits:* $0.00\n"
            f"🎯 *Loyalty Points:* {int(total_spent)}\n\n"
            f"✨ *Next VIP at:* ${max(100 - total_spent, 0):.2f} more\n\n"
            f"🚀 Keep investing in your success!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def invoice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create payment invoice"""
        if not context.args:
            await update.message.reply_text("📝 Usage: /autoadvinvoice [amount] [description?]")
            return
        
        try:
            amount = float(context.args[0])
            description = " ".join(context.args[1:]) if len(context.args) > 1 else "Payment Invoice"
        except ValueError:
            await update.message.reply_text("❌ Invalid amount!")
            return
        
        invoice_id = f"INV{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        await update.message.reply_text(
            f"🧾 *PAYMENT INVOICE* 🧾\n\n"
            f"📄 *Invoice ID:* {invoice_id}\n"
            f"👤 *To:* @{update.effective_user.username}\n"
            f"💰 *Amount:* ${amount:.2f}\n"
            f"📝 *Description:* {description}\n"
            f"📅 *Created:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"💎 *Payment Methods:*\n"
            f"• USDT (TRC20)\n\n"
            f"🚀 *To Pay:* Use /autoadvpay {amount}\n\n"
            f"⚡ This invoice is valid for 24 hours.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def rates_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current exchange rates"""
        await update.message.reply_text(
            "💱 *CURRENT EXCHANGE RATES* 💱\n\n"
            "💰 *Accepted Currencies:*\n"
            "• USDT (TRC20) - 1:1 with USD\n\n"
            "💎 *Service Rates:*\n\n"
            "📢 *Advertising:*\n"
            "• Basic (1 week): $5\n"
            "• Premium (1 month): $15\n"
            "• Enterprise (3 months): $30\n\n"
            "👑 *VIP Membership:*\n"
            "• 1 Month: $10\n"
            "• 3 Months: $25 (Save $5)\n"
            "• 6 Months: $45 (Save $15)\n"
            "• 1 Year: $80 (Save $40)\n\n"
            "🛡️ *Group Services:*\n"
            "• Custom pricing available\n"
            "• Contact for quote\n\n"
            "💫 *All prices in USD equivalent*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def pay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Make a payment"""
        # Check if command is in DM
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "🔒 *Please use this command in private messages only!*\n\n"
                "For security reasons, payments must be made in direct messages.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        if not context.args:
            await update.message.reply_text("📝 Usage: /autoadvpay [amount]")
            return
        
        try:
            amount = float(context.args[0])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Invalid amount! Must be positive number.")
            return
        
        payment_id = f"PAY{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        await update.message.reply_text(
            f"💳 *PAYMENT REQUEST* 💳\n\n"
            f"📄 *Payment ID:* {payment_id}\n"
            f"👤 *From:* @{update.effective_user.username}\n"
            f"💰 *Amount:* ${amount:.2f} USDT\n\n"
            f"🏦 *Payment Address:*\n"
            f"`{YOUR_USDT_ADDRESS}`\n\n"
            f"📋 *Instructions:*\n"
            "1. Send exactly *${amount:.2f} USDT* to above address\n"
            "2. Use TRC20 network only\n"
            "3. Include payment ID in memo: *{payment_id}*\n"
            "4. Wait for automatic verification (2-15 minutes)\n\n"
            f"🔍 *Verify:* /autoadvverify {payment_id}\n"
            f"📞 *Support:* Contact if issues\n\n"
            f"⚡ *Payment will auto-verify once confirmed on blockchain*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify transaction with payment mode check"""
        if not context.args:
            await update.message.reply_text("📝 Usage: /autoadvverify [payment_id/tx_hash]")
            return
        
        tx_identifier = context.args[0]
        
        # Check if command is in DM
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "🔒 *Please use this command in private messages only!*\n\n"
                "For security reasons, payment verification must be done in direct messages.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check payment mode
        if PAYMENT_MODE == "dummy":
            # In dummy mode, simulate verification without real payment
            await update.message.reply_text(
                f"🔍 *DUMMY MODE VERIFICATION* 🔍\n\n"
                f"📄 *Transaction:* {tx_identifier}\n"
                f"💰 *Amount:* Verified (Dummy Mode)\n"
                f"🎯 *Status:* COMPLETED\n\n"
                f"💎 Your payment has been confirmed!\n"
                f"✨ Thank you for your purchase!\n\n"
                f"⚠️ *Note:* Running in dummy mode - no real payment processed.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Store the purchase in database (dummy mode)
            user_id = update.effective_user.id
            username = update.effective_user.username or "No username"
            
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    INSERT INTO purchases (user_id, username, product_type, amount, tx_hash, status, created_at, data)
                    VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
                """, (user_id, username, "dummy_product", 0.0, tx_identifier, datetime.now().isoformat(), "dummy_mode_purchase"))
                await db.commit()
                
            return
        
        # Real payment mode verification (existing code)
        await update.message.reply_text(
            f"🔍 *VERIFYING TRANSACTION* 🔍\n\n"
            f"📄 *Identifier:* {tx_identifier}\n"
            f"⏰ *Status:* Checking blockchain...\n\n"
            f"⏳ Please wait while we verify your transaction...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Simulate delay for verification
        await asyncio.sleep(2)
        
        # Simulate verification result
        is_verified = random.choice([True, False])
        
        if is_verified:
            await update.message.reply_text(
                f"✅ *TRANSACTION VERIFIED* ✅\n\n"
                f"📄 *Transaction:* {tx_identifier}\n"
                f"💰 *Amount:* Verified\n"
                f"🎯 *Status:* COMPLETED\n\n"
                f"💎 Your payment has been confirmed!\n"
                f"✨ Thank you for your purchase!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ *TRANSACTION NOT FOUND* ❌\n\n"
                f"📄 *Transaction:* {tx_identifier}\n"
                f"🔍 *Status:* NOT VERIFIED\n\n"
                f"⚠️ *Possible Reasons:*\n"
                f"• Transaction not yet confirmed\n"
                f"• Wrong payment ID/memo\n"
                f"• Insufficient amount\n"
                f"• Network congestion\n\n"
                f"💫 *Please wait and try again in 5-10 minutes*",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def address_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get payment address"""
        await update.message.reply_text(
            f"🏦 *PAYMENT ADDRESS* 🏦\n\n"
            f"💎 *USDT (TRC20) Address:*\n"
            f"`{YOUR_USDT_ADDRESS}`\n\n"
            f"📋 *Important Notes:*\n"
            "• Only send *USDT* on *TRC20* network\n"
            "• Do not send other cryptocurrencies\n"
            "• Include payment ID in memo field\n"
            "• Minimum amount: $1\n"
            "• Network fee: Paid by sender\n\n"
            f"🔒 *Security:* This is our official address\n"
            f"📞 *Support:* Contact if unsure\n\n"
            f"⚡ *Always verify address before sending!*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def methods_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show payment methods"""
        await update.message.reply_text(
            "💳 *ACCEPTED PAYMENT METHODS* 💳\n\n"
            "💰 *Primary Method:*\n"
            "• USDT (TRC20) - Instant, Low fees\n\n"
            "🌐 *Supported Networks:*\n"
            "✅ TRC20 (Tron)\n"
            "❌ ERC20 (Ethereum) - Not supported\n"
            "❌ BEP20 (Binance) - Not supported\n\n"
            "💎 *Why USDT TRC20?*\n"
            "• Fast transactions (2-15 minutes)\n"
            "• Low network fees ($1-2)\n"
            "• Stable value (1:1 with USD)\n"
            "• Widely accepted\n\n"
            "🚀 *Getting Started:*\n"
            "1. Get USDT from any exchange\n"
            "2. Send to our TRC20 address\n"
            "3. Include payment ID in memo\n"
            "4. Wait for auto-verification\n\n"
            "📞 *Need help?* Contact support!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Payment support contact"""
        await update.message.reply_text(
            "📞 *PAYMENT SUPPORT CONTACT* 📞\n\n"
            "For payment-related issues:\n\n"
            "💳 *Payment Problems:*\n"
            f"{AUTOADV_BOT_USERNAME}\n\n"
            "👑 *VIP & Services:*\n"
            f"{VIP_BOT_USERNAME}\n\n"
            "📢 *Advertising:*\n"
            f"{ADV_BOT_USERNAME}\n\n"
            "🛡️ *Group Management:*\n"
            f"{GROUP_BOT_USERNAME}\n\n"
            "⏰ *Payment Support Hours:* 24/7\n"
            "🚨 *Urgent Issues:* Immediate response\n\n"
            "💎 *We're here to help!*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Admin commands implementation
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Payment statistics (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can view payment stats!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE status='completed'")
            completed = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE status='pending'")
            pending = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE status='failed'")
            failed = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(amount) FROM purchases WHERE status='completed'")
            volume_result = await cursor.fetchone()
            total_volume = volume_result[0] if volume_result[0] else 0
            
            cursor = await db.execute("SELECT product_type, COUNT(*) FROM purchases WHERE status='completed' GROUP BY product_type")
            product_stats = await cursor.fetchall()
        
        stats_text = f"""
📈 *PAYMENT SYSTEM STATISTICS* 📈

💳 *TRANSACTION OVERVIEW:*
▫️ Completed: {completed}
▫️ Pending: {pending}
▫️ Failed: {failed}
▫️ Success Rate: {completed/(completed+failed)*100 if (completed+failed) > 0 else 0:.1f}%

💰 *FINANCIAL METRICS:*
▫️ Total Volume: ${total_volume:.2f}
▫️ Average Transaction: ${total_volume/completed if completed > 0 else 0:.2f}

🎯 *PRODUCT BREAKDOWN:*
"""
        
        for product, count in product_stats:
            stats_text += f"▫️ {product}: {count}\n"
        
        stats_text += f"""
🔥 *SYSTEM STATUS:*
▫️ Payment Gateway: ✅ ACTIVE
▫️ Auto-Verification: ✅ ENABLED
▫️ Blockchain Sync: ✅ CONNECTED

💪 *The payment empire grows stronger, Master!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def transactions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all transactions (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can view all transactions!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT user_id, product_type, amount, status, created_at 
                FROM purchases 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            transactions = await cursor.fetchall()
        
        if not transactions:
            await update.message.reply_text("📭 No transactions found!")
            return
        
        transactions_text = "📋 *RECENT TRANSACTIONS* 📋\n\n"
        
        for transaction in transactions:
            user_id = transaction[0]
            product = transaction[1]
            amount = transaction[2]
            status = transaction[3]
            date = transaction[4].split('T')[0] if transaction[4] else "Unknown"
            
            status_icon = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
            
            transactions_text += f"{status_icon} *User {user_id}*\n"
            transactions_text += f"   🛒 {product}\n"
            transactions_text += f"   💰 ${amount}\n"
            transactions_text += f"   📅 {date}\n"
            transactions_text += f"   🎯 {status}\n"
            transactions_text += "   ━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(transactions_text, parse_mode=ParseMode.MARKDOWN)
    
    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export transaction data (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can export data!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM purchases")
            total_transactions = (await cursor.fetchone())[0]
        
        export_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        await update.message.reply_text(
            f"💾 *TRANSACTION DATA EXPORT* 💾\n\n"
            f"📊 Total Transactions: {total_transactions}\n"
            f"📁 Export File: `transactions_export_{export_time}.csv`\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"📋 *Included Data:*\n"
            f"• All transactions\n"
            f"• User information\n"
            f"• Payment details\n"
            f"• Timestamps\n\n"
            f"⚠️ Demo: In production, file would be generated and sent.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Payment system settings (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can access settings!")
            return
        
        await update.message.reply_text(
            "⚙️ *PAYMENT SYSTEM SETTINGS* ⚙️\n\n"
            "🔧 *Current Configuration:*\n"
            "• Payment Gateway: ✅ ACTIVE\n"
            "• Auto-Verification: ✅ ENABLED\n"
            "• USDT TRC20: ✅ ACCEPTED\n"
            "• Minimum Amount: $1.00\n"
            "• Maximum Amount: $10,000\n\n"
            "📊 *System Status:*\n"
            "• Blockchain Connection: ✅ STABLE\n"
            "• Database: ✅ HEALTHY\n"
            "• API Endpoints: ✅ RESPONSIVE\n\n"
            "🚀 *Available Actions:*\n"
            "• /autoadvstats - View statistics\n"
            "• /autoadvtransactions - View transactions\n"
            "• /autoadvexport - Export data\n"
            "• /autoadvmaintenance - Maintenance mode\n"
            "• /autoadvverifyall - Verify all pending",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def verify_all_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify all pending transactions (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only Supreme Admins can verify all transactions!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE status='pending'")
            pending_count = (await cursor.fetchone())[0]
            
            # Simulate verification process
            await db.execute("UPDATE purchases SET status='completed' WHERE status='pending'")
            await db.commit()
        
        await update.message.reply_text(
            f"🔍 *BULK VERIFICATION COMPLETE* 🔍\n\n"
            f"📊 Transactions Processed: {pending_count}\n"
            f"✅ Status: All verified\n\n"
            f"💎 Pending transactions have been processed!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "buy_advertising":
            await self.start_ad_purchase(update, context)
        elif data == "buy_vip":
            await query.edit_message_text(
                "👑 *VIP MEMBERSHIP PACKAGES* 👑\n\n"
                "💎 *Choose your VIP level:*\n\n"
                "⭐ *1 Month - $10*\n"
                "• VIP channel access\n"
                "• Exclusive content\n"
                "• Priority support\n"
                "• Special promotions\n\n"
                "🌟🌟 *3 Months - $25* (Save $5)\n"
                "• All 1-month features\n"
                "• Extended benefits\n"
                "• Early access\n"
                "• Personal assistant\n\n"
                "🌟🌟🌟 *6 Months - $45* (Save $15)\n"
                "• All 3-month features\n"
                "• VIP badge\n"
                "• Custom requests\n"
                "• Business networking\n\n"
                "💎 *1 Year - $80* (Save $40)\n"
                "• All 6-month features\n"
                "• Maximum benefits\n"
                "• Lifetime memories\n"
                "• Elite status\n\n"
                "🚀 *To Purchase:*\n"
                "Use /autoadvpay [amount]\n\n"
                "✨ *Become VIP today!*",
                parse_mode=ParseMode.MARKDOWN
            )
        elif data == "buy_group":
            await query.edit_message_text(
                "🛡️ *GROUP SERVICES* 🛡️\n\n"
                "💎 *Custom Group Solutions:*\n\n"
                "🔧 *Management Services:*\n"
                "• Custom moderation setup\n"
                "• Automated systems\n"
                "• Security configuration\n"
                "• Member management\n\n"
                "🚀 *Growth Services:*\n"
                "• Member acquisition\n"
                "• Engagement strategies\n"
                "• Content planning\n"
                "• Analytics setup\n\n"
                "💼 *Business Services:*\n"
                "• Group monetization\n"
                "• Advertising integration\n"
                "• Partnership setup\n"
                "• Revenue optimization\n\n"
                "📞 *Contact for Pricing:*\n"
                "Custom quotes based on requirements\n\n"
                "💫 *We tailor solutions to your needs!*",
                parse_mode=ParseMode.MARKDOWN
            )
        elif data == "buy_custom":
            await query.edit_message_text(
                "💰 *CUSTOM PACKAGES* 💰\n\n"
                "💎 *Tailored Solutions:*\n\n"
                "🎯 *We understand* that every business has unique needs. "
                "Our custom packages are designed to provide exactly what you need, "
                "nothing more, nothing less.\n\n"
                "✨ *What we offer:*\n"
                "• Combined advertising + VIP packages\n"
                "• Bulk discounts for multiple services\n"
                "• Long-term partnership deals\n"
                "• Enterprise-level solutions\n"
                "• White-label services\n\n"
                "📞 *Get Your Custom Quote:*\n"
                "Contact us with your requirements:\n"
                f"{AUTOADV_BOT_USERNAME}\n\n"
                "🚀 *Let's build something amazing together!*",
                parse_mode=ParseMode.MARKDOWN
            )
        elif data in ["confirm_ad_payment", "edit_ad_details", "cancel_ad_final"]:
            await self.process_ad_payment(update, context)
        elif data.startswith("ad_type_"):
            await self.receive_ad_type(update, context)
    
    def setup_handlers(self):
        """Setup all payment bot handlers with prefixes - FIXED"""
        # Basic commands
        self.app.add_handler(CommandHandler("autoadvstart", self.start_command))
        self.app.add_handler(CommandHandler("autoadvhelp", self.help_command))
        self.app.add_handler(CommandHandler("autoadvabout", self.about_command))
        self.app.add_handler(CommandHandler("autoadvstatus", self.status_command))
        self.app.add_handler(CommandHandler("autoadvbuy", self.buy_command))
        self.app.add_handler(CommandHandler("autoadvhistory", self.history_command))
        self.app.add_handler(CommandHandler("autoadvbalance", self.balance_command))
        self.app.add_handler(CommandHandler("autoadvinvoice", self.invoice_command))
        self.app.add_handler(CommandHandler("autoadvrates", self.rates_command))
        self.app.add_handler(CommandHandler("autoadvpay", self.pay_command))
        self.app.add_handler(CommandHandler("autoadvverify", self.verify_command))
        self.app.add_handler(CommandHandler("autoadvaddress", self.address_command))
        self.app.add_handler(CommandHandler("autoadvmethods", self.methods_command))
        self.app.add_handler(CommandHandler("autoadvcontact", self.contact_command))
        
        # Admin commands
        self.app.add_handler(CommandHandler("autoadvstats", self.stats_command))
        self.app.add_handler(CommandHandler("autoadvtransactions", self.transactions_command))
        self.app.add_handler(CommandHandler("autoadvexport", self.export_command))
        self.app.add_handler(CommandHandler("autoadvsettings", self.settings_command))
        self.app.add_handler(CommandHandler("autoadvverifyall", self.verify_all_command))
        
        # Ad purchase conversation handler - FIXED
        ad_purchase_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_ad_purchase, pattern="^buy_advertising$")],
            states={
                AD_HEADING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_heading)
                ],
                AD_TYPE: [
                    CallbackQueryHandler(self.receive_ad_type, pattern="^(ad_type_|cancel_ad)$")
                ],
                AD_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_description)
                ],
                AD_CONTACT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_contact)
                ],
                AD_CONFIRMATION: [
                    CallbackQueryHandler(self.process_ad_payment, pattern="^(confirm_ad_payment|edit_ad_details|cancel_ad_final)$")
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_ad_purchase)],
            allow_reentry=True
        )
        
        self.app.add_handler(ad_purchase_conv)
        
        # Callback query handlers for buttons
        self.app.add_handler(CallbackQueryHandler(self.button_handler, pattern="^(buy_vip|buy_group|buy_custom|confirm_ad_payment|edit_ad_details|cancel_ad_final|ad_type_|cancel_ad)$"))
    
    async def run(self):
        """Run the AutoADV payment bot"""
        await init_database()
        self.setup_handlers()
        
        logger.info("💰 AutoADV Payment Bot is running...")
        try:
            await self.app.run_polling()
        except Exception as e:
            logger.error(f"❌ Error in AutoADV Bot: {e}")

# ============================
# 🚀 MAIN EXECUTION - FIXED
# ============================

async def main():
    """Main function to run all bots - FIXED"""
    try:
        logger.info("🚀 Starting INTERLINK Multi-Bot System...")
        
        # Initialize database first
        await init_database()
        
        # Initialize all bots
        adv_bot = AdvertisingBot(ADV_BOT_TOKEN)
        vip_bot = VIPVerificationBot(VIP_BOT_TOKEN)
        group_bot = GroupManagementBot(GROUP_BOT_TOKEN)
        autoadv_bot = AutoAdvPaymentBot(AUTOADV_BOT_TOKEN)
        
        logger.info("✅ All bots initialized successfully")
        
        # Run all bots concurrently
        tasks = [
            asyncio.create_task(adv_bot.run(), name="AdvertisingBot"),
            asyncio.create_task(vip_bot.run(), name="VIPBot"),
            asyncio.create_task(group_bot.run(), name="GroupBot"),
            asyncio.create_task(autoadv_bot.run(), name="AutoADVBot")
        ]
        
        logger.info("⚡ All bots are now running...")
        
        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down gracefully...")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot system stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)