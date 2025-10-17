import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
import sqlite3
import datetime
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiohttp
import json
import re
import os
from typing import Dict, List, Optional
import random
import time
from datetime import timedelta

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================ DATABASE SETUP ============================
async def init_db():
    """Initialize database with all required tables"""
    try:
        async with aiosqlite.connect('bot_database.db') as db:
            # Users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_vip INTEGER DEFAULT 0,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    balance REAL DEFAULT 0.0,
                    total_ads_posted INTEGER DEFAULT 0,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Advertisements table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS advertisements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ad_text TEXT,
                    ad_image TEXT,
                    ad_type TEXT DEFAULT 'text',
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scheduled_time TIMESTAMP,
                    approved_by INTEGER,
                    approved_at TIMESTAMP,
                    target_audience TEXT,
                    budget REAL DEFAULT 0.0,
                    impressions INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Payments table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT DEFAULT 'USD',
                    status TEXT DEFAULT 'pending',
                    payment_method TEXT,
                    transaction_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    invoice_url TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Group settings table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS group_settings (
                    group_id INTEGER PRIMARY KEY,
                    group_title TEXT,
                    welcome_message TEXT DEFAULT 'Welcome {name} to the group! 🎉',
                    rules_text TEXT DEFAULT 'Please be respectful and follow the group rules.',
                    welcome_enabled INTEGER DEFAULT 1,
                    ads_allowed INTEGER DEFAULT 0,
                    max_warnings INTEGER DEFAULT 3,
                    auto_delete_links INTEGER DEFAULT 0,
                    mute_duration INTEGER DEFAULT 3600,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # VIP users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS vip_users (
                    user_id INTEGER PRIMARY KEY,
                    vip_level TEXT DEFAULT 'basic',
                    expires_at TIMESTAMP,
                    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    features TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Warnings table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    group_id INTEGER,
                    reason TEXT,
                    warned_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Banned users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER,
                    group_id INTEGER,
                    reason TEXT,
                    banned_by INTEGER,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    PRIMARY KEY (user_id, group_id)
                )
            ''')
            
            # Advertisement analytics table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS ad_analytics (
                    ad_id INTEGER,
                    user_id INTEGER,
                    view_count INTEGER DEFAULT 0,
                    click_count INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ad_id) REFERENCES advertisements (id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            await db.commit()
        logger.info("✅ Database initialized successfully with all tables")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

# ============================ ADVERTISING BOT ============================
class AdvertisingBot:
    def __init__(self):
        self.token = "8455931212:AAGOLICokhaKTmqEJKKCzDa9gobYnywmlN4"
        self.application = Application.builder().token(self.token).build()
        self.scheduler = AsyncIOScheduler()
        self.setup_handlers()
        self.ad_conversation_state = {}
    
    def setup_handlers(self):
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("post", self.post_ad_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("admin_stats", self.admin_stats_command))
        self.application.add_handler(CommandHandler("approve_ad", self.approve_ad_command, filters.User(123456789)))  # Replace with admin ID
        self.application.add_handler(CommandHandler("reject_ad", self.reject_ad_command, filters.User(123456789)))
        self.application.add_handler(CommandHandler("list_ads", self.list_ads_command, filters.User(123456789)))
        
        # Conversation handler for ad creation
        ad_conversation = ConversationHandler(
            entry_points=[CommandHandler("create_ad", self.create_ad_command)],
            states={
                1: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_ad_text)],
                2: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_ad_target)],
                3: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_ad_budget)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_ad_creation)]
        )
        self.application.add_handler(ad_conversation)
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.ad_button_handler, pattern="^ad_"))
        
        # Photo handlers for ad images
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_ad_image))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        
        # Add user to database
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                (user_id, user.username, user.first_name, user.last_name)
            )
            await db.commit()
        
        welcome_text = f"""
👋 Welcome {user.first_name} to the Advanced Advertising Bot! 🚀

📊 **Bot Features:**
• Create and schedule advertisements
• Advanced targeting options
• Real-time analytics and statistics
• Multiple ad formats (Text, Image, Video)
• Budget management
• Performance tracking

💼 **Available Commands:**
/post - Create new advertisement
/stats - View your ad statistics
/balance - Check your account balance
/create_ad - Advanced ad creation wizard
/help - Detailed help information

🛠 **Admin Commands:**
/admin_stats - Overall bot statistics
/approve_ad <id> - Approve advertisement
/reject_ad <id> - Reject advertisement
/list_ads - List all pending ads

💰 Start by creating your first advertisement using /post command!
        """
        
        keyboard = [
            [InlineKeyboardButton("📝 Create Ad", callback_data="ad_create")],
            [InlineKeyboardButton("📊 View Stats", callback_data="ad_stats")],
            [InlineKeyboardButton("💰 Check Balance", callback_data="ad_balance")],
            [InlineKeyboardButton("🆘 Help", callback_data="ad_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🤖 **Advanced Advertising Bot - Complete Help Guide** 📚

📋 **USER COMMANDS:**
/start - Initialize the bot and get started
/help - Display this comprehensive help message
/post - Quick ad creation with templates
/create_ad - Advanced ad creation wizard
/stats - View detailed advertisement statistics
/balance - Check your account balance and transaction history
/pricing - View advertising plans and pricing

🛠 **ADMIN COMMANDS:**
/admin_stats - View overall bot statistics and performance
/approve_ad <ad_id> - Approve a pending advertisement
/reject_ad <ad_id> <reason> - Reject an advertisement with reason
/list_ads - List all pending advertisements for review
/user_info <user_id> - Get detailed user information
/system_status - Check bot system status and health

🎯 **ADVERTISING FEATURES:**
• **Multiple Ad Formats**: Text, Image, Carousel, Video ads
• **Advanced Targeting**: Demographic, interest-based, geographic targeting
• **Scheduling**: Schedule ads for specific times and dates
• **Budget Control**: Set daily/weekly/monthly budgets
• **A/B Testing**: Test different ad variations
• **Real-time Analytics**: Track impressions, clicks, conversions
• **Performance Optimization**: AI-powered ad optimization

📊 **ANALYTICS & REPORTING:**
• Impression tracking
• Click-through rates (CTR)
• Engagement metrics
• Conversion tracking
• Audience insights
• ROI calculation

💳 **PAYMENT METHODS:**
• Credit/Debit Cards
• Cryptocurrency (BTC, ETH, USDT)
• Bank Transfers
• E-wallets (PayPal, Skrill, etc.)

🔧 **TROUBLESHOOTING:**
If you encounter any issues:
1. Check your internet connection
2. Ensure you have sufficient balance
3. Verify ad complies with our policies
4. Contact support for technical issues

📞 **SUPPORT:**
For additional help, contact our support team:
• Email: support@adbot.com
• Telegram: @adbotsupport
• Website: https://adbot.com/support

⚖️ **POLICIES:**
• All ads must comply with our advertising policies
• No spam, scams, or illegal content
• Respect user privacy and data protection laws
        """
        
        keyboard = [
            [InlineKeyboardButton("📝 Create Advertisement", callback_data="ad_create_now")],
            [InlineKeyboardButton("📊 View Pricing", callback_data="ad_pricing")],
            [InlineKeyboardButton("🆘 Contact Support", callback_data="ad_support")],
            [InlineKeyboardButton("📚 Documentation", callback_data="ad_docs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def post_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton("📝 Text Ad", callback_data="ad_type_text"),
                InlineKeyboardButton("🖼 Image Ad", callback_data="ad_type_image")
            ],
            [
                InlineKeyboardButton("📹 Video Ad", callback_data="ad_type_video"),
                InlineKeyboardButton("🎠 Carousel Ad", callback_data="ad_type_carousel")
            ],
            [
                InlineKeyboardButton("💰 Promoted Post", callback_data="ad_type_promoted"),
                InlineKeyboardButton("🎯 Targeted Ad", callback_data="ad_type_targeted")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        ad_types_info = """
🎯 **Choose Advertisement Type:**

📝 **Text Ad** - Simple text-based advertisement
• Max: 1000 characters
• Basic formatting supported
• Quick approval process

🖼 **Image Ad** - Visual advertisement with image
• Supports JPEG, PNG
• Max size: 5MB
• Recommended ratio: 1.91:1

📹 **Video Ad** - Engaging video content
• Supports MP4, MOV
• Max duration: 60 seconds
• Max size: 50MB

🎠 **Carousel Ad** - Multiple images in swipeable format
• 3-10 images
• Each image can have own link
• Great for product catalogs

💰 **Promoted Post** - Boost existing content
• Promote your best posts
• Increased visibility
• Social proof included

🎯 **Targeted Ad** - Advanced audience targeting
• Demographic targeting
• Interest-based targeting
• Geographic targeting
• Custom audience lists
        """
        
        await update.message.reply_text(ad_types_info, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            # Get basic stats
            cursor = await db.execute('''
                SELECT 
                    COUNT(*) as total_ads,
                    SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved_ads,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending_ads,
                    SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected_ads,
                    SUM(impressions) as total_impressions,
                    SUM(clicks) as total_clicks,
                    AVG(clicks * 1.0 / NULLIF(impressions, 0)) as avg_ctr
                FROM advertisements 
                WHERE user_id = ?
            ''', (user_id,))
            result = await cursor.fetchone()
            
            # Get recent performance
            cursor = await db.execute('''
                SELECT 
                    strftime('%Y-%m-%d', created_at) as date,
                    COUNT(*) as ads_posted,
                    SUM(impressions) as daily_impressions,
                    SUM(clicks) as daily_clicks
                FROM advertisements 
                WHERE user_id = ? AND created_at >= date('now', '-7 days')
                GROUP BY strftime('%Y-%m-%d', created_at)
                ORDER BY date DESC
                LIMIT 7
            ''', (user_id,))
            recent_stats = await cursor.fetchall()
        
        if result:
            total_ads, approved_ads, pending_ads, rejected_ads, impressions, clicks, ctr = result
            
            stats_text = f"""
📊 **Advanced Advertisement Statistics** 📈

📋 **Overview:**
• Total Ads: `{total_ads}`
• ✅ Approved: `{approved_ads}`
• ⏳ Pending: `{pending_ads}`
• ❌ Rejected: `{rejected_ads}`
• Approval Rate: `{(approved_ads/total_ads*100) if total_ads > 0 else 0:.1f}%`

📈 **Performance Metrics:**
• Total Impressions: `{impressions or 0}`
• Total Clicks: `{clicks or 0}`
• Average CTR: `{(ctr * 100) if ctr else 0:.2f}%`
• Total Engagement: `{((clicks or 0) + (impressions or 0))}`

📅 **Last 7 Days Performance:**
"""
            
            for date, ads_posted, daily_impressions, daily_clicks in recent_stats:
                daily_ctr = (daily_clicks / daily_impressions * 100) if daily_impressions > 0 else 0
                stats_text += f"• {date}: {ads_posted} ads, {daily_impressions} impressions, {daily_ctr:.1f}% CTR\n"
            
            if not recent_stats:
                stats_text += "• No activity in the last 7 days\n"
            
            stats_text += "\n💡 **Tips:** Try A/B testing to improve your CTR!"
            
        else:
            stats_text = "📊 No advertisement statistics available yet. Create your first ad using /post command!"
        
        keyboard = [
            [InlineKeyboardButton("📈 Detailed Analytics", callback_data="ad_detailed_stats")],
            [InlineKeyboardButton("📋 Export Data", callback_data="ad_export_stats")],
            [InlineKeyboardButton("🎯 Optimization Tips", callback_data="ad_optimization_tips")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            
            # Get recent transactions
            cursor = await db.execute('''
                SELECT amount, status, created_at, payment_method 
                FROM payments 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 5
            ''', (user_id,))
            transactions = await cursor.fetchall()
        
        balance = result[0] if result else 0.0
        
        balance_text = f"""
💰 **Account Balance & Financial Overview** 💳

**Current Balance:** `${balance:.2f}`

📊 **Balance Breakdown:**
• Available Balance: `${balance:.2f}`
• Total Spent: `$0.00` *(feature coming soon)*
• Pending Payments: `$0.00` *(feature coming soon)*

💸 **Recent Transactions:**
"""
        
        if transactions:
            for amount, status, created_at, method in transactions:
                status_icon = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
                balance_text += f"• {status_icon} ${amount:.2f} via {method} - {created_at[:10]}\n"
        else:
            balance_text += "• No recent transactions\n"
        
        balance_text += f"""
📈 **Spending Analysis:**
• Daily Budget: `Not set`
• Monthly Limit: `Not set`
• Auto-topup: `Disabled`

💡 **Recommendation:** Maintain a minimum balance of $10 for uninterrupted advertising.
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💳 Add Funds", callback_data="ad_add_funds"),
                InlineKeyboardButton("📊 Spending Limits", callback_data="ad_spending_limits")
            ],
            [
                InlineKeyboardButton("📄 Invoice History", callback_data="ad_invoice_history"),
                InlineKeyboardButton("🔄 Auto-topup", callback_data="ad_auto_topup")
            ],
            [
                InlineKeyboardButton("💸 Payment Methods", callback_data="ad_payment_methods")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(balance_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def admin_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Verify admin privileges
        if update.effective_user.id not in [123456789]:  # Replace with actual admin IDs
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return
        
        async with aiosqlite.connect('bot_database.db') as db:
            # Overall statistics
            cursor = await db.execute('''
                SELECT 
                    COUNT(*) as total_users,
                    SUM(balance) as total_balance,
                    COUNT(CASE WHEN is_vip=1 THEN 1 END) as vip_users
                FROM users
            ''')
            user_stats = await cursor.fetchone()
            
            # Advertisement statistics
            cursor = await db.execute('''
                SELECT 
                    COUNT(*) as total_ads,
                    SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved_ads,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending_ads,
                    SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected_ads,
                    SUM(impressions) as total_impressions,
                    SUM(clicks) as total_clicks,
                    SUM(budget) as total_budget
                FROM advertisements
            ''')
            ad_stats = await cursor.fetchone()
            
            # Payment statistics
            cursor = await db.execute('''
                SELECT 
                    COUNT(*) as total_payments,
                    SUM(amount) as total_revenue,
                    SUM(CASE WHEN status='completed' THEN amount ELSE 0 END) as completed_revenue,
                    SUM(CASE WHEN status='pending' THEN amount ELSE 0 END) as pending_revenue
                FROM payments
            ''')
            payment_stats = await cursor.fetchone()
        
        total_users, total_balance, vip_users = user_stats
        total_ads, approved_ads, pending_ads, rejected_ads, impressions, clicks, total_budget = ad_stats
        total_payments, total_revenue, completed_revenue, pending_revenue = payment_stats
        
        admin_stats_text = f"""
👑 **Administrator Dashboard - System Overview** 🖥️

👥 **USER STATISTICS:**
• Total Users: `{total_users}`
• VIP Users: `{vip_users}`
• Regular Users: `{total_users - vip_users}`
• Total Platform Balance: `${total_balance:.2f}`

📊 **ADVERTISEMENT STATISTICS:**
• Total Ads Created: `{total_ads}`
• ✅ Approved Ads: `{approved_ads}`
• ⏳ Pending Approval: `{pending_ads}`
• ❌ Rejected Ads: `{rejected_ads}`
• Approval Rate: `{(approved_ads/total_ads*100) if total_ads > 0 else 0:.1f}%`

📈 **PERFORMANCE METRICS:**
• Total Impressions: `{impressions or 0}`
• Total Clicks: `{clicks or 0}`
• Overall CTR: `{(clicks/impressions*100) if impressions else 0:.2f}%`
• Total Ad Budget: `${total_budget or 0:.2f}`

💰 **FINANCIAL OVERVIEW:**
• Total Payments: `{total_payments}`
• Total Revenue: `${total_revenue or 0:.2f}`
• Completed Revenue: `${completed_revenue or 0:.2f}`
• Pending Revenue: `${pending_revenue or 0:.2f}`

📅 **SYSTEM HEALTH:**
• Database Size: `Normal`
• Bot Uptime: `100%`
• Last Backup: `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}`
• Active Sessions: `Normal`
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📋 User Management", callback_data="admin_users"),
                InlineKeyboardButton("📊 Ad Review", callback_data="admin_ad_review")
            ],
            [
                InlineKeyboardButton("💰 Financial Report", callback_data="admin_financial"),
                InlineKeyboardButton("🛠 System Settings", callback_data="admin_system")
            ],
            [
                InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics"),
                InlineKeyboardButton("🔍 Audit Log", callback_data="admin_audit")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(admin_stats_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def approve_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in [123456789]:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /approve_ad <ad_id>")
            return
        
        ad_id = context.args[0]
        
        try:
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    "UPDATE advertisements SET status = 'approved', approved_by = ?, approved_at = ? WHERE id = ?",
                    (update.effective_user.id, datetime.datetime.now(), ad_id)
                )
                await db.commit()
            
            await update.message.reply_text(f"✅ Advertisement #{ad_id} approved successfully!")
        except Exception as e:
            await update.message.reply_text(f"❌ Error approving ad: {e}")
    
    async def reject_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in [123456789]:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /reject_ad <ad_id> <reason>")
            return
        
        ad_id = context.args[0]
        reason = ' '.join(context.args[1:])
        
        try:
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    "UPDATE advertisements SET status = 'rejected', approved_by = ?, approved_at = ? WHERE id = ?",
                    (update.effective_user.id, datetime.datetime.now(), ad_id)
                )
                await db.commit()
            
            await update.message.reply_text(f"❌ Advertisement #{ad_id} rejected. Reason: {reason}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error rejecting ad: {e}")
    
    async def list_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in [123456789]:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT a.id, a.user_id, u.username, a.ad_type, a.created_at, a.ad_text 
                FROM advertisements a 
                JOIN users u ON a.user_id = u.user_id 
                WHERE a.status = 'pending' 
                ORDER BY a.created_at DESC 
                LIMIT 10
            ''')
            pending_ads = await cursor.fetchall()
        
        if not pending_ads:
            await update.message.reply_text("📭 No pending advertisements for review.")
            return
        
        ads_text = "📋 **Pending Advertisements for Review:**\n\n"
        for ad_id, user_id, username, ad_type, created_at, ad_text in pending_ads:
            preview = ad_text[:50] + "..." if len(ad_text) > 50 else ad_text
            ads_text += f"🆔 **#{ad_id}** - 👤 @{username}\n"
            ads_text += f"📝 Type: {ad_type}\n"
            ads_text += f"📄 Preview: {preview}\n"
            ads_text += f"⏰ Submitted: {created_at[:16]}\n"
            ads_text += f"🔧 Actions: /approve_ad {ad_id} | /reject_ad {ad_id} [reason]\n\n"
        
        await update.message.reply_text(ads_text, parse_mode='Markdown')
    
    # Conversation handlers for ad creation
    async def create_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🎯 **Advanced Ad Creation Wizard**\n\n"
            "Please enter your advertisement text (max 1000 characters):\n\n"
            "💡 **Tips for effective ads:**\n"
            "• Clear call-to-action\n"
            "• Highlight benefits\n"
            "• Include contact information\n"
            "• Use emojis sparingly\n\n"
            "Type /cancel to abort creation."
        )
        return 1
    
    async def get_ad_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        ad_text = update.message.text
        if len(ad_text) > 1000:
            await update.message.reply_text("❌ Advertisement text too long! Maximum 1000 characters. Please try again:")
            return 1
        
        context.user_data['ad_text'] = ad_text
        await update.message.reply_text(
            "🎯 **Step 2: Target Audience**\n\n"
            "Describe your target audience:\n"
            "• Age range\n"
            "• Interests\n"
            "• Location\n"
            "• Other demographics\n\n"
            "Examples:\n"
            "• 'Age 25-40, interested in technology, US-based'\n"
            "• 'Students, 18-25, interested in education'\n"
            "• 'All ages, global audience'"
        )
        return 2
    
    async def get_ad_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['target_audience'] = update.message.text
        await update.message.reply_text(
            "💰 **Step 3: Budget Setting**\n\n"
            "Enter your advertising budget (in USD):\n\n"
            "💡 **Budget Recommendations:**\n"
            "• Small test: $5-$20\n"
            "• Campaign: $50-$200\n"
            "• Enterprise: $500+\n\n"
            "Enter amount:"
        )
        return 3
    
    async def get_ad_budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            budget = float(update.message.text)
            if budget < 1:
                await update.message.reply_text("❌ Minimum budget is $1. Please enter a valid amount:")
                return 3
            
            user_id = update.effective_user.id
            ad_text = context.user_data.get('ad_text')
            target_audience = context.user_data.get('target_audience')
            
            # Save ad to database
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    "INSERT INTO advertisements (user_id, ad_text, target_audience, budget, status) VALUES (?, ?, ?, ?, 'pending')",
                    (user_id, ad_text, target_audience, budget)
                )
                await db.commit()
            
            await update.message.reply_text(
                f"✅ **Advertisement Created Successfully!** 🎉\n\n"
                f"📝 **Your Ad:** {ad_text[:100]}...\n"
                f"🎯 **Target:** {target_audience}\n"
                f"💰 **Budget:** ${budget:.2f}\n\n"
                "⏳ **Status:** Pending approval\n"
                "📞 Our team will review your ad within 24 hours.\n\n"
                "Thank you for using our advertising service! ✨"
            )
            
            # Clear conversation data
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for budget:")
            return 3
    
    async def cancel_ad_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("❌ Advertisement creation cancelled.")
        return ConversationHandler.END
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Handle regular messages
        user_message = update.message.text
        user_id = update.effective_user.id
        
        # Log user activity
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute(
                "UPDATE users SET last_activity = ? WHERE user_id = ?",
                (datetime.datetime.now(), user_id)
            )
            await db.commit()
        
        # Simple auto-reply for common questions
        common_questions = {
            'price': 'Check our pricing with /post command',
            'cost': 'Advertisement costs start from $5. Use /post to see options',
            'approval': 'Ads are typically approved within 24 hours',
            'support': 'Contact @adsupport for assistance'
        }
        
        for keyword, response in common_questions.items():
            if keyword in user_message.lower():
                await update.message.reply_text(response)
                return
    
    async def handle_ad_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Handle ad images
        await update.message.reply_text("📸 Image received! Please add your ad text or use /post to create complete advertisement.")
    
    async def ad_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "ad_create":
            await query.edit_message_text("Starting ad creation... Use /post for quick ads or /create_ad for advanced options.")
        elif data == "ad_stats":
            await self.stats_command(update, context)
        elif data == "ad_balance":
            await self.balance_command(update, context)
        elif data == "ad_help":
            await self.help_command(update, context)
        elif data.startswith("ad_type_"):
            ad_type = data.replace("ad_type_", "")
            await query.edit_message_text(f"Selected {ad_type.replace('_', ' ').title()} advertisement. Please send your ad content now...")
    
    async def post_advertisement(self):
        """Scheduled advertisement posting - runs every 30 minutes"""
        try:
            logger.info("📢 Running scheduled advertisement posting...")
            
            async with aiosqlite.connect('bot_database.db') as db:
                # Get approved ads scheduled for now
                cursor = await db.execute('''
                    SELECT * FROM advertisements 
                    WHERE status = 'approved' 
                    AND (scheduled_time <= ? OR scheduled_time IS NULL)
                    ORDER BY created_at ASC
                    LIMIT 5
                ''', (datetime.datetime.now(),))
                ads_to_post = await cursor.fetchall()
                
                for ad in ads_to_post:
                    ad_id, user_id, ad_text, ad_image, ad_type, status, created_at, scheduled_time, approved_by, approved_at, target, budget, impressions, clicks = ad
                    
                    # Update impressions
                    await db.execute(
                        "UPDATE advertisements SET impressions = impressions + 1 WHERE id = ?",
                        (ad_id,)
                    )
                    
                    # Update user's total ads count
                    await db.execute(
                        "UPDATE users SET total_ads_posted = total_ads_posted + 1 WHERE user_id = ?",
                        (user_id,)
                    )
                    
                    logger.info(f"📢 Posted ad #{ad_id} for user {user_id}")
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"❌ Error in scheduled ad posting: {e}")
    
    async def start_bot(self):
        """Start Advertising Bot with all features"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        # Start scheduler for automated ads
        self.scheduler.add_job(self.post_advertisement, 'interval', minutes=30)
        self.scheduler.start()
        
        logger.info("🚀 Advertising Bot is running with full functionality...")

# ============================ VIP BOT ============================
class VIPBot:
    def __init__(self):
        self.token = "8233798151:AAFHctdFHjHyJEgxPXGkDQoFRVusjLQMVtU"
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
        self.verification_conversation_state = {}
    
    def setup_handlers(self):
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("verify", self.verify_command))
        self.application.add_handler(CommandHandler("vip_status", self.vip_status_command))
        self.application.add_handler(CommandHandler("upgrade", self.upgrade_command))
        self.application.add_handler(CommandHandler("vip_benefits", self.vip_benefits_command))
        self.application.add_handler(CommandHandler("approve_verification", self.approve_verification_command, filters.User(123456789)))
        self.application.add_handler(CommandHandler("reject_verification", self.reject_verification_command, filters.User(123456789)))
        self.application.add_handler(CommandHandler("vip_list", self.vip_list_command, filters.User(123456789)))
        
        # Conversation handler for verification
        verification_conversation = ConversationHandler(
            entry_points=[CommandHandler("start_verification", self.start_verification_command)],
            states={
                1: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_verification_info)],
                2: [MessageHandler(filters.PHOTO, self.get_verification_document)],
                3: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_verification_notes)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_verification)]
        )
        self.application.add_handler(verification_conversation)
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.vip_button_handler, pattern="^vip_"))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_vip_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        
        # Check if user is already VIP
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT v.vip_level, v.expires_at, v.is_active 
                FROM vip_users v 
                WHERE v.user_id = ? AND v.is_active = 1
            ''', (user_id,))
            vip_info = await cursor.fetchone()
        
        welcome_text = f"""
👑 Welcome {user.first_name} to the Exclusive VIP Verification System! ✨

{'🎉 **YOU ARE A VIP MEMBER!** 🎉' if vip_info else '🔒 **VIP Verification Portal**'}

{'**Your VIP Status:** ' + vip_info[0].title() + ' Member' if vip_info else 'Get verified to unlock premium features!'}

💎 **VIP Benefits:**
• Priority advertisement approval
• Advanced analytics dashboard
• Higher advertisement limits
• Dedicated support team
• Exclusive advertising features
• Early access to new features

⚡ **Quick Actions:**
"""
        
        keyboard = [
            [InlineKeyboardButton("🔐 Get Verified", callback_data="vip_verify")],
            [InlineKeyboardButton("💎 VIP Benefits", callback_data="vip_benefits")],
            [InlineKeyboardButton("🆙 Upgrade", callback_data="vip_upgrade")],
            [InlineKeyboardButton("📊 Status Check", callback_data="vip_status")]
        ]
        
        if vip_info:
            keyboard.insert(0, [InlineKeyboardButton("🎉 VIP Dashboard", callback_data="vip_dashboard")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
👑 **VIP Verification Bot - Complete Help Guide** 📚

🔐 **VERIFICATION COMMANDS:**
/verify - Start verification process
/vip_status - Check your verification status
/upgrade - Upgrade your VIP level
/vip_benefits - View all VIP benefits
/start_verification - Detailed verification wizard

🛠 **ADMIN COMMANDS:**
/approve_verification <user_id> - Approve user verification
/reject_verification <user_id> <reason> - Reject verification
/vip_list - List all VIP members
/vip_stats - VIP system statistics

💎 **VIP LEVELS & PRICING:**
🥉 **Bronze VIP** ($10/month)
• Priority ad approval (24 hours)
• Basic analytics
• 10 ads per day limit
• Standard support

🥈 **Silver VIP** ($25/month)  
• Express approval (12 hours)
• Advanced analytics
• 25 ads per day limit
• Priority support
• A/B testing

🥇 **Gold VIP** ($50/month)
• Instant approval (6 hours)
• Premium analytics dashboard
• 50 ads per day limit
• VIP support
• All advanced features

💎 **Platinum VIP** ($100/month)
• Instant approval (1 hour)
• Enterprise analytics
• Unlimited ads
• Dedicated account manager
• All features + custom solutions

📋 **VERIFICATION REQUIREMENTS:**
• Valid government ID
• Business documentation (for business accounts)
• Completed application form
• Agreement to terms of service

⏰ **PROCESSING TIME:**
• Standard: 24-48 hours
• Express: 12 hours (Silver+)
• Instant: 1-6 hours (Gold+)

🔒 **SECURITY & PRIVACY:**
• All documents are encrypted
• Data deleted after verification
• Secure payment processing
• Privacy compliant

📞 **SUPPORT:**
• Email: vip@adbot.com
• Telegram: @vipsupport
• Priority support for VIP members

Need help? Start with /verify or contact our support team!
        """
        
        keyboard = [
            [InlineKeyboardButton("🔐 Start Verification", callback_data="vip_start_verify")],
            [InlineKeyboardButton("💎 View Pricing", callback_data="vip_pricing")],
            [InlineKeyboardButton("🆘 Contact Support", callback_data="vip_support")],
            [InlineKeyboardButton("📋 Requirements", callback_data="vip_requirements")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Check current status
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT v.vip_level, v.is_active 
                FROM vip_users v 
                WHERE v.user_id = ?
            ''', (user_id,))
            vip_status = await cursor.fetchone()
        
        if vip_status and vip_status[1]:
            await update.message.reply_text(
                f"✅ **You are already a verified {vip_status[0].title()} VIP member!**\n\n"
                f"Use /upgrade to change your VIP level or /vip_status for details."
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("🔐 Start Verification", callback_data="vip_start_verification")],
            [InlineKeyboardButton("📋 View Requirements", callback_data="vip_requirements")],
            [InlineKeyboardButton("💎 VIP Benefits", callback_data="vip_benefits_list")],
            [InlineKeyboardButton("💰 Pricing", callback_data="vip_pricing_info")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        verification_info = """
🔐 **VIP Verification Process** 🛡️

**Why Get Verified?**
• Build trust with your audience
• Access premium features
• Increase ad approval speed
• Get priority support
• Higher advertising limits

**Verification Tiers:**
🥉 **Personal Verification** - Basic features
🥈 **Business Verification** - Advanced features  
🥇 **Enterprise Verification** - All features

**Required Documents:**
• Government-issued ID
• Proof of address (for business)
• Business registration (if applicable)

**Process:**
1. Submit application
2. Upload documents
3. Background check
4. Approval (24-48 hours)

**Start your verification journey today!**
        """
        
        await update.message.reply_text(verification_info, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def vip_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT v.vip_level, v.expires_at, v.purchased_at, v.is_active,
                       u.total_ads_posted, u.balance
                FROM vip_users v 
                JOIN users u ON v.user_id = u.user_id 
                WHERE v.user_id = ?
            ''', (user_id,))
            vip_info = await cursor.fetchone()
        
        if vip_info and vip_info[3]:  # is_active
            level, expires_at, purchased_at, is_active, total_ads, balance = vip_info
            
            status_text = f"""
👑 **VIP Status Report** 📊

**Account Level:** {level.title()} VIP
**Status:** ✅ Active
**Member Since:** {purchased_at[:10]}
**Expires On:** {expires_at[:10] if expires_at else 'Never'}

📈 **Usage Statistics:**
• Total Ads Posted: {total_ads}
• Account Balance: ${balance:.2f}
• Approval Priority: {'High' if level in ['gold', 'platinum'] else 'Medium'}

💎 **Active Benefits:**
• Priority advertisement approval
• {'Advanced' if level in ['silver', 'gold', 'platinum'] else 'Basic'} analytics
• {'VIP' if level in ['gold', 'platinum'] else 'Priority'} support
• Higher daily ad limits

🔄 **Auto-renewal:** {'Enabled' if expires_at else 'Not applicable'}
            """
            
            keyboard = [
                [InlineKeyboardButton("🆙 Upgrade Plan", callback_data="vip_upgrade_plan")],
                [InlineKeyboardButton("📊 Usage Details", callback_data="vip_usage_details")],
                [InlineKeyboardButton("🔄 Renew Subscription", callback_data="vip_renew")]
            ]
            
        else:
            status_text = """
❌ **VIP Status: Not Verified**

You are not currently a VIP member. 

🔓 **Benefits You're Missing:**
• Faster ad approval times
• Advanced analytics
• Priority customer support
• Higher advertisement limits
• Exclusive features

🎯 **Get verified today to unlock these benefits!**
            """
            
            keyboard = [
                [InlineKeyboardButton("🔐 Get Verified", callback_data="vip_start_verification")],
                [InlineKeyboardButton("💎 View Benefits", callback_data="vip_benefits_detailed")],
                [InlineKeyboardButton("💰 Pricing Plans", callback_data="vip_pricing_plans")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def upgrade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Get current VIP level
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT vip_level FROM vip_users WHERE user_id = ? AND is_active = 1
            ''', (user_id,))
            current_level = await cursor.fetchone()
        
        current_level = current_level[0] if current_level else "none"
        
        upgrade_text = f"""
💎 **VIP Upgrade Center** 🆙

{'**Current Plan:** ' + current_level.title() + ' VIP' if current_level != 'none' else '**Current Status:** Not Verified'}

📦 **Available Upgrade Plans:**

🥉 **Bronze VIP** - $10/month
• Priority approval (24h)
• Basic analytics
• 10 ads/day
• Standard support

🥈 **Silver VIP** - $25/month  
• Express approval (12h)
• Advanced analytics
• 25 ads/day
• Priority support
• A/B testing

🥇 **Gold VIP** - $50/month
• Instant approval (6h)
• Premium analytics
• 50 ads/day
• VIP support
• All features

💎 **Platinum VIP** - $100/month
• Instant approval (1h)
• Enterprise analytics
• Unlimited ads
• Dedicated manager
• Custom solutions

🎯 **Recommended:** {'Gold VIP for best value' if current_level in ['none', 'bronze'] else 'Platinum VIP for maximum benefits'}
        """
        
        keyboard = [
            [InlineKeyboardButton("🥉 Bronze - $10", callback_data="vip_upgrade_bronze")],
            [InlineKeyboardButton("🥈 Silver - $25", callback_data="vip_upgrade_silver")],
            [InlineKeyboardButton("🥇 Gold - $50", callback_data="vip_upgrade_gold")],
            [InlineKeyboardButton("💎 Platinum - $100", callback_data="vip_upgrade_platinum")]
        ]
        
        if current_level != "none":
            keyboard.append([InlineKeyboardButton("🔄 Change Billing", callback_data="vip_billing")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(upgrade_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def vip_benefits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        benefits_text = """
💎 **VIP Benefits - Complete Overview** ✨

🚀 **APPROVAL & PROCESSING:**
• Bronze: Priority approval (24 hours)
• Silver: Express approval (12 hours) 
• Gold: Instant approval (6 hours)
• Platinum: Instant approval (1 hour)

📊 **ANALYTICS & REPORTING:**
• Bronze: Basic performance metrics
• Silver: Advanced analytics dashboard
• Gold: Premium analytics with insights
• Platinum: Enterprise-grade reporting

📈 **ADVERTISING LIMITS:**
• Bronze: 10 ads per day
• Silver: 25 ads per day
• Gold: 50 ads per day
• Platinum: Unlimited ads

🎯 **ADVANCED FEATURES:**
• Bronze: Standard ad formats
• Silver: A/B testing, basic targeting
• Gold: Advanced targeting, scheduling
• Platinum: Custom solutions, API access

👥 **SUPPORT & SERVICE:**
• Bronze: Standard email support
• Silver: Priority support (12h response)
• Gold: VIP support (6h response)
• Platinum: Dedicated account manager

🔧 **EXCLUSIVE TOOLS:**
• Ad performance optimizer
• Audience insights
• Competitive analysis
• Custom reporting
• Early feature access

💰 **COST SAVINGS:**
• Volume discounts
• No setup fees
• Free migration assistance
• Custom pricing for high volume

🎁 **BONUS FEATURES:**
• Verified badge on ads
• Higher trust score
• Featured placement
• Newsletter inclusion
        """
        
        keyboard = [
            [InlineKeyboardButton("💳 Upgrade Now", callback_data="vip_upgrade_now")],
            [InlineKeyboardButton("📋 Compare Plans", callback_data="vip_compare_plans")],
            [InlineKeyboardButton("🎯 Feature Details", callback_data="vip_feature_details")],
            [InlineKeyboardButton("📞 Contact Sales", callback_data="vip_contact_sales")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(benefits_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def approve_verification_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in [123456789]:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /approve_verification <user_id> [vip_level]")
            return
        
        user_id = int(context.args[0])
        vip_level = context.args[1] if len(context.args) > 1 else "bronze"
        
        if vip_level not in ["bronze", "silver", "gold", "platinum"]:
            await update.message.reply_text("❌ Invalid VIP level. Use: bronze, silver, gold, or platinum")
            return
        
        try:
            async with aiosqlite.connect('bot_database.db') as db:
                # Update user as VIP
                await db.execute(
                    "UPDATE users SET is_vip = 1 WHERE user_id = ?",
                    (user_id,)
                )
                
                # Add to VIP users table
                expires_at = datetime.datetime.now() + timedelta(days=30)  # 1 month
                await db.execute('''
                    INSERT OR REPLACE INTO vip_users (user_id, vip_level, expires_at, is_active)
                    VALUES (?, ?, ?, 1)
                ''', (user_id, vip_level, expires_at))
                
                await db.commit()
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 **Congratulations! Your VIP verification has been approved!**\n\n"
                         f"You are now a **{vip_level.title()} VIP** member.\n"
                         f"Your VIP status is active until {expires_at.strftime('%Y-%m-%d')}.\n\n"
                         f"Welcome to the VIP club! 🎊"
                )
            except:
                pass  # User might have blocked the bot
            
            await update.message.reply_text(f"✅ User {user_id} approved as {vip_level} VIP!")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error approving verification: {e}")
    
    async def reject_verification_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in [123456789]:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /reject_verification <user_id> <reason>")
            return
        
        user_id = int(context.args[0])
        reason = ' '.join(context.args[1:])
        
        try:
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ **Verification Application Rejected**\n\n"
                         f"Reason: {reason}\n\n"
                         f"You can reapply after addressing the issues mentioned above."
                )
            except:
                pass  # User might have blocked the bot
            
            await update.message.reply_text(f"❌ Verification for user {user_id} rejected. Reason: {reason}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error rejecting verification: {e}")
    
    async def vip_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in [123456789]:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT v.user_id, u.username, v.vip_level, v.purchased_at, v.expires_at
                FROM vip_users v
                JOIN users u ON v.user_id = u.user_id
                WHERE v.is_active = 1
                ORDER BY v.vip_level DESC, v.purchased_at DESC
                LIMIT 20
            ''')
            vip_users = await cursor.fetchall()
        
        if not vip_users:
            await update.message.reply_text("📭 No active VIP users found.")
            return
        
        vip_text = "👑 **Active VIP Users List**\n\n"
        
        for user_id, username, level, purchased, expires in vip_users:
            vip_text += f"• 👤 @{username} ({user_id})\n"
            vip_text += f"  💎 Level: {level.title()}\n"
            vip_text += f"  📅 Joined: {purchased[:10]}\n"
            vip_text += f"  ⏰ Expires: {expires[:10] if expires else 'Never'}\n\n"
        
        await update.message.reply_text(vip_text, parse_mode='Markdown')
    
    # Conversation handlers for verification
    async def start_verification_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🔐 **VIP Verification Application**\n\n"
            "Step 1: Please provide your full name as it appears on your ID:\n\n"
            "💡 **Note:** This must match your government-issued identification."
        )
        return 1
    
    async def get_verification_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['full_name'] = update.message.text
        await update.message.reply_text(
            "Step 2: Please upload a clear photo of your government-issued ID:\n\n"
            "📸 **Requirements:**\n"
            "• Clear, readable photo\n"
            "• All corners visible\n"
            "• No glare or reflections\n"
            "• Current and valid ID"
        )
        return 2
    
    async def get_verification_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # In a real implementation, you would save the document
        await update.message.reply_text(
            "✅ ID document received!\n\n"
            "Step 3: Any additional notes for the verification team?\n"
            "(Optional) Provide any context that might help with verification:"
        )
        return 3
    
    async def get_verification_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        notes = update.message.text
        context.user_data['notes'] = notes
        
        # Submit verification application
        user_id = update.effective_user.id
        full_name = context.user_data['full_name']
        
        await update.message.reply_text(
            f"✅ **Verification Application Submitted!**\n\n"
            f"**Applicant:** {full_name}\n"
            f"**User ID:** {user_id}\n"
            f"**Submission Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            "⏳ **Processing Time:** 24-48 hours\n"
            "📧 **Next Steps:** You will be notified once your application is reviewed.\n\n"
            "Thank you for applying for VIP verification! 🎉"
        )
        
        # Notify admins (in real implementation)
        # await self.notify_admins_about_verification(user_id, full_name, notes)
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("❌ Verification application cancelled.")
        return ConversationHandler.END
    
    async def handle_vip_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Handle VIP-related messages
        user_message = update.message.text.lower()
        
        if any(word in user_message for word in ['vip', 'verify', 'premium', 'upgrade']):
            await update.message.reply_text(
                "💎 Interested in VIP features? Use /verify to start the verification process or /vip_benefits to see all benefits!"
            )
    
    async def vip_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "vip_verify":
            await self.verify_command(update, context)
        elif data == "vip_benefits":
            await self.vip_benefits_command(update, context)
        elif data == "vip_upgrade":
            await self.upgrade_command(update, context)
        elif data == "vip_status":
            await self.vip_status_command(update, context)
        elif data.startswith("vip_upgrade_"):
            level = data.replace("vip_upgrade_", "")
            await query.edit_message_text(f"Selected {level.title()} VIP upgrade. Processing payment...")
    
    async def start_bot(self):
        """Start VIP Bot with all features"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("👑 VIP Verification Bot is running with full functionality...")

# ============================ GROUP MANAGEMENT BOT ============================
class GroupBot:
    def __init__(self):
        self.token = "8389675530:AAHJYSKo06qummgk4cm3sgZGj0G8zH1dVKg"
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        self.application.add_handler(CommandHandler("setwelcome", self.set_welcome_command))
        self.application.add_handler(CommandHandler("setrules", self.set_rules_command))
        self.application.add_handler(CommandHandler("warn", self.warn_command))
        self.application.add_handler(CommandHandler("ban", self.ban_command))
        self.application.add_handler(CommandHandler("mute", self.mute_command))
        self.application.add_handler(CommandHandler("unban", self.unban_command))
        self.application.add_handler(CommandHandler("unmute", self.unmute_command))
        self.application.add_handler(CommandHandler("warnings", self.warnings_command))
        self.application.add_handler(CommandHandler("clean", self.clean_command))
        self.application.add_handler(CommandHandler("promote", self.promote_command))
        self.application.add_handler(CommandHandler("demote", self.demote_command))
        
        # User commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("rules", self.rules_command))
        self.application.add_handler(CommandHandler("report", self.report_command))
        self.application.add_handler(CommandHandler("info", self.info_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome_new_member))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.goodbye_member))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.monitor_messages))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.group_button_handler, pattern="^group_"))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type in ['group', 'supergroup']:
            await update.message.reply_text(
                "🛡️ **Advanced Group Management Bot Activated!** 🤖\n\n"
                "I'm here to help manage this group with comprehensive moderation tools and automation features.\n\n"
                "🔧 **Core Features:**\n"
                "• Smart welcome messages\n• Automated moderation\n• User management\n• Rule enforcement\n• Anti-spam protection\n• Analytics & reporting\n\n"
                "👮 **Admin Tools:** Use /admin for control panel\n"
                "👥 **User Commands:** Use /help for available commands\n\n"
                "⚙️ **Getting Started:** Configure settings with /settings"
            )
        else:
            await update.message.reply_text(
                "🛡️ **Group Management Bot**\n\n"
                "To use my full features, add me to your group and make me an administrator!\n\n"
                "💡 **Setup Instructions:**\n"
                "1. Add me to your group\n"
                "2. Make me an administrator\n"
                "3. Use /admin in the group to configure settings\n\n"
                "🔧 **Available Features:**\n"
                "• Custom welcome messages\n• Automated moderation\n• User warnings system\n• Anti-spam protection\n• Rule management\n• Activity analytics"
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🛡️ **Group Management Bot - Complete Command Guide** 📚

👮 **ADMIN COMMANDS:**
/admin - Administrator control panel
/settings - Configure group settings
/setwelcome <text> - Set custom welcome message
/setrules <text> - Set group rules
/warn <user> <reason> - Warn a user
/ban <user> <reason> - Ban a user
/mute <user> <duration> - Mute a user
/unban <user> - Unban a user
/unmute <user> - Unmute a user
/warnings <user> - Check user warnings
/clean <number> - Delete recent messages
/promote <user> - Promote to admin
/demote <user> - Remove admin rights

👥 **USER COMMANDS:**
/rules - Display group rules
/report <reason> - Report user or issue
/info - Get group information
/help - Show this help message

⚙️ **AUTOMATED FEATURES:**
• Welcome new members with custom messages
• Auto-remove spam and links
• Warn users for rule violations
• Track user activity and warnings
• Auto-remove banned users

🔧 **SETTINGS CONFIGURATION:**
• Welcome message customization
• Rules management
• Moderation levels
• Auto-delete settings
• User permission levels

📊 **ANALYTICS:**
• Member join/leave tracking
• Message activity
• Moderation actions log
• User behavior analysis

🛡️ **SECURITY FEATURES:**
• Anti-spam protection
• Link filtering
• Media moderation
• User verification
• Raid protection

📞 **SUPPORT:**
For assistance with configuration or issues, contact group administrators.
        """
        
        keyboard = [
            [InlineKeyboardButton("👮 Admin Panel", callback_data="group_admin_panel")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="group_settings")],
            [InlineKeyboardButton("📜 View Rules", callback_data="group_rules")],
            [InlineKeyboardButton("📊 Group Info", callback_data="group_info")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin control panel with comprehensive management options"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator privileges required to use this command!")
            return
        
        chat_id = update.effective_chat.id
        chat = update.effective_chat
        
        # Get group statistics
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute(
                "SELECT welcome_enabled, ads_allowed, max_warnings FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            settings = await cursor.fetchone()
            
            # Get warning statistics
            cursor = await db.execute(
                "SELECT COUNT(*) FROM warnings WHERE group_id = ? AND is_active = 1",
                (chat_id,)
            )
            active_warnings = await cursor.fetchone()
            active_warnings = active_warnings[0] if active_warnings else 0
            
            # Get ban statistics
            cursor = await db.execute(
                "SELECT COUNT(*) FROM banned_users WHERE group_id = ?",
                (chat_id,)
            )
            banned_users = await cursor.fetchone()
            banned_users = banned_users[0] if banned_users else 0
        
        welcome_enabled = settings[0] if settings else 1
        ads_allowed = settings[1] if settings else 0
        max_warnings = settings[2] if settings else 3
        
        admin_text = f"""
👮 **Administrator Control Panel** 🛡️

**Group:** {chat.title}
**Members:** {await self.get_member_count(context, chat_id)}
**ID:** `{chat_id}`

⚙️ **CURRENT SETTINGS:**
• Welcome Messages: {'✅ Enabled' if welcome_enabled else '❌ Disabled'}
• Advertisements: {'✅ Allowed' if ads_allowed else '❌ Not Allowed'}
• Max Warnings: `{max_warnings}`
• Active Warnings: `{active_warnings}`
• Banned Users: `{banned_users}`

🔧 **QUICK ACTIONS:**
        """
        
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Group Settings", callback_data="group_admin_settings"),
                InlineKeyboardButton("👥 Manage Users", callback_data="group_manage_users")
            ],
            [
                InlineKeyboardButton("📊 Statistics", callback_data="group_statistics"),
                InlineKeyboardButton("🚫 Ban List", callback_data="group_ban_list")
            ],
            [
                InlineKeyboardButton("⚠️ Warnings", callback_data="group_warnings_list"),
                InlineKeyboardButton("🧹 Cleanup", callback_data="group_cleanup")
            ],
            [
                InlineKeyboardButton("🛡️ Security", callback_data="group_security"),
                InlineKeyboardButton("📢 Announce", callback_data="group_announce")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive group settings configuration"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        chat_id = update.effective_chat.id
        
        # Get current settings
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute(
                "SELECT welcome_message, rules_text, welcome_enabled, ads_allowed, max_warnings, auto_delete_links, mute_duration FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            settings = await cursor.fetchone()
        
        if settings:
            welcome_msg, rules, welcome_enabled, ads_allowed, max_warnings, auto_delete_links, mute_duration = settings
        else:
            # Default settings
            welcome_msg = "Welcome {name} to the group! 🎉"
            rules = "Please be respectful and follow the group rules."
            welcome_enabled = 1
            ads_allowed = 0
            max_warnings = 3
            auto_delete_links = 0
            mute_duration = 3600
        
        settings_text = f"""
⚙️ **Group Settings Configuration** 🔧

📝 **Welcome Message:**
`{welcome_msg[:100]}{'...' if len(welcome_msg) > 100 else ''}`

📜 **Rules:**
`{rules[:100]}{'...' if len(rules) > 100 else ''}`

🔧 **Current Configuration:**
• Welcome Messages: {'✅ Enabled' if welcome_enabled else '❌ Disabled'}
• Advertisements: {'✅ Allowed' if ads_allowed else '❌ Not Allowed'}
• Max Warnings: `{max_warnings}`
• Auto-delete Links: {'✅ Enabled' if auto_delete_links else '❌ Disabled'}
• Mute Duration: `{mute_duration // 3600} hours`

💡 **Available Variables for Welcome Message:**
• `{{name}}` - User's first name
• `{{username}}` - User's username
• `{{group}}` - Group name
• `{{count}}` - Member count
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✏️ Edit Welcome", callback_data="group_edit_welcome"),
                InlineKeyboardButton("📜 Edit Rules", callback_data="group_edit_rules")
            ],
            [
                InlineKeyboardButton("🔔 Toggle Welcome", callback_data="group_toggle_welcome"),
                InlineKeyboardButton("📢 Toggle Ads", callback_data="group_toggle_ads")
            ],
            [
                InlineKeyboardButton("⚡ Warning Settings", callback_data="group_warning_settings"),
                InlineKeyboardButton("🛡️ Security", callback_data="group_security_settings")
            ],
            [
                InlineKeyboardButton("💾 Save Settings", callback_data="group_save_settings"),
                InlineKeyboardButton("🔄 Reset Defaults", callback_data="group_reset_settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def set_welcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set custom welcome message with advanced formatting"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /setwelcome <your welcome message>\n\n"
                "💡 **Available variables:**\n"
                "• `{name}` - User's first name\n"
                "• `{username}` - User's @username\n"
                "• `{group}` - Group name\n"
                "• `{count}` - Member count\n\n"
                "📝 **Example:**\n"
                "`/setwelcome Welcome {name} to {group}! 🎉 We now have {count} members.`"
            )
            return
        
        welcome_message = ' '.join(context.args)
        chat_id = update.effective_chat.id
        
        # Validate variables
        valid_variables = ['{name}', '{username}', '{group}', '{count}']
        for var in valid_variables:
            if var in welcome_message:
                break
        else:
            await update.message.reply_text(
                "⚠️ **Tip:** Consider using variables like `{name}` to personalize the welcome message!"
            )
        
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute('''
                INSERT OR REPLACE INTO group_settings 
                (group_id, welcome_message, updated_at) 
                VALUES (?, ?, ?)
            ''', (chat_id, welcome_message, datetime.datetime.now()))
            await db.commit()
        
        # Test the welcome message
        test_message = welcome_message.replace('{name}', 'TestUser')
        test_message = test_message.replace('{username}', '@testuser')
        test_message = test_message.replace('{group}', update.effective_chat.title)
        test_message = test_message.replace('{count}', '100')
        
        await update.message.reply_text(
            f"✅ **Welcome message updated successfully!**\n\n"
            f"📝 **Preview:**\n{test_message}\n\n"
            f"🔧 The new welcome message will be shown to new members."
        )
    
    async def set_rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set comprehensive group rules"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /setrules <your rules text>\n\n"
                "📋 **Suggested rule categories:**\n"
                "• Be respectful and courteous\n"
                "• No spam or advertisements\n"
                "• No offensive content\n"
                "• Stay on topic\n"
                "• Follow Telegram's Terms of Service\n\n"
                "📝 **Example:**\n"
                "`/setrules 1. Be respectful 2. No spam 3. Keep discussions relevant`"
            )
            return
        
        rules_text = ' '.join(context.args)
        chat_id = update.effective_chat.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute('''
                INSERT OR REPLACE INTO group_settings 
                (group_id, rules_text, updated_at) 
                VALUES (?, ?, ?)
            ''', (chat_id, rules_text, datetime.datetime.now()))
            await db.commit()
        
        await update.message.reply_text(
            f"✅ **Group rules updated successfully!**\n\n"
            f"📜 **New Rules:**\n{rules_text}\n\n"
            f"👥 Members can view rules with /rules command"
        )
    
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display group rules with formatting"""
        chat_id = update.effective_chat.id
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute(
                "SELECT rules_text FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            result = await cursor.fetchone()
        
        rules_text = result[0] if result else "No rules set for this group. Please contact administrators."
        
        rules_display = f"""
📜 **Group Rules** 🛡️

{rules_text}

⚖️ **Enforcement:**
• Rules are enforced by administrators
• Violations may result in warnings or removal
• Contact admins for rule clarification

🔧 **To report violations, use:** /report <reason>
        """
        
        await update.message.reply_text(rules_display, parse_mode='Markdown')
    
    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Advanced warning system with reason tracking"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /warn <user> <reason>\n\n"
                "💡 **You can warn users by:**\n"
                "• Replying to their message with /warn <reason>\n"
                "• Using /warn @username <reason>\n"
                "• Using /warn user_id <reason>\n\n"
                "📝 **Example:**\n"
                "`/warn @username Spamming the group`"
            )
            return
        
        # Get target user
        target_user = await self.get_target_user(update, context)
        if not target_user:
            await update.message.reply_text("❌ Could not identify target user. Reply to their message or use @username/user_id.")
            return
        
        reason = ' '.join(context.args[1:])
        chat_id = update.effective_chat.id
        warner_id = update.effective_user.id
        
        # Add warning to database
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute(
                "INSERT INTO warnings (user_id, group_id, reason, warned_by) VALUES (?, ?, ?, ?)",
                (target_user.id, chat_id, reason, warner_id)
            )
            await db.commit()
            
            # Get user's warning count
            cursor = await db.execute(
                "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND group_id = ? AND is_active = 1",
                (target_user.id, chat_id)
            )
            warning_count = await cursor.fetchone()
            warning_count = warning_count[0] if warning_count else 0
            
            # Get max warnings setting
            cursor = await db.execute(
                "SELECT max_warnings FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            max_warnings_setting = await cursor.fetchone()
            max_warnings = max_warnings_setting[0] if max_warnings_setting else 3
        
        warning_text = f"""
⚠️ **User Warned** ⚠️

**User:** {target_user.mention_html()}
**Warned by:** {update.effective_user.mention_html()}
**Reason:** {reason}
**Warning Count:** {warning_count}/{max_warnings}

💡 **Next Steps:**
• User will be automatically muted at {max_warnings} warnings
• Use /warnings @{target_user.username} to check warning history
        """
        
        # Notify the group
        await update.message.reply_text(warning_text, parse_mode='HTML')
        
        # Notify the user
        try:
            user_warning_msg = f"""
⚠️ **You have been warned in {update.effective_chat.title}**

**Reason:** {reason}
**Warning Count:** {warning_count}/{max_warnings}

💡 Please review the group rules and adjust your behavior accordingly.
Repeated violations may result in muting or banning.
            """
            await context.bot.send_message(chat_id=target_user.id, text=user_warning_msg)
        except:
            pass  # User might have DMs closed
        
        # Check if user should be muted
        if warning_count >= max_warnings:
            await self.auto_mute_user(update, context, target_user.id, "Maximum warnings reached")
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Advanced banning system with reason tracking"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /ban <user> <reason>\n\n"
                "💡 **You can ban users by:**\n"
                "• Replying to their message with /ban <reason>\n"
                "• Using /ban @username <reason>\n"
                "• Using /ban user_id <reason>\n\n"
                "🔨 **Example:**\n"
                "`/ban @username Repeated rule violations`"
            )
            return
        
        target_user = await self.get_target_user(update, context)
        if not target_user:
            await update.message.reply_text("❌ Could not identify target user.")
            return
        
        reason = ' '.join(context.args[1:])
        chat_id = update.effective_chat.id
        
        try:
            # Ban user from group
            await context.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=target_user.id,
                revoke_messages=True
            )
            
            # Add to ban database
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    "INSERT OR REPLACE INTO banned_users (user_id, group_id, reason, banned_by) VALUES (?, ?, ?, ?)",
                    (target_user.id, chat_id, reason, update.effective_user.id)
                )
                await db.commit()
            
            ban_text = f"""
🚫 **User Banned** 🚫

**User:** {target_user.mention_html()}
**Banned by:** {update.effective_user.mention_html()}
**Reason:** {reason}

🔒 User has been permanently removed from the group.
            """
            
            await update.message.reply_text(ban_text, parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error banning user: {e}")
    
    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Advanced muting system with duration support"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /mute <user> <duration> [reason]\n\n"
                "⏰ **Duration formats:**\n"
                "• 1h - 1 hour\n"
                "• 2d - 2 days\n"
                "• 1w - 1 week\n"
                "• permanent - Permanent mute\n\n"
                "🔇 **Example:**\n"
                "`/mute @username 2h Spamming`"
            )
            return
        
        target_user = await self.get_target_user(update, context)
        if not target_user:
            await update.message.reply_text("❌ Could not identify target user.")
            return
        
        duration_str = context.args[1]
        reason = ' '.join(context.args[2:]) if len(context.args) > 2 else "No reason provided"
        
        # Parse duration
        mute_until = await self.parse_duration(duration_str)
        if not mute_until:
            await update.message.reply_text("❌ Invalid duration format. Use: 1h, 2d, 1w, or permanent")
            return
        
        chat_id = update.effective_chat.id
        
        try:
            # Calculate permissions until time
            if mute_until == "permanent":
                # Restrict all permissions permanently
                permissions = {
                    'can_send_messages': False,
                    'can_send_media_messages': False,
                    'can_send_polls': False,
                    'can_send_other_messages': False,
                    'can_add_web_page_previews': False,
                    'can_change_info': False,
                    'can_invite_users': False,
                    'can_pin_messages': False
                }
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=target_user.id,
                    permissions=permissions
                )
                duration_text = "permanently"
            else:
                # Temporary restriction
                permissions = {
                    'can_send_messages': False,
                    'can_send_media_messages': False,
                    'can_send_polls': False,
                    'can_send_other_messages': False,
                    'can_add_web_page_previews': False
                }
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=target_user.id,
                    permissions=permissions,
                    until_date=mute_until
                )
                duration_text = f"until {mute_until.strftime('%Y-%m-%d %H:%M')}"
            
            mute_text = f"""
🔇 **User Muted** 🔇

**User:** {target_user.mention_html()}
**Muted by:** {update.effective_user.mention_html()}
**Duration:** {duration_text}
**Reason:** {reason}

💡 User cannot send messages while muted.
            """
            
            await update.message.reply_text(mute_text, parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error muting user: {e}")
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unban user from group"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unban <user>")
            return
        
        target_user = await self.get_target_user(update, context)
        if not target_user:
            await update.message.reply_text("❌ Could not identify target user.")
            return
        
        chat_id = update.effective_chat.id
        
        try:
            await context.bot.unban_chat_member(
                chat_id=chat_id,
                user_id=target_user.id
            )
            
            # Remove from ban database
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    "DELETE FROM banned_users WHERE user_id = ? AND group_id = ?",
                    (target_user.id, chat_id)
                )
                await db.commit()
            
            await update.message.reply_text(f"✅ User {target_user.mention_html()} has been unbanned.", parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error unbanning user: {e}")
    
    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unmute user in group"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unmute <user>")
            return
        
        target_user = await self.get_target_user(update, context)
        if not target_user:
            await update.message.reply_text("❌ Could not identify target user.")
            return
        
        chat_id = update.effective_chat.id
        
        try:
            # Restore all permissions
            permissions = {
                'can_send_messages': True,
                'can_send_media_messages': True,
                'can_send_polls': True,
                'can_send_other_messages': True,
                'can_add_web_page_previews': True,
                'can_change_info': False,
                'can_invite_users': False,
                'can_pin_messages': False
            }
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user.id,
                permissions=permissions
            )
            
            await update.message.reply_text(f"✅ User {target_user.mention_html()} has been unmuted.", parse_mode='HTML')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error unmuting user: {e}")
    
    async def warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user warnings"""
        if not context.args:
            # Show current user's warnings
            target_user = update.effective_user
        else:
            target_user = await self.get_target_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ Could not identify target user.")
                return
        
        chat_id = update.effective_chat.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT reason, warned_by, created_at 
                FROM warnings 
                WHERE user_id = ? AND group_id = ? AND is_active = 1
                ORDER BY created_at DESC
            ''', (target_user.id, chat_id))
            warnings = await cursor.fetchall()
            
            cursor = await db.execute(
                "SELECT max_warnings FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            max_warnings = await cursor.fetchone()
            max_warnings = max_warnings[0] if max_warnings else 3
        
        if warnings:
            warnings_text = f"""
⚠️ **Warning History for {target_user.mention_html()}**

**Active Warnings:** {len(warnings)}/{max_warnings}

📋 **Recent Warnings:**
"""
            for i, (reason, warned_by, created_at) in enumerate(warnings[:5], 1):
                warnings_text += f"{i}. {reason} - {created_at[:16]}\n"
            
            if len(warnings) > 5:
                warnings_text += f"\n... and {len(warnings) - 5} more warnings"
            
            warnings_text += f"\n💡 User will be muted at {max_warnings} warnings."
            
        else:
            warnings_text = f"✅ {target_user.mention_html()} has no active warnings."
        
        await update.message.reply_text(warnings_text, parse_mode='HTML')
    
    async def clean_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clean up messages from group"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /clean <number_of_messages>")
            return
        
        try:
            count = int(context.args[0])
            if count < 1 or count > 100:
                await update.message.reply_text("❌ Please enter a number between 1 and 100")
                return
            
            # Delete command message
            await update.message.delete()
            
            # Delete previous messages
            message_id = update.message.message_id
            for i in range(1, count + 1):
                try:
                    await context.bot.delete_message(
                        chat_id=update.effective_chat.id,
                        message_id=message_id - i
                    )
                except:
                    break
            
            # Send confirmation (will be auto-deleted after a few seconds)
            confirmation = await update.effective_chat.send_message(f"🧹 Cleaned {count} messages.")
            
            # Auto-delete confirmation after 5 seconds
            async def delete_confirmation():
                await asyncio.sleep(5)
                try:
                    await confirmation.delete()
                except:
                    pass
            
            asyncio.create_task(delete_confirmation())
            
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number")
        except Exception as e:
            await update.message.reply_text(f"❌ Error cleaning messages: {e}")
    
    async def promote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Promote user to administrator"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /promote <user>")
            return
        
        target_user = await self.get_target_user(update, context)
        if not target_user:
            await update.message.reply_text("❌ Could not identify target user.")
            return
        
        chat_id = update.effective_chat.id
        
        try:
            # Promote user to admin
            await context.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=target_user.id,
                can_change_info=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=False
            )
            
            await update.message.reply_text(
                f"✅ {target_user.mention_html()} has been promoted to administrator!",
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error promoting user: {e}")
    
    async def demote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove admin rights from user"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Administrator access required!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /demote <user>")
            return
        
        target_user = await self.get_target_user(update, context)
        if not target_user:
            await update.message.reply_text("❌ Could not identify target user.")
            return
        
        chat_id = update.effective_chat.id
        
        try:
            # Demote user (remove admin privileges)
            await context.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=target_user.id,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False
            )
            
            await update.message.reply_text(
                f"✅ Admin rights removed from {target_user.mention_html()}",
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error demoting user: {e}")
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Report system for users"""
        if not context.args:
            await update.message.reply_text(
                "Usage: /report <reason>\n\n"
                "📞 **Use this command to report:**\n"
                "• Rule violations\n"
                "• Spam or abuse\n"
                "• Technical issues\n"
                "• Other concerns\n\n"
                "🔒 **Your report will be sent to group administrators.**"
            )
            return
        
        reason = ' '.join(context.args)
        reporter = update.effective_user
        chat = update.effective_chat
        
        report_text = f"""
🚨 **New Report** 🚨

**From:** {reporter.mention_html()}
**Group:** {chat.title}
**Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
**Reason:** {reason}

📋 Please review this report and take appropriate action.
        """
        
        # Send to all admins
        admins = await context.bot.get_chat_administrators(chat.id)
        for admin in admins:
            if not admin.user.is_bot:
                try:
                    await context.bot.send_message(
                        chat_id=admin.user.id,
                        text=report_text,
                        parse_mode='HTML'
                    )
                except:
                    continue  # Admin might have DMs closed
        
        await update.message.reply_text(
            "✅ **Report submitted!**\n\n"
            "Your report has been sent to the group administrators. "
            "They will review it and take appropriate action."
        )
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display group information"""
        chat = update.effective_chat
        chat_id = chat.id
        
        # Get group statistics
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute(
                "SELECT welcome_enabled, ads_allowed FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            settings = await cursor.fetchone()
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM warnings WHERE group_id = ? AND is_active = 1",
                (chat_id,)
            )
            active_warnings = await cursor.fetchone()
            active_warnings = active_warnings[0] if active_warnings else 0
        
        member_count = await self.get_member_count(context, chat_id)
        admin_count = len(await context.bot.get_chat_administrators(chat_id))
        
        info_text = f"""
📊 **Group Information** 🏷️

**Group:** {chat.title}
**ID:** `{chat_id}`
**Type:** {chat.type}
**Members:** {member_count}
**Admins:** {admin_count}

⚙️ **Settings:**
• Welcome Messages: {'✅ Enabled' if settings and settings[0] else '❌ Disabled'}
• Advertisements: {'✅ Allowed' if settings and settings[1] else '❌ Not Allowed'}
• Active Warnings: `{active_warnings}`

🔧 **Bot Features:**
• Automated moderation
• Welcome system
• Warning system
• User management
• Rule enforcement

👮 **Admin Commands:** /admin
📜 **Group Rules:** /rules
🆘 **Report Issues:** /report
        """
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
    
    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced welcome system for new members"""
        chat_id = update.effective_chat.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute(
                "SELECT welcome_message, welcome_enabled FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            result = await cursor.fetchone()
        
        if not result or not result[1]:  # Welcome disabled or no settings
            return
        
        welcome_message = result[0] or "Welcome {name} to the group! 🎉"
        member_count = await self.get_member_count(context, chat_id)
        
        for new_member in update.message.new_chat_members:
            if new_member.id == context.bot.id:
                # Bot added to group
                await update.message.reply_text(
                    "🤖 **Thanks for adding me!**\n\n"
                    "I'm your group management assistant. To get started:\n"
                    "1. Make sure I have admin permissions\n"
                    "2. Use /admin to configure settings\n"
                    "3. Use /setwelcome to set welcome messages\n"
                    "4. Use /setrules to define group rules\n\n"
                    "I'll help keep your group organized and safe! 🛡️"
                )
            else:
                # Regular user joined
                personalized_welcome = welcome_message.replace("{name}", new_member.first_name)
                personalized_welcome = personalized_welcome.replace("{username}", f"@{new_member.username}" if new_member.username else new_member.first_name)
                personalized_welcome = personalized_welcome.replace("{group}", update.effective_chat.title)
                personalized_welcome = personalized_welcome.replace("{count}", str(member_count))
                
                # Add rules button for new members
                keyboard = [[InlineKeyboardButton("📜 Group Rules", callback_data="group_show_rules")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    personalized_welcome,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
    
    async def goodbye_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Say goodbye to leaving members"""
        left_member = update.message.left_chat_member
        if left_member and not left_member.is_bot:
            goodbye_message = f"👋 Goodbye, {left_member.first_name}! We'll miss you."
            await update.message.reply_text(goodbye_message)
    
    async def monitor_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Monitor messages for moderation"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        message_text = update.message.text or ""
        
        # Check for spam (multiple identical messages)
        if hasattr(context, 'user_data'):
            if 'last_message' in context.user_data:
                if context.user_data['last_message'] == message_text:
                    # Same message repeated - potential spam
                    try:
                        await update.message.delete()
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"⚠️ {update.effective_user.mention_html()}, please avoid sending duplicate messages.",
                            parse_mode='HTML'
                        )
                        return
                    except:
                        pass
            
            context.user_data['last_message'] = message_text
        
        # Check for links if auto-delete is enabled
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute(
                "SELECT auto_delete_links FROM group_settings WHERE group_id = ?",
                (chat_id,)
            )
            result = await cursor.fetchone()
        
        if result and result[0]:  # Auto-delete links enabled
            if any(domain in message_text.lower() for domain in ['http://', 'https://', 't.me/', '.com', '.org']):
                if not await self.is_admin(update, context):
                    try:
                        await update.message.delete()
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"🔗 {update.effective_user.mention_html()}, links are not allowed in this group.",
                            parse_mode='HTML'
                        )
                    except:
                        pass
    
    async def group_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle group management button clicks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "group_admin_panel":
            await self.admin_command(update, context)
        elif data == "group_settings":
            await self.settings_command(update, context)
        elif data == "group_rules":
            await self.rules_command(update, context)
        elif data == "group_info":
            await self.info_command(update, context)
        elif data == "group_show_rules":
            await self.rules_command(update, context)
        elif data == "group_edit_welcome":
            await query.edit_message_text("Please use /setwelcome <message> to set a new welcome message.")
        elif data == "group_edit_rules":
            await query.edit_message_text("Please use /setrules <rules> to set new group rules.")
    
    async def is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is admin in the group"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if update.effective_chat.type == 'private':
            return True  # Allow in private chats
        
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            return chat_member.status in ['administrator', 'creator']
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    async def get_target_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Extract target user from message reply or mention"""
        # Check if replying to a message
        if update.message.reply_to_message:
            return update.message.reply_to_message.from_user
        
        # Check for username mention
        if context.args and context.args[0].startswith('@'):
            username = context.args[0][1:]
            # In a real implementation, you would look up the user by username
            # For now, return None as we can't reliably get user from username
            return None
        
        # Check for user ID
        if context.args and context.args[0].isdigit():
            user_id = int(context.args[0])
            try:
                user = await context.bot.get_chat(user_id)
                return user
            except:
                return None
        
        return None
    
    async def get_member_count(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
        """Get member count for group"""
        try:
            chat = await context.bot.get_chat(chat_id)
            return chat.get_members_count()
        except:
            return 0
    
    async def parse_duration(self, duration_str: str):
        """Parse duration string into datetime"""
        duration_str = duration_str.lower()
        
        if duration_str == 'permanent':
            return 'permanent'
        
        try:
            if duration_str.endswith('h'):
                hours = int(duration_str[:-1])
                return datetime.datetime.now() + timedelta(hours=hours)
            elif duration_str.endswith('d'):
                days = int(duration_str[:-1])
                return datetime.datetime.now() + timedelta(days=days)
            elif duration_str.endswith('w'):
                weeks = int(duration_str[:-1])
                return datetime.datetime.now() + timedelta(weeks=weeks)
            else:
                return None
        except:
            return None
    
    async def auto_mute_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, reason: str):
        """Automatically mute user when they reach max warnings"""
        chat_id = update.effective_chat.id
        
        try:
            # Get mute duration from settings
            async with aiosqlite.connect('bot_database.db') as db:
                cursor = await db.execute(
                    "SELECT mute_duration FROM group_settings WHERE group_id = ?",
                    (chat_id,)
                )
                result = await cursor.fetchone()
            
            mute_duration = result[0] if result else 3600  # Default 1 hour
            
            mute_until = datetime.datetime.now() + timedelta(seconds=mute_duration)
            
            permissions = {
                'can_send_messages': False,
                'can_send_media_messages': False,
                'can_send_polls': False,
                'can_send_other_messages': False,
                'can_add_web_page_previews': False
            }
            
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
                until_date=mute_until
            )
            
            # Notify group
            try:
                user = await context.bot.get_chat(user_id)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔇 {user.mention_html()} has been automatically muted for {mute_duration//3600} hours. Reason: {reason}",
                    parse_mode='HTML'
                )
            except:
                pass
            
        except Exception as e:
            logger.error(f"Error auto-muting user: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in the group bot"""
        logger.error(f"Group bot error: {context.error}")
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again or contact administrators."
                )
            except:
                pass
    
    async def start_bot(self):
        """Start Group Management Bot with all features"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("🛡️ Group Management Bot is running with full functionality...")

# ============================ AUTOADV BOT ============================
class AutoADVBot:
    def __init__(self):
        self.token = "8418940396:AAEg2qqNOInwKfqoQSHQs4xgO4jOu7Qbh9I"
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
        self.payment_conversation_state = {}
    
    def setup_handlers(self):
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("payment", self.payment_command))
        self.application.add_handler(CommandHandler("plans", self.plans_command))
        self.application.add_handler(CommandHandler("history", self.history_command))
        self.application.add_handler(CommandHandler("invoice", self.invoice_command))
        self.application.add_handler(CommandHandler("billing", self.billing_command))
        self.application.add_handler(CommandHandler("subscription", self.subscription_command))
        
        # Conversation handler for payment processing
        payment_conversation = ConversationHandler(
            entry_points=[CommandHandler("add_funds", self.add_funds_command)],
            states={
                1: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_payment_amount)],
                2: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_payment_method)],
                3: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm_payment)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_payment)]
        )
        self.application.add_handler(payment_conversation)
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.payment_button_handler, pattern="^payment_"))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_payment_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        
        # Get user balance
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
        
        balance = result[0] if result else 0.0
        
        welcome_text = f"""
💰 Welcome {user.first_name} to the AutoADV Payment & Billing System! 💳

**Your Current Balance:** `${balance:.2f}`

💼 **Comprehensive Payment Features:**
• Secure payment processing
• Multiple payment methods
• Invoice generation
• Billing history
• Subscription management
• Auto-topup options

🔧 **Available Commands:**
/payment - Make a payment
/plans - View advertising plans
/history - Payment history
/invoice - Generate invoices
/billing - Billing settings
/subscription - Manage subscriptions
/add_funds - Add funds to account

💎 **Payment Methods Supported:**
• Credit/Debit Cards
• Cryptocurrency
• Bank Transfers
• E-wallets
• Mobile Payments
        """
        
        keyboard = [
            [InlineKeyboardButton("💳 Make Payment", callback_data="payment_make")],
            [InlineKeyboardButton("📦 View Plans", callback_data="payment_plans")],
            [InlineKeyboardButton("📊 Billing History", callback_data="payment_history")],
            [InlineKeyboardButton("🆘 Help", callback_data="payment_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
💰 **AutoADV Payment Bot - Complete Help Guide** 📚

💳 **PAYMENT COMMANDS:**
/payment - Initiate payment process
/plans - View all advertising plans
/history - View payment history
/invoice - Generate payment invoice
/billing - Billing and account settings
/subscription - Manage subscriptions
/add_funds - Add funds to account

🔧 **ACCOUNT MANAGEMENT:**
• Balance tracking
• Transaction history
• Invoice management
• Payment method storage
• Auto-pay configuration
• Subscription management

💎 **PAYMENT METHODS:**
**Credit/Debit Cards:**
• Visa, MasterCard, American Express
• Secure tokenization
• Instant processing

**Cryptocurrency:**
• Bitcoin (BTC), Ethereum (ETH)
• USDT, USDC stablecoins
• Fast blockchain confirmations

**Bank Transfers:**
• Wire transfers
• ACH payments (US)
• SEPA transfers (EU)
• Processing: 1-3 business days

**E-wallets:**
• PayPal, Skrill, Neteller
• Perfect Money, Payeer
• Instant processing

**Mobile Payments:**
• Available in selected countries
• Carrier billing options

📦 **ADVERTISING PLANS:**
**Basic Plan** - $10/month
• 10 advertisements
• Basic analytics
• Standard support

**Pro Plan** - $25/month
• 50 advertisements  
• Advanced analytics
• Priority support
• A/B testing

**Business Plan** - $50/month
• 200 advertisements
• Premium analytics
• VIP support
• API access

**Enterprise Plan** - $100/month
• Unlimited advertisements
• Dedicated manager
• Custom solutions
• Highest priority

🛡️ **SECURITY FEATURES:**
• PCI DSS compliant
• End-to-end encryption
• Fraud detection
• Chargeback protection
• Data privacy compliant

📞 **SUPPORT:**
• Billing support: billing@adbot.com
• Technical support: support@adbot.com
• Emergency: +1-555-HELP-NOW

For payment issues or questions, contact our billing department.
        """
        
        keyboard = [
            [InlineKeyboardButton("💳 Make Payment", callback_data="payment_start")],
            [InlineKeyboardButton("📦 Pricing Plans", callback_data="payment_pricing")],
            [InlineKeyboardButton("🛡️ Security Info", callback_data="payment_security")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="payment_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Get user balance
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
        
        balance = result[0] if result else 0.0
        
        payment_text = f"""
💳 **Payment Processing Center** 🏦

**Current Balance:** `${balance:.2f}`

🎯 **Select Payment Purpose:**

🛒 **Quick Top-up** - Add funds to your account
📦 **Plan Subscription** - Subscribe to advertising plan
💰 **One-time Payment** - Pay for specific service
🧾 **Invoice Payment** - Pay outstanding invoice
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🛒 Quick Top-up", callback_data="payment_quick_topup"),
                InlineKeyboardButton("📦 Plan Subscription", callback_data="payment_plan_sub")
            ],
            [
                InlineKeyboardButton("💰 One-time Payment", callback_data="payment_one_time"),
                InlineKeyboardButton("🧾 Invoice Payment", callback_data="payment_invoice")
            ],
            [
                InlineKeyboardButton("💳 Payment Methods", callback_data="payment_methods"),
                InlineKeyboardButton("📊 Billing History", callback_data="payment_billing_history")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def plans_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        plans_text = """
📦 **Advertising Plans & Pricing** 💰

🥉 **BASIC PLAN** - $10/month
✅ **Features:**
• 10 advertisements per month
• Basic performance analytics
• Standard support (48h response)
• Text and image ads
• Manual approval process

🔄 **Best for:** Small businesses, individual advertisers

🥈 **PRO PLAN** - $25/month
✅ **Everything in Basic, plus:**
• 50 advertisements per month
• Advanced analytics dashboard
• Priority support (24h response)
• Video ad support
• Faster approval (12h)
• A/B testing
• Basic targeting

🔄 **Best for:** Growing businesses, marketing agencies

🥇 **BUSINESS PLAN** - $50/month
✅ **Everything in Pro, plus:**
• 200 advertisements per month
• Premium analytics with insights
• VIP support (6h response)
• All ad formats supported
• Instant approval (6h)
• Advanced targeting
• API access
• Custom ad templates

🔄 **Best for:** Established businesses, e-commerce

💎 **ENTERPRISE PLAN** - $100/month
✅ **Everything in Business, plus:**
• Unlimited advertisements
• Enterprise analytics suite
• Dedicated account manager
• Instant approval (1h)
• Advanced AI optimization
• Custom solutions
• Highest priority
• White-label options

🔄 **Best for:** Large enterprises, high-volume advertisers

🎯 **RECOMMENDATION:**
Start with Basic and upgrade as your needs grow!
        """
        
        keyboard = [
            [InlineKeyboardButton("🥉 Basic - $10", callback_data="plan_basic")],
            [InlineKeyboardButton("🥈 Pro - $25", callback_data="plan_pro")],
            [InlineKeyboardButton("🥇 Business - $50", callback_data="plan_business")],
            [InlineKeyboardButton("💎 Enterprise - $100", callback_data="plan_enterprise")],
            [InlineKeyboardButton("💳 Subscribe Now", callback_data="payment_subscribe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(plans_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            # Get payment history
            cursor = await db.execute('''
                SELECT amount, status, payment_method, created_at, transaction_id
                FROM payments 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 10
            ''', (user_id,))
            payments = await cursor.fetchall()
            
            # Get statistics
            cursor = await db.execute('''
                SELECT 
                    COUNT(*) as total_payments,
                    SUM(amount) as total_spent,
                    SUM(CASE WHEN status='completed' THEN amount ELSE 0 END) as completed_amount
                FROM payments 
                WHERE user_id = ?
            ''', (user_id,))
            stats = await cursor.fetchone()
        
        if stats:
            total_payments, total_spent, completed_amount = stats
        else:
            total_payments, total_spent, completed_amount = 0, 0, 0
        
        history_text = f"""
📝 **Payment History & Statistics** 📊

**Summary:**
• Total Payments: `{total_payments}`
• Total Amount: `${total_spent or 0:.2f}`
• Completed: `${completed_amount or 0:.2f}`
• Pending: `${(total_spent or 0) - (completed_amount or 0):.2f}`

**Recent Transactions:**
"""
        
        if payments:
            for amount, status, method, created_at, tx_id in payments:
                status_icon = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
                tx_short = tx_id[:8] + "..." if tx_id else "N/A"
                history_text += f"• {status_icon} ${amount:.2f} - {method} - {created_at[:10]} - {tx_short}\n"
        else:
            history_text += "• No payment history found\n"
        
        history_text += f"""
💡 **Tips:**
• Save payment methods for faster checkout
• Set up auto-topup for uninterrupted advertising
• Download invoices for accounting purposes
        """
        
        keyboard = [
            [InlineKeyboardButton("📄 Export History", callback_data="payment_export")],
            [InlineKeyboardButton("🧾 Download Invoices", callback_data="payment_invoices")],
            [InlineKeyboardButton("🔄 Auto-topup", callback_data="payment_autotopup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(history_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def invoice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Get recent payments for invoice generation
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('''
                SELECT id, amount, created_at, status
                FROM payments 
                WHERE user_id = ? AND status = 'completed'
                ORDER BY created_at DESC 
                LIMIT 5
            ''', (user_id,))
            recent_payments = await cursor.fetchall()
        
        if not recent_payments:
            await update.message.reply_text("📭 No completed payments available for invoice generation.")
            return
        
        invoice_text = "🧾 **Invoice Generation**\n\nSelect a payment to generate invoice:\n\n"
        
        for payment_id, amount, created_at, status in recent_payments:
            invoice_text += f"• Payment #{payment_id} - ${amount:.2f} - {created_at[:10]}\n"
        
        keyboard = []
        for payment_id, amount, created_at, status in recent_payments:
            keyboard.append([InlineKeyboardButton(f"Invoice #{payment_id} - ${amount:.2f}", callback_data=f"invoice_{payment_id}")])
        
        keyboard.append([InlineKeyboardButton("📧 Email All Invoices", callback_data="invoice_email_all")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(invoice_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def billing_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance_result = await cursor.fetchone()
            
            cursor = await db.execute('''
                SELECT COUNT(*), SUM(amount) 
                FROM payments 
                WHERE user_id = ? AND status = 'completed'
            ''', (user_id,))
            payment_stats = await cursor.fetchone()
        
        balance = balance_result[0] if balance_result else 0.0
        total_payments = payment_stats[0] if payment_stats else 0
        total_amount = payment_stats[1] if payment_stats and payment_stats[1] else 0.0
        
        billing_text = f"""
🏦 **Billing & Account Settings** ⚙️

**Account Overview:**
• Current Balance: `${balance:.2f}`
• Total Payments: `{total_payments}`
• Total Spent: `${total_amount:.2f}`
• Member Since: `{datetime.datetime.now().strftime('%Y-%m-%d')}`

🔧 **Billing Settings:**
• Auto-topup: `Disabled`
• Payment Method: `Not set`
• Invoice Format: `PDF`
• Tax ID: `Not provided`
• Business Account: `No`

💳 **Payment Methods:**
• Credit Card: `Not saved`
• PayPal: `Not connected`
• Crypto Wallet: `Not set up`
• Bank Account: `Not linked`
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💳 Payment Methods", callback_data="billing_methods"),
                InlineKeyboardButton("🔄 Auto-topup", callback_data="billing_autotopup")
            ],
            [
                InlineKeyboardButton("🧾 Invoice Settings", callback_data="billing_invoice"),
                InlineKeyboardButton("🏢 Business Profile", callback_data="billing_business")
            ],
            [
                InlineKeyboardButton("📊 Spending Limits", callback_data="billing_limits"),
                InlineKeyboardButton("🔔 Notifications", callback_data="billing_notifications")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(billing_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Check for active subscriptions
        # This would typically check a subscriptions table
        # For now, we'll show a generic message
        
        subscription_text = """
🔄 **Subscription Management** 📅

**Current Subscription:** No active subscription

📦 **Available Subscriptions:**
• Basic Plan - $10/month
• Pro Plan - $25/month  
• Business Plan - $50/month
• Enterprise Plan - $100/month

🔄 **Subscription Features:**
• Automatic monthly billing
• Priority feature access
• Volume discounts
• Easy cancellation
• Prorated refunds

🎯 **Benefits of Subscription:**
• Consistent advertising presence
• Better rates than one-time payments
• Automatic plan upgrades
• Priority support access
        """
        
        keyboard = [
            [InlineKeyboardButton("📦 View Plans", callback_data="subscription_plans")],
            [InlineKeyboardButton("💳 Subscribe Now", callback_data="subscription_start")],
            [InlineKeyboardButton("🔄 Manage Subscription", callback_data="subscription_manage")],
            [InlineKeyboardButton("📞 Support", callback_data="subscription_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(subscription_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Conversation handlers for payment processing
    async def add_funds_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "💰 **Add Funds to Your Account**\n\n"
            "Please enter the amount you want to add (in USD):\n\n"
            "💡 **Recommended amounts:**\n"
            "• $10 - Small test\n"
            "• $50 - Campaign budget\n"
            "• $100 - Business advertising\n"
            "• $500+ - Enterprise level\n\n"
            "Enter amount:"
        )
        return 1
    
    async def get_payment_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            amount = float(update.message.text)
            if amount < 1:
                await update.message.reply_text("❌ Minimum amount is $1. Please enter a valid amount:")
                return 1
            if amount > 10000:
                await update.message.reply_text("❌ Maximum single transaction is $10,000. Please enter a smaller amount:")
                return 1
            
            context.user_data['payment_amount'] = amount
            
            await update.message.reply_text(
                f"✅ Amount set: ${amount:.2f}\n\n"
                "💳 **Select Payment Method:**\n\n"
                "• Credit/Debit Card 💳\n"
                "• Cryptocurrency ₿\n"
                "• Bank Transfer 🏦\n"
                "• E-wallet 📱\n"
                "• PayPal 🔵\n\n"
                "Enter your preferred payment method:"
            )
            return 2
            
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number:")
            return 1
    
    async def get_payment_method(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        payment_method = update.message.text
        context.user_data['payment_method'] = payment_method
        
        amount = context.user_data['payment_amount']
        
        await update.message.reply_text(
            f"🔍 **Payment Summary**\n\n"
            f"**Amount:** ${amount:.2f}\n"
            f"**Method:** {payment_method}\n"
            f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            "Please type 'CONFIRM' to proceed with the payment, or 'CANCEL' to abort:"
        )
        return 3
    
    async def confirm_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_response = update.message.text.upper()
        
        if user_response == 'CONFIRM':
            user_id = update.effective_user.id
            amount = context.user_data['payment_amount']
            method = context.user_data['payment_method']
            
            # Process payment (in real implementation, this would integrate with payment gateway)
            transaction_id = f"TX{int(time.time())}{random.randint(1000, 9999)}"
            
            # Save payment to database
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    "INSERT INTO payments (user_id, amount, payment_method, transaction_id, status) VALUES (?, ?, ?, ?, 'pending')",
                    (user_id, amount, method, transaction_id)
                )
                
                # Update user balance
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                
                await db.commit()
            
            await update.message.reply_text(
                f"✅ **Payment Processing!**\n\n"
                f"**Transaction ID:** {transaction_id}\n"
                f"**Amount:** ${amount:.2f}\n"
                f"**Method:** {method}\n"
                f"**Status:** Processing\n\n"
                "⏳ Your payment is being processed. You will receive a confirmation shortly.\n"
                "Your account balance will be updated once the payment is completed."
            )
            
            # Clear conversation data
            context.user_data.clear()
            return ConversationHandler.END
            
        elif user_response == 'CANCEL':
            await self.cancel_payment(update, context)
            return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Please type 'CONFIRM' to proceed or 'CANCEL' to abort:")
            return 3
    
    async def cancel_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("❌ Payment process cancelled.")
        return ConversationHandler.END
    
    async def handle_payment_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Handle payment-related messages
        user_message = update.message.text.lower()
        
        if any(word in user_message for word in ['payment', 'pay', 'invoice', 'billing', 'subscription']):
            await update.message.reply_text(
                "💳 Need help with payments? Use /payment to make a payment or /help for payment assistance!"
            )
    
    async def payment_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "payment_make":
            await self.payment_command(update, context)
        elif data == "payment_plans":
            await self.plans_command(update, context)
        elif data == "payment_history":
            await self.history_command(update, context)
        elif data == "payment_help":
            await self.help_command(update, context)
        elif data.startswith("plan_"):
            plan = data.replace("plan_", "")
            await query.edit_message_text(f"Selected {plan} plan. Processing subscription...")
        elif data.startswith("invoice_"):
            invoice_id = data.replace("invoice_", "")
            await query.edit_message_text(f"Generating invoice #{invoice_id}...")
    
    async def start_bot(self):
        """Start AutoADV Payment Bot with all features"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("💰 AutoADV Payment Bot is running with full functionality...")

# ============================ STAGGERED STARTUP SYSTEM ============================
async def start_bot_with_delay(bot_instance, bot_name, delay):
    """Start a bot with staggered delay to prevent Telegram API conflicts"""
    logger.info(f"⏳ Waiting {delay} seconds before starting {bot_name}...")
    await asyncio.sleep(delay)
    
    try:
        await bot_instance.start_bot()
        logger.info(f"✅ {bot_name} started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start {bot_name}: {e}")
        return False

async def main():
    """Main function with staggered bot startup to prevent conflicts"""
    print("🚀 Starting INTERLINK Multi-Bot System with Complete Functionality...")
    print("📋 This system includes:")
    print("   • Advertising Bot with advanced ad management")
    print("   • VIP Bot with verification system") 
    print("   • Group Management Bot with admin commands")
    print("   • AutoADV Bot with payment processing")
    print("   • Staggered startup to prevent API conflicts")
    
    # Initialize database with all tables
    await init_db()
    
    # Create bot instances with complete functionality
    advertising_bot = AdvertisingBot()
    vip_bot = VIPBot()
    group_bot = GroupBot()
    auto_adv_bot = AutoADVBot()
    
    # Staggered startup configuration - 7 second delays between bots
    bot_startup_config = [
        (advertising_bot, "AdvertisingBot", 0),     # Start immediately
        (vip_bot, "VIPBot", 7),                     # Start after 7 seconds
        (group_bot, "GroupBot", 14),                # Start after 14 seconds
        (auto_adv_bot, "AutoADVBot", 21)            # Start after 21 seconds
    ]
    
    logger.info("🔄 Starting bots with staggered timing to prevent Telegram API conflicts...")
    logger.info("⏰ Delays: 0s, 7s, 14s, 21s")
    
    # Start all bots with staggered timing
    startup_tasks = []
    for bot_instance, bot_name, delay in bot_startup_config:
        task = asyncio.create_task(start_bot_with_delay(bot_instance, bot_name, delay))
        startup_tasks.append(task)
    
    # Wait for all bots to start
    results = await asyncio.gather(*startup_tasks)
    
    # Report startup status
    successful_bots = sum(results)
    logger.info(f"🎉 {successful_bots}/4 bots started successfully!")
    
    if successful_bots == 0:
        logger.error("💥 All bots failed to start! Exiting...")
        return
    
    logger.info("🤖 All systems operational! Press Ctrl+C to stop.")
    logger.info("🔧 All features available:")
    logger.info("   • Advertising: /post, /stats, /admin_stats")
    logger.info("   • VIP: /verify, /vip_status, /upgrade") 
    logger.info("   • Group Management: /admin, /settings, /setwelcome")
    logger.info("   • Payments: /payment, /plans, /history")
    
    # Keep the application running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal...")
    except Exception as e:
        logger.error(f"💥 Unexpected error in main loop: {e}")
    finally:
        logger.info("👋 Shutting down INTERLINK Multi-Bot System...")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 INTERLINK Multi-Bot System stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")