"""
MAD v5 agents for phishing debate.
"""

import ast
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.llm import deepseek

VALID_STANCES = {"PHISHING", "SUSPICIOUS", "LEGITIMATE"}

OUTPUT_SCHEMA = (
    '{"stance":"PHISHING|SUSPICIOUS|LEGITIMATE",'
    '"confidence":0.0,'
    '"key_arguments":["arg1","arg2"],'
    '"evidence":{"key":"value"}}'
)


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
    """Response from a single MAD v5 agent."""

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
    """Base class for MAD v5 agents."""

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
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        pass

    def analyze(
        self,
        message_data: dict,
        context: dict | None = None,
        previous_result: dict | None = None,
    ) -> AgentResponse:
        prompt = self._construct_prompt(message_data, context, previous_result)
        return self._query_llm(prompt)

    def deliberate(
        self,
        message_data: dict,
        own_response: AgentResponse,
        other_responses: list[AgentResponse],
        context: dict | None = None,
    ) -> AgentResponse:
        prompt = self._construct_deliberation_prompt(
            message_data, own_response, other_responses, context
        )

        try:
            updated = self._query_llm(prompt)
            if updated.agent_type != self.agent_type:
                updated.agent_type = self.agent_type
            return updated
        except Exception as exc:
            if _is_fatal_llm_error(exc):
                raise
            return own_response

    def _query_llm(self, prompt: str) -> AgentResponse:
        try:
            response = self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=450,
                json_mode=True,
            )

            content = response.get("content", {})
            content = self._parse_llm_content(content)

            stance_raw = content.get("stance")
            stance = self._normalize_stance(stance_raw)

            confidence = self._normalize_confidence(content.get("confidence", 0.5))
            stance_missing = stance_raw is None
            if stance_missing:
                confidence = min(confidence, 0.6)

            key_arguments = content.get("key_arguments", [])
            if not isinstance(key_arguments, list):
                key_arguments = [str(key_arguments)]
            key_arguments = [str(arg) for arg in key_arguments]
            if stance_missing and not key_arguments:
                key_arguments = ["Model response missing required 'stance' field."]

            evidence = content.get("evidence", {})
            if not isinstance(evidence, dict):
                evidence = {"raw": evidence}

            return AgentResponse(
                agent_type=self.agent_type,
                stance=stance,
                confidence=confidence,
                key_arguments=key_arguments,
                evidence=evidence,
                tokens_input=response.get("tokens_input", 0),
                tokens_output=response.get("tokens_output", 0),
                processing_time_ms=response.get("processing_time_ms", 0),
            )
        except Exception as exc:
            if _is_fatal_llm_error(exc):
                raise
            return AgentResponse(
                agent_type=self.agent_type,
                stance="SUSPICIOUS",
                confidence=0.5,
                key_arguments=[f"Analysis failed: {exc}"],
                evidence={"error": str(exc)},
            )

    def _parse_llm_content(self, content) -> dict:
        """Parse LLM output with tolerant JSON fallbacks."""
        if isinstance(content, dict):
            return content
        if content is None:
            return {}
        if not isinstance(content, str):
            raise ValueError("LLM content is not JSON/dict")

        text = content.strip()
        if not text:
            return {}

        # Remove fenced markdown wrappers if model still emits them.
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        candidates = [text]
        first_curly = text.find("{")
        last_curly = text.rfind("}")
        if first_curly != -1 and last_curly != -1 and last_curly > first_curly:
            candidates.append(text[first_curly:last_curly + 1])

        for candidate in candidates:
            # Strict JSON parse.
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            # Repair trailing commas.
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            # Last resort: Python literal dict.
            try:
                parsed = ast.literal_eval(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        raise ValueError("Unable to parse JSON object from LLM response.")

    def _normalize_stance(self, stance_raw) -> str:
        stance = str(stance_raw or "SUSPICIOUS").upper().strip()
        stance_aliases = {
            "SAFE": "LEGITIMATE",
            "NORMAL": "LEGITIMATE",
            "LEGIT": "LEGITIMATE",
            "MALICIOUS": "PHISHING",
            "SCAM": "PHISHING",
        }
        stance = stance_aliases.get(stance, stance)
        if stance not in VALID_STANCES:
            return "SUSPICIOUS"
        return stance

    def _normalize_confidence(self, confidence_raw) -> float:
        try:
            confidence = float(confidence_raw if confidence_raw is not None else 0.5)
        except (TypeError, ValueError):
            confidence = 0.5

        # Allow % format (e.g., 85 means 0.85).
        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0

        return max(0.0, min(1.0, confidence))

    @abstractmethod
    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None,
    ) -> str:
        pass

    def _construct_deliberation_prompt(
        self,
        message_data: dict,
        own_response: AgentResponse,
        other_responses: list[AgentResponse],
        context: dict | None,
    ) -> str:
        parts = ["=== Round 2: Deliberasi MAD v5 ===", ""]
        parts.append(f"Pesan: \"{message_data.get('content', '')}\"")
        parts.append("")
        parts.append("Stance Anda di Round 1:")
        parts.append(f"- Stance: {own_response.stance}")
        parts.append(f"- Confidence: {own_response.confidence:.0%}")
        parts.append(f"- Argumen: {own_response.key_arguments}")
        parts.append("")
        parts.append("Stance agent lain:")
        for resp in other_responses:
            parts.append(f"- {resp.agent_type}: {resp.stance} ({resp.confidence:.0%})")
            parts.append(f"  Argumen: {resp.key_arguments}")

        if context and context.get("url_checks"):
            parts.append("")
            parts.append("Data URL checker tersedia. Gunakan sebagai bukti objektif.")

        parts.append("")
        parts.append("Tinjau blind spot, lalu putuskan apakah stance harus berubah.")
        self._append_output_contract(parts)
        return "\n".join(parts)

    def _append_shared_context(
        self,
        parts: list[str],
        message_data: dict,
        context: dict | None,
        previous_result: dict | None,
    ) -> None:
        parts.append(f"Pesan: \"{message_data.get('content', '')}\"")
        parts.append(f"Waktu: {message_data.get('timestamp', 'unknown')}")

        sender = message_data.get("sender", {})
        if sender:
            parts.append(f"Pengirim: @{sender.get('username', 'unknown')}")

        urls = message_data.get("urls", [])
        if urls:
            parts.append("URL ditemukan:")
            for url in urls:
                parts.append(f"- {url}")
        else:
            parts.append("URL ditemukan: tidak ada")

        triage = message_data.get("triage", {})
        if triage:
            parts.append(f"Triage risk score: {triage.get('risk_score', 0)}")
            parts.append(f"Triage flags: {triage.get('triggered_flags', [])}")

        baseline = context.get("baseline", {}) if context else {}
        if baseline and baseline.get("total_messages", 0) > 0:
            parts.append(f"Riwayat pesan user: {baseline.get('total_messages', 0)}")
            parts.append(f"URL sharing rate: {baseline.get('url_sharing_rate', 0):.2%}")

        url_checks = context.get("url_checks", {}) if context else {}
        if url_checks:
            parts.append("URL checker eksternal:")
            for url, result in url_checks.items():
                if isinstance(result, dict):
                    parts.append(
                        f"- {url}: malicious={result.get('is_malicious', False)}, "
                        f"risk={result.get('risk_score', 0)}"
                    )

        if previous_result:
            parts.append(
                f"Single-shot: {previous_result.get('classification', 'N/A')} "
                f"({previous_result.get('confidence', 0):.0%})"
            )

            # MAD stage only receives risky or uncertain cases.
            parts.append(
                "Catatan: pesan ini sudah di-eskalasi ke Stage-3 karena dianggap berisiko "
                "atau belum meyakinkan di tahap sebelumnya."
            )

    def _append_output_contract(self, parts: list[str]) -> None:
        parts.append("")
        parts.append("Output WAJIB JSON valid tanpa markdown, komentar, atau trailing comma.")
        parts.append("Gunakan schema persis berikut:")
        parts.append(OUTPUT_SCHEMA)


class DetectorAgent(BaseAgent):
    """Primary detector agent."""

    @property
    def agent_type(self) -> str:
        return "detector_agent"

    @property
    def system_prompt(self) -> str:
        return (
            "Kamu adalah Detector Agent untuk deteksi phishing. "
            "Prioritasmu adalah menemukan indikasi serangan secara cepat "
            "berdasarkan pola social engineering, ancaman URL, dan anomali pesan. "
            "WAJIB output JSON valid sesuai schema yang diminta user prompt."
        )

    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None,
    ) -> str:
        parts = ["=== Round 1: Detector Agent ===", ""]
        self._append_shared_context(parts, message_data, context, previous_result)
        parts.append("")
        parts.append("Tugas:")
        parts.append("- Berikan deteksi awal seagresif mungkin berbasis indikator risiko.")
        parts.append("- Jelaskan sinyal paling kuat yang mengarah ke phishing.")
        parts.append("- Jika ada >=2 indikator risiko kuat, utamakan PHISHING.")
        parts.append("- Gunakan SUSPICIOUS hanya bila bukti ambigu.")
        self._append_output_contract(parts)
        return "\n".join(parts)


class CriticAgent(BaseAgent):
    """Agent that challenges weak or overstated conclusions."""

    @property
    def agent_type(self) -> str:
        return "critic_agent"

    @property
    def system_prompt(self) -> str:
        return (
            "Kamu adalah Critic Agent dalam debat deteksi phishing. "
            "Peranmu adalah menguji ketahanan argumen, mencari lompatan logika, "
            "dan menurunkan keyakinan jika bukti tidak cukup. "
            "WAJIB output JSON valid sesuai schema yang diminta user prompt."
        )

    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None,
    ) -> str:
        parts = ["=== Round 1: Critic Agent ===", ""]
        self._append_shared_context(parts, message_data, context, previous_result)
        parts.append("")
        parts.append("Tugas:")
        parts.append("- Cari alasan kenapa pesan bisa saja bukan phishing.")
        parts.append("- Identifikasi kelemahan bukti atau kemungkinan false positive.")
        parts.append("- Jika tetap berisiko tinggi, tetap boleh memilih PHISHING.")
        self._append_output_contract(parts)
        return "\n".join(parts)


class DefenderAgent(BaseAgent):
    """Agent that looks for legitimate explanations."""

    @property
    def agent_type(self) -> str:
        return "defender_agent"

    @property
    def system_prompt(self) -> str:
        return (
            "Kamu adalah Defender Agent dalam debat deteksi phishing. "
            "Peranmu membela kemungkinan LEGITIMATE secara rasional, "
            "namun tetap patuh pada bukti objektif keamanan. "
            "WAJIB output JSON valid sesuai schema yang diminta user prompt."
        )

    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None,
    ) -> str:
        parts = ["=== Round 1: Defender Agent ===", ""]
        self._append_shared_context(parts, message_data, context, previous_result)
        parts.append("")
        parts.append("Tugas:")
        parts.append("- Cari penjelasan yang valid jika pesan ini normal/legitimate.")
        parts.append("- Tunjukkan bukti yang mendukung konteks akademik normal.")
        parts.append("- Jika tidak bisa dipertahankan, turunkan stance ke SUSPICIOUS/PHISHING.")
        self._append_output_contract(parts)
        return "\n".join(parts)


class FactCheckerAgent(BaseAgent):
    """Agent that validates facts and external evidence."""

    @property
    def agent_type(self) -> str:
        return "fact_checker_agent"

    @property
    def system_prompt(self) -> str:
        return (
            "Kamu adalah Fact Checker Agent untuk verifikasi klaim phishing. "
            "Fokus pada validasi fakta: URL evidence, metadata, dan konsistensi data. "
            "WAJIB output JSON valid sesuai schema yang diminta user prompt."
        )

    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None,
    ) -> str:
        parts = ["=== Round 1: Fact Checker Agent ===", ""]
        self._append_shared_context(parts, message_data, context, previous_result)
        parts.append("")
        parts.append("Tugas:")
        parts.append("- Verifikasi klaim berbasis data faktual (URL checks, triage flags).")
        parts.append("- Pisahkan fakta, asumsi, dan ketidakpastian.")
        parts.append("- Beri confidence tinggi hanya jika bukti objektif kuat.")
        self._append_output_contract(parts)
        return "\n".join(parts)


class JudgeAgent(BaseAgent):
    """Agent that provides a balanced ruling."""

    @property
    def agent_type(self) -> str:
        return "judge_agent"

    @property
    def system_prompt(self) -> str:
        return (
            "Kamu adalah Judge Agent dalam sistem debat phishing. "
            "Peranmu adalah menyeimbangkan deteksi agresif dan pencegahan false alarm, "
            "lalu memberi putusan paling defensible. "
            "WAJIB output JSON valid sesuai schema yang diminta user prompt."
        )

    def _construct_prompt(
        self,
        message_data: dict,
        context: dict | None,
        previous_result: dict | None,
    ) -> str:
        parts = ["=== Round 1: Judge Agent ===", ""]
        self._append_shared_context(parts, message_data, context, previous_result)
        parts.append("")
        parts.append("Tugas:")
        parts.append("- Putuskan verdict awal yang paling seimbang dan defensible.")
        parts.append("- Pertimbangkan cost false negative dan false positive.")
        parts.append(
            "- Jika ada indikasi kuat phishing, jangan default ke SUSPICIOUS."
        )
        self._append_output_contract(parts)
        return "\n".join(parts)
