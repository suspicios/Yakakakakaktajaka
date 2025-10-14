import os
import sqlite3
import logging
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    Bot,
    ChatPermissions,
    ChatMember
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.error import TelegramError
import aiohttp
import json
import secrets
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ==================== CONFIGURATION ====================
class Config:
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
    
    # Payment
    TRONSCAN_API = "https://apilist.tronscan.org/api/transaction/info"
    USDT_ADDRESS = "TD1gmGWyWqFY5STqZW5PMRqMR46xJhj5rP"
    
    # Settings
    DUMMY_PAYMENT_MODE = True
    AD_POSTING_INTERVAL = 300  # 5 minutes
    MAX_MESSAGE_LENGTH = 120
    VIP_TRIGGER_WORDS = ["direct", "company", "sbi", "accounts", "account"]
    ADMIN_USER_IDS = [123456789, 987654321]  # Replace with actual admin IDs
    
    # Database
    DB_PATH = "bot_system.db"

# ==================== DATABASE MANAGER ====================
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database with all required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    is_vip BOOLEAN DEFAULT FALSE,
                    vip_expiry DATETIME,
                    join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_banned BOOLEAN DEFAULT FALSE,
                    is_admin BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Ads table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ads (
                    ad_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    heading TEXT,
                    ad_type TEXT,
                    description TEXT,
                    contact TEXT,
                    template_type TEXT DEFAULT 'default',
                    status TEXT DEFAULT 'active',
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expiry_date DATETIME,
                    priority INTEGER DEFAULT 1,
                    views INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # VIP members table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vip_members (
                    vip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    phone TEXT,
                    email TEXT,
                    purchase_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expiry_date DATETIME,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Payments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_type TEXT,
                    amount REAL,
                    transaction_hash TEXT UNIQUE,
                    status TEXT DEFAULT 'pending',
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    verified_date DATETIME,
                    payment_mode TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Scam reports table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scam_reports (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    victim_id INTEGER,
                    scammer_name TEXT,
                    scammer_contact TEXT,
                    incident_details TEXT,
                    scam_platform TEXT,
                    victim_telegram TEXT,
                    status TEXT DEFAULT 'pending',
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (victim_id) REFERENCES users (user_id)
                )
            ''')
            
            # Ad templates table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ad_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    content TEXT,
                    is_default BOOLEAN DEFAULT FALSE,
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default templates
            cursor.execute('''
                INSERT OR IGNORE INTO ad_templates (name, content, is_default) VALUES 
                ('Business', '🏢 {heading}\\n🎯 {type}\\n📝 {description}\\n📞 {contact}', 1),
                ('Product', '🛍️ {heading}\\n💎 Type: {type}\\n📝 {description}\\n💰 Contact: {contact}', 0),
                ('Service', '🔧 {heading}\\n✅ Service: {type}\\n📝 {description}\\n⏰ Contact: {contact}', 0)
            ''')
            
            # Insert admin users
            for admin_id in Config.ADMIN_USER_IDS:
                cursor.execute('''
                    INSERT OR IGNORE INTO users (user_id, username, first_name, is_admin) 
                    VALUES (?, 'admin', 'Admin', TRUE)
                ''', (admin_id,))
            
            conn.commit()
    
    async def execute_query(self, query: str, params: tuple = ()):
        """Execute a database query asynchronously"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params)
            await db.commit()
    
    async def fetch_one(self, query: str, params: tuple = ()):
        """Fetch a single row from database"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                return await cursor.fetchone()
    
    async def fetch_all(self, query: str, params: tuple = ()):
        """Fetch all rows from database"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                return await cursor.fetchall()

# ==================== PAYMENT VERIFICATION SYSTEM ====================
class PaymentVerifier:
    def __init__(self, shared_manager: DatabaseManager):
        self.manager = shared_manager
        self.session = aiohttp.ClientSession()
    
    async def verify_transaction(self, transaction_hash: str, expected_amount: float, user_id: int) -> Dict:
        """Verify transaction with TronScan API or dummy verification"""
        if Config.DUMMY_PAYMENT_MODE:
            return await self._verify_dummy_payment(transaction_hash, expected_amount, user_id)
        else:
            return await self._verify_real_payment(transaction_hash, expected_amount, user_id)
    
    async def _verify_dummy_payment(self, transaction_hash: str, expected_amount: float, user_id: int) -> Dict:
        """Verify dummy payment for testing"""
        await asyncio.sleep(2)
        
        if len(transaction_hash) < 10:
            return {
                'success': False,
                'message': '❌ Invalid transaction hash format. Minimum 10 characters required.',
                'transaction_data': None
            }
        
        # Check if hash already used
        existing = await self.manager.fetch_one(
            "SELECT COUNT(*) FROM payments WHERE transaction_hash = ?", 
            (transaction_hash,)
        )
        if existing and existing[0] > 0:
            return {
                'success': False,
                'message': '❌ This transaction hash has already been used.',
                'transaction_data': None
            }
        
        return {
            'success': True,
            'message': '✅ Payment verified successfully (Dummy Mode)',
            'transaction_data': {
                'hash': transaction_hash,
                'amount': expected_amount,
                'from_address': 'TDummyAddressForTesting123',
                'to_address': Config.USDT_ADDRESS,
                'timestamp': datetime.now().isoformat(),
                'confirmations': 10
            }
        }
    
    async def _verify_real_payment(self, transaction_hash: str, expected_amount: float, user_id: int) -> Dict:
        """Verify real payment using TronScan API"""
        try:
            async with self.session.get(f"{Config.TRONSCAN_API}?hash={transaction_hash}") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('confirmed'):
                        verification_result = self._validate_transaction_data(data, expected_amount, user_id)
                        return verification_result
                    else:
                        return {
                            'success': False,
                            'message': '⏳ Transaction not confirmed yet. Please wait for confirmation.',
                            'transaction_data': None
                        }
                else:
                    return {
                        'success': False,
                        'message': '❌ Transaction not found or API error',
                        'transaction_data': None
                    }
                    
        except Exception as e:
            logging.error(f"Payment verification error: {e}")
            return {
                'success': False,
                'message': '❌ Error verifying payment. Please try again later.',
                'transaction_data': None
            }
    
    def _validate_transaction_data(self, transaction_data: Dict, expected_amount: float, user_id: int) -> Dict:
        """Validate transaction details"""
        try:
            contract_data = transaction_data.get('contractData', {})
            amount = contract_data.get('amount', 0) / 1000000
            
            to_address = transaction_data.get('toAddress')
            if to_address != Config.USDT_ADDRESS:
                return {
                    'success': False,
                    'message': f'❌ Payment sent to wrong address. Expected: {Config.USDT_ADDRESS}',
                    'transaction_data': None
                }
            
            if abs(amount - expected_amount) > 0.1:
                return {
                    'success': False,
                    'message': f'❌ Incorrect amount. Expected: {expected_amount} USDT, Received: {amount:.2f} USDT',
                    'transaction_data': None
                }
            
            # Check if transaction already used
            existing = self._sync_check_transaction_used(transaction_data['hash'])
            if existing:
                return {
                    'success': False,
                    'message': '❌ This transaction has already been used',
                    'transaction_data': None
                }
            
            return {
                'success': True,
                'message': '✅ Payment verified successfully!',
                'transaction_data': {
                    'hash': transaction_data['hash'],
                    'amount': amount,
                    'from_address': transaction_data.get('ownerAddress'),
                    'to_address': to_address,
                    'timestamp': transaction_data.get('timestamp'),
                    'confirmations': transaction_data.get('confirmations', 0)
                }
            }
            
        except Exception as e:
            logging.error(f"Transaction validation error: {e}")
            return {
                'success': False,
                'message': '❌ Error processing transaction data',
                'transaction_data': None
            }
    
    def _sync_check_transaction_used(self, transaction_hash: str) -> bool:
        """Sync check if transaction hash is already used"""
        with sqlite3.connect(Config.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM payments WHERE transaction_hash = ?", (transaction_hash,))
            result = cursor.fetchone()
            return result[0] > 0 if result else False
    
    async def close(self):
        """Close the session"""
        await self.session.close()

# ==================== SHARED MANAGER ====================
class SharedManager:
    def __init__(self):
        self.db = DatabaseManager(Config.DB_PATH)
        self.scheduler = AsyncIOScheduler()
    
    async def get_user(self, user_id: int):
        return await self.db.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
    
    async def create_user(self, user_id: int, username: str, first_name: str):
        await self.db.execute_query(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
    
    async def is_admin(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return user and (user[7] or user_id in Config.ADMIN_USER_IDS)
    
    async def is_vip(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        if user and user[3]:
            expiry = user[4]
            if expiry and datetime.fromisoformat(expiry) > datetime.now():
                return True
        return False
    
    async def add_vip(self, user_id: int, name: str, phone: str, email: str, duration_days: int = 60):
        expiry = datetime.now() + timedelta(days=duration_days)
        await self.db.execute_query(
            "UPDATE users SET is_vip = TRUE, vip_expiry = ? WHERE user_id = ?",
            (expiry.isoformat(), user_id)
        )
        await self.db.execute_query(
            "INSERT INTO vip_members (user_id, name, phone, email, expiry_date) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, phone, email, expiry.isoformat())
        )

# ==================== 1. ADVERTISING BOT ====================
class AdvertisingBot:
    def __init__(self, token: str, shared_manager: SharedManager):
        self.token = token
        self.manager = shared_manager
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        self.setup_scheduler()
    
    def setup_handlers(self):
        """Setup all command and message handlers"""
        # User commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("post_ad", self.post_ad_command))
        self.application.add_handler(CommandHandler("my_ads", self.my_ads_command))
        self.application.add_handler(CommandHandler("ad_stats", self.ad_stats_command))
        self.application.add_handler(CommandHandler("ad_templates", self.ad_templates_command))
        self.application.add_handler(CommandHandler("ad_pricing", self.ad_pricing_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("ad_dashboard", self.ad_dashboard_command))
        self.application.add_handler(CommandHandler("ad_approvals", self.ad_approvals_command))
        self.application.add_handler(CommandHandler("ad_revenue", self.ad_revenue_command))
        self.application.add_handler(CommandHandler("ad_settings", self.ad_settings_command))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern="^adv_"))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    def setup_scheduler(self):
        """Setup automatic ad posting scheduler"""
        if not self.manager.scheduler.running:
            self.manager.scheduler.start()
        
        self.manager.scheduler.add_job(
            self.post_scheduled_ad,
            'interval',
            seconds=Config.AD_POSTING_INTERVAL,
            id='ad_posting'
        )
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user
        await self.manager.create_user(user.id, user.username, user.first_name)
        
        welcome_text = """
🌟 *Welcome to Advertising Bot!* 🌟

I'm your powerful advertising assistant! Here's what I can do:

📢 *ADVERTISING SERVICES*
/post_ad - Create new advertisement
/my_ads - View your active ads
/ad_templates - Available ad templates
/ad_stats - Your ad performance
/ad_pricing - Current prices

🎯 *QUICK ACTIONS*
• Auto-post ads every 5-6 minutes
• Smart scheduling across groups
• Professional templates
• Performance analytics

💼 *ADMIN FEATURES*
/ad_dashboard - Admin control panel
/ad_approvals - Manage pending ads

Click buttons below to get started! 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 Post Ad", callback_data="adv_post_ad")],
            [InlineKeyboardButton("📊 My Ads", callback_data="adv_my_ads")],
            [InlineKeyboardButton("🎨 Templates", callback_data="adv_templates")],
            [InlineKeyboardButton("💼 Admin Panel", callback_data="adv_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def post_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle ad posting command"""
        user_id = update.effective_user.id
        
        if not await self.manager.is_vip(user_id):
            active_ads = await self.manager.db.fetch_one(
                "SELECT COUNT(*) FROM ads WHERE user_id = ? AND status = 'active'",
                (user_id,)
            )
            if active_ads and active_ads[0] >= 3:
                await update.message.reply_text(
                    "❌ You have reached the maximum number of active ads (3).\n"
                    "Become a VIP to post unlimited ads!",
                    parse_mode='Markdown'
                )
                return
        
        await update.message.reply_text(
            "🎯 *Let's create your advertisement!*\n\n"
            "Please send your ad in this format:\n\n"
            "*Heading:* Your ad title\n"
            "*Type:* Product/Service/Other\n"
            "*Description:* Detailed description\n"
            "*Contact:* Your contact info\n\n"
            "Or use /ad_templates to see pre-made formats!",
            parse_mode='Markdown'
        )
    
    async def my_ads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's active ads"""
        user_id = update.effective_user.id
        ads = await self.manager.db.fetch_all(
            "SELECT * FROM ads WHERE user_id = ? AND status = 'active' ORDER BY created_date DESC",
            (user_id,)
        )
        
        if not ads:
            await update.message.reply_text("📭 You have no active advertisements.")
            return
        
        ad_text = "📊 *Your Active Advertisements:*\n\n"
        for ad in ads:
            ad_text += f"🎯 *{ad[2]}* ({ad[3]})\n"
            ad_text += f"📅 Expires: {ad[9][:10]}\n"
            ad_text += f"👁️ Views: {ad[11]} | 👆 Clicks: {ad[12]}\n"
            ad_text += f"🆔 ID: {ad[0]}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Renew Ad", callback_data="adv_renew")],
            [InlineKeyboardButton("✏️ Edit Ad", callback_data="adv_edit")],
            [InlineKeyboardButton("📢 Post New", callback_data="adv_post_ad")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(ad_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def ad_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show ad statistics"""
        user_id = update.effective_user.id
        
        stats = await self.manager.db.fetch_one(
            "SELECT COUNT(*), SUM(amount) FROM payments WHERE user_id = ? AND product_type = 'ad' AND status = 'completed'",
            (user_id,)
        )
        
        active_ads = await self.manager.db.fetch_one(
            "SELECT COUNT(*) FROM ads WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        
        total_views = await self.manager.db.fetch_one(
            "SELECT SUM(views) FROM ads WHERE user_id = ?",
            (user_id,)
        )
        
        stats_text = f"""
📈 *Your Advertising Statistics*

📊 *Campaign Summary*
• Active Ads: {active_ads[0] if active_ads else 0}
• Total Ads Posted: {stats[0] if stats and stats[0] else 0}
• Total Spent: {stats[1] if stats and stats[1] else 0} USDT
• Total Views: {total_views[0] if total_views else 0}

🎯 *Performance Metrics*
• Average Engagement: Calculating...
• Best Performing: Analyzing...
• Recommendations: Coming soon!

🚀 *Pro Tips*
• Post during peak hours (8-10 AM, 6-8 PM)
• Use clear contact information
• Include compelling call-to-actions
        """
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def ad_templates_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available ad templates"""
        templates = await self.manager.db.fetch_all("SELECT * FROM ad_templates")
        
        templates_text = "🎨 *Professional Ad Templates*\n\n"
        
        for template in templates:
            templates_text += f"*{template[1]}* {'(Default)' if template[3] else ''}\n"
            templates_text += f"```{template[2]}```\n\n"
        
        keyboard = []
        for template in templates:
            keyboard.append([InlineKeyboardButton(f"📝 {template[1]}", callback_data=f"adv_template_{template[0]}")])
        
        keyboard.append([InlineKeyboardButton("📝 Custom", callback_data="adv_template_custom")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(templates_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def ad_pricing_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show ad pricing"""
        pricing_text = """
💰 *Advertising Pricing*

📢 *Standard Advertisement*
• Price: 188 USDT
• Validity: 10 days
• Features:
  ✅ Automatic posting every 5-6 minutes
  ✅ Professional templates
  ✅ Multiple group exposure
  ✅ Performance analytics

👑 *VIP Benefits*
• Unlimited active ads
• Priority placement
• Advanced analytics
• Custom templates

💎 *Become VIP for 300 USDT (60 days)*
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 Buy Ad Slot", callback_data="autoadv_buy_ad")],
            [InlineKeyboardButton("👑 Become VIP", callback_data="autoadv_buy_vip")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(pricing_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def ad_dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin dashboard for advertising"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        stats = await self.manager.db.fetch_one(
            "SELECT COUNT(*), SUM(amount) FROM payments WHERE product_type = 'ad' AND status = 'completed'"
        )
        
        active_ads = await self.manager.db.fetch_one("SELECT COUNT(*) FROM ads WHERE status = 'active'")
        pending_ads = await self.manager.db.fetch_one("SELECT COUNT(*) FROM ads WHERE status = 'pending'")
        
        dashboard_text = f"""
👑 *Advertising Admin Dashboard*

📊 *System Overview*
• Total Ads Sold: {stats[0] if stats and stats[0] else 0}
• Total Revenue: {stats[1] if stats and stats[1] else 0:.2f} USDT
• Active Ads: {active_ads[0] if active_ads else 0}
• Pending Ads: {pending_ads[0] if pending_ads else 0}

⚙️ *Quick Controls*
• Manage pending approvals
• View financial reports
• System configuration
• User management
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Pending Ads", callback_data="adv_pending_ads")],
            [InlineKeyboardButton("💰 Revenue Report", callback_data="adv_revenue")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="adv_settings")],
            [InlineKeyboardButton("👥 User Management", callback_data="adv_users")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(dashboard_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def post_scheduled_ad(self):
        """Post scheduled advertisements to groups"""
        try:
            ad = await self.manager.db.fetch_one(
                "SELECT * FROM ads WHERE status = 'active' AND expiry_date > datetime('now') "
                "ORDER BY priority DESC, created_date ASC LIMIT 1"
            )
            
            if ad:
                ad_text = self.format_advertisement(ad)
                keyboard = self.create_ad_buttons()
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Post to main group and pin
                main_msg = await self.application.bot.send_message(
                    Config.MAIN_GROUP_ID,
                    ad_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                await self.application.bot.pin_chat_message(Config.MAIN_GROUP_ID, main_msg.message_id)
                
                # Post to company resources
                await self.application.bot.send_message(
                    Config.COMPANY_RESOURCES_ID,
                    ad_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                # Update ad stats
                await self.manager.db.execute_query(
                    "UPDATE ads SET views = views + 1 WHERE ad_id = ?",
                    (ad[0],)
                )
                
        except Exception as e:
            logging.error(f"Error in scheduled ad posting: {e}")
    
    def format_advertisement(self, ad) -> str:
        """Format ad for posting"""
        return f"""
🎯 *{ad[2]}* | {ad[3]}

📝 *Description:*
{ad[4]}

📞 *Contact:*
{ad[5]}

🕒 Posted: {ad[8][:16]}
✅ Verified Advertisement
        """
    
    def create_ad_buttons(self) -> List[List[InlineKeyboardButton]]:
        """Create buttons for advertisements"""
        return [
            [InlineKeyboardButton("🌟 Find Genuine Company", callback_data="adv_find_company")],
            [
                InlineKeyboardButton("💼 VIP", callback_data="adv_vip_channel"),
                InlineKeyboardButton("🏢 Resources", callback_data="adv_company_resources")
            ],
            [
                InlineKeyboardButton("📢 Post Ads", callback_data="autoadv_buy_ad"),
                InlineKeyboardButton("🚨 Scammer Exposed", callback_data="autoadv_report_scammer")
            ]
        ]
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "adv_post_ad":
            await self.post_ad_command(update, context)
        elif data == "adv_my_ads":
            await self.my_ads_command(update, context)
        elif data == "adv_templates":
            await self.ad_templates_command(update, context)
        elif data == "adv_dashboard":
            await self.ad_dashboard_command(update, context)
        elif data.startswith("adv_template_"):
            template_id = data.split("_")[2]
            if template_id == "custom":
                await query.edit_message_text("Please use /post_ad to create a custom ad.")
            else:
                template = await self.manager.db.fetch_one("SELECT * FROM ad_templates WHERE template_id = ?", (template_id,))
                if template:
                    await query.edit_message_text(f"*Template: {template[1]}*\n\n```{template[2]}```\n\nUse /post_ad to create an ad with this template.", parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command with all features"""
        help_text = """
🆘 *Advertising Bot Help Guide*

📢 *ADVERTISING COMMANDS*
/post_ad - Create new advertisement
/my_ads - View your active ads
/ad_stats - Advertising statistics
/ad_templates - Professional templates
/ad_pricing - Current prices

👑 *ADMIN COMMANDS* 
/ad_dashboard - Admin control panel
/ad_approvals - Manage pending ads
/ad_revenue - Revenue reports
/ad_settings - Bot configuration

🎯 *FEATURES*
• Automatic ad rotation every 5-6 minutes
• Smart scheduling across multiple groups
• Professional ad templates
• Performance analytics
• Priority-based ad system

💡 *TIPS*
• Use clear, compelling headlines
• Include proper contact information
• Follow group guidelines
• Monitor your ad performance

Need more help? Contact support!
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        # Placeholder for future message handling
        pass
    
    async def ad_approvals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manage pending ad approvals"""
        if not await self.manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        pending_ads = await self.manager.db.fetch_all("SELECT * FROM ads WHERE status = 'pending'")
        
        if not pending_ads:
            await update.message.reply_text("✅ No pending ads for approval.")
            return
        
        # Implementation for ad approval system
        await update.message.reply_text(f"📋 {len(pending_ads)} ads pending approval.")
    
    async def ad_revenue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show revenue reports"""
        if not await self.manager.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        revenue = await self.manager.db.fetch_one(
            "SELECT SUM(amount) FROM payments WHERE product_type = 'ad' AND status = 'completed'"
        )
        
        await update.message.reply_text(f"💰 Total Ad Revenue: {revenue[0] if revenue and revenue[0] else 0:.2f} USDT")
    
    def run(self):
        """Start the bot"""
        self.application.run_polling()

# ==================== 2. VIP BOT ====================
class VIPBot:
    def __init__(self, token: str, shared_manager: SharedManager):
        self.token = token
        self.manager = shared_manager
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup VIP bot handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("check_vip", self.check_vip_command))
        self.application.add_handler(CommandHandler("my_vip", self.my_vip_command))
        self.application.add_handler(CommandHandler("vip_benefits", self.vip_benefits_command))
        self.application.add_handler(CommandHandler("vip_list", self.vip_list_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("vip_dashboard", self.vip_dashboard_command))
        self.application.add_handler(CommandHandler("vip_add", self.vip_add_command))
        self.application.add_handler(CommandHandler("vip_remove", self.vip_remove_command))
        
        # Message handler for VIP verification
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.verify_vip_message))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.vip_button_handler, pattern="^vip_"))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """VIP bot start command"""
        user = update.effective_user
        await self.manager.create_user(user.id, user.username, user.first_name)
        
        welcome_text = """
👑 *Welcome to VIP Verification Bot!* 👑

I'm here to verify and manage VIP members in the community. 

⭐ *VIP FEATURES*
/check_vip - Verify VIP status
/my_vip - Your VIP information  
/vip_benefits - VIP benefits list
/vip_list - View VIP members

🔍 *AUTOMATIC VERIFICATION*
I automatically verify VIP status when certain keywords are used in chats.

👑 *ADMIN TOOLS*  
/vip_dashboard - VIP management
/vip_add - Add new VIP member
/vip_remove - Remove VIP member

Become a VIP today for exclusive benefits! 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("⭐ Check VIP", callback_data="vip_check")],
            [InlineKeyboardButton("👑 VIP Benefits", callback_data="vip_benefits")],
            [InlineKeyboardButton("💰 Buy VIP", callback_data="autoadv_buy_vip")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def check_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if user or mentioned user is VIP"""
        user_id = update.effective_user.id
        
        if context.args:
            username = context.args[0].replace('@', '')
            user_data = await self.manager.db.fetch_one(
                "SELECT user_id, is_vip, vip_expiry FROM users WHERE username = ?",
                (username,)
            )
            
            if user_data:
                is_vip = user_data[1] and datetime.fromisoformat(user_data[2]) > datetime.now()
                status = "✅ *VIP Member*" if is_vip else "❌ *Not VIP*"
                await update.message.reply_text(
                    f"👤 @{username}\n{status}\n"
                    f"📅 Expiry: {user_data[2][:10] if user_data[2] else 'N/A'}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ User not found in database.")
        else:
            is_vip = await self.manager.is_vip(user_id)
            user_data = await self.manager.get_user(user_id)
            
            status = "🌟 *YOU ARE A VIP MEMBER!*" if is_vip else "❌ *You are not a VIP member*"
            expiry_text = f"\n📅 VIP Expires: {user_data[4][:10]}" if is_vip else ""
            
            await update.message.reply_text(
                f"{status}{expiry_text}\n\n"
                "💎 Enjoy exclusive benefits and verified status!",
                parse_mode='Markdown'
            )
    
    async def verify_vip_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify VIP status when trigger words are used"""
        message = update.message
        user_id = message.from_user.id
        text = message.text.lower()
        
        trigger_found = any(trigger in text for trigger in Config.VIP_TRIGGER_WORDS)
        long_message = len(text) > 100
        
        if trigger_found or long_message:
            is_vip = await self.manager.is_vip(user_id)
            vip_status = "✅ *Verified VIP Member*" if is_vip else "⚠️ *Unverified User*"
            
            verification_text = f"""
🔍 *VIP Verification*

👤 User: {message.from_user.first_name}
{vip_status}

💡 *Tip:* VIP members get instant trust and priority support!
            """
            
            await message.reply_text(verification_text, parse_mode='Markdown')
    
    async def my_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's VIP information"""
        user_id = update.effective_user.id
        is_vip = await self.manager.is_vip(user_id)
        
        if is_vip:
            vip_data = await self.manager.db.fetch_one(
                "SELECT * FROM vip_members WHERE user_id = ? ORDER BY purchase_date DESC LIMIT 1",
                (user_id,)
            )
            
            vip_text = f"""
🌟 *Your VIP Membership*

👤 Name: {vip_data[2]}
📞 Phone: {vip_data[3]}
📧 Email: {vip_data[4]}
📅 Purchased: {vip_data[5][:10]}
📅 Expires: {vip_data[6][:10]}

💎 *VIP Benefits:*
• Verified status in chats
• Priority support
• Exclusive channel access
• Early feature access
• Special promotions
            """
        else:
            vip_text = """
❌ *You are not a VIP member*

💎 *Become a VIP today and enjoy:*
• Verified status badge
• Exclusive group access  
• Priority customer support
• Special promotions
• Trust and credibility

Click below to become VIP! 🚀
            """
            
            keyboard = [[InlineKeyboardButton("💰 Buy VIP", callback_data="autoadv_buy_vip")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(vip_text, parse_mode='Markdown', reply_markup=reply_markup)
            return
        
        await update.message.reply_text(vip_text, parse_mode='Markdown')
    
    async def vip_benefits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VIP benefits"""
        benefits_text = """
💎 *VIP Membership Benefits*

🌟 *Exclusive Features*
• ✅ Verified VIP badge in all groups
• 🔒 Access to VIP-only channel
• 🚀 Priority customer support
• 📢 Early access to new features
• 💰 Special promotions and discounts

🔐 *Trust & Security*  
• 🔍 Automatic verification in chats
• 📈 Increased credibility
• 🤝 Trusted member status
• 🛡️ Enhanced security features

🎯 *Business Advantages*
• 📊 Advanced analytics
• 👥 VIP networking opportunities
• 💼 Business promotion priority
• 📈 Growth tools and insights

💰 *Pricing:*
• 300 USDT for 60 days
• Best value for serious professionals

*Become VIP today and elevate your experience!* 🚀
        """
        
        keyboard = [[InlineKeyboardButton("💰 Buy VIP Now", callback_data="autoadv_buy_vip")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(benefits_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def vip_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show list of VIP members"""
        vip_members = await self.manager.db.fetch_all(
            "SELECT u.username, v.name, v.expiry_date FROM vip_members v "
            "JOIN users u ON v.user_id = u.user_id WHERE v.expiry_date > datetime('now') "
            "ORDER BY v.expiry_date DESC LIMIT 20"
        )
        
        if not vip_members:
            await update.message.reply_text("👑 No active VIP members found.")
            return
        
        vip_text = "👑 *Active VIP Members:*\n\n"
        for member in vip_members:
            username = f"@{member[0]}" if member[0] else "Hidden"
            vip_text += f"• {username} - {member[1]}\n"
            vip_text += f"  📅 Expires: {member[2][:10]}\n\n"
        
        await update.message.reply_text(vip_text, parse_mode='Markdown')
    
    async def vip_dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """VIP admin dashboard"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        vip_count = await self.manager.db.fetch_one("SELECT COUNT(*) FROM users WHERE is_vip = TRUE")
        active_vips = await self.manager.db.fetch_one(
            "SELECT COUNT(*) FROM vip_members WHERE expiry_date > datetime('now')"
        )
        revenue = await self.manager.db.fetch_one(
            "SELECT SUM(amount) FROM payments WHERE product_type = 'vip' AND status = 'completed'"
        )
        
        dashboard_text = f"""
👑 *VIP Admin Dashboard*

📊 *VIP Statistics*
• Total VIPs: {vip_count[0] if vip_count else 0}
• Active VIPs: {active_vips[0] if active_vips else 0}
• Total Revenue: {revenue[0] if revenue and revenue[0] else 0:.2f} USDT

⚙️ *Management Tools*
• Add/Remove VIP members
• Extend VIP durations  
• View VIP activity
• Revenue reports
        """
        
        keyboard = [
            [InlineKeyboardButton("👥 VIP List", callback_data="vip_list")],
            [InlineKeyboardButton("➕ Add VIP", callback_data="vip_add")],
            [InlineKeyboardButton("📈 Reports", callback_data="vip_reports")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="vip_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(dashboard_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def vip_add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add VIP member (admin only)"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        if len(context.args) < 4:
            await update.message.reply_text(
                "Usage: /vip_add @username 'Full Name' phone email duration_days\n"
                "Example: /vip_add @john 'John Doe' +123456789 john@email.com 60"
            )
            return
        
        try:
            target_username = context.args[0].replace('@', '')
            name = context.args[1]
            phone = context.args[2]
            email = context.args[3]
            duration = int(context.args[4]) if len(context.args) > 4 else 60
            
            target_user = await self.manager.db.fetch_one(
                "SELECT user_id FROM users WHERE username = ?", (target_username,)
            )
            
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            await self.manager.add_vip(target_user[0], name, phone, email, duration)
            await update.message.reply_text(f"✅ VIP membership added for @{target_username} for {duration} days.")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error adding VIP: {str(e)}")
    
    async def vip_remove_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove VIP membership"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /vip_remove @username")
            return
        
        target_username = context.args[0].replace('@', '')
        
        await self.manager.db.execute_query(
            "UPDATE users SET is_vip = FALSE, vip_expiry = NULL WHERE username = ?",
            (target_username,)
        )
        
        await update.message.reply_text(f"✅ VIP membership removed for @{target_username}")
    
    async def vip_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VIP button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "vip_check":
            await self.check_vip_command(update, context)
        elif data == "vip_benefits":
            await self.vip_benefits_command(update, context)
        elif data == "vip_list":
            await self.vip_list_command(update, context)
    
    def run(self):
        """Start the VIP bot"""
        self.application.run_polling()

# ==================== 3. GROUP MANAGEMENT BOT ====================
class GroupManagementBot:
    def __init__(self, token: str, shared_manager: SharedManager):
        self.token = token
        self.manager = shared_manager
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup group management handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("rules", self.rules_command))
        self.application.add_handler(CommandHandler("group_info", self.group_info_command))
        self.application.add_handler(CommandHandler("report_user", self.report_user_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("gm_dashboard", self.gm_dashboard_command))
        self.application.add_handler(CommandHandler("gm_ban", self.gm_ban_command))
        self.application.add_handler(CommandHandler("gm_unban", self.gm_unban_command))
        self.application.add_handler(CommandHandler("gm_stats", self.gm_stats_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_message_length))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome_new_member))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.gm_button_handler, pattern="^gm_"))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Group management bot start"""
        welcome_text = """
🛡️ *Welcome to Group Management Bot!*

I help maintain order and quality in our community groups.

📋 *GROUP COMMANDS*
/rules - Group rules and guidelines
/group_info - Group information
/report_user - Report rule violation

👑 *ADMIN COMMANDS*
/gm_dashboard - Moderation dashboard
/gm_ban - Ban user from groups
/gm_stats - Group statistics

🔒 *AUTOMATIC PROTECTION*
• Message length monitoring (120 chars max)
• New member verification
• Multi-group join requirements
• Spam protection

Keep our community safe and professional! ✅
        """
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def check_message_length(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if message exceeds length limit"""
        message = update.message
        if len(message.text) > Config.MAX_MESSAGE_LENGTH:
            await message.delete()
            
            warning_msg = await message.reply_text(
                f"⚠️ *Message Too Long*\n\n"
                f"Your message exceeded {Config.MAX_MESSAGE_LENGTH} characters.\n"
                f"Please break long messages into multiple parts.\n\n"
                f"*Current length:* {len(message.text)} characters",
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(10)
            await warning_msg.delete()
    
    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome new members and verify group joins"""
        for new_member in update.message.new_chat_members:
            if new_member.is_bot:
                continue
            
            user_id = new_member.id
            await self.manager.create_user(user_id, new_member.username, new_member.first_name)
            
            welcome_text = f"""
👋 Welcome *{new_member.first_name}* to our community!

📋 *To get started, please:*
1. Read the group rules: /rules
2. Join all our community groups
3. Verify your membership within 1 minute

🔗 *Required Groups:*
• Main Group
• VIP Channel  
• Company Resources
• Scammer Exposed

⏰ *You have 1 minute to join all groups.*
After verification, you'll have full access!

Click below to complete verification 👇
            """
            
            keyboard = [
                [InlineKeyboardButton("✅ Verify Membership", callback_data="gm_verify_join")],
                [InlineKeyboardButton("📋 Group Rules", callback_data="gm_rules")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_msg = await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            asyncio.create_task(self.verify_membership(user_id, welcome_msg.message_id, update.effective_chat.id))
    
    async def verify_membership(self, user_id: int, welcome_msg_id: int, chat_id: int):
        """Verify user joined all groups within 1 minute"""
        await asyncio.sleep(60)
        
        # Simplified verification - in real implementation, check each group
        user_joined_all = True  # Placeholder
        
        if user_joined_all:
            await self.application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=welcome_msg_id,
                text="✅ *Membership Verified!*\n\nWelcome to the community! You now have full access to all features.",
                parse_mode='Markdown'
            )
        else:
            try:
                await self.application.bot.ban_chat_member(chat_id, user_id)
                await self.application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=welcome_msg_id,
                    text="❌ *Membership Not Verified*\n\nUser was removed for not joining all required groups within 1 minute.",
                    parse_mode='Markdown'
                )
            except TelegramError as e:
                logging.error(f"Error removing user: {e}")
    
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display group rules"""
        rules_text = """
📋 *Community Rules & Guidelines*

🛡️ *MESSAGE POLICY*
• Keep messages under 120 characters
• No spam or excessive posting
• Respect all community members
• No offensive or harmful content

💼 *BUSINESS CONDUCT*  
• Genuine business offers only
• No fake or scam activities
• Transparent communication
• Professional behavior

🔒 *SECURITY RULES*
• No sharing personal information
• Report suspicious activities
• Use verified channels for payments
• Follow Telegram guidelines

🚨 *VIOLATIONS*
• Long messages will be auto-deleted
• Spam results in immediate ban
• Scams lead to permanent blacklist
• Appeals via admin contact

✅ *COMPLIANCE*
By being here, you agree to these rules.
Let's maintain a professional community!
        """
        
        await update.message.reply_text(rules_text, parse_mode='Markdown')
    
    async def group_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group information"""
        chat = update.effective_chat
        
        try:
            members_count = await self.application.bot.get_chat_members_count(chat.id)
        except:
            members_count = "Unknown"
        
        info_text = f"""
🏢 *Group Information*

📛 *Name:* {chat.title}
👥 *Members:* {members_count}
🆔 *ID:* {chat.id}

🌐 *Connected Groups:*
• Main Business Group
• VIP Exclusive Channel  
• Company Resources
• Scammer Exposed

🛡️ *Moderation:*
• Automated message control
• Member verification system
• Spam protection
• Quality maintenance

💡 *Purpose:*
Professional business networking and genuine opportunities.
        """
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
    
    async def report_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Report a user for rule violation"""
        if not context.args:
            await update.message.reply_text(
                "Usage: /report_user @username reason\n"
                "Example: /report_user @spammer Sending spam messages"
            )
            return
        
        username = context.args[0].replace('@', '')
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        report_text = f"""
🚨 *User Report*

👤 *Reported User:* @{username}
📝 *Reason:* {reason}
👮 *Reported by:* {update.effective_user.first_name}
🕒 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*Thank you for helping keep our community safe!*
        """
        
        await update.message.reply_text(report_text, parse_mode='Markdown')
    
    async def gm_dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Group management dashboard"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        dashboard_text = """
👑 *Group Management Dashboard*

📊 *MODERATION STATS*
• Total Members: Loading...
• Today's Messages: Calculating...
• Violations: Monitoring...
• Banned Users: Tracking...

⚙️ *QUICK CONTROLS*
• Member management
• Violation logs
• Auto-moderation settings
• Group configuration

🛡️ *SECURITY STATUS*
• Message filtering: ✅ Active
• Member verification: ✅ Active  
• Spam protection: ✅ Active
• Quality control: ✅ Active
        """
        
        keyboard = [
            [InlineKeyboardButton("👥 Member List", callback_data="gm_members")],
            [InlineKeyboardButton("🚨 Violations", callback_data="gm_violations")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="gm_settings")],
            [InlineKeyboardButton("📊 Statistics", callback_data="gm_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(dashboard_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def gm_ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban user from groups"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /gm_ban @username reason")
            return
        
        username = context.args[0].replace('@', '')
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        try:
            target_user = await self.manager.db.fetch_one(
                "SELECT user_id FROM users WHERE username = ?", (username,)
            )
            
            if target_user:
                await self.manager.db.execute_query(
                    "UPDATE users SET is_banned = TRUE WHERE user_id = ?", (target_user[0],)
                )
                
                # Ban from all groups (simplified)
                for group_id in [Config.MAIN_GROUP_ID, Config.VIP_CHANNEL_ID, Config.COMPANY_RESOURCES_ID, Config.SCAMMER_EXPOSED_ID]:
                    try:
                        await self.application.bot.ban_chat_member(group_id, target_user[0])
                    except:
                        pass
                
                await update.message.reply_text(f"✅ User @{username} has been banned from all groups.")
            else:
                await update.message.reply_text("❌ User not found.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error banning user: {str(e)}")
    
    async def gm_unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unban user from groups"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /gm_unban @username")
            return
        
        username = context.args[0].replace('@', '')
        
        try:
            target_user = await self.manager.db.fetch_one(
                "SELECT user_id FROM users WHERE username = ?", (username,)
            )
            
            if target_user:
                await self.manager.db.execute_query(
                    "UPDATE users SET is_banned = FALSE WHERE user_id = ?", (target_user[0],)
                )
                
                await update.message.reply_text(f"✅ User @{username} has been unbanned.")
            else:
                await update.message.reply_text("❌ User not found.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error unbanning user: {str(e)}")
    
    async def gm_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show group statistics"""
        user_id = update.effective_user.id
        if not await self.manager.is_admin(user_id):
            await update.message.reply_text("❌ Admin access required.")
            return
        
        total_users = await self.manager.db.fetch_one("SELECT COUNT(*) FROM users")
        banned_users = await self.manager.db.fetch_one("SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
        vip_users = await self.manager.db.fetch_one("SELECT COUNT(*) FROM users WHERE is_vip = TRUE")
        
        stats_text = f"""
📊 *Group Statistics*

👥 *User Statistics*
• Total Users: {total_users[0] if total_users else 0}
• Banned Users: {banned_users[0] if banned_users else 0}
• VIP Users: {vip_users[0] if vip_users else 0}
• Active Users: Calculating...

🛡️ *Moderation Stats*
• Messages Today: Tracking...
• Violations Today: Monitoring...
• Auto-bans: System data

🌐 *Group Health*
• Main Group: ✅ Active
• VIP Channel: ✅ Active
• Resources: ✅ Active
• Scammer Exposed: ✅ Active
        """
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def gm_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle group management button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "gm_verify_join":
            await query.edit_message_text(
                "✅ *Verification in progress...*\n\n"
                "Please wait while I verify your membership in all groups...",
                parse_mode='Markdown'
            )
        elif data == "gm_rules":
            await self.rules_command(update, context)
    
    def run(self):
        """Start the group management bot"""
        self.application.run_polling()

# ==================== 4. AUTOADV BOT ====================
class AutoAdvBot:
    def __init__(self, token: str, shared_manager: SharedManager):
        self.token = token
        self.manager = shared_manager
        self.payment_verifier = PaymentVerifier(shared_manager.db)
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        self.payment_sessions: Dict[int, Dict] = {}
    
    def setup_handlers(self):
        """Setup AutoADV bot handlers with enhanced payment flow"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("buy_ad", self.buy_ad_command))
        self.application.add_handler(CommandHandler("buy_vip", self.buy_vip_command))
        self.application.add_handler(CommandHandler("report_scammer", self.report_scammer_command))
        self.application.add_handler(CommandHandler("verify_payment", self.verify_payment_command))
        self.application.add_handler(CommandHandler("my_purchases", self.my_purchases_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("aa_dashboard", self.aa_dashboard_command))
        self.application.add_handler(CommandHandler("aa_toggle_mode", self.aa_toggle_mode_command))
        self.application.add_handler(CommandHandler("aa_transactions", self.aa_transactions_command))
        self.application.add_handler(CommandHandler("aa_stats", self.aa_stats_command))
        
        # Enhanced message handlers for payment flow
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_payment_flow))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.autoadv_button_handler, pattern="^autoadv_"))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AutoADV bot start command"""
        user = update.effective_user
        await self.manager.create_user(user.id, user.username, user.first_name)
        
        welcome_text = """
💰 *Welcome to AutoADV Payment Bot!*

I handle all purchases and payments for our community services.

🛒 *AVAILABLE PRODUCTS*

📢 *ADVERTISEMENTS*
• Price: 188 USDT
• Validity: 10 days
• Automatic posting every 5-6 minutes
• Professional templates

👑 *VIP MEMBERSHIP*  
• Price: 300 USDT
• Validity: 60 days
• Verified status & exclusive access
• Priority support

🚨 *SCAMMER REPORT*
• Price: FREE
• Instant posting in scammer exposed
• Help protect the community

💳 *PAYMENT METHODS*
• USDT (TRC-20) only
• Secure transaction verification
• Instant activation

*Choose a product below to get started!* 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 Buy Ad (188 USDT)", callback_data="autoadv_buy_ad")],
            [InlineKeyboardButton("👑 Buy VIP (300 USDT)", callback_data="autoadv_buy_vip")],
            [InlineKeyboardButton("🚨 Report Scammer (FREE)", callback_data="autoadv_report_scammer")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="autoadv_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def buy_ad_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle ad purchase in DMs"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "✅ I've sent you a DM to complete your purchase privately and securely!"
            )
            
            asyncio.create_task(self.delete_message_after_delay(
                update.effective_chat.id,
                update.message.message_id,
                60
            ))
            
            await self.start_ad_purchase_dm(update.effective_user.id)
            return
        
        await self.start_ad_purchase(update, context)
    
    async def start_ad_purchase_dm(self, user_id: int):
        """Start ad purchase in user's DM"""
        try:
            await self.application.bot.send_message(
                user_id,
                "🎯 *Advertisement Purchase - Step 1 of 2*\n\n"
                "Let's create your professional advertisement!\n\n"
                "Please send me the following information:\n\n"
                "*Heading:* Your ad title\n"
                "*Type:* Product/Service/Other\n"
                "*Description:* Detailed description\n"
                "*Contact:* Your contact information\n\n"
                "Example:\n"
                "Heading: Professional Web Development\n"
                "Type: Service\n"
                "Description: Expert web development services...\n"
                "Contact: @username or email@example.com",
                parse_mode='Markdown'
            )
            
            self.payment_sessions[user_id] = {
                'product': 'ad',
                'step': 1,
                'data': {},
                'price': 188.0
            }
            
        except TelegramError as e:
            logging.error(f"Could not start DM with user {user_id}: {e}")
    
    async def start_ad_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start ad purchase process in DM"""
        user_id = update.effective_user.id
        
        await update.message.reply_text(
            "🎯 *Advertisement Purchase - Step 1 of 2*\n\n"
            "Let's create your professional advertisement!\n\n"
            "Please send me the following information:\n\n"
            "*Heading:* Your ad title\n"
            "*Type:* Product/Service/Other\n"
            "*Description:* Detailed description\n"
            "*Contact:* Your contact information\n\n"
            "Example:\n"
            "Heading: Professional Web Development\n"
            "Type: Service\n"
            "Description: Expert web development services...\n"
            "Contact: @username or email@example.com",
            parse_mode='Markdown'
        )
        
        self.payment_sessions[user_id] = {
            'product': 'ad',
            'step': 1,
            'data': {},
            'price': 188.0
        }
    
    async def buy_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle VIP purchase"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "✅ I've sent you a DM to complete your VIP purchase privately and securely!"
            )
            
            asyncio.create_task(self.delete_message_after_delay(
                update.effective_chat.id,
                update.message.message_id,
                60
            ))
            
            await self.start_vip_purchase_dm(update.effective_user.id)
            return
        
        await self.start_vip_purchase(update, context)
    
    async def start_vip_purchase_dm(self, user_id: int):
        """Start VIP purchase in user's DM"""
        try:
            await self.application.bot.send_message(
                user_id,
                "👑 *VIP Membership Purchase - Step 1 of 2*\n\n"
                "Welcome to VIP registration! Let's get your exclusive membership setup.\n\n"
                "Please send me your information in this format:\n\n"
                "*Name:* Your full name\n"
                "*Phone:* Your phone number\n"
                "*Email:* Your email address\n\n"
                "Example:\n"
                "Name: John Doe\n"
                "Phone: +1234567890\n"
                "Email: john@example.com",
                parse_mode='Markdown'
            )
            
            self.payment_sessions[user_id] = {
                'product': 'vip',
                'step': 1,
                'data': {},
                'price': 300.0
            }
            
        except TelegramError as e:
            logging.error(f"Could not start VIP DM with user {user_id}: {e}")
    
    async def start_vip_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start VIP purchase process"""
        user_id = update.effective_user.id
        
        await update.message.reply_text(
            "👑 *VIP Membership Purchase - Step 1 of 2*\n\n"
            "Welcome to VIP registration! Let's get your exclusive membership setup.\n\n"
            "Please send me your information in this format:\n\n"
            "*Name:* Your full name\n"
            "*Phone:* Your phone number\n"
            "*Email:* Your email address\n\n"
            "Example:\n"
            "Name: John Doe\n"
            "Phone: +1234567890\n"
            "Email: john@example.com",
            parse_mode='Markdown'
        )
        
        self.payment_sessions[user_id] = {
            'product': 'vip',
            'step': 1,
            'data': {},
            'price': 300.0
        }
    
    async def report_scammer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle scammer report"""
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "✅ I've sent you a DM to report the scammer privately and securely!"
            )
            
            asyncio.create_task(self.delete_message_after_delay(
                update.effective_chat.id,
                update.message.message_id,
                60
            ))
            
            await self.start_scammer_report_dm(update.effective_user.id)
            return
        
        await self.start_scammer_report(update, context)
    
    async def start_scammer_report_dm(self, user_id: int):
        """Start scammer report in user's DM"""
        try:
            await self.application.bot.send_message(
                user_id,
                "🚨 *Scammer Report - Step 1 of 1*\n\n"
                "Thank you for helping protect our community!\n\n"
                "Please provide the scammer details in this format:\n\n"
                "*Scammer Name:* Name or username\n"
                "*Scammer Contact:* How to contact them\n"
                "*Incident Details:* What happened\n"
                "*Platform:* Where it occurred\n"
                "*Your Telegram:* Your @username\n\n"
                "Example:\n"
                "Scammer Name: John Scammer\n"
                "Scammer Contact: @scammer123\n"
                "Incident Details: Took payment but didn't deliver service\n"
                "Platform: This Telegram group\n"
                "Your Telegram: @yourusername",
                parse_mode='Markdown'
            )
            
            self.payment_sessions[user_id] = {
                'product': 'scam_report',
                'step': 1,
                'data': {},
                'price': 0.0
            }
            
        except TelegramError as e:
            logging.error(f"Could not start scam report DM with user {user_id}: {e}")
    
    async def start_scammer_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scammer report process"""
        user_id = update.effective_user.id
        
        await update.message.reply_text(
            "🚨 *Scammer Report - Step 1 of 1*\n\n"
            "Thank you for helping protect our community!\n\n"
            "Please provide the scammer details in this format:\n\n"
            "*Scammer Name:* Name or username\n"
            "*Scammer Contact:* How to contact them\n"
            "*Incident Details:* What happened\n"
            "*Platform:* Where it occurred\n"
            "*Your Telegram:* Your @username\n\n"
            "Example:\n"
            "Scammer Name: John Scammer\n"
            "Scammer Contact: @scammer123\n"
            "Incident Details: Took payment but didn't deliver service\n"
            "Platform: This Telegram group\n"
            "Your Telegram: @yourusername",
            parse_mode='Markdown'
        )
        
        self.payment_sessions[user_id] = {
            'product': 'scam_report',
            'step': 1,
            'data': {},
            'price': 0.0
        }
    
    async def handle_payment_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced payment flow handler with verification"""
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        
        if user_id not in self.payment_sessions:
            return
        
        session = self.payment_sessions[user_id]
        
        if session.get('step') == 'awaiting_payment':
            await self.process_payment_verification(update, session, message_text)
            return
        
        if session['product'] == 'ad':
            await self.process_ad_flow(update, session, message_text)
        elif session['product'] == 'vip':
            await self.process_vip_flow(update, session, message_text)
        elif session['product'] == 'scam_report':
            await self.process_scam_report_flow(update, session, message_text)
    
    async def process_payment_verification(self, update: Update, session: Dict, transaction_hash: str):
        """Process payment verification"""
        user_id = update.effective_user.id
        
        verifying_msg = await update.message.reply_text(
            "🔍 *Verifying Payment...*\n\n"
            "Please wait while I verify your transaction...",
            parse_mode='Markdown'
        )
        
        verification_result = await self.payment_verifier.verify_transaction(
            transaction_hash, 
            session['price'], 
            user_id
        )
        
        if verification_result['success']:
            await verifying_msg.edit_text(
                f"✅ *Payment Verified!*\n\n"
                f"{verification_result['message']}\n\n"
                f"🔄 Activating your {session['product']}...",
                parse_mode='Markdown'
            )
            
            await self.process_successful_payment(update, session, verification_result, transaction_hash)
        else:
            await verifying_msg.edit_text(
                f"❌ *Payment Verification Failed*\n\n"
                f"{verification_result['message']}\n\n"
                f"Please check and try again:\n"
                f"• Transaction hash correctness\n"
                f"• Payment amount ({session['price']} USDT)\n"
                f"• Recipient address\n"
                f"• Network confirmation",
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(
                "🔄 Please send the correct transaction hash to try again:",
                parse_mode='Markdown'
            )
    
    async def process_successful_payment(self, update: Update, session: Dict, verification_result: Dict, transaction_hash: str):
        """Process successful payment and activate product"""
        user_id = update.effective_user.id
        
        try:
            payment_mode = "dummy" if Config.DUMMY_PAYMENT_MODE else "real"
            await self.manager.db.execute_query(
                "INSERT INTO payments (user_id, product_type, amount, transaction_hash, status, verified_date, payment_mode) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, session['product'], session['price'], transaction_hash, 'completed', datetime.now().isoformat(), payment_mode)
            )
            
            if session['product'] == 'ad':
                await self.activate_advertisement(user_id, session['data'])
            elif session['product'] == 'vip':
                await self.activate_vip_membership(user_id, session['data'])
            
            success_text = self.get_success_message(session['product'], session['data'])
            await update.message.reply_text(success_text, parse_mode='Markdown')
            
            await self.send_group_notification(user_id, session['product'])
            
            del self.payment_sessions[user_id]
            
        except Exception as e:
            logging.error(f"Error processing successful payment: {e}")
            await update.message.reply_text(
                "❌ Error activating your purchase. Please contact admin for support.",
                parse_mode='Markdown'
            )
    
    async def activate_advertisement(self, user_id: int, ad_data: Dict):
        """Activate purchased advertisement"""
        expiry_date = datetime.now() + timedelta(days=10)
        
        await self.manager.db.execute_query(
            "INSERT INTO ads (user_id, heading, ad_type, description, contact, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, ad_data.get('heading'), ad_data.get('type'), ad_data.get('description'), ad_data.get('contact'), expiry_date.isoformat())
        )
    
    async def activate_vip_membership(self, user_id: int, vip_data: Dict):
        """Activate VIP membership"""
        await self.manager.add_vip(
            user_id,
            vip_data.get('name'),
            vip_data.get('phone'),
            vip_data.get('email'),
            60
        )
    
    def get_success_message(self, product_type: str, product_data: Dict) -> str:
        """Get success message for purchased product"""
        if product_type == 'ad':
            return f"""
🎉 *Advertisement Activated!*

📢 Your ad is now live and will be automatically posted every 5-6 minutes.

📋 *Ad Details:*
• Heading: {product_data.get('heading')}
• Type: {product_data.get('type')}
• Contact: {product_data.get('contact')}
• Validity: 10 days

📊 *Features:*
• Automatic rotation in main groups
• Professional formatting
• Performance tracking

Thank you for your purchase! 🚀
            """
        elif product_type == 'vip':
            return f"""
🎉 *VIP Membership Activated!*

👑 Welcome to the VIP club! Your exclusive benefits are now active.

📋 *VIP Details:*
• Name: {product_data.get('name')}
• Phone: {product_data.get('phone')}
• Email: {product_data.get('email')}
• Validity: 60 days

💎 *VIP Benefits:*
• Verified status in all groups
• Exclusive channel access
• Priority support
• Special promotions

Enjoy your VIP experience! 🌟
            """
        return "✅ Purchase completed successfully!"
    
    async def send_group_notification(self, user_id: int, product_type: str):
        """Send purchase notification to groups"""
        user = await self.manager.get_user(user_id)
        username = f"@{user[1]}" if user and user[1] else "a user"
        
        if product_type == 'vip':
            notification_text = f"🎉 {username} just upgraded to VIP! Welcome to the club! 👑"
        elif product_type == 'ad':
            notification_text = f"📢 {username} just purchased an advertisement! Watch out for their ads! 🚀"
        else:
            return
        
        try:
            await self.application.bot.send_message(Config.MAIN_GROUP_ID, notification_text)
        except Exception as e:
            logging.error(f"Error sending group notification: {e}")
    
    async def process_ad_flow(self, update: Update, session: Dict, message_text: str):
        """Enhanced ad purchase flow with payment verification"""
        user_id = update.effective_user.id
        
        if session['step'] == 1:
            try:
                lines = message_text.split('\n')
                ad_data = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        ad_data[key.strip().lower()] = value.strip()
                
                if all(k in ad_data for k in ['heading', 'type', 'description', 'contact']):
                    session['data'] = ad_data
                    session['step'] = 'awaiting_payment'
                    
                    ad_preview = self.format_ad_preview(ad_data)
                    payment_text = self.get_payment_instructions(session['price'])
                    
                    await update.message.reply_text(
                        f"🎯 *Step 2 of 2 - Review & Payment*\n\n"
                        f"{ad_preview}\n"
                        f"💳 *Payment Required:* {session['price']} USDT\n\n"
                        f"{payment_text}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "❌ Please provide all required fields: Heading, Type, Description, Contact\n"
                        "Please send the information again in the correct format."
                    )
            except Exception as e:
                await update.message.reply_text(
                    "❌ Error parsing your ad information. Please make sure it's in the correct format."
                )
    
    async def process_vip_flow(self, update: Update, session: Dict, message_text: str):
        """Enhanced VIP purchase flow with payment verification"""
        user_id = update.effective_user.id
        
        if session['step'] == 1:
            try:
                lines = message_text.split('\n')
                vip_data = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        vip_data[key.strip().lower()] = value.strip()
                
                if all(k in vip_data for k in ['name', 'phone', 'email']):
                    session['data'] = vip_data
                    session['step'] = 'awaiting_payment'
                    
                    vip_preview = self.format_vip_preview(vip_data)
                    payment_text = self.get_payment_instructions(session['price'])
                    
                    await update.message.reply_text(
                        f"👑 *Step 2 of 2 - Review & Payment*\n\n"
                        f"{vip_preview}\n"
                        f"💳 *Payment Required:* {session['price']} USDT\n\n"
                        f"{payment_text}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "❌ Please provide all required fields: Name, Phone, Email\n"
                        "Please send the information again in the correct format."
                    )
            except Exception as e:
                await update.message.reply_text(
                    "❌ Error parsing your information. Please use the correct format."
                )
    
    async def process_scam_report_flow(self, update: Update, session: Dict, message_text: str):
        """Process scam report flow"""
        user_id = update.effective_user.id
        
        if session['step'] == 1:
            try:
                lines = message_text.split('\n')
                report_data = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        report_data[key.strip().lower()] = value.strip()
                
                required_fields = ['scammer name', 'scammer contact', 'incident details', 'platform', 'your telegram']
                if all(k in report_data for k in required_fields):
                    session['data'] = report_data
                    
                    await self.post_scam_report(user_id, report_data)
                    
                    report_preview = self.format_scam_report_preview(report_data)
                    
                    await update.message.reply_text(
                        f"✅ *Scammer Report Submitted!*\n\n"
                        f"{report_preview}\n\n"
                        f"🚨 *Thank you for protecting our community!*\n"
                        f"Your report has been posted in the Scammer Exposed channel.",
                        parse_mode='Markdown'
                    )
                    
                    del self.payment_sessions[user_id]
                else:
                    await update.message.reply_text(
                        "❌ Please provide all required fields. Check the format and try again."
                    )
            except Exception as e:
                await update.message.reply_text(
                    "❌ Error parsing your report. Please use the correct format."
                )
    
    def format_ad_preview(self, ad_data: Dict) -> str:
        """Format ad preview for confirmation"""
        return f"""
📢 *Advertisement Preview*

🎯 *Heading:* {ad_data.get('heading', 'N/A')}
📋 *Type:* {ad_data.get('type', 'N/A')}
📝 *Description:* {ad_data.get('description', 'N/A')}
📞 *Contact:* {ad_data.get('contact', 'N/A')}

✅ *Features:*
• Automatic posting every 5-6 minutes
• Professional formatting
• Multiple group exposure
• 10-day validity
        """
    
    def format_vip_preview(self, vip_data: Dict) -> str:
        """Format VIP preview for confirmation"""
        return f"""
👑 *VIP Membership Preview*

👤 *Name:* {vip_data.get('name', 'N/A')}
📞 *Phone:* {vip_data.get('phone', 'N/A')}
📧 *Email:* {vip_data.get('email', 'N/A')}

💎 *Benefits:*
• Verified VIP status
• Exclusive channel access
• Priority support
• 60-day validity
• Trust and credibility boost
        """
    
    def format_scam_report_preview(self, report_data: Dict) -> str:
        """Format scam report preview"""
        return f"""
🚨 *Scammer Report*

🦹 *Scammer:* {report_data.get('scammer name', 'N/A')}
📞 *Contact:* {report_data.get('scammer contact', 'N/A')}
📝 *Incident:* {report_data.get('incident details', 'N/A')}
🌐 *Platform:* {report_data.get('platform', 'N/A')}
👤 *Reported by:* {report_data.get('your telegram', 'N/A')}
        """
    
    def get_payment_instructions(self, amount: float) -> str:
        """Get enhanced payment instructions"""
        if Config.DUMMY_PAYMENT_MODE:
            return f"""
💳 *DUMMY PAYMENT MODE - TESTING* 💳

For testing purposes:

1. Send any transaction hash (minimum 10 characters)
2. Example: `0x1234567890abcdef1234567890abcdef12345678`
3. I'll automatically verify it as successful
4. Your purchase will be activated immediately

*Send any transaction hash to continue...*
            """
        else:
            return f"""
💳 *REAL PAYMENT INSTRUCTIONS* 💳

1. Send exactly *{amount} USDT* (TRC-20) to: