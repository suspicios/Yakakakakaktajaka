"""
Telegram Multi-Bot Management System
Handles Advertising, VIP Management, Group Moderation, and Auto-Advertisement Sales
"""

import asyncio
import re
import json
import time
import signal
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set
import aiohttp
import logging

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============= CONFIGURATION =============
class Config:
    # Bot Tokens
    ADVERTISING_BOT_TOKEN = "8455931212:AAGOLICokhaKTmqEJKKCzDa9gobYnywmlN4"
    VIP_BOT_TOKEN = "8233798151:AAFHctdFHjHyJEgxPXGkDQoFRVusjLQMVtU"
    GROUP_MGMT_BOT_TOKEN = "8389675530:AAHJYSKo06qummgk4cm3sgZGj0G8zH1dVKg"
    AUTOADV_BOT_TOKEN = "8418940396:AAEg2qqNOInwKfqoQSHQs4xgO4jOu7Qbh9I"
    
    # Group IDs
    MAIN_GROUP_ID = -1003097566042
    VIP_GROUP_ID = -1003075027543
    COMPANY_RESOURCES_ID = -1003145253219
    SCAMMER_EXPOSED_ID = -1002906057259
    
    # Invite Links
    MAIN_GROUP_LINK = "https://t.me/addlist/Q3yfSoHIJnpiMGJl"
    VIP_GROUP_LINK = "https://t.me/addlist/Q3yfSoHIJnpiMGJl"
    COMPANY_RESOURCES_LINK = "https://t.me/addlist/Q3yfSoHIJnpiMGJl"
    SCAMMER_EXPOSED_LINK = "https://t.me/addlist/Q3yfSoHIJnpiMGJl"
    
    # Pricing
    ADS_PRICE_USDT = 188
    ADS_VALIDITY_DAYS = 10
    VIP_PRICE_USDT = 300
    VIP_VALIDITY_DAYS = 60
    
    # TronScan API
    TRONSCAN_API = "https://apilist.tronscanapi.com/api"
    WALLET_ADDRESS = "TD1gmGWyWqFY5STqZW5PMRqMR46xJhj5rP"


# ============= DATABASE (JSON-based for simplicity) =============
class Database:
    def __init__(self):
        self.data = {
            'ads': [],
            'vip_users': {},  # user_id: expiry_timestamp
            'pending_payments': {},
            'ad_purchases': {}
        }
        self.load()
    
    def load(self):
        try:
            with open('bot_database.json', 'r') as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.save()
    
    def save(self):
        with open('bot_database.json', 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_ad(self, ad_data: dict):
        self.data['ads'].append(ad_data)
        self.save()
    
    def get_active_ads(self) -> list:
        current_time = time.time()
        return [ad for ad in self.data['ads'] if ad.get('expiry', 0) > current_time]
    
    def add_vip_user(self, user_id: int, days: int = Config.VIP_VALIDITY_DAYS):
        expiry = time.time() + (days * 24 * 60 * 60)
        self.data['vip_users'][str(user_id)] = expiry
        self.save()
    
    def is_vip(self, user_id: int) -> bool:
        user_id_str = str(user_id)
        if user_id_str in self.data['vip_users']:
            if self.data['vip_users'][user_id_str] > time.time():
                return True
            else:
                del self.data['vip_users'][user_id_str]
                self.save()
        return False
    
    def add_pending_payment(self, user_id: int, order_data: dict):
        self.data['pending_payments'][str(user_id)] = order_data
        self.save()
    
    def get_pending_payment(self, user_id: int):
        return self.data['pending_payments'].get(str(user_id))
    
    def remove_pending_payment(self, user_id: int):
        if str(user_id) in self.data['pending_payments']:
            del self.data['pending_payments'][str(user_id)]
            self.save()


db = Database()


# ============= BOT 1: ADVERTISING BOT =============
class AdvertisingBot:
    def __init__(self):
        self.app = Application.builder().token(Config.ADVERTISING_BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("stopadv", self.stop_advertising))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Advertising Bot Started!\n"
            "Ads will be posted every 5-6 minutes in Main Group and Company Resources."
        )
        # Start advertising loop
        context.job_queue.run_repeating(
            self.post_advertisements,
            interval=330,  # 5.5 minutes average
            first=10
        )
    
    async def stop_advertising(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        jobs = context.job_queue.get_jobs_by_name('advertising')
        for job in jobs:
            job.schedule_removal()
        await update.message.reply_text("✅ Advertising stopped.")
    
    async def post_advertisements(self, context: ContextTypes.DEFAULT_TYPE):
        ads = db.get_active_ads()
        
        # Default platform ad
        default_ad = {
            'heading': '🚀 Platform Upgraded!',
            'type': 'Announcement',
            'description': 'Find genuine companies on our VIP section and access quality resources!',
        }
        
        # Rotate through ads
        current_ad = ads[0] if ads else default_ad
        
        keyboard = [
            [
                InlineKeyboardButton("📌 VIP Section", url=Config.VIP_GROUP_LINK),
                InlineKeyboardButton("📚 Company Resources", url=Config.COMPANY_RESOURCES_LINK)
            ],
            [
                InlineKeyboardButton("📢 Post Your Ad", url=f"https://t.me/{context.bot.username}?start=post_ad"),
                InlineKeyboardButton("⚠️ Scammer Exposed", url=Config.SCAMMER_EXPOSED_LINK)
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            f"**{current_ad.get('heading', 'Advertisement')}**\n\n"
            f"**Type:** {current_ad.get('type', 'N/A')}\n"
            f"**Description:** {current_ad.get('description', 'N/A')}\n"
        )
        
        if 'contact' in current_ad:
            message_text += f"**Contact:** {current_ad['contact']}\n"
        
        # Post to groups
        for group_id in [Config.MAIN_GROUP_ID, Config.COMPANY_RESOURCES_ID]:
            try:
                await context.bot.send_message(
                    chat_id=group_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error posting ad to {group_id}: {e}")
        
        # Rotate ads
        if ads:
            ads.append(ads.pop(0))


# ============= BOT 2: VIP BOT =============
class VIPBot:
    VIP_KEYWORDS = ['direct', 'company', 'sbi', 'accounts', 'account']
    
    def __init__(self):
        self.app = Application.builder().token(Config.VIP_BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.check_vip_required
        ))
        self.app.add_handler(CommandHandler("checkvip", self.check_vip_status))
    
    async def check_vip_required(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id not in [Config.MAIN_GROUP_ID, Config.COMPANY_RESOURCES_ID]:
            return
        
        user_id = update.effective_user.id
        message_text = update.message.text.lower()
        
        # Check if VIP verification needed
        needs_vip = (
            any(keyword in message_text for keyword in self.VIP_KEYWORDS) or
            len(message_text) > 100
        )
        
        if needs_vip and not db.is_vip(user_id):
            await update.message.delete()
            
            keyboard = [[
                InlineKeyboardButton("🌟 Get VIP Access", url=f"https://t.me/{context.bot.username}?start=buy_vip")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ {update.effective_user.mention_html()}, this type of message requires VIP access!",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    async def check_vip_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        is_vip = db.is_vip(user_id)
        
        if is_vip:
            expiry = db.data['vip_users'][str(user_id)]
            expiry_date = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M')
            await update.message.reply_text(f"✅ You are a VIP member!\nExpires on: {expiry_date}")
        else:
            keyboard = [[
                InlineKeyboardButton("🌟 Purchase VIP", url=f"https://t.me/{context.bot.username}?start=buy_vip")
            ]]
            await update.message.reply_text(
                "❌ You are not a VIP member.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


# ============= BOT 3: GROUP MANAGEMENT BOT =============
class GroupManagementBot:
    def __init__(self):
        self.app = Application.builder().token(Config.GROUP_MGMT_BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.moderate_message
        ))
        self.app.add_handler(MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            self.welcome_new_member
        ))
    
    async def moderate_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id not in [Config.MAIN_GROUP_ID, Config.COMPANY_RESOURCES_ID]:
            return
        
        message_text = update.message.text
        word_count = len(message_text.split())
        
        # Remove messages over 50 words
        if word_count > 50:
            try:
                await update.message.delete()
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"⚠️ {update.effective_user.mention_html()}, your message was too long (over 50 words) and has been removed.",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Error deleting message: {e}")
    
    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        for new_member in update.message.new_chat_members:
            keyboard = [
                [InlineKeyboardButton("📌 Main Group", url=Config.MAIN_GROUP_LINK)],
                [InlineKeyboardButton("🌟 VIP Group", url=Config.VIP_GROUP_LINK)],
                [InlineKeyboardButton("📚 Company Resources", url=Config.COMPANY_RESOURCES_LINK)],
                [InlineKeyboardButton("⚠️ Scammer Exposed", url=Config.SCAMMER_EXPOSED_LINK)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_text = (
                f"👋 Welcome {new_member.mention_html()}!\n\n"
                f"Please join all our groups for the complete experience:"
            )
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=welcome_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )


# ============= BOT 4: AUTO-ADVERTISEMENT SALES BOT =============
class AutoAdvBot:
    def __init__(self):
        self.app = Application.builder().token(Config.AUTOADV_BOT_TOKEN).build()
        self.user_states = {}
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_input))
        self.app.add_handler(CommandHandler("verify", self.verify_payment))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📢 Buy Advertisement (188 USDT)", callback_data="buy_ads")],
            [InlineKeyboardButton("🌟 Buy VIP Access (300 USDT)", callback_data="buy_vip")],
            [InlineKeyboardButton("💰 Check Prices", callback_data="prices")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 **Welcome to Auto-Advertisement Bot!**\n\n"
            "Purchase ads or VIP access with USDT payments.\n"
            "Select an option below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "buy_ads":
            await self.start_ad_purchase(query, context)
        elif query.data == "buy_vip":
            await self.start_vip_purchase(query, context)
        elif query.data == "prices":
            await self.show_prices(query)
        elif query.data == "help":
            await self.show_help(query)
    
    async def start_ad_purchase(self, query, context):
        user_id = query.from_user.id
        self.user_states[user_id] = {
            'type': 'ad',
            'step': 'heading',
            'data': {}
        }
        
        await query.message.reply_text(
            "📢 **Advertisement Purchase**\n\n"
            "**Price:** 188 USDT\n"
            "**Validity:** 10 days\n\n"
            "Please provide the **Heading** for your ad:"
        )
    
    async def start_vip_purchase(self, query, context):
        user_id = query.from_user.id
        self.user_states[user_id] = {
            'type': 'vip',
            'step': 'name',
            'data': {}
        }
        
        await query.message.reply_text(
            "🌟 **VIP Access Purchase**\n\n"
            "**Price:** 300 USDT\n"
            "**Validity:** 60 days\n\n"
            "Please provide your **Name**:"
        )
    
    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        user_input = update.message.text
        
        if state['type'] == 'ad':
            await self.handle_ad_input(update, context, state, user_input)
        elif state['type'] == 'vip':
            await self.handle_vip_input(update, context, state, user_input)
    
    async def handle_ad_input(self, update, context, state, user_input):
        user_id = update.effective_user.id
        step = state['step']
        
        if step == 'heading':
            state['data']['heading'] = user_input
            state['step'] = 'type'
            await update.message.reply_text("Please provide the **Type** of your ad:")
        
        elif step == 'type':
            state['data']['type'] = user_input
            state['step'] = 'description'
            await update.message.reply_text("Please provide the **Description**:")
        
        elif step == 'description':
            state['data']['description'] = user_input
            state['step'] = 'contact'
            await update.message.reply_text("Please provide your **Contact** information:")
        
        elif step == 'contact':
            state['data']['contact'] = user_input
            await self.request_payment(update, context, 'ad')
    
    async def handle_vip_input(self, update, context, state, user_input):
        user_id = update.effective_user.id
        step = state['step']
        
        if step == 'name':
            state['data']['name'] = user_input
            state['step'] = 'phone'
            await update.message.reply_text("Please provide your **Phone Number**:")
        
        elif step == 'phone':
            state['data']['phone'] = user_input
            state['step'] = 'email'
            await update.message.reply_text("Please provide your **Email**:")
        
        elif step == 'email':
            state['data']['email'] = user_input
            await self.request_payment(update, context, 'vip')
    
    async def request_payment(self, update, context, purchase_type):
        user_id = update.effective_user.id
        state = self.user_states[user_id]
        
        amount = Config.ADS_PRICE_USDT if purchase_type == 'ad' else Config.VIP_PRICE_USDT
        
        # Save pending payment
        order_data = {
            'type': purchase_type,
            'data': state['data'],
            'amount': amount,
            'timestamp': time.time()
        }
        db.add_pending_payment(user_id, order_data)
        
        payment_text = (
            f"💳 **Payment Required**\n\n"
            f"**Amount:** {amount} USDT (TRC20)\n"
            f"**Wallet Address:**\n`{Config.WALLET_ADDRESS}`\n\n"
            f"⚠️ **Important:**\n"
            f"1. Send exactly {amount} USDT to the address above\n"
            f"2. After sending, use /verify <transaction_hash> to confirm\n"
            f"3. Your order will be processed within 5 minutes\n\n"
            f"Example: `/verify abc123def456...`"
        )
        
        await update.message.reply_text(payment_text, parse_mode='Markdown')
        
        # Clean up state
        del self.user_states[user_id]
    
    async def verify_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if len(context.args) < 1:
            await update.message.reply_text("❌ Please provide transaction hash: /verify <hash>")
            return
        
        tx_hash = context.args[0]
        pending = db.get_pending_payment(user_id)
        
        if not pending:
            await update.message.reply_text("❌ No pending payment found.")
            return
        
        # Verify payment on TronScan
        is_valid = await self.verify_tronscan_payment(tx_hash, pending['amount'])
        
        if is_valid:
            await update.message.reply_text("✅ Payment verified! Processing your order...")
            
            if pending['type'] == 'ad':
                # Add advertisement
                ad_data = pending['data']
                ad_data['expiry'] = time.time() + (Config.ADS_VALIDITY_DAYS * 24 * 60 * 60)
                ad_data['user_id'] = user_id
                db.add_ad(ad_data)
                
                await update.message.reply_text(
                    "✅ Your advertisement has been activated!\n"
                    f"It will run for {Config.ADS_VALIDITY_DAYS} days."
                )
            
            elif pending['type'] == 'vip':
                # Add VIP user
                db.add_vip_user(user_id, Config.VIP_VALIDITY_DAYS)
                
                # Send VIP group link
                keyboard = [[InlineKeyboardButton("🌟 Join VIP Group", url=Config.VIP_GROUP_LINK)]]
                
                await update.message.reply_text(
                    "✅ VIP access granted!\n"
                    f"Valid for {Config.VIP_VALIDITY_DAYS} days.\n\n"
                    "Click below to join the VIP group:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            
            db.remove_pending_payment(user_id)
        else:
            await update.message.reply_text(
                "❌ Payment verification failed!\n"
                "Please check:\n"
                "1. Transaction hash is correct\n"
                "2. Payment amount matches\n"
                "3. Payment was sent to correct address\n\n"
                "Contact support if issue persists."
            )
    
    async def verify_tronscan_payment(self, tx_hash: str, expected_amount: float) -> bool:
        """
        Verify USDT payment on TronScan
        Returns True if payment is valid
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{Config.TRONSCAN_API}/transaction-info?hash={tx_hash}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check if transaction exists and is confirmed
                        if not data.get('confirmed'):
                            return False
                        
                        # Verify receiver address
                        to_address = data.get('toAddress')
                        if to_address != Config.WALLET_ADDRESS:
                            return False
                        
                        # Verify amount (USDT has 6 decimals)
                        amount = float(data.get('amount', 0)) / 1_000_000
                        if abs(amount - expected_amount) > 0.01:  # Allow 0.01 tolerance
                            return False
                        
                        return True
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            return False
    
    async def show_prices(self, query):
        text = (
            "💰 **Pricing Information**\n\n"
            "📢 **Advertisement**\n"
            f"Price: {Config.ADS_PRICE_USDT} USDT\n"
            f"Validity: {Config.ADS_VALIDITY_DAYS} days\n"
            "Posted every 5-6 minutes in Main & Company Resources groups\n\n"
            "🌟 **VIP Access**\n"
            f"Price: {Config.VIP_PRICE_USDT} USDT\n"
            f"Validity: {Config.VIP_VALIDITY_DAYS} days\n"
            "Benefits:\n"
            "- Access VIP group\n"
            "- Post longer messages (100+ chars)\n"
            "- Use keywords: direct, company, sbi, accounts\n"
            "- Priority support"
        )
        await query.message.reply_text(text, parse_mode='Markdown')
    
    async def show_help(self, query):
        text = (
            "❓ **Help & Support**\n\n"
            "**How to purchase:**\n"
            "1. Select product (Ad or VIP)\n"
            "2. Fill in required information\n"
            "3. Send USDT to provided wallet\n"
            "4. Submit transaction hash with /verify\n\n"
            "**Payment Methods:**\n"
            "- USDT (TRC20) only\n\n"
            "**Contact Support:**\n"
            "For issues, contact group admins"
        )
        await query.message.reply_text(text, parse_mode='Markdown')


# ============= MAIN RUNNER =============
def run_all_bots():
    """Run all bots concurrently using asyncio"""
    async def start_bots():
        adv_bot = AdvertisingBot()
        vip_bot = VIPBot()
        group_bot = GroupManagementBot()
        autoadv_bot = AutoAdvBot()
        
        # Initialize all applications
        async with adv_bot.app:
            await adv_bot.app.initialize()
            await adv_bot.app.start()
            
            async with vip_bot.app:
                await vip_bot.app.initialize()
                await vip_bot.app.start()
                
                async with group_bot.app:
                    await group_bot.app.initialize()
                    await group_bot.app.start()
                    
                    async with autoadv_bot.app:
                        await autoadv_bot.app.initialize()
                        await autoadv_bot.app.start()
                        
                        # Start polling for all bots
                        print("✅ All bots started successfully!")
                        
                        await asyncio.gather(
                            adv_bot.app.updater.start_polling(drop_pending_updates=True),
                            vip_bot.app.updater.start_polling(drop_pending_updates=True),
                            group_bot.app.updater.start_polling(drop_pending_updates=True),
                            autoadv_bot.app.updater.start_polling(drop_pending_updates=True)
                        )
                        
                        # Keep running
                        stop_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGABRT)
                        for sig in stop_signals:
                            signal.signal(sig, lambda s, f: None)
                        
                        await asyncio.Event().wait()
    
    asyncio.run(start_bots())


if __name__ == "__main__":
    print("🤖 Starting Telegram Multi-Bot System...")
    print("✅ All configuration loaded!")
    
    try:
        run_all_bots()
    except KeyboardInterrupt:
        print("\n👋 Bots stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()