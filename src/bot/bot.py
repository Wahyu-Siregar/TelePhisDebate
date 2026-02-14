"""
TelePhisBot - Main Bot Module
Telegram bot for phishing detection using Multi-Agent Debate
"""

import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler as TelegramMessageHandler,
    filters
)

from src import __version__
from src.config import config
from src.detection import PhishingDetectionPipeline
from src.database.client import get_supabase_client
from .handlers import MessageHandler
from .actions import BotActions


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Friendly stage names for display
STAGE_NAMES = {
    "triage": "Rule-Based Triage",
    "single_shot": "Single-Shot LLM",
    "mad": "Multi-Agent Debate",
}


class TelePhisBot:
    """
    TelePhisDebate Telegram Bot
    
    Features:
    - Real-time phishing detection in group chats
    - Multi-stage analysis (Triage → LLM → MAD)
    - VirusTotal URL checking for all links
    - Admin notifications for phishing/suspicious content
    - Persistent stats from Supabase database
    - User registration and baseline tracking
    - Statistics and monitoring commands
    """
    
    def __init__(
        self,
        token: str | None = None,
        admin_chat_id: int | str | None = None,
        custom_whitelist: set[str] | None = None,
        custom_blacklist: set[str] | None = None,
        enable_logging: bool = True
    ):
        """
        Initialize the bot.
        
        Args:
            token: Telegram bot token (uses config if not provided)
            admin_chat_id: Chat ID for admin notifications
            custom_whitelist: Additional domains to whitelist
            custom_blacklist: Additional domains to blacklist
            enable_logging: Whether to log to database
        """
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.admin_chat_id = admin_chat_id
        self.enable_logging = enable_logging
        
        # Initialize detection pipeline
        self.pipeline = PhishingDetectionPipeline(
            custom_whitelist=custom_whitelist,
            custom_blacklist=custom_blacklist
        )
        
        # Build application
        self.application = Application.builder().token(self.token).build()
        
        # Initialize handlers
        self._setup_handlers()
        
        logger.info("TelePhisBot initialized successfully")
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        
        # Initialize bot actions
        self.bot_actions = BotActions(
            bot=self.application.bot,
            admin_chat_id=self.admin_chat_id
        )
        
        # Initialize message handler
        self.message_handler = MessageHandler(
            pipeline=self.pipeline,
            actions=self.bot_actions,
            enable_logging=self.enable_logging
        )
        
        # Command handlers
        self.application.add_handler(
            CommandHandler("start", self._cmd_start)
        )
        self.application.add_handler(
            CommandHandler("help", self._cmd_help)
        )
        self.application.add_handler(
            CommandHandler("status", self._cmd_status)
        )
        self.application.add_handler(
            CommandHandler("stats", self._cmd_stats)
        )
        self.application.add_handler(
            CommandHandler("check", self._cmd_check)
        )
        
        # Message handler (for all text messages in groups)
        self.application.add_handler(
            TelegramMessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.message_handler.handle_message
            )
        )
        
        # Handler for messages with captions (photos, videos, documents)
        self.application.add_handler(
            TelegramMessageHandler(
                filters.CAPTION,
                self.message_handler.handle_message
            )
        )
        
        # Handler for forwarded messages
        self.application.add_handler(
            TelegramMessageHandler(
                filters.FORWARDED,
                self.message_handler.handle_message
            )
        )
        
        # Error handler
        self.application.add_error_handler(self._error_handler)
    
    async def _cmd_start(self, update: Update, context):
        """Handle /start command"""
        welcome_text = """
🛡️ **TelePhisDebate Bot**

Selamat datang! Saya adalah bot deteksi phishing berbasis Multi-Agent Debate.

**Fitur:**
• Deteksi real-time pesan phishing
• Analisis multi-tahap (Triage → LLM → MAD)
• Hapus otomatis pesan berbahaya
• Notifikasi admin untuk review

**Commands:**
/help - Bantuan lengkap
/status - Status bot
/stats - Statistik deteksi
/check <pesan> - Cek manual suatu pesan

Bot ini aktif memantau semua pesan di grup ini.
"""
        await update.message.reply_text(welcome_text, parse_mode="Markdown")
    
    async def _cmd_help(self, update: Update, context):
        """Handle /help command"""
        help_text = """
📖 **Panduan TelePhisDebate**

**Cara Kerja:**
1. **Triage** - Filter cepat berbasis aturan
2. **Single-Shot LLM** - Klasifikasi dengan AI
3. **Multi-Agent Debate** - 3 agen AI berdebat untuk kasus ambigu

**Aksi Otomatis:**
• ✅ SAFE - Tidak ada aksi
• ⚠️ SUSPICIOUS - Peringatan
• 🚨 PHISHING - Hapus & notifikasi

**Commands:**
• `/status` - Cek status bot
• `/stats` - Lihat statistik
• `/check <teks>` - Analisis manual

**Untuk Admin:**
Bot memerlukan izin berikut di grup:
• Hapus pesan
• Kirim pesan

**Laporan False Positive:**
Hubungi admin grup jika pesan anda salah dihapus.
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def _cmd_status(self, update: Update, context):
        """Handle /status command - show bot status with DB stats"""
        session_stats = self.message_handler.get_stats()
        
        # Fetch DB stats if logging is enabled
        db_section = ""
        usage_section = ""
        if self.enable_logging:
            try:
                db = get_supabase_client()
                
                # Total messages from database
                msg_count = db.table("messages").select(
                    "id", count="exact"
                ).execute()
                total_db = msg_count.count or 0
                
                # Detection breakdown from DB
                safe_db = db.table("messages").select(
                    "id", count="exact"
                ).eq("classification", "SAFE").execute()
                suspicious_db = db.table("messages").select(
                    "id", count="exact"
                ).eq("classification", "SUSPICIOUS").execute()
                phishing_db = db.table("messages").select(
                    "id", count="exact"
                ).eq("classification", "PHISHING").execute()
                
                db_section = f"""
📦 **Database (All-Time):**
• Total pesan: {total_db}
• Safe: {safe_db.count or 0}
• Suspicious: {suspicious_db.count or 0}
• Phishing: {phishing_db.count or 0}"""
                
                # API usage from api_usage table
                usage = db.table("api_usage").select(
                    "total_tokens_input, total_tokens_output, total_requests"
                ).execute()
                
                if usage.data:
                    total_in = sum(r.get("total_tokens_input", 0) or 0 for r in usage.data)
                    total_out = sum(r.get("total_tokens_output", 0) or 0 for r in usage.data)
                    total_reqs = sum(r.get("total_requests", 0) or 0 for r in usage.data)
                    
                    usage_section = f"""
🧠 **Inference Activity (All-Time):**
• Total requests: {total_reqs:,}
• Input tokens: {total_in:,}
• Output tokens: {total_out:,}"""
                
            except Exception as e:
                logger.warning(f"Could not fetch DB stats: {e}")
                db_section = "\n📦 **Database:** Error fetching stats"
        
        status_text = f"""
🤖 **Status TelePhisBot v{__version__}**

✅ Bot aktif dan berjalan

📊 **Session Stats:**
• Pesan diproses: {session_stats['total_processed']}
• Safe: {session_stats['safe_count']}
• Suspicious: {session_stats['suspicious_count']}
• Phishing: {session_stats['phishing_count']}
• Dihapus: {session_stats['deleted_count']}
{db_section}
{usage_section}

🔧 **Config:**
• Logging: {'Enabled' if self.enable_logging else 'Disabled'}
• Admin notifications: {'Enabled' if self.admin_chat_id else 'Disabled'}
"""
        await update.message.reply_text(status_text, parse_mode="Markdown")
    
    async def _cmd_stats(self, update: Update, context):
        """Handle /stats command - comprehensive detection stats from DB"""
        session_stats = self.message_handler.get_stats()
        
        # Try to get persistent stats from database
        db_stats_text = ""
        if self.enable_logging:
            try:
                db = get_supabase_client()
                
                # Overall counts
                total_msg = db.table("messages").select(
                    "id", count="exact"
                ).execute()
                safe_msg = db.table("messages").select(
                    "id", count="exact"
                ).eq("classification", "SAFE").execute()
                suspicious_msg = db.table("messages").select(
                    "id", count="exact"
                ).eq("classification", "SUSPICIOUS").execute()
                phishing_msg = db.table("messages").select(
                    "id", count="exact"
                ).eq("classification", "PHISHING").execute()
                
                total = total_msg.count or 0
                safe = safe_msg.count or 0
                suspicious = suspicious_msg.count or 0
                phishing = phishing_msg.count or 0
                
                if total > 0:
                    safe_pct = safe / total * 100
                    suspicious_pct = suspicious / total * 100
                    phishing_pct = phishing / total * 100
                else:
                    safe_pct = suspicious_pct = phishing_pct = 0
                
                # Stage breakdown from detection_logs
                triage_count = db.table("detection_logs").select(
                    "id", count="exact"
                ).eq("stage", "triage").execute()
                ss_count = db.table("detection_logs").select(
                    "id", count="exact"
                ).eq("stage", "single_shot").execute()
                mad_count = db.table("detection_logs").select(
                    "id", count="exact"
                ).eq("stage", "mad").execute()
                
                # API usage
                usage = db.table("api_usage").select(
                    "total_tokens_input, total_tokens_output, total_requests"
                ).execute()
                
                total_in = sum(r.get("total_tokens_input", 0) or 0 for r in (usage.data or []))
                total_out = sum(r.get("total_tokens_output", 0) or 0 for r in (usage.data or []))
                total_reqs = sum(r.get("total_requests", 0) or 0 for r in (usage.data or []))
                total_tokens = total_in + total_out
                avg_tokens = total_tokens / total if total > 0 else 0
                
                db_stats_text = f"""
📈 **Statistik Deteksi (Database)**

**Total Diproses:** {total}

**Distribusi:**
```
SAFE:       {safe:>4} ({safe_pct:>5.1f}%)
SUSPICIOUS: {suspicious:>4} ({suspicious_pct:>5.1f}%)
PHISHING:   {phishing:>4} ({phishing_pct:>5.1f}%)
```

**Stage Breakdown:**
• Triage (filtered): {triage_count.count or 0}
• Single-Shot LLM: {ss_count.count or 0}
• Multi-Agent Debate: {mad_count.count or 0}

**Inference Activity:**
• Total requests: {total_reqs:,}
• Input tokens: {total_in:,}
• Output tokens: {total_out:,}
• Avg tokens/msg: {avg_tokens:,.0f}
"""
            except Exception as e:
                logger.warning(f"Could not fetch DB stats: {e}")
                db_stats_text = ""
        
        # Fallback to session stats if no DB data
        if not db_stats_text:
            total = session_stats['total_processed']
            if total > 0:
                safe_pct = session_stats['safe_count'] / total * 100
                suspicious_pct = session_stats['suspicious_count'] / total * 100
                phishing_pct = session_stats['phishing_count'] / total * 100
            else:
                safe_pct = suspicious_pct = phishing_pct = 0
            
            db_stats_text = f"""
📈 **Statistik Deteksi (Session)**

**Total Diproses:** {total}

**Distribusi:**
```
SAFE:       {session_stats['safe_count']:>4} ({safe_pct:>5.1f}%)
SUSPICIOUS: {session_stats['suspicious_count']:>4} ({suspicious_pct:>5.1f}%)
PHISHING:   {session_stats['phishing_count']:>4} ({phishing_pct:>5.1f}%)
```

**Aksi:**
• Pesan dihapus: {session_stats['deleted_count']}
• Detection rate: {session_stats['detection_rate']:.1f}%

**Token:**
• Total tokens: {session_stats['total_tokens']}
• Avg tokens/msg: {session_stats['total_tokens'] / total:.1f if total > 0 else 0}
"""
        
        await update.message.reply_text(db_stats_text, parse_mode="Markdown")
    
    async def _cmd_check(self, update: Update, context):
        """Handle /check command - manual message analysis with URL checking"""
        # Get text to check
        if context.args:
            text_to_check = ' '.join(context.args)
        elif update.message.reply_to_message and update.message.reply_to_message.text:
            text_to_check = update.message.reply_to_message.text
        else:
            await update.message.reply_text(
                "❌ Gunakan: `/check <teks>` atau reply ke pesan dengan `/check`",
                parse_mode="Markdown"
            )
            return
        
        # Send "analyzing" indicator
        status_msg = await update.message.reply_text("🔍 Menganalisis...")
        
        # Check URLs with VirusTotal (async)
        url_checks = await self.message_handler._check_urls_async(text_to_check)
        
        # Run detection with URL checks
        result = self.pipeline.process_message(
            message_text=text_to_check,
            message_id="manual_check",
            url_checks=url_checks
        )
        
        # Delete "analyzing" message
        try:
            await status_msg.delete()
        except Exception:
            pass
        
        # Format result
        emoji = {"SAFE": "✅", "SUSPICIOUS": "⚠️", "PHISHING": "🚨"}.get(result.classification, "❓")
        stage_name = STAGE_NAMES.get(result.decided_by, result.decided_by)
        
        result_text = f"""
{emoji} **Hasil Analisis**

**Teks:**
```
{text_to_check[:200]}{'...' if len(text_to_check) > 200 else ''}
```

**Klasifikasi:** {result.classification}
**Confidence:** {result.confidence:.0%}
**Dianalisis oleh:** {stage_name}
**Waktu:** {result.total_processing_time_ms}ms
**Tokens:** {result.total_tokens_used} (in: {result.tokens_input}, out: {result.tokens_output})

**Rekomendasi:** {result.action.upper()}
"""
        
        # Add triage details
        if result.triage_result:
            flags = result.triage_result.get("triggered_flags", [])
            risk_score = result.triage_result.get("risk_score", 0)
            result_text += f"\n**Triage:** Risk score {risk_score}, Flags: {', '.join(flags) if flags else 'None'}"
        
        # Add URL check details
        if url_checks:
            result_text += "\n\n**URL Analysis:**"
            for url, check in url_checks.items():
                url_display = url[:50] + "..." if len(url) > 50 else url
                is_malicious = check.get("is_malicious", False)
                vt_score = check.get("malicious_count", 0)
                status_icon = "🔴" if is_malicious else "🟢"
                result_text += f"\n{status_icon} `{url_display}` (VT: {vt_score} detections)"
        
        # Add single-shot details
        if result.single_shot_result:
            ss = result.single_shot_result
            reasoning = ss.get("reasoning", "")
            if reasoning:
                result_text += f"\n\n**LLM Reasoning:** {reasoning[:200]}"
        
        # Add MAD details
        if result.mad_result:
            mad = result.mad_result
            votes = mad.get("agent_votes", {})
            if votes:
                result_text += "\n\n**Agent Votes:**"
                for agent, vote in votes.items():
                    agent_label = agent.replace("_", " ").title()
                    result_text += f"\n• {agent_label}: {vote}"
        
        await update.message.reply_text(result_text, parse_mode="Markdown")
    
    async def _error_handler(self, update: Update, context):
        """Handle errors"""
        logger.error(f"Error: {context.error}")
        
        if update and update.message:
            try:
                await update.message.reply_text(
                    "❌ Terjadi error saat memproses pesan. Silakan coba lagi."
                )
            except Exception:
                pass
    
    async def set_commands(self):
        """Set bot commands menu"""
        commands = [
            BotCommand("start", "Mulai bot"),
            BotCommand("help", "Bantuan"),
            BotCommand("status", "Status bot"),
            BotCommand("stats", "Statistik deteksi"),
            BotCommand("check", "Analisis manual pesan")
        ]
        await self.application.bot.set_my_commands(commands)
    
    def run(self):
        """Run the bot (blocking)"""
        logger.info("Starting TelePhisBot...")
        
        # Set commands on startup
        self.application.post_init = lambda app: self.set_commands()
        
        # Run polling
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    
    async def run_async(self):
        """Run the bot asynchronously"""
        logger.info("Starting TelePhisBot (async)...")
        
        await self.application.initialize()
        await self.set_commands()
        await self.application.start()
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    
    async def stop(self):
        """Stop the bot"""
        logger.info("Stopping TelePhisBot...")
        await self.application.stop()
        await self.application.shutdown()
