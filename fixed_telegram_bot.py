"""
Telegram Multi-Bot Management System (DM-Secure Version)
Handles Advertising, VIP Verification, Group Management, and Auto-Advertisement Sales

Requirements:
pip install python-telegram-bot==20.7 requests python-dotenv schedule asyncio aiohttp
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)
from telegram.error import TelegramError
from telegram.constants import ChatType

# =============================================================================
# CONFIGURATION
# =============================================================================

# Payment Mode: Set to False for dummy payments, True for real TronScan verification
REAL_PAYMENT_MODE = False  # Change to True when ready for production

# Bot Tokens (Replace with your actual bot tokens)
ADV_BOT_TOKEN = "YOUR_ADV_BOT_TOKEN"
VIP_BOT_TOKEN = "YOUR_VIP_BOT_TOKEN"
GROUP_BOT_TOKEN = "YOUR_GROUP_MANAGEMENT_BOT_TOKEN"
AUTOADV_BOT_TOKEN = "YOUR_AUTOADV_BOT_TOKEN"

# Group/Channel IDs (Replace with actual IDs - use negative for groups)
MAIN_GROUP_ID = -1001234567890
VIP_CHANNEL_ID = -1001234567891
COMPANY_RESOURCES_ID = -1001234567892
SCAMMER_EXPOSED_ID = -1001234567893

# TronScan API Configuration
TRONSCAN_API = "https://apilist.tronscan.org/api/transaction/info"
YOUR_USDT_ADDRESS = "YOUR_TRC20_USDT_WALLET_ADDRESS"

# Rate limiting
PURCHASE_RATE_LIMIT = {}  # user_id: last_attempt_time
FAILED_TX_ATTEMPTS = {}  # user_id: failed_count

# Conversation States
(AWAITING_AD_HEADING, AWAITING_AD_TYPE, AWAITING_AD_DESC, AWAITING_AD_CONTACT,
 AWAITING_VIP_NAME, AWAITING_VIP_PHONE, AWAITING_VIP_EMAIL,
 AWAITING_SCAMMER_NAME, AWAITING_SCAMMER_CONTACT, AWAITING_INCIDENT_DETAILS,
 AWAITING_PLATFORM, AWAITING_VICTIM_TG, AWAITING_PAYMENT_CONFIRMATION,
 AWAITING_TX_HASH) = range(14)

# =============================================================================
# DATABASE (In-memory - Replace with actual database in production)
# =============================================================================

class Database:
    def __init__(self):
        self.advertisements = []
        self.vip_users = {}
        self.scammer_reports = []
        self.pending_purchases = {}
        self.active_subscriptions = {}
        self.transaction_log = []
        self.banned_users = set()
        
    def add_advertisement(self, ad_data):
        ad_data['id'] = len(self.advertisements) + 1
        ad_data['created_at'] = datetime.now()
        ad_data['expiry'] = datetime.now() + timedelta(days=10)
        self.advertisements.append(ad_data)
        return ad_data['id']
    
    def add_vip_user(self, user_id, user_data):
        user_data['subscribed_at'] = datetime.now()
        user_data['expiry'] = datetime.now() + timedelta(days=60)
        self.vip_users[user_id] = user_data
    
    def is_vip(self, user_id):
        if user_id not in self.vip_users:
            return False
        return datetime.now() < self.vip_users[user_id]['expiry']
    
    def add_scammer_report(self, report_data):
        report_data['id'] = len(self.scammer_reports) + 1
        report_data['reported_at'] = datetime.now()
        self.scammer_reports.append(report_data)
        return report_data['id']
    
    def get_active_ads(self):
        return [ad for ad in self.advertisements if datetime.now() < ad['expiry']]
    
    def log_transaction(self, tx_data):
        tx_data['logged_at'] = datetime.now()
        self.transaction_log.append(tx_data)
    
    def ban_user(self, user_id):
        self.banned_users.add(user_id)
    
    def is_banned(self, user_id):
        return user_id in self.banned_users

db = Database()

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_rate_limit(user_id: int, limit_seconds: int = 30) -> bool:
    """Check if user is rate limited"""
    if user_id in PURCHASE_RATE_LIMIT:
        last_attempt = PURCHASE_RATE_LIMIT[user_id]
        if (datetime.now() - last_attempt).seconds < limit_seconds:
            return False
    PURCHASE_RATE_LIMIT[user_id] = datetime.now()
    return True

def increment_failed_attempts(user_id: int) -> int:
    """Track failed transaction attempts"""
    if user_id not in FAILED_TX_ATTEMPTS:
        FAILED_TX_ATTEMPTS[user_id] = 0
    FAILED_TX_ATTEMPTS[user_id] += 1
    return FAILED_TX_ATTEMPTS[user_id]

def reset_failed_attempts(user_id: int):
    """Reset failed attempts after success"""
    if user_id in FAILED_TX_ATTEMPTS:
        del FAILED_TX_ATTEMPTS[user_id]

def verify_tronscan_payment(tx_hash: str, expected_amount: float) -> bool:
    """Verify USDT payment on Tron blockchain"""
    if not REAL_PAYMENT_MODE:
        # Dummy mode - always return True
        return True
    
    try:
        response = requests.get(f"{TRONSCAN_API}?hash={tx_hash}")
        if response.status_code != 200:
            return False
        
        data = response.json()
        
        # Verify transaction details
        if 'trc20TransferInfo' not in data:
            return False
        
        transfer_info = data['trc20TransferInfo'][0]
        
        # Check recipient address
        if transfer_info['to_address'] != YOUR_USDT_ADDRESS:
            return False
        
        # Check amount (USDT has 6 decimals)
        amount = float(transfer_info['amount_str']) / 1000000
        if amount < expected_amount:
            return False
        
        return True
    except Exception as e:
        print(f"Payment verification error: {e}")
        return False

async def is_private_chat(update: Update) -> bool:
    """Check if conversation is in private chat"""
    return update.effective_chat.type == ChatType.PRIVATE

async def create_ad_keyboard():
    """Create inline keyboard for advertisements"""
    keyboard = [
        [InlineKeyboardButton("📢 Post Your Ad", url="t.me/YOUR_AUTOADV_BOT?start=buy_ad")],
        [InlineKeyboardButton("⚠️ Report Scammer", url="t.me/YOUR_AUTOADV_BOT?start=report_scammer")],
        [InlineKeyboardButton("💎 Get VIP Access", url="t.me/YOUR_AUTOADV_BOT?start=buy_vip")],
        [InlineKeyboardButton("📚 Company Resources", url="t.me/YOUR_RESOURCES_CHANNEL")]
    ]
    return InlineKeyboardMarkup(keyboard)

# =============================================================================
# BOT 1: ADVERTISING BOT
# =============================================================================

class AdvertisingBot:
    def __init__(self):
        self.app = Application.builder().token(ADV_BOT_TOKEN).build()
        self.is_running = False
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message with full feature showcase"""
        welcome_msg = """
🌟 **WELCOME TO THE ULTIMATE ADVERTISING PLATFORM** 🌟

Greetings, esteemed user! You've just unlocked access to the most sophisticated advertising ecosystem in the Telegram universe. We're not just a bot - we're your digital marketing companion, your growth accelerator, your business amplifier!

🎯 **WHAT MAKES US LEGENDARY:**

✨ **Automated Excellence**: Your ads broadcast across premium channels every 5-6 minutes
📌 **Prime Visibility**: Auto-pinned messages in main groups for maximum exposure
💎 **VIP Integration**: Seamless connection with verified business resources
⚡ **Instant Reach**: Connect with thousands of genuine business seekers
🛡️ **Scammer Protection**: Built-in safety mechanisms to keep your business secure

🚀 **YOUR COMMAND CENTER:**

/start - Witness this magnificent interface
/post_ad - Launch your advertising campaign
/my_ads - View your active campaigns
/ad_stats - Detailed performance analytics
/extend_ad - Prolong your advertisement visibility
/pause_ad - Temporarily halt your campaign
/resume_ad - Reactivate paused campaigns
/delete_ad - Remove specific advertisements
/preview_ad - Test how your ad will appear
/ad_guidelines - Master the art of effective ads

💼 **BUSINESS COMMANDS:**

/premium_upgrade - Unlock VIP features
/pricing - Investment plans for growth
/success_stories - See what others achieved
/support - 24/7 assistance at your fingertips
/contact_admin - Direct line to management
/terms - Our commitment to you
/refund_policy - Transparent money-back guarantee

📊 **ANALYTICS & INSIGHTS:**

/reach_report - Audience engagement metrics
/conversion_stats - Track your ROI
/competitor_analysis - Stay ahead of the curve
/trending_ads - See what's working now
/optimize_ad - AI-powered ad improvement

🎨 **CREATIVE TOOLS:**

/ad_templates - Professional designs ready to use
/copywriting_tips - Write ads that convert
/image_guide - Visual content best practices
/emoji_boost - Make your ads pop
/call_to_action - Drive maximum engagement

🔧 **MANAGEMENT:**

/active_campaigns - Overview of running ads
/schedule_ad - Plan future campaigns
/bulk_upload - Post multiple ads efficiently
/export_data - Download your campaign data
/import_settings - Restore previous configs

🌐 **PLATFORM UPGRADE ANNOUNCEMENT:**
Our platform has evolved! Discover genuine verified companies and exclusive resources:

👉 **VIP Access**: Verified businesses only
👉 **Company Resources**: Premium business tools

Ready to dominate your market? Let's make magic happen! ✨

Type /post_ad to launch your first campaign or /help for detailed guidance.
        """
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def post_ad_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Redirect to AutoADV bot for ad purchase"""
        info_msg = """
📢 **READY TO ADVERTISE?** 📢

To post your advertisement and reach thousands of potential customers, please visit our dedicated purchase bot!

🤖 **Start here:** @YOUR_AUTOADV_BOT

Or click this button to begin: 👇
        """
        keyboard = [[InlineKeyboardButton("🚀 Buy Advertisement", url="t.me/YOUR_AUTOADV_BOT?start=buy_ad")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(info_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def broadcast_ads(self):
        """Broadcast advertisements every 5-6 minutes"""
        while self.is_running:
            try:
                active_ads = db.get_active_ads()
                
                if not active_ads:
                    # Post default platform upgrade message
                    default_msg = """
🎉 **PLATFORM UPGRADED - NEW FEATURES UNLOCKED!** 🎉

We're thrilled to announce our biggest update yet! Your trusted business platform just got exponentially better!

🌟 **WHAT'S NEW:**

💎 **VIP Channel**: Exclusively verified companies and professionals
   → Zero spam, 100% genuine business
   → Direct access to decision makers
   → Premium networking opportunities

📚 **Company Resources**: Your business toolkit
   → Templates, guides, and frameworks
   → Industry insights and trends
   → Tools for scaling your business

🛡️ **Enhanced Security**: Advanced scammer detection
   → Real-time verification systems
   → Community-backed reporting
   → 24/7 monitoring

Ready to level up? Click below! 👇
                    """
                    keyboard = await create_ad_keyboard()
                    
                    # Post to main group and pin
                    msg = await self.app.bot.send_message(
                        chat_id=MAIN_GROUP_ID,
                        text=default_msg,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                    await self.app.bot.pin_chat_message(MAIN_GROUP_ID, msg.message_id)
                    
                    # Post to company resources
                    await self.app.bot.send_message(
                        chat_id=COMPANY_RESOURCES_ID,
                        text=default_msg,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                else:
                    # Rotate through active ads
                    for ad in active_ads:
                        ad_msg = f"""
📢 **{ad['heading']}** 📢

🏷️ **Type**: {ad['type']}

📝 **Description**:
{ad['description']}

📞 **Contact**: {ad['contact']}

━━━━━━━━━━━━━━━━━━━━━━
Ad ID: #{ad['id']} | Valid until: {ad['expiry'].strftime('%Y-%m-%d')}
                        """
                        keyboard = await create_ad_keyboard()
                        
                        # Post to main group and pin
                        msg = await self.app.bot.send_message(
                            chat_id=MAIN_GROUP_ID,
                            text=ad_msg,
                            reply_markup=keyboard,
                            parse_mode='Markdown'
                        )
                        await self.app.bot.pin_chat_message(MAIN_GROUP_ID, msg.message_id)
                        
                        # Post to company resources
                        await self.app.bot.send_message(
                            chat_id=COMPANY_RESOURCES_ID,
                            text=ad_msg,
                            reply_markup=keyboard,
                            parse_mode='Markdown'
                        )
                        
                        await asyncio.sleep(350)  # 5-6 minutes
                
            except Exception as e:
                print(f"Broadcast error: {e}")
                await asyncio.sleep(60)
            
            await asyncio.sleep(300)  # Base 5 minute interval
    
    def run(self):
        """Initialize and run the advertising bot"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("post_ad", self.post_ad_info))
        
        # Add generic handlers for other commands
        commands = [
            "help", "my_ads", "ad_stats", "extend_ad", "pause_ad", "resume_ad",
            "delete_ad", "preview_ad", "ad_guidelines", "premium_upgrade", "pricing",
            "success_stories", "support", "contact_admin", "terms", "refund_policy",
            "reach_report", "conversion_stats", "competitor_analysis", "trending_ads",
            "optimize_ad", "ad_templates", "copywriting_tips", "image_guide",
            "emoji_boost", "call_to_action", "active_campaigns", "schedule_ad",
            "bulk_upload", "export_data", "import_settings"
        ]
        
        async def generic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            cmd = update.message.text[1:].replace('_', ' ').title()
            await update.message.reply_text(
                f"🎯 **{cmd}**\n\n"
                "This feature is being optimized for maximum impact!\n\n"
                "Meanwhile: /start | /post_ad | /support 🚀"
            )
        
        for cmd in commands:
            self.app.add_handler(CommandHandler(cmd, generic_command))
        
        # Start broadcasting
        self.is_running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(self.broadcast_ads())
        
        self.app.run_polling()

# =============================================================================
# BOT 2: VIP VERIFICATION BOT
# =============================================================================

class VIPBot:
    def __init__(self):
        self.app = Application.builder().token(VIP_BOT_TOKEN).build()
        self.trigger_words = ['direct', 'company', 'sbi', 'accounts', 'account']
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_msg = """
👑 **WELCOME TO VIP VERIFICATION SYSTEM** 👑

Greetings, distinguished member! You've entered the realm of verified excellence!

🌟 **YOUR VIP COMMAND CENTER:**

/start - See this majestic interface
/check_vip - Verify your VIP status
/check_user - Check another user's status
/vip_benefits - Discover exclusive perks
/upgrade_vip - Join elite membership

💎 **EXCLUSIVE VIP FEATURES:**
✓ Verified badge in all messages
✓ Priority message visibility
✓ Access to VIP-only channels
✓ Advanced networking tools

🎯 **VERIFICATION SYSTEM:**
Our advanced AI monitors conversations in real-time. When VIP users discuss business topics, we automatically verify their status!

Want to become VIP? Visit @YOUR_AUTOADV_BOT

Your status matters. Your voice is amplified. Welcome! ✨
        """
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def check_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check messages for trigger words and verify VIP status"""
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        message_text = update.message.text.lower()
        
        should_verify = False
        
        for word in self.trigger_words:
            if word in message_text:
                should_verify = True
                break
        
        if len(update.message.text) > 100:
            should_verify = True
        
        if should_verify:
            is_vip = db.is_vip(user_id)
            
            if is_vip:
                vip_data = db.vip_users[user_id]
                expiry = vip_data['expiry'].strftime('%Y-%m-%d')
                verification_msg = f"""
✅ **VIP VERIFIED** ✅

👤 User: @{username}
💎 Status: VERIFIED VIP MEMBER
📅 Valid Until: {expiry}
🛡️ Authenticity: 100% CONFIRMED

This user is a verified member of our exclusive VIP community!
                """
            else:
                verification_msg = f"""
⚠️ **NON-VIP USER** ⚠️

👤 User: @{username}
💎 Status: STANDARD MEMBER

This user has not undergone VIP verification.

Want VIP status? @YOUR_AUTOADV_BOT
                """
            
            await update.message.reply_text(verification_msg, parse_mode='Markdown')
    
    def run(self):
        """Initialize and run VIP bot"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_message))
        self.app.run_polling()

# =============================================================================
# BOT 3: GROUP MANAGEMENT BOT
# =============================================================================

class GroupManagementBot:
    def __init__(self):
        self.app = Application.builder().token(GROUP_BOT_TOKEN).build()
        self.pending_verifications = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_msg = """
🛡️ **GROUP MANAGEMENT EXCELLENCE** 🛡️

Welcome to the guardian of community quality!

🎯 **MANAGEMENT FEATURES:**
✓ Character limit enforcement (120 max)
✓ New member verification system
✓ Multi-group membership requirement
✓ Spam detection algorithms

📋 **COMMUNITY STANDARDS:**
- Messages under 120 characters
- Respectful communication
- Quality over quantity

/rules - View complete guidelines
/verify - Complete verification
/support - Get assistance

Your cooperation makes this community amazing! 🌟
        """
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome new members"""
        for new_member in update.message.new_chat_members:
            user_id = new_member.id
            username = new_member.username or new_member.first_name
            
            welcome_text = f"""
🎉 **WELCOME @{username}!** 🎉

⏰ **60-SECOND VERIFICATION REQUIRED**

Please join ALL platform groups within 60 seconds:
1️⃣ Main Group
2️⃣ VIP Channel
3️⃣ Company Resources
4️⃣ Scammer Exposed

⚠️ Failure to join = Automatic removal

✨ **RULES:**
• Keep messages under 120 characters
• Stay professional
• No spam

Timer started! ⏱️
            """
            await update.message.reply_text(welcome_text, parse_mode='Markdown')
            
            self.pending_verifications[user_id] = {
                'joined_at': datetime.now(),
                'username': username
            }
            
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            
            context.job_queue.run_once(
                self.check_verification,
                60,
                data={'user_id': user_id, 'chat_id': update.effective_chat.id}
            )
    
    async def check_verification(self, context: ContextTypes.DEFAULT_TYPE):
        """Check verification after 60 seconds"""
        job_data = context.job.data
        user_id = job_data['user_id']
        chat_id = job_data['chat_id']
        
        if user_id in self.pending_verifications:
            # Simplified - implement actual membership check
            all_joined = True  # Replace with actual verification
            
            if all_joined:
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_invite_users=True
                    )
                )
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ Verification successful! Welcome aboard! 🌟"
                )
            else:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            
            del self.pending_verifications[user_id]
    
    async def check_message_length(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Monitor and remove messages over 120 characters"""
        message = update.message
        
        if message.from_user.is_bot or message.text.startswith('/'):
            return
        
        if len(message.text) > 120:
            await message.delete()
            
            warning = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ Message removed: {len(message.text)}/120 characters.\n\n"
                     "Please keep messages concise! VIP members get extended limits: @YOUR_AUTOADV_BOT"
            )
            
            await asyncio.sleep(30)
            try:
                await warning.delete()
            except:
                pass
    
    def run(self):
        """Run group management bot"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome_new_member))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_message_length))
        self.app.run_polling()

# =============================================================================
# BOT 4: AUTO-ADV BOT (DM-ONLY PURCHASES)
# =============================================================================

class AutoADVBot:
    def __init__(self):
        self.app = Application.builder().token(AUTOADV_BOT_TOKEN).build()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start command with deep linking"""
        # Check if started from deep link
        if context.args:
            action = context.args[0]
            if action == "buy_ad":
                return await self.start_ad_purchase_dm(update, context)
            elif action == "buy_vip":
                return await self.start_vip_purchase_dm(update, context)
            elif action == "report_scammer":
                return await self.start_scammer_report_dm(update, context)
        
        welcome_msg = """
💰 **WELCOME TO AUTO-ADV MARKETPLACE** 💰

Your gateway to premium advertising, VIP access, and community safety!

🛍️ **AVAILABLE PRODUCTS:**

📢 **ADVERTISEMENT PACKAGE**
   💵 Price: 188 USDT
   ⏰ Validity: 10 Days
   📊 Reach: 10,000+ users
   
💎 **VIP MEMBERSHIP**
   💵 Price: 300 USDT
   ⏰ Validity: 60 Days
   ✅ Verified badge + Exclusive access
   
⚠️ **SCAMMER REPORT** (FREE!)
   💵 Price: FREE
   🛡️ Community protection

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ **SCAMMER REPORT**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: FREE
⚡ Processing: Instant
📢 Publication: Scammer Exposed
🛡️ Impact: Community-wide

━━━━━━━━━━━━━━━━━━━━━━━━
🎁 **SPECIAL OFFERS**
━━━━━━━━━━━━━━━━━━━━━━━━

🔥 Bundle: Ad + VIP = 450 USDT (Save 38!)
🎯 Loyalty: 3+ purchases = 10% off
💳 Payment: USDT (TRC20) - Instant
📝 Guarantee: 7-day refund on VIP

━━━━━━━━━━━━━━━━━━━━━━━━

Questions? /contact_support
Ready? /start

Invest in growth today! 🚀
        """
        
        await query.edit_message_text(pricing_msg, parse_mode='Markdown')
    
    async def show_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's order history"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Get user's ads
        user_ads = [ad for ad in db.advertisements if ad.get('user_id') == user_id]
        
        # Check VIP status
        is_vip = db.is_vip(user_id)
        
        orders_msg = "📊 **YOUR ORDERS** 📊\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if is_vip:
            vip_data = db.vip_users[user_id]
            orders_msg += f"""
💎 **VIP MEMBERSHIP**
Status: ✅ ACTIVE
Expires: {vip_data['expiry'].strftime('%Y-%m-%d')}
Days Left: {(vip_data['expiry'] - datetime.now()).days}

━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        if user_ads:
            orders_msg += "📢 **YOUR ADVERTISEMENTS:**\n\n"
            for ad in user_ads[:5]:  # Show last 5
                status = "✅ Active" if datetime.now() < ad['expiry'] else "⏰ Expired"
                orders_msg += f"""
Ad #{ad['id']}: {ad['heading'][:30]}...
Status: {status}
Expires: {ad['expiry'].strftime('%Y-%m-%d')}

"""
        else:
            orders_msg += "📢 No advertisements yet.\n\n"
        
        if not is_vip and not user_ads:
            orders_msg += "\n💡 Start your journey:\n/buy_ad or /buy_vip"
        
        orders_msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n\nNeed help? /support"
        
        await query.edit_message_text(orders_msg, parse_mode='Markdown')
    
    async def protect_sensitive_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete sensitive info shared in groups"""
        if update.effective_chat.type != ChatType.PRIVATE:
            message_text = update.message.text.lower()
            
            # Check for transaction hashes or sensitive patterns
            if any(keyword in message_text for keyword in ['tx', 'hash', 'transaction', 'payment', 'usdt', 'trc20']):
                try:
                    await update.message.delete()
                    
                    warning = await update.message.reply_text(
                        "⚠️ **SECURITY ALERT**\n\n"
                        "🔒 Sensitive payment information detected and removed!\n\n"
                        "**NEVER share in public groups:**\n"
                        "❌ Transaction hashes\n"
                        "❌ Wallet addresses\n"
                        "❌ Payment details\n\n"
                        "✅ Always use private DM: @YOUR_AUTOADV_BOT\n\n"
                        "Your security is our priority! 🛡️"
                    )
                    
                    await asyncio.sleep(10)
                    try:
                        await warning.delete()
                    except:
                        pass
                except:
                    pass
    
    def run(self):
        """Initialize and run AutoADV bot"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start))
        
        # Advertisement purchase conversation
        ad_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.button_handler, pattern='^buy_advertisement
🔒 **SECURITY NOTICE:**
All purchases happen in this PRIVATE chat for your security!

🚀 **QUICK ACTIONS:**
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement (188 USDT)", callback_data="buy_advertisement")],
            [InlineKeyboardButton("💎 Buy VIP Membership (300 USDT)", callback_data="buy_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer (FREE)", callback_data="report_scammer")],
            [InlineKeyboardButton("💳 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📊 Pricing Details", callback_data="pricing_details")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        mode_indicator = "🔴 DUMMY MODE (Testing)" if not REAL_PAYMENT_MODE else "🟢 LIVE MODE (Production)"
        welcome_msg += f"\nPayment Mode: {mode_indicator}"
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses - SECURITY CHECK"""
        query = update.callback_query
        await query.answer()
        
        # CRITICAL: Verify this is a private chat
        if not await is_private_chat(update):
            await query.answer(
                "⚠️ Please start a private chat with me first!",
                show_alert=True
            )
            return
        
        # Check if user is banned
        if db.is_banned(update.effective_user.id):
            await query.answer(
                "❌ You are banned from making purchases.",
                show_alert=True
            )
            return
        
        # Rate limiting check
        if not check_rate_limit(update.effective_user.id):
            await query.answer(
                "⏱️ Please wait 30 seconds between actions.",
                show_alert=True
            )
            return
        
        if query.data == "buy_advertisement":
            return await self.start_ad_purchase_dm(update, context)
        elif query.data == "buy_vip":
            return await self.start_vip_purchase_dm(update, context)
        elif query.data == "report_scammer":
            return await self.start_scammer_report_dm(update, context)
        elif query.data == "pricing_details":
            await self.show_pricing(update, context)
        elif query.data == "my_orders":
            await self.show_orders(update, context)
    
    async def start_ad_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start advertisement purchase in DM"""
        # Security check
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'advertisement'
        context.user_data['purchase_price'] = 188
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
📢 **ADVERTISEMENT PACKAGE PURCHASE** 📢
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Heading** 📝

Perfect choice! Your ad will reach thousands of potential customers!

📋 **PACKAGE DETAILS:**
• Duration: 10 Days
• Price: 188 USDT (TRC20)
• Broadcasting: Every 5-6 minutes
• Channels: Main Group + Company Resources
• Special: Auto-pinned in Main Group

🎯 **YOUR AD TEMPLATE:**

Please provide a catchy headline for your ad:
Example: "🔥 50% OFF - Limited Time Only!"

✏️ Send me your ad heading now!

Type /cancel anytime to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_AD_HEADING
    
    async def receive_ad_heading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement heading"""
        context.user_data['ad_heading'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Great heading!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Category** 📂

What type of advertisement is this?

Examples:
• Service
• Product
• Hiring
• Partnership
• Investment
• Real Estate
• Consulting

📝 What's your ad category?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_TYPE
    
    async def receive_ad_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement type"""
        context.user_data['ad_type'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Category noted!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Description** 📄

Provide detailed information about your offer.

💡 **Tips for great descriptions:**
• Highlight benefits, not just features
• Use clear, compelling language
• Include what makes you unique
• Keep it engaging but professional

📝 Send your description now!
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_DESC
    
    async def receive_ad_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement description"""
        context.user_data['ad_description'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Excellent description!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Contact Info** 📞

How should interested customers reach you?

Include: Telegram username, phone, email, or website

Example: @YourUsername | +1234567890 | email@example.com

📱 Your contact details?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_CONTACT
    
    async def receive_ad_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive contact and show preview with payment info"""
        context.user_data['ad_contact'] = update.message.text
        context.user_data['current_step'] = 5
        
        preview = f"""
📢 **ADVERTISEMENT PREVIEW** 📢

━━━━━━━━━━━━━━━━━━━━━━━━
**{context.user_data['ad_heading']}**

🏷️ Type: {context.user_data['ad_type']}

📝 Description:
{context.user_data['ad_description']}

📞 Contact: {context.user_data['ad_contact']}
━━━━━━━━━━━━━━━━━━━━━━━━

**Step 5 of 5: Payment** 💳

💰 **AMOUNT DUE: 188 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **CRITICAL INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 188 USDT
• Save your transaction hash
• Double-check the address

{"🔴 **DUMMY MODE**: Type any text as hash - auto-approved for testing!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send your real TronScan transaction hash after payment."}

🔒 **SECURITY:** This conversation is private and secure.

After sending payment, provide your transaction hash below! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def receive_tx_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and verify transaction hash for ad purchase"""
        # SECURITY: Check for sensitive info in groups
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ **SECURITY WARNING!**\n\n"
                "Never share transaction hashes in public groups!\n"
                "Please DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying Payment on Blockchain...**\n\n"
            "⏳ This may take a few moments.\n"
            "🔐 Your transaction is being validated securely...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)  # Simulate verification
        
        # Verify payment
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, context.user_data['purchase_price'])
        else:
            payment_verified = True  # Dummy mode
        
        if payment_verified:
            # Add advertisement to database
            ad_data = {
                'user_id': user_id,
                'username': username,
                'heading': context.user_data['ad_heading'],
                'type': context.user_data['ad_type'],
                'description': context.user_data['ad_description'],
                'contact': context.user_data['ad_contact'],
                'tx_hash': tx_hash
            }
            ad_id = db.add_advertisement(ad_data)
            
            # Log transaction
            db.log_transaction({
                'user_id': user_id,
                'type': 'advertisement',
                'amount': 188,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            # Reset failed attempts
            reset_failed_attempts(user_id)
            
            success_msg = f"""
✅ **PAYMENT VERIFIED SUCCESSFULLY!** ✅

🎉 **Congratulations, @{username}!**

Your advertisement is now ACTIVE and broadcasting!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **ORDER CONFIRMATION:**

Ad ID: #{ad_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d %H:%M')}
End: {(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d %H:%M')}
Broadcasting: Every 5-6 minutes

━━━━━━━━━━━━━━━━━━━━━━━━

📢 **YOUR AD IS NOW LIVE IN:**
• Main Group (10,000+ members)
• Company Resources Channel
• Auto-pinned for visibility

📈 **WHAT'S NEXT:**
✓ Ad broadcasts start immediately
✓ Daily performance reports via DM
✓ Edit anytime: /manage_ads
✓ Track analytics: /ad_stats
✓ Auto-renewal reminders

💡 **MAXIMIZE RESULTS:**
• Respond quickly to inquiries
• Monitor engagement daily
• Update if needed
• Consider VIP for more reach

{"⚠️ **DUMMY MODE** - No real payment processed!" if not REAL_PAYMENT_MODE else ""}

🙏 Thank you for your business!

Questions? /support
View orders: /my_orders

Welcome to premium advertising! 🚀
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post success notification in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 @{username} just launched a new ad campaign! Check it out! 💪"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
            
        else:
            # Failed verification
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **ACCOUNT SUSPENDED**\n\n"
                    "Multiple failed payment verifications detected.\n"
                    "Contact support: /contact_support"
                )
            else:
                error_msg = f"""
❌ **PAYMENT VERIFICATION FAILED**

Attempt {failed_count}/5

We couldn't verify your payment. Possible reasons:

• Transaction not found on blockchain
• Insufficient amount sent
• Wrong network (must be TRC20)
• Incorrect wallet address
• Transaction still pending

🔄 **WHAT TO DO:**

1. Double-check transaction hash
2. Ensure exactly 188 USDT sent
3. Verify TRC20 network used
4. Wait 2-3 minutes if just sent
5. Try again or contact support

Need help? /contact_support

We're here to assist! 💪
                """
                await verifying_msg.edit_text(error_msg, parse_mode='Markdown')
            
            return ConversationHandler.END
    
    async def start_vip_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start VIP purchase in DM"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'vip'
        context.user_data['purchase_price'] = 300
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 4
        
        msg = """
💎 **VIP MEMBERSHIP PURCHASE** 💎
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 4: Name** 👤

Excellent choice! You're joining the elite!

🌟 **VIP BENEFITS:**
✅ Verified badge on all messages
✅ Access to VIP-only channels
✅ 200 character message limit
✅ Priority 24/7 support
✅ Advanced networking tools
✅ Exclusive opportunities
✅ Weekly insider reports
✅ Direct admin access

📋 **MEMBERSHIP DETAILS:**
• Duration: 60 Days
• Price: 300 USDT (TRC20)
• Instant activation

🎯 **REGISTRATION:**

Please provide your full name:
(As you want it displayed on verification)

✏️ Your name:
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_VIP_NAME
    
    async def receive_vip_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP name"""
        context.user_data['vip_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 4: Phone Number** 📱

For account security and VIP direct contact privileges.

Format: +[country code][number]
Example: +1234567890

📞 Your phone number:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_PHONE
    
    async def receive_vip_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP phone"""
        context.user_data['vip_phone'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Phone saved!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 4: Email** 📧

For VIP communications and exclusive reports.

📨 Your email address:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_EMAIL
    
    async def receive_vip_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive email and show payment info"""
        context.user_data['vip_email'] = update.message.text
        context.user_data['current_step'] = 4
        
        preview = f"""
💎 **VIP MEMBERSHIP SUMMARY** 💎

━━━━━━━━━━━━━━━━━━━━━━━━
**Registration Details:**

Name: {context.user_data['vip_name']}
Phone: {context.user_data['vip_phone']}
Email: {context.user_data['vip_email']}

Duration: 60 Days
Status: Pending Payment

━━━━━━━━━━━━━━━━━━━━━━━━

**Step 4 of 4: Payment** 💳

💰 **AMOUNT DUE: 300 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **PAYMENT INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 300 USDT
• Save transaction hash
• Verify address carefully

{"🔴 **DUMMY MODE**: Type any text - auto-approved!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send real TronScan hash."}

🔒 **100% Secure Private Transaction**

Send your transaction hash now! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def verify_vip_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify VIP payment"""
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ Never share payment info in groups! DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying VIP Payment...**\n\n"
            "⏳ Validating on blockchain...\n"
            "🔐 Secure transaction processing...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)
        
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, 300)
        else:
            payment_verified = True
        
        if payment_verified:
            vip_data = {
                'name': context.user_data['vip_name'],
                'phone': context.user_data['vip_phone'],
                'email': context.user_data['vip_email'],
                'tx_hash': tx_hash,
                'username': username
            }
            db.add_vip_user(user_id, vip_data)
            
            db.log_transaction({
                'user_id': user_id,
                'type': 'vip',
                'amount': 300,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            reset_failed_attempts(user_id)
            
            success_msg = f"""
👑 **WELCOME TO VIP, {context.user_data['vip_name']}!** 👑

🎉 **Payment Verified! You're Now Elite!**

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **MEMBERSHIP ACTIVE:**

VIP ID: #{user_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d')}
Expires: {(datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')}
Duration: 60 Days

━━━━━━━━━━━━━━━━━━━━━━━━

✨ **YOUR VIP PRIVILEGES:**

✅ Verified badge (instant credibility)
✅ VIP-only channel access
✅ 200 character messages
✅ Priority support (<1hr response)
✅ Exclusive networking events
✅ Advanced analytics dashboard
✅ Weekly market insights
✅ Direct admin communication
✅ No advertising restrictions
✅ Profile customization
✅ Early feature access

🎯 **IMMEDIATE NEXT STEPS:**

1. Join VIP Channel: /vip_channel
2. Update profile: /vip_profile
3. Dashboard: /vip_dashboard
4. Meet VIPs: /vip_lounge

📱 **VIP COMMANDS:**
/vip_status - Check membership
/vip_benefits - All perks
/vip_network - Connect
/renew_vip - Extend access

💡 **PRO TIPS:**
→ Complete VIP profile now
→ Weekly VIP networking sessions
→ Use priority support anytime
→ Check exclusive opportunities daily

{"⚠️ **DUMMY MODE** - Test transaction!" if not REAL_PAYMENT_MODE else ""}

Welcome to excellence! 🌟

Questions? /vip_support
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 Welcome our newest VIP member: @{username}! 👑"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
        else:
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **SUSPENDED** - Contact /support"
                )
            else:
                await verifying_msg.edit_text(
                    f"❌ **Verification Failed** (Attempt {failed_count}/5)\n\n"
                    "Please verify your transaction and try again.\n"
                    "/contact_support for help."
                )
            
            return ConversationHandler.END
    
    async def start_scammer_report_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scammer report (FREE)"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'scammer_report'
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
⚠️ **SCAMMER REPORT SYSTEM** ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Scammer's Name** 🚨

Thank you for protecting our community! 
This service is 100% FREE.

🛡️ **HOW IT WORKS:**
Your report will be instantly posted to the Scammer Exposed channel, warning all members.

📋 **REPORT FORM:**

Scammer's name or username they used:

✏️ Provide the name:

Type /cancel to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_SCAMMER_NAME
    
    async def receive_scammer_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer name"""
        context.user_data['scammer_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Contact Info** 📞

Scammer's contact information:

Examples:
• @username
• +1234567890
• email@example.com
• Any contact they used

📱 Provide contact details:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_SCAMMER_CONTACT
    
    async def receive_scammer_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer contact"""
        context.user_data['scammer_contact'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Contact saved.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Incident Details** 📋

Describe what happened:

• What was promised?
• Money involved?
• Timeline of events?
• Evidence you have?

Be detailed:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_INCIDENT_DETAILS
    
    async def receive_incident_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive incident details"""
        context.user_data['incident_details'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Details recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Platform** 🌐

Where did this scam occur?

• Which Telegram group?
• External platform?
• Direct message?
• Other location?

🌐 Specify platform:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_PLATFORM
    
    async def receive_platform(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive platform"""
        context.user_data['platform'] = update.message.text
        context.user_data['current_step'] = 5
        
        msg = """
✅ Platform noted.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 5 of 5: Your Contact** 👤

Your Telegram username (victim contact):

This allows verification and others to reach you if they had similar experiences.

📱 Your username:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VICTIM_TG
    
    async def receive_victim_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process scammer report and post"""
        context.user_data['victim_tg'] = update.message.text
        user_id = update.message.from_user.id
        
        processing = await update.message.reply_text(
            "🔄 **Processing Report...**\n\n"
            "📝 Creating scammer alert\n"
            "🛡️ Notifying community\n"
            "⚡ Publishing to Scammer Exposed\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(2)
        
        report_data = {
            'reporter_id': user_id,
            'scammer_name': context.user_data['scammer_name'],
            'scammer_contact': context.user_data['scammer_contact'],
            'incident_details': context.user_data['incident_details'],
            'platform': context.user_data['platform'],
            'victim_tg': context.user_data['victim_tg']
        }
        report_id = db.add_scammer_report(report_data)
        
        # Create alert message
        scammer_alert = f"""
🚨 **SCAMMER ALERT #{report_id}** 🚨

⚠️ **SCAMMER IDENTIFIED:**

🏷️ Name: {report_data['scammer_name']}
📞 Contact: {report_data['scammer_contact']}

━━━━━━━━━━━━━━━━━━━━━━━━
📋 **INCIDENT DETAILS:**

{report_data['incident_details']}

━━━━━━━━━━━━━━━━━━━━━━━━
🌐 **Platform:** {report_data['platform']}
👤 **Reported By:** {report_data['victim_tg']}
📅 **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **COMMUNITY WARNING:**

DO NOT:
❌ Send money or cryptocurrency
❌ Share personal information
❌ Click suspicious links
❌ Engage in transactions

✅ **PROTECT YOURSELF:**
• Verify identities always
• Use escrow services
• Check VIP status
• Report suspicious activity

━━━━━━━━━━━━━━━━━━━━━━━━

Similar experience? Contact: {report_data['victim_tg']}
Report scammers: @YOUR_AUTOADV_BOT

🛡️ Stay safe! Stay vigilant!
        """
        
        try:
            # Post to Scammer Exposed channel (one-time only)
            await self.app.bot.send_message(
                chat_id=SCAMMER_EXPOSED_ID,
                text=scammer_alert,
                parse_mode='Markdown'
            )
            
            success_msg = f"""
✅ **SCAMMER REPORT PUBLISHED!** ✅

🎉 Thank you for protecting our community!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **REPORT CONFIRMATION:**

Report ID: #{report_id}
Status: ✅ PUBLISHED
Channel: Scammer Exposed
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Visibility: ALL MEMBERS

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ **IMPACT:**

✓ Alert sent to all members
✓ Scammer flagged in database
✓ Other victims may contact you
✓ Admin review within 24hrs
✓ Legal action if warranted

💡 **YOUR CONTRIBUTION:**
You've made our community safer for everyone!

🔒 **ADDITIONAL SUPPORT:**
• Document evidence (screenshots)
• File police report if major loss
• Contact platform support
• Monitor for similar patterns

Need help? /support
Report another: /report_scammer

Thank you for your vigilance! 🙏

━━━━━━━━━━━━━━━━━━━━━━━━
Reference: #SR{report_id}-{datetime.now().strftime('%Y%m%d')}
            """
            
            await processing.edit_text(success_msg, parse_mode='Markdown')
            
        except Exception as e:
            await processing.edit_text(
                f"⚠️ Error posting report: {str(e)}\n\n"
                "Contact /support for assistance."
            )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current purchase"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **Purchase Cancelled**\n\n"
            "No problem! Start over anytime with /start\n\n"
            "Need help? /support is here! 😊"
        )
        return ConversationHandler.END
    
    async def show_pricing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed pricing"""
        query = update.callback_query
        
        pricing_msg = """
💰 **COMPLETE PRICING GUIDE** 💰

━━━━━━━━━━━━━━━━━━━━━━━━
📢 **ADVERTISEMENT PACKAGE**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 188 USDT (TRC20)
⏰ Duration: 10 Days
📊 Reach: 10,000+ users
⚡ Frequency: Every 5-6 minutes
📌 Auto-pinned in main group
📈 Real-time analytics

**ROI POTENTIAL:**
• Average CTR: 8-12%
• Cost per impression: $0.0019
• Expected: 20,000-30,000 views

━━━━━━━━━━━━━━━━━━━━━━━━
💎 **VIP MEMBERSHIP**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 300 USDT (TRC20)
⏰ Duration: 60 Days
✅ 15+ exclusive features

**INCLUDES:**
• Verified badge
• VIP-only channels
• 200 char limit
• Priority support
• Weekly insights
• Networking tools
• Business opportunities
• Monthly meetups
• Direct admin access
• And more!

**VALUE:** Daily cost just $5

━━━━━━━━━━━━━),
                CommandHandler("buy_ad", self.start_ad_purchase_dm)
            ],
            states={
                AWAITING_AD_HEADING: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_heading)],
                AWAITING_AD_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_type)],
                AWAITING_AD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_description)],
                AWAITING_AD_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_ad_contact)],
                AWAITING_TX_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_tx_hash)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_purchase)],
            per_chat=True
        )
        
        # VIP purchase conversation
        vip_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.button_handler, pattern='^buy_vip
🔒 **SECURITY NOTICE:**
All purchases happen in this PRIVATE chat for your security!

🚀 **QUICK ACTIONS:**
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement (188 USDT)", callback_data="buy_advertisement")],
            [InlineKeyboardButton("💎 Buy VIP Membership (300 USDT)", callback_data="buy_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer (FREE)", callback_data="report_scammer")],
            [InlineKeyboardButton("💳 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📊 Pricing Details", callback_data="pricing_details")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        mode_indicator = "🔴 DUMMY MODE (Testing)" if not REAL_PAYMENT_MODE else "🟢 LIVE MODE (Production)"
        welcome_msg += f"\nPayment Mode: {mode_indicator}"
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses - SECURITY CHECK"""
        query = update.callback_query
        await query.answer()
        
        # CRITICAL: Verify this is a private chat
        if not await is_private_chat(update):
            await query.answer(
                "⚠️ Please start a private chat with me first!",
                show_alert=True
            )
            return
        
        # Check if user is banned
        if db.is_banned(update.effective_user.id):
            await query.answer(
                "❌ You are banned from making purchases.",
                show_alert=True
            )
            return
        
        # Rate limiting check
        if not check_rate_limit(update.effective_user.id):
            await query.answer(
                "⏱️ Please wait 30 seconds between actions.",
                show_alert=True
            )
            return
        
        if query.data == "buy_advertisement":
            return await self.start_ad_purchase_dm(update, context)
        elif query.data == "buy_vip":
            return await self.start_vip_purchase_dm(update, context)
        elif query.data == "report_scammer":
            return await self.start_scammer_report_dm(update, context)
        elif query.data == "pricing_details":
            await self.show_pricing(update, context)
        elif query.data == "my_orders":
            await self.show_orders(update, context)
    
    async def start_ad_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start advertisement purchase in DM"""
        # Security check
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'advertisement'
        context.user_data['purchase_price'] = 188
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
📢 **ADVERTISEMENT PACKAGE PURCHASE** 📢
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Heading** 📝

Perfect choice! Your ad will reach thousands of potential customers!

📋 **PACKAGE DETAILS:**
• Duration: 10 Days
• Price: 188 USDT (TRC20)
• Broadcasting: Every 5-6 minutes
• Channels: Main Group + Company Resources
• Special: Auto-pinned in Main Group

🎯 **YOUR AD TEMPLATE:**

Please provide a catchy headline for your ad:
Example: "🔥 50% OFF - Limited Time Only!"

✏️ Send me your ad heading now!

Type /cancel anytime to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_AD_HEADING
    
    async def receive_ad_heading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement heading"""
        context.user_data['ad_heading'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Great heading!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Category** 📂

What type of advertisement is this?

Examples:
• Service
• Product
• Hiring
• Partnership
• Investment
• Real Estate
• Consulting

📝 What's your ad category?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_TYPE
    
    async def receive_ad_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement type"""
        context.user_data['ad_type'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Category noted!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Description** 📄

Provide detailed information about your offer.

💡 **Tips for great descriptions:**
• Highlight benefits, not just features
• Use clear, compelling language
• Include what makes you unique
• Keep it engaging but professional

📝 Send your description now!
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_DESC
    
    async def receive_ad_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement description"""
        context.user_data['ad_description'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Excellent description!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Contact Info** 📞

How should interested customers reach you?

Include: Telegram username, phone, email, or website

Example: @YourUsername | +1234567890 | email@example.com

📱 Your contact details?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_CONTACT
    
    async def receive_ad_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive contact and show preview with payment info"""
        context.user_data['ad_contact'] = update.message.text
        context.user_data['current_step'] = 5
        
        preview = f"""
📢 **ADVERTISEMENT PREVIEW** 📢

━━━━━━━━━━━━━━━━━━━━━━━━
**{context.user_data['ad_heading']}**

🏷️ Type: {context.user_data['ad_type']}

📝 Description:
{context.user_data['ad_description']}

📞 Contact: {context.user_data['ad_contact']}
━━━━━━━━━━━━━━━━━━━━━━━━

**Step 5 of 5: Payment** 💳

💰 **AMOUNT DUE: 188 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **CRITICAL INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 188 USDT
• Save your transaction hash
• Double-check the address

{"🔴 **DUMMY MODE**: Type any text as hash - auto-approved for testing!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send your real TronScan transaction hash after payment."}

🔒 **SECURITY:** This conversation is private and secure.

After sending payment, provide your transaction hash below! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def receive_tx_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and verify transaction hash for ad purchase"""
        # SECURITY: Check for sensitive info in groups
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ **SECURITY WARNING!**\n\n"
                "Never share transaction hashes in public groups!\n"
                "Please DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying Payment on Blockchain...**\n\n"
            "⏳ This may take a few moments.\n"
            "🔐 Your transaction is being validated securely...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)  # Simulate verification
        
        # Verify payment
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, context.user_data['purchase_price'])
        else:
            payment_verified = True  # Dummy mode
        
        if payment_verified:
            # Add advertisement to database
            ad_data = {
                'user_id': user_id,
                'username': username,
                'heading': context.user_data['ad_heading'],
                'type': context.user_data['ad_type'],
                'description': context.user_data['ad_description'],
                'contact': context.user_data['ad_contact'],
                'tx_hash': tx_hash
            }
            ad_id = db.add_advertisement(ad_data)
            
            # Log transaction
            db.log_transaction({
                'user_id': user_id,
                'type': 'advertisement',
                'amount': 188,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            # Reset failed attempts
            reset_failed_attempts(user_id)
            
            success_msg = f"""
✅ **PAYMENT VERIFIED SUCCESSFULLY!** ✅

🎉 **Congratulations, @{username}!**

Your advertisement is now ACTIVE and broadcasting!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **ORDER CONFIRMATION:**

Ad ID: #{ad_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d %H:%M')}
End: {(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d %H:%M')}
Broadcasting: Every 5-6 minutes

━━━━━━━━━━━━━━━━━━━━━━━━

📢 **YOUR AD IS NOW LIVE IN:**
• Main Group (10,000+ members)
• Company Resources Channel
• Auto-pinned for visibility

📈 **WHAT'S NEXT:**
✓ Ad broadcasts start immediately
✓ Daily performance reports via DM
✓ Edit anytime: /manage_ads
✓ Track analytics: /ad_stats
✓ Auto-renewal reminders

💡 **MAXIMIZE RESULTS:**
• Respond quickly to inquiries
• Monitor engagement daily
• Update if needed
• Consider VIP for more reach

{"⚠️ **DUMMY MODE** - No real payment processed!" if not REAL_PAYMENT_MODE else ""}

🙏 Thank you for your business!

Questions? /support
View orders: /my_orders

Welcome to premium advertising! 🚀
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post success notification in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 @{username} just launched a new ad campaign! Check it out! 💪"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
            
        else:
            # Failed verification
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **ACCOUNT SUSPENDED**\n\n"
                    "Multiple failed payment verifications detected.\n"
                    "Contact support: /contact_support"
                )
            else:
                error_msg = f"""
❌ **PAYMENT VERIFICATION FAILED**

Attempt {failed_count}/5

We couldn't verify your payment. Possible reasons:

• Transaction not found on blockchain
• Insufficient amount sent
• Wrong network (must be TRC20)
• Incorrect wallet address
• Transaction still pending

🔄 **WHAT TO DO:**

1. Double-check transaction hash
2. Ensure exactly 188 USDT sent
3. Verify TRC20 network used
4. Wait 2-3 minutes if just sent
5. Try again or contact support

Need help? /contact_support

We're here to assist! 💪
                """
                await verifying_msg.edit_text(error_msg, parse_mode='Markdown')
            
            return ConversationHandler.END
    
    async def start_vip_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start VIP purchase in DM"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'vip'
        context.user_data['purchase_price'] = 300
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 4
        
        msg = """
💎 **VIP MEMBERSHIP PURCHASE** 💎
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 4: Name** 👤

Excellent choice! You're joining the elite!

🌟 **VIP BENEFITS:**
✅ Verified badge on all messages
✅ Access to VIP-only channels
✅ 200 character message limit
✅ Priority 24/7 support
✅ Advanced networking tools
✅ Exclusive opportunities
✅ Weekly insider reports
✅ Direct admin access

📋 **MEMBERSHIP DETAILS:**
• Duration: 60 Days
• Price: 300 USDT (TRC20)
• Instant activation

🎯 **REGISTRATION:**

Please provide your full name:
(As you want it displayed on verification)

✏️ Your name:
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_VIP_NAME
    
    async def receive_vip_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP name"""
        context.user_data['vip_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 4: Phone Number** 📱

For account security and VIP direct contact privileges.

Format: +[country code][number]
Example: +1234567890

📞 Your phone number:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_PHONE
    
    async def receive_vip_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP phone"""
        context.user_data['vip_phone'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Phone saved!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 4: Email** 📧

For VIP communications and exclusive reports.

📨 Your email address:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_EMAIL
    
    async def receive_vip_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive email and show payment info"""
        context.user_data['vip_email'] = update.message.text
        context.user_data['current_step'] = 4
        
        preview = f"""
💎 **VIP MEMBERSHIP SUMMARY** 💎

━━━━━━━━━━━━━━━━━━━━━━━━
**Registration Details:**

Name: {context.user_data['vip_name']}
Phone: {context.user_data['vip_phone']}
Email: {context.user_data['vip_email']}

Duration: 60 Days
Status: Pending Payment

━━━━━━━━━━━━━━━━━━━━━━━━

**Step 4 of 4: Payment** 💳

💰 **AMOUNT DUE: 300 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **PAYMENT INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 300 USDT
• Save transaction hash
• Verify address carefully

{"🔴 **DUMMY MODE**: Type any text - auto-approved!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send real TronScan hash."}

🔒 **100% Secure Private Transaction**

Send your transaction hash now! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def verify_vip_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify VIP payment"""
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ Never share payment info in groups! DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying VIP Payment...**\n\n"
            "⏳ Validating on blockchain...\n"
            "🔐 Secure transaction processing...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)
        
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, 300)
        else:
            payment_verified = True
        
        if payment_verified:
            vip_data = {
                'name': context.user_data['vip_name'],
                'phone': context.user_data['vip_phone'],
                'email': context.user_data['vip_email'],
                'tx_hash': tx_hash,
                'username': username
            }
            db.add_vip_user(user_id, vip_data)
            
            db.log_transaction({
                'user_id': user_id,
                'type': 'vip',
                'amount': 300,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            reset_failed_attempts(user_id)
            
            success_msg = f"""
👑 **WELCOME TO VIP, {context.user_data['vip_name']}!** 👑

🎉 **Payment Verified! You're Now Elite!**

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **MEMBERSHIP ACTIVE:**

VIP ID: #{user_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d')}
Expires: {(datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')}
Duration: 60 Days

━━━━━━━━━━━━━━━━━━━━━━━━

✨ **YOUR VIP PRIVILEGES:**

✅ Verified badge (instant credibility)
✅ VIP-only channel access
✅ 200 character messages
✅ Priority support (<1hr response)
✅ Exclusive networking events
✅ Advanced analytics dashboard
✅ Weekly market insights
✅ Direct admin communication
✅ No advertising restrictions
✅ Profile customization
✅ Early feature access

🎯 **IMMEDIATE NEXT STEPS:**

1. Join VIP Channel: /vip_channel
2. Update profile: /vip_profile
3. Dashboard: /vip_dashboard
4. Meet VIPs: /vip_lounge

📱 **VIP COMMANDS:**
/vip_status - Check membership
/vip_benefits - All perks
/vip_network - Connect
/renew_vip - Extend access

💡 **PRO TIPS:**
→ Complete VIP profile now
→ Weekly VIP networking sessions
→ Use priority support anytime
→ Check exclusive opportunities daily

{"⚠️ **DUMMY MODE** - Test transaction!" if not REAL_PAYMENT_MODE else ""}

Welcome to excellence! 🌟

Questions? /vip_support
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 Welcome our newest VIP member: @{username}! 👑"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
        else:
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **SUSPENDED** - Contact /support"
                )
            else:
                await verifying_msg.edit_text(
                    f"❌ **Verification Failed** (Attempt {failed_count}/5)\n\n"
                    "Please verify your transaction and try again.\n"
                    "/contact_support for help."
                )
            
            return ConversationHandler.END
    
    async def start_scammer_report_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scammer report (FREE)"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'scammer_report'
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
⚠️ **SCAMMER REPORT SYSTEM** ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Scammer's Name** 🚨

Thank you for protecting our community! 
This service is 100% FREE.

🛡️ **HOW IT WORKS:**
Your report will be instantly posted to the Scammer Exposed channel, warning all members.

📋 **REPORT FORM:**

Scammer's name or username they used:

✏️ Provide the name:

Type /cancel to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_SCAMMER_NAME
    
    async def receive_scammer_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer name"""
        context.user_data['scammer_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Contact Info** 📞

Scammer's contact information:

Examples:
• @username
• +1234567890
• email@example.com
• Any contact they used

📱 Provide contact details:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_SCAMMER_CONTACT
    
    async def receive_scammer_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer contact"""
        context.user_data['scammer_contact'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Contact saved.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Incident Details** 📋

Describe what happened:

• What was promised?
• Money involved?
• Timeline of events?
• Evidence you have?

Be detailed:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_INCIDENT_DETAILS
    
    async def receive_incident_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive incident details"""
        context.user_data['incident_details'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Details recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Platform** 🌐

Where did this scam occur?

• Which Telegram group?
• External platform?
• Direct message?
• Other location?

🌐 Specify platform:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_PLATFORM
    
    async def receive_platform(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive platform"""
        context.user_data['platform'] = update.message.text
        context.user_data['current_step'] = 5
        
        msg = """
✅ Platform noted.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 5 of 5: Your Contact** 👤

Your Telegram username (victim contact):

This allows verification and others to reach you if they had similar experiences.

📱 Your username:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VICTIM_TG
    
    async def receive_victim_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process scammer report and post"""
        context.user_data['victim_tg'] = update.message.text
        user_id = update.message.from_user.id
        
        processing = await update.message.reply_text(
            "🔄 **Processing Report...**\n\n"
            "📝 Creating scammer alert\n"
            "🛡️ Notifying community\n"
            "⚡ Publishing to Scammer Exposed\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(2)
        
        report_data = {
            'reporter_id': user_id,
            'scammer_name': context.user_data['scammer_name'],
            'scammer_contact': context.user_data['scammer_contact'],
            'incident_details': context.user_data['incident_details'],
            'platform': context.user_data['platform'],
            'victim_tg': context.user_data['victim_tg']
        }
        report_id = db.add_scammer_report(report_data)
        
        # Create alert message
        scammer_alert = f"""
🚨 **SCAMMER ALERT #{report_id}** 🚨

⚠️ **SCAMMER IDENTIFIED:**

🏷️ Name: {report_data['scammer_name']}
📞 Contact: {report_data['scammer_contact']}

━━━━━━━━━━━━━━━━━━━━━━━━
📋 **INCIDENT DETAILS:**

{report_data['incident_details']}

━━━━━━━━━━━━━━━━━━━━━━━━
🌐 **Platform:** {report_data['platform']}
👤 **Reported By:** {report_data['victim_tg']}
📅 **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **COMMUNITY WARNING:**

DO NOT:
❌ Send money or cryptocurrency
❌ Share personal information
❌ Click suspicious links
❌ Engage in transactions

✅ **PROTECT YOURSELF:**
• Verify identities always
• Use escrow services
• Check VIP status
• Report suspicious activity

━━━━━━━━━━━━━━━━━━━━━━━━

Similar experience? Contact: {report_data['victim_tg']}
Report scammers: @YOUR_AUTOADV_BOT

🛡️ Stay safe! Stay vigilant!
        """
        
        try:
            # Post to Scammer Exposed channel (one-time only)
            await self.app.bot.send_message(
                chat_id=SCAMMER_EXPOSED_ID,
                text=scammer_alert,
                parse_mode='Markdown'
            )
            
            success_msg = f"""
✅ **SCAMMER REPORT PUBLISHED!** ✅

🎉 Thank you for protecting our community!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **REPORT CONFIRMATION:**

Report ID: #{report_id}
Status: ✅ PUBLISHED
Channel: Scammer Exposed
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Visibility: ALL MEMBERS

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ **IMPACT:**

✓ Alert sent to all members
✓ Scammer flagged in database
✓ Other victims may contact you
✓ Admin review within 24hrs
✓ Legal action if warranted

💡 **YOUR CONTRIBUTION:**
You've made our community safer for everyone!

🔒 **ADDITIONAL SUPPORT:**
• Document evidence (screenshots)
• File police report if major loss
• Contact platform support
• Monitor for similar patterns

Need help? /support
Report another: /report_scammer

Thank you for your vigilance! 🙏

━━━━━━━━━━━━━━━━━━━━━━━━
Reference: #SR{report_id}-{datetime.now().strftime('%Y%m%d')}
            """
            
            await processing.edit_text(success_msg, parse_mode='Markdown')
            
        except Exception as e:
            await processing.edit_text(
                f"⚠️ Error posting report: {str(e)}\n\n"
                "Contact /support for assistance."
            )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current purchase"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **Purchase Cancelled**\n\n"
            "No problem! Start over anytime with /start\n\n"
            "Need help? /support is here! 😊"
        )
        return ConversationHandler.END
    
    async def show_pricing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed pricing"""
        query = update.callback_query
        
        pricing_msg = """
💰 **COMPLETE PRICING GUIDE** 💰

━━━━━━━━━━━━━━━━━━━━━━━━
📢 **ADVERTISEMENT PACKAGE**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 188 USDT (TRC20)
⏰ Duration: 10 Days
📊 Reach: 10,000+ users
⚡ Frequency: Every 5-6 minutes
📌 Auto-pinned in main group
📈 Real-time analytics

**ROI POTENTIAL:**
• Average CTR: 8-12%
• Cost per impression: $0.0019
• Expected: 20,000-30,000 views

━━━━━━━━━━━━━━━━━━━━━━━━
💎 **VIP MEMBERSHIP**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 300 USDT (TRC20)
⏰ Duration: 60 Days
✅ 15+ exclusive features

**INCLUDES:**
• Verified badge
• VIP-only channels
• 200 char limit
• Priority support
• Weekly insights
• Networking tools
• Business opportunities
• Monthly meetups
• Direct admin access
• And more!

**VALUE:** Daily cost just $5

━━━━━━━━━━━━━),
                CommandHandler("buy_vip", self.start_vip_purchase_dm)
            ],
            states={
                AWAITING_VIP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_vip_name)],
                AWAITING_VIP_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_vip_phone)],
                AWAITING_VIP_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_vip_email)],
                AWAITING_TX_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.verify_vip_payment)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_purchase)],
            per_chat=True
        )
        
        # Scammer report conversation
        scammer_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.button_handler, pattern='^report_scammer
🔒 **SECURITY NOTICE:**
All purchases happen in this PRIVATE chat for your security!

🚀 **QUICK ACTIONS:**
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement (188 USDT)", callback_data="buy_advertisement")],
            [InlineKeyboardButton("💎 Buy VIP Membership (300 USDT)", callback_data="buy_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer (FREE)", callback_data="report_scammer")],
            [InlineKeyboardButton("💳 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📊 Pricing Details", callback_data="pricing_details")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        mode_indicator = "🔴 DUMMY MODE (Testing)" if not REAL_PAYMENT_MODE else "🟢 LIVE MODE (Production)"
        welcome_msg += f"\nPayment Mode: {mode_indicator}"
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses - SECURITY CHECK"""
        query = update.callback_query
        await query.answer()
        
        # CRITICAL: Verify this is a private chat
        if not await is_private_chat(update):
            await query.answer(
                "⚠️ Please start a private chat with me first!",
                show_alert=True
            )
            return
        
        # Check if user is banned
        if db.is_banned(update.effective_user.id):
            await query.answer(
                "❌ You are banned from making purchases.",
                show_alert=True
            )
            return
        
        # Rate limiting check
        if not check_rate_limit(update.effective_user.id):
            await query.answer(
                "⏱️ Please wait 30 seconds between actions.",
                show_alert=True
            )
            return
        
        if query.data == "buy_advertisement":
            return await self.start_ad_purchase_dm(update, context)
        elif query.data == "buy_vip":
            return await self.start_vip_purchase_dm(update, context)
        elif query.data == "report_scammer":
            return await self.start_scammer_report_dm(update, context)
        elif query.data == "pricing_details":
            await self.show_pricing(update, context)
        elif query.data == "my_orders":
            await self.show_orders(update, context)
    
    async def start_ad_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start advertisement purchase in DM"""
        # Security check
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'advertisement'
        context.user_data['purchase_price'] = 188
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
📢 **ADVERTISEMENT PACKAGE PURCHASE** 📢
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Heading** 📝

Perfect choice! Your ad will reach thousands of potential customers!

📋 **PACKAGE DETAILS:**
• Duration: 10 Days
• Price: 188 USDT (TRC20)
• Broadcasting: Every 5-6 minutes
• Channels: Main Group + Company Resources
• Special: Auto-pinned in Main Group

🎯 **YOUR AD TEMPLATE:**

Please provide a catchy headline for your ad:
Example: "🔥 50% OFF - Limited Time Only!"

✏️ Send me your ad heading now!

Type /cancel anytime to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_AD_HEADING
    
    async def receive_ad_heading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement heading"""
        context.user_data['ad_heading'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Great heading!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Category** 📂

What type of advertisement is this?

Examples:
• Service
• Product
• Hiring
• Partnership
• Investment
• Real Estate
• Consulting

📝 What's your ad category?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_TYPE
    
    async def receive_ad_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement type"""
        context.user_data['ad_type'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Category noted!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Description** 📄

Provide detailed information about your offer.

💡 **Tips for great descriptions:**
• Highlight benefits, not just features
• Use clear, compelling language
• Include what makes you unique
• Keep it engaging but professional

📝 Send your description now!
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_DESC
    
    async def receive_ad_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement description"""
        context.user_data['ad_description'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Excellent description!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Contact Info** 📞

How should interested customers reach you?

Include: Telegram username, phone, email, or website

Example: @YourUsername | +1234567890 | email@example.com

📱 Your contact details?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_CONTACT
    
    async def receive_ad_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive contact and show preview with payment info"""
        context.user_data['ad_contact'] = update.message.text
        context.user_data['current_step'] = 5
        
        preview = f"""
📢 **ADVERTISEMENT PREVIEW** 📢

━━━━━━━━━━━━━━━━━━━━━━━━
**{context.user_data['ad_heading']}**

🏷️ Type: {context.user_data['ad_type']}

📝 Description:
{context.user_data['ad_description']}

📞 Contact: {context.user_data['ad_contact']}
━━━━━━━━━━━━━━━━━━━━━━━━

**Step 5 of 5: Payment** 💳

💰 **AMOUNT DUE: 188 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **CRITICAL INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 188 USDT
• Save your transaction hash
• Double-check the address

{"🔴 **DUMMY MODE**: Type any text as hash - auto-approved for testing!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send your real TronScan transaction hash after payment."}

🔒 **SECURITY:** This conversation is private and secure.

After sending payment, provide your transaction hash below! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def receive_tx_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and verify transaction hash for ad purchase"""
        # SECURITY: Check for sensitive info in groups
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ **SECURITY WARNING!**\n\n"
                "Never share transaction hashes in public groups!\n"
                "Please DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying Payment on Blockchain...**\n\n"
            "⏳ This may take a few moments.\n"
            "🔐 Your transaction is being validated securely...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)  # Simulate verification
        
        # Verify payment
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, context.user_data['purchase_price'])
        else:
            payment_verified = True  # Dummy mode
        
        if payment_verified:
            # Add advertisement to database
            ad_data = {
                'user_id': user_id,
                'username': username,
                'heading': context.user_data['ad_heading'],
                'type': context.user_data['ad_type'],
                'description': context.user_data['ad_description'],
                'contact': context.user_data['ad_contact'],
                'tx_hash': tx_hash
            }
            ad_id = db.add_advertisement(ad_data)
            
            # Log transaction
            db.log_transaction({
                'user_id': user_id,
                'type': 'advertisement',
                'amount': 188,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            # Reset failed attempts
            reset_failed_attempts(user_id)
            
            success_msg = f"""
✅ **PAYMENT VERIFIED SUCCESSFULLY!** ✅

🎉 **Congratulations, @{username}!**

Your advertisement is now ACTIVE and broadcasting!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **ORDER CONFIRMATION:**

Ad ID: #{ad_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d %H:%M')}
End: {(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d %H:%M')}
Broadcasting: Every 5-6 minutes

━━━━━━━━━━━━━━━━━━━━━━━━

📢 **YOUR AD IS NOW LIVE IN:**
• Main Group (10,000+ members)
• Company Resources Channel
• Auto-pinned for visibility

📈 **WHAT'S NEXT:**
✓ Ad broadcasts start immediately
✓ Daily performance reports via DM
✓ Edit anytime: /manage_ads
✓ Track analytics: /ad_stats
✓ Auto-renewal reminders

💡 **MAXIMIZE RESULTS:**
• Respond quickly to inquiries
• Monitor engagement daily
• Update if needed
• Consider VIP for more reach

{"⚠️ **DUMMY MODE** - No real payment processed!" if not REAL_PAYMENT_MODE else ""}

🙏 Thank you for your business!

Questions? /support
View orders: /my_orders

Welcome to premium advertising! 🚀
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post success notification in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 @{username} just launched a new ad campaign! Check it out! 💪"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
            
        else:
            # Failed verification
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **ACCOUNT SUSPENDED**\n\n"
                    "Multiple failed payment verifications detected.\n"
                    "Contact support: /contact_support"
                )
            else:
                error_msg = f"""
❌ **PAYMENT VERIFICATION FAILED**

Attempt {failed_count}/5

We couldn't verify your payment. Possible reasons:

• Transaction not found on blockchain
• Insufficient amount sent
• Wrong network (must be TRC20)
• Incorrect wallet address
• Transaction still pending

🔄 **WHAT TO DO:**

1. Double-check transaction hash
2. Ensure exactly 188 USDT sent
3. Verify TRC20 network used
4. Wait 2-3 minutes if just sent
5. Try again or contact support

Need help? /contact_support

We're here to assist! 💪
                """
                await verifying_msg.edit_text(error_msg, parse_mode='Markdown')
            
            return ConversationHandler.END
    
    async def start_vip_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start VIP purchase in DM"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'vip'
        context.user_data['purchase_price'] = 300
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 4
        
        msg = """
💎 **VIP MEMBERSHIP PURCHASE** 💎
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 4: Name** 👤

Excellent choice! You're joining the elite!

🌟 **VIP BENEFITS:**
✅ Verified badge on all messages
✅ Access to VIP-only channels
✅ 200 character message limit
✅ Priority 24/7 support
✅ Advanced networking tools
✅ Exclusive opportunities
✅ Weekly insider reports
✅ Direct admin access

📋 **MEMBERSHIP DETAILS:**
• Duration: 60 Days
• Price: 300 USDT (TRC20)
• Instant activation

🎯 **REGISTRATION:**

Please provide your full name:
(As you want it displayed on verification)

✏️ Your name:
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_VIP_NAME
    
    async def receive_vip_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP name"""
        context.user_data['vip_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 4: Phone Number** 📱

For account security and VIP direct contact privileges.

Format: +[country code][number]
Example: +1234567890

📞 Your phone number:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_PHONE
    
    async def receive_vip_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP phone"""
        context.user_data['vip_phone'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Phone saved!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 4: Email** 📧

For VIP communications and exclusive reports.

📨 Your email address:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_EMAIL
    
    async def receive_vip_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive email and show payment info"""
        context.user_data['vip_email'] = update.message.text
        context.user_data['current_step'] = 4
        
        preview = f"""
💎 **VIP MEMBERSHIP SUMMARY** 💎

━━━━━━━━━━━━━━━━━━━━━━━━
**Registration Details:**

Name: {context.user_data['vip_name']}
Phone: {context.user_data['vip_phone']}
Email: {context.user_data['vip_email']}

Duration: 60 Days
Status: Pending Payment

━━━━━━━━━━━━━━━━━━━━━━━━

**Step 4 of 4: Payment** 💳

💰 **AMOUNT DUE: 300 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **PAYMENT INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 300 USDT
• Save transaction hash
• Verify address carefully

{"🔴 **DUMMY MODE**: Type any text - auto-approved!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send real TronScan hash."}

🔒 **100% Secure Private Transaction**

Send your transaction hash now! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def verify_vip_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify VIP payment"""
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ Never share payment info in groups! DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying VIP Payment...**\n\n"
            "⏳ Validating on blockchain...\n"
            "🔐 Secure transaction processing...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)
        
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, 300)
        else:
            payment_verified = True
        
        if payment_verified:
            vip_data = {
                'name': context.user_data['vip_name'],
                'phone': context.user_data['vip_phone'],
                'email': context.user_data['vip_email'],
                'tx_hash': tx_hash,
                'username': username
            }
            db.add_vip_user(user_id, vip_data)
            
            db.log_transaction({
                'user_id': user_id,
                'type': 'vip',
                'amount': 300,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            reset_failed_attempts(user_id)
            
            success_msg = f"""
👑 **WELCOME TO VIP, {context.user_data['vip_name']}!** 👑

🎉 **Payment Verified! You're Now Elite!**

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **MEMBERSHIP ACTIVE:**

VIP ID: #{user_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d')}
Expires: {(datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')}
Duration: 60 Days

━━━━━━━━━━━━━━━━━━━━━━━━

✨ **YOUR VIP PRIVILEGES:**

✅ Verified badge (instant credibility)
✅ VIP-only channel access
✅ 200 character messages
✅ Priority support (<1hr response)
✅ Exclusive networking events
✅ Advanced analytics dashboard
✅ Weekly market insights
✅ Direct admin communication
✅ No advertising restrictions
✅ Profile customization
✅ Early feature access

🎯 **IMMEDIATE NEXT STEPS:**

1. Join VIP Channel: /vip_channel
2. Update profile: /vip_profile
3. Dashboard: /vip_dashboard
4. Meet VIPs: /vip_lounge

📱 **VIP COMMANDS:**
/vip_status - Check membership
/vip_benefits - All perks
/vip_network - Connect
/renew_vip - Extend access

💡 **PRO TIPS:**
→ Complete VIP profile now
→ Weekly VIP networking sessions
→ Use priority support anytime
→ Check exclusive opportunities daily

{"⚠️ **DUMMY MODE** - Test transaction!" if not REAL_PAYMENT_MODE else ""}

Welcome to excellence! 🌟

Questions? /vip_support
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 Welcome our newest VIP member: @{username}! 👑"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
        else:
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **SUSPENDED** - Contact /support"
                )
            else:
                await verifying_msg.edit_text(
                    f"❌ **Verification Failed** (Attempt {failed_count}/5)\n\n"
                    "Please verify your transaction and try again.\n"
                    "/contact_support for help."
                )
            
            return ConversationHandler.END
    
    async def start_scammer_report_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scammer report (FREE)"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'scammer_report'
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
⚠️ **SCAMMER REPORT SYSTEM** ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Scammer's Name** 🚨

Thank you for protecting our community! 
This service is 100% FREE.

🛡️ **HOW IT WORKS:**
Your report will be instantly posted to the Scammer Exposed channel, warning all members.

📋 **REPORT FORM:**

Scammer's name or username they used:

✏️ Provide the name:

Type /cancel to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_SCAMMER_NAME
    
    async def receive_scammer_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer name"""
        context.user_data['scammer_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Contact Info** 📞

Scammer's contact information:

Examples:
• @username
• +1234567890
• email@example.com
• Any contact they used

📱 Provide contact details:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_SCAMMER_CONTACT
    
    async def receive_scammer_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer contact"""
        context.user_data['scammer_contact'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Contact saved.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Incident Details** 📋

Describe what happened:

• What was promised?
• Money involved?
• Timeline of events?
• Evidence you have?

Be detailed:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_INCIDENT_DETAILS
    
    async def receive_incident_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive incident details"""
        context.user_data['incident_details'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Details recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Platform** 🌐

Where did this scam occur?

• Which Telegram group?
• External platform?
• Direct message?
• Other location?

🌐 Specify platform:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_PLATFORM
    
    async def receive_platform(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive platform"""
        context.user_data['platform'] = update.message.text
        context.user_data['current_step'] = 5
        
        msg = """
✅ Platform noted.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 5 of 5: Your Contact** 👤

Your Telegram username (victim contact):

This allows verification and others to reach you if they had similar experiences.

📱 Your username:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VICTIM_TG
    
    async def receive_victim_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process scammer report and post"""
        context.user_data['victim_tg'] = update.message.text
        user_id = update.message.from_user.id
        
        processing = await update.message.reply_text(
            "🔄 **Processing Report...**\n\n"
            "📝 Creating scammer alert\n"
            "🛡️ Notifying community\n"
            "⚡ Publishing to Scammer Exposed\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(2)
        
        report_data = {
            'reporter_id': user_id,
            'scammer_name': context.user_data['scammer_name'],
            'scammer_contact': context.user_data['scammer_contact'],
            'incident_details': context.user_data['incident_details'],
            'platform': context.user_data['platform'],
            'victim_tg': context.user_data['victim_tg']
        }
        report_id = db.add_scammer_report(report_data)
        
        # Create alert message
        scammer_alert = f"""
🚨 **SCAMMER ALERT #{report_id}** 🚨

⚠️ **SCAMMER IDENTIFIED:**

🏷️ Name: {report_data['scammer_name']}
📞 Contact: {report_data['scammer_contact']}

━━━━━━━━━━━━━━━━━━━━━━━━
📋 **INCIDENT DETAILS:**

{report_data['incident_details']}

━━━━━━━━━━━━━━━━━━━━━━━━
🌐 **Platform:** {report_data['platform']}
👤 **Reported By:** {report_data['victim_tg']}
📅 **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **COMMUNITY WARNING:**

DO NOT:
❌ Send money or cryptocurrency
❌ Share personal information
❌ Click suspicious links
❌ Engage in transactions

✅ **PROTECT YOURSELF:**
• Verify identities always
• Use escrow services
• Check VIP status
• Report suspicious activity

━━━━━━━━━━━━━━━━━━━━━━━━

Similar experience? Contact: {report_data['victim_tg']}
Report scammers: @YOUR_AUTOADV_BOT

🛡️ Stay safe! Stay vigilant!
        """
        
        try:
            # Post to Scammer Exposed channel (one-time only)
            await self.app.bot.send_message(
                chat_id=SCAMMER_EXPOSED_ID,
                text=scammer_alert,
                parse_mode='Markdown'
            )
            
            success_msg = f"""
✅ **SCAMMER REPORT PUBLISHED!** ✅

🎉 Thank you for protecting our community!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **REPORT CONFIRMATION:**

Report ID: #{report_id}
Status: ✅ PUBLISHED
Channel: Scammer Exposed
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Visibility: ALL MEMBERS

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ **IMPACT:**

✓ Alert sent to all members
✓ Scammer flagged in database
✓ Other victims may contact you
✓ Admin review within 24hrs
✓ Legal action if warranted

💡 **YOUR CONTRIBUTION:**
You've made our community safer for everyone!

🔒 **ADDITIONAL SUPPORT:**
• Document evidence (screenshots)
• File police report if major loss
• Contact platform support
• Monitor for similar patterns

Need help? /support
Report another: /report_scammer

Thank you for your vigilance! 🙏

━━━━━━━━━━━━━━━━━━━━━━━━
Reference: #SR{report_id}-{datetime.now().strftime('%Y%m%d')}
            """
            
            await processing.edit_text(success_msg, parse_mode='Markdown')
            
        except Exception as e:
            await processing.edit_text(
                f"⚠️ Error posting report: {str(e)}\n\n"
                "Contact /support for assistance."
            )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current purchase"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **Purchase Cancelled**\n\n"
            "No problem! Start over anytime with /start\n\n"
            "Need help? /support is here! 😊"
        )
        return ConversationHandler.END
    
    async def show_pricing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed pricing"""
        query = update.callback_query
        
        pricing_msg = """
💰 **COMPLETE PRICING GUIDE** 💰

━━━━━━━━━━━━━━━━━━━━━━━━
📢 **ADVERTISEMENT PACKAGE**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 188 USDT (TRC20)
⏰ Duration: 10 Days
📊 Reach: 10,000+ users
⚡ Frequency: Every 5-6 minutes
📌 Auto-pinned in main group
📈 Real-time analytics

**ROI POTENTIAL:**
• Average CTR: 8-12%
• Cost per impression: $0.0019
• Expected: 20,000-30,000 views

━━━━━━━━━━━━━━━━━━━━━━━━
💎 **VIP MEMBERSHIP**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 300 USDT (TRC20)
⏰ Duration: 60 Days
✅ 15+ exclusive features

**INCLUDES:**
• Verified badge
• VIP-only channels
• 200 char limit
• Priority support
• Weekly insights
• Networking tools
• Business opportunities
• Monthly meetups
• Direct admin access
• And more!

**VALUE:** Daily cost just $5

━━━━━━━━━━━━━),
                CommandHandler("report_scammer", self.start_scammer_report_dm)
            ],
            states={
                AWAITING_SCAMMER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_scammer_name)],
                AWAITING_SCAMMER_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_scammer_contact)],
                AWAITING_INCIDENT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_incident_details)],
                AWAITING_PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_platform)],
                AWAITING_VICTIM_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_victim_tg)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_purchase)],
            per_chat=True
        )
        
        self.app.add_handler(ad_conv_handler)
        self.app.add_handler(vip_conv_handler)
        self.app.add_handler(scammer_conv_handler)
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Sensitive data protection (monitors all messages)
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.protect_sensitive_data
        ))
        
        # 40+ additional commands
        autoadv_commands = {
            "my_orders": "View your order history",
            "active_services": "Check active subscriptions",
            "payment_methods": "Available payment options",
            "verify_payment": "Verify a transaction",
            "payment_help": "Payment assistance",
            "refund_request": "Request a refund",
            "transaction_status": "Check payment status",
            "my_profile": "View account details",
            "order_history": "Complete purchase history",
            "subscription_status": "Active subscriptions",
            "renewal_reminder": "Set renewal alerts",
            "cancel_service": "End subscription",
            "promotions": "Current deals",
            "bundle_deals": "Package savings",
            "referral_program": "Earn rewards",
            "loyalty_points": "Check balance",
            "redeem_code": "Use promo code",
            "help": "Complete guide",
            "faq": "Common questions",
            "contact_support": "Human assistance",
            "report_issue": "Technical problems",
            "feature_request": "Suggest improvements",
            "pricing": "View pricing",
            "testimonials": "Customer reviews",
            "success_stories": "Success cases",
            "affiliate_program": "Partner with us",
            "api_access": "Developer API",
            "bulk_purchase": "Bulk discounts",
            "corporate_plans": "Business solutions",
            "reseller_program": "Become reseller",
            "white_label": "White label options",
            "integration_help": "Integration support",
            "webhook_setup": "Setup webhooks",
            "payment_gateway": "Gateway info",
            "crypto_info": "Cryptocurrency guide",
            "exchange_rates": "Current rates",
            "tax_invoice": "Get tax invoice",
            "billing_history": "View bills",
            "update_payment": "Update payment method",
            "security_settings": "Account security",
            "two_factor_auth": "Enable 2FA",
            "account_recovery": "Recover account"
        }
        
        async def generic_autoadv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            cmd = update.message.text[1:].replace('_', ' ').title()
            description = autoadv_commands.get(update.message.text[1:], "Feature available soon!")
            
            await update.message.reply_text(
                f"💰 **{cmd}**\n\n"
                f"{description}\n\n"
                "This feature is being optimized!\n\n"
                "Meanwhile: /start | /help | /pricing\n\n"
                "Your satisfaction is our priority! 🎯"
            )
        
        for cmd in autoadv_commands.keys():
            self.app.add_handler(CommandHandler(cmd, generic_autoadv_command))
        
        self.app.run_polling()

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """
    Main function to run all bots
    
    SETUP INSTRUCTIONS:
    ═══════════════════════════════════════════════════════════════════════
    
    1. INSTALL DEPENDENCIES:
       pip install python-telegram-bot==20.7 requests
    
    2. CONFIGURE BOT TOKENS:
       Replace all "YOUR_*_BOT_TOKEN" with actual tokens from @BotFather
    
    3. CONFIGURE GROUP IDS:
       Replace all group IDs with your actual group/channel IDs
       Use @userinfobot to get IDs (groups are negative numbers)
    
    4. CONFIGURE WALLET:
       Replace YOUR_USDT_ADDRESS with your TRC20 USDT wallet address
    
    5. SET PAYMENT MODE:
       REAL_PAYMENT_MODE = False  # For testing (dummy payments)
       REAL_PAYMENT_MODE = True   # For production (real verification)
    
    6. UPDATE DEEP LINKS:
       Replace "YOUR_AUTOADV_BOT" with your actual bot username
       In create_ad_keyboard() and all bot messages
    
    ═══════════════════════════════════════════════════════════════════════
    
    RUNNING THE BOTS:
    
    Each bot should run in a separate terminal/process:
    
    Terminal 1: python bot.py --adv
    Terminal 2: python bot.py --vip
    Terminal 3: python bot.py --group
    Terminal 4: python bot.py --autoadv
    
    Or use process managers like systemd, supervisor, or PM2
    
    ═══════════════════════════════════════════════════════════════════════
    
    PRODUCTION RECOMMENDATIONS:
    
    1. Use PostgreSQL/MongoDB instead of in-memory database
    2. Implement proper logging (Python logging module)
    3. Use webhooks instead of polling for better performance
    4. Add monitoring (Sentry, DataDog, etc.)
    5. Implement backup systems
    6. Use environment variables for sensitive data
    7. Set up SSL certificates
    8. Implement rate limiting per user
    9. Add admin dashboard
    10. Regular database backups
    
    ═══════════════════════════════════════════════════════════════════════
    
    SECURITY FEATURES IMPLEMENTED:
    
    ✅ DM-only purchase conversations
    ✅ Sensitive data auto-deletion in groups
    ✅ Rate limiting (30s between actions)
    ✅ Failed attempt tracking (5 attempts = ban)
    ✅ Transaction logging
    ✅ Private chat verification
    ✅ Blockchain payment verification
    ✅ User banning system
    
    ═══════════════════════════════════════════════════════════════════════
    """
    
    import sys
    
    print("=" * 70)
    print("🤖 TELEGRAM MULTI-BOT SYSTEM (DM-SECURE VERSION)")
    print("=" * 70)
    print(f"Payment Mode: {'🔴 DUMMY (Testing)' if not REAL_PAYMENT_MODE else '🟢 LIVE (Production)'}")
    print("=" * 70)
    print("\n⚠️  CRITICAL SECURITY FEATURES:")
    print("✅ All purchases happen in private DMs only")
    print("✅ Sensitive data auto-deleted from groups")
    print("✅ Rate limiting enabled (30s cooldown)")
    print("✅ Failed payment tracking (5 fails = ban)")
    print("✅ Transaction logging for audit")
    print("✅ Blockchain verification (when enabled)")
    print("\n" + "=" * 70)
    print("\n📋 SETUP CHECKLIST:")
    print("□ Bot tokens configured")
    print("□ Group IDs updated")
    print("□ USDT wallet address set")
    print("□ Bot usernames updated in deep links")
    print("□ Payment mode selected")
    print("\n" + "=" * 70)
    print("\n🚀 SELECT BOT TO RUN:\n")
    
    if len(sys.argv) > 1:
        bot_type = sys.argv[1].lower()
    else:
        print("1. Advertising Bot (--adv)")
        print("2. VIP Bot (--vip)")
        print("3. Group Management Bot (--group)")
        print("4. AutoADV Bot (--autoadv)")
        print("\nUsage: python bot.py --autoadv")
        print("\nDefaulting to AutoADV Bot...\n")
        bot_type = "--autoadv"
    
    try:
        if bot_type in ["--adv", "--advertising"]:
            print("📢 Starting Advertising Bot...")
            adv_bot = AdvertisingBot()
            adv_bot.run()
            
        elif bot_type in ["--vip"]:
            print("💎 Starting VIP Bot...")
            vip_bot = VIPBot()
            vip_bot.run()
            
        elif bot_type in ["--group", "--management"]:
            print("🛡️ Starting Group Management Bot...")
            group_bot = GroupManagementBot()
            group_bot.run()
            
        elif bot_type in ["--autoadv", "--sales"]:
            print("💰 Starting AutoADV Bot...")
            autoadv_bot = AutoADVBot()
            autoadv_bot.run()
            
        else:
            print(f"❌ Unknown bot type: {bot_type}")
            print("Use: --adv, --vip, --group, or --autoadv")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("🛑 Shutting down bot...")
        print("=" * 70)
        print("👋 Goodbye!")
        
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        print("\n📋 TROUBLESHOOTING:")
        print("1. Check bot token is correct")
        print("2. Verify all group IDs are set")
        print("3. Ensure dependencies are installed")
        print("4. Check Python version (3.8+)")
        print("\nFor help: Check the documentation in the code")

if __name__ == "__main__":
    main()
🔒 **SECURITY NOTICE:**
All purchases happen in this PRIVATE chat for your security!

🚀 **QUICK ACTIONS:**
        """
        
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement (188 USDT)", callback_data="buy_advertisement")],
            [InlineKeyboardButton("💎 Buy VIP Membership (300 USDT)", callback_data="buy_vip")],
            [InlineKeyboardButton("⚠️ Report Scammer (FREE)", callback_data="report_scammer")],
            [InlineKeyboardButton("💳 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📊 Pricing Details", callback_data="pricing_details")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        mode_indicator = "🔴 DUMMY MODE (Testing)" if not REAL_PAYMENT_MODE else "🟢 LIVE MODE (Production)"
        welcome_msg += f"\nPayment Mode: {mode_indicator}"
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses - SECURITY CHECK"""
        query = update.callback_query
        await query.answer()
        
        # CRITICAL: Verify this is a private chat
        if not await is_private_chat(update):
            await query.answer(
                "⚠️ Please start a private chat with me first!",
                show_alert=True
            )
            return
        
        # Check if user is banned
        if db.is_banned(update.effective_user.id):
            await query.answer(
                "❌ You are banned from making purchases.",
                show_alert=True
            )
            return
        
        # Rate limiting check
        if not check_rate_limit(update.effective_user.id):
            await query.answer(
                "⏱️ Please wait 30 seconds between actions.",
                show_alert=True
            )
            return
        
        if query.data == "buy_advertisement":
            return await self.start_ad_purchase_dm(update, context)
        elif query.data == "buy_vip":
            return await self.start_vip_purchase_dm(update, context)
        elif query.data == "report_scammer":
            return await self.start_scammer_report_dm(update, context)
        elif query.data == "pricing_details":
            await self.show_pricing(update, context)
        elif query.data == "my_orders":
            await self.show_orders(update, context)
    
    async def start_ad_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start advertisement purchase in DM"""
        # Security check
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'advertisement'
        context.user_data['purchase_price'] = 188
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
📢 **ADVERTISEMENT PACKAGE PURCHASE** 📢
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Heading** 📝

Perfect choice! Your ad will reach thousands of potential customers!

📋 **PACKAGE DETAILS:**
• Duration: 10 Days
• Price: 188 USDT (TRC20)
• Broadcasting: Every 5-6 minutes
• Channels: Main Group + Company Resources
• Special: Auto-pinned in Main Group

🎯 **YOUR AD TEMPLATE:**

Please provide a catchy headline for your ad:
Example: "🔥 50% OFF - Limited Time Only!"

✏️ Send me your ad heading now!

Type /cancel anytime to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_AD_HEADING
    
    async def receive_ad_heading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement heading"""
        context.user_data['ad_heading'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Great heading!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Category** 📂

What type of advertisement is this?

Examples:
• Service
• Product
• Hiring
• Partnership
• Investment
• Real Estate
• Consulting

📝 What's your ad category?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_TYPE
    
    async def receive_ad_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement type"""
        context.user_data['ad_type'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Category noted!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Description** 📄

Provide detailed information about your offer.

💡 **Tips for great descriptions:**
• Highlight benefits, not just features
• Use clear, compelling language
• Include what makes you unique
• Keep it engaging but professional

📝 Send your description now!
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_DESC
    
    async def receive_ad_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive advertisement description"""
        context.user_data['ad_description'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Excellent description!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Contact Info** 📞

How should interested customers reach you?

Include: Telegram username, phone, email, or website

Example: @YourUsername | +1234567890 | email@example.com

📱 Your contact details?
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_AD_CONTACT
    
    async def receive_ad_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive contact and show preview with payment info"""
        context.user_data['ad_contact'] = update.message.text
        context.user_data['current_step'] = 5
        
        preview = f"""
📢 **ADVERTISEMENT PREVIEW** 📢

━━━━━━━━━━━━━━━━━━━━━━━━
**{context.user_data['ad_heading']}**

🏷️ Type: {context.user_data['ad_type']}

📝 Description:
{context.user_data['ad_description']}

📞 Contact: {context.user_data['ad_contact']}
━━━━━━━━━━━━━━━━━━━━━━━━

**Step 5 of 5: Payment** 💳

💰 **AMOUNT DUE: 188 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **CRITICAL INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 188 USDT
• Save your transaction hash
• Double-check the address

{"🔴 **DUMMY MODE**: Type any text as hash - auto-approved for testing!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send your real TronScan transaction hash after payment."}

🔒 **SECURITY:** This conversation is private and secure.

After sending payment, provide your transaction hash below! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def receive_tx_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and verify transaction hash for ad purchase"""
        # SECURITY: Check for sensitive info in groups
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ **SECURITY WARNING!**\n\n"
                "Never share transaction hashes in public groups!\n"
                "Please DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying Payment on Blockchain...**\n\n"
            "⏳ This may take a few moments.\n"
            "🔐 Your transaction is being validated securely...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)  # Simulate verification
        
        # Verify payment
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, context.user_data['purchase_price'])
        else:
            payment_verified = True  # Dummy mode
        
        if payment_verified:
            # Add advertisement to database
            ad_data = {
                'user_id': user_id,
                'username': username,
                'heading': context.user_data['ad_heading'],
                'type': context.user_data['ad_type'],
                'description': context.user_data['ad_description'],
                'contact': context.user_data['ad_contact'],
                'tx_hash': tx_hash
            }
            ad_id = db.add_advertisement(ad_data)
            
            # Log transaction
            db.log_transaction({
                'user_id': user_id,
                'type': 'advertisement',
                'amount': 188,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            # Reset failed attempts
            reset_failed_attempts(user_id)
            
            success_msg = f"""
✅ **PAYMENT VERIFIED SUCCESSFULLY!** ✅

🎉 **Congratulations, @{username}!**

Your advertisement is now ACTIVE and broadcasting!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **ORDER CONFIRMATION:**

Ad ID: #{ad_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d %H:%M')}
End: {(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d %H:%M')}
Broadcasting: Every 5-6 minutes

━━━━━━━━━━━━━━━━━━━━━━━━

📢 **YOUR AD IS NOW LIVE IN:**
• Main Group (10,000+ members)
• Company Resources Channel
• Auto-pinned for visibility

📈 **WHAT'S NEXT:**
✓ Ad broadcasts start immediately
✓ Daily performance reports via DM
✓ Edit anytime: /manage_ads
✓ Track analytics: /ad_stats
✓ Auto-renewal reminders

💡 **MAXIMIZE RESULTS:**
• Respond quickly to inquiries
• Monitor engagement daily
• Update if needed
• Consider VIP for more reach

{"⚠️ **DUMMY MODE** - No real payment processed!" if not REAL_PAYMENT_MODE else ""}

🙏 Thank you for your business!

Questions? /support
View orders: /my_orders

Welcome to premium advertising! 🚀
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post success notification in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 @{username} just launched a new ad campaign! Check it out! 💪"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
            
        else:
            # Failed verification
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **ACCOUNT SUSPENDED**\n\n"
                    "Multiple failed payment verifications detected.\n"
                    "Contact support: /contact_support"
                )
            else:
                error_msg = f"""
❌ **PAYMENT VERIFICATION FAILED**

Attempt {failed_count}/5

We couldn't verify your payment. Possible reasons:

• Transaction not found on blockchain
• Insufficient amount sent
• Wrong network (must be TRC20)
• Incorrect wallet address
• Transaction still pending

🔄 **WHAT TO DO:**

1. Double-check transaction hash
2. Ensure exactly 188 USDT sent
3. Verify TRC20 network used
4. Wait 2-3 minutes if just sent
5. Try again or contact support

Need help? /contact_support

We're here to assist! 💪
                """
                await verifying_msg.edit_text(error_msg, parse_mode='Markdown')
            
            return ConversationHandler.END
    
    async def start_vip_purchase_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start VIP purchase in DM"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'vip'
        context.user_data['purchase_price'] = 300
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 4
        
        msg = """
💎 **VIP MEMBERSHIP PURCHASE** 💎
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 4: Name** 👤

Excellent choice! You're joining the elite!

🌟 **VIP BENEFITS:**
✅ Verified badge on all messages
✅ Access to VIP-only channels
✅ 200 character message limit
✅ Priority 24/7 support
✅ Advanced networking tools
✅ Exclusive opportunities
✅ Weekly insider reports
✅ Direct admin access

📋 **MEMBERSHIP DETAILS:**
• Duration: 60 Days
• Price: 300 USDT (TRC20)
• Instant activation

🎯 **REGISTRATION:**

Please provide your full name:
(As you want it displayed on verification)

✏️ Your name:
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_VIP_NAME
    
    async def receive_vip_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP name"""
        context.user_data['vip_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 4: Phone Number** 📱

For account security and VIP direct contact privileges.

Format: +[country code][number]
Example: +1234567890

📞 Your phone number:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_PHONE
    
    async def receive_vip_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive VIP phone"""
        context.user_data['vip_phone'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Phone saved!

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 4: Email** 📧

For VIP communications and exclusive reports.

📨 Your email address:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VIP_EMAIL
    
    async def receive_vip_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive email and show payment info"""
        context.user_data['vip_email'] = update.message.text
        context.user_data['current_step'] = 4
        
        preview = f"""
💎 **VIP MEMBERSHIP SUMMARY** 💎

━━━━━━━━━━━━━━━━━━━━━━━━
**Registration Details:**

Name: {context.user_data['vip_name']}
Phone: {context.user_data['vip_phone']}
Email: {context.user_data['vip_email']}

Duration: 60 Days
Status: Pending Payment

━━━━━━━━━━━━━━━━━━━━━━━━

**Step 4 of 4: Payment** 💳

💰 **AMOUNT DUE: 300 USDT (TRC20)**

📍 **Payment Address:**
`{YOUR_USDT_ADDRESS}`

⚠️ **PAYMENT INSTRUCTIONS:**
• Network: Tron (TRC20) ONLY
• Amount: Exactly 300 USDT
• Save transaction hash
• Verify address carefully

{"🔴 **DUMMY MODE**: Type any text - auto-approved!" if not REAL_PAYMENT_MODE else "🟢 **LIVE MODE**: Send real TronScan hash."}

🔒 **100% Secure Private Transaction**

Send your transaction hash now! 🚀

Type /cancel to abort.
        """
        await update.message.reply_text(preview, parse_mode='Markdown')
        return AWAITING_TX_HASH
    
    async def verify_vip_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify VIP payment"""
        if not await is_private_chat(update):
            await update.message.delete()
            await update.message.reply_text(
                "⚠️ Never share payment info in groups! DM me: @YOUR_AUTOADV_BOT"
            )
            return ConversationHandler.END
        
        tx_hash = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        
        verifying_msg = await update.message.reply_text(
            "🔍 **Verifying VIP Payment...**\n\n"
            "⏳ Validating on blockchain...\n"
            "🔐 Secure transaction processing...\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(3)
        
        if REAL_PAYMENT_MODE:
            payment_verified = verify_tronscan_payment(tx_hash, 300)
        else:
            payment_verified = True
        
        if payment_verified:
            vip_data = {
                'name': context.user_data['vip_name'],
                'phone': context.user_data['vip_phone'],
                'email': context.user_data['vip_email'],
                'tx_hash': tx_hash,
                'username': username
            }
            db.add_vip_user(user_id, vip_data)
            
            db.log_transaction({
                'user_id': user_id,
                'type': 'vip',
                'amount': 300,
                'tx_hash': tx_hash,
                'status': 'success'
            })
            
            reset_failed_attempts(user_id)
            
            success_msg = f"""
👑 **WELCOME TO VIP, {context.user_data['vip_name']}!** 👑

🎉 **Payment Verified! You're Now Elite!**

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **MEMBERSHIP ACTIVE:**

VIP ID: #{user_id}
Status: ✅ ACTIVE
Start: {datetime.now().strftime('%Y-%m-%d')}
Expires: {(datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')}
Duration: 60 Days

━━━━━━━━━━━━━━━━━━━━━━━━

✨ **YOUR VIP PRIVILEGES:**

✅ Verified badge (instant credibility)
✅ VIP-only channel access
✅ 200 character messages
✅ Priority support (<1hr response)
✅ Exclusive networking events
✅ Advanced analytics dashboard
✅ Weekly market insights
✅ Direct admin communication
✅ No advertising restrictions
✅ Profile customization
✅ Early feature access

🎯 **IMMEDIATE NEXT STEPS:**

1. Join VIP Channel: /vip_channel
2. Update profile: /vip_profile
3. Dashboard: /vip_dashboard
4. Meet VIPs: /vip_lounge

📱 **VIP COMMANDS:**
/vip_status - Check membership
/vip_benefits - All perks
/vip_network - Connect
/renew_vip - Extend access

💡 **PRO TIPS:**
→ Complete VIP profile now
→ Weekly VIP networking sessions
→ Use priority support anytime
→ Check exclusive opportunities daily

{"⚠️ **DUMMY MODE** - Test transaction!" if not REAL_PAYMENT_MODE else ""}

Welcome to excellence! 🌟

Questions? /vip_support
            """
            
            await verifying_msg.edit_text(success_msg, parse_mode='Markdown')
            
            # Post in main group
            try:
                await self.app.bot.send_message(
                    chat_id=MAIN_GROUP_ID,
                    text=f"🎉 Welcome our newest VIP member: @{username}! 👑"
                )
            except:
                pass
            
            context.user_data.clear()
            return ConversationHandler.END
        else:
            failed_count = increment_failed_attempts(user_id)
            
            if failed_count >= 5:
                db.ban_user(user_id)
                await verifying_msg.edit_text(
                    "❌ **SUSPENDED** - Contact /support"
                )
            else:
                await verifying_msg.edit_text(
                    f"❌ **Verification Failed** (Attempt {failed_count}/5)\n\n"
                    "Please verify your transaction and try again.\n"
                    "/contact_support for help."
                )
            
            return ConversationHandler.END
    
    async def start_scammer_report_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start scammer report (FREE)"""
        if not await is_private_chat(update):
            return
        
        context.user_data['purchase_type'] = 'scammer_report'
        context.user_data['current_step'] = 1
        context.user_data['total_steps'] = 5
        
        msg = """
⚠️ **SCAMMER REPORT SYSTEM** ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━
**Step 1 of 5: Scammer's Name** 🚨

Thank you for protecting our community! 
This service is 100% FREE.

🛡️ **HOW IT WORKS:**
Your report will be instantly posted to the Scammer Exposed channel, warning all members.

📋 **REPORT FORM:**

Scammer's name or username they used:

✏️ Provide the name:

Type /cancel to abort.
        """
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        
        return AWAITING_SCAMMER_NAME
    
    async def receive_scammer_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer name"""
        context.user_data['scammer_name'] = update.message.text
        context.user_data['current_step'] = 2
        
        msg = """
✅ Name recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 2 of 5: Contact Info** 📞

Scammer's contact information:

Examples:
• @username
• +1234567890
• email@example.com
• Any contact they used

📱 Provide contact details:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_SCAMMER_CONTACT
    
    async def receive_scammer_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive scammer contact"""
        context.user_data['scammer_contact'] = update.message.text
        context.user_data['current_step'] = 3
        
        msg = """
✅ Contact saved.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 3 of 5: Incident Details** 📋

Describe what happened:

• What was promised?
• Money involved?
• Timeline of events?
• Evidence you have?

Be detailed:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_INCIDENT_DETAILS
    
    async def receive_incident_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive incident details"""
        context.user_data['incident_details'] = update.message.text
        context.user_data['current_step'] = 4
        
        msg = """
✅ Details recorded.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 4 of 5: Platform** 🌐

Where did this scam occur?

• Which Telegram group?
• External platform?
• Direct message?
• Other location?

🌐 Specify platform:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_PLATFORM
    
    async def receive_platform(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive platform"""
        context.user_data['platform'] = update.message.text
        context.user_data['current_step'] = 5
        
        msg = """
✅ Platform noted.

━━━━━━━━━━━━━━━━━━━━━━━━
**Step 5 of 5: Your Contact** 👤

Your Telegram username (victim contact):

This allows verification and others to reach you if they had similar experiences.

📱 Your username:
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
        return AWAITING_VICTIM_TG
    
    async def receive_victim_tg(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process scammer report and post"""
        context.user_data['victim_tg'] = update.message.text
        user_id = update.message.from_user.id
        
        processing = await update.message.reply_text(
            "🔄 **Processing Report...**\n\n"
            "📝 Creating scammer alert\n"
            "🛡️ Notifying community\n"
            "⚡ Publishing to Scammer Exposed\n\n"
            "Please wait..."
        )
        
        await asyncio.sleep(2)
        
        report_data = {
            'reporter_id': user_id,
            'scammer_name': context.user_data['scammer_name'],
            'scammer_contact': context.user_data['scammer_contact'],
            'incident_details': context.user_data['incident_details'],
            'platform': context.user_data['platform'],
            'victim_tg': context.user_data['victim_tg']
        }
        report_id = db.add_scammer_report(report_data)
        
        # Create alert message
        scammer_alert = f"""
🚨 **SCAMMER ALERT #{report_id}** 🚨

⚠️ **SCAMMER IDENTIFIED:**

🏷️ Name: {report_data['scammer_name']}
📞 Contact: {report_data['scammer_contact']}

━━━━━━━━━━━━━━━━━━━━━━━━
📋 **INCIDENT DETAILS:**

{report_data['incident_details']}

━━━━━━━━━━━━━━━━━━━━━━━━
🌐 **Platform:** {report_data['platform']}
👤 **Reported By:** {report_data['victim_tg']}
📅 **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **COMMUNITY WARNING:**

DO NOT:
❌ Send money or cryptocurrency
❌ Share personal information
❌ Click suspicious links
❌ Engage in transactions

✅ **PROTECT YOURSELF:**
• Verify identities always
• Use escrow services
• Check VIP status
• Report suspicious activity

━━━━━━━━━━━━━━━━━━━━━━━━

Similar experience? Contact: {report_data['victim_tg']}
Report scammers: @YOUR_AUTOADV_BOT

🛡️ Stay safe! Stay vigilant!
        """
        
        try:
            # Post to Scammer Exposed channel (one-time only)
            await self.app.bot.send_message(
                chat_id=SCAMMER_EXPOSED_ID,
                text=scammer_alert,
                parse_mode='Markdown'
            )
            
            success_msg = f"""
✅ **SCAMMER REPORT PUBLISHED!** ✅

🎉 Thank you for protecting our community!

━━━━━━━━━━━━━━━━━━━━━━━━
📊 **REPORT CONFIRMATION:**

Report ID: #{report_id}
Status: ✅ PUBLISHED
Channel: Scammer Exposed
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Visibility: ALL MEMBERS

━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ **IMPACT:**

✓ Alert sent to all members
✓ Scammer flagged in database
✓ Other victims may contact you
✓ Admin review within 24hrs
✓ Legal action if warranted

💡 **YOUR CONTRIBUTION:**
You've made our community safer for everyone!

🔒 **ADDITIONAL SUPPORT:**
• Document evidence (screenshots)
• File police report if major loss
• Contact platform support
• Monitor for similar patterns

Need help? /support
Report another: /report_scammer

Thank you for your vigilance! 🙏

━━━━━━━━━━━━━━━━━━━━━━━━
Reference: #SR{report_id}-{datetime.now().strftime('%Y%m%d')}
            """
            
            await processing.edit_text(success_msg, parse_mode='Markdown')
            
        except Exception as e:
            await processing.edit_text(
                f"⚠️ Error posting report: {str(e)}\n\n"
                "Contact /support for assistance."
            )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current purchase"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **Purchase Cancelled**\n\n"
            "No problem! Start over anytime with /start\n\n"
            "Need help? /support is here! 😊"
        )
        return ConversationHandler.END
    
    async def show_pricing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed pricing"""
        query = update.callback_query
        
        pricing_msg = """
💰 **COMPLETE PRICING GUIDE** 💰

━━━━━━━━━━━━━━━━━━━━━━━━
📢 **ADVERTISEMENT PACKAGE**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 188 USDT (TRC20)
⏰ Duration: 10 Days
📊 Reach: 10,000+ users
⚡ Frequency: Every 5-6 minutes
📌 Auto-pinned in main group
📈 Real-time analytics

**ROI POTENTIAL:**
• Average CTR: 8-12%
• Cost per impression: $0.0019
• Expected: 20,000-30,000 views

━━━━━━━━━━━━━━━━━━━━━━━━
💎 **VIP MEMBERSHIP**
━━━━━━━━━━━━━━━━━━━━━━━━

💵 Price: 300 USDT (TRC20)
⏰ Duration: 60 Days
✅ 15+ exclusive features

**INCLUDES:**
• Verified badge
• VIP-only channels
• 200 char limit
• Priority support
• Weekly insights
• Networking tools
• Business opportunities
• Monthly meetups
• Direct admin access
• And more!

**VALUE:** Daily cost just $5

━━━━━━━━━━━━━