"""
Base Agent class and individual agent implementations
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.llm import deepseek


@dataclass
class AgentResponse:
    """Response from a single agent"""
    agent_type: str
    stance: str  # PHISHING, SUSPICIOUS, LEGITIMATE
    confidence: float
    key_arguments: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    
    # Metadata
    tokens_input: int = 0
    tokens_output: int = 0
    processing_time_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "agent_type": self.agent_type,
            "stance": self.stance,
            "confidence": self.confidence,
            "key_arguments": self.key_arguments,
            "evidence": self.evidence
        }


class BaseAgent(ABC):
    """Base class for all debate agents"""
    
    def __init__(self):
        self._llm = None
    
    @property
    def llm(self):
        if self._llm is None:
            self._llm = deepseek()
        return self._llm
    
    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Return agent type identifier"""
        pass
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return agent's system prompt"""
        pass
    
    def analyze(
        self,
        message_data: dict,
        context: dict | None = None,
        previous_result: dict | None = None
    ) -> AgentResponse:
        """
        Analyze message and return agent's stance.
        
        Args:
            message_data: Message information
            context: Additional context (baseline, history, etc.)
            previous_result: Result from single-shot stage
            
        Returns:
            AgentResponse with stance and arguments
        """
        prompt = self._construct_prompt(message_data, context, previous_result)
        
        try:
            response = self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=400,
                json_mode=True
            )
            
            content = response["content"]
            if isinstance(content, str):
                content = json.loads(content)
            
            return AgentResponse(
                agent_type=self.agent_type,
                stance=content.get("stance", "SUSPICIOUS"),
                confidence=float(content.get("confidence", 0.5)),
                key_arguments=content.get("key_arguments", []),
                evidence=content.get("evidence", {}),
                tokens_input=response.get("tokens_input", 0),
                tokens_output=response.get("tokens_output", 0),
                processing_time_ms=response.get("processing_time_ms", 0)
            )
            
        except Exception as e:
            return AgentResponse(
                agent_type=self.agent_type,
                stance="SUSPICIOUS",
                confidence=0.5,
                key_arguments=[f"Analysis failed: {str(e)}"],
                evidence={"error": str(e)}
            )
    
    def deliberate(
        self,
        message_data: dict,
        own_response: AgentResponse,
        other_responses: list[AgentResponse],
        context: dict | None = None
    ) -> AgentResponse:
        """
        Round 2: Reconsider stance after seeing other agents' arguments.
        
        Args:
            message_data: Original message data
            own_response: This agent's Round 1 response
            other_responses: Other agents' Round 1 responses
            context: Additional context
            
        Returns:
            Updated AgentResponse (may change stance)
        """
        prompt = self._construct_deliberation_prompt(
            message_data, own_response, other_responses, context
        )
        
        try:
            response = self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400,
                json_mode=True
            )
            
            content = response["content"]
            if isinstance(content, str):
                content = json.loads(content)
            
            return AgentResponse(
                agent_type=self.agent_type,
                stance=content.get("stance", own_response.stance),
                confidence=float(content.get("confidence", own_response.confidence)),
                key_arguments=content.get("key_arguments", own_response.key_arguments),
                evidence=content.get("evidence", own_response.evidence),
                tokens_input=response.get("tokens_input", 0),
                tokens_output=response.get("tokens_output", 0),
                processing_time_ms=response.get("processing_time_ms", 0)
            )
            
        except Exception:
            return own_response  # Keep original stance on error
    
    @abstractmethod
    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None
    ) -> str:
        """Construct analysis prompt"""
        pass
    
    def _construct_deliberation_prompt(
        self,
        message_data: dict,
        own_response: AgentResponse,
        other_responses: list[AgentResponse],
        context: dict | None
    ) -> str:
        """Construct deliberation prompt for Round 2"""
        parts = ["=== Round 2: Deliberasi ===\n"]
        
        # Original message
        parts.append(f"Pesan yang dianalisis: \"{message_data.get('content', '')}\"")
        parts.append("")
        
        # Own analysis
        parts.append("Analisis Anda di Round 1:")
        parts.append(f"- Stance: {own_response.stance}")
        parts.append(f"- Confidence: {own_response.confidence:.0%}")
        parts.append(f"- Argumen: {own_response.key_arguments}")
        parts.append("")
        
        # Other agents' analyses
        parts.append("Analisis Agent Lain:")
        for resp in other_responses:
            parts.append(f"\n[{resp.agent_type}]")
            parts.append(f"- Stance: {resp.stance}")
            parts.append(f"- Confidence: {resp.confidence:.0%}")
            parts.append(f"- Argumen: {resp.key_arguments}")
        
        parts.append("")
        parts.append("Pertimbangkan argumen agent lain. Apakah ada blind spot dalam analisis Anda?")
        parts.append("Anda boleh mempertahankan atau mengubah stance jika ada bukti kuat.")
        parts.append("")
        parts.append("Output JSON dengan format yang sama.")
        
        return "\n".join(parts)


class ContentAnalyzer(BaseAgent):
    """
    Agent 1: Content Analyzer
    Focuses on linguistic patterns, behavioral deviation, and social engineering tactics
    """
    
    @property
    def agent_type(self) -> str:
        return "content_analyzer"
    
    @property
    def system_prompt(self) -> str:
        return """Kamu adalah Content Analyzer agent dalam sistem deteksi phishing.

Peran: Menganalisis konten pesan, pola linguistik, dan deviasi perilaku.

Fokus analisis:
1. Konsistensi gaya bahasa dengan baseline pengguna
2. Taktik social engineering (urgensi, otoritas palsu, ketakutan)
3. Relevansi konteks dengan aktivitas akademik grup
4. Anomali struktur dan format pesan
5. Penggunaan bahasa Indonesia yang tidak wajar

Output JSON:
{
  "stance": "PHISHING" | "SUSPICIOUS" | "LEGITIMATE",
  "confidence": 0.0-1.0,
  "key_arguments": ["argumen1", "argumen2", ...],
  "evidence": {
    "style_deviation": 0.0-1.0,
    "urgency_score": 0.0-1.0,
    "social_engineering_detected": true/false,
    "linguistic_anomalies": ["anomali1", ...]
  }
}"""
    
    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None
    ) -> str:
        parts = ["=== Analisis Konten Pesan ===\n"]
        
        # Message content
        parts.append(f"Pesan: \"{message_data.get('content', '')}\"")
        parts.append(f"Panjang: {message_data.get('length', 0)} karakter")
        parts.append(f"Waktu: {message_data.get('timestamp', 'unknown')}")
        parts.append("")
        
        # Sender info
        sender = message_data.get('sender', {})
        if sender:
            parts.append("Pengirim:")
            parts.append(f"- Username: @{sender.get('username', 'unknown')}")
        
        # Baseline if available
        baseline = context.get('baseline', {}) if context else {}
        if baseline and baseline.get('total_messages', 0) > 0:
            parts.append("\nBaseline Pengguna:")
            parts.append(f"- Rata-rata panjang pesan: {baseline.get('avg_message_length', 'N/A')}")
            parts.append(f"- Emoji usage rate: {baseline.get('emoji_usage_rate', 0):.2%}")
            parts.append(f"- Total pesan historis: {baseline.get('total_messages', 0)}")
        
        # Previous stage result
        if previous_result:
            parts.append("\nHasil Single-Shot LLM:")
            parts.append(f"- Classification: {previous_result.get('classification', 'N/A')}")
            parts.append(f"- Confidence: {previous_result.get('confidence', 0):.0%}")
            parts.append(f"- Risk factors: {previous_result.get('risk_factors', [])}")
        
        # Triage flags
        triage = message_data.get('triage', {})
        if triage:
            parts.append("\nTriage Flags:")
            parts.append(f"- Risk score: {triage.get('risk_score', 0)}")
            parts.append(f"- Triggered: {triage.get('triggered_flags', [])}")
        
        parts.append("\nAnalisis konten pesan ini dan berikan stance Anda.")
        
        return "\n".join(parts)


class SecurityValidator(BaseAgent):
    """
    Agent 2: Security Validator
    Focuses on URL analysis, domain reputation, and external security evidence
    """
    
    @property
    def agent_type(self) -> str:
        return "security_validator"
    
    @property
    def system_prompt(self) -> str:
        return """Kamu adalah Security Validator agent dalam sistem deteksi phishing.

Peran: Memverifikasi URL, reputasi domain, dan bukti keamanan eksternal.

Fokus analisis:
1. Struktur URL (obfuscation, patterns mencurigakan)
2. Reputasi domain berdasarkan data yang tersedia
3. Verifikasi tujuan link
4. Kecocokan dengan database phishing historis
5. HTTPS vs HTTP, TLD analysis

Output JSON:
{
  "stance": "PHISHING" | "SUSPICIOUS" | "LEGITIMATE",
  "confidence": 0.0-1.0,
  "key_arguments": ["argumen1", "argumen2", ...],
  "evidence": {
    "url_risk_score": 0.0-1.0,
    "domain_trusted": true/false,
    "is_shortened": true/false,
    "tld_suspicious": true/false,
    "security_checks": {"check1": "result", ...}
  }
}"""
    
    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None
    ) -> str:
        parts = ["=== Validasi Keamanan URL ===\n"]
        
        # Message content
        parts.append(f"Pesan: \"{message_data.get('content', '')}\"")
        parts.append("")
        
        # URLs found
        urls = message_data.get('urls', [])
        if urls:
            parts.append("URLs ditemukan:")
            for url in urls:
                parts.append(f"  - {url}")
        else:
            parts.append("URLs: Tidak ada URL ditemukan")
        
        # URL analysis from triage
        triage = message_data.get('triage', {})
        if triage:
            parts.append("\nAnalisis URL (Triage):")
            parts.append(f"- Whitelisted URLs: {triage.get('whitelisted_urls', [])}")
            parts.append(f"- Risk score: {triage.get('risk_score', 0)}")
            
            triggered = triage.get('triggered_flags', [])
            url_flags = [f for f in triggered if 'url' in f or 'tld' in f or 'domain' in f]
            if url_flags:
                parts.append(f"- URL-related flags: {url_flags}")
        
        # External checks if available (VirusTotal, etc.)
        url_checks = context.get('url_checks', {}) if context else {}
        if url_checks:
            parts.append("\n=== Hasil VirusTotal ===")
            for url, result in url_checks.items():
                parts.append(f"\nURL: {url}")
                if isinstance(result, dict):
                    is_malicious = result.get('is_malicious', False)
                    risk_score = result.get('risk_score', 0)
                    source = result.get('source', 'unknown')
                    details = result.get('details', {})
                    
                    status = "⚠️ BERBAHAYA" if is_malicious else "✅ AMAN"
                    parts.append(f"  Status: {status}")
                    parts.append(f"  Risk Score: {risk_score:.2f}")
                    parts.append(f"  Source: {source}")
                    
                    if details:
                        if 'malicious' in details:
                            parts.append(f"  Engines deteksi malicious: {details.get('malicious', 0)}/{details.get('total_engines', 0)}")
                        if 'suspicious' in details:
                            parts.append(f"  Engines deteksi suspicious: {details.get('suspicious', 0)}")
                        if 'reputation' in details:
                            parts.append(f"  Reputation score: {details.get('reputation', 0)}")
                        if 'risk_factors' in details:
                            parts.append(f"  Risk factors: {', '.join(details['risk_factors'])}")
                else:
                    parts.append(f"  Result: {result}")
        
        # Previous stage
        if previous_result:
            parts.append("\nHasil Single-Shot LLM:")
            parts.append(f"- Classification: {previous_result.get('classification', 'N/A')}")
            parts.append(f"- Confidence: {previous_result.get('confidence', 0):.0%}")
        
        parts.append("\nAnalisis keamanan URL dan berikan stance Anda.")
        
        return "\n".join(parts)


class SocialContextEvaluator(BaseAgent):
    """
    Agent 3: Social Context Evaluator
    Focuses on social dynamics, user history, and academic context relevance
    """
    
    @property
    def agent_type(self) -> str:
        return "social_context"
    
    @property
    def system_prompt(self) -> str:
        return """Kamu adalah Social Context Evaluator agent dalam sistem deteksi phishing.

Peran: Mengevaluasi konteks sosial dan perilaku khusus untuk grup akademik.

Fokus analisis:
1. Pola perilaku historis pengirim
2. Kesesuaian waktu posting
3. Relevansi dengan aktivitas akademik yang sedang berlangsung
4. Dinamika sosial dalam grup mahasiswa
5. Apakah konten masuk akal untuk konteks akademik

Output JSON:
{
  "stance": "PHISHING" | "SUSPICIOUS" | "LEGITIMATE",
  "confidence": 0.0-1.0,
  "key_arguments": ["argumen1", "argumen2", ...],
  "evidence": {
    "behavior_anomaly_score": 0.0-1.0,
    "context_relevance": 0.0-1.0,
    "timing_appropriate": true/false,
    "academic_context_match": true/false
  }
}"""
    
    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None
    ) -> str:
        parts = ["=== Evaluasi Konteks Sosial ===\n"]
        
        # Message content
        parts.append(f"Pesan: \"{message_data.get('content', '')}\"")
        parts.append(f"Waktu: {message_data.get('timestamp', 'unknown')}")
        parts.append("")
        
        # Sender info and history
        sender = message_data.get('sender', {})
        parts.append("Pengirim:")
        parts.append(f"- Username: @{sender.get('username', 'unknown')}")
        if sender.get('joined_group_at'):
            parts.append(f"- Bergabung: {sender.get('joined_group_at')}")
        
        # Baseline behavior
        baseline = context.get('baseline', {}) if context else {}
        if baseline and baseline.get('total_messages', 0) > 0:
            parts.append("\nRiwayat Perilaku:")
            parts.append(f"- Total pesan: {baseline.get('total_messages', 0)}")
            parts.append(f"- URL sharing rate: {baseline.get('url_sharing_rate', 0):.2%}")
            
            typical_hours = baseline.get('typical_hours', [])
            if typical_hours:
                parts.append(f"- Jam aktif tipikal: {min(typical_hours)}:00 - {max(typical_hours)}:00")
        else:
            parts.append("\nRiwayat Perilaku: Tidak cukup data baseline")
        
        # Recent context
        recent = context.get('recent_topics', []) if context else []
        if recent:
            parts.append(f"\nTopik grup terkini: {recent}")
        
        # Behavioral anomalies
        triage = message_data.get('triage', {})
        triggered = triage.get('triggered_flags', [])
        behavioral_flags = [f for f in triggered if 'anomaly' in f or 'first_time' in f]
        if behavioral_flags:
            parts.append(f"\nAnomali perilaku terdeteksi: {behavioral_flags}")
        
        # Previous stage
        if previous_result:
            parts.append("\nHasil Single-Shot LLM:")
            parts.append(f"- Classification: {previous_result.get('classification', 'N/A')}")
            parts.append(f"- Confidence: {previous_result.get('confidence', 0):.0%}")
        
        parts.append("\nKonteks: Grup mahasiswa Teknik Informatika UIR")
        parts.append("Evaluasi apakah pesan ini sesuai dengan konteks sosial dan berikan stance Anda.")
        
        return "\n".join(parts)
