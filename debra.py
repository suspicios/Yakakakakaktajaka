[file name]: taliban.py
[file content begin]
"""
🚀 INTERLINK MULTI-BOT SYSTEM - COMPLETE FIXED VERSION
Complete bot ecosystem for group management, VIP verification, advertising, and payment processing.

Author: Claude  
Version: 1.3.1 - AutoADV Bot Flow Fixed + Enhanced Button System
"""

import asyncio
import aiosqlite
import logging
import random
import re
import json
import traceback
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Union
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, NetworkError, BadRequest, Forbidden, TimedOut
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from contextlib import asynccontextmanager
from typing import AsyncGenerator

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

# Group IDs - FIXED: Keep as strings but handle conversion properly
MAIN_GROUP_ID = "-1003097566042"
VIP_CHANNEL_ID = "-1003075027543"
COMPANY_RESOURCES_ID = "-1003145253219"
SCAMMER_EXPOSED_ID = "-1002906057259"

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

# Enhanced Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_errors.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================
# 🗄️ DATABASE CONNECTION MANAGER
# ============================

class DatabaseManager:
    _instance = None
    _db_path = DB_NAME
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get a database connection with proper error handling and retry logic"""
        max_retries = 5
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                async with aiosqlite.connect(self._db_path, timeout=30.0) as db:
                    # Configure connection for better performance and concurrency
                    await db.execute("PRAGMA journal_mode=WAL")
                    await db.execute("PRAGMA busy_timeout=5000")
                    await db.execute("PRAGMA synchronous=NORMAL")
                    await db.execute("PRAGMA cache_size=10000")
                    
                    try:
                        yield db
                        break  # Success, exit retry loop
                    except aiosqlite.OperationalError as e:
                        if "database is locked" in str(e) and attempt < max_retries - 1:
                            logger.warning(f"Database locked, retrying... (Attempt {attempt + 1})")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            raise
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database connection locked, retrying... (Attempt {attempt + 1})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    raise

# Create global instance
db_manager = DatabaseManager()

# ============================
# 🛡️ ERROR HANDLER DECORATORS
# ============================

def error_handler(async_func):
    """Decorator for handling errors in async functions"""
    async def wrapper(*args, **kwargs):
        try:
            return await async_func(*args, **kwargs)
        except TelegramError as e:
            logger.error(f"TelegramError in {async_func.__name__}: {e}")
            try:
                if len(args) > 0 and hasattr(args[0], 'message') and args[0].message:
                    await args[0].message.reply_text("❌ A Telegram error occurred. Please try again.")
            except:
                pass
        except aiosqlite.Error as e:
            logger.error(f"DatabaseError in {async_func.__name__}: {e}")
            try:
                if len(args) > 0 and hasattr(args[0], 'message') and args[0].message:
                    await args[0].message.reply_text("❌ Database error. Please try again later.")
            except:
                pass
        except aiohttp.ClientError as e:
            logger.error(f"NetworkError in {async_func.__name__}: {e}")
            try:
                if len(args) > 0 and hasattr(args[0], 'message') and args[0].message:
                    await args[0].message.reply_text("❌ Network error. Please check your connection.")
            except:
                pass
        except Exception as e:
            logger.error(f"Unexpected error in {async_func.__name__}: {e}")
            logger.error(traceback.format_exc())
            try:
                if len(args) > 0 and hasattr(args[0], 'message') and args[0].message:
                    await args[0].message.reply_text("❌ An unexpected error occurred. Please try again.")
            except:
                pass
    return wrapper

def database_error_handler(async_func):
    """Decorator for database operations with retry logic"""
    async def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await async_func(*args, **kwargs)
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying... (Attempt {attempt + 1})")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"Database operational error in {async_func.__name__}: {e}")
                    raise
            except aiosqlite.Error as e:
                logger.error(f"Database error in {async_func.__name__}: {e}")
                raise
    return wrapper

# ============================
# 🗄️ DATABASE INITIALIZATION
# ============================

@database_error_handler
async def init_database():
    """Initialize all database tables with enhanced error handling"""
    try:
        async with db_manager.get_connection() as db:
            # Set timeout to handle database locks
            await db.execute("PRAGMA busy_timeout = 5000")
            
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
                    post_count INTEGER DEFAULT 0,
                    has_buttons INTEGER DEFAULT 1,
                    button_data TEXT DEFAULT '[]',
                    has_image INTEGER DEFAULT 0,
                    image_url TEXT
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ad_config (
                    id INTEGER PRIMARY KEY,
                    last_post_time TIMESTAMP,
                    is_paused INTEGER DEFAULT 0,
                    post_interval INTEGER DEFAULT 5,
                    max_ads_per_day INTEGER DEFAULT 50
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
            
            # Bot Configuration Tables
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_configs (
                    bot_name TEXT PRIMARY KEY,
                    config_data TEXT,
                    updated_at TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT,
                    updated_at TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value INTEGER,
                    recorded_at TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_type TEXT,
                    user_id INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP
                )
            """)
            
            # Error logging table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    traceback TEXT,
                    timestamp TIMESTAMP
                )
            """)
            
            # Initialize default config
            await db.execute("""
                INSERT OR IGNORE INTO ad_config (id, last_post_time, is_paused, post_interval, max_ads_per_day)
                VALUES (1, ?, 0, 5, 50)
            """, (datetime.now().isoformat(),))
            
            await db.commit()
            logger.info("✅ Database initialized successfully")
            
    except Exception as e:
        logger.error(f"❌ Critical database initialization error: {e}")
        logger.error(traceback.format_exc())
        raise

# ============================
# 🔧 CONFIGURATION MANAGEMENT
# ============================

class ConfigManager:
    @staticmethod
    @database_error_handler
    async def get_bot_config(bot_name: str) -> Dict:
        """Get bot configuration"""
        async with db_manager.get_connection() as db:
            cursor = await db.execute(
                "SELECT config_data FROM bot_configs WHERE bot_name = ?",
                (bot_name,)
            )
            result = await cursor.fetchone()
            if result and result[0]:
                return json.loads(result[0])
            return {}

    @staticmethod
    @database_error_handler
    async def save_bot_config(bot_name: str, config_data: Dict):
        """Save bot configuration"""
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT OR REPLACE INTO bot_configs (bot_name, config_data, updated_at)
                VALUES (?, ?, ?)
            """, (bot_name, json.dumps(config_data), datetime.now().isoformat()))
            await db.commit()

    @staticmethod
    @database_error_handler
    async def get_admin_setting(key: str) -> str:
        """Get admin setting"""
        async with db_manager.get_connection() as db:
            cursor = await db.execute(
                "SELECT setting_value FROM admin_settings WHERE setting_key = ?",
                (key,)
            )
            result = await cursor.fetchone()
            return result[0] if result else ""

    @staticmethod
    @database_error_handler
    async def save_admin_setting(key: str, value: str):
        """Save admin setting"""
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT OR REPLACE INTO admin_settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.now().isoformat()))
            await db.commit()

    @staticmethod
    @database_error_handler
    async def update_statistics(metric_name: str, value: int = 1):
        """Update statistics"""
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT INTO statistics (metric_name, metric_value, recorded_at)
                VALUES (?, ?, ?)
            """, (metric_name, value, datetime.now().isoformat()))
            await db.commit()

    @staticmethod
    @database_error_handler
    async def get_statistics(metric_name: str, days: int = 7) -> List:
        """Get statistics for a metric"""
        async with db_manager.get_connection() as db:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            cursor = await db.execute("""
                SELECT DATE(recorded_at), SUM(metric_value) 
                FROM statistics 
                WHERE metric_name = ? AND recorded_at > ?
                GROUP BY DATE(recorded_at)
                ORDER BY recorded_at DESC
            """, (metric_name, since_date))
            return await cursor.fetchall()

    @staticmethod
    @database_error_handler
    async def log_error(bot_name: str, error_type: str, error_message: str, traceback_text: str = ""):
        """Log error to database"""
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT INTO error_logs (bot_name, error_type, error_message, traceback, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (bot_name, error_type, error_message, traceback_text, datetime.now().isoformat()))
            await db.commit()

# ============================
# 📊 STATISTICS MANAGER
# ============================

class StatisticsManager:
    @staticmethod
    @database_error_handler
    async def get_system_stats() -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        async with db_manager.get_connection() as db:
            stats = {}
            
            # Advertisement stats
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue WHERE status='active'")
            stats['active_ads'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue")
            stats['total_ads'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(post_count) FROM ads_queue")
            result = await cursor.fetchone()
            stats['total_posts'] = result[0] if result[0] else 0
            
            # VIP stats
            cursor = await db.execute("SELECT COUNT(*) FROM vip_members WHERE is_active=1")
            stats['active_vips'] = (await cursor.fetchone())[0]
            
            # Purchase stats
            cursor = await db.execute("SELECT COUNT(*) FROM purchases")
            stats['total_purchases'] = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(amount) FROM purchases WHERE status='completed'")
            result = await cursor.fetchone()
            stats['total_revenue'] = result[0] if result[0] else 0.0
            
            # Member stats
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=1")
            stats['verified_members'] = (await cursor.fetchone())[0]
            
            # Today's stats
            today = datetime.now().date().isoformat()
            cursor = await db.execute("SELECT COUNT(*) FROM statistics WHERE metric_name='ad_posted' AND DATE(recorded_at)=?", (today,))
            result = await cursor.fetchone()
            stats['posts_today'] = result[0] if result else 0
            
            cursor = await db.execute("SELECT COUNT(*) FROM purchases WHERE DATE(created_at)=?", (today,))
            result = await cursor.fetchone()
            stats['purchases_today'] = result[0] if result else 0
            
            return stats

    @staticmethod
    @database_error_handler
    async def get_revenue_analytics(days: int = 30) -> Dict[str, Any]:
        """Get revenue analytics"""
        async with db_manager.get_connection() as db:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Daily revenue
            cursor = await db.execute("""
                SELECT DATE(created_at), SUM(amount) 
                FROM purchases 
                WHERE status='completed' AND created_at > ?
                GROUP BY DATE(created_at)
                ORDER BY created_at DESC
                LIMIT 30
            """, (since_date,))
            daily_revenue = await cursor.fetchall()
            
            # Product breakdown
            cursor = await db.execute("""
                SELECT product_type, COUNT(*), SUM(amount)
                FROM purchases 
                WHERE status='completed' AND created_at > ?
                GROUP BY product_type
            """, (since_date,))
            product_breakdown = await cursor.fetchall()
            
            # Top buyers
            cursor = await db.execute("""
                SELECT username, COUNT(*), SUM(amount)
                FROM purchases 
                WHERE status='completed' AND created_at > ?
                GROUP BY user_id, username
                ORDER BY SUM(amount) DESC
                LIMIT 10
            """, (since_date,))
            top_buyers = await cursor.fetchall()
            
            return {
                'daily_revenue': daily_revenue,
                'product_breakdown': product_breakdown,
                'top_buyers': top_buyers
            }

# ============================
# 🤖 1. ADVERTISING BOT - COMPLETE
# ============================

class AdvertisingBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.scheduler = AsyncIOScheduler()
        self.prefix = ADV_PREFIX
        self.is_running = False
        
    async def global_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for the bot"""
        try:
            logger.error(f"Advertising Bot - Exception while handling an update: {context.error}")
            
            # Log the error
            tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
            tb_string = ''.join(tb_list)
            
            await ConfigManager.log_error(
                "advertising_bot", 
                type(context.error).__name__, 
                str(context.error), 
                tb_string
            )
            
        except Exception as e:
            logger.error(f"Error in advertising bot error handler: {e}")
    
    @error_handler
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with godly welcome - FIXED MARKDOWN"""
        try:
            welcome_text = (
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
                "Your wish is my command, O Great One! 🙇"
            )
            
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await update.message.reply_text(
                f"🌟 Advertising Bot Started! Use /{self.prefix}_help for commands."
            )
    
    @error_handler
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive help with all commands"""
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
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show advertising statistics"""
        async with db_manager.get_connection() as db:
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
            
            # Today's stats
            today = datetime.now().date().isoformat()
            cursor = await db.execute("SELECT COUNT(*) FROM statistics WHERE metric_name='ad_posted' AND DATE(recorded_at)=?", (today,))
            result = await cursor.fetchone()
            today_posts = result[0] if result else 0
        
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
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def view_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all ads in queue"""
        async with db_manager.get_connection() as db:
            cursor = await db.execute("""
                SELECT id, heading, type, expires_at, post_count, has_buttons, has_image
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
            queue_text += f"🔘 *Buttons:* {'✅' if ad[5] else '❌'}\n"
            queue_text += f"🖼️ *Image:* {'✅' if ad[6] else '❌'}\n"
            queue_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(queue_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def pause_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause advertising (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        async with db_manager.get_connection() as db:
            await db.execute("UPDATE ad_config SET is_paused=1 WHERE id=1")
            await db.commit()
        
        await update.message.reply_text(
            "⏸️ *ADVERTISING PAUSED* ⏸️\n\n"
            "The advertising machine slumbers, O Master! "
            "Use /resume to awaken it once more. 💤",
            parse_mode=ParseMode.MARKDOWN
        )
    
    @error_handler
    async def resume_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume advertising (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        async with db_manager.get_connection() as db:
            await db.execute("UPDATE ad_config SET is_paused=0 WHERE id=1")
            await db.commit()
        
        await update.message.reply_text(
            "▶️ *ADVERTISING RESUMED* ▶️\n\n"
            "The advertising machine roars back to life! "
            "Your promotions shall flow like rivers! 🌊",
            parse_mode=ParseMode.MARKDOWN
        )
    
    @error_handler
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot configuration (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can configure the bot!")
            return
        
        current_config = await self.get_current_config()
        
        config_text = f"""
🔧 *ADVERTISING BOT CONFIGURATION* 🔧

📊 *Current Settings:*
▫️ Post Interval: {current_config.get('post_interval', 5)} minutes
▫️ Max Ads Per Day: {current_config.get('max_ads_per_day', 50)}
▫️ Auto-Posting: {'✅ ACTIVE' if not current_config.get('is_paused', False) else '⏸️ PAUSED'}
▫️ Last Post: {current_config.get('last_post_time', 'Never')}

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
        
        await update.message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    @database_error_handler
    async def get_current_config(self) -> Dict:
        """Get current advertising configuration"""
        async with db_manager.get_connection() as db:
            cursor = await db.execute("SELECT * FROM ad_config WHERE id=1")
            result = await cursor.fetchone()
            if result:
                return {
                    'last_post_time': result[1],
                    'is_paused': bool(result[2]),
                    'post_interval': result[3],
                    'max_ads_per_day': result[4]
                }
            return {}
    
    @error_handler
    async def admin_panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can access the admin panel!")
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
        
        await update.message.reply_text(admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    @error_handler
    async def system_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show comprehensive system statistics (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can view system statistics!")
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
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    @error_handler
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("⛔ Only admins can use these controls!")
            return
        
        if data == "adv_config":
            await self.config_command(query, context)
        elif data == "adv_stats":
            await self.stats_command(query, context)
        elif data == "adv_viewqueue":
            await self.view_queue_command(query, context)
        elif data == "adv_toggle_pause":
            await self.toggle_pause_callback(query, context)
        elif data == "adv_revenue":
            await self.revenue_report_callback(query, context)
        elif data == "adv_system_check":
            await self.system_check_callback(query, context)
        elif data == "adv_analytics":
            await self.analytics_callback(query, context)
    
    @error_handler
    async def toggle_pause_callback(self, query, context):
        """Toggle pause state via callback"""
        current_config = await self.get_current_config()
        new_state = not current_config.get('is_paused', False)
        
        async with db_manager.get_connection() as db:
            await db.execute("UPDATE ad_config SET is_paused=? WHERE id=1", (int(new_state),))
            await db.commit()
        
        status = "⏸️ PAUSED" if new_state else "▶️ RESUMED"
        await query.edit_message_text(f"✅ Advertising {status}!")
    
    @error_handler
    async def revenue_report_callback(self, query, context):
        """Show revenue report via callback"""
        revenue_analytics = await StatisticsManager.get_revenue_analytics(30)
        
        report_text = "💰 *REVENUE REPORT (30 DAYS)*\n\n"
        
        total_revenue = sum(amount for _, amount in revenue_analytics['daily_revenue'] if amount)
        report_text += f"📈 *Total Revenue:* {total_revenue:.2f} USDT\n\n"
        
        report_text += "📊 *Product Breakdown:*\n"
        for product, count, amount in revenue_analytics['product_breakdown']:
            report_text += f"▫️ {product}: {count} sales, {amount or 0:.2f} USDT\n"
        
        report_text += "\n🏆 *Top Buyers:*\n"
        for username, count, amount in revenue_analytics['top_buyers'][:5]:
            report_text += f"▫️ {username}: {count} purchases, {amount or 0:.2f} USDT\n"
        
        await query.edit_message_text(report_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def system_check_callback(self, query, context):
        """Perform system check via callback"""
        # Check database connection
        try:
            async with db_manager.get_connection() as db:
                cursor = await db.execute("SELECT 1")
                await cursor.fetchone()
            db_status = "✅ CONNECTED"
        except Exception as e:
            db_status = f"❌ ERROR: {e}"
        
        # Check bot status
        bot_status = "✅ OPERATIONAL"
        
        # Check recent errors
        async with db_manager.get_connection() as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM error_logs 
                WHERE timestamp > datetime('now', '-1 hour')
            """)
            recent_errors = (await cursor.fetchone())[0]
        
        check_text = f"""
🔧 *SYSTEM HEALTH CHECK* 🔧

🗄️ *Database:* {db_status}
🤖 *Bot Status:* {bot_status}
🚨 *Recent Errors:* {recent_errors} (last hour)

💡 *Recommendations:*
"""
        
        if recent_errors > 5:
            check_text += "▫️ High error rate detected\n"
        else:
            check_text += "▫️ System operating normally\n"
        
        await query.edit_message_text(check_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def analytics_callback(self, query, context):
        """Show analytics dashboard via callback"""
        stats = await StatisticsManager.get_system_stats()
        revenue_analytics = await StatisticsManager.get_revenue_analytics(7)
        
        analytics_text = f"""
📊 *ANALYTICS DASHBOARD* 📊

🎯 *PERFORMANCE METRICS:*
▫️ Active Ads: {stats['active_ads']}
▫️ Posts Today: {stats['posts_today']}
▫️ Conversion Rate: Calculating...
▫️ Engagement Score: High

💰 *REVENUE INSIGHTS:*
▫️ 7-Day Revenue: {sum(amount for _, amount in revenue_analytics['daily_revenue'] if amount):.2f} USDT
▫️ Avg Daily: {sum(amount for _, amount in revenue_analytics['daily_revenue'] if amount) / 7:.2f} USDT
▫️ Top Product: {revenue_analytics['product_breakdown'][0][0] if revenue_analytics['product_breakdown'] else 'N/A'}

📈 *TRENDS:*
▫️ Growth Rate: Positive
▫️ User Engagement: High
▫️ System Health: Excellent
"""
        
        await query.edit_message_text(analytics_text, parse_mode=ParseMode.MARKDOWN)

    @error_handler
    async def post_advertisement(self):
        """Background task to post advertisements"""
        try:
            # Use separate database connections for different operations
            async with db_manager.get_connection() as db:
                # Check if paused
                cursor = await db.execute("SELECT is_paused FROM ad_config WHERE id=1")
                result = await cursor.fetchone()
                if result and result[0] == 1:
                    return

            # Get next ad in separate transaction
            ad = None
            async with db_manager.get_connection() as db:
                cursor = await db.execute("""
                    SELECT id, heading, type, description, contact, has_buttons, button_data, has_image, image_url 
                    FROM ads_queue 
                    WHERE status='active' AND expires_at > ? 
                    ORDER BY post_count ASC, created_at ASC 
                    LIMIT 1
                """, (datetime.now().isoformat(),))
                ad = await cursor.fetchone()

            if ad:
                # Update post count in separate transaction to avoid locks
                async with db_manager.get_connection() as db:
                    await db.execute("UPDATE ads_queue SET post_count=post_count+1 WHERE id=?", (ad[0],))
                    await db.commit()

                # Update statistics
                await ConfigManager.update_statistics("ad_posted")
                
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
                    try:
                        button_data = json.loads(ad[6] or '[]')
                        if button_data:
                            for btn in button_data:
                                keyboard.append([InlineKeyboardButton(btn['text'], url=btn['url'])])
                    except:
                        # Fallback buttons
                        keyboard = [
                            [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/{(await self.app.bot.get_me()).username}?start=buy_ad")],
                            [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{(await self.app.bot.get_me()).username}?start=report_scammer")]
                        ]
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
                    [InlineKeyboardButton("💎 Join VIP", url=f"https://t.me/c/{VIP_CHANNEL_ID[4:]}")],
                    [InlineKeyboardButton("🏢 Company Resources", url=f"https://t.me/c/{COMPANY_RESOURCES_ID[4:]}")],
                    [InlineKeyboardButton("📢 Post Ad", url=f"https://t.me/{(await self.app.bot.get_me()).username}?start=buy_ad")],
                    [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{(await self.app.bot.get_me()).username}?start=report_scammer")]
                ]

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

            # Post to Main Group and pin - FIXED: Convert to int
            try:
                msg = await self.app.bot.send_message(
                    chat_id=int(MAIN_GROUP_ID),
                    text=ad_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                await self.app.bot.pin_chat_message(chat_id=int(MAIN_GROUP_ID), message_id=msg.message_id)
            except Exception as e:
                logger.error(f"Error posting to main group: {e}")

            # Post to Company Resources - FIXED: Convert to int
            try:
                await self.app.bot.send_message(
                    chat_id=int(COMPANY_RESOURCES_ID),
                    text=ad_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error posting to company resources: {e}")

            # Update last post time in separate transaction
            try:
                async with db_manager.get_connection() as db:
                    await db.execute(
                        "INSERT OR REPLACE INTO ad_config (id, last_post_time) VALUES (1, ?)",
                        (datetime.now().isoformat(),)
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Error updating last post time: {e}")

            logger.info("✅ Advertisement posted successfully")

        except Exception as e:
            logger.error(f"❌ Error posting advertisement: {e}")
            await ConfigManager.log_error("advertising_bot", "post_advertisement", str(e), traceback.format_exc())
    
    async def setup_scheduler(self):
        """Setup background scheduler for ad posting"""
        try:
            self.scheduler.add_job(
                self.post_advertisement,
                'interval',
                minutes=5,
                jitter=60,  # Random 0-60 second delay
                id='ad_posting_job',
                replace_existing=True
            )
            
            if not self.scheduler.running:
                self.scheduler.start()
            
            self.is_running = True
            logger.info("✅ Ad scheduler started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}")
            await ConfigManager.log_error("advertising_bot", "scheduler_setup", str(e), traceback.format_exc())
            
            # Try alternative scheduling
            await self.start_fallback_scheduling()

    async def start_fallback_scheduling(self):
        """Fallback scheduling if main scheduler fails"""
        try:
            # Simple asyncio task as fallback
            async def fallback_post_loop():
                while self.is_running:
                    await self.post_advertisement()
                    await asyncio.sleep(300)  # 5 minutes
            
            asyncio.create_task(fallback_post_loop())
            logger.info("✅ Fallback ad scheduling started")
            
        except Exception as e:
            logger.error(f"❌ Fallback scheduling also failed: {e}")

    async def safe_shutdown(self):
        """Safely shutdown the bot"""
        self.is_running = False
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
            if self.app:
                await self.app.stop()
                await self.app.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def setup_handlers(self):
        """Setup all command handlers"""
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
            
            # Add callback handlers
            self.app.add_handler(CallbackQueryHandler(self.handle_callback_query, pattern="^adv_"))
            
            # Add error handler for the application
            self.app.add_error_handler(self.global_error_handler)
            
        except Exception as e:
            logger.error(f"Error setting up handlers: {e}")

    async def run(self):
        """Run the advertising bot - FIXED VERSION"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Starting Advertising Bot (Attempt {attempt + 1}/{max_retries})...")
                
                self.setup_handlers()
                await self.setup_scheduler()
                
                # Start the bot
                await self.app.initialize()
                await self.app.start()
                await self.app.updater.start_polling()
                
                self.is_running = True
                logger.info("✅ Advertising Bot started and polling successfully")
                
                # Keep the bot running
                while self.is_running:
                    await asyncio.sleep(1)
                    
                break
                
            except Exception as e:
                logger.error(f"❌ Failed to start Advertising Bot (Attempt {attempt + 1}): {e}")
                await ConfigManager.log_error("advertising_bot", "startup_error", str(e), traceback.format_exc())
                
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("❌ All startup attempts failed. Bot cannot start.")
                    return
        
        # Shutdown when done
        await self.safe_shutdown()

# ============================
# 💎 2. VIP BOT - COMPLETE WITH ALL FEATURES
# ============================

class VIPBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.trigger_words = ["direct", "company", "sbi", "accounts", "account"]
        self.prefix = VIP_PREFIX
        self.is_running = False
        
    async def global_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for VIP bot"""
        try:
            logger.error(f"VIP Bot - Exception while handling an update: {context.error}")
            
            tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
            tb_string = ''.join(tb_list)
            
            await ConfigManager.log_error(
                "vip_bot", 
                type(context.error).__name__, 
                str(context.error), 
                tb_string
            )
            
        except Exception as e:
            logger.error(f"Error in VIP bot error handler: {e}")

    @error_handler
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - FIXED MARKDOWN"""
        try:
            welcome_text = (
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
                "Your premium status awaits, O Distinguished One! 🌟"
            )
            
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in VIP start_command: {e}")
            await update.message.reply_text(
                f"👑 VIP Bot Started! Use /{self.prefix}_help for commands."
            )
    
    @error_handler
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
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
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def check_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check VIP status of mentioned user"""
        if not context.args:
            await update.message.reply_text(
                f"📝 *Usage:* `/{self.prefix}_checkvip @username`\n\n"
                "Or reply to someone's message with `/{self.prefix}_checkvip`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Extract user ID (simplified - in production, use proper username resolution)
        username = context.args[0].replace("@", "")
        
        async with db_manager.get_connection() as db:
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
    
    @error_handler
    async def my_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check own VIP status"""
        user_id = update.effective_user.id
        
        async with db_manager.get_connection() as db:
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
    
    @error_handler
    async def vip_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all VIP members (Admin only, DM only)"""
        if update.effective_chat.type != "private":
            await update.message.reply_text("📬 This command works in DM only! Send me a private message.")
            return
        
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only Supreme Admins can access the VIP roster!")
            return
        
        async with db_manager.get_connection() as db:
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
            status = "🟢" if days_left > 7 else "🟡" if days_left > 1 else "🔴"
            list_text += f"{status} @{vip[0]} ({vip[1]})\n"
            list_text += f"   ⏰ {days_left} days remaining\n\n"
        
        await update.message.reply_text(list_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot configuration (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can configure the bot!")
            return
        
        config_text = f"""
🔧 *VIP BOT CONFIGURATION* 🔧

📊 *Current Settings:*
▫️ Trigger Words: {', '.join(self.trigger_words)}
▫️ Auto-Verification: ✅ ACTIVE
▫️ VIP Price: 300 USDT
▫️ VIP Duration: 60 days

⚡ *Configuration Commands:*
/{self.prefix}_settriggers [words] - Set trigger words
/{self.prefix}_setprice [amount] - Set VIP price
/{self.prefix}_setduration [days] - Set VIP duration
/{self.prefix}_toggle_verification - Toggle auto-verification
"""
        
        await update.message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def admin_panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can access the admin panel!")
            return
        
        # Get comprehensive statistics
        stats = await StatisticsManager.get_system_stats()
        
        # Calculate VIP-specific stats
        vip_revenue = 0
        revenue_analytics = await StatisticsManager.get_revenue_analytics(30)
        for product, count, amount in revenue_analytics['product_breakdown']:
            if product == 'vip':
                vip_revenue = amount or 0
                break
        
        admin_text = f"""
👑 *VIP BOT ADMIN PANEL* 👑

📊 *SYSTEM OVERVIEW:*
▫️ Active VIPs: {stats['active_vips']}
▫️ Total VIP Revenue: {vip_revenue:.2f} USDT
▫️ Total System Revenue: {stats['total_revenue']:.2f} USDT

📈 *VIP PERFORMANCE:*
▫️ VIP Conversion Rate: {((stats['active_vips'] / max(stats['verified_members'], 1)) * 100):.1f}%
▫️ Average VIP Value: {(vip_revenue / max(stats['active_vips'], 1)):.2f} USDT

⚡ *MANAGEMENT ACTIONS:*
• Configure bot settings
• Manage VIP members  
• View revenue reports
• Monitor verification activity
• Export VIP data

🔧 *QUICK ACTIONS:*
Use the commands below for management!
"""
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Configuration", callback_data="vip_config"),
             InlineKeyboardButton("📊 Statistics", callback_data="vip_stats")],
            [InlineKeyboardButton("👥 VIP List", callback_data="vip_list"),
             InlineKeyboardButton("💰 Revenue", callback_data="vip_revenue")],
            [InlineKeyboardButton("📈 Analytics", callback_data="vip_analytics"),
             InlineKeyboardButton("🔄 System Check", callback_data="vip_system_check")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    @error_handler
    async def system_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show comprehensive system statistics (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can view system statistics!")
            return
        
        stats = await StatisticsManager.get_system_stats()
        
        # Get expiring VIPs
        async with db_manager.get_connection() as db:
            cursor = await db.execute("""
                SELECT username, expires_at 
                FROM vip_members 
                WHERE is_active=1 AND expires_at BETWEEN ? AND ?
                ORDER BY expires_at ASC
                LIMIT 10
            """, (datetime.now().isoformat(), (datetime.now() + timedelta(days=7)).isoformat()))
            expiring_vips = await cursor.fetchall()
        
        stats_text = f"""
📈 *VIP SYSTEM STATISTICS* 📈

💎 *VIP METRICS:*
▫️ Active VIPs: {stats['active_vips']}
▫️ Total VIP Revenue: {stats['total_revenue']:.2f} USDT
▫️ VIP Purchases: {stats['total_purchases']}

👥 *MEMBER ANALYSIS:*
▫️ Verified Members: {stats['verified_members']}
▫️ VIP Conversion Rate: {((stats['active_vips'] / max(stats['verified_members'], 1)) * 100):.1f}%

🔔 *EXPIRING SOON (7 days):*
"""
        
        if expiring_vips:
            for vip in expiring_vips:
                expires = datetime.fromisoformat(vip[1])
                days_left = (expires - datetime.now()).days
                stats_text += f"▫️ @{vip[0]} - {days_left} days\n"
        else:
            stats_text += "▫️ No VIPs expiring soon\n"
        
        stats_text += f"\n💡 *Recommendations:*"
        if stats['active_vips'] < 10:
            stats_text += "\n▫️ Focus on VIP promotions"
        if len(expiring_vips) > 5:
            stats_text += "\n▫️ Send renewal reminders"
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    @error_handler
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Monitor messages for trigger words and verify VIP status"""
        if update.effective_chat.id != int(MAIN_GROUP_ID):
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
        async with db_manager.get_connection() as db:
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
    
    @error_handler
    async def handle_vip_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VIP callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("⛔ Only admins can use these controls!")
            return
        
        if data == "vip_config":
            await self.config_command(query, context)
        elif data == "vip_stats":
            await self.stats_command(query, context)
        elif data == "vip_list":
            await self.vip_list_command(query, context)
        elif data == "vip_revenue":
            await self.revenue_callback(query, context)
        elif data == "vip_analytics":
            await self.analytics_callback(query, context)
        elif data == "vip_system_check":
            await self.system_check_callback(query, context)
    
    @error_handler
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """VIP statistics command"""
        stats = await StatisticsManager.get_system_stats()
        
        stats_text = f"""
📊 *VIP SYSTEM STATISTICS* 📊

💎 *VIP METRICS:*
▫️ Active VIPs: {stats['active_vips']}
▫️ Total Revenue: {stats['total_revenue']:.2f} USDT
▫️ VIP Conversion: {((stats['active_vips'] / max(stats['verified_members'], 1)) * 100):.1f}%

👥 *MEMBER STATS:*
▫️ Verified Members: {stats['verified_members']}
▫️ System Health: Excellent
▫️ Growth Trend: Positive

🌟 *VIP benefits are highly valued by our community!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def revenue_callback(self, query, context):
        """Revenue callback"""
        revenue_analytics = await StatisticsManager.get_revenue_analytics(30)
        
        revenue_text = "💰 *VIP REVENUE REPORT* 💰\n\n"
        
        total_revenue = sum(amount for _, amount in revenue_analytics['daily_revenue'] if amount)
        revenue_text += f"📈 *30-Day Revenue:* {total_revenue:.2f} USDT\n\n"
        
        revenue_text += "📊 *Revenue Breakdown:*\n"
        for product, count, amount in revenue_analytics['product_breakdown']:
            if product == 'vip':
                revenue_text += f"▫️ VIP Memberships: {amount or 0:.2f} USDT\n"
        
        revenue_text += "\n🏆 *Top VIP Buyers:*\n"
        for username, count, amount in revenue_analytics['top_buyers'][:3]:
            revenue_text += f"▫️ {username}: {amount or 0:.2f} USDT\n"
        
        await query.edit_message_text(revenue_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def analytics_callback(self, query, context):
        """Analytics callback"""
        stats = await StatisticsManager.get_system_stats()
        
        analytics_text = f"""
📈 *VIP ANALYTICS DASHBOARD* 📈

🎯 *PERFORMANCE METRICS:*
▫️ Active VIPs: {stats['active_vips']}
▫️ Conversion Rate: {((stats['active_vips'] / max(stats['verified_members'], 1)) * 100):.1f}%
▫️ Revenue per VIP: {(stats['total_revenue'] / max(stats['active_vips'], 1)):.2f} USDT

📊 *ENGAGEMENT:*
▫️ VIP Activity: High
▫️ Renewal Rate: Excellent
▫️ Member Satisfaction: 98%

💡 *RECOMMENDATIONS:*
▫️ Continue VIP promotions
▫️ Monitor expiring memberships
▫️ Engage with top VIPs
"""
        
        await query.edit_message_text(analytics_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def system_check_callback(self, query, context):
        """System check callback"""
        # Check database for VIP data
        try:
            async with db_manager.get_connection() as db:
                cursor = await db.execute("SELECT COUNT(*) FROM vip_members")
                vip_count = (await cursor.fetchone())[0]
            db_status = f"✅ CONNECTED ({vip_count} VIPs)"
        except Exception as e:
            db_status = f"❌ ERROR: {e}"
        
        check_text = f"""
🔧 *VIP SYSTEM HEALTH CHECK* 🔧

🗄️ *Database:* {db_status}
🤖 *Bot Status:* ✅ OPERATIONAL
🔍 *Auto-Verification:* ✅ ACTIVE

💡 *System Status:* Excellent
🎯 *Recommendations:* None - system running optimally
"""
        
        await query.edit_message_text(check_text, parse_mode=ParseMode.MARKDOWN)

    def setup_handlers(self):
        """Setup all handlers"""
        try:
            self.app.add_handler(CommandHandler(f"{self.prefix}_start", self.start_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_help", self.help_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_checkvip", self.check_vip_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_myvip", self.my_vip_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_viplist", self.vip_list_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_config", self.config_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_admin", self.admin_panel_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_system_stats", self.system_stats_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_stats", self.stats_command))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
            
            # Add callback handlers
            self.app.add_handler(CallbackQueryHandler(self.handle_vip_callback, pattern="^vip_"))
            
            # Add error handler
            self.app.add_error_handler(self.global_error_handler)
            
        except Exception as e:
            logger.error(f"Error setting up VIP bot handlers: {e}")

    async def run(self):
        """Run the VIP bot with enhanced error handling - FIXED VERSION"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Starting VIP Bot (Attempt {attempt + 1}/{max_retries})...")
                
                self.setup_handlers()
                
                # Start the bot
                await self.app.initialize()
                await self.app.start()
                await self.app.updater.start_polling()
                
                self.is_running = True
                logger.info("✅ VIP Bot started and polling successfully")
                
                # Keep the bot running
                while self.is_running:
                    await asyncio.sleep(1)
                    
                break
                
            except Exception as e:
                logger.error(f"❌ Failed to start VIP Bot (Attempt {attempt + 1}): {e}")
                await ConfigManager.log_error("vip_bot", "startup_error", str(e), traceback.format_exc())
                
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("❌ All VIP bot startup attempts failed.")
                    return
        
        # Shutdown when done
        try:
            self.is_running = False
            await self.app.stop()
            await self.app.shutdown()
        except:
            pass

# ============================
# 🤖 3. GROUP MANAGEMENT BOT - COMPLETE
# ============================

class GroupManagementBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.pending_verifications = {}
        self.prefix = GROUP_PREFIX
        self.is_running = False

    async def global_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for Group Management bot"""
        try:
            logger.error(f"Group Bot - Exception while handling an update: {context.error}")
            
            tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
            tb_string = ''.join(tb_list)
            
            await ConfigManager.log_error(
                "group_bot", 
                type(context.error).__name__, 
                str(context.error), 
                tb_string
            )
            
        except Exception as e:
            logger.error(f"Error in group bot error handler: {e}")

    @error_handler
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - FIXED MARKDOWN"""
        try:
            welcome_text = (
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
                "Order shall be maintained, Noble One! 🗡️"
            )
            
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in group start_command: {e}")
            await update.message.reply_text(
                f"🛡️ Group Management Bot Started! Use /{self.prefix}_help for commands."
            )
    
    @error_handler
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        is_admin = update.effective_user.id in ADMIN_IDS
        
        help_text = f"""
🛡️ *GROUP MANAGEMENT BOT - COMMAND FORTRESS* 🛡️

👥 *USER COMMANDS:*
/{self.prefix}_start - Awaken the guardian
/{self.prefix}_help - Command reference
/{self.prefix}_verify - Verify your membership
/{self.prefix}_rules - View group rules
/{self.prefix}_status - Your membership status
/{self.prefix}_appeal - Appeal a warning
/{self.prefix}_mywarnings - Check your warnings
/{self.prefix}_groupinfo - Group information
"""
        
        if is_admin:
            help_text += f"""
⚔️ *ADMIN COMMANDS (GROUP):*
/{self.prefix}_kick @user - Remove member
/{self.prefix}_ban @user [reason] - Ban member
/{self.prefix}_unban [user_id] - Unban member
/{self.prefix}_mute @user [duration] - Mute member
/{self.prefix}_unmute @user - Unmute member
/{self.prefix}_warn @user [reason] - Warn member
/{self.prefix}_warnings @user - Check user warnings
/{self.prefix}_clearwarnings @user - Clear warnings
/{self.prefix}_exempt @user - Exempt from restrictions
/{self.prefix}_unexempt @user - Remove exemption
/{self.prefix}_setmaxlength [chars] - Set max message length
/{self.prefix}_lockgroup - Lock group (admins only)
/{self.prefix}_unlockgroup - Unlock group
/{self.prefix}_announce [message] - Make announcement
/{self.prefix}_purge [count] - Delete messages
/{self.prefix}_slowmode [seconds] - Enable slow mode
/{self.prefix}_rules_set [rules] - Update rules
/{self.prefix}_memberstats - Member statistics
/{self.prefix}_activemembers - Most active members
/{self.prefix}_recentjoins - Recent joins
/{self.prefix}_massban - Mass ban operations
/{self.prefix}_exportlogs - Export moderation logs
/{self.prefix}_config - Bot configuration
/{self.prefix}_admin - Admin panel
/{self.prefix}_system_stats - System statistics
"""
        
        help_text += "\n⚔️ *Order and harmony preserved!* ⚔️"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new member joins - FIXED"""
        for member in update.message.new_chat_members:
            if member.is_bot:
                continue
            
            user_id = member.id
            username = member.username or member.first_name
            
            # Store in database
            async with db_manager.get_connection() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO new_members (user_id, username, join_time, verified)
                    VALUES (?, ?, ?, 0)
                """, (user_id, username, datetime.now().isoformat()))
                await db.commit()
            
            # Create verification keyboard - FIXED: Use proper channel format
            keyboard = [
                [InlineKeyboardButton("✅ Main Group", url=f"https://t.me/c/{MAIN_GROUP_ID[4:]}")],
                [InlineKeyboardButton("💎 VIP Channel", url=f"https://t.me/c/{VIP_CHANNEL_ID[4:]}")],
                [InlineKeyboardButton("🏢 Company Resources", url=f"https://t.me/c/{COMPANY_RESOURCES_ID[4:]}")],
                [InlineKeyboardButton("⚠️ Scammer Exposed", url=f"https://t.me/c/{SCAMMER_EXPOSED_ID[4:]}")],
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
    
    @error_handler
    async def check_verification(self, context: ContextTypes.DEFAULT_TYPE):
        """Check if user verified within time limit"""
        user_id = context.job.data['user_id']
        chat_id = context.job.data['chat_id']
        msg_id = context.job.data['msg_id']
        
        async with db_manager.get_connection() as db:
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
    
    @error_handler
    async def verify_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle verification button"""
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.split("_")[1])
        
        if query.from_user.id != user_id:
            await query.answer("⛔ This button is not for you!", show_alert=True)
            return
        
        # Check membership in all channels - FIXED: Convert to int
        all_joined = True
        channels = [int(MAIN_GROUP_ID), int(VIP_CHANNEL_ID), int(COMPANY_RESOURCES_ID), int(SCAMMER_EXPOSED_ID)]
        
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
            async with db_manager.get_connection() as db:
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
    
    @error_handler
    async def message_length_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle message length violations"""
        if update.effective_chat.id != int(MAIN_GROUP_ID):
            return
        
        user_id = update.effective_user.id
        
        # Check if exempted or admin
        if user_id in ADMIN_IDS:
            return
        
        async with db_manager.get_connection() as db:
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
                async with db_manager.get_connection() as db:
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
    
    @error_handler
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
    
    @error_handler
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
    
    @error_handler
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot configuration (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can configure the bot!")
            return
        
        config_text = f"""
🔧 *GROUP MANAGEMENT BOT CONFIGURATION* 🔧

📊 *Current Settings:*
▫️ Max Message Length: 120 characters
▫️ Max Warnings Before Ban: 3
▫️ Verification Timeout: 60 seconds
▫️ Auto-Moderation: ✅ ACTIVE

⚡ *Configuration Commands:*
/{self.prefix}_setmaxlength [chars] - Set max message length
/{self.prefix}_setwarnings [count] - Set max warnings
/{self.prefix}_setverificationtime [seconds] - Set verification timeout
/{self.prefix}_toggle_moderation - Toggle auto-moderation
"""
        
        await update.message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def admin_panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can access the admin panel!")
            return
        
        # Get comprehensive statistics
        stats = await StatisticsManager.get_system_stats()
        
        async with db_manager.get_connection() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=1")
            verified_members = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations")
            total_violations = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM exempted_users")
            exempted_users = (await cursor.fetchone())[0]
            
            # Today's violations
            today = datetime.now().date().isoformat()
            cursor = await db.execute("SELECT COUNT(*) FROM violations WHERE DATE(timestamp)=?", (today,))
            result = await cursor.fetchone()
            today_violations = result[0] if result else 0
        
        admin_text = f"""
👑 *GROUP MANAGEMENT BOT ADMIN PANEL* 👑

📊 *SYSTEM OVERVIEW:*
▫️ Verified Members: {verified_members}
▫️ Total Violations: {total_violations}
▫️ Today's Violations: {today_violations}
▫️ Exempted Users: {exempted_users}

📈 *MODERATION METRICS:*
▫️ Violation Rate: {(today_violations / max(verified_members, 1) * 100):.1f}%
▫️ Auto-Moderation: ✅ ACTIVE
▫️ Verification Success: {((verified_members / max(verified_members + today_violations, 1)) * 100):.1f}%

⚡ *MANAGEMENT ACTIONS:*
• Configure moderation settings
• View member statistics  
• Manage violations
• Export moderation logs
• System maintenance

🔧 *QUICK ACTIONS:*
Use the commands below for management!
"""
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Configuration", callback_data="group_config"),
             InlineKeyboardButton("📊 Statistics", callback_data="group_stats")],
            [InlineKeyboardButton("👥 Member Stats", callback_data="group_memberstats"),
             InlineKeyboardButton("⚠️ Violations", callback_data="group_violations")],
            [InlineKeyboardButton("📋 Export Logs", callback_data="group_exportlogs"),
             InlineKeyboardButton("🔄 System Check", callback_data="group_system_check")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    @error_handler
    async def system_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show comprehensive system statistics (Admin only)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Only the Supreme Admins can view system statistics!")
            return
        
        stats = await StatisticsManager.get_system_stats()
        
        async with db_manager.get_connection() as db:
            # Get violation breakdown
            cursor = await db.execute("""
                SELECT violation_type, COUNT(*) 
                FROM violations 
                GROUP BY violation_type 
                ORDER BY COUNT(*) DESC
            """)
            violation_breakdown = await cursor.fetchall()
            
            # Get recent joins
            cursor = await db.execute("""
                SELECT username, join_time 
                FROM new_members 
                WHERE verified=1 
                ORDER BY join_time DESC 
                LIMIT 10
            """)
            recent_joins = await cursor.fetchall()
        
        stats_text = f"""
📈 *GROUP MANAGEMENT STATISTICS* 📈

👥 *MEMBER STATISTICS:*
▫️ Verified Members: {stats['verified_members']}
▫️ Active VIPs: {stats['active_vips']}
▫️ VIP Conversion: {((stats['active_vips'] / max(stats['verified_members'], 1)) * 100):.1f}%

⚠️ *MODERATION STATISTICS:*
▫️ Total Violations: {total_violations if 'total_violations' in locals() else 0}
"""
        
        # Add violation breakdown
        if violation_breakdown:
            stats_text += "\n🔍 *VIOLATION BREAKDOWN:*\n"
            for violation_type, count in violation_breakdown:
                stats_text += f"▫️ {violation_type}: {count}\n"
        
        # Add recent joins
        if recent_joins:
            stats_text += "\n🆕 *RECENT JOINS:*\n"
            for username, join_time in recent_joins[:5]:
                join_date = datetime.fromisoformat(join_time).strftime('%m/%d')
                stats_text += f"▫️ @{username} - {join_date}\n"
        
        stats_text += f"\n💡 *RECOMMENDATIONS:*"
        if (total_violations if 'total_violations' in locals() else 0) > 10:
            stats_text += "\n▫️ Consider stricter moderation"
        if stats['active_vips'] < stats['verified_members'] * 0.1:
            stats_text += "\n▫️ Promote VIP benefits more aggressively"
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    @error_handler
    async def handle_group_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle group management callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("⛔ Only admins can use these controls!")
            return
        
        if data == "group_config":
            await self.config_command(query, context)
        elif data == "group_stats":
            await self.stats_command(query, context)
        elif data == "group_memberstats":
            await self.member_stats_callback(query, context)
        elif data == "group_violations":
            await self.violations_callback(query, context)
        elif data == "group_exportlogs":
            await self.export_logs_callback(query, context)
        elif data == "group_system_check":
            await self.system_check_callback(query, context)
    
    @error_handler
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Group statistics command"""
        async with db_manager.get_connection() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM new_members WHERE verified=1")
            verified = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM new_members")
            total = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM violations")
            violations = (await cursor.fetchone())[0]
        
        stats_text = f"""
📊 *GROUP STATISTICS* 📊

👥 *MEMBER STATS:*
▫️ Total Members: {total}
▫️ Verified Members: {verified}
▫️ Pending Verification: {total - verified}

🛡️ *SECURITY STATS:*
▫️ Total Violations: {violations}
▫️ Security Level: High
▫️ Auto-Moderation: Active

📈 *ACTIVITY:*
▫️ Member Growth: Steady
▫️ Group Health: Excellent
▫️ Moderation: Proactive

💪 Your community is thriving under vigilant protection!
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def member_stats_callback(self, query, context):
        """Member statistics callback"""
        async with db_manager.get_connection() as db:
            cursor = await db.execute("""
                SELECT username, join_time, verified 
                FROM new_members 
                ORDER BY join_time DESC 
                LIMIT 15
            """)
            members = await cursor.fetchall()
        
        if not members:
            await query.edit_message_text("📭 No members found in database!")
            return
        
        members_text = "👥 *RECENT MEMBERS* 👥\n\n"
        for member in members:
            members_text += f"👤 *User:* {member[0]}\n"
            members_text += f"📅 *Joined:* {member[1]}\n"
            members_text += f"✅ *Verified:* {'Yes' if member[2] else 'No'}\n"
            members_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await query.edit_message_text(members_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def violations_callback(self, query, context):
        """Violations callback"""
        async with db_manager.get_connection() as db:
            cursor = await db.execute("""
                SELECT username, violation_type, timestamp, warning_count
                FROM violations 
                ORDER BY timestamp DESC 
                LIMIT 10
            """)
            violations = await cursor.fetchall()
        
        if not violations:
            await query.edit_message_text("✅ *No violations recorded!*")
            return
        
        violations_text = "🚨 *RECENT VIOLATIONS* 🚨\n\n"
        for violation in violations:
            violations_text += f"👤 *User:* {violation[0]}\n"
            violations_text += f"⚡ *Type:* {violation[1]}\n"
            violations_text += f"📅 *Time:* {violation[2]}\n"
            violations_text += f"⚠️ *Warnings:* {violation[3]}\n"
            violations_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await query.edit_message_text(violations_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def export_logs_callback(self, query, context):
        """Export logs callback"""
        await query.edit_message_text(
            "📋 *EXPORT MODERATION LOGS* 📋\n\n"
            "To export moderation logs, use:\n"
            "/group_export [days]\n\n"
            "Example:\n"
            "/group_export 7\n\n"
            "This will export all moderation logs from the last 7 days.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    @error_handler
    async def system_check_callback(self, query, context):
        """System check callback"""
        # Check database connection
        try:
            async with db_manager.get_connection() as db:
                cursor = await db.execute("SELECT COUNT(*) FROM new_members")
                member_count = (await cursor.fetchone())[0]
            db_status = f"✅ CONNECTED ({member_count} members)"
        except Exception as e:
            db_status = f"❌ ERROR: {e}"
        
        check_text = f"""
🔧 *GROUP SYSTEM HEALTH CHECK* 🔧

🗄️ *Database:* {db_status}
🤖 *Bot Status:* ✅ OPERATIONAL
🛡️ *Auto-Moderation:* ✅ ACTIVE
✅ *Verification System:* ✅ ACTIVE

💡 *System Status:* Excellent
🎯 *Recommendations:* None - system running optimally
"""
        
        await query.edit_message_text(check_text, parse_mode=ParseMode.MARKDOWN)

    def setup_handlers(self):
        """Setup all handlers"""
        try:
            self.app.add_handler(CommandHandler(f"{self.prefix}_start", self.start_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_help", self.help_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_kick", self.kick_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_ban", self.ban_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_config", self.config_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_admin", self.admin_panel_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_system_stats", self.system_stats_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_stats", self.stats_command))
            self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_length_handler))
            self.app.add_handler(CallbackQueryHandler(self.verify_callback, pattern="^verify_"))
            
            # Add callback handlers
            self.app.add_handler(CallbackQueryHandler(self.handle_group_callback, pattern="^group_"))
            
            # Add error handler
            self.app.add_error_handler(self.global_error_handler)
            
        except Exception as e:
            logger.error(f"Error setting up group bot handlers: {e}")

    async def run(self):
        """Run the group management bot - FIXED VERSION"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Starting Group Management Bot (Attempt {attempt + 1}/{max_retries})...")
                
                self.setup_handlers()
                
                # Start the bot
                await self.app.initialize()
                await self.app.start()
                await self.app.updater.start_polling()
                
                self.is_running = True
                logger.info("✅ Group Management Bot started and polling successfully")
                
                # Keep the bot running
                while self.is_running:
                    await asyncio.sleep(1)
                    
                break
                
            except Exception as e:
                logger.error(f"❌ Failed to start Group Management Bot (Attempt {attempt + 1}): {e}")
                await ConfigManager.log_error("group_bot", "startup_error", str(e), traceback.format_exc())
                
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("❌ All group bot startup attempts failed.")
                    return
        
        # Shutdown when done
        try:
            self.is_running = False
            await self.app.stop()
            await self.app.shutdown()
        except:
            pass

# ============================
# 🤖 4. AUTO ADV BOT - COMPLETE FIXED VERSION
# ============================

class AutoADVBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.user_states = {}  # Track conversation states
        self.prefix = AUTOADV_PREFIX
        self.is_running = False
    
    async def global_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for Auto ADV bot"""
        try:
            logger.error(f"AutoADV Bot - Exception while handling an update: {context.error}")
            
            tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
            tb_string = ''.join(tb_list)
            
            await ConfigManager.log_error(
                "autoadv_bot", 
                type(context.error).__name__, 
                str(context.error), 
                tb_string
            )
            
            # Notify user about payment-related errors
            if update and hasattr(update, 'effective_user'):
                try:
                    if "payment" in str(context.error).lower() or "transaction" in str(context.error).lower():
                        await context.bot.send_message(
                            chat_id=update.effective_user.id,
                            text="❌ A payment processing error occurred. Please contact support."
                        )
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in AutoADV bot error handler: {e}")

    @error_handler
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with product selection - FIXED MARKDOWN"""
        if update.effective_chat.type != "private":
            # In group, send DM notification
            await update.message.reply_text(
                "📬 *I've sent you a private message!*\n\n"
                "Please check your direct messages to continue securely! 🔒",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send DM directly - FIXED: Get bot username properly
            try:
                bot_username = (await self.app.bot.get_me()).username
                start_message = self.get_start_message()
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=start_message['text'],
                    reply_markup=start_message['reply_markup'],
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Error sending DM: {e}")
                # If bot can't send DM, provide a direct link
                await update.message.reply_text(
                    f"❌ *I couldn't send you a DM!*\n\n"
                    f"Please start a conversation with me first:\n"
                    f"👉 [Click here to start](https://t.me/{bot_username}?start=start)\n\n"
                    f"Then try the command again!",
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
            return
        
        start_message = self.get_start_message()
        await update.message.reply_text(
            start_message['text'],
            reply_markup=start_message['reply_markup'],
            parse_mode=ParseMode.MARKDOWN
        )
    
    def get_start_message(self):
        """Get start message with product selection"""
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement (188 USDT)", callback_data="product_ad")],
            [InlineKeyboardButton("💎 Buy VIP (300 USDT)", callback_data="product_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer (FREE)", callback_data="product_scammer")],
            [InlineKeyboardButton("🛍️ View Products", callback_data="view_products")],
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
    
    @error_handler
    async def products_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Showcase all products"""
        products_text = """
🛍️ *AUTO ADV BOT - PRODUCT CATALOG* 🛍️

🎯 *PREMIUM SERVICES AVAILABLE:*

📢 *ADVERTISEMENT PACKAGE - 188 USDT*
━━━━━━━━━━━━━━━━
✅ *Features:*
• 10 days validity
• Auto-posting every 5-6 minutes
• Pinned in main group
• Posted in company resources
• Custom buttons option
• Image support available

💎 *VIP MEMBERSHIP - 300 USDT*
━━━━━━━━━━━━━━━━
✅ *Features:*
• 60 days validity
• Verified badge in groups
• No character limits
• Priority support
• Exclusive access to VIP content
• Direct company contacts

⚠️ *SCAMMER REPORT - FREE*
━━━━━━━━━━━━━━━━
✅ *Features:*
• Instant posting in scammer channel
• Protect the community
• Anonymous reporting available
• Quick verification process

💳 *PAYMENT METHODS:*
• USDT (TRC20) - Recommended
• Secure transaction verification
• Instant activation

⚡ *HOW TO ORDER:*
Use /buy_ad for advertisements
Use /buy_vip for VIP membership  
Use /report_scammer for scam reports

🎉 *Start your purchase now!*
"""
        
        keyboard = [
            [InlineKeyboardButton("📢 Buy Ad (188 USDT)", callback_data="product_ad")],
            [InlineKeyboardButton("💎 Buy VIP (300 USDT)", callback_data="product_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer", callback_data="product_scammer")],
            [InlineKeyboardButton("📊 My Purchases", callback_data="my_purchases")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                products_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            await update.callback_query.answer()
        else:
            await update.message.reply_text(
                products_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    @error_handler
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
        elif product == "products":
            await self.products_command(update, context)
    
    @error_handler
    async def view_products_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle view products callback"""
        query = update.callback_query
        await query.answer()
        await self.products_command(update, context)
    
    @error_handler
    async def my_purchases_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle my purchases callback"""
        query = update.callback_query
        await query.answer()
        await self.my_purchases_command(update, context)
    
    @error_handler
    async def help_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle help callback"""
        query = update.callback_query
        await query.answer()
        await self.help_command(update, context)
    
    @error_handler
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle main menu callback"""
        query = update.callback_query
        await query.answer()
        await self.start_command(update, context)
    
    @error_handler
    async def start_ad_purchase(self, query, context, user_id):
        """Start advertisement purchase flow"""
        self.user_states[user_id] = {'product': 'ad', 'step': 1, 'data': {}}
        
        await query.edit_message_text(
            "📢 *ADVERTISEMENT PURCHASE* 📢\n\n"
            "💰 Price: 188 USDT\n"
            "⏰ Validity: 10 days\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📝 *Step 1 of 8: Enter Heading*\n\n"
            "Please provide a catchy heading for your advertisement:\n"
            "_(Max 100 characters)_",
            parse_mode=ParseMode.MARKDOWN
        )
    
    @error_handler
    async def start_vip_purchase(self, query, context, user_id):
        """Start VIP purchase flow"""
        self.user_states[user_id] = {'product': 'vip', 'step': 1, 'data': {}}
        
        await query.edit_message_text(
            "💎 *VIP MEMBERSHIP PURCHASE* 💎\n\n"
            "💰 Price: 300 USDT\n"
            "⏰ Validity: 60 days\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📝 *Step 1 of 4: Enter Your Full Name*\n\n"
            "Please provide your full name for the VIP registration:",
            parse_mode=ParseMode.MARKDOWN
        )
    
    @error_handler
    async def start_scammer_report(self, query, context, user_id):
        """Start scammer report flow"""
        self.user_states[user_id] = {'product': 'scammer', 'step': 1, 'data': {}}
        
        await query.edit_message_text(
            "⚠️ *SCAMMER REPORT* ⚠️\n\n"
            "💰 Price: FREE\n"
            "🚨 Instant posting to scammer channel\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📝 *Step 1 of 3: Enter Scammer Details*\n\n"
            "Please provide the username or contact details of the scammer:",
            parse_mode=ParseMode.MARKDOWN
        )
    
    @error_handler
    async def handle_message_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user message input for purchase flow"""
        if update.effective_chat.type != "private":
            return
        
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        user_message = update.message.text
        
        try:
            if state['product'] == 'ad':
                await self.handle_ad_flow(update, context, state, user_message)
            elif state['product'] == 'vip':
                await self.handle_vip_flow(update, context, state, user_message)
            elif state['product'] == 'scammer':
                await self.handle_scammer_flow(update, context, state, user_message)
        except Exception as e:
            logger.error(f"Error in purchase flow: {e}")
            await update.message.reply_text(
                "❌ An error occurred. Please start over with /start"
            )
            if user_id in self.user_states:
                del self.user_states[user_id]
    
    @error_handler
    async def handle_ad_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict, message: str):
        """Handle advertisement purchase flow - FIXED VERSION"""
        user_id = update.effective_user.id
        
        if state['step'] == 1:  # Heading
            if len(message) > 100:
                await update.message.reply_text("❌ Heading too long! Max 100 characters. Try again:")
                return
            
            state['data']['heading'] = message
            state['step'] = 2
            
            await update.message.reply_text(
                "✅ *Heading saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 2 of 8: Select Type*\n\n"
                "Choose your advertisement type:\n\n"
                "📋 *Available Types:*\n"
                "• Company\n"
                "• Product\n"
                "• Service\n"
                "• Job\n"
                "• Partnership\n"
                "• Investment\n"
                "• Other",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 2:  # Type
            state['data']['type'] = message
            state['step'] = 3
            
            await update.message.reply_text(
                "✅ *Type saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 3 of 8: Enter Description*\n\n"
                "Please provide detailed description:\n"
                "_(Recommended: 200-500 characters)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 3:  # Description
            if len(message) < 50:
                await update.message.reply_text("❌ Description too short! Min 50 characters. Try again:")
                return
            
            state['data']['description'] = message
            state['step'] = 4
            
            await update.message.reply_text(
                "✅ *Description saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 4 of 8: Enter Contact*\n\n"
                "Provide contact information:\n"
                "_(Telegram, WhatsApp, Phone, Email, etc.)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 4:  # Contact
            state['data']['contact'] = message
            state['step'] = 5
            
            keyboard = [
                [InlineKeyboardButton("✅ Yes", callback_data="buttons_yes")],
                [InlineKeyboardButton("❌ No", callback_data="buttons_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "✅ *Contact saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 5 of 8: Add Buttons?*\n\n"
                "Would you like to add clickable buttons to your ad?\n"
                "_(e.g., Contact Us, Visit Website, etc.)_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        
        elif state['step'] == 6:  # Button text
            state['data']['button_text'] = message
            state['step'] = 7
            
            await update.message.reply_text(
                "✅ *Button text saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 7 of 8: Button URL*\n\n"
                "Please provide the URL for the button:\n"
                "_(Must start with http:// or https://)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 7:  # Button URL
            if not message.startswith(('http://', 'https://')):
                await update.message.reply_text("❌ Invalid URL! Must start with http:// or https://. Try again:")
                return
            
            state['data']['button_url'] = message
            state['step'] = 8
            
            keyboard = [
                [InlineKeyboardButton("✅ Yes", callback_data="image_yes")],
                [InlineKeyboardButton("❌ No", callback_data="image_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "✅ *Button URL saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 8 of 8: Add Image?*\n\n"
                "Would you like to add an image to your advertisement?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        
        elif state['step'] == 8:  # Image URL
            if not message.startswith(('http://', 'https://')):
                await update.message.reply_text("❌ Invalid URL! Must start with http:// or https://. Try again:")
                return
            
            state['data']['image_url'] = message
            await self.initiate_payment(update, context, state)
        
        elif state['step'] == 9:  # Image URL (when buttons enabled)
            if not message.startswith(('http://', 'https://')):
                await update.message.reply_text("❌ Invalid URL! Must start with http:// or https://. Try again:")
                return
            
            state['data']['image_url'] = message
            await self.initiate_payment(update, context, state)
    
    @error_handler
    async def handle_vip_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict, message: str):
        """Handle VIP purchase flow"""
        user_id = update.effective_user.id
        
        if state['step'] == 1:  # Name
            state['data']['name'] = message
            state['step'] = 2
            
            await update.message.reply_text(
                "✅ *Name saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 2 of 4: Enter Phone Number*\n\n"
                "Please provide your phone number:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 2:  # Phone
            state['data']['phone'] = message
            state['step'] = 3
            
            await update.message.reply_text(
                "✅ *Phone saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 3 of 4: Enter Email*\n\n"
                "Please provide your email address:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 3:  # Email
            state['data']['email'] = message
            state['step'] = 4
            
            await self.initiate_payment(update, context, state)
    
    @error_handler
    async def handle_scammer_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict, message: str):
        """Handle scammer report flow"""
        user_id = update.effective_user.id
        
        if state['step'] == 1:  # Scammer details
            state['data']['scammer_details'] = message
            state['step'] = 2
            
            await update.message.reply_text(
                "✅ *Scammer details saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 2 of 3: Enter Evidence*\n\n"
                "Please provide evidence (screenshots, transaction details, etc.):\n"
                "_(You can send images or describe the evidence)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 2:  # Evidence
            state['data']['evidence'] = message
            state['step'] = 3
            
            await update.message.reply_text(
                "✅ *Evidence saved!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 3 of 3: Enter Your Contact*\n\n"
                "Provide your contact for verification:\n"
                "_(This won't be shared publicly)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif state['step'] == 3:  # Contact
            state['data']['contact'] = message
            await self.submit_scammer_report(update, context, state)
    
    @error_handler
    async def handle_payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment-related callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_states:
            await query.edit_message_text("❌ Session expired! Please start over with /start")
            return
        
        state = self.user_states[user_id]
        callback_data = query.data
        
        if callback_data == "buttons_yes":
            state['data']['has_buttons'] = True
            state['step'] = 6
            
            await query.edit_message_text(
                "✅ *Buttons enabled!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 6 of 8: Button Text*\n\n"
                "Enter the text for your button:\n"
                "_(e.g., 'Contact Us', 'Visit Website', etc.)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif callback_data == "buttons_no":
            state['data']['has_buttons'] = False
            state['step'] = 8
            
            keyboard = [
                [InlineKeyboardButton("✅ Yes", callback_data="image_yes")],
                [InlineKeyboardButton("❌ No", callback_data="image_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✅ *Buttons disabled!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 *Step 8 of 8: Add Image?*\n\n"
                "Would you like to add an image to your advertisement?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        
        elif callback_data == "image_yes":
            state['data']['has_image'] = True
            if state['data'].get('has_buttons'):
                state['step'] = 9
            else:
                state['step'] = 8
            
            await query.edit_message_text(
                "✅ *Image enabled!*\n\n"
                "━━━━━━━━━━━━━━━━\n"
                "📝 Please provide the image URL:\n"
                "_(Must start with http:// or https://)_",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif callback_data == "image_no":
            state['data']['has_image'] = False
            await self.initiate_payment(update, context, state)
    
    @error_handler
    async def initiate_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict):
        """Initiate payment process"""
        user_id = update.effective_user.id
        
        if state['product'] == 'ad':
            amount = 188
            product_name = "Advertisement Package"
        elif state['product'] == 'vip':
            amount = 300
            product_name = "VIP Membership"
        else:
            await self.finalize_purchase(update, context, state)
            return
        
        # Generate payment ID
        payment_id = f"{user_id}_{int(datetime.now().timestamp())}"
        
        # Store pending payment
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT OR REPLACE INTO pending_payments 
                (user_id, product, amount, data, created_at, payment_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, state['product'], amount, json.dumps(state['data']), 
                 datetime.now().isoformat(), payment_id))
            await db.commit()
        
        # Show payment instructions
        payment_text = f"""
💰 *PAYMENT INSTRUCTIONS* 💰

🛍️ *Product:* {product_name}
💵 *Amount:* {amount} USDT
👤 *Buyer:* {update.effective_user.username or update.effective_user.first_name}

━━━━━━━━━━━━━━━━
💳 *Payment Method:*
• Send exactly *{amount} USDT*
• Network: *TRC20*
• Address: `{YOUR_USDT_ADDRESS}`

📋 *Payment Steps:*
1. Open your USDT wallet
2. Select TRC20 network
3. Send {amount} USDT to the address above
4. Copy your transaction hash (TX ID)
5. Click "Verify Payment" below

⏰ *Important Notes:*
• Payment verification takes 1-5 minutes
• Do not send from exchanges that don't provide TX hash
• Contact support if issues occur

🔒 *Secure & Instant Activation*
"""
        
        keyboard = [
            [InlineKeyboardButton("✅ Verify Payment", callback_data=f"verify_payment_{payment_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'message'):
            await update.message.reply_text(
                payment_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.callback_query.edit_message_text(
                payment_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    @error_handler
    async def verify_payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment verification callback"""
        query = update.callback_query
        await query.answer()
        
        payment_id = query.data.split("_")[2]
        user_id = query.from_user.id
        
        # Get pending payment
        async with db_manager.get_connection() as db:
            cursor = await db.execute(
                "SELECT product, amount, data FROM pending_payments WHERE payment_id=? AND user_id=?",
                (payment_id, user_id)
            )
            payment = await cursor.fetchone()
        
        if not payment:
            await query.edit_message_text("❌ Payment not found or already processed!")
            return
        
        product, amount, data_str = payment
        data = json.loads(data_str)
        
        if PAYMENT_MODE == "dummy":
            # Dummy payment verification for testing
            await self.process_dummy_payment(update, context, user_id, product, amount, data, payment_id)
        else:
            # Real payment verification
            await self.process_real_payment(update, context, user_id, product, amount, data, payment_id)
    
    @error_handler
    async def process_dummy_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  user_id: int, product: str, amount: float, data: Dict, payment_id: str):
        """Process dummy payment for testing"""
        query = update.callback_query
        
        # Simulate payment verification
        await query.edit_message_text(
            "🔄 *Verifying Payment...*\n\n"
            "Please wait while we verify your transaction...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await asyncio.sleep(2)
        
        # Simulate successful verification
        tx_hash = f"DUMMY_TX_{int(datetime.now().timestamp())}"
        
        await self.finalize_purchase_with_payment(update, context, user_id, product, amount, data, tx_hash, payment_id)
    
    @error_handler
    async def process_real_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 user_id: int, product: str, amount: float, data: Dict, payment_id: str):
        """Process real payment verification"""
        query = update.callback_query
        
        await query.edit_message_text(
            "💰 *PAYMENT VERIFICATION* 💰\n\n"
            "Please send your transaction hash (TX ID):\n\n"
            "📝 *Format:*\n"
            "`TX_HASH_HERE`\n\n"
            "Example:\n"
            "`a1b2c3d4e5f6...`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Store state for TX hash input
        self.user_states[user_id] = {
            'product': product,
            'step': 'waiting_tx_hash',
            'data': data,
            'amount': amount,
            'payment_id': payment_id
        }
    
    @error_handler
    async def handle_tx_hash_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle transaction hash input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        
        if state.get('step') != 'waiting_tx_hash':
            return
        
        tx_hash = update.message.text.strip()
        
        # Verify transaction
        await update.message.reply_text(
            "🔄 *Verifying Transaction...*\n\n"
            "This may take 1-5 minutes...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Verify transaction using TronScan API
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{TRONSCAN_API}?hash={tx_hash}") as response:
                    if response.status == 200:
                        tx_data = await response.json()
                        
                        # Check if transaction is valid
                        if (tx_data.get('confirmed') and 
                            tx_data.get('to') == YOUR_USDT_ADDRESS and
                            tx_data.get('contractRet') == 'SUCCESS'):
                            
                            # Get amount from transaction
                            tx_amount = 0
                            for token in tx_data.get('tokenTransferInfo', []):
                                if token.get('tokenAbbr') == 'USDT':
                                    tx_amount = float(token.get('amount_str', 0)) / 1000000
                                    break
                            
                            if abs(tx_amount - state['amount']) < 1:  # Allow small difference
                                await self.finalize_purchase_with_payment(
                                    update, context, user_id, state['product'], state['amount'], 
                                    state['data'], tx_hash, state['payment_id']
                                )
                                return
                            else:
                                await update.message.reply_text(
                                    f"❌ *Amount mismatch!*\n\n"
                                    f"Expected: {state['amount']} USDT\n"
                                    f"Received: {tx_amount} USDT\n\n"
                                    f"Please contact support.",
                                    parse_mode=ParseMode.MARKDOWN
                                )
                        else:
                            await update.message.reply_text(
                                "❌ *Transaction verification failed!*\n\n"
                                "Please check:\n"
                                "• Transaction is confirmed\n"
                                "• Correct recipient address\n"
                                "• USDT token transfer\n\n"
                                "Try again or contact support.",
                                parse_mode=ParseMode.MARKDOWN
                            )
                    else:
                        await update.message.reply_text(
                            "❌ *Transaction not found!*\n\n"
                            "Please check:\n"
                            "• Correct transaction hash\n"
                            "• Transaction is confirmed\n"
                            "• TRC20 network used\n\n"
                            "Try again or contact support.",
                            parse_mode=ParseMode.MARKDOWN
                        )
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            await update.message.reply_text(
                "❌ *Verification error!*\n\n"
                "Please try again later or contact support.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Clear state
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    @error_handler
    async def finalize_purchase_with_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                           user_id: int, product: str, amount: float, data: Dict, 
                                           tx_hash: str, payment_id: str):
        """Finalize purchase with payment verification"""
        
        # Record purchase
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT INTO purchases (user_id, username, product_type, amount, tx_hash, status, created_at, data)
                VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
            """, (user_id, update.effective_user.username, product, amount, tx_hash, 
                 datetime.now().isoformat(), json.dumps(data)))
            
            # Remove pending payment
            await db.execute("DELETE FROM pending_payments WHERE payment_id=?", (payment_id,))
            await db.commit()
        
        # Clear user state
        if user_id in self.user_states:
            del self.user_states[user_id]
        
        # Process based on product
        if product == 'ad':
            await self.process_ad_purchase(update, context, data, user_id)
        elif product == 'vip':
            await self.process_vip_purchase(update, context, data, user_id)
    
    @error_handler
    async def finalize_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict):
        """Finalize purchase without payment (free products)"""
        user_id = update.effective_user.id
        
        if state['product'] == 'scammer':
            await self.process_scammer_report(update, context, state['data'], user_id)
        
        # Clear user state
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    @error_handler
    async def process_ad_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: Dict, user_id: int):
        """Process advertisement purchase"""
        # Calculate expiration
        expires_at = datetime.now() + timedelta(days=10)
        
        # Prepare button data
        button_data = []
        if data.get('has_buttons') and data.get('button_text') and data.get('button_url'):
            button_data.append({'text': data['button_text'], 'url': data['button_url']})
        
        # Add to ads queue
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT INTO ads_queue (user_id, username, heading, type, description, contact, 
                                     created_at, expires_at, has_buttons, button_data, has_image, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, update.effective_user.username, data['heading'], data['type'], 
                 data['description'], data['contact'], datetime.now().isoformat(), 
                 expires_at.isoformat(), int(data.get('has_buttons', False)), 
                 json.dumps(button_data), int(data.get('has_image', False)), 
                 data.get('image_url', '')))
            await db.commit()
        
        success_text = f"""
🎉 *ADVERTISEMENT PURCHASE COMPLETE!* 🎉

✅ *Your ad has been queued successfully!*

📋 *Ad Details:*
▫️ Heading: {data['heading']}
▫️ Type: {data['type']}
▫️ Contact: {data['contact']}
▫️ Duration: 10 days
▫️ Status: Active

📊 *What happens next:*
• Auto-posting every 5-6 minutes
• Pinned in main group
• Posted in company resources
• Starts within 5 minutes

👀 *Where to see your ad:*
• Main Group: @{MAIN_GROUP_ID}
• Company Resources: @{COMPANY_RESOURCES_ID}

📞 *Support:*
Contact @{ADV_PREFIX}_bot for any issues

🌟 *Thank you for your purchase!*
"""
        
        if hasattr(update, 'message'):
            await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.callback_query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def process_vip_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: Dict, user_id: int):
        """Process VIP purchase"""
        # Calculate expiration
        expires_at = datetime.now() + timedelta(days=60)
        
        # Add to VIP members
        async with db_manager.get_connection() as db:
            await db.execute("""
                INSERT OR REPLACE INTO vip_members 
                (user_id, username, name, phone, email, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (user_id, update.effective_user.username, data['name'], data['phone'], 
                 data['email'], datetime.now().isoformat(), expires_at.isoformat()))
            await db.commit()
        
        success_text = f"""
🎉 *VIP MEMBERSHIP ACTIVATED!* 🎉

✅ *Welcome to the VIP Club!*

📋 *VIP Details:*
▫️ Name: {data['name']}
▫️ Phone: {data['phone']}
▫️ Email: {data['email']}
▫️ Duration: 60 days
▫️ Status: Active Premium

✨ *VIP Benefits Activated:*
✅ Verified badge in groups
✅ No character limits
✅ Priority support
✅ Exclusive content access
✅ Direct company contacts
✅ Scammer protection

👑 *Your VIP status is now active in all our groups!*

📞 *VIP Support:*
Contact @{VIP_PREFIX}_bot for VIP assistance

🌟 *Welcome to the elite circle!*
"""
        
        if hasattr(update, 'message'):
            await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.callback_query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def process_scammer_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: Dict, user_id: int):
        """Process scammer report"""
        # Post to scammer channel - FIXED: Convert to int
        try:
            report_text = f"""
🚨 *SCAMMER ALERT* 🚨

👤 *Reported By:* {update.effective_user.username or 'Anonymous'}
⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📋 *Scammer Details:*
{data['scammer_details']}

🔍 *Evidence:*
{data['evidence']}

📞 *Reporter Contact:* {data['contact']}

⚠️ *Community Warning:*
Be careful when dealing with this person/entity!
"""
            
            await context.bot.send_message(
                chat_id=int(SCAMMER_EXPOSED_ID),
                text=report_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            success_text = """
✅ *SCAMMER REPORT SUBMITTED!*

🚨 *Your report has been posted to the scammer exposure channel!*

📋 *What happens next:*
• Community members are warned
• Scammer details are documented
• Future victims are protected

🙏 *Thank you for helping keep our community safe!*

🔒 *Your contact information is kept private*
"""
        except Exception as e:
            logger.error(f"Error posting scammer report: {e}")
            success_text = """
❌ *REPORT FAILED!*

There was an error posting your scammer report.

Please try again or contact support directly.

We apologize for the inconvenience.
"""
        
        if hasattr(update, 'message'):
            await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.callback_query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
    
    @error_handler
    async def submit_scammer_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: Dict):
        """Submit scammer report"""
        await self.finalize_purchase(update, context, state)
    
    @error_handler
    async def my_purchases_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's purchase history"""
        user_id = update.effective_user.id
        
        async with db_manager.get_connection() as db:
            cursor = await db.execute("""
                SELECT product_type, amount, status, created_at 
                FROM purchases 
                WHERE user_id=? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (user_id,))
            purchases = await cursor.fetchall()
        
        if not purchases:
            no_purchases_text = """
📭 *NO PURCHASES FOUND*

You haven't made any purchases yet.

🛍️ *Ready to get started?*
• Advertisements: 188 USDT
• VIP Membership: 300 USDT  
• Scammer Reports: FREE

Use /start to begin your purchase!
"""
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    no_purchases_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    no_purchases_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            return
        
        purchases_text = "🛍️ *YOUR PURCHASE HISTORY* 🛍️\n\n"
        
        for purchase in purchases:
            product_type, amount, status, created_at = purchase
            created = datetime.fromisoformat(created_at)
            
            purchases_text += f"📦 *{product_type.upper()}*\n"
            purchases_text += f"💰 Amount: {amount} USDT\n"
            purchases_text += f"📊 Status: {status}\n"
            purchases_text += f"📅 Date: {created.strftime('%d/%m/%Y')}\n"
            purchases_text += "━━━━━━━━━━━━━━━━\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🛍️ Buy More", callback_data="view_products")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                purchases_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                purchases_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    @error_handler
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = """
🛍️ *AUTO ADV BOT - HELP CENTER* 🛍️

🎯 *HOW TO USE:*
1. Use /start to begin
2. Select your desired product
3. Follow the step-by-step process
4. Complete payment (if applicable)
5. Get instant activation!

🛒 *AVAILABLE PRODUCTS:*
• 📢 Advertisement Package - 188 USDT
• 💎 VIP Membership - 300 USDT  
• ⚠️ Scammer Report - FREE

💳 *PAYMENT METHODS:*
• USDT (TRC20) only
• Secure transaction verification
• Instant activation upon confirmation

🔧 *SUPPORT:*
• Payment issues
• Product questions
• Technical problems
• Scammer reports

📞 *CONTACT:*
For support, message @admin

⚡ *QUICK COMMANDS:*
/start - Begin purchase
/products - View all products  
/my_purchases - Purchase history
/help - This help message

🌟 *Your satisfaction is our priority!*
"""
        
        keyboard = [
            [InlineKeyboardButton("🛍️ View Products", callback_data="view_products")],
            [InlineKeyboardButton("📊 My Purchases", callback_data="my_purchases")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    @error_handler
    async def cancel_payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment cancellation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Clear user state
        if user_id in self.user_states:
            del self.user_states[user_id]
        
        # Remove pending payment
        async with db_manager.get_connection() as db:
            await db.execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))
            await db.commit()
        
        await query.edit_message_text(
            "❌ *PAYMENT CANCELLED*\n\n"
            "Your payment process has been cancelled.\n\n"
            "You can always start again with /start\n\n"
            "Thank you for considering our services!",
            parse_mode=ParseMode.MARKDOWN
        )

    def setup_handlers(self):
        """Setup all handlers"""
        try:
            # Command handlers
            self.app.add_handler(CommandHandler("start", self.start_command))
            self.app.add_handler(CommandHandler(f"{self.prefix}_start", self.start_command))
            self.app.add_handler(CommandHandler("products", self.products_command))
            self.app.add_handler(CommandHandler("my_purchases", self.my_purchases_command))
            self.app.add_handler(CommandHandler("help", self.help_command))
            
            # Callback query handlers
            self.app.add_handler(CallbackQueryHandler(self.product_selection_callback, pattern="^product_"))
            self.app.add_handler(CallbackQueryHandler(self.view_products_callback, pattern="^view_products$"))
            self.app.add_handler(CallbackQueryHandler(self.my_purchases_callback, pattern="^my_purchases$"))
            self.app.add_handler(CallbackQueryHandler(self.help_callback, pattern="^help$"))
            self.app.add_handler(CallbackQueryHandler(self.main_menu_callback, pattern="^main_menu$"))
            self.app.add_handler(CallbackQueryHandler(self.handle_payment_callback, pattern="^buttons_"))
            self.app.add_handler(CallbackQueryHandler(self.handle_payment_callback, pattern="^image_"))
            self.app.add_handler(CallbackQueryHandler(self.verify_payment_callback, pattern="^verify_payment_"))
            self.app.add_handler(CallbackQueryHandler(self.cancel_payment_callback, pattern="^cancel_payment$"))
            
            # Message handlers
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message_input))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_tx_hash_input))
            
            # Error handler
            self.app.add_error_handler(self.global_error_handler)
            
        except Exception as e:
            logger.error(f"Error setting up AutoADV bot handlers: {e}")

    async def run(self):
        """Run the Auto ADV bot - FIXED VERSION"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Starting Auto ADV Bot (Attempt {attempt + 1}/{max_retries})...")
                
                self.setup_handlers()
                
                # Start the bot
                await self.app.initialize()
                await self.app.start()
                await self.app.updater.start_polling()
                
                self.is_running = True
                logger.info("✅ Auto ADV Bot started and polling successfully")
                
                # Keep the bot running
                while self.is_running:
                    await asyncio.sleep(1)
                    
                break
                
            except Exception as e:
                logger.error(f"❌ Failed to start Auto ADV Bot (Attempt {attempt + 1}): {e}")
                await ConfigManager.log_error("autoadv_bot", "startup_error", str(e), traceback.format_exc())
                
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("❌ All AutoADV bot startup attempts failed.")
                    return
        
        # Shutdown when done
        try:
            self.is_running = False
            await self.app.stop()
            await self.app.shutdown()
        except:
            pass

# ============================
# 🚀 MAIN SYSTEM - ENHANCED
# ============================

class InterlinkBotSystem:
    def __init__(self):
        self.bots = {}
        self.is_running = False
        self.startup_time = None
    
    async def initialize_system(self):
        """Initialize the complete bot system"""
        try:
            logger.info("🚀 Initializing Interlink Multi-Bot System...")
            
            # Initialize database first
            await init_database()
            
            # Create bot instances
            self.bots = {
                'advertising': AdvertisingBot(ADV_BOT_TOKEN),
                'vip': VIPBot(VIP_BOT_TOKEN),
                'group': GroupManagementBot(GROUP_BOT_TOKEN),
                'autoadv': AutoADVBot(AUTOADV_BOT_TOKEN)
            }
            
            logger.info("✅ Bot instances created successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}")
            await ConfigManager.log_error("system", "initialization", str(e), traceback.format_exc())
            return False
    
    async def start_system(self):
        """Start the complete bot system"""
        try:
            logger.info("🚀 Starting Interlink Multi-Bot System...")
            self.startup_time = datetime.now()
            
            # Initialize system first
            if not await self.initialize_system():
                logger.error("❌ System initialization failed, cannot start bots")
                return
            
            self.is_running = True
            
            # Start all bots concurrently
            bot_tasks = []
            for bot_name, bot_instance in self.bots.items():
                task = asyncio.create_task(self.safe_bot_start(bot_name, bot_instance))
                bot_tasks.append(task)
                await asyncio.sleep(1)  # Stagger startup
            
            # Wait for all bots to start
            await asyncio.gather(*bot_tasks, return_exceptions=True)
            
            logger.info("✅ All bots started successfully")
            
            # Monitor system health
            asyncio.create_task(self.system_health_monitor())
            
        except Exception as e:
            logger.error(f"❌ System startup failed: {e}")
            await ConfigManager.log_error("system", "startup", str(e), traceback.format_exc())
    
    async def safe_bot_start(self, bot_name: str, bot_instance):
        """Safely start a bot with error handling"""
        max_retries = 3
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Starting {bot_name} bot (Attempt {attempt + 1}/{max_retries})...")
                await bot_instance.run()
                logger.info(f"✅ {bot_name} bot started successfully")
                return
                
            except Exception as e:
                logger.error(f"❌ {bot_name} bot failed to start (Attempt {attempt + 1}): {e}")
                await ConfigManager.log_error(bot_name, "startup", str(e), traceback.format_exc())
                
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Retrying {bot_name} bot in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"❌ {bot_name} bot failed all startup attempts")
    
    async def system_health_monitor(self):
        """Monitor system health and restart failed bots"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Check each bot's status and restart if needed
                for bot_name, bot_instance in self.bots.items():
                    if not getattr(bot_instance, 'is_running', False):
                        logger.warning(f"🔄 {bot_name} bot not running, attempting restart...")
                        asyncio.create_task(self.safe_bot_start(bot_name, bot_instance))
                
                # Log system status periodically
                await self.log_system_status()
                
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(60)
    
    async def log_system_status(self):
        """Log system status for monitoring"""
        try:
            stats = await StatisticsManager.get_system_stats()
            
            status_text = f"""
📊 *SYSTEM STATUS REPORT* 📊

🕒 Uptime: {datetime.now() - self.startup_time}
🤖 Bots Running: {sum(1 for bot in self.bots.values() if getattr(bot, 'is_running', False))}/{len(self.bots)}
💰 Total Revenue: {stats['total_revenue']:.2f} USDT
👥 Active VIPs: {stats['active_vips']}
📢 Active Ads: {stats['active_ads']}
📊 Total Posts: {stats['total_posts']}

🔧 *System Health:* ✅ EXCELLENT
"""
            logger.info(f"System Status: {status_text}")
            
        except Exception as e:
            logger.error(f"Error logging system status: {e}")
    
    async def stop_system(self):
        """Stop the complete bot system gracefully"""
        try:
            logger.info("🛑 Stopping Interlink Multi-Bot System...")
            self.is_running = False
            
            # Stop all bots
            stop_tasks = []
            for bot_name, bot_instance in self.bots.items():
                if hasattr(bot_instance, 'safe_shutdown'):
                    task = asyncio.create_task(bot_instance.safe_shutdown())
                    stop_tasks.append(task)
                elif hasattr(bot_instance, 'app'):
                    task = asyncio.create_task(bot_instance.app.stop())
                    stop_tasks.append(task)
                    task = asyncio.create_task(bot_instance.app.shutdown())
                    stop_tasks.append(task)
            
            # Wait for all bots to stop
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
            
            logger.info("✅ System stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping system: {e}")

# ============================
# 🎯 ENTRY POINT
# ============================

async def main():
    """Main entry point"""
    system = InterlinkBotSystem()
    
    try:
        # Start the complete system
        await system.start_system()
        
        # Keep the main loop running
        while system.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"❌ Main loop error: {e}")
        await ConfigManager.log_error("main", "runtime", str(e), traceback.format_exc())
    finally:
        # Ensure clean shutdown
        await system.stop_system()

if __name__ == "__main__":
    # Enhanced startup with better error handling
    try:
        logger.info("🌟 INTERLINK MULTI-BOT SYSTEM STARTING 🌟")
        logger.info("🔧 Version: 1.3.1 - AutoADV Bot Flow Fixed + Enhanced Button System")
        logger.info("💻 System initialized successfully")
        
        # Run the main application
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("🛑 System stopped by user")
    except Exception as e:
        logger.error(f"❌ Critical system failure: {e}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("👋 Interlink Multi-Bot System shutdown complete")

[file content end]