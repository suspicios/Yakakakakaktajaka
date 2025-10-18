"""
🚀 INTERLINK MULTI-BOT SYSTEM
Complete bot ecosystem for group management, VIP verification, advertising, and payment processing.

Author: 
Version: 1.1.0
Enhanced with comprehensive error handlig
"""

import asyncio
import aiosqlite
import logging
import random
import re
import json
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, NetworkError, BadRequest, TimedOut, ChatMigrated
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError

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

# Bot Prefixes
ADV_PREFIX = "adv"
VIP_PREFIX = "vip"
GROUP_PREFIX = "group"
AUTOADV_PREFIX = "autoadv"

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================
# 🛡️ ERROR HANDLER UTILITIES
# ============================

class ErrorHandler:
    """Comprehensive error handling utilities"""
    
    @staticmethod
    async def handle_telegram_error(method, *args, **kwargs):
        """Handle Telegram API errors with retry logic"""
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                return await method(*args, **kwargs)
            except (NetworkError, TimedOut) as e:
                last_exception = e
                logger.warning(f"Telegram network error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except BadRequest as e:
                logger.error(f"Telegram bad request error: {e}")
                raise
            except ChatMigrated as e:
                logger.error(f"Chat migrated error: {e}")
                raise
            except TelegramError as e:
                logger.error(f"Telegram API error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in Telegram operation: {e}")
                raise
        
        logger.error(f"All retry attempts failed for {method.__name__}")
        raise last_exception
    
    @staticmethod
    async def handle_database_error(method, *args, **kwargs):
        """Handle database errors with retry logic"""
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                return await method(*args, **kwargs)
            except aiosqlite.Error as e:
                last_exception = e
                logger.warning(f"Database error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except Exception as e:
                logger.error(f"Unexpected database error: {e}")
                raise
        
        logger.error(f"All database retry attempts failed for {method.__name__}")
        raise last_exception
    
    @staticmethod
    async def safe_send_message(bot, chat_id, text, **kwargs):
        """Safely send message with comprehensive error handling"""
        try:
            return await ErrorHandler.handle_telegram_error(
                bot.send_message, chat_id, text, **kwargs
            )
        except BadRequest as e:
            if "Message is too long" in str(e):
                # Split long messages
                chunks = [text[i:i + 4096] for i in range(0, len(text), 4096)]
                for chunk in chunks:
                    await ErrorHandler.safe_send_message(bot, chat_id, chunk, **kwargs)
            else:
                logger.error(f"Failed to send message to {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
    
    @staticmethod
    async def safe_edit_message(query, text, **kwargs):
        """Safely edit message with error handling"""
        try:
            return await ErrorHandler.handle_telegram_error(
                query.edit_message_text, text, **kwargs
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass  # Ignore if message wasn't modified
            else:
                logger.error(f"Failed to edit message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error editing message: {e}")

# ============================
# 🗄️ DATABASE INITIALIZATION
# ============================

async def init_database():
    """Initialize all database tables with error handling"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Advertising Bot Tables
            await ErrorHandler.handle_database_error(
                db.execute,
                """
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
                    post_count INTEGER DEFAULT 0,
                    has_buttons INTEGER DEFAULT 1,
                    has_image INTEGER DEFAULT 0,
                    image_url TEXT
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS ad_config (
                    id INTEGER PRIMARY KEY,
                    last_post_time TIMESTAMP,
                    is_paused INTEGER DEFAULT 0,
                    post_interval INTEGER DEFAULT 5,
                    max_ads_per_day INTEGER DEFAULT 50
                )
                """
            )
            
            # VIP Bot Tables
            await ErrorHandler.handle_database_error(
                db.execute,
                """
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
                """
            )
            
            # Group Management Tables
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS new_members (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    join_time TIMESTAMP,
                    verified INTEGER DEFAULT 0
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    violation_type TEXT,
                    timestamp TIMESTAMP,
                    warning_count INTEGER DEFAULT 1
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS exempted_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    added_at TIMESTAMP
                )
                """
            )
            
            # AutoADV Bot Tables
            await ErrorHandler.handle_database_error(
                db.execute,
                """
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
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS pending_payments (
                    user_id INTEGER PRIMARY KEY,
                    product TEXT,
                    amount REAL,
                    data TEXT,
                    created_at TIMESTAMP,
                    payment_id TEXT
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER,
                    action TEXT,
                    timestamp TIMESTAMP,
                    count INTEGER DEFAULT 1
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS transaction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    tx_hash TEXT,
                    verified INTEGER,
                    timestamp TIMESTAMP,
                    details TEXT
                )
                """
            )
            
            # Bot Configuration Tables
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS bot_configs (
                    bot_name TEXT PRIMARY KEY,
                    config_data TEXT,
                    updated_at TIMESTAMP
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS admin_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT,
                    updated_at TIMESTAMP
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value INTEGER,
                    recorded_at TIMESTAMP
                )
                """
            )
            
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_type TEXT,
                    user_id INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP
                )
                """
            )
            
            # Error logging table
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    traceback TEXT,
                    user_id INTEGER,
                    timestamp TIMESTAMP
                )
                """
            )
            
            # Initialize default config
            await ErrorHandler.handle_database_error(
                db.execute,
                """
                INSERT OR IGNORE INTO ad_config (id, last_post_time, is_paused, post_interval, max_ads_per_day)
                VALUES (1, ?, 0, 5, 50)
                """,
                (datetime.now().isoformat(),)
            )
            
            await ErrorHandler.handle_database_error(db.commit)
            logger.info("✅ Database initialized successfully")
            
    except Exception as e:
        logger.error(f"❌ Critical error initializing database: {e}")
        raise

async def log_error(bot_name: str, error: Exception, user_id: int = None):
    """Log errors to database"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                INSERT INTO error_logs (bot_name, error_type, error_message, traceback, user_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (bot_name, type(error).__name__, str(error), traceback.format_exc(), user_id, datetime.now().isoformat())
            )
            await db.commit()
    except Exception as log_error:
        logger.error(f"Failed to log error: {log_error}")

# ============================
# 🔧 CONFIGURATION MANAGEMENT
# ============================

class ConfigManager:
    @staticmethod
    async def get_bot_config(bot_name: str) -> Dict:
        """Get bot configuration with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT config_data FROM bot_configs WHERE bot_name = ?",
                    (bot_name,)
                )
                result = await cursor.fetchone()
                if result and result[0]:
                    return json.loads(result[0])
                return {}
        except Exception as e:
            logger.error(f"Error getting bot config for {bot_name}: {e}")
            await log_error("ConfigManager", e)
            return {}

    @staticmethod
    async def save_bot_config(bot_name: str, config_data: Dict):
        """Save bot configuration with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    INSERT OR REPLACE INTO bot_configs (bot_name, config_data, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (bot_name, json.dumps(config_data), datetime.now().isoformat())
                )
                await ErrorHandler.handle_database_error(db.commit)
        except Exception as e:
            logger.error(f"Error saving bot config for {bot_name}: {e}")
            await log_error("ConfigManager", e)
            raise

    @staticmethod
    async def get_admin_setting(key: str) -> str:
        """Get admin setting with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT setting_value FROM admin_settings WHERE setting_key = ?",
                    (key,)
                )
                result = await cursor.fetchone()
                return result[0] if result else ""
        except Exception as e:
            logger.error(f"Error getting admin setting {key}: {e}")
            await log_error("ConfigManager", e)
            return ""

    @staticmethod
    async def save_admin_setting(key: str, value: str):
        """Save admin setting with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    INSERT OR REPLACE INTO admin_settings (setting_key, setting_value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, value, datetime.now().isoformat())
                )
                await ErrorHandler.handle_database_error(db.commit)
        except Exception as e:
            logger.error(f"Error saving admin setting {key}: {e}")
            await log_error("ConfigManager", e)
            raise

    @staticmethod
    async def update_statistics(metric_name: str, value: int = 1):
        """Update statistics with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    INSERT INTO statistics (metric_name, metric_value, recorded_at)
                    VALUES (?, ?, ?)
                    """,
                    (metric_name, value, datetime.now().isoformat())
                )
                await ErrorHandler.handle_database_error(db.commit)
        except Exception as e:
            logger.error(f"Error updating statistics for {metric_name}: {e}")
            await log_error("ConfigManager", e)

    @staticmethod
    async def get_statistics(metric_name: str, days: int = 7) -> List:
        """Get statistics for a metric with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                since_date = (datetime.now() - timedelta(days=days)).isoformat()
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT DATE(recorded_at), SUM(metric_value) 
                    FROM statistics 
                    WHERE metric_name = ? AND recorded_at > ?
                    GROUP BY DATE(recorded_at)
                    ORDER BY recorded_at DESC
                    """,
                    (metric_name, since_date)
                )
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting statistics for {metric_name}: {e}")
            await log_error("ConfigManager", e)
            return []

# ============================
# 📊 STATISTICS MANAGER
# ============================

class StatisticsManager:
    @staticmethod
    async def get_system_stats() -> Dict[str, Any]:
        """Get comprehensive system statistics with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                stats = {}
                
                # Advertisement stats
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM ads_queue WHERE status='active'"
                )
                stats['active_ads'] = (await cursor.fetchone())[0]
                
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM ads_queue"
                )
                stats['total_ads'] = (await cursor.fetchone())[0]
                
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT SUM(post_count) FROM ads_queue"
                )
                result = await cursor.fetchone()
                stats['total_posts'] = result[0] if result[0] else 0
                
                # VIP stats
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM vip_members WHERE is_active=1"
                )
                stats['active_vips'] = (await cursor.fetchone())[0]
                
                # Purchase stats
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM purchases"
                )
                stats['total_purchases'] = (await cursor.fetchone())[0]
                
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT SUM(amount) FROM purchases WHERE status='completed'"
                )
                result = await cursor.fetchone()
                stats['total_revenue'] = result[0] if result[0] else 0
                
                # Member stats
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM new_members WHERE verified=1"
                )
                stats['verified_members'] = (await cursor.fetchone())[0]
                
                # Today's stats
                today = datetime.now().date().isoformat()
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM statistics WHERE metric_name='ad_posted' AND DATE(recorded_at)=?",
                    (today,)
                )
                stats['posts_today'] = (await cursor.fetchone())[0]
                
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM purchases WHERE DATE(created_at)=?",
                    (today,)
                )
                stats['purchases_today'] = (await cursor.fetchone())[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            await log_error("StatisticsManager", e)
            return {
                'active_ads': 0, 'total_ads': 0, 'total_posts': 0,
                'active_vips': 0, 'total_purchases': 0, 'total_revenue': 0,
                'verified_members': 0, 'posts_today': 0, 'purchases_today': 0
            }

    @staticmethod
    async def get_revenue_analytics(days: int = 30) -> Dict[str, Any]:
        """Get revenue analytics with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                since_date = (datetime.now() - timedelta(days=days)).isoformat()
                
                # Daily revenue
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT DATE(created_at), SUM(amount) 
                    FROM purchases 
                    WHERE status='completed' AND created_at > ?
                    GROUP BY DATE(created_at)
                    ORDER BY created_at DESC
                    LIMIT 30
                    """,
                    (since_date,)
                )
                daily_revenue = await cursor.fetchall()
                
                # Product breakdown
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT product_type, COUNT(*), SUM(amount)
                    FROM purchases 
                    WHERE status='completed' AND created_at > ?
                    GROUP BY product_type
                    """,
                    (since_date,)
                )
                product_breakdown = await cursor.fetchall()
                
                # Top buyers
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT username, COUNT(*), SUM(amount)
                    FROM purchases 
                    WHERE status='completed' AND created_at > ?
                    GROUP BY user_id, username
                    ORDER BY SUM(amount) DESC
                    LIMIT 10
                    """,
                    (since_date,)
                )
                top_buyers = await cursor.fetchall()
                
                return {
                    'daily_revenue': daily_revenue,
                    'product_breakdown': product_breakdown,
                    'top_buyers': top_buyers
                }
                
        except Exception as e:
            logger.error(f"Error getting revenue analytics: {e}")
            await log_error("StatisticsManager", e)
            return {
                'daily_revenue': [],
                'product_breakdown': [],
                'top_buyers': []
            }

# ============================
# 🤖 1. ADVERTISING BOT
# ============================

class AdvertisingBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.scheduler = AsyncIOScheduler()
        self.prefix = ADV_PREFIX
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with godly welcome"""
        try:
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "🌟 *GREETINGS, MASTER OF ADVERTISING!* 🌟\n\n"
                "I am the *Advertising Bot*, your divine servant in the realm of promotions! "
                "I exist to spread your message across the sacred grounds of your groups.\n\n"
                "✨ *MY DIVINE POWERS:* ✨\n"
                "📢 Auto-posting ads every 5-6 minutes\n"
                "📌 Auto-pinning in Main Group\n"
                "🎯 Showcasing platform upgrades\n"
                "🔄 Rotating purchased advertisements\n\n"
                "⚡ *COMMANDS AT YOUR DISPOSAL:* ⚡\n"
                f"/{self.prefix}_help - View all my divine commands\n"
                f"/{self.prefix}_stats - See advertising statistics\n"
                f"/{self.prefix}_viewqueue - Check pending ads\n\n"
                "Your wish is my command, O Great One! 🙇",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive help with all commands"""
        try:
            is_admin = update.effective_user.id in ADMIN_IDS
            
            user_commands = f"""
🌟 *ADVERTISING BOT - COMMAND BIBLE* 🌟

📱 *GENERAL COMMANDS:*
/{self.prefix}_start - Awaken the advertising god
/{self.prefix}_help - Divine command reference
/{self.prefix}_about - Learn about my existence
/{self.prefix}_status - Current bot status
/{self.prefix}_stats - Advertising statistics
/{self.prefix}_viewqueue - See all pending ads
/{self.prefix}_myads - Your active advertisements
/{self.prefix}_contact - Contact support

🎯 *AD MANAGEMENT:*
/{self.prefix}_viewqueue - All ads in queue
/{self.prefix}_checkad [id] - Check specific ad
/{self.prefix}_adstats - Detailed ad analytics
/{self.prefix}_topads - Most viewed ads
"""
            
            admin_commands = f"""
👑 *ADMIN COMMANDS:*
/{self.prefix}_pause - Pause all advertising
/{self.prefix}_resume - Resume advertising
/{self.prefix}_clearqueue - Clear ad queue
/{self.prefix}_removead [id] - Remove specific ad
/{self.prefix}_editad [id] - Edit advertisement
/{self.prefix}_setinterval [min] - Set post interval
/{self.prefix}_forcead - Force post next ad
/{self.prefix}_skipnext - Skip next scheduled ad
/{self.prefix}_broadcast [msg] - Broadcast message
/{self.prefix}_adlogs - View posting logs
/{self.prefix}_resetstats - Reset statistics
/{self.prefix}_backup - Backup ad database
/{self.prefix}_restore - Restore from backup
/{self.prefix}_maintenance - Toggle maintenance mode
/{self.prefix}_adpreview [id] - Preview ad before posting
/{self.prefix}_schedulepost [time] - Schedule specific post
/{self.prefix}_analytics - Deep analytics dashboard
/{self.prefix}_exportads - Export ads to CSV
/{self.prefix}_importads - Import ads from file
/{self.prefix}_pinnext - Pin next ad manually
/{self.prefix}_unpinlast - Unpin last ad
/{self.prefix}_setemergency [msg] - Set emergency broadcast
/{self.prefix}_testpost - Test ad posting
/{self.prefix}_config - Bot configuration
/{self.prefix}_admin - Admin panel
/{self.prefix}_system_stats - System statistics
"""
            
            help_text = user_commands
            if is_admin:
                help_text += admin_commands
            
            help_text += "\n💫 *Your command is my sacred duty!* 💫"
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                help_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in help_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show advertising statistics"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                # Total ads
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM ads_queue WHERE status='active'"
                )
                active_ads = (await cursor.fetchone())[0]
                
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM ads_queue"
                )
                total_ads = (await cursor.fetchone())[0]
                
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT SUM(post_count) FROM ads_queue"
                )
                result = await cursor.fetchone()
                total_posts = result[0] if result[0] else 0
                
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT last_post_time FROM ad_config WHERE id=1"
                )
                result = await cursor.fetchone()
                last_post = result[0] if result else "Never"
                
                # Today's stats
                today = datetime.now().date().isoformat()
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT COUNT(*) FROM statistics WHERE metric_name='ad_posted' AND DATE(recorded_at)=?",
                    (today,)
                )
                today_posts = (await cursor.fetchone())[0]
            
            stats_text = f"""
📊 *ADVERTISING EMPIRE STATISTICS* 📊

🎯 *ADVERTISEMENT METRICS:*
▫️ Active Ads: {active_ads}
▫️ Total Ads (All Time): {total_ads}
▫️ Total Posts Delivered: {total_posts}
▫️ Posts Today: {today_posts}
▫️ Last Posted: {last_post}

🔥 *CURRENT STATUS:*
▫️ Auto-Posting: ✅ ACTIVE
▫️ Interval: 5-6 minutes
▫️ Target Groups: Main + Company Resources

💪 *Your advertising empire grows stronger, Master!*
"""
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                stats_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in stats_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error retrieving statistics. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def view_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all ads in queue"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT id, heading, type, expires_at, post_count, has_buttons, has_image
                    FROM ads_queue WHERE status='active' 
                    ORDER BY created_at DESC LIMIT 10
                    """
                )
                ads = await cursor.fetchall()
            
            if not ads:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
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
                queue_text += f"🔘 *Buttons:* {'✅' if ad[5] else '❌'}\n"
                queue_text += f"🖼️ *Image:* {'✅' if ad[6] else '❌'}\n"
                queue_text += "━━━━━━━━━━━━━━━━\n\n"
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                queue_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in view_queue_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error retrieving ad queue. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def pause_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause advertising (Admin only)"""
        try:
            if update.effective_user.id not in ADMIN_IDS:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "⛔ Only the Supreme Admins can use this power!"
                )
                return
            
            async with aiosqlite.connect(DB_NAME) as db:
                await ErrorHandler.handle_database_error(
                    db.execute,
                    "UPDATE ad_config SET is_paused=1 WHERE id=1"
                )
                await ErrorHandler.handle_database_error(db.commit)
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "⏸️ *ADVERTISING PAUSED* ⏸️\n\n"
                "The advertising machine slumbers, O Master! "
                "Use /resume to awaken it once more. 💤",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in pause_ads_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error pausing ads. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def resume_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume advertising (Admin only)"""
        try:
            if update.effective_user.id not in ADMIN_IDS:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "⛔ Only the Supreme Admins can use this power!"
                )
                return
            
            async with aiosqlite.connect(DB_NAME) as db:
                await ErrorHandler.handle_database_error(
                    db.execute,
                    "UPDATE ad_config SET is_paused=0 WHERE id=1"
                )
                await ErrorHandler.handle_database_error(db.commit)
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "▶️ *ADVERTISING RESUMED* ▶️\n\n"
                "The advertising machine roars back to life! "
                "Your promotions shall flow like rivers! 🌊",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in resume_ads_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error resuming ads. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot configuration (Admin only)"""
        try:
            if update.effective_user.id not in ADMIN_IDS:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "⛔ Only the Supreme Admins can configure the bot!"
                )
                return
            
            config = await ConfigManager.get_bot_config("advertising_bot")
            current_config = await self.get_current_config()
            
            config_text = f"""
🔧 *ADVERTISING BOT CONFIGURATION* 🔧

📊 *Current Settings:*
▫️ Post Interval: {current_config['post_interval']} minutes
▫️ Max Ads Per Day: {current_config['max_ads_per_day']}
▫️ Auto-Posting: {'✅ ACTIVE' if not current_config['is_paused'] else '⏸️ PAUSED'}
▫️ Last Post: {current_config['last_post_time']}

⚡ *Configuration Commands:*
/{self.prefix}_setinterval [minutes] - Set post interval
/{self.prefix}_setmaxads [number] - Set max ads per day
/{self.prefix}_toggle_autopost - Toggle auto-posting
/{self.prefix}_reset_config - Reset to defaults
"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 Set Interval", callback_data="adv_set_interval")],
                [InlineKeyboardButton("📊 Set Max Ads", callback_data="adv_set_maxads")],
                [InlineKeyboardButton("⏸️ Toggle Auto-Post", callback_data="adv_toggle_autopost")],
                [InlineKeyboardButton("🔄 Reset Config", callback_data="adv_reset_config")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                config_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error in config_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error loading configuration. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def get_current_config(self) -> Dict:
        """Get current advertising configuration with error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT * FROM ad_config WHERE id=1"
                )
                result = await cursor.fetchone()
                if result:
                    return {
                        'last_post_time': result[1],
                        'is_paused': bool(result[2]),
                        'post_interval': result[3],
                        'max_ads_per_day': result[4]
                    }
                return {}
        except Exception as e:
            logger.error(f"Error getting current config: {e}")
            await log_error("AdvertisingBot", e)
            return {}
    
    async def admin_panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel (Admin only)"""
        try:
            if update.effective_user.id not in ADMIN_IDS:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "⛔ Only the Supreme Admins can access the admin panel!"
                )
                return
            
            # Get comprehensive statistics
            stats = await StatisticsManager.get_system_stats()
            current_config = await self.get_current_config()
            
            admin_text = f"""
👑 *ADVERTISING BOT ADMIN PANEL* 👑

📊 *SYSTEM OVERVIEW:*
▫️ Active Ads: {stats['active_ads']}
▫️ Total Posts: {stats['total_posts']}
▫️ Posts Today: {stats['posts_today']}
▫️ Verified Members: {stats['verified_members']}

⚙️ *CURRENT CONFIG:*
▫️ Post Interval: {current_config.get('post_interval', 5)} min
▫️ Max Ads/Day: {current_config.get('max_ads_per_day', 50)}
▫️ Status: {'⏸️ PAUSED' if current_config.get('is_paused') else '✅ ACTIVE'}

⚡ *MANAGEMENT ACTIONS:*
• Configure bot settings
• Monitor ad performance  
• Manage ad queue
• View financial reports
• System maintenance

🔧 *QUICK ACTIONS:*
Use the buttons below for quick management!
"""
            
            keyboard = [
                [InlineKeyboardButton("⚙️ Configuration", callback_data="adv_config"),
                 InlineKeyboardButton("📊 Statistics", callback_data="adv_stats")],
                [InlineKeyboardButton("📋 View Queue", callback_data="adv_viewqueue"),
                 InlineKeyboardButton("⏸️ Pause/Resume", callback_data="adv_toggle_pause")],
                [InlineKeyboardButton("💰 Revenue Report", callback_data="adv_revenue"),
                 InlineKeyboardButton("🔄 System Check", callback_data="adv_system_check")],
                [InlineKeyboardButton("📈 Analytics", callback_data="adv_analytics")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                admin_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error in admin_panel_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error loading admin panel. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def system_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show comprehensive system statistics (Admin only)"""
        try:
            if update.effective_user.id not in ADMIN_IDS:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "⛔ Only the Supreme Admins can view system statistics!"
                )
                return
            
            stats = await StatisticsManager.get_system_stats()
            revenue_analytics = await StatisticsManager.get_revenue_analytics(7)
            
            stats_text = f"""
📈 *COMPREHENSIVE SYSTEM STATISTICS* 📈

🎯 *ADVERTISEMENTS:*
▫️ Active Ads: {stats['active_ads']}
▫️ Total Ads: {stats['total_ads']}
▫️ Total Posts: {stats['total_posts']}
▫️ Posts Today: {stats['posts_today']}

💎 *VIP SYSTEM:*
▫️ Active VIPs: {stats['active_vips']}

💰 *FINANCIAL:*
▫️ Total Revenue: {stats['total_revenue']:.2f} USDT
▫️ Total Purchases: {stats['total_purchases']}
▫️ Purchases Today: {stats['purchases_today']}

👥 *MEMBERS:*
▫️ Verified Members: {stats['verified_members']}

📅 *LAST 7 DAYS REVENUE:*
"""
            
            # Add daily revenue for last 7 days
            for date, amount in revenue_analytics['daily_revenue'][:7]:
                stats_text += f"▫️ {date}: {amount or 0:.2f} USDT\n"
            
            # Add product breakdown
            stats_text += "\n🛍️ *PRODUCT BREAKDOWN:*\n"
            for product, count, amount in revenue_analytics['product_breakdown']:
                stats_text += f"▫️ {product}: {count} sales, {amount or 0:.2f} USDT\n"
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                stats_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in system_stats_command: {e}")
            await log_error("AdvertisingBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error loading system statistics. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )

    async def post_advertisement(self):
        """Background task to post advertisements with comprehensive error handling"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                # Check if paused
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    "SELECT is_paused FROM ad_config WHERE id=1"
                )
                result = await cursor.fetchone()
                if result and result[0] == 1:
                    return
                
                # Get next ad or use default
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT id, heading, type, description, contact, has_buttons, has_image, image_url 
                    FROM ads_queue 
                    WHERE status='active' AND expires_at > ? 
                    ORDER BY post_count ASC, created_at ASC 
                    LIMIT 1
                    """,
                    (datetime.now().isoformat(),)
                )
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
                    keyboard = []
                    if ad[5]:  # has_buttons
                        keyboard = [
                            [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/{AUTOADV_BOT_TOKEN.split(':')[0]}?start=buy_ad")],
                            [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{AUTOADV_BOT_TOKEN.split(':')[0]}?start=report_scammer")]
                        ]
                    
                    # Update post count
                    await ErrorHandler.handle_database_error(
                        db.execute,
                        "UPDATE ads_queue SET post_count=post_count+1 WHERE id=?",
                        (ad[0],)
                    )
                    
                    # Update statistics
                    await ConfigManager.update_statistics("ad_posted")
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
                
                # Post to Main Group and pin with error handling
                try:
                    msg = await ErrorHandler.handle_telegram_error(
                        self.app.bot.send_message,
                        chat_id=MAIN_GROUP_ID,
                        text=ad_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                    await ErrorHandler.handle_telegram_error(
                        self.app.bot.pin_chat_message,
                        chat_id=MAIN_GROUP_ID,
                        message_id=msg.message_id
                    )
                except Exception as e:
                    logger.error(f"Error posting to main group: {e}")
                    # Continue with other groups even if one fails
                
                # Post to Company Resources with error handling
                try:
                    await ErrorHandler.handle_telegram_error(
                        self.app.bot.send_message,
                        chat_id=COMPANY_RESOURCES_ID,
                        text=ad_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error posting to company resources: {e}")
                
                # Update last post time
                await ErrorHandler.handle_database_error(
                    db.execute,
                    "INSERT OR REPLACE INTO ad_config (id, last_post_time) VALUES (1, ?)",
                    (datetime.now().isoformat(),)
                )
                await ErrorHandler.handle_database_error(db.commit)
                
                logger.info("✅ Advertisement posted successfully")
        
        except Exception as e:
            logger.error(f"❌ Critical error posting advertisement: {e}")
            await log_error("AdvertisingBot", e)
    
    async def setup_scheduler(self):
        """Setup background scheduler for ad posting with error handling"""
        try:
            self.scheduler.add_job(
                self.post_advertisement,
                'interval',
                minutes=5,
                jitter=60,  # Random 0-60 second delay
                misfire_grace_time=300  # Allow 5 minutes grace period
            )
            self.scheduler.start()
            logger.info("✅ Ad scheduler started")
        except Exception as e:
            logger.error(f"❌ Error starting scheduler: {e}")
            await log_error("AdvertisingBot", e)
    
    def setup_handlers(self):
        """Setup all command handlers with error handling"""
        try:
            self.app.add_handler(CommandHandler(f"{self.prefix}_start", self.start_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_help", self.help_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_stats", self.stats_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_viewqueue", self.view_queue_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_pause", self.pause_ads_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_resume", self.resume_ads_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_config", self.config_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_admin", self.admin_panel_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_system_stats", self.system_stats_command))
            
            # Add error handler for this bot
            self.app.add_error_handler(self.error_handler)
            
        except Exception as e:
            logger.error(f"❌ Error setting up handlers: {e}")
            await log_error("AdvertisingBot", e)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in telegram handlers"""
        try:
            logger.error(f"Exception while handling an update: {context.error}")
            
            # Log the error
            user_id = update.effective_user.id if update and update.effective_user else None
            await log_error("AdvertisingBot", context.error, user_id)
            
            # Notify user if possible
            if update and hasattr(update, 'message') and update.message:
                try:
                    await ErrorHandler.safe_send_message(
                        update.message.reply_text,
                        "❌ An error occurred while processing your request. Please try again later.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass  # Ignore errors in error handling
                    
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
    
    async def run(self):
        """Run the advertising bot with comprehensive error handling"""
        try:
            self.setup_handlers()
            await self.setup_scheduler()
            
            await ErrorHandler.handle_telegram_error(self.app.initialize)
            await ErrorHandler.handle_telegram_error(self.app.start)
            await ErrorHandler.handle_telegram_error(self.app.updater.start_polling)
            logger.info("✅ Advertising Bot started and polling")
            
            # Keep the bot running forever
            await asyncio.Future()
            
        except Exception as e:
            logger.error(f"❌ Critical error in Advertising Bot: {e}")
            await log_error("AdvertisingBot", e)
            raise

# ============================
# 🤖 2. VIP BOT
# ============================

class VIPBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.trigger_words = ["direct", "company", "sbi", "accounts", "account"]
        self.prefix = VIP_PREFIX
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        try:
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "👑 *WELCOME TO THE VIP VERIFICATION SYSTEM!* 👑\n\n"
                "I am the *VIP Bot*, guardian of premium status and verifier of excellence!\n\n"
                "✨ *MY DIVINE ABILITIES:* ✨\n"
                "🔍 Instant VIP verification\n"
                "✅ Real-time status checking\n"
                "👥 Member authenticity validation\n"
                "🎫 Exclusive access management\n\n"
                "⚡ *COMMANDS FOR YOUR USE:* ⚡\n"
                f"/{self.prefix}_checkvip @username - Verify anyone's VIP status\n"
                f"/{self.prefix}_myvip - Check your own VIP status\n"
                f"/{self.prefix}_help - All available commands\n\n"
                "Your premium status awaits, O Distinguished One! 🌟",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in VIP start_command: {e}")
            await log_error("VIPBot", e, update.effective_user.id)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        try:
            is_admin = update.effective_user.id in ADMIN_IDS
            
            help_text = f"""
👑 *VIP BOT - COMMAND SANCTUARY* 👑

🎯 *VERIFICATION COMMANDS:*
/{self.prefix}_start - Begin your VIP journey
/{self.prefix}_help - Divine guidance
/{self.prefix}_checkvip @user - Verify any member
/{self.prefix}_myvip - Your VIP status
/{self.prefix}_stats - VIP statistics
/{self.prefix}_viplist - All VIP members (DM only)
/{self.prefix}_benefits - Learn VIP perks
/{self.prefix}_renew - Renew your VIP status
"""
            
            if is_admin:
                help_text += f"""
👑 *ADMIN COMMANDS (DM ONLY):*
/{self.prefix}_addvip [user_id] - Manually add VIP
/{self.prefix}_removevip [user_id] - Remove VIP status
/{self.prefix}_extendvip [user_id] [days] - Extend VIP
/{self.prefix}_analytics - Detailed analytics
/{self.prefix}_exportvips - Export VIP database
/{self.prefix}_revenue - Revenue statistics
/{self.prefix}_bulkvip - Bulk VIP operations
/{self.prefix}_logs - Activity logs
/{self.prefix}_searchvip [query] - Search VIPs
/{self.prefix}_expiringsoon - VIPs expiring soon
/{self.prefix}_renewalreminder - Send renewal reminders
/{self.prefix}_backup - Backup VIP database
/{self.prefix}_restore - Restore VIP database
/{self.prefix}_config - Bot configuration
/{self.prefix}_admin - Admin panel
/{self.prefix}_system_stats - System statistics
"""
            
            help_text += "\n💎 *Excellence recognized, premium delivered!* 💎"
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                help_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in VIP help_command: {e}")
            await log_error("VIPBot", e, update.effective_user.id)
    
    async def check_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check VIP status of mentioned user"""
        try:
            if not context.args:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    f"📝 *Usage:* `/{self.prefix}_checkvip @username`\n\n"
                    "Or reply to someone's message with `/{self.prefix}_checkvip`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Extract user ID (simplified - in production, use proper username resolution)
            username = context.args[0].replace("@", "")
            
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT name, expires_at, is_active 
                    FROM vip_members 
                    WHERE username=? AND is_active=1
                    """,
                    (username,)
                )
                vip = await cursor.fetchone()
            
            if vip:
                expires = datetime.fromisoformat(vip[1])
                if expires > datetime.now():
                    await ErrorHandler.safe_send_message(
                        update.message.reply_text,
                        f"✅ *VIP STATUS CONFIRMED!* ✅\n\n"
                        f"👤 *User:* @{username}\n"
                        f"💎 *Status:* PREMIUM VIP\n"
                        f"📅 *Valid Until:* {expires.strftime('%d/%m/%Y')}\n\n"
                        f"🌟 *This member is verified and trusted!*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await ErrorHandler.safe_send_message(
                        update.message.reply_text,
                        f"⚠️ *VIP EXPIRED* ⚠️\n\n"
                        f"@{username} was a VIP member but their subscription has expired.\n\n"
                        f"🔄 They can renew anytime!",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    f"❌ *NOT A VIP MEMBER* ❌\n\n"
                    f"@{username} is not currently a VIP member.\n\n"
                    f"💎 Want VIP benefits? Contact our AutoADV bot!",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"Error in VIP check_vip_command: {e}")
            await log_error("VIPBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error checking VIP status. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def my_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check own VIP status"""
        try:
            user_id = update.effective_user.id
            
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT name, phone, email, created_at, expires_at 
                    FROM vip_members 
                    WHERE user_id=? AND is_active=1
                    """,
                    (user_id,)
                )
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
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    status_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
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
        except Exception as e:
            logger.error(f"Error in VIP my_vip_command: {e}")
            await log_error("VIPBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error checking your VIP status. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def vip_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all VIP members (Admin only, DM only)"""
        try:
            if update.effective_chat.type != "private":
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "📬 This command works in DM only! Send me a private message."
                )
                return
            
            if update.effective_user.id not in ADMIN_IDS:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "⛔ Only Supreme Admins can access the VIP roster!"
                )
                return
            
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await ErrorHandler.handle_database_error(
                    db.execute,
                    """
                    SELECT username, name, expires_at 
                    FROM vip_members 
                    WHERE is_active=1 
                    ORDER BY expires_at DESC 
                    LIMIT 50
                    """
                )
                vips = await cursor.fetchall()
            
            if not vips:
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "📭 No VIP members found!"
                )
                return
            
            list_text = "👑 *VIP MEMBER ROSTER* 👑\n\n"
            for vip in vips:
                expires = datetime.fromisoformat(vip[2])
                days_left = (expires - datetime.now()).days
                status = "🟢" if days_left > 7 else "🟡" if days_left > 1 else "🔴"
                list_text += f"{status} @{vip[0]} ({vip[1]})\n"
                list_text += f"   ⏰ {days_left} days remaining\n\n"
            
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                list_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in VIP vip_list_command: {e}")
            await log_error("VIPBot", e, update.effective_user.id)
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "❌ Error retrieving VIP list. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )

    # ... (Continuing with other VIP bot methods with similar error handling)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in VIP bot handlers"""
        try:
            logger.error(f"Exception in VIP bot while handling an update: {context.error}")
            
            user_id = update.effective_user.id if update and update.effective_user else None
            await log_error("VIPBot", context.error, user_id)
            
            if update and hasattr(update, 'message') and update.message:
                try:
                    await ErrorHandler.safe_send_message(
                        update.message.reply_text,
                        "❌ An error occurred in VIP system. Please try again later.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in VIP error handler: {e}")
    
    def setup_handlers(self):
        """Setup all handlers with error handling"""
        try:
            self.app.add_handler(CommandHandler(f"{self.prefix}_start", self.start_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_help", self.help_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_checkvip", self.check_vip_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_myvip", self.my_vip_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_viplist", self.vip_list_command))
            # Add other command handlers...
            
            self.app.add_error_handler(self.error_handler)
            
        except Exception as e:
            logger.error(f"❌ Error setting up VIP bot handlers: {e}")
            await log_error("VIPBot", e)
    
    async def run(self):
        """Run the VIP bot with comprehensive error handling"""
        try:
            self.setup_handlers()
            
            await ErrorHandler.handle_telegram_error(self.app.initialize)
            await ErrorHandler.handle_telegram_error(self.app.start)
            await ErrorHandler.handle_telegram_error(self.app.updater.start_polling)
            logger.info("✅ VIP Bot started and polling")
            
            await asyncio.Future()
            
        except Exception as e:
            logger.error(f"❌ Critical error in VIP Bot: {e}")
            await log_error("VIPBot", e)
            raise

# ============================
# 🤖 3. GROUP MANAGEMENT BOT
# ============================

class GroupManagementBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.pending_verifications = {}
        self.prefix = GROUP_PREFIX
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        try:
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                "🛡️ *GUARDIAN OF THE REALM AWAKENS!* 🛡️\n\n"
                "I am the *Group Management Bot*, protector of order and enforcer of harmony!\n\n"
                "⚔️ *MY SACRED DUTIES:* ⚔️\n"
                "🚫 Spam elimination\n"
                "✅ Member verification\n"
                "📏 Message length control\n"
                "👥 Access management\n\n"
                "⚡ *COMMANDS TO COMMAND ME:* ⚡\n"
                f"/{self.prefix}_help - View all commands\n"
                f"/{self.prefix}_verify - Verify your membership\n"
                f"/{self.prefix}_rules - See group rules\n\n"
                "Order shall be maintained, Noble One! 🗡️",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in GroupManagement start_command: {e}")
            await log_error("GroupManagementBot", e, update.effective_user.id)

    # ... (Implement all Group Management Bot methods with similar error handling pattern)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in group management bot"""
        try:
            logger.error(f"Exception in Group Management bot: {context.error}")
            
            user_id = update.effective_user.id if update and update.effective_user else None
            await log_error("GroupManagementBot", context.error, user_id)
            
            if update and hasattr(update, 'message') and update.message:
                try:
                    await ErrorHandler.safe_send_message(
                        update.message.reply_text,
                        "❌ An error occurred in group management. Please try again.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in Group Management error handler: {e}")
    
    def setup_handlers(self):
        """Setup all handlers with error handling"""
        try:
            self.app.add_handler(CommandHandler(f"{self.prefix}_start", self.start_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_help", self.help_command))
            # Add other command handlers...
            
            self.app.add_error_handler(self.error_handler)
            
        except Exception as e:
            logger.error(f"❌ Error setting up Group Management bot handlers: {e}")
            await log_error("GroupManagementBot", e)
    
    async def run(self):
        """Run the group management bot with comprehensive error handling"""
        try:
            self.setup_handlers()
            
            await ErrorHandler.handle_telegram_error(self.app.initialize)
            await ErrorHandler.handle_telegram_error(self.app.start)
            await ErrorHandler.handle_telegram_error(self.app.updater.start_polling)
            logger.info("✅ Group Management Bot started and polling")
            
            await asyncio.Future()
            
        except Exception as e:
            logger.error(f"❌ Critical error in Group Management Bot: {e}")
            await log_error("GroupManagementBot", e)
            raise

# ============================
# 🤖 4. AUTO ADV BOT
# ============================

class AutoADVBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.user_states = {}  # Track conversation states
        self.prefix = AUTOADV_PREFIX
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with product selection"""
        try:
            if update.effective_chat.type != "private":
                # In group, send DM notification
                await ErrorHandler.safe_send_message(
                    update.message.reply_text,
                    "📬 *I've sent you a private message!*\n\n"
                    "Please check your direct messages to continue securely! 🔒",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Delete messages after 60 seconds with error handling
                try:
                    context.job_queue.run_once(
                        lambda ctx: update.message.delete(),
                        60
                    )
                except Exception as e:
                    logger.warning(f"Could not schedule message deletion: {e}")
                
                # Send DM directly
                try:
                    start_message = self.get_start_message()
                    await ErrorHandler.safe_send_message(
                        context.bot.send_message,
                        chat_id=update.effective_user.id,
                        text=start_message['text'],
                        reply_markup=start_message['reply_markup'],
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"Error sending DM: {e}")
                    # If bot can't send DM, provide a direct link
                    bot_username = (await self.app.bot.get_me()).username
                    await ErrorHandler.safe_send_message(
                        update.message.reply_text,
                        f"❌ *I couldn't send you a DM!*\n\n"
                        f"Please start a conversation with me first:\n"
                        f"👉 [Click here to start](https://t.me/{bot_username}?start=start)\n\n"
                        f"Then try the command again!",
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True
                    )
                return
            
            start_message = self.get_start_message()
            await ErrorHandler.safe_send_message(
                update.message.reply_text,
                start_message['text'],
                reply_markup=start_message['reply_markup'],
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in AutoADV start_command: {e}")
            await log_error("AutoADVBot", e, update.effective_user.id)

    # ... (Implement all AutoADV Bot methods with similar comprehensive error handling)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in AutoADV bot"""
        try:
            logger.error(f"Exception in AutoADV bot: {context.error}")
            
            user_id = update.effective_user.id if update and update.effective_user else None
            await log_error("AutoADVBot", context.error, user_id)
            
            if update and hasattr(update, 'message') and update.message:
                try:
                    await ErrorHandler.safe_send_message(
                        update.message.reply_text,
                        "❌ An error occurred in payment processing. Please try again.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in AutoADV error handler: {e}")
    
    def setup_handlers(self):
        """Setup all handlers with error handling"""
        try:
            self.app.add_handler(CommandHandler(f"{self.prefix}_start", self.start_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_help", self.help_command))
            # Add other command handlers...
            
            self.app.add_error_handler(self.error_handler)
            
        except Exception as e:
            logger.error(f"❌ Error setting up AutoADV bot handlers: {e}")
            await log_error("AutoADVBot", e)
    
    async def run(self):
        """Run the auto ADV bot with comprehensive error handling"""
        try:
            self.setup_handlers()
            
            await ErrorHandler.handle_telegram_error(self.app.initialize)
            await ErrorHandler.handle_telegram_error(self.app.start)
            await ErrorHandler.handle_telegram_error(self.app.updater.start_polling)
            logger.info("✅ Auto ADV Bot started and polling")
            
            await asyncio.Future()
            
        except Exception as e:
            logger.error(f"❌ Critical error in Auto ADV Bot: {e}")
            await log_error("AutoADVBot", e)
            raise

# ============================
# 🚀 MAIN EXECUTION
# ============================

async def main():
    """Initialize and run all bots concurrently with comprehensive error handling"""
    logger.info("🚀 Starting Interlink Multi-Bot System...")
    
    try:
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
        
        # Run all bots concurrently with error handling
        tasks = [
            asyncio.create_task(adv_bot.run()),
            asyncio.create_task(vip_bot.run()),
            asyncio.create_task(group_bot.run()),
            asyncio.create_task(autoadv_bot.run())
        ]
        
        # Wait for all tasks with proper error handling
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        
        # Check for exceptions
        for task in done:
            if task.exception():
                logger.error(f"Bot task failed: {task.exception()}")
                # Cancel pending tasks
                for pending_task in pending:
                    pending_task.cancel()
                raise task.exception()
                
    except Exception as e:
        logger.error(f"❌ Critical error in main execution: {e}")
        logger.error(traceback.format_exc())
        raise

async def graceful_shutdown():
    """Gracefully shutdown all bots"""
    logger.info("🛑 Initiating graceful shutdown...")
    # Add any cleanup logic here
    logger.info("✅ Shutdown complete")

if __name__ == "__main__":
    """Entry point with comprehensive error handling"""
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
    ║  Version: 1.1.0                                          ║
    ║  Payment Mode: {mode}                                    ║
    ║  Enhanced with Comprehensive Error Handling              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """.format(mode=PAYMENT_MODE.upper()))
    
    # Run the main function with error handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bots stopped by user")
        asyncio.run(graceful_shutdown())
    except Exception as e:
        print(f"\n💥 Critical system error: {e}")
        logger.critical(f"System crash: {e}")
        logger.critical(traceback.format_exc())
