"""
🚀 INTERLINK MULTI-BOT SYSTEM - ENHANCED VERSION
Complete bot ecosystem with fixed purchase flows, DM protection, and new features.

Author: Claude
Version: 2.0.0
Enhanced with: Purchase confirmations, DM-only protection, Image/Button options
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

# Group Links
MAIN_GROUP_LINK = "https://t.me/+bEyi7RpG_NxjZjk1"
COMPANY_RESOURCES_LINK = "https://t.me/+D9yrbrh6xTcyNGE1"
VIP_CHANNEL_LINK = "https://t.me/+bPg3y6q4E400MjE1"
SCAMMER_EXPOSED_LINK = "https://t.me/+eztpF3kA2-Y2Yzk1"

# Group IDs
MAIN_GROUP_ID = -1003097566042
VIP_CHANNEL_ID = -1003075027543
COMPANY_RESOURCES_ID = -1003145253219

# Payment Config
YOUR_USDT_ADDRESS = "TD1gmGWyWqFY5STqZW5PMRqMR46xJhj5rP"

# Admin User IDs
ADMIN_IDS = [7578682081]

# Database
DB_NAME = "interlink_bots.db"

# Enhanced Conversation states
AD_HEADING, AD_TYPE, AD_DESCRIPTION, AD_IMAGE_OPTION, AD_IMAGE_UPLOAD, AD_BUTTON_OPTION, AD_BUTTON_DETAILS, AD_CONTACT, AD_CONFIRMATION = range(9)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================
# 🛡️ DM-ONLY PROTECTION DECORATOR
# ============================

def dm_only(func):
    """Decorator to restrict commands to private messages only"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type != "private":
            bot_username = getattr(context.bot, 'username', AUTOADV_BOT_USERNAME)
            await update.message.reply_text(
                "🤖 *Please use me in private messages!*\n\n"
                f"Click here to start: [Private Chat](https://t.me/{bot_username.replace('@', '')})",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def dm_only_callback(func):
    """Decorator to restrict callbacks to private messages only"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        query = update.callback_query
        if query.message.chat.type != "private":
            bot_username = getattr(context.bot, 'username', AUTOADV_BOT_USERNAME)
            await query.edit_message_text(
                "🤖 *Please use me in private messages!*\n\n"
                f"Click here to start: [Private Chat](https://t.me/{bot_username.replace('@', '')})",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ============================
# 🗄️ DATABASE INITIALIZATION
# ============================

async def init_database():
    """Initialize all database tables with enhanced features"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Enhanced Advertising Bot Tables
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
                has_image INTEGER DEFAULT 0,
                image_file_id TEXT,
                has_button INTEGER DEFAULT 0,
                button_text TEXT,
                button_url TEXT
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
        
        # Enhanced Purchases Table
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
                completed_at TIMESTAMP,
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
        logger.info("✅ Enhanced database initialized successfully")

# ============================
# 🤖 1. ENHANCED ADVERTISING BOT
# ============================

class EnhancedAdvertisingBot:
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
        """Start command with enhanced welcome"""
        await update.message.reply_text(
            "🌟 *ENHANCED ADVERTISING BOT* 🌟\n\n"
            "I am the *Enhanced Advertising Bot* with new features! "
            "I exist to spread your message across the sacred grounds of your groups.\n\n"
            "✨ *ENHANCED POWERS:* ✨\n"
            "📢 Auto-posting ads every 5-6 minutes\n"
            "🖼️ Image advertisement support\n"
            "🔘 Interactive button options\n"
            "📌 Auto-pinning in Main Group\n"
            "🎯 Enhanced ad formatting\n\n"
            "⚡ *ENHANCED COMMANDS:* ⚡\n"
            "/adhelp - View all enhanced commands\n"
            "/adstats - See enhanced statistics\n"
            "/adviewqueue - Check pending ads with features\n\n"
            "Your wish is my command, O Great One! 🙇",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced help with all commands"""
        is_admin = await self.is_admin(update.effective_user.id)
        
        user_commands = f"""
🌟 *ENHANCED ADVERTISING BOT - COMMAND BIBLE* 🌟

✨ *NEW FEATURES:*
• Image Advertisement Support 🖼️
• Interactive Button Options 🔘
• Enhanced Ad Formatting 🎨
• Better Status Tracking 📊

📱 *GENERAL COMMANDS:*
/{self.bot_prefix}start - Awaken the enhanced advertising god
/{self.bot_prefix}help - Divine command reference
/{self.bot_prefix}about - Learn about enhanced features
/{self.bot_prefix}status - Current enhanced bot status
/{self.bot_prefix}stats - Enhanced advertising statistics
/{self.bot_prefix}viewqueue - See all pending ads with features
/{self.bot_prefix}myads - Your active advertisements
/{self.bot_prefix}contact - Contact enhanced support

🎯 *AD MANAGEMENT:*
/{self.bot_prefix}viewqueue - All ads in queue with features
/{self.bot_prefix}checkad [id] - Check specific ad with details
/{self.bot_prefix}adstats - Detailed ad analytics
/{self.bot_prefix}topads - Most viewed ads
"""
        
        admin_commands = f"""
👑 *ENHANCED ADMIN COMMANDS:*
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
    
    async def post_advertisement(self):
        """Enhanced background task to post advertisements with new features"""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                # Check if paused
                cursor = await db.execute("SELECT is_paused FROM ad_config WHERE id=1")
                result = await cursor.fetchone()
                if result and result[0] == 1:
                    return
                
                # Get next ad with enhanced features
                cursor = await db.execute("""
                    SELECT id, heading, type, description, contact, has_image, image_file_id, has_button, button_text, button_url 
                    FROM ads_queue 
                    WHERE status='active' AND expires_at > ? 
                    ORDER BY post_count ASC, created_at ASC 
                    LIMIT 1
                """, (datetime.now().isoformat(),))
                ad = await cursor.fetchone()
                
                if ad:
                    # Enhanced ad text with feature indicators
                    ad_text = f"""
🎯 *{ad[1]}* {'🖼️' if ad[5] == 1 else ''} {'🔘' if ad[7] == 1 else ''}

🏷️ *Type:* {ad[2]}
📝 *Description:*
{ad[3]}

📞 *Contact:* {ad[4]}

━━━━━━━━━━━━━━━━
✨ _Posted by Enhanced Advertising Bot_
"""
                    # Update post count
                    await db.execute("UPDATE ads_queue SET post_count=post_count+1 WHERE id=?", (ad[0],))
                    await db.commit()
                    
                    # Enhanced keyboard with optional button
                    keyboard = []
                    if ad[7] == 1 and ad[8] and ad[9]:  # has_button, button_text, button_url
                        keyboard.append([InlineKeyboardButton(ad[8], url=ad[9])])
                    
                    keyboard.extend([
                        [InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=buy_ad")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=report_scammer")]
                    ])
                    
                else:
                    # Enhanced default ad
                    ad_text = f"""
🎯 *NEED ADVERTISING?* 🖼️🔘

🏷️ *Type:* Premium Promotion
📝 *Description:*
Promote your business with enhanced features! 
Get image support and interactive buttons for maximum engagement.

📞 *Contact:* {AUTOADV_BOT_USERNAME}

━━━━━━━━━━━━━━━━
✨ _Posted by Enhanced Advertising Bot_
"""
                    keyboard = [
                        [InlineKeyboardButton("📢 Post Enhanced Ad", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=buy_ad")],
                        [InlineKeyboardButton("⚠️ Report Scammer", url=f"https://t.me/NepalChinIndiaAUTOADV_bot?start=report_scammer")]
                    ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Post to groups with enhanced features
                groups = [MAIN_GROUP_ID, COMPANY_RESOURCES_ID]
                
                for group_id in groups:
                    try:
                        if ad and ad[5] == 1 and ad[6]:  # has_image and image_file_id
                            # Send enhanced ad with image
                            message = await self.app.bot.send_photo(
                                chat_id=group_id,
                                photo=ad[6],
                                caption=ad_text,
                                reply_markup=reply_markup,
                                parse_mode=ParseMode.MARKDOWN
                            )
                        else:
                            # Send text-only enhanced ad
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
            logger.error(f"Error in enhanced post_advertisement: {e}")
    
    async def view_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced view queue with feature indicators"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT id, heading, type, expires_at, post_count, has_image, has_button 
                FROM ads_queue WHERE status='active' 
                ORDER BY created_at DESC LIMIT 10
            """)
            ads = await cursor.fetchall()
        
        if not ads:
            await update.message.reply_text(
                "📭 *The enhanced queue is empty, Master!*\n\n"
                "No enhanced advertisements await their glorious debut. "
                "The stage is set for new promotions with images and buttons! 🎭",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        queue_text = "📋 *ENHANCED ADVERTISEMENT QUEUE* 📋\n\n"
        for ad in ads:
            features = ""
            if ad[5] == 1:  # has_image
                features += "🖼️ "
            if ad[6] == 1:  # has_button
                features += "🔘 "
                
            queue_text += f"🎯 *ID:* {ad[0]} {features}\n"
            queue_text += f"📌 *Heading:* {ad[1]}\n"
            queue_text += f"🏷️ *Type:* {ad[2]}\n"
            queue_text += f"⏰ *Expires:* {ad[3]}\n"
            queue_text += f"📊 *Posted:* {ad[4]} times\n"
            queue_text += "━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(queue_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced statistics with feature metrics"""
        async with aiosqlite.connect(DB_NAME) as db:
            # Total ads
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue WHERE status='active'")
            active_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue")
            total_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(post_count) FROM ads_queue")
            result = await cursor.fetchone()
            total_posts = result[0] if result[0] else 0
            
            # Enhanced feature stats
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue WHERE has_image=1")
            image_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM ads_queue WHERE has_button=1")
            button_ads = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT last_post_time FROM ad_config WHERE id=1")
            result = await cursor.fetchone()
            last_post = result[0] if result else "Never"
            
            # Top ad
            cursor = await db.execute("SELECT heading, post_count FROM ads_queue ORDER BY post_count DESC LIMIT 1")
            top_ad = await cursor.fetchone()
            top_ad_text = f"{top_ad[0]} ({top_ad[1]} posts)" if top_ad else "None"
        
        stats_text = f"""
📊 *ENHANCED ADVERTISING EMPIRE STATISTICS* 📊

🎯 *ADVERTISEMENT METRICS:*
▫️ Active Ads: {active_ads}
▫️ Total Ads (All Time): {total_ads}
▫️ Total Posts Delivered: {total_posts}
▫️ Last Posted: {last_post}
▫️ Top Performing: {top_ad_text}

✨ *ENHANCED FEATURES:*
▫️ Ads with Images: {image_ads}
▫️ Ads with Buttons: {button_ads}
▫️ Feature Usage: {((image_ads + button_ads) / (active_ads * 2)) * 100 if active_ads > 0 else 0:.1f}%

🔥 *CURRENT STATUS:*
▫️ Auto-Posting: ✅ ACTIVE
▫️ Enhanced Features: ✅ ENABLED
▫️ Interval: 5-6 minutes
▫️ Target Groups: Main + Company Resources

💪 *Your enhanced advertising empire grows stronger, Master!*
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    def setup_handlers(self):
        """Setup enhanced command handlers"""
        self.app.add_handler(CommandHandler("adstart", self.start_command))
        self.app.add_handler(CommandHandler("adhelp", self.help_command))
        self.app.add_handler(CommandHandler("adstats", self.stats_command))
        self.app.add_handler(CommandHandler("adviewqueue", self.view_queue_command))
    
    def start_scheduler(self):
        """Start the enhanced advertisement scheduler"""
        try:
            self.scheduler.add_job(
                self.post_advertisement,
                'interval',
                minutes=random.randint(5, 6),
                id='enhanced_ad_posting'
            )
            self.scheduler.start()
            logger.info("✅ Enhanced advertising scheduler started successfully")
        except Exception as e:
            logger.error(f"❌ Error starting enhanced scheduler: {e}")
    
    def run_bot(self):
        """Run the enhanced advertising bot"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_run():
            await init_database()
            self.setup_handlers()
            self.start_scheduler()
            
            logger.info("🚀 Enhanced Advertising Bot is running...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            while True:
                await asyncio.sleep(3600)
        
        try:
            loop.run_until_complete(async_run())
        except KeyboardInterrupt:
            logger.info("🛑 Enhanced Advertising Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in Enhanced Advertising Bot: {e}")
        finally:
            loop.run_until_complete(self.app.stop())
            loop.run_until_complete(self.app.shutdown())
            loop.close()

# ============================
# 👑 2. ENHANCED VIP VERIFICATION BOT
# ============================

class EnhancedVIPVerificationBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "vip"
        self.bot_username = VIP_BOT_USERNAME
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command for VIP verification"""
        await update.message.reply_text(
            "👑 *ENHANCED VIP VERIFICATION* 👑\n\n"
            "I am the *Enhanced VIP Verification Bot* with better tracking! "
            "I verify and manage VIP members with divine precision.\n\n"
            "✨ *ENHANCED FEATURES:* ✨\n"
            "✅ Enhanced verification system\n"
            "🛡️ Better member tracking\n"
            "📊 Improved analytics\n"
            "🔒 Secure premium access\n\n"
            "⚡ *ENHANCED COMMANDS:* ⚡\n"
            "/viphelp - All enhanced VIP commands\n"
            "/vipverify - Enhanced verification\n"
            "/vipstatus - Enhanced status checking\n"
            "/vipmembers - View VIP members\n\n"
            "Enter the realm of exclusivity, O Worthy One! 🏰",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced VIP verification"""
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
            days_remaining = (datetime.fromisoformat(vip_data[1]) - datetime.now()).days if vip_data[1] else 999
            
            status_icon = "🟢" if days_remaining > 7 else "🟡" if days_remaining > 1 else "🔴"
            
            await update.message.reply_text(
                f"✅ *ENHANCED VIP VERIFICATION SUCCESSFUL* ✅\n\n"
                f"{status_icon} *Status:* ACTIVE VIP MEMBER\n"
                f"👑 Welcome back, VIP member!\n"
                f"🎯 Username: @{username}\n"
                f"⏰ VIP Expiry: {expiry_date}\n"
                f"📅 Days Remaining: {days_remaining}\n\n"
                f"💎 Your enhanced VIP status is active and verified!\n"
                f"✨ Enjoy your exclusive access!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ *ENHANCED VIP VERIFICATION FAILED* ❌\n\n"
                f"🔒 User: @{username}\n"
                f"📊 Status: NOT VIP MEMBER\n\n"
                f"💫 To become a VIP member:\n"
                f"1. Contact {AUTOADV_BOT_USERNAME}\n"
                f"2. Complete enhanced payment\n"
                f"3. Get verified instantly\n\n"
                f"🚀 Unlock exclusive enhanced benefits today!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def setup_handlers(self):
        """Setup enhanced VIP handlers"""
        self.app.add_handler(CommandHandler("vipstart", self.start_command))
        self.app.add_handler(CommandHandler("vipverify", self.verify_command))
    
    def run_bot(self):
        """Run the enhanced VIP verification bot"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_run():
            await init_database()
            self.setup_handlers()
            
            logger.info("👑 Enhanced VIP Verification Bot is running...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            while True:
                await asyncio.sleep(3600)
        
        try:
            loop.run_until_complete(async_run())
        except KeyboardInterrupt:
            logger.info("🛑 Enhanced VIP Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in Enhanced VIP Bot: {e}")
        finally:
            loop.run_until_complete(self.app.stop())
            loop.run_until_complete(self.app.shutdown())
            loop.close()

# ============================
# 💰 3. ENHANCED AUTOADV PAYMENT BOT
# ============================

class EnhancedAutoAdvPaymentBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.bot_prefix = "autoadv"
        self.bot_username = AUTOADV_BOT_USERNAME
        self.ad_purchase_data = {}
        self.payment_mode = PAYMENT_MODE

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    @dm_only
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command with DM protection"""
        await update.message.reply_text(
            "💰 *ENHANCED AUTOADV PAYMENTS* 💰\n\n"
            "I am the *Enhanced AutoADV Payment Bot* with advanced features! "
            "I handle all payments with divine precision and enhanced security.\n\n"
            "✨ *ENHANCED FEATURES:* ✨\n"
            "💳 Secure DM-only transactions\n"
            "🖼️ Image advertisement support\n"
            "🔘 Interactive button options\n"
            "✅ Enhanced confirmation system\n"
            "🛡️ Better error handling\n\n"
            "⚡ *COMMANDS AT YOUR DISPOSAL:* ⚡\n"
            "/autoadvhelp - All enhanced commands\n"
            "/autoadvbuy - Purchase with new features\n"
            "/autoadvstatus - Enhanced payment status\n"
            "/autoadvhistory - Detailed purchase history\n\n"
            "Let the enhanced transactions begin! 💎",
            parse_mode=ParseMode.MARKDOWN
        )
    
    @dm_only
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced help command"""
        help_text = """
💰 *ENHANCED AUTOADV PAYMENT BOT - COMMAND BIBLE* 💰

✨ *NEW ENHANCED FEATURES:*
• DM-Only Protection 🛡️
• Image Advertisement Support 🖼️
• Interactive Button Options 🔘
• Enhanced Confirmation System ✅
• Better Error Handling ⚠️

📱 *GENERAL COMMANDS:*
/autoadvstart - Begin enhanced payment journey
/autoadvhelp - Enhanced command reference
/autoadvabout - About enhanced system
/autoadvstatus - Enhanced payment status
/autoadvbuy - Enhanced purchase flow
/autoadvhistory - Detailed purchase history
/autoadvbalance - Your enhanced balance

💳 *ENHANCED PAYMENT FLOW:*
• Advertisement with images and buttons
• VIP membership with auto-activation
• Group promotion packages
• Custom service options

🎯 *SECURITY FEATURES:*
• DM-only transaction protection
• Enhanced confirmation messages
• Better status tracking
• Improved error handling

💎 *Experience the enhanced payment system!*
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    @dm_only
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced purchase process with DM protection"""
        keyboard = [
            [InlineKeyboardButton("📢 Enhanced Advertisement", callback_data="buy_ad")],
            [InlineKeyboardButton("👑 VIP Membership", callback_data="buy_vip")],
            [InlineKeyboardButton("🛡️ Group Promotion", callback_data="buy_promotion")],
            [InlineKeyboardButton("💰 Custom Service", callback_data="buy_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🛍️ *ENHANCED PURCHASE SYSTEM* 🛍️\n\n"
            "💎 *Enhanced Services Available:*\n"
            "📢 *Enhanced Advertisement* - With images & buttons\n"
            "👑 *VIP Membership* - Auto-activation\n"
            "🛡️ *Group Promotion* - Boost your group\n"
            "💰 *Custom Service* - Tailored solutions\n\n"
            "✨ *New Features:*\n"
            "• Image support for ads\n"
            "• Interactive buttons\n"
            "• Enhanced confirmation\n"
            "• Better status tracking\n\n"
            "🎯 *Select a service to continue:*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ============================
    # 🎯 ENHANCED ADVERTISEMENT PURCHASE FLOW
    # ============================
    
    @dm_only_callback
    async def start_ad_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start enhanced advertisement purchase conversation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        self.ad_purchase_data[user_id] = {
            'step': 'heading',
            'features': []  # Track enabled features
        }
        
        await query.edit_message_text(
            "📢 *ENHANCED ADVERTISEMENT PURCHASE* 📢\n\n"
            "✨ *New Features Available:*\n"
            "• Image upload support 🖼️\n"
            "• Interactive buttons 🔘\n"
            "• Enhanced formatting 🎨\n\n"
            "Let's create your enhanced advertisement!\n\n"
            "🎯 *Step 1/8: Advertisement Heading*\n"
            "Enter a catchy heading for your ad (max 50 characters):",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_HEADING
    
    async def receive_ad_heading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement heading with validation"""
        user_id = update.message.from_user.id
        heading = update.message.text
        
        if len(heading) > 50:
            await update.message.reply_text(
                "❌ Heading too long! Maximum 50 characters.\n"
                "Please enter a shorter heading:"
            )
            return AD_HEADING
        
        if len(heading) < 5:
            await update.message.reply_text(
                "❌ Heading too short! Minimum 5 characters.\n"
                "Please enter a more descriptive heading:"
            )
            return AD_HEADING
        
        self.ad_purchase_data[user_id]['heading'] = heading
        self.ad_purchase_data[user_id]['step'] = 'type'
        
        keyboard = [
            [InlineKeyboardButton("🛒 Product", callback_data="type_product")],
            [InlineKeyboardButton("🏢 Business", callback_data="type_business")],
            [InlineKeyboardButton("💼 Service", callback_data="type_service")],
            [InlineKeyboardButton("🎯 Promotion", callback_data="type_promotion")],
            [InlineKeyboardButton("🏠 Real Estate", callback_data="type_realestate")],
            [InlineKeyboardButton("💻 Technology", callback_data="type_technology")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ *Heading Saved:* {heading}\n\n"
            "🎯 *Step 2/8: Advertisement Type*\n"
            "Select the type of your advertisement:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_TYPE
    
    async def receive_ad_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement type with enhanced options"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        ad_type = query.data.replace('type_', '')
        
        type_display = {
            'product': '🛒 Product',
            'business': '🏢 Business', 
            'service': '💼 Service',
            'promotion': '🎯 Promotion',
            'realestate': '🏠 Real Estate',
            'technology': '💻 Technology'
        }
        
        self.ad_purchase_data[user_id]['type'] = ad_type
        self.ad_purchase_data[user_id]['step'] = 'description'
        
        await query.edit_message_text(
            f"✅ *Type Selected:* {type_display.get(ad_type, ad_type)}\n\n"
            "🎯 *Step 3/8: Advertisement Description*\n"
            "Enter the description of your advertisement:\n\n"
            "📋 *Guidelines:*\n"
            "• Maximum 300 characters\n"
            "• Be clear and descriptive\n"
            "• Include key benefits\n"
            "• Add call to action\n\n"
            "📝 *Enter your description:*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_DESCRIPTION
    
    async def receive_ad_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement description with validation"""
        user_id = update.message.from_user.id
        description = update.message.text
        
        if len(description) > 300:
            await update.message.reply_text(
                "❌ Description too long! Maximum 300 characters.\n"
                "Please shorten your description:"
            )
            return AD_DESCRIPTION
        
        if len(description) < 20:
            await update.message.reply_text(
                "❌ Description too short! Minimum 20 characters.\n"
                "Please provide more details:"
            )
            return AD_DESCRIPTION
        
        self.ad_purchase_data[user_id]['description'] = description
        self.ad_purchase_data[user_id]['step'] = 'image_option'
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Add Image (+$5)", callback_data="image_yes")],
            [InlineKeyboardButton("❌ No, Text Only", callback_data="image_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ *Description Saved!* ({len(description)}/300 characters)\n\n"
            "🎯 *Step 4/8: Add Image to Advertisement*\n"
            "Would you like to add an image to your advertisement?\n\n"
            "🖼️ *Image Benefits:*\n"
            "• 63% higher engagement\n"
            "• Better visibility in feeds\n"
            "• Professional appearance\n"
            "• Increased click-through rates\n\n"
            "💰 *Additional Cost:* $5.00\n\n"
            "Select your choice:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_IMAGE_OPTION
    
    async def receive_image_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive image option choice with cost information"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        image_choice = query.data.replace('image_', '')
        
        self.ad_purchase_data[user_id]['has_image'] = 1 if image_choice == 'yes' else 0
        
        if image_choice == 'yes':
            self.ad_purchase_data[user_id]['step'] = 'image_upload'
            self.ad_purchase_data[user_id]['features'].append('image')
            await query.edit_message_text(
                "✅ *Image Option Selected:* Yes (+$5.00)\n\n"
                "🎯 *Step 5/8: Upload Advertisement Image*\n"
                "Please upload an image for your advertisement:\n\n"
                "📋 *Requirements:*\n"
                "• Format: JPG, PNG, GIF\n"
                "• Size: Under 5MB\n"
                "• Aspect Ratio: 1:1 or 16:9 recommended\n"
                "• Quality: Clear and professional\n\n"
                "💡 *Tips for best results:*\n"
                "• Use high-quality images\n"
                "• Ensure good lighting\n"
                "• Focus on your product/service\n"
                "• Avoid text-heavy images\n\n"
                "📤 *Upload your image now:*",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_IMAGE_UPLOAD
        else:
            self.ad_purchase_data[user_id]['step'] = 'button_option'
            await query.edit_message_text(
                "✅ *Image Option Selected:* No\n\n"
                "🎯 *Step 5/8: Interactive Button*\n"
                "Would you like to add an interactive button to your advertisement?\n\n"
                "🔘 *Button Benefits:*\n"
                "• 45% higher conversion rates\n"
                "• Direct user action\n"
                "• Link to your website/service\n"
                "• Easy customer engagement\n\n"
                "Select your choice:",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_BUTTON_OPTION
    
    async def receive_image_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive uploaded image with validation"""
        user_id = update.message.from_user.id
        
        if update.message.photo:
            # Get the highest quality photo
            photo_file = update.message.photo[-1]
            self.ad_purchase_data[user_id]['image_file_id'] = photo_file.file_id
            
            # Send confirmation
            await update.message.reply_photo(
                photo=photo_file.file_id,
                caption="✅ *Image Uploaded Successfully!*\n\n"
                       "🖼️ Your image has been received and will be used in your advertisement."
            )
            
            self.ad_purchase_data[user_id]['step'] = 'button_option'
            
            keyboard = [
                [InlineKeyboardButton("✅ Yes, Add Button", callback_data="button_yes")],
                [InlineKeyboardButton("❌ No Button", callback_data="button_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎯 *Step 6/8: Interactive Button*\n"
                "Would you like to add an interactive button to your advertisement?\n\n"
                "🔘 *Button Benefits:*\n"
                "• Direct user action\n"
                "• Higher conversion rates\n"
                "• Link to your website/service\n"
                "• Easy customer engagement\n\n"
                "Select your choice:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_BUTTON_OPTION
        else:
            await update.message.reply_text(
                "❌ Please upload a valid image file (JPG/PNG/GIF).\n"
                "📤 Try uploading your image again:"
            )
            return AD_IMAGE_UPLOAD
    
    async def receive_button_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive button option choice"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        button_choice = query.data.replace('button_', '')
        
        self.ad_purchase_data[user_id]['has_button'] = 1 if button_choice == 'yes' else 0
        
        if button_choice == 'yes':
            self.ad_purchase_data[user_id]['step'] = 'button_details'
            self.ad_purchase_data[user_id]['features'].append('button')
            await query.edit_message_text(
                "✅ *Button Option Selected:* Yes\n\n"
                "🎯 *Step 7/8: Button Details*\n"
                "Please provide the button details:\n\n"
                "1. *Button Text* (e.g., 'Visit Website', 'Contact Us', 'Learn More')\n"
                "   - Maximum 20 characters\n"
                "   - Clear call to action\n\n"
                "2. *Button URL* (must start with http:// or https://)\n"
                "   - Your website link\n"
                "   - Telegram channel/group\n"
                "   - Contact page\n\n"
                "📝 *Enter button text first:*",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_BUTTON_DETAILS
        else:
            self.ad_purchase_data[user_id]['step'] = 'contact'
            await query.edit_message_text(
                "✅ *Button Option Selected:* No\n\n"
                "🎯 *Step 7/8: Contact Information*\n"
                "Enter how people can contact you:\n\n"
                "📞 *Examples:*\n"
                "• Phone: +1234567890\n"
                "• Email: your@email.com\n"
                "• Telegram: @username\n"
                "• Website: yourwebsite.com\n\n"
                "📝 *Enter your contact information:*",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_CONTACT
    
    async def receive_button_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive button details with validation"""
        user_id = update.message.from_user.id
        ad_data = self.ad_purchase_data[user_id]
        
        if 'button_text' not in ad_data:
            # First message - button text
            button_text = update.message.text
            if len(button_text) > 20:
                await update.message.reply_text(
                    "❌ Button text too long! Maximum 20 characters.\n"
                    "Please enter shorter button text:"
                )
                return AD_BUTTON_DETAILS
            
            if len(button_text) < 2:
                await update.message.reply_text(
                    "❌ Button text too short! Minimum 2 characters.\n"
                    "Please enter proper button text:"
                )
                return AD_BUTTON_DETAILS
            
            self.ad_purchase_data[user_id]['button_text'] = button_text
            await update.message.reply_text(
                f"✅ *Button Text Saved:* {button_text}\n\n"
                "📝 Now enter the button URL (must start with http:// or https://):\n\n"
                "🌐 *Examples:*\n"
                "• https://yourwebsite.com\n"
                "• https://t.me/yourchannel\n"
                "• http://yourapp.com\n\n"
                "🔗 *Enter button URL:*",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_BUTTON_DETAILS
        else:
            # Second message - button URL
            button_url = update.message.text
            if not button_url.startswith(('http://', 'https://')):
                await update.message.reply_text(
                    "❌ Invalid URL! Must start with http:// or https://\n"
                    "Please enter a valid URL:"
                )
                return AD_BUTTON_DETAILS
            
            # Basic URL validation
            if len(button_url) > 200:
                await update.message.reply_text(
                    "❌ URL too long! Maximum 200 characters.\n"
                    "Please enter a shorter URL:"
                )
                return AD_BUTTON_DETAILS
            
            self.ad_purchase_data[user_id]['button_url'] = button_url
            self.ad_purchase_data[user_id]['step'] = 'contact'
            
            await update.message.reply_text(
                f"✅ *Button URL Saved:* {button_url}\n\n"
                "🎯 *Step 8/8: Contact Information*\n"
                "Enter how people can contact you:\n\n"
                "📞 *Examples:*\n"
                "• Phone: +1234567890\n"
                "• Email: your@email.com\n"
                "• Telegram: @username\n"
                "• Website: yourwebsite.com\n\n"
                "📝 *Enter your contact information:*",
                parse_mode=ParseMode.MARKDOWN
            )
            return AD_CONTACT
    
    async def receive_ad_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive contact information with validation"""
        user_id = update.message.from_user.id
        contact = update.message.text
        
        if len(contact) > 100:
            await update.message.reply_text(
                "❌ Contact information too long! Maximum 100 characters.\n"
                "Please shorten your contact information:"
            )
            return AD_CONTACT
        
        if len(contact) < 3:
            await update.message.reply_text(
                "❌ Contact information too short! Minimum 3 characters.\n"
                "Please provide proper contact information:"
            )
            return AD_CONTACT
        
        self.ad_purchase_data[user_id]['contact'] = contact
        self.ad_purchase_data[user_id]['step'] = 'confirmation'
        
        # Calculate total price
        base_price = 50.00
        image_price = 5.00 if self.ad_purchase_data[user_id].get('has_image') == 1 else 0
        total_price = base_price + image_price
        
        # Build enhanced confirmation message
        ad_data = self.ad_purchase_data[user_id]
        
        confirmation_text = (
            f"📋 *ENHANCED ADVERTISEMENT CONFIRMATION* 📋\n\n"
            f"🎯 *Basic Information:*\n"
            f"• Heading: {ad_data['heading']}\n"
            f"• Type: {ad_data['type']}\n"
            f"• Description: {ad_data['description'][:100]}...\n"
            f"• Contact: {ad_data['contact']}\n\n"
        )
        
        # Add enhanced features section
        confirmation_text += "✨ *Enhanced Features:*\n"
        if ad_data.get('has_image') == 1:
            confirmation_text += "• 🖼️ Image: ✅ INCLUDED (+$5.00)\n"
        else:
            confirmation_text += "• 🖼️ Image: ❌ NOT INCLUDED\n"
            
        if ad_data.get('has_button') == 1:
            confirmation_text += f"• 🔘 Button: ✅ {ad_data.get('button_text', 'TEXT')} → {ad_data.get('button_url', 'URL')}\n"
        else:
            confirmation_text += "• 🔘 Button: ❌ NOT INCLUDED\n"
        
        # Add pricing
        confirmation_text += f"\n💰 *Pricing Breakdown:*\n"
        confirmation_text += f"• Base Advertisement: ${base_price:.2f}\n"
        if image_price > 0:
            confirmation_text += f"• Image Feature: ${image_price:.2f}\n"
        confirmation_text += f"• Total: ${total_price:.2f}\n\n"
        
        confirmation_text += (
            f"⏰ *Duration:* 7 days\n"
            f"📊 *Posting:* Every 5-6 minutes\n"
            f"🎯 *Groups:* Main + Company Resources\n\n"
        )
        
        confirmation_text += "Please confirm your enhanced advertisement:"
        
        # Enhanced keyboard with better labels
        if self.payment_mode == "real":
            confirm_text = f"✅ Confirm & Pay ${total_price:.2f}"
        else:
            confirm_text = f"✅ Confirm Purchase ${total_price:.2f}"
        
        keyboard = [
            [InlineKeyboardButton(confirm_text, callback_data="confirm_purchase")],
            [InlineKeyboardButton("🔧 Edit Details", callback_data="edit_purchase")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_purchase")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AD_CONFIRMATION
    
    async def confirm_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced purchase confirmation with better feedback"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        ad_data = self.ad_purchase_data.get(user_id, {})
        
        if not ad_data:
            await query.edit_message_text(
                "❌ *Purchase data not found!*\n\n"
                "Please start over with /autoadvbuy",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Calculate final price
        base_price = 50.00
        image_price = 5.00 if ad_data.get('has_image') == 1 else 0
        total_price = base_price + image_price
        
        try:
            # Save to database with enhanced features
            async with aiosqlite.connect(DB_NAME) as db:
                # Save advertisement
                ad_result = await db.execute("""
                    INSERT INTO ads_queue (
                        user_id, username, heading, type, description, contact, 
                        created_at, expires_at, status, has_image, image_file_id, 
                        has_button, button_text, button_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    query.from_user.username,
                    ad_data['heading'],
                    ad_data['type'],
                    ad_data['description'],
                    ad_data['contact'],
                    datetime.now().isoformat(),
                    (datetime.now() + timedelta(days=7)).isoformat(),
                    ad_data.get('has_image', 0),
                    ad_data.get('image_file_id'),
                    ad_data.get('has_button', 0),
                    ad_data.get('button_text'),
                    ad_data.get('button_url')
                ))
                
                ad_id = ad_result.lastrowid
                
                # Enhanced purchase recording
                if self.payment_mode == "dummy":
                    status = "completed"
                    completed_at = datetime.now().isoformat()
                    purchase_id = f"PUR{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    status = "pending"
                    completed_at = None
                    purchase_id = f"PUR{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                await db.execute("""
                    INSERT INTO purchases (user_id, username, product_type, amount, status, created_at, completed_at, data)
                    VALUES (?, ?, 'Enhanced Advertisement', ?, ?, ?, ?, ?)
                """, (
                    user_id, 
                    query.from_user.username, 
                    total_price, 
                    status, 
                    datetime.now().isoformat(),
                    completed_at,
                    json.dumps({
                        **ad_data,
                        'ad_id': ad_id,
                        'purchase_id': purchase_id,
                        'features': ad_data.get('features', [])
                    })
                ))
                
                await db.commit()
            
            # Clear purchase data
            if user_id in self.ad_purchase_data:
                del self.ad_purchase_data[user_id]
            
            # Enhanced confirmation message based on payment mode
            if self.payment_mode == "dummy":
                confirmation_message = self._create_dummy_confirmation(ad_data, total_price, purchase_id, ad_id)
            else:
                confirmation_message = self._create_real_payment_confirmation(ad_data, total_price, purchase_id)
            
            await query.edit_message_text(
                confirmation_message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            # Send additional success message
            success_tips = (
                f"💫 *Quick Tips for Success:*\n\n"
                f"📊 *Monitor Your Ad:*\n"
                f"• Use /adviewqueue to see your ad\n"
                f"• Check /adstats for performance\n"
                f"• View /admyads for your active ads\n\n"
                f"🎯 *Maximize Results:*\n"
                f"• Engage with users who contact you\n"
                f"• Track responses and conversions\n"
                f"• Consider renewing successful ads\n\n"
                f"📞 *Need Help?*\n"
                f"Contact {AUTOADV_BOT_USERNAME}"
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=success_tips,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error confirming purchase: {e}")
            await query.edit_message_text(
                "❌ *Error Processing Purchase!*\n\n"
                "There was an error processing your purchase. Please try again or contact support.\n\n"
                f"📞 Support: {AUTOADV_BOT_USERNAME}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return ConversationHandler.END
    
    def _create_dummy_confirmation(self, ad_data: dict, total_price: float, purchase_id: str, ad_id: int) -> str:
        """Create enhanced dummy mode confirmation message"""
        return (
            f"🎉 *ENHANCED PURCHASE COMPLETED!* 🎉\n\n"
            f"📄 *Purchase ID:* `{purchase_id}`\n"
            f"🎯 *Ad ID:* `{ad_id}`\n\n"
            f"💎 *Purchase Details:*\n"
            f"• Service: Enhanced Advertisement Package\n"
            f"• Amount: ${total_price:.2f}\n"
            f"• Duration: 7 days\n"
            f"• Status: ✅ **ACTIVE**\n\n"
            f"✨ *Enhanced Features Activated:*\n"
            f"• Heading: {ad_data['heading']}\n"
            f"• Type: {ad_data['type']}\n"
            f"• Image: {'✅ INCLUDED' if ad_data.get('has_image') == 1 else '❌ NOT INCLUDED'}\n"
            f"• Button: {'✅ INCLUDED' if ad_data.get('has_button') == 1 else '❌ NOT INCLUDED'}\n\n"
            f"🚀 *Immediate Activation:*\n"
            f"• Your ad is now in rotation\n"
            f"• Auto-posting every 5-6 minutes\n"
            f"• Pinned in main group\n"
            f"• Enhanced formatting applied\n\n"
            f"📊 *Next Steps:*\n"
            f"• Monitor performance with /adstats\n"
            f"• View your ads with /admyads\n"
            f"• Check queue with /adviewqueue\n\n"
            f"💫 *Payment Status:* ✅ COMPLETED (Dummy Mode)\n"
            f"📞 *Support:* {AUTOADV_BOT_USERNAME}"
        )
    
    def _create_real_payment_confirmation(self, ad_data: dict, total_price: float, purchase_id: str) -> str:
        """Create enhanced real payment mode confirmation message"""
        return (
            f"🎉 *PURCHASE CONFIRMED - AWAITING PAYMENT* 🎉\n\n"
            f"📄 *Purchase ID:* `{purchase_id}`\n\n"
            f"💎 *Purchase Details:*\n"
            f"• Service: Enhanced Advertisement Package\n"
            f"• Amount: ${total_price:.2f}\n"
            f"• Duration: 7 days\n"
            f"• Status: ⏳ **PENDING PAYMENT**\n\n"
            f"✨ *Enhanced Features Ready:*\n"
            f"• Heading: {ad_data['heading']}\n"
            f"• Type: {ad_data['type']}\n"
            f"• Image: {'✅ INCLUDED' if ad_data.get('has_image') == 1 else '❌ NOT INCLUDED'}\n"
            f"• Button: {'✅ INCLUDED' if ad_data.get('has_button') == 1 else '❌ NOT INCLUDED'}\n\n"
            f"💳 *Payment Instructions:*\n"
            f"Please send ${total_price:.2f} USDT to:\n"
            f"`{YOUR_USDT_ADDRESS}`\n\n"
            f"📋 *Important Payment Notes:*\n"
            f"• Use **TRC20 network only**\n"
            f"• Include memo: `{purchase_id}`\n"
            f"• After sending, use /autoadvverify {purchase_id}\n"
            f"• Ad activates after payment confirmation\n"
            f"• Payment timeout: 24 hours\n\n"
            f"⏰ *After Payment:*\n"
            f"• Ad goes live immediately\n"
            f"• Enhanced features activated\n"
            f"• 7-day rotation starts\n\n"
            f"📞 *Support:* {AUTOADV_BOT_USERNAME}"
        )
    
    # ============================
    # 👑 ENHANCED VIP PURCHASE FLOW
    # ============================
    
    @dm_only_callback
    async def start_vip_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start enhanced VIP purchase conversation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Store VIP purchase data
        self.ad_purchase_data[user_id] = {
            'product_type': 'VIP Membership',
            'step': 'vip_duration',
            'features': ['vip_access', 'premium_content', 'priority_support']
        }
        
        keyboard = [
            [InlineKeyboardButton("1 Month - $10", callback_data="vip_1")],
            [InlineKeyboardButton("3 Months - $25", callback_data="vip_3")],
            [InlineKeyboardButton("6 Months - $45", callback_data="vip_6")],
            [InlineKeyboardButton("1 Year - $80", callback_data="vip_12")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👑 *ENHANCED VIP MEMBERSHIP* 👑\n\n"
            "✨ *Premium Benefits Included:*\n"
            "✅ Exclusive VIP channel access\n"
            "✅ Premium content library\n"
            "✅ 24/7 priority support\n"
            "✅ Special member promotions\n"
            "✅ Early feature access\n"
            "✅ Personal assistant\n\n"
            "🎯 *Select your VIP duration:*",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def handle_vip_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VIP duration selection with enhanced confirmation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        duration = query.data.replace('vip_', '')
        
        if duration == 'back':
            await self.buy_command(update, context)
            return
        
        duration_map = {
            '1': {'months': 1, 'amount': 10.00, 'text': '1 Month', 'savings': '0%'},
            '3': {'months': 3, 'amount': 25.00, 'text': '3 Months', 'savings': '17%'},
            '6': {'months': 6, 'amount': 45.00, 'text': '6 Months', 'savings': '25%'},
            '12': {'months': 12, 'amount': 80.00, 'text': '1 Year', 'savings': '33%'}
        }
        
        selected = duration_map.get(duration)
        if not selected:
            await query.edit_message_text("❌ Invalid duration selection!")
            return
        
        self.ad_purchase_data[user_id].update({
            'duration_months': selected['months'],
            'amount': selected['amount'],
            'duration_text': selected['text'],
            'savings': selected['savings'],
            'step': 'vip_confirmation'
        })
        
        # Enhanced confirmation with savings
        if self.payment_mode == "real":
            confirm_text = f"✅ Confirm & Pay ${selected['amount']:.2f}"
        else:
            confirm_text = f"✅ Confirm Purchase ${selected['amount']:.2f}"
        
        keyboard = [
            [InlineKeyboardButton(confirm_text, callback_data="confirm_vip")],
            [InlineKeyboardButton("🔙 Change Duration", callback_data="buy_vip")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_purchase")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        confirmation_text = (
            f"👑 *VIP MEMBERSHIP CONFIRMATION* 👑\n\n"
            f"📅 *Duration:* {selected['text']}\n"
            f"💰 *Amount:* ${selected['amount']:.2f}\n"
            f"🎁 *Savings:* {selected['savings']} off monthly rate\n"
            f"👤 *User:* @{query.from_user.username}\n\n"
            f"💎 *VIP Benefits Included:*\n"
            f"• Exclusive channel access\n"
            f"• Premium content library\n"
            f"• 24/7 priority support\n"
            f"• Special member promotions\n"
            f"• Early feature access\n"
            f"• Personal assistant\n\n"
            f"⏰ *Membership Period:*\n"
            f"Starts: Immediately\n"
            f"Ends: {(datetime.now() + timedelta(days=30 * selected['months'])).strftime('%Y-%m-%d')}\n\n"
            f"Please confirm your VIP membership:"
        )
        
        await query.edit_message_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def confirm_vip_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced VIP purchase confirmation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        vip_data = self.ad_purchase_data.get(user_id, {})
        
        if not vip_data:
            await query.edit_message_text("❌ VIP purchase data not found. Please start over.")
            return
        
        try:
            # Save VIP purchase to database
            async with aiosqlite.connect(DB_NAME) as db:
                purchase_id = f"VIP{datetime.now().strftime('%Y%m%d%H%M%S')}"
                expires_at = datetime.now() + timedelta(days=30 * vip_data['duration_months'])
                
                if self.payment_mode == "dummy":
                    status = "completed"
                    completed_at = datetime.now().isoformat()
                    
                    # Auto-activate VIP membership
                    await db.execute("""
                        INSERT OR REPLACE INTO vip_members 
                        (user_id, username, created_at, expires_at, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    """, (user_id, query.from_user.username, datetime.now().isoformat(), expires_at.isoformat()))
                    
                else:
                    status = "pending"
                    completed_at = None
                
                await db.execute("""
                    INSERT INTO purchases (user_id, username, product_type, amount, status, created_at, completed_at, data)
                    VALUES (?, ?, 'VIP Membership', ?, ?, ?, ?, ?)
                """, (
                    user_id, 
                    query.from_user.username, 
                    vip_data['amount'], 
                    status, 
                    datetime.now().isoformat(),
                    completed_at,
                    json.dumps({
                        **vip_data,
                        'purchase_id': purchase_id,
                        'expires_at': expires_at.isoformat()
                    })
                ))
                
                await db.commit()
            
            # Clear purchase data
            if user_id in self.ad_purchase_data:
                del self.ad_purchase_data[user_id]
            
            # Enhanced confirmation message
            if self.payment_mode == "dummy":
                confirmation_message = self._create_vip_dummy_confirmation(vip_data, purchase_id, expires_at)
            else:
                confirmation_message = self._create_vip_real_confirmation(vip_data, purchase_id)
            
            await query.edit_message_text(
                confirmation_message,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error confirming VIP purchase: {e}")
            await query.edit_message_text(
                "❌ *Error Processing VIP Purchase!*\n\n"
                "There was an error processing your VIP membership. Please try again.\n\n"
                f"📞 Support: {AUTOADV_BOT_USERNAME}",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def _create_vip_dummy_confirmation(self, vip_data: dict, purchase_id: str, expires_at: datetime) -> str:
        """Create enhanced VIP dummy mode confirmation"""
        return (
            f"🎉 *VIP MEMBERSHIP ACTIVATED!* 🎉\n\n"
            f"📄 *Membership ID:* `{purchase_id}`\n\n"
            f"👑 *Welcome to VIP!* 👑\n\n"
            f"💎 *Membership Details:*\n"
            f"• Duration: {vip_data['duration_text']}\n"
            f"• Amount: ${vip_data['amount']:.2f}\n"
            f"• Savings: {vip_data['savings']} off monthly\n"
            f"• Status: ✅ **ACTIVE**\n"
            f"• Expires: {expires_at.strftime('%Y-%m-%d')}\n\n"
            f"✨ *VIP Benefits Now Active:*\n"
            f"• Exclusive channel access\n"
            f"• Premium content library\n"
            f"• 24/7 priority support\n"
            f"• Special member promotions\n"
            f"• Early feature access\n"
            f"• Personal assistant\n\n"
            f"🚀 *Immediate Access:*\n"
            f"• VIP channels unlocked\n"
            f"• Premium content available\n"
            f"• Priority support active\n\n"
            f"📞 *VIP Support:* {VIP_BOT_USERNAME}\n"
            f"💫 *Payment Status:* ✅ COMPLETED (Dummy Mode)"
        )
    
    def _create_vip_real_confirmation(self, vip_data: dict, purchase_id: str) -> str:
        """Create enhanced VIP real payment mode confirmation"""
        return (
            f"🎉 *VIP PURCHASE CONFIRMED - AWAITING PAYMENT* 🎉\n\n"
            f"📄 *Purchase ID:* `{purchase_id}`\n\n"
            f"👑 *VIP Membership Details:*\n"
            f"• Duration: {vip_data['duration_text']}\n"
            f"• Amount: ${vip_data['amount']:.2f}\n"
            f"• Savings: {vip_data['savings']} off monthly\n"
            f"• Status: ⏳ **PENDING PAYMENT**\n\n"
            f"💎 *VIP Benefits Included:*\n"
            f"• Exclusive channel access\n"
            f"• Premium content library\n"
            f"• 24/7 priority support\n"
            f"• Special member promotions\n"
            f"• Early feature access\n"
            f"• Personal assistant\n\n"
            f"💳 *Payment Instructions:*\n"
            f"Please send ${vip_data['amount']:.2f} USDT to:\n"
            f"`{YOUR_USDT_ADDRESS}`\n\n"
            f"📋 *Payment Notes:*\n"
            f"• Use **TRC20 network only**\n"
            f"• Include memo: `{purchase_id}`\n"
            f"• After payment, use /autoadvverify {purchase_id}\n"
            f"• VIP access activates after payment\n"
            f"• Payment timeout: 24 hours\n\n"
            f"📞 *Support:* {AUTOADV_BOT_USERNAME}"
        )
    
    # ============================
    # 🛡️ ENHANCED ERROR HANDLING
    # ============================
    
    async def cancel_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced purchase cancellation"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if user_id in self.ad_purchase_data:
            del self.ad_purchase_data[user_id]
        
        await query.edit_message_text(
            "❌ *PURCHASE CANCELLED* ❌\n\n"
            "Your purchase has been cancelled successfully.\n\n"
            "💫 *You can always:*\n"
            "• Start over with /autoadvbuy\n"
            "• Browse services anytime\n"
            "• Contact support for help\n\n"
            f"📞 Support: {AUTOADV_BOT_USERNAME}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced conversation cancellation"""
        user_id = update.message.from_user.id
        if user_id in self.ad_purchase_data:
            del self.ad_purchase_data[user_id]
        
        await update.message.reply_text(
            "❌ *PURCHASE CANCELLED* ❌\n\n"
            "Your purchase process has been cancelled.\n\n"
            f"💫 You can start over with /{self.bot_prefix}buy anytime!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    # ============================
    # 🔧 ENHANCED BOT SETUP
    # ============================
    
    def setup_handlers(self):
        """Setup all enhanced handlers"""
        # Enhanced command handlers with DM protection
        self.app.add_handler(CommandHandler("autoadvstart", self.start_command))
        self.app.add_handler(CommandHandler("autoadvhelp", self.help_command))
        self.app.add_handler(CommandHandler("autoadvbuy", self.buy_command))
        
        # Enhanced purchase conversation handler
        ad_purchase_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_ad_purchase, pattern="^buy_ad$")],
            states={
                AD_HEADING: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_heading)],
                AD_TYPE: [CallbackQueryHandler(self.receive_ad_type, pattern="^type_")],
                AD_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_description)],
                AD_IMAGE_OPTION: [CallbackQueryHandler(self.receive_image_option, pattern="^image_")],
                AD_IMAGE_UPLOAD: [MessageHandler(filters.PHOTO, self.receive_image_upload)],
                AD_BUTTON_OPTION: [CallbackQueryHandler(self.receive_button_option, pattern="^button_")],
                AD_BUTTON_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_button_details)],
                AD_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_contact)],
                AD_CONFIRMATION: [
                    CallbackQueryHandler(self.confirm_purchase, pattern="^confirm_purchase$"),
                    CallbackQueryHandler(self.cancel_purchase, pattern="^cancel_purchase$")
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_conversation),
                CallbackQueryHandler(self.cancel_purchase, pattern="^cancel_purchase$")
            ],
            per_message=False,
            conversation_timeout=300  # 5 minutes timeout
        )
        
        self.app.add_handler(ad_purchase_conv)
        
        # Enhanced VIP purchase handlers
        self.app.add_handler(CallbackQueryHandler(self.start_vip_purchase, pattern="^buy_vip$"))
        self.app.add_handler(CallbackQueryHandler(self.handle_vip_duration, pattern="^vip_"))
        self.app.add_handler(CallbackQueryHandler(self.confirm_vip_purchase, pattern="^confirm_vip$"))
        
        # Other purchase callbacks
        self.app.add_handler(CallbackQueryHandler(self.start_ad_purchase, pattern="^buy_promotion$"))
        self.app.add_handler(CallbackQueryHandler(self.start_ad_purchase, pattern="^buy_custom$"))
        self.app.add_handler(CallbackQueryHandler(self.buy_command, pattern="^back_main$"))
        
        logger.info("✅ Enhanced AutoADV bot handlers setup complete")
    
    def run_bot(self):
        """Run the enhanced AutoADV bot"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_run():
            await init_database()
            self.setup_handlers()
            
            logger.info("💰 Enhanced AutoADV Payment Bot is running...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            while True:
                await asyncio.sleep(3600)
        
        try:
            loop.run_until_complete(async_run())
        except KeyboardInterrupt:
            logger.info("🛑 Enhanced AutoADV Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in Enhanced AutoADV Bot: {e}")
        finally:
            loop.run_until_complete(self.app.stop())
            loop.run_until_complete(self.app.shutdown())
            loop.close()

# ============================
# 🚀 MAIN EXECUTION - ALL BOTS
# ============================

def run_all_bots():
    """Run all enhanced bots in separate threads"""
    import threading
    import time
    
    def run_advertising_bot():
        """Run enhanced advertising bot"""
        try:
            adv_bot = EnhancedAdvertisingBot(ADV_BOT_TOKEN)
            adv_bot.run_bot()
        except Exception as e:
            logger.error(f"Advertising bot error: {e}")
    
    def run_vip_bot():
        """Run enhanced VIP bot"""
        try:
            vip_bot = EnhancedVIPVerificationBot(VIP_BOT_TOKEN)
            vip_bot.run_bot()
        except Exception as e:
            logger.error(f"VIP bot error: {e}")
    
    def run_autoadv_bot():
        """Run enhanced AutoADV bot"""
        try:
            autoadv_bot = EnhancedAutoAdvPaymentBot(AUTOADV_BOT_TOKEN)
            autoadv_bot.run_bot()
        except Exception as e:
            logger.error(f"AutoADV bot error: {e}")
    
    # Start all bots in separate threads
    threads = []
    
    logger.info("🚀 Starting all enhanced bots...")
    
    # Start Advertising Bot
    adv_thread = threading.Thread(target=run_advertising_bot, daemon=True)
    adv_thread.start()
    threads.append(adv_thread)
    logger.info("✅ Enhanced Advertising Bot started")
    
    time.sleep(2)  # Stagger startup
    
    # Start VIP Bot
    vip_thread = threading.Thread(target=run_vip_bot, daemon=True)
    vip_thread.start()
    threads.append(vip_thread)
    logger.info("✅ Enhanced VIP Bot started")
    
    time.sleep(2)  # Stagger startup
    
    # Start AutoADV Bot
    autoadv_thread = threading.Thread(target=run_autoadv_bot, daemon=True)
    autoadv_thread.start()
    threads.append(autoadv_thread)
    logger.info("✅ Enhanced AutoADV Bot started")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 All enhanced bots stopped by user")

# ============================
# 🚀 MAIN EXECUTION - ALL BOTS
# ============================

def main():
    """Main function - automatically run all bots in container environment"""
    logger.info("🚀 Starting ALL enhanced bots in container mode...")
    
    # In container environment, automatically run all bots
    run_all_bots()

if __name__ == "__main__":
    # Initialize database first
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_database())
    loop.close()
    
    logger.info("✅ Enhanced database initialized successfully")
    main()
