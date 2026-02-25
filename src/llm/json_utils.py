"""
Shared JSON parsing helpers for LLM outputs.

Some providers occasionally wrap JSON in markdown fences or include a short preamble.
These helpers keep parsing tolerant so agents/classifiers don't crash and default to
safe fallbacks instead.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _normalize_label(label: str) -> str:
    """
    Normalize common classification/stance labels across providers/languages.
    """
    if label is None:
        return ""
    t = str(label).strip().upper()
    # Indonesian/common variants
    if t in {"AMAN", "LEGIT", "LEGITIMATE", "SAFE"}:
        return "SAFE"
    if t in {"MENCURIGAKAN", "SUSPICIOUS"}:
        return "SUSPICIOUS"
    if t in {"PENIPUAN", "PHISHING", "SCAM", "BERBAHAYA", "MALICIOUS"}:
        return "PHISHING"
    return t


def _label_payload(label: str) -> dict[str, Any]:
    """
    Build a minimal payload for bare-label model outputs.
    Returns both classification and stance when possible.
    """
    raw = str(label).strip().upper()
    norm = _normalize_label(label)
    out: dict[str, Any] = {}

    if raw == "LEGITIMATE":
        out["stance"] = "LEGITIMATE"
        out["classification"] = "SAFE"
        return out

    if norm in {"SAFE", "SUSPICIOUS", "PHISHING"}:
        out["classification"] = norm
        out["stance"] = "LEGITIMATE" if norm == "SAFE" else norm

    return out


def parse_json_object(value: Any) -> dict:
    """
    Best-effort parse a JSON object from an LLM response.

    Returns:
      dict: parsed object, or {} if parsing fails.
    """
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if not isinstance(value, str):
        return {}

    text = _strip_fences(value)
    if not text:
        return {}

    # If the model outputs just a label (common in small/fast models), accept it.
    # Keep this conservative by only accepting when the first non-empty line begins with a known label.
    first_line = text.splitlines()[0].strip()
    m = re.match(
        r"^(PHISHING|SUSPICIOUS|LEGITIMATE|SAFE|AMAN|MENCURIGAKAN|PENIPUAN)\b(?:\s*[\-:,(].*)?$",
        first_line,
        flags=re.IGNORECASE,
    )
    if m:
        payload = _label_payload(m.group(1))
        if payload:
            return payload

    candidates: list[str] = [text]
    first_curly = text.find("{")
    last_curly = text.rfind("}")
    if first_curly != -1 and last_curly != -1 and last_curly > first_curly:
        candidates.append(text[first_curly:last_curly + 1])

    for candidate in candidates:
        # Strict JSON.
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

        # Python literal dict fallback.
        try:
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # Key-value extraction fallback for providers/models that ignore "JSON only" instructions.
    # This is intentionally conservative: it only extracts a few common fields used across the project.
    # Example tolerated formats:
    # - "classification: PHISHING, confidence: 0.82"
    # - "stance = LEGITIMATE (confidence 70%)"
    out: dict[str, Any] = {}
    m = re.search(
        r"\b(classification|klasifikasi)\b\s*[:=]\s*\"?\s*(SAFE|SUSPICIOUS|PHISHING|AMAN|MENCURIGAKAN|PENIPUAN)\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        out["classification"] = _normalize_label(m.group(2))

    m = re.search(
        r"\b(stance|verdict|putusan)\b\s*[:=]\s*\"?\s*(PHISHING|SUSPICIOUS|LEGITIMATE|SAFE|AMAN|MENCURIGAKAN|PENIPUAN)\b",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        payload = _label_payload(m.group(2))
        if payload.get("stance"):
            out["stance"] = payload["stance"]
        if payload.get("classification"):
            out.setdefault("classification", payload["classification"])

    m = re.search(
        r"\b(confidence|keyakinan)\b\s*[:=]?\s*\"?\s*([0-9]+(?:\.[0-9]+)?)\s*%?",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        try:
            v = float(m.group(2))
            if v > 1.0:
                v = v / 100.0
            # Clamp to [0,1]
            out["confidence"] = max(0.0, min(1.0, v))
        except Exception:
            pass

    if out:
        return out

    return {}
