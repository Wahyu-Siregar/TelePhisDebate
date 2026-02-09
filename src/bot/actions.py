"""
Bot Actions Module
Handles bot responses: warn, notify admin, flag for review
"""

import asyncio
from datetime import datetime
from telegram import Bot, Message
from telegram.constants import ParseMode
from telegram.error import TelegramError

from src.detection.pipeline import DetectionResult

# Friendly stage names
STAGE_DISPLAY = {
    "triage": "Rule-Based Triage",
    "single_shot": "Single-Shot LLM",
    "mad": "Multi-Agent Debate (3 Agents)",
}

# DeepSeek API pricing
COST_PER_INPUT_TOKEN = 0.28 / 1_000_000
COST_PER_OUTPUT_TOKEN = 0.42 / 1_000_000


class BotActions:
    """
    Handles bot actions based on detection results.
    
    Actions:
    - none: Do nothing (SAFE messages)
    - warn: Reply with warning (SUSPICIOUS with high confidence)
    - flag_review: Notify admin for manual review (PHISHING & low-conf SUSPICIOUS)
    
    NOTE: Bot does NOT auto-delete messages. All PHISHING results are flagged
    for admin review. Admin can manually delete confirmed phishing.
    """
    
    # Warning message templates (using HTML for better compatibility)
    TEMPLATES = {
        "phishing_alert": """🚨 <b>PERINGATAN PHISHING TERDETEKSI</b> 🚨

⚠️ Pesan dari @{username} terindikasi sebagai <b>PHISHING</b>!

🔍 <b>Detail Analisis:</b>
• Confidence: {confidence:.0%}
• Dianalisis oleh: {stage}
• Risk Factors: {risk_factors}

⛔ <b>JANGAN KLIK LINK APAPUN</b> dalam pesan tersebut!

📢 Admin telah diberitahu untuk review.
Jika ini kesalahan, hubungi admin grup.""",
        
        "suspicious_warning": """⚠️ <b>Peringatan: Pesan Mencurigakan</b>

Pesan dari @{username} ditandai sebagai mencurigakan.

🔍 <b>Perhatian:</b>
- Jangan klik link sebelum dikonfirmasi aman
- Admin akan review pesan ini

Confidence: {confidence:.0%}""",
        
        "admin_notification": """🔔 <b>Review Diperlukan</b>

📩 <b>Pesan dari:</b> @{username} ({user_id})
📅 <b>Waktu:</b> {timestamp}
💬 <b>Group:</b> {group_name}

📝 <b>Isi Pesan:</b>
<code>{message_text}</code>

🔍 <b>Hasil Analisis:</b>
- Classification: {classification}
- Confidence: {confidence:.0%}
- Stage: {stage}
- Action: {action}

⚡ <b>Performance:</b>
- Processing: {processing_time}ms
- Tokens: {tokens_total} (in: {tokens_in}, out: {tokens_out})
- Est. cost: ${cost:.6f}

{stage_details}

🔗 <b>Link ke Pesan:</b> {message_link}"""
    }
    
    # Auto-delete warning after this many seconds
    WARNING_AUTO_DELETE_SECONDS = 120
    
    def __init__(self, bot: Bot, admin_chat_id: int | str | None = None):
        """
        Initialize bot actions.
        
        Args:
            bot: Telegram Bot instance
            admin_chat_id: Chat ID to send admin notifications
        """
        self.bot = bot
        self.admin_chat_id = admin_chat_id
    
    async def execute_action(
        self,
        message: Message,
        result: DetectionResult,
        group_name: str = "Unknown Group"
    ) -> dict:
        """
        Execute appropriate action based on detection result.
        
        Args:
            message: Original Telegram message
            result: Detection pipeline result
            group_name: Name of the group
            
        Returns:
            Dict with action details and success status
        """
        action = result.action
        
        action_result = {
            "action": action,
            "success": True,
            "message_deleted": False,
            "warning_sent": False,
            "admin_notified": False,
            "error": None
        }
        
        try:
            if action == "none":
                # Safe message, no action needed
                pass
                
            elif action == "warn":
                # Send warning reply
                action_result = await self._handle_warn(message, result)
                
            elif action == "flag_review":
                # Notify admin for manual review (includes PHISHING)
                action_result = await self._handle_flag_review(message, result, group_name)
                
        except TelegramError as e:
            action_result["success"] = False
            action_result["error"] = str(e)
        
        return action_result
    
    async def _handle_warn(
        self,
        message: Message,
        result: DetectionResult
    ) -> dict:
        """Send warning reply for suspicious message"""
        action_result = {
            "action": "warn",
            "success": True,
            "message_deleted": False,
            "warning_sent": False,
            "admin_notified": False,
            "error": None
        }
        
        username = message.from_user.username or message.from_user.first_name
        
        try:
            warning_text = self.TEMPLATES["suspicious_warning"].format(
                username=username,
                confidence=result.confidence
            )
            
            await message.reply_text(
                text=warning_text,
                parse_mode=ParseMode.HTML
            )
            action_result["warning_sent"] = True
            
        except TelegramError as e:
            action_result["success"] = False
            action_result["error"] = str(e)
        
        return action_result
    
    async def _handle_flag_review(
        self,
        message: Message,
        result: DetectionResult,
        group_name: str
    ) -> dict:
        """Flag message for admin review - send alert in group AND notify admin"""
        action_result = {
            "action": "flag_review",
            "success": True,
            "message_deleted": False,
            "warning_sent": False,
            "admin_notified": False,
            "error": None
        }
        
        username = message.from_user.username or message.from_user.first_name
        
        # Get risk factors for alert
        risk_factors = []
        if result.triage_result:
            risk_factors = result.triage_result.get("triggered_flags", [])
        
        # STEP 1: Send alert in GROUP (reply to the suspicious message)
        if result.classification == "PHISHING":
            try:
                alert_text = self.TEMPLATES["phishing_alert"].format(
                    username=username,
                    confidence=result.confidence,
                    stage=STAGE_DISPLAY.get(result.decided_by, result.decided_by),
                    risk_factors=", ".join(risk_factors) if risk_factors else "Suspicious patterns detected"
                )
                
                warning_msg = await message.reply_text(
                    text=alert_text,
                    parse_mode=ParseMode.HTML
                )
                action_result["warning_sent"] = True
                
                # Schedule auto-delete of warning after 10 minutes
                asyncio.create_task(
                    self._auto_delete_message(warning_msg, 600)
                )
                
            except TelegramError as e:
                action_result["error"] = f"Could not send group alert: {e}"
        
        # STEP 2: Notify admin for manual review/deletion
        if self.admin_chat_id:
            # Build stage details
            stage_details = self._format_stage_details(result)
            
            # Build message link
            if message.chat.username:
                message_link = f"https://t.me/{message.chat.username}/{message.message_id}"
            else:
                message_link = f"https://t.me/c/{str(message.chat_id)[4:]}/{message.message_id}"
            
            try:
                # Calculate cost for this detection
                cost = (result.tokens_input * COST_PER_INPUT_TOKEN) + \
                       (result.tokens_output * COST_PER_OUTPUT_TOKEN)
                
                notification_text = self.TEMPLATES["admin_notification"].format(
                    username=username,
                    user_id=message.from_user.id,
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    group_name=group_name,
                    message_text=message.text[:500] if message.text else "[No text]",
                    classification=result.classification,
                    confidence=result.confidence,
                    stage=STAGE_DISPLAY.get(result.decided_by, result.decided_by),
                    action="⚠️ WAITING ADMIN REVIEW",
                    processing_time=result.total_processing_time_ms,
                    tokens_total=result.total_tokens_used,
                    tokens_in=result.tokens_input,
                    tokens_out=result.tokens_output,
                    cost=cost,
                    stage_details=stage_details,
                    message_link=message_link
                )
                
                await self.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=notification_text,
                    parse_mode=ParseMode.HTML
                )
                action_result["admin_notified"] = True
                
            except TelegramError as e:
                if not action_result["error"]:
                    action_result["error"] = f"Could not notify admin: {e}"
        else:
            if not action_result["error"]:
                action_result["error"] = "No admin chat ID configured"
        
        return action_result
    
    def _format_stage_details(self, result: DetectionResult) -> str:
        """Format detailed stage information for admin"""
        details = []
        
        if result.triage_result:
            triage = result.triage_result
            flags = triage.get("triggered_flags", [])
            details.append(f"📋 <b>Triage:</b> {triage.get('classification')} (risk: {triage.get('risk_score', 0)})")
            if flags:
                details.append(f"   Flags: {', '.join(flags)}")
        
        if result.single_shot_result:
            ss = result.single_shot_result
            details.append(f"🤖 <b>Single-Shot LLM:</b> {ss.get('classification')} ({ss.get('confidence', 0):.0%})")
            if ss.get('reasoning'):
                details.append(f"   Reason: {str(ss['reasoning'])[:150]}")
        
        if result.mad_result:
            mad = result.mad_result
            details.append(f"🗣️ <b>Multi-Agent Debate:</b> {mad.get('decision')} ({mad.get('confidence', 0):.0%})")
            votes = mad.get('agent_votes', {})
            if votes:
                vote_strs = [f"{k.replace('_', ' ').title()}: {v}" for k, v in votes.items()]
                details.append(f"   Votes: {' | '.join(vote_strs)}")
        
        return "\n".join(details) if details else "No details available"
    
    async def _auto_delete_message(self, message: Message, delay_seconds: int):
        """Auto-delete a message after delay"""
        await asyncio.sleep(delay_seconds)
        try:
            await message.delete()
        except TelegramError:
            pass  # Message might already be deleted
