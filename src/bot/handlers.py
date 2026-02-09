"""
Message Handler Module
Processes incoming Telegram messages through the detection pipeline
"""

import asyncio
import logging
from datetime import datetime, date
from telegram import Update, Message
from telegram.ext import ContextTypes

from src.config import config
from src.detection import PhishingDetectionPipeline, DetectionResult
from src.detection.url_checker import check_urls_external_async
from src.database.client import get_supabase_client
from .actions import BotActions

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    Handles incoming Telegram messages and runs detection pipeline.
    
    Features:
    - Filters out bot messages and commands
    - Extracts message features for analysis
    - Runs detection pipeline
    - Executes appropriate actions
    - Logs results to database
    """
    
    def __init__(
        self,
        pipeline: PhishingDetectionPipeline,
        actions: BotActions,
        enable_logging: bool = True
    ):
        """
        Initialize message handler.
        
        Args:
            pipeline: Detection pipeline instance
            actions: Bot actions handler
            enable_logging: Whether to log to database
        """
        self.pipeline = pipeline
        self.actions = actions
        self.enable_logging = enable_logging
        self.db = get_supabase_client() if enable_logging else None
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "safe_count": 0,
            "suspicious_count": 0,
            "phishing_count": 0,
            "deleted_count": 0,
            "total_tokens": 0
        }
    
    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Main message handler for Telegram bot.
        
        Args:
            update: Telegram update object
            context: Bot context
        """
        message = update.message
        
        # Skip if no message
        if not message:
            return
        
        # Get text content (from text, caption, or forwarded message)
        text_content = self._extract_text_content(message)
        
        # Skip if no text content
        if not text_content:
            return
        
        # Skip bot messages
        if message.from_user and message.from_user.is_bot:
            return
        
        # Skip commands
        if text_content.startswith('/'):
            return
        
        # Skip very short messages (unlikely to be phishing)
        if len(text_content) < 10:
            return
        
        # Process message
        await self._process_message(message, context, text_content)
    
    def _extract_text_content(self, message: Message) -> str | None:
        """
        Extract text content from message.
        Handles: regular text, captions, forwarded messages
        """
        # Regular text message
        if message.text:
            return message.text
        
        # Caption (for photos, videos, documents with caption)
        if message.caption:
            return message.caption
        
        return None
    
    async def _process_message(
        self,
        message: Message,
        context: ContextTypes.DEFAULT_TYPE,
        text_content: str | None = None
    ):
        """Process a single message through detection pipeline"""
        
        # Use provided text or extract from message
        if text_content is None:
            text_content = self._extract_text_content(message)
        
        if not text_content:
            return
        
        # Extract sender info
        sender_info = self._extract_sender_info(message)
        
        # Check if this is a forwarded message (python-telegram-bot v21+)
        if message.forward_origin:
            sender_info["is_forwarded"] = True
            # Try to get original sender info
            try:
                if hasattr(message.forward_origin, 'sender_user') and message.forward_origin.sender_user:
                    sender_info["original_sender"] = message.forward_origin.sender_user.username or message.forward_origin.sender_user.first_name
                elif hasattr(message.forward_origin, 'sender_user_name'):
                    sender_info["original_sender"] = message.forward_origin.sender_user_name
            except Exception:
                pass
        
        # Get user baseline from database (if available)
        baseline_metrics = await self._get_user_baseline(message.from_user.id)
        
        # Ensure user is registered in the database
        if self.enable_logging:
            await self._ensure_user_registered(message.from_user, message.chat_id)
        
        # Extract URLs and check them asynchronously with VirusTotal
        url_checks = await self._check_urls_async(text_content)
        
        # Run detection pipeline
        result = self.pipeline.process_message(
            message_text=text_content,
            message_id=str(message.message_id),
            message_timestamp=message.date,
            sender_info=sender_info,
            baseline_metrics=baseline_metrics,
            url_checks=url_checks  # Pass pre-computed URL checks
        )
        
        # Update statistics
        self._update_stats(result)
        
        # Execute action based on result
        group_name = message.chat.title or "Private Chat"
        action_result = await self.actions.execute_action(
            message=message,
            result=result,
            group_name=group_name
        )
        
        # Log to database
        if self.enable_logging:
            await self._log_detection(message, result, action_result)
        
        # Update deleted count
        if action_result.get("message_deleted"):
            self.stats["deleted_count"] += 1
    
    def _extract_sender_info(self, message: Message) -> dict:
        """Extract sender information from message"""
        user = message.from_user
        
        return {
            "user_id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_bot": user.is_bot,
            "is_premium": getattr(user, 'is_premium', False),
            "language_code": user.language_code or "id"
        }
    
    async def _get_user_baseline(self, user_id: int) -> dict | None:
        """Get user baseline metrics from database"""
        if not self.db:
            return None
        
        try:
            response = self.db.table("users").select(
                "baseline_metrics"
            ).eq("telegram_user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0].get("baseline_metrics")
        except Exception:
            pass
        
        return None
    
    async def _ensure_user_registered(self, user, chat_id: int):
        """
        Register or update user in the users table.
        Tracks basic info and updates last_seen timestamp.
        """
        if not self.db:
            return
        
        try:
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            
            # Check if user exists
            existing = self.db.table("users").select("id").eq(
                "telegram_user_id", user_id
            ).execute()
            
            now = datetime.now().isoformat()
            
            if existing.data and len(existing.data) > 0:
                # Update last_seen
                self.db.table("users").update({
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "last_seen": now
                }).eq("telegram_user_id", user_id).execute()
            else:
                # Insert new user
                self.db.table("users").insert({
                    "telegram_user_id": user_id,
                    "telegram_chat_id": chat_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "last_seen": now,
                    "baseline_metrics": {}
                }).execute()
                logger.info(f"New user registered: @{username} ({user_id})")
        except Exception as e:
            logger.debug(f"User registration skipped: {e}")
    
    async def _check_urls_async(self, text_content: str) -> dict | None:
        """
        Extract URLs from text and check them with VirusTotal.
        Runs asynchronously to not block the bot.
        
        Returns:
            dict mapping URL to check results, or None if no URLs/error
        """
        import re
        
        # Extract URLs from text
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text_content)
        
        if not urls:
            return None
        
        try:
            logger.info(f"Checking {len(urls)} URLs with VirusTotal...")
            url_checks = await check_urls_external_async(urls)
            
            if url_checks:
                # Log summary
                malicious_count = sum(1 for r in url_checks.values() if r.get('is_malicious'))
                logger.info(f"URL check complete: {malicious_count}/{len(urls)} flagged as malicious")
            
            return url_checks
        except Exception as e:
            logger.error(f"URL check failed: {e}")
            return None
    
    def _update_stats(self, result: DetectionResult):
        """Update handler statistics"""
        self.stats["total_processed"] += 1
        self.stats["total_tokens"] += result.total_tokens_used
        
        if result.classification == "SAFE":
            self.stats["safe_count"] += 1
        elif result.classification == "SUSPICIOUS":
            self.stats["suspicious_count"] += 1
        elif result.classification == "PHISHING":
            self.stats["phishing_count"] += 1
    
    async def _log_detection(
        self,
        message: Message,
        result: DetectionResult,
        action_result: dict
    ):
        """Log detection result to database"""
        if not self.db:
            return
        
        try:
            # Get text content
            text_content = self._extract_text_content(message)
            
            # Log to messages table
            message_data = {
                "telegram_message_id": message.message_id,
                "telegram_chat_id": message.chat_id,
                "content": text_content[:1000] if text_content else "",
                "content_length": len(text_content) if text_content else 0,
                "timestamp": message.date.isoformat() if message.date else datetime.now().isoformat(),
                "urls_extracted": result.triage_result.get("urls_found", []) if result.triage_result else [],
                "classification": result.classification,
                "confidence": result.confidence,
                "decided_by": result.decided_by,
                "processing_time_ms": result.total_processing_time_ms,
                "action_taken": action_result.get("action")
            }
            
            # Insert message and get the ID
            msg_result = self.db.table("messages").insert(message_data).execute()
            
            # Get the inserted message ID for detection_logs foreign key
            inserted_msg_id = msg_result.data[0]["id"] if msg_result.data else None
            
            # Log to detection_logs table
            log_data = {
                "message_id": inserted_msg_id,
                "stage": result.decided_by,
                "stage_result": {
                    "triage": result.triage_result,
                    "single_shot": result.single_shot_result,
                    "mad": result.mad_result
                },
                "tokens_input": result.tokens_input,
                "tokens_output": result.tokens_output,
                "processing_time_ms": result.total_processing_time_ms
            }
            
            self.db.table("detection_logs").insert(log_data).execute()
            
            # Log to api_usage table for cost tracking
            if result.total_tokens_used > 0:
                await self._log_api_usage(result)
            
        except Exception as e:
            # Log error but don't fail the handler
            print(f"[DB Error] Could not log detection: {e}")
    
    async def _log_api_usage(self, result: DetectionResult):
        """
        Log API token usage and estimated cost to api_usage table.
        
        DeepSeek API Pricing (as of 2026):
        - Input tokens (cache miss): $0.28 / 1M tokens
        - Input tokens (cache hit):  $0.028 / 1M tokens  
        - Output tokens:             $0.42 / 1M tokens
        
        We use cache miss pricing as conservative estimate.
        """
        if not self.db:
            return
        
        # DeepSeek pricing per token (cache miss)
        COST_PER_INPUT_TOKEN = 0.28 / 1_000_000   # $0.28 per 1M tokens
        COST_PER_OUTPUT_TOKEN = 0.42 / 1_000_000   # $0.42 per 1M tokens
        
        tokens_in = result.tokens_input
        tokens_out = result.tokens_output
        estimated_cost = (tokens_in * COST_PER_INPUT_TOKEN) + (tokens_out * COST_PER_OUTPUT_TOKEN)
        
        today = date.today().isoformat()
        stage = result.decided_by  # "triage", "single_shot", or "mad"
        
        try:
            # Try to update existing record for today
            existing = self.db.table("api_usage").select("*").eq(
                "date", today
            ).execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing record for today
                record = existing.data[0]
                update_data = {
                    "total_tokens_input": (record.get("total_tokens_input", 0) or 0) + tokens_in,
                    "total_tokens_output": (record.get("total_tokens_output", 0) or 0) + tokens_out,
                    "estimated_cost_usd": round(
                        float(record.get("estimated_cost_usd", 0) or 0) + estimated_cost, 6
                    ),
                    "total_requests": (record.get("total_requests", 0) or 0) + 1,
                    "updated_at": datetime.now().isoformat()
                }
                
                # Increment stage-specific counters
                if stage == "triage":
                    update_data["triage_requests"] = (record.get("triage_requests", 0) or 0) + 1
                elif stage == "single_shot":
                    update_data["single_shot_requests"] = (record.get("single_shot_requests", 0) or 0) + 1
                    update_data["single_shot_tokens"] = (record.get("single_shot_tokens", 0) or 0) + tokens_in + tokens_out
                elif stage == "mad":
                    update_data["mad_requests"] = (record.get("mad_requests", 0) or 0) + 1
                    update_data["mad_tokens"] = (record.get("mad_tokens", 0) or 0) + tokens_in + tokens_out
                
                self.db.table("api_usage").update(update_data).eq("date", today).execute()
            else:
                # Insert new record for today
                insert_data = {
                    "date": today,
                    "total_tokens_input": tokens_in,
                    "total_tokens_output": tokens_out,
                    "estimated_cost_usd": round(estimated_cost, 6),
                    "total_requests": 1,
                    "triage_requests": 1 if stage == "triage" else 0,
                    "single_shot_requests": 1 if stage == "single_shot" else 0,
                    "single_shot_tokens": (tokens_in + tokens_out) if stage == "single_shot" else 0,
                    "mad_requests": 1 if stage == "mad" else 0,
                    "mad_tokens": (tokens_in + tokens_out) if stage == "mad" else 0
                }
                self.db.table("api_usage").insert(insert_data).execute()
        except Exception as e:
            print(f"[DB Error] Could not log API usage: {e}")
    
    def get_stats(self) -> dict:
        """Get current handler statistics"""
        return {
            **self.stats,
            "detection_rate": (
                (self.stats["suspicious_count"] + self.stats["phishing_count"]) / 
                self.stats["total_processed"] * 100
                if self.stats["total_processed"] > 0 else 0
            )
        }
    
    def reset_stats(self):
        """Reset handler statistics"""
        self.stats = {
            "total_processed": 0,
            "safe_count": 0,
            "suspicious_count": 0,
            "phishing_count": 0,
            "deleted_count": 0,
            "total_tokens": 0
        }
