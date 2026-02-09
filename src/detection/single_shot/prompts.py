"""
Prompt templates for Single-Shot LLM classification
"""

from datetime import datetime
from typing import Any


# System prompt for phishing detection
SYSTEM_PROMPT = """Kamu adalah sistem deteksi phishing untuk grup Telegram akademik Indonesia.
Tugasmu: Menganalisis apakah pesan dari akun mahasiswa terverifikasi menunjukkan tanda-tanda akun yang disusupi atau upaya phishing.

Konteks:
- Grup: Mahasiswa Teknik Informatika, Universitas Islam Riau (UIR)
- Konten tipikal: diskusi akademik, tugas kuliah, pengumuman event kampus
- Model ancaman: Akun mahasiswa yang dikompromikan mengirimkan link phishing

Kriteria Phishing:
1. URL mencurigakan (shortened, TLD aneh, domain mirip tapi beda)
2. Taktik social engineering (urgensi berlebihan, otoritas palsu, ketakutan)
3. Permintaan data sensitif (password, OTP, transfer uang)
4. Perilaku tidak konsisten dengan baseline pengguna
5. Konteks tidak relevan dengan aktivitas akademik

Kriteria Legitimate:
1. URL dari domain terpercaya (kampus, Google, GitHub, dll)
2. Konteks sesuai aktivitas akademik
3. Gaya pesan konsisten dengan pengguna
4. Tidak ada indikator social engineering

Output dalam format JSON strict:
{
  "classification": "SAFE" | "SUSPICIOUS" | "PHISHING",
  "confidence": 0.0-1.0,
  "reasoning": "penjelasan singkat dalam Bahasa Indonesia",
  "risk_factors": ["faktor1", "faktor2", ...]
}

PENTING:
- Berikan confidence tinggi (>0.85) hanya jika sangat yakin
- Gunakan "SUSPICIOUS" jika ragu antara SAFE dan PHISHING
- Pertimbangkan konteks grup akademik Indonesia"""


def construct_analysis_prompt(
    message_text: str,
    message_timestamp: datetime,
    sender_info: dict | None = None,
    baseline_metrics: dict | None = None,
    triage_result: dict | None = None
) -> str:
    """
    Construct the analysis prompt for Single-Shot LLM.
    
    Args:
        message_text: The message content to analyze
        message_timestamp: When the message was sent
        sender_info: Information about the sender (username, join date, etc.)
        baseline_metrics: User's baseline behavior metrics
        triage_result: Result from rule-based triage stage
        
    Returns:
        Formatted prompt string
    """
    prompt_parts = ["=== Permintaan Analisis Pesan ===\n"]
    
    # Sender information
    if sender_info:
        username = sender_info.get("username", "unknown")
        join_date = sender_info.get("joined_group_at", "unknown")
        prompt_parts.append(f"Pengirim: @{username}")
        prompt_parts.append(f"Bergabung: {join_date}")
    else:
        prompt_parts.append("Pengirim: (tidak diketahui)")
    
    prompt_parts.append("")
    
    # Baseline behavior
    if baseline_metrics and baseline_metrics.get("total_messages", 0) > 0:
        prompt_parts.append("Perilaku Baseline:")
        
        avg_len = baseline_metrics.get("avg_message_length")
        if avg_len:
            prompt_parts.append(f"- Rata-rata panjang pesan: {avg_len:.0f} karakter")
        
        typical_hours = baseline_metrics.get("typical_hours", [])
        if typical_hours:
            hour_range = f"{min(typical_hours):02d}:00 - {max(typical_hours):02d}:00"
            prompt_parts.append(f"- Jam posting tipikal: {hour_range}")
        
        url_rate = baseline_metrics.get("url_sharing_rate", 0)
        prompt_parts.append(f"- Frekuensi share URL: {url_rate:.2%} per pesan")
        
        total_msgs = baseline_metrics.get("total_messages", 0)
        prompt_parts.append(f"- Total pesan historis: {total_msgs}")
    else:
        prompt_parts.append("Perilaku Baseline: (belum cukup data)")
    
    prompt_parts.append("")
    
    # Current message details
    prompt_parts.append("Pesan Saat Ini:")
    prompt_parts.append(f"- Waktu: {message_timestamp.strftime('%Y-%m-%d %H:%M')} WIB")
    prompt_parts.append(f"- Panjang: {len(message_text)} karakter")
    prompt_parts.append(f"- Isi pesan:")
    prompt_parts.append(f'  "{message_text}"')
    
    prompt_parts.append("")
    
    # Triage results
    if triage_result:
        prompt_parts.append("Hasil Triage (rule-based):")
        prompt_parts.append(f"- Risk Score: {triage_result.get('risk_score', 0)}/100")
        
        flags = triage_result.get("triggered_flags", [])
        if flags:
            prompt_parts.append(f"- Red Flags: {', '.join(flags)}")
        
        urls = triage_result.get("urls_found", [])
        if urls:
            prompt_parts.append(f"- URLs ditemukan: {urls}")
        
        whitelisted = triage_result.get("whitelisted_urls", [])
        if whitelisted:
            prompt_parts.append(f"- URLs whitelisted: {whitelisted}")
    
    prompt_parts.append("")
    prompt_parts.append("Analisis pesan ini dan berikan klasifikasi dalam format JSON.")
    
    return "\n".join(prompt_parts)


def construct_minimal_prompt(message_text: str) -> str:
    """
    Construct a minimal prompt for quick analysis.
    Used when context is limited.
    
    Args:
        message_text: The message to analyze
        
    Returns:
        Minimal prompt string
    """
    return f"""Analisis pesan Telegram berikut untuk deteksi phishing:

Pesan: "{message_text}"

Berikan klasifikasi dalam format JSON."""
