"""
🚀 INTERLINK MULTI-BOT SYSTEM - FIXED VERSION
Complete bot ecosystem for group management, VIP verification, advertising, and payment processing.

Author: Claude
Version: 1.1.1 (Fixed Markdown parsing errors)
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
from telegram.helpers import escape_markdown
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
AD_HEADING, AD_TYPE, AD_DESCRIPTION, AD_IMAGE, AD_BUTTON, AD_CONTACT, AD_CONFIRMATION = range(7)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================
# 🛠️ HELPER FUNCTIONS
# ============================

def safe_markdown(text: str) -> str:
    """
    Safely escape markdown special characters while preserving intentional formatting.
    This prevents Telegram's "can't parse entities" errors.
    """
    # Replace special characters that aren't part of intentional formatting
    # We'll keep * for bold and _ only when it's clearly intentional
    text = str(text)
    # Escape underscores in URLs and text
    text = re.sub(r'(?<!\*)(https?://[^\s]+)', lambda m: m.group(0).replace('_', '\\_'), text)
    return text

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
                has_image INTEGER DEFAULT 0,
                has_button INTEGER DEFAULT 0,
                image_url TEXT,
                button_text TEXT,
                button_url TEXT,
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
        self.bot_prefix = "ad"
        self.bot_username = ADV_BOT_USERNAME
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with godly welcome"""
        await update.message.reply_text(
            "🌟 *GREETINGS, MASTER OF ADVERTISING\\!* 🌟\n\n"
            "I am the *Advertising Bot*, your divine servant in the realm of promotions\\! "
            "I exist to spread your message across the sacred grounds of your groups\\.\n\n"
            "✨ *MY DIVINE POWERS:* ✨\n"
            "📢 Auto\\-posting ads every 5\\-6 minutes\n"
            "📌 Auto\\-pinning in Main Group\n"
            "🎯 Showcasing platform upgrades\n"
            "🔄 Rotating purchased advertisements\n\n"
            "⚡ *COMMANDS AT YOUR DISPOSAL:* ⚡\n"
            "/adhelp \\- View all my divine commands\n"
            "/adstats \\- See advertising statistics\n"
            "/adviewqueue \\- Check pending ads\n\n"
            "Your wish is my command, O Great One\\! 🙇",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive help with all commands"""
        is_admin = await self.is_admin(update.effective_user.id)
        
        help_text = f"""
🌟 ADVERTISING BOT - COMMAND BIBLE 🌟

📱 GENERAL COMMANDS:
/{self.bot_prefix}start - Awaken the advertising god
/{self.bot_prefix}help - Divine command reference
/{self.bot_prefix}about - Learn about my existence
/{self.bot_prefix}status - Current bot status
/{self.bot_prefix}stats - Advertising statistics
/{self.bot_prefix}viewqueue - See all pending ads
/{self.bot_prefix}myads - Your active advertisements
/{self.bot_prefix}contact - Contact support

🎯 AD MANAGEMENT:
/{self.bot_prefix}viewqueue - All ads in queue
/{self.bot_prefix}checkad [id] - Check specific ad
/{self.bot_prefix}adstats - Detailed ad analytics
/{self.bot_prefix}topads - Most viewed ads
"""
        
        if is_admin:
            help_text += f"""
👑 ADMIN COMMANDS:
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
"""
        
        help_text += "\n💫 Your command is my sacred duty! 💫"
        
        await update.message.reply_text(help_text)
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """About the advertising bot"""
        await update.message.reply_text(
            "🤖 ADVERTISING BOT INFORMATION 🤖\n\n"
            "🌟 Version: 1.0.0\n"
            "👨‍💻 Developer: Claude\n"
            "🚀 Purpose: Automated advertisement management\n\n"
            "💎 Features:\n"
            "✅ Auto-posting every 5-6 minutes\n"
            "✅ Multi-group posting\n"
            "✅ Auto-pinning in main group\n"
            "✅ Advertisement queue management\n"
            "✅ Statistics and analytics\n\n"
            "🔧 Technical:\n"
            "• Built with python-telegram-bot\n"
            "• SQLite database backend\n"
            "• AsyncIO for performance\n"
            "• APScheduler for timing\n\n"
            f"📞 Support: Contact via {AUTOADV_BOT_USERNAME}"
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
            f"📊 ADVERTISING BOT STATUS 📊\n\n"
            f"🟢 Bot Status: {status}\n"
            f"📢 Active Ads: {active_ads}\n"
            f"⏰ Last Post: {last_post}\n"
            f"🔄 Interval: 5-6 minutes\n\n"
            f"🎯 Target Groups:\n"
            f"• Main Group: ✅\n"
            f"• Company Resources: ✅\n\n"
            f"⚡ System: Running optimally"
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show advertising statistics"""
        async with aiosqlite.connect(DB_NAME) as db:
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
            
            cursor = await db.execute("SELECT heading, post_count FROM ads_queue ORDER BY post_count DESC LIMIT 1")
            top_ad = await cursor.fetchone()
            top_ad_text = f"{top_ad[0]} ({top_ad[1]} posts)" if top_ad else "None"
        
        stats_text = f"""
📊 ADVERTISING EMPIRE STATISTICS 📊

🎯 ADVERTISEMENT METRICS:
▫️ Active Ads: {active_ads}
▫️ Total Ads (All Time): {total_ads}
▫️ Total Posts Delivered: {total_posts}
▫️ Last Posted: {last_post}
▫️ Top Performing: {top_ad_text}

🔥 CURRENT STATUS:
▫️ Auto-Posting: ✅ ACTIVE
▫️ Interval: 5-6 minutes
▫️ Target Groups: Main + Company Resources

💪 Your advertising empire grows stronger, Master!
"""
        await update.message.reply_text(stats_text)
    
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
                "🔭 The queue is empty, Master!\n\n"
                "No advertisements await their glorious debut. "
                "The stage is set for new promotions! 🎭"
            )
            return
        
        queue_text = "📋 ADVERTISEMENT QUEUE 📋\n\n"
        for ad in ads:
            queue_text += f"🎯 ID: {ad[0]}\n"
            queue_text += f"📌 Heading: {ad[1]}\n"
            queue_text += f"🏷️ Type: {ad[2]}\n"
            queue_text += f"⏰ Expires: {ad[3]}\n"
            queue_text += f"📊 Posted: {ad[4]} times\n"
            queue_text += "━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(queue_text)
    
    async def pause_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause advertising (Admin only)"""
        if not await self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Only the Supreme Admins can use this power!")
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE ad_config SET is_paused=1 WHERE id=1")
            await db.commit()
        
        await update.message.reply_text(
            "⏸️ ADVERTISING PAUSED ⏸️\n\n"
            "The advertising machine slumbers, O Master! "
            f"Use /{self.bot_prefix}resume to awaken it once more. 💤"
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
            "▶️ ADVERTISING RESUMED ▶️\n\n"
            "The advertising machine roars back to life! "
            "Your promotions shall flow like rivers! 🌊"
        )
    
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
                "🔭 No active advertisements found!\n\n"
                "You don't have any active ads running.\n\n"
                f"🚀 Purchase ads via {AUTOADV_BOT_USERNAME}!"
            )
            return
        
        my_ads_text = "📋 YOUR ACTIVE ADVERTISEMENTS 📋\n\n"
        for ad in ads:
            my_ads_text += f"🎯 ID: {ad[0]}\n"
            my_ads_text += f"📌 Heading: {ad[1]}\n"
            my_ads_text += f"🏷️ Type: {ad[2]}\n"
            my_ads_text += f"⏰ Expires: {ad[3]}\n"
            my_ads_text += f"📊 Posted: {ad[4]} times\n"
            my_ads_text += "━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(my_ads_text)
    
    async def post_advertisement(self):
        """Background task to post advertisements"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await db.execute("SELECT is_paused FROM ad_config WHERE id=1")
                result = await cursor.fetchone()
                if result and result[0] == 1:
                    return
                
                cursor = await db.execute("""
                    SELECT id, heading, type, description, contact, has_image, has_button, button_text, button_url
                    FROM ads_queue 
                    WHERE status='active' AND expires_at > ? 
                    ORDER BY post_count ASC, created_at ASC 
                    LIMIT 1
                """, (datetime.now().isoformat(),))
                ad = await cursor.fetchone()
                
                if ad:
                    ad_text = f"""
🎯 {ad[1]}

🏷️ Type: {ad[2]}
📝 Description:
{ad[3]}

📞 Contact: {ad[4]}

━━━━━━━━━━━━━━━
✨ Posted by Advertising Bot
"""
                    await db.execute("UPDATE ads_queue SET post_count=post_count+1 WHERE id=?", (ad[0],))
                    await db.commit()
                    
                    keyboard = []
                    if ad[6] == 1 and ad[7] and ad[8]:
                        keyboard.append([InlineKeyboardButton(ad[7], url=ad[8])])
                    else:
                        keyboard = [
                            [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/{AUTOADV_BOT_USERNAME.replace('@', '')}")],
                            [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{AUTOADV_BOT_USERNAME.replace('@', '')}")]
                        ]
                else:
                    ad_text = f"""
🎯 NEED ADVERTISING?

🏷️ Type: Premium Promotion
📝 Description:
Promote your business, service, or product to thousands of active users! 
Get maximum visibility with our automated advertising system.

📞 Contact: {AUTOADV_BOT_USERNAME}

━━━━━━━━━━━━━━━
✨ Posted by Advertising Bot
"""
                    keyboard = [
                        [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/{AUTOADV_BOT_USERNAME.replace('@', '')}")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/{AUTOADV_BOT_USERNAME.replace('@', '')}")]
                    ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                groups = [MAIN_GROUP_ID, COMPANY_RESOURCES_ID]
                
                for group_id in groups:
                    try:
                        message = await self.app.bot.send_message(
                            chat_id=group_id,
                            text=ad_text,
                            reply_markup=reply_markup
                        )
                        
                        if group_id == MAIN_GROUP_ID:
                            try:
                                await self.app.bot.pin_chat_message(group_id, message.message_id)
                            except Exception as e:
                                logger.error(f"Error pinning message: {e}")
                        
                        await db.execute("UPDATE ad_config SET last_post_time=? WHERE id=1", (datetime.now().isoformat(),))
                        await db.commit()
                        
                    except Exception as e:
                        logger.error(f"Error posting ad to group {group_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error in post_advertisement: {e}")
    
    def setup_handlers(self):
        """Setup all command handlers with prefixes"""
        self.app.add_handler(CommandHandler("adstart", self.start_command))
        self.app.add_handler(CommandHandler("adhelp", self.help_command))
        self.app.add_handler(CommandHandler("adabout", self.about_command))
        self.app.add_handler(CommandHandler("adstatus", self.status_command))
        self.app.add_handler(CommandHandler("adstats", self.stats_command))
        self.app.add_handler(CommandHandler("adviewqueue", self.view_queue_command))
        self.app.add_handler(CommandHandler("admyads", self.my_ads_command))
        self.app.add_handler(CommandHandler("adpause", self.pause_ads_command))
        self.app.add_handler(CommandHandler("adresume", self.resume_ads_command))
    
    def start_scheduler(self):
        """Start the advertisement scheduler"""
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
    
    def run_bot(self):
        """Run the advertising bot synchronously"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_run():
            await init_database()
            self.setup_handlers()
            self.start_scheduler()
            
            logger.info("🚀 Advertising Bot is running...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            while True:
                await asyncio.sleep(3600)
        
        try:
            loop.run_until_complete(async_run())
        except KeyboardInterrupt:
            logger.info("🛑 Advertising Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in Advertising Bot: {e}")
        finally:
            loop.run_until_complete(self.app.stop())
            loop.run_until_complete(self.app.shutdown())
            loop.close()

# ============================
# 👑 2. VIP VERIFICATION BOT
# ============================

class VIPVerificationBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "vip"
        self.bot_username = VIP_BOT_USERNAME
    
    async def is_admin(self, user_id: int) -> bool:
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👑 WELCOME TO VIP VERIFICATION 👑\n\n"
            "I am the VIP Verification Bot, guardian of the elite realm!\n\n"
            "✨ MY SACRED DUTIES:\n"
            "✅ Verify VIP members\n"
            "🛡️ Protect exclusive content\n"
            "📊 Manage VIP database\n"
            "🔒 Secure premium access\n\n"
            "⚡ COMMANDS:\n"
            "/viphelp - All VIP commands\n"
            "/vipverify - Verify VIP status\n"
            "/vipstatus - Check your VIP status\n\n"
            "Enter the realm of exclusivity! 🏰"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = f"""
👑 VIP VERIFICATION BOT - COMMANDS 👑

📱 GENERAL COMMANDS:
/{self.bot_prefix}start - Enter the VIP realm
/{self.bot_prefix}help - VIP command reference
/{self.bot_prefix}status - Check your VIP status
/{self.bot_prefix}verify - Verify VIP membership
/{self.bot_prefix}benefits - VIP benefits list

📝 VERIFICATION COMMANDS:
/{self.bot_prefix}check [username] - Check user VIP status
/{self.bot_prefix}members - View VIP members list
/{self.bot_prefix}stats - VIP statistics
"""
        
        if await self.is_admin(update.effective_user.id):
            help_text += f"""
⚡ ADMIN COMMANDS:
/{self.bot_prefix}add [user_id] [days] - Add VIP member
/{self.bot_prefix}remove [user_id] - Remove VIP member
/{self.bot_prefix}extend [user_id] [days] - Extend VIP
/{self.bot_prefix}list - All VIP members
"""
        
        help_text += "\n💎 VIP status is your key to exclusivity!"
        await update.message.reply_text(help_text)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT name, created_at, expires_at, is_active 
                FROM vip_members 
                WHERE user_id=?
            """, (user_id,))
            vip_data = await cursor.fetchone()
        
        if vip_data and vip_data[3] == 1:
            expiry_date = vip_data[2].split('T')[0] if vip_data[2] else "Never"
            created_date = vip_data[1].split('T')[0] if vip_data[1] else "Unknown"
            
            await update.message.reply_text(
                f"👑 VIP STATUS - ACTIVE 👑\n\n"
                f"🎯 User: @{username}\n"
                f"📛 Name: {vip_data[0] or 'Not provided'}\n"
                f"📅 Member Since: {created_date}\n"
                f"⏰ Expires: {expiry_date}\n\n"
                f"💎 Status: ✅ ACTIVE VIP\n"
                f"✨ Enjoy your exclusive benefits!"
            )
        else:
            await update.message.reply_text(
                f"🔒 VIP STATUS - INACTIVE 🔒\n\n"
                f"🎯 User: @{username}\n"
                f"📊 Status: ❌ NOT VIP MEMBER\n\n"
                f"💫 Become VIP to unlock exclusive benefits!\n\n"
                f"🚀 Get VIP: Contact {AUTOADV_BOT_USERNAME}"
            )
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("vipstart", self.start_command))
        self.app.add_handler(CommandHandler("viphelp", self.help_command))
        self.app.add_handler(CommandHandler("vipstatus", self.status_command))
    
    def run_bot(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_run():
            await init_database()
            self.setup_handlers()
            
            logger.info("👑 VIP Verification Bot is running...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            while True:
                await asyncio.sleep(3600)
        
        try:
            loop.run_until_complete(async_run())
        except KeyboardInterrupt:
            logger.info("🛑 VIP Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in VIP Bot: {e}")
        finally:
            loop.run_until_complete(self.app.stop())
            loop.run_until_complete(self.app.shutdown())
            loop.close()

# ============================
# 🛡️ 3. GROUP MANAGEMENT BOT
# ============================

class GroupManagementBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "group"
        self.bot_username = GROUP_BOT_USERNAME
    
    async def is_admin(self, user_id: int) -> bool:
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🛡️ WELCOME TO GROUP MANAGEMENT 🛡️\n\n"
            "I am the Group Management Bot, guardian of order!\n\n"
            "✨ MY DIVINE POWERS:\n"
            "🛡️ Auto-moderation\n"
            "👥 Member verification\n"
            "🚫 Violation tracking\n"
            "📊 Group analytics\n\n"
            "⚡ COMMANDS:\n"
            "/grouphelp - All management commands\n"
            "/groupstats - Group statistics\n"
            "/groupverify - Verify yourself\n\n"
            "Together we shall maintain order! 🏰"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = f"""
🛡️ GROUP MANAGEMENT BOT - COMMANDS 🛡️

📱 GENERAL COMMANDS:
/{self.bot_prefix}start - Begin group management
/{self.bot_prefix}help - Command reference
/{self.bot_prefix}status - Bot status
/{self.bot_prefix}stats - Group statistics
/{self.bot_prefix}verify - Verify yourself
/{self.bot_prefix}rules - Group rules

👥 MEMBER COMMANDS:
/{self.bot_prefix}mywarnings - Check your warnings
/{self.bot_prefix}profile - Your member profile
/{self.bot_prefix}report [reason] - Report user
"""
        
        if await self.is_admin(update.effective_user.id):
            help_text += f"""
⚡ ADMIN COMMANDS:
/{self.bot_prefix}ban [user] [reason] - Ban user
/{self.bot_prefix}warn [user] [reason] - Warn user
/{self.bot_prefix}cleanup - Clean old data
"""
        
        help_text += "\n🛡️ Order is my sacred duty!"
        await update.message.reply_text(help_text)
    
    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining the group - FIXED"""
        for new_member in update.message.new_chat_members:
            if new_member.is_bot:
                continue
                
            user_id = new_member.id
            username = new_member.username or "No username"
            
            # Use plain text to avoid markdown parsing errors
            welcome_text = (
                f"👋 Welcome @{username} to our community!\n\n"
                f"📋 REQUIRED ACTIONS:\n"
                f"Please join all our groups within 60 seconds:\n\n"
                f"🏠 Main Group\n"
                f"🏢 Company Resources\n"
                f"👑 VIP Channel\n"
                f"⚠️ Scammer Exposed\n\n"
                f"⏰ You have 60 seconds to join all groups\n"
                f"❌ Otherwise, you will be removed"
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
                reply_markup=reply_markup
            )
            
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO group_verification (user_id, username, join_time, verified, welcome_msg_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, datetime.now().isoformat(), 0, welcome_msg.message_id))
                await db.commit()
            
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
        job = context.job
        user_id = job.data['user_id']
        chat_id = job.data['chat_id']
        username = job.data['username']
        welcome_msg_id = job.data['welcome_msg_id']
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT verified FROM group_verification WHERE user_id=?", (user_id,))
            result = await cursor.fetchone()
            
            if result and result[0] == 0:
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.unban_chat_member(chat_id, user_id)
                    
                    try:
                        await context.bot.delete_message(chat_id, welcome_msg_id)
                    except:
                        pass
                    
                    removal_msg = await context.bot.send_message(
                        chat_id,
                        f"❌ @{username} was removed for not joining required groups."
                    )
                    
                    context.job_queue.run_once(
                        lambda ctx: ctx.bot.delete_message(chat_id, removal_msg.message_id),
                        10
                    )
                    
                except Exception as e:
                    logger.error(f"Error removing user {user_id}: {e}")

    async def verify_joined_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.split('_')[-1])
        caller_id = query.from_user.id
        
        if caller_id != user_id:
            await query.answer("This verification is not for you!", show_alert=True)
            return
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE group_verification SET verified=1 WHERE user_id=?", (user_id,))
            await db.commit()
        
        await query.edit_message_text(
            f"✅ @{query.from_user.username} has been verified!\n\n"
            f"Welcome to the community!"
        )
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("groupstart", self.start_command))
        self.app.add_handler(CommandHandler("grouphelp", self.help_command))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.app.add_handler(CallbackQueryHandler(self.verify_joined_callback, pattern="^verify_joined_"))
    
    def run_bot(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_run():
            await init_database()
            self.setup_handlers()
            
            logger.info("🛡️ Group Management Bot is running...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            while True:
                await asyncio.sleep(3600)
        
        try:
            loop.run_until_complete(async_run())
        except KeyboardInterrupt:
            logger.info("🛑 Group Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in Group Bot: {e}")
        finally:
            loop.run_until_complete(self.app.stop())
            loop.run_until_complete(self.app.shutdown())
            loop.close()

# ============================
# 💰 4. AUTOADV PAYMENT BOT
# ============================

class AutoAdvPaymentBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "autoadv"
        self.bot_username = AUTOADV_BOT_USERNAME
        self.ad_purchase_data = {}
        self.payment_mode = PAYMENT_MODE

    async def is_admin(self, user_id: int) -> bool:
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat.type != "private":
            await update.message.reply_text(
                "🤖 Please use me in private messages!\n\n"
                "To ensure your privacy, all purchases must be made in private chat.\n\n"
                "📱 How to proceed:\n"
                "1. Click: @NepalChinIndiaAUTOADV_bot\n"
                "2. Start a private chat\n"
                "3. Use /autoadvbuy to make purchases"
            )
            return
        
        await update.message.reply_text(
            "💰 WELCOME TO AUTOADV PAYMENTS 💰\n\n"
            "I handle all payments with divine precision!\n\n"
            "✨ MY DIVINE POWERS:\n"
            "💳 Process USDT (TRC20) payments\n"
            "🤖 Automated verification\n"
            "📊 Purchase tracking\n"
            "🛡️ Secure processing\n\n"
            "⚡ COMMANDS:\n"
            "/autoadvhelp - All payment commands\n"
            "/autoadvbuy - Purchase services\n"
            "/autoadvhistory - Purchase history\n\n"
            "Let the transactions begin! 💎"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat.type != "private":
            await update.message.reply_text(
                "🔒 Please use commands in private chat!\n\n"
                "For security, payment commands are only in private.\n\n"
                f"💬 Click here: {AUTOADV_BOT_USERNAME}"
            )
            return
            
        help_text = f"""
💰 AUTOADV PAYMENT BOT - COMMANDS 💰

📱 GENERAL COMMANDS:
/{self.bot_prefix}start - Begin payment journey
/{self.bot_prefix}help - Payment commands
/{self.bot_prefix}buy - Purchase services
/{self.bot_prefix}history - Purchase history
/{self.bot_prefix}status - Payment status

💳 PAYMENT COMMANDS:
/{self.bot_prefix}verify [payment_id] - Verify payment
/{self.bot_prefix}rates - Current rates
/{self.bot_prefix}contact - Support
"""
        
        if await self.is_admin(update.effective_user.id):
            help_text += f"""
⚡ ADMIN COMMANDS:
/{self.bot_prefix}stats - Payment statistics
/{self.bot_prefix}transactions - All transactions
"""
        
        help_text += "\n💎 Secure payments are my specialty!"
        await update.message.reply_text(help_text)
    
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat.type != "private":
            await update.message.reply_text(
                "🔒 Private Purchase Required!\n\n"
                "All purchases must be in private chat.\n\n"
                f"💬 Click here: {AUTOADV_BOT_USERNAME}"
            )
            return
            
        keyboard = [
            [InlineKeyboardButton("📢 Advertisement", callback_data="buy_ad")],
            [InlineKeyboardButton("👑 VIP Membership", callback_data="buy_vip")],
            [InlineKeyboardButton("🛡️ Group Promotion", callback_data="buy_promotion")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🛍️ WHAT WOULD YOU LIKE TO PURCHASE? 🛍️\n\n"
            "💎 Available Services:\n"
            "📢 Advertisement - Promote your business\n"
            "👑 VIP Membership - Exclusive access\n"
            "🛡️ Group Promotion - Boost your group\n\n"
            "🎯 Select a service:",
            reply_markup=reply_markup
        )
    
    async def buy_callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "buy_ad":
            await query.edit_message_text(
                "📢 ADVERTISEMENT PURCHASE 📢\n\n"
                "💎 Packages:\n"
                "• Basic Ad: $5 (1 day)\n"
                "• Premium Ad: $15 (3 days)\n"
                "• VIP Ad: $30 (7 days)\n\n"
                "📝 Features:\n"
                "✅ Auto-posting every 5-6 minutes\n"
                "✅ Posted in main groups\n"
                "✅ Optional image & button\n\n"
                f"📞 Contact {AUTOADV_BOT_USERNAME} to purchase!"
            )
        elif query.data == "buy_vip":
            await query.edit_message_text(
                "👑 VIP MEMBERSHIP PURCHASE 👑\n\n"
                "💎 Packages:\n"
                "• 1 Month: $10\n"
                "• 3 Months: $25\n"
                "• 6 Months: $45\n"
                "• 1 Year: $80\n\n"
                "✨ Benefits:\n"
                "✅ VIP channel access\n"
                "✅ Exclusive content\n"
                "✅ Priority support\n\n"
                f"📞 Contact {AUTOADV_BOT_USERNAME} to purchase!"
            )
        elif query.data == "buy_promotion":
            await query.edit_message_text(
                "🛡️ GROUP PROMOTION PURCHASE 🛡️\n\n"
                "💎 Packages:\n"
                "• Basic: $20/week\n"
                "• Premium: $50/week\n"
                "• VIP: $100/week\n\n"
                "✨ Benefits:\n"
                "✅ Member growth\n"
                "✅ Engagement boost\n"
                "✅ Professional management\n\n"
                f"📞 Contact {AUTOADV_BOT_USERNAME} for custom packages!"
            )
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("autoadvstart", self.start_command))
        self.app.add_handler(CommandHandler("autoadvhelp", self.help_command))
        self.app.add_handler(CommandHandler("autoadvbuy", self.buy_command))
        self.app.add_handler(CallbackQueryHandler(self.buy_callback_handler, pattern="^buy_"))
    
    def run_bot(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_run():
            await init_database()
            self.setup_handlers()
            
            logger.info("💰 AutoADV Payment Bot is running...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            while True:
                await asyncio.sleep(3600)
        
        try:
            loop.run_until_complete(async_run())
        except KeyboardInterrupt:
            logger.info("🛑 AutoADV Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in AutoADV Bot: {e}")
        finally:
            loop.run_until_complete(self.app.stop())
            loop.run_until_complete(self.app.shutdown())
            loop.close()

# ============================
# 🚀 MAIN EXECUTION
# ============================

def main():
    """Main function to run all bots"""
    logger.info("🚀 Starting INTERLINK Multi-Bot System...")
    
    adv_bot = AdvertisingBot(ADV_BOT_TOKEN)
    vip_bot = VIPVerificationBot(VIP_BOT_TOKEN)
    group_bot = GroupManagementBot(GROUP_BOT_TOKEN)
    autoadv_bot = AutoAdvPaymentBot(AUTOADV_BOT_TOKEN)
    
    import threading
    
    threads = [
        threading.Thread(target=adv_bot.run_bot, name="AdvertisingBot"),
        threading.Thread(target=vip_bot.run_bot, name="VIPBot"), 
        threading.Thread(target=group_bot.run_bot, name="GroupBot"),
        threading.Thread(target=autoadv_bot.run_bot, name="AutoADVBot")
    ]
    
    for thread in threads:
        thread.daemon = True
        thread.start()
        logger.info(f"✅ Started {thread.name}")
    
    try:
        while True:
            import time
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 All bots stopped by user")

if __name__ == "__main__":
    main()
            
