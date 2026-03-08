"""
Base Agent class and individual agent implementations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.llm import deepseek
from src.llm.json_utils import parse_json_object


def _is_fatal_llm_error(exc: Exception) -> bool:
    """
    Detect non-recoverable LLM errors (usually misconfiguration).

    If these happen, silently defaulting to SUSPICIOUS will poison evaluations.
    """
    name = exc.__class__.__name__
    msg = str(exc)
    fatal_markers = ("NotFoundError", "AuthenticationError", "PermissionDeniedError")
    if name in fatal_markers:
        return True
    return any(m in msg for m in fatal_markers)


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
            "evidence": self.evidence,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "processing_time_ms": self.processing_time_ms,
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
            
            content = parse_json_object(response.get("content"))

            # If parsing yields nothing, capture a short raw excerpt for debugging/evaluation.
            if not content:
                raw = response.get("content")
                if isinstance(raw, str) and raw.strip():
                    content = {"evidence": {"raw_excerpt": raw.strip()[:240]}}
            else:
                # If the model returned a dict but omitted most fields, keep an excerpt anyway.
                stance_missing = "stance" not in content
                confidence_missing = "confidence" not in content
                if stance_missing or confidence_missing:
                    raw = response.get("raw_content") or response.get("content")
                    if isinstance(raw, str) and raw.strip():
                        content.setdefault("evidence", {})
                        if isinstance(content["evidence"], dict) and "raw_excerpt" not in content["evidence"]:
                            content["evidence"]["raw_excerpt"] = raw.strip()[:240]

            key_arguments = self._normalize_arguments(content.get("key_arguments", []))
            if not key_arguments:
                evidence_obj = content.get("evidence", {})
                raw_excerpt = evidence_obj.get("raw_excerpt") if isinstance(evidence_obj, dict) else None
                if isinstance(raw_excerpt, str) and raw_excerpt.strip():
                    key_arguments = [f"Raw model output tidak terstruktur: {raw_excerpt.strip()[:220]}..."]
                else:
                    key_arguments = ["Model tidak mengembalikan key_arguments terstruktur."]
            
            return AgentResponse(
                agent_type=self.agent_type,
                stance=self._normalize_stance(
                    content.get("stance", content.get("classification")),
                    default="SUSPICIOUS",
                ),
                confidence=self._normalize_confidence(content.get("confidence", 0.5), default=0.5),
                key_arguments=key_arguments,
                evidence=self._normalize_evidence(content.get("evidence", {})),
                tokens_input=response.get("tokens_input", 0),
                tokens_output=response.get("tokens_output", 0),
                processing_time_ms=response.get("processing_time_ms", 0)
            )
            
        except Exception as e:
            if _is_fatal_llm_error(e):
                raise
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
            
            content = parse_json_object(response.get("content"))

            if not content:
                raw = response.get("content")
                if isinstance(raw, str) and raw.strip():
                    content = {"evidence": {"raw_excerpt": raw.strip()[:240]}}
            else:
                stance_missing = "stance" not in content
                confidence_missing = "confidence" not in content
                if stance_missing or confidence_missing:
                    raw = response.get("raw_content") or response.get("content")
                    if isinstance(raw, str) and raw.strip():
                        content.setdefault("evidence", {})
                        if isinstance(content["evidence"], dict) and "raw_excerpt" not in content["evidence"]:
                            content["evidence"]["raw_excerpt"] = raw.strip()[:240]

            fallback_args = own_response.key_arguments if own_response.key_arguments else []
            key_arguments = self._normalize_arguments(content.get("key_arguments", fallback_args))
            if not key_arguments:
                evidence_obj = content.get("evidence", own_response.evidence)
                raw_excerpt = evidence_obj.get("raw_excerpt") if isinstance(evidence_obj, dict) else None
                if isinstance(raw_excerpt, str) and raw_excerpt.strip():
                    key_arguments = [f"Raw model output tidak terstruktur: {raw_excerpt.strip()[:220]}..."]
                else:
                    key_arguments = ["Model tidak mengembalikan key_arguments terstruktur."]
            
            return AgentResponse(
                agent_type=self.agent_type,
                stance=self._normalize_stance(
                    content.get("stance", content.get("classification")),
                    default=own_response.stance,
                ),
                confidence=self._normalize_confidence(
                    content.get("confidence", own_response.confidence),
                    default=own_response.confidence,
                ),
                key_arguments=key_arguments,
                evidence=self._normalize_evidence(
                    content.get("evidence", own_response.evidence)
                ),
                tokens_input=response.get("tokens_input", 0),
                tokens_output=response.get("tokens_output", 0),
                processing_time_ms=response.get("processing_time_ms", 0)
            )
            
        except Exception as e:
            if _is_fatal_llm_error(e):
                raise
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

        # Re-attach objective evidence in round 2 to avoid pure argument-only drift.
        triage = message_data.get("triage", {}) if isinstance(message_data, dict) else {}
        if triage:
            parts.append("")
            parts.append("Evidence Triage:")
            parts.append(f"- Risk score: {triage.get('risk_score', 0)}")
            parts.append(f"- Triggered flags: {triage.get('triggered_flags', [])}")

        url_checks = context.get("url_checks", {}) if context else {}
        if isinstance(url_checks, dict) and url_checks:
            parts.append("")
            parts.append("Evidence URL Checker:")
            for url, result in url_checks.items():
                if isinstance(result, dict):
                    parts.append(
                        f"- {url}: malicious={result.get('is_malicious', False)}, "
                        f"risk={result.get('risk_score', 0)}, source={result.get('source', 'unknown')}"
                    )

        single_shot = context.get("single_shot", {}) if context else {}
        if isinstance(single_shot, dict) and single_shot:
            parts.append("")
            parts.append("Hasil Single-Shot:")
            parts.append(f"- Classification: {single_shot.get('classification', 'N/A')}")
            parts.append(f"- Confidence: {single_shot.get('confidence', 0):.0%}")
        
        parts.append("")
        parts.append("Pertimbangkan argumen agent lain. Apakah ada blind spot dalam analisis Anda?")
        parts.append("Anda boleh mempertahankan atau mengubah stance jika ada bukti kuat.")
        parts.append("")
        parts.append("Output WAJIB hanya 1 objek JSON valid dengan format yang sama (tanpa markdown/teks lain).")
        
        return "\n".join(parts)

    def _normalize_stance(self, stance: Any, default: str = "SUSPICIOUS") -> str:
        val = str(stance or default).strip().upper()
        aliases = {
            "SAFE": "LEGITIMATE",
            "AMAN": "LEGITIMATE",
            "LEGIT": "LEGITIMATE",
            "MENCURIGAKAN": "SUSPICIOUS",
            "PENIPUAN": "PHISHING",
            "SCAM": "PHISHING",
            "MALICIOUS": "PHISHING",
        }
        val = aliases.get(val, val)
        if val not in {"PHISHING", "SUSPICIOUS", "LEGITIMATE"}:
            return default if default in {"PHISHING", "SUSPICIOUS", "LEGITIMATE"} else "SUSPICIOUS"
        return val

    def _normalize_confidence(self, confidence: Any, default: float = 0.5) -> float:
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            value = float(default)
        if value > 1.0 and value <= 100.0:
            value = value / 100.0
        return max(0.0, min(1.0, value))

    def _normalize_arguments(self, args: Any) -> list[str]:
        if isinstance(args, list):
            return [str(a) for a in args]
        if args is None:
            return []
        return [str(args)]

    def _normalize_evidence(self, evidence: Any) -> dict:
        if isinstance(evidence, dict):
            return evidence
        if evidence is None:
            return {}
        return {"raw": str(evidence)}


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
        return """Kamu adalah Content Analyzer agent dalam sistem deteksi phishing untuk grup Telegram akademik Indonesia.

                    Peran: Menganalisis konten pesan, pola linguistik, dan deviasi perilaku pengirim.

                    Fokus analisis:
                    1. Konsistensi gaya bahasa dengan baseline pengguna
                    2. Taktik social engineering (urgensi, otoritas palsu, ketakutan, simpati)
                    3. Relevansi konteks dengan aktivitas akademik grup
                    4. Anomali struktur dan format pesan
                    5. Penggunaan bahasa Indonesia yang tidak wajar
                    6. Permintaan uang/pulsa/transfer/top-up — sinyal kuat account takeover
                       (penyerang ambil alih akun asli lalu meminta bantuan finansial ke anggota grup)
                    7. Permintaan redirect ke chat pribadi/DM untuk menghindari perhatian grup
                    8. Indikasi impersonasi: username sama tapi akun berbeda,
                       pesan tidak konsisten dengan karakter historis pemilik asli

                    Model ancaman yang harus dikenali:
                    - Akun dikompromikan mengirim link phishing
                    - Account takeover: akun asli diambil alih, penyerang minta pulsa/transfer
                    - Impersonasi: akun baru dibuat menyerupai dosen/mahasiswa asli

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
                    }

                    PENTING:
                    - Output WAJIB hanya 1 objek JSON valid sesuai schema di atas.
                    - Jangan gunakan markdown/code fence. Jangan tambah teks di luar JSON.
                    - Nilai stance harus salah satu: PHISHING, SUSPICIOUS, LEGITIMATE.
                    - confidence harus angka 0.0-1.0.
                    - Pesan tanpa URL tetap bisa phishing (pulsa scam, account takeover)."""
    
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
        
        # Triage flags — highlight new social-engineering flags explicitly
        triage = message_data.get('triage', {})
        if triage:
            triggered = triage.get('triggered_flags', [])
            parts.append("\nTriage Flags:")
            parts.append(f"- Risk score: {triage.get('risk_score', 0)}")
            parts.append(f"- Triggered: {triggered}")

            # Highlight flags paling relevan untuk content analysis
            HIGH_SIGNAL_FLAGS = {
                "redirect_to_private": "Pesan meminta penerima balas via DM/chat pribadi — taktik menghindari perhatian grup.",
                "suspected_impersonation": "Username dipakai user_id berbeda — kemungkinan akun klonan/impersonasi.",
                "first_time_solicitation": "Anggota lama tiba-tiba minta uang/pulsa/transfer untuk pertama kali — sinyal account takeover.",
                "urgency_keywords": "Terdapat kata-kata yang menciptakan tekanan atau rasa urgensi.",
                "phishing_keywords": "Terdapat kata/frasa indikator phishing.",
                "authority_impersonation": "Pesan mengklaim dari otoritas resmi.",
            }
            active_signals = []
            for flag in (triggered if isinstance(triggered, list) else []):
                if flag in HIGH_SIGNAL_FLAGS:
                    active_signals.append(f"  ⚠️ [{flag}] {HIGH_SIGNAL_FLAGS[flag]}")
            if active_signals:
                parts.append("Sinyal social engineering aktif:")
                parts.extend(active_signals)

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

    URL_RELEVANT_FLAGS = {
        "blacklisted_domain",
        "shortened_url",
        "shortened_url_expand_failed",
        "suspicious_tld",
        "first_time_url",
    }
    
    @property
    def system_prompt(self) -> str:
        return """Kamu adalah Security Validator agent dalam sistem deteksi phishing untuk grup Telegram akademik Indonesia.

                Peran: Memverifikasi bukti keamanan teknis — URL, domain, dan pola solicitation.

                Fokus analisis:
                1. Struktur URL (obfuscation, patterns mencurigakan)
                2. Reputasi domain berdasarkan data yang tersedia
                3. Verifikasi tujuan link (expanded URL, redirect chain)
                4. Kecocokan dengan database phishing historis
                5. HTTPS vs HTTP, TLD analysis
                6. URL shortener bukan bukti phishing jika expanded URL menunjuk domain tepercaya
                7. PERHATIAN KHUSUS — Jika TIDAK ADA URL:
                   - Analisa apakah ada pola solicitation (minta pulsa, transfer, nomor HP,
                     atau redirect ke DM) yang merupakan indikator account takeover/social scam
                   - Pesan tanpa URL bisa tetap berbahaya dan harus diberi confidence tinggi
                     jika triage flags menunjukkan `first_time_solicitation` atau `redirect_to_private`

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
                }

                PENTING:
                - Output WAJIB hanya 1 objek JSON valid sesuai schema di atas.
                - Jangan gunakan markdown/code fence. Jangan tambah teks di luar JSON.
                - Nilai stance harus salah satu: PHISHING, SUSPICIOUS, LEGITIMATE.
                - confidence harus angka 0.0-1.0.
                - Absennya URL bukan justifikasi untuk LEGITIMATE jika ada sinyal solicitation."""
    
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
            expanded_urls = triage.get('expanded_urls', {})
            if expanded_urls:
                parts.append("- Expanded URLs (Triage):")
                for original_url, expansion in expanded_urls.items():
                    if not isinstance(expansion, dict):
                        continue
                    expanded_url = expansion.get("expanded_url")
                    final_domain = expansion.get("final_domain")
                    source = expansion.get("source", "triage_expander")
                    if expanded_url:
                        parts.append(
                            f"  - {original_url} -> {expanded_url} "
                            f"(domain: {final_domain or 'unknown'}, source: {source})"
                        )
            
            triggered = triage.get('triggered_flags', [])
            url_flags: list[str] = []
            if isinstance(triggered, list):
                for flag in triggered:
                    flag_str = str(flag).strip()
                    if not flag_str:
                        continue
                    if flag_str in self.URL_RELEVANT_FLAGS:
                        url_flags.append(flag_str)

                # Backward compatibility for unknown future flag names.
                if not url_flags:
                    url_flags = [
                        str(f).strip()
                        for f in triggered
                        if any(k in str(f) for k in ("url", "tld", "domain"))
                    ]

                # Keep deterministic order, drop duplicates.
                url_flags = list(dict.fromkeys(url_flags))
            if url_flags:
                parts.append(f"- URL-related flags: {url_flags}")
        
        # External checks if available (VirusTotal, etc.)
        url_checks = context.get('url_checks', {}) if context else {}
        if url_checks:
            parts.append("\n=== Hasil URL Checker Eksternal ===")
            for url, result in url_checks.items():
                parts.append(f"\nURL: {url}")
                if isinstance(result, dict):
                    is_malicious = result.get('is_malicious', False)
                    risk_score = result.get('risk_score', 0)
                    source = result.get('source', 'unknown')
                    expanded_url = result.get('expanded_url')
                    details = result.get('details', {})
                    
                    status = "⚠️ BERBAHAYA" if is_malicious else "✅ AMAN"
                    parts.append(f"  Status: {status}")
                    parts.append(f"  Risk Score: {risk_score:.2f}")
                    parts.append(f"  Source: {source}")
                    if expanded_url:
                        parts.append(f"  Expanded URL: {expanded_url}")
                    
                    if details:
                        if details.get('trusted_domain') is True:
                            parts.append("  Trusted domain: ya")
                        if 'redirect_chain' in details:
                            redirect_chain = details.get('redirect_chain') or []
                            if redirect_chain:
                                parts.append(f"  Redirect chain: {' -> '.join(redirect_chain)}")
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
        
        # Jika tidak ada URL, arahkan agent untuk menganalisis pola solicitation
        if not urls:
            triage = message_data.get('triage', {})
            triggered = triage.get('triggered_flags', []) if triage else []
            no_url_signals = [
                f for f in (triggered if isinstance(triggered, list) else [])
                if f in ("first_time_solicitation", "redirect_to_private",
                         "suspected_impersonation", "phishing_keywords", "urgency_keywords")
            ]
            if no_url_signals:
                parts.append("\n⚠️ Pesan ini tidak mengandung URL tetapi memiliki sinyal risiko langsung:")
                for sig in no_url_signals:
                    parts.append(f"  - {sig}")
                parts.append("Analisis apakah sinyal tersebut cukup untuk mengklasifikasikan sebagai PHISHING/SUSPICIOUS.")
            else:
                parts.append("\nTidak ada URL dan tidak ada sinyal triage risiko tinggi. Pertimbangkan LEGITIMATE jika konten sesuai konteks akademik.")
        else:
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
        return """Kamu adalah Social Context Evaluator agent dalam sistem deteksi phishing untuk grup Telegram akademik Indonesia.

                Peran: Mengevaluasi konteks sosial, perilaku pengirim, dan kewajaran pesan dalam konteks grup mahasiswa.

                Fokus analisis:
                1. Pola perilaku historis pengirim vs konten pesan saat ini
                2. Kesesuaian waktu posting (jam, hari)
                3. Relevansi dengan aktivitas akademik yang sedang berlangsung
                4. Dinamika sosial dalam grup mahasiswa TI UIR
                5. Apakah konten masuk akal untuk konteks akademik
                6. Sinyal account takeover: anggota aktif yang tiba-tiba mengirim
                   permintaan uang/pulsa/transfer — sangat tidak wajar dalam grup akademik
                7. Sinyal impersonasi: ada flag `suspected_impersonation` berarti username
                   ini sebelumnya terdaftar dengan user_id berbeda — kemungkinan akun klonan
                8. Permintaan redirect ke DM/chat pribadi: tidak lazim untuk pesan akademik

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
                }

                PENTING:
                - Output WAJIB hanya 1 objek JSON valid sesuai schema di atas.
                - Jangan gunakan markdown/code fence. Jangan tambah teks di luar JSON.
                - Nilai stance harus salah satu: PHISHING, SUSPICIOUS, LEGITIMATE.
                - confidence harus angka 0.0-1.0.
                - Gunakan waktu lokal WIB dari input prompt (jangan asumsi UTC).
                - Sebut "dini hari" HANYA jika jam lokal WIB < 05:00.
                - Permintaan uang/pulsa di grup akademik hampir selalu mencurigakan."""
    
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
        hour_wib = message_data.get("hour_wib")
        if isinstance(hour_wib, int):
            parts.append(f"Jam lokal WIB: {hour_wib:02d}:00")
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
        
        # Behavioral anomalies — include all relevant flags (not just 'anomaly'/'first_time')
        triage = message_data.get('triage', {})
        triggered = triage.get('triggered_flags', []) if triage else []
        BEHAVIORAL_FLAGS = {
            'time_anomaly', 'length_anomaly', 'emoji_anomaly',
            'first_time_url', 'first_time_solicitation',
            'redirect_to_private', 'suspected_impersonation',
            'recent_suspicious_context',
        }
        BEHAVIORAL_DESCRIPTIONS = {
            'redirect_to_private': 'Pesan meminta penerima balas lewat DM — menghindari pantauan grup.',
            'suspected_impersonation': 'Username sudah terdaftar dengan user_id berbeda — kemungkinan impersonasi.',
            'first_time_solicitation': 'Anggota lama pertama kali minta uang/pulsa — sinyal account takeover.',
            'recent_suspicious_context': 'Pesan ini dikirim <15 menit setelah pesan SUSPICIOUS/PHISHING dari user yang sama — kemungkinan eskalasi percakapan scam.',
        }
        behavioral_flags = [f for f in (triggered if isinstance(triggered, list) else []) if f in BEHAVIORAL_FLAGS]
        if behavioral_flags:
            parts.append("\nAnomali / Sinyal sosial terdeteksi:")
            for bf in behavioral_flags:
                desc = BEHAVIORAL_DESCRIPTIONS.get(bf, "")
                parts.append(f"  - {bf}" + (f": {desc}" if desc else ""))
        
        # Previous stage
        if previous_result:
            parts.append("\nHasil Single-Shot LLM:")
            parts.append(f"- Classification: {previous_result.get('classification', 'N/A')}")
            parts.append(f"- Confidence: {previous_result.get('confidence', 0):.0%}")

        parts.append("\nKonteks: Grup mahasiswa Teknik Informatika UIR")
        parts.append("Evaluasi apakah pesan ini sesuai dengan konteks sosial dan berikan stance Anda.")

        return "\n".join(parts)
