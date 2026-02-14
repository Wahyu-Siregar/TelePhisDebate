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
- Konten tipikal: diskusi akademik, Informasi akademik, pengumuman event kampus
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
5. URL shortener tidak otomatis berbahaya jika expanded URL mengarah ke domain terpercaya

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
- Jangan memberi label PHISHING hanya karena URL shortener jika evidence expand/trusted mendukung LEGITIMATE
- Pertimbangkan konteks grup akademik Indonesia"""


def construct_analysis_prompt(
    message_text: str,
    message_timestamp: datetime,
    sender_info: dict | None = None,
    baseline_metrics: dict | None = None,
    triage_result: dict | None = None
) -> str:
    """
    Susun prompt analisis untuk LLM Single-Shot.
    
    Args:
        message_text: Konten pesan yang akan dianalisis
        message_timestamp: Waktu ketika pesan dikirim
        sender_info: Informasi tentang pengirim (nama pengguna, tanggal bergabung, dll.)
        baseline_metrics: Metrik perilaku dasar pengguna
        triage_result: Hasil dari tahap triase berbasis aturan
        
    Returns:
        String prompt yang telah diformat
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
        
        expanded_urls = triage_result.get("expanded_urls", {})
        if expanded_urls:
            prompt_parts.append("- Evidence ekspansi URL:")
            for original_url, expansion in expanded_urls.items():
                if not isinstance(expansion, dict):
                    continue
                expanded_url = expansion.get("expanded_url")
                final_domain = expansion.get("final_domain")
                source = expansion.get("source", "triage_expander")
                if expanded_url:
                    prompt_parts.append(
                        f"  - {original_url} -> {expanded_url} "
                        f"(domain: {final_domain or 'unknown'}, source: {source})"
                    )
                else:
                    prompt_parts.append(
                        f"  - {original_url} -> gagal expand "
                        f"(source: {source})"
                    )
    
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
