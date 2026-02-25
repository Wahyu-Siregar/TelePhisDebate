# TelePhisDebate — Dokumentasi Sistem

## Sistem Deteksi Phishing Berbasis Multi-Agent Debate untuk Grup Telegram

> **Proyek Tugas Akhir (Skripsi)**
> Universitas Islam Riau — Teknik Informatika
> Versi: `0.4.0`

---

## Daftar Isi

1. [Ringkasan Sistem](#1-ringkasan-sistem)
2. [Arsitektur Sistem](#2-arsitektur-sistem)
3. [Struktur Direktori](#3-struktur-direktori)
4. [Pipeline Deteksi — 3 Tahap](#4-pipeline-deteksi--3-tahap)
   - 4.1 [Stage 1: Rule-Based Triage](#41-stage-1-rule-based-triage)
   - 4.2 [Stage 2: Single-Shot LLM](#42-stage-2-single-shot-llm)
   - 4.3 [Stage 3: Multi-Agent Debate (MAD)](#43-stage-3-multi-agent-debate-mad)
5. [Komponen Pendukung](#5-komponen-pendukung)
   - 5.1 [LLM Client (DeepSeek + OpenRouter)](#51-llm-client-deepseek--openrouter)
   - 5.2 [URL Security Checker](#52-url-security-checker)
   - 5.3 [Database (Supabase)](#53-database-supabase)
6. [Telegram Bot](#6-telegram-bot)
   - 6.1 [Bot Core](#61-bot-core)
   - 6.2 [Message Handler](#62-message-handler)
   - 6.3 [Bot Actions](#63-bot-actions)
7. [Dashboard Monitoring](#7-dashboard-monitoring)
8. [Konfigurasi](#8-konfigurasi)
9. [Alur Data End-to-End](#9-alur-data-end-to-end)
10. [Testing](#10-testing)
11. [Dependencies](#11-dependencies)
12. [Cara Menjalankan](#12-cara-menjalankan)
13. [Perhitungan dan Formula](#13-perhitungan-dan-formula-yang-digunakan)
   - 13.1 [Triage Risk Score](#131-stage-1--triage-risk-score)
   - 13.2 [Deteksi Anomali Perilaku](#132-deteksi-anomali-perilaku-behavioral)
   - 13.3 [Blacklist CAPS Lock Ratio](#133-blacklist--caps-lock-ratio)
   - 13.4 [URL Heuristic Risk Score](#134-url-heuristic-risk-score)
   - 13.5 [VirusTotal Risk Score](#135-virustotal--risk-score)
   - 13.6 [Logika Eskalasi Single-Shot](#136-stage-2--logika-eskalasi-single-shot)
   - 13.7 [Multi-Agent Debate Voting](#137-stage-3--multi-agent-debate)
   - 13.8 [Penentuan Aksi Pipeline](#138-pipeline--penentuan-aksi)
   - 13.9 [Ringkasan Konstanta & Threshold](#139-ringkasan-konstanta--threshold)

---

## 1. Ringkasan Sistem

**TelePhisDebate** adalah bot Telegram untuk mendeteksi pesan phishing di grup akademik, khususnya grup Teknik Informatika Universitas Islam Riau (UIR). Sistem menggunakan pendekatan **hybrid 3-tahap** yang menggabungkan:

| Tahap | Metode | Tujuan |
|-------|--------|--------|
| **Stage 1** | Rule-Based Triage | Filter cepat berbasis aturan untuk kasus jelas |
| **Stage 2** | Single-Shot LLM (Configurable Provider) | Klasifikasi AI untuk kasus non-trivial |
| **Stage 3** | Multi-Agent Debate (MAD) | 3 agen AI berdebat untuk kasus ambigu |

**Keunggulan arsitektur ini:**
- **Prioritas deteksi**: kasus ambigu dieskalasi untuk analisis lebih dalam
- **Akurasi tinggi**: Kasus ambigu diselesaikan melalui debat multi-agen
- **Respons cepat**: Pesan aman diproses instan (<10ms), pesan berbahaya <15 detik
- **Konteks lokal**: Disesuaikan untuk grup akademik Indonesia (bahasa, pola, domain)

---

## 2. Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────┐
│                     TELEGRAM GROUP CHAT                         │
│                  (Grup TI UIR / Test Group)                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Pesan masuk
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TELEGRAM BOT (TelePhisBot)                    │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────┐             │
│  │ Handlers │→ │ MessageHandler│→ │  BotActions   │             │
│  │ /start   │  │ (filter,      │  │ (warn/        │             │
│  │ /help    │  │  extract,     │  │  flag_review) │             │
│  │ /check   │  │  register,    │  │               │             │
│  │ /status  │  │  process)     │  │               │             │
│  │ /stats   │  │               │  │               │             │
│  └──────────┘  └───────┬───────┘  └──────────────┘             │
└────────────────────────┼────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHISHING DETECTION PIPELINE                        │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   STAGE 1    │    │   STAGE 2    │    │     STAGE 3      │  │
│  │  Rule-Based  │───→│ Single-Shot  │───→│  Multi-Agent     │  │
│  │   Triage     │    │    LLM       │    │    Debate        │  │
│  │              │    │              │    │                   │  │
│  │ • Whitelist  │    │ • DeepSeek   │    │ • Content Agent  │  │
│  │ • Blacklist  │    │ • Prompt Eng │    │ • Security Agent │  │
│  │ • Behavioral │    │ • JSON Parse │    │ • Social Agent   │  │
│  │ • URL Analyze│    │ • Escalation │    │ • Aggregator     │  │
│  └──────┬───────┘    └──────┬───────┘    └────────┬─────────┘  │
│         │ SAFE              │                      │            │
│         │ (skip)            │ High conf            │ Final      │
│         ▼                   ▼                      ▼            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  DetectionResult                         │   │
│  │  classification | confidence | decided_by | action       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌────────────┐ ┌───────────┐ ┌─────────────┐
   │  Supabase  │ │ VirusTotal│ │  Dashboard  │
   │  Database  │ │    API    │ │   (Flask)   │
   │  (logging) │ │ (URL chk) │ │ (monitoring)│
   └────────────┘ └───────────┘ └─────────────┘
```

---

## 3. Struktur Direktori

```
TelePhisDebate/
├── main.py                    # Entry point — menjalankan bot
├── run_dashboard.py           # Entry point — menjalankan dashboard web
├── requirements.txt           # Dependencies Python
├── .env                       # Environment variables (tidak di-commit)
│
├── src/                       # Source code utama
│   ├── __init__.py            # Package root (versi 0.4.0)
│   ├── config.py              # Konfigurasi dari env variables
│   │
│   ├── bot/                   # Telegram Bot
│   │   ├── bot.py             # TelePhisBot — class utama bot
│   │   ├── handlers.py        # MessageHandler — proses pesan masuk
│   │   └── actions.py         # BotActions — hapus/warn/notify admin
│   │
│   ├── detection/             # Pipeline deteksi phishing
│   │   ├── pipeline.py        # PhishingDetectionPipeline — orchestrator
│   │   ├── url_checker.py     # URLSecurityChecker + VirusTotal API
│   │   │
│   │   ├── triage/            # Stage 1: Rule-Based Triage
│   │   │   ├── triage.py      # RuleBasedTriage — koordinator
│   │   │   ├── whitelist.py   # WhitelistChecker — domain terpercaya
│   │   │   ├── blacklist.py   # BlacklistChecker — pola berbahaya
│   │   │   ├── url_analyzer.py # URLAnalyzer — ekstraksi & analisis URL
│   │   │   └── behavioral.py  # BehavioralAnomalyDetector — anomali perilaku
│   │   │
│   │   ├── single_shot/       # Stage 2: Single-Shot LLM
│   │   │   ├── classifier.py  # SingleShotClassifier — klasifikasi LLM
│   │   │   └── prompts.py     # Template prompt (Bahasa Indonesia)
│   │   │
│   │   ├── mad/               # Stage 3a: MAD v3 (3 agen)
│   │   │   ├── agents.py      # 3 agen: Content, Security, Social
│   │   │   ├── orchestrator.py # MultiAgentDebate — koordinator debat
│   │   │   └── aggregator.py  # VotingAggregator — weighted voting
│   │   └── mad5/              # Stage 3b: MAD v5 (5 agen)
│   │       ├── agents.py      # 5 agen: detector/critic/defender/fact-checker/judge
│   │       ├── orchestrator.py
│   │       └── aggregator.py
│   │
│   ├── llm/                   # LLM Client (provider: deepseek/openrouter)
│   │   ├── __init__.py        # Public API (`llm()` / provider factory)
│   │   ├── factory.py         # LLMFactory — pilih provider via env `LLM_PROVIDER`
│   │   ├── deepseek_client.py # DeepSeekClient — DeepSeek (OpenAI-compatible)
│   │   ├── openrouter_client.py # OpenRouterClient — OpenRouter (OpenAI-compatible)
│   │   └── json_utils.py      # Helper parsing JSON toleran (untuk output structured)
│   │
│   ├── database/              # Database (Supabase)
│   │   └── client.py          # Supabase client singleton
│   │
│   └── dashboard/             # Web Dashboard
│       ├── app.py             # Flask app + REST API endpoints
│       ├── templates/index.html, evaluation.html, mad_compare.html, evaluation_modes.html
│       └── static/css/style.css, js/dashboard.js
│
├── dataset/                   # Dataset
│   └── suspicious_tlds_list.csv  # TLD mencurigakan (300+ entries)
│
├── tests/                     # Unit tests
│   ├── test_url_checker.py
│   └── test_url_checker_standalone.py
│
├── test_*.py                  # Integration/end-to-end tests
│   ├── test_bot.py            # Test inisialisasi bot
│   ├── test_connections.py    # Test koneksi API (Telegram, DeepSeek, Supabase, VT)
│   ├── test_pipeline.py       # Test full pipeline end-to-end
│   ├── test_triage.py         # Test stage 1
│   ├── test_single_shot.py    # Test stage 2
│   └── test_mad.py            # Test stage 3
│
└── diagrams/                  # Diagram arsitektur (.mmd, .puml, .d2)
```

---

## 4. Pipeline Deteksi — 3 Tahap

### 4.1 Stage 1: Rule-Based Triage

**File:** `src/detection/triage/`
**Class:** `RuleBasedTriage`

Tahap pertama melakukan filtering cepat tanpa panggilan API LLM. Terdiri dari 4 sub-komponen:

#### A. Whitelist Checker (`whitelist.py`)

Memeriksa apakah URL dalam pesan berasal dari domain terpercaya. Jika **semua** URL termasuk whitelist, pesan langsung diklasifikasi **SAFE**.

**Kategori domain terpercaya:**

| Kategori | Contoh Domain |
|----------|---------------|
| Akademik UIR | `uir.ac.id`, `student.uir.ac.id`, `elearning.uir.ac.id` |
| Platform Akademik | `classroom.google.com`, `github.com`, `scholar.google.com` |
| Meeting | `zoom.us`, `meet.google.com`, `teams.microsoft.com` |
| Sosial Media | `youtube.com`, `instagram.com`, `t.me` |
| Pemerintah | `go.id`, `kemdikbud.go.id` |

Mendukung pencocokan subdomain: `sub.uir.ac.id` akan cocok karena `uir.ac.id` ada di whitelist.

#### B. Blacklist Checker (`blacklist.py`)

Mendeteksi indikator phishing melalui 7 jenis pemeriksaan:

| Red Flag | Contoh | Bobot Skor |
|----------|--------|------------|
| `blacklisted_domain` | Domain yang dilaporkan | +50 |
| `shortened_url` | `bit.ly`, `tinyurl.com`, `s.id` | +10 (reduced) |
| `shortened_url_expand_failed` | Shortener gagal di-expand | +15 |
| `suspicious_tld` | `.tk`, `.ml`, `.xyz`, `.click` | +15 |
| `urgency_keywords` | "segera", "buruan", "verifikasi" | +15 |
| `phishing_keywords` | "akun diblokir", "transfer", "OTP" | +20 |
| `caps_lock_abuse` | Lebih dari 50% huruf besar | +10 |
| `authority_impersonation` | "dari pihak kampus", "admin resmi" | +20 |

> **Catatan penting:** URL shortener **bukan otomatis indikator phishing**. Dosen dan mahasiswa sering menggunakan shortener (bit.ly, s.id) untuk berbagi link akademik. Sistem akan meng-expand shortened URL dan mengevaluasi domain tujuan. Jika tujuan adalah domain whitelisted (misal `classroom.google.com`), skor dikurangi -10 (bonus).

**Kata kunci phishing** yang dimonitor (dalam Bahasa Indonesia):
- Verifikasi: "verifikasi akun", "konfirmasi data", "update data"
- Ketakutan: "akun diblokir", "ditangguhkan", "bermasalah"
- Finansial: "transfer", "kirim uang", "bayar", "hadiah"
- Urgensi: "klik sekarang", "login sekarang", "segera"
- Data sensitif: "password", "OTP", "nomor rekening"

#### C. URL Analyzer (`url_analyzer.py`)

Mengekstrak dan menganalisis URL dari teks pesan menggunakan regex pattern:
- Mengenali format: `https://...`, `http://...`, `www.xxx`, `domain.tld/path`
- Normalisasi: menambahkan `https://` jika tidak ada, membersihkan tanda baca trailing
- Menghasilkan `URLInfo`: domain, TLD, HTTPS status, path depth, query parameters

#### D. URL Expansion & Security Check

> **Catatan:** Fungsi URL expansion sekarang terintegrasi dalam `URLSecurityChecker` (`src/detection/url_checker.py`). Lihat [Bagian 5.2](#52-url-security-checker) untuk dokumentasi lengkap.

URL expansion dilakukan secara **async** di message handler sebelum pipeline:

| Fitur | Detail |
|-------|--------|
| **Method** | HTTP HEAD request (fallback ke GET) |
| **Timeout** | 10 detik per URL |
| **Max Redirects** | 10 hops |
| **Shortener dikenali** | 17+ layanan (bit.ly, tinyurl.com, s.id, t.co, cutt.ly, dll) |

**Alur kerja baru (v0.3.0):**
1. **Handler** (`handlers.py`): Extract URLs → `check_urls_external_async()`
2. **URLSecurityChecker**: Expand URL → cek trusted domain → VirusTotal/heuristic
3. **Pipeline**: Pass `url_checks` dict ke triage
4. **Triage** (`triage.py`): Cek `url_checks` untuk URL dengan `source='whitelist'`
5. Jika URL trusted → langsung masuk `whitelisted_urls` (skip expansion lokal)
6. Jika semua URL whitelisted → `skip_llm=True` → **SAFE** di Stage 1

**Integrasi dengan Triage:**
```python
# Di triage.analyze()
for url, check_result in url_checks.items():
    if check_result.get('source') == 'whitelist':
        # URL sudah di-verify trusted → tambahkan ke whitelist
        trusted_urls_from_checker.add(url)

# URL trusted tidak perlu dicek lagi
for url in trusted_urls_from_checker:
    non_whitelisted_urls.remove(url)
    whitelisted_urls.append(url)
```

**Keuntungan integrasi:**
- Satu kali HTTP request untuk expansion + checking
- Trusted domain langsung bypass VirusTotal (hemat API quota)
- Redirect chain tersimpan untuk audit trail
- **Shortened URL → trusted domain = SAFE** (bukan SUSPICIOUS)

#### E. Behavioral Anomaly Detector (`behavioral.py`)

Mendeteksi penyimpangan dari baseline perilaku historis user:

| Anomali | Deskripsi | Deviation Score |
|---------|-----------|-----------------|
| `time_anomaly` | Posting di jam tidak biasa (>2 jam dari range tipikal) | 0.0-1.0 berdasarkan jarak |
| `length_anomaly` | Panjang pesan menyimpang >2σ dari rata-rata | 0.0-1.0 berdasarkan z-score |
| `first_time_url` | User belum pernah share URL sebelumnya | 0.7 (tetap) |
| `emoji_anomaly` | Penggunaan emoji berbeda >30% dari baseline | 0.0-1.0 berdasarkan deviasi |

#### Logika Keputusan Triage

```python
# Triage sekarang menerima url_checks dari URLSecurityChecker
triage_result = triage.analyze(
    message_text,
    message_timestamp,
    user_baseline,
    url_checks=url_checks  # ← NEW: Pre-computed URL check results
)

# Risk Score dihitung dari akumulasi bobot red flags + (bobot anomali × deviation_score)
# URL dengan source='whitelist' di url_checks langsung masuk whitelisted

if risk_score == 0 AND (semua URL whitelisted ATAU tidak ada URL):
    → SAFE (skip_llm = True)        ← Selesai di Stage 1
elif risk_score < 30:
    → LOW_RISK (skip_llm = False)   ← Lanjut ke Stage 2
else:
    → HIGH_RISK (skip_llm = False)  ← Lanjut ke Stage 2
```

**Contoh: bit.ly → Google Forms**
```
Input: https://bit.ly/PendaftaranSeminarTI

1. Handler calls check_urls_external_async()
2. URLSecurityChecker:
   - Expand: bit.ly → docs.google.com/forms/...
   - Check: accounts.google.com ∈ TRUSTED_DOMAINS
   - Return: {source: 'whitelist', risk_score: 0.0}
3. Pipeline passes url_checks to Triage
4. Triage sees source='whitelist' → add to whitelisted_urls
5. All URLs whitelisted → skip_llm=True
6. Result: SAFE (decided at Stage 1, no LLM calls)
```

---

### 4.2 Stage 2: Single-Shot LLM

**File:** `src/detection/single_shot/`
**Class:** `SingleShotClassifier`

Menggunakan **LLM provider yang terkonfigurasi** (`LLM_PROVIDER`) dengan satu kali panggilan API untuk mengklasifikasi pesan.

Provider yang didukung saat ini:
- `openrouter` (default) → model: `OPENROUTER_MODEL` (default: `google/gemini-2.5-flash-lite`)
- `deepseek` → model: `deepseek-chat`

#### Prompt Engineering

**System prompt** dirancang spesifik untuk konteks grup akademik Indonesia:
- Konteks: Mahasiswa TI UIR, diskusi akademik, tugas kuliah
- Model ancaman: Akun mahasiswa yang dikompromikan
- Output: JSON strict (`classification`, `confidence`, `reasoning`, `risk_factors`)
- Bahasa: Indonesia

**Analysis prompt** menyertakan konteks lengkap:
- Informasi pengirim (username, waktu bergabung)
- Baseline perilaku (rata-rata panjang pesan, jam posting tipikal, frekuensi URL)
- Detail pesan saat ini (waktu, panjang, isi)
- Hasil triage sebelumnya (risk score, triggered flags, URLs)

#### Parameter LLM

| Parameter | Default | Catatan |
|-----------|---------|--------|
| `model` | `deepseek-chat` (provider `deepseek`) | Untuk provider `openrouter`, gunakan `OPENROUTER_MODEL` |
| `temperature` | `0.3` | Rendah untuk konsistensi klasifikasi |
| `max_tokens` | `500` | Cukup untuk reasoning + JSON |
| `response_format` | `json_object` | Untuk stabilitas parsing, gunakan model yang mendukung structured output/`response_format` (sangat direkomendasikan untuk OpenRouter) |

#### Logika Eskalasi ke MAD

> **PENTING:** Single-shot bertindak sebagai **ROUTER**, bukan hakim akhir.
> Klasifikasi PHISHING **selalu** dieskalasi ke MAD untuk verifikasi.
> Ini mencegah masalah "yakin tapi salah" — false alert yang menyebabkan spam notifikasi ke admin.

```python
# Keputusan final di Stage 2 (TIDAK eskalasi):
if confidence >= 0.90 AND classification == "SAFE"     → Selesai

# SELALU eskalasi ke Stage 3 (MAD):
if classification == "PHISHING"                         → Eskalasi (SELALU, berapapun confidence)
if classification == "SUSPICIOUS"                       → Eskalasi (ragu)
if confidence < 0.70                                    → Eskalasi (ambigu)
if triage_risk >= 50 AND confidence < 0.80              → Eskalasi (risk tinggi + uncertainty)
```

**Rasional:** Single-shot LLM dapat memberikan confidence tinggi (≥85%) untuk klasifikasi PHISHING yang ternyata salah (false positive). Karena bot hanya melakukan flag_review (bukan auto-delete), false PHISHING = spam notifikasi ke admin. MAD dengan 3 agen memberikan verifikasi lebih akurat.

#### Fallback

Jika LLM gagal (timeout, API error), sistem menggunakan klasifikasi heuristic:
- HIGH_RISK triage → SUSPICIOUS (confidence 0.6)
- LOW_RISK triage → SUSPICIOUS (confidence 0.5)
- Selalu eskalasi ke MAD untuk verifikasi manual

---

### 4.3 Stage 3: Multi-Agent Debate (MAD)

**Files:**
- `src/detection/mad/` (MAD3)
- `src/detection/mad5/` (MAD5)

**Class utama:** `MultiAgentDebate` (varian `mad3` dan `mad5` memiliki implementasi orchestrator/aggregator terpisah)

Tahap terakhir menggunakan pendekatan **Multi-Agent Debate (MAD)** dan mendukung:
- **Multi-round debate** (default 2 ronde, dapat dikonfigurasi lebih dari 2)
- **Early termination** (default aktif): debat berhenti segera saat konsensus tercapai
- **Optional timeout**: debat berhenti jika melewati batas waktu total (opsional)

#### Varian MAD

| Varian | Agen | Catatan |
|--------|------|--------|
| `mad3` | 3 agen (Content/Security/Social) | Lebih ringan, cocok untuk baseline |
| `mad5` | 5 agen (detector/critic/defender/fact-checker/judge) | Lebih kaya peran, termasuk **judge** |

#### Agen MAD3 (3 Agen Spesialis)

| Agen | Fokus | Bobot Voting |
|------|-------|-------------|
| **Content Analyzer** | Pola linguistik, social engineering, deviasi gaya bahasa | 1.0 |
| **Security Validator** | Analisis URL, reputasi domain, evidence keamanan (VirusTotal) | 1.5 (tertinggi) |
| **Social Context Evaluator** | Konteks sosial akademik, perilaku historis, relevansi topik | 1.0 |

Setiap agen memiliki **system prompt unik** dan menghasilkan output JSON:
```json
{
  "stance": "PHISHING | SUSPICIOUS | LEGITIMATE",
  "confidence": 0.0-1.0,
  "key_arguments": ["argumen1", "argumen2"],
  "evidence": { /* domain-specific evidence */ }
}
```

#### Alur Debat (Multi-Round + Early Termination)

**Round 1 — Analisis Independen**
- Semua agen menganalisis pesan **secara paralel**
- Input: konten pesan, konteks pengirim, baseline, hasil triage, hasil single-shot, dan hasil URL check/VirusTotal

**Consensus Check (setiap ronde)**
```python
# Unanimous: semua agen sama → konsensus
if len(set(stances)) == 1:
    consensus = True

# Strong majority: mayoritas kuat + confidence minimum
if stance_count >= 2 AND avg_confidence >= 0.75:
    consensus = True
```

**Round 2..N — Deliberasi** (jika konsensus belum tercapai)
- Agen melihat argumen dari ronde sebelumnya
- Agen boleh mempertahankan atau mengubah stance berdasarkan bukti baru
- Stop condition:
  - `consensus` (early termination, default)
  - `max_rounds` (batas ronde)
  - `timeout` (opsional)

#### Weighted Voting Aggregation

```python
# Skor dihitung: weight × confidence untuk setiap agen
weighted_score = agent_weight × agent_confidence

# Normalisasi probabilitas phishing
phishing_prob = phishing_score / (phishing_score + legitimate_score)

# Keputusan berdasarkan threshold
if phishing_prob >= 0.65 → "PHISHING"
if phishing_prob <= 0.35 → "LEGITIMATE"
else                     → "SUSPICIOUS"
```

Security Validator memiliki bobot 1.5× karena evidence objektif (VirusTotal data) dianggap lebih reliable dibanding analisis subjektif.

#### Output Tambahan (Metadata Debat)

Hasil MAD menyertakan metadata untuk audit/debug:
- `rounds_executed`
- `round_summaries` (seluruh ronde yang dieksekusi)
- `stop_reason`: `consensus` | `max_rounds` | `timeout`
- `consensus_round` (jika konsensus tercapai)

---

## 5. Komponen Pendukung

### 5.1 LLM Client (DeepSeek + OpenRouter)

Sistem mendukung 2 provider LLM yang dipilih lewat environment variable `LLM_PROVIDER`.

#### A. DeepSeek

**File:** `src/llm/deepseek_client.py`  
**Class:** `DeepSeekClient`  
Model: `deepseek-chat` (OpenAI-compatible).

#### B. OpenRouter

**File:** `src/llm/openrouter_client.py`  
**Class:** `OpenRouterClient`  
Model: dikonfigurasi lewat `OPENROUTER_MODEL` (OpenAI-compatible via base URL OpenRouter).

Catatan penting:
- Untuk pipeline yang mengandalkan output JSON, **pilih model OpenRouter yang mendukung structured output/`response_format`** (contoh yang stabil pada evaluasi terbaru: `google/gemini-2.5-flash-lite`).
- Untuk free-tier OpenRouter, throttle/parallel tuning tersedia di `OPENROUTER_MAX_RPM` dan `OPENROUTER_PARALLEL`.

### 5.2 URL Security Checker

**File:** `src/detection/url_checker.py`
**Classes:** `VirusTotalChecker`, `URLSecurityChecker`

Sistem pengecekan URL 4-lapis yang komprehensif:

**Layer 1 — URL Expansion** (untuk shortened URLs):
| Parameter | Nilai |
|-----------|-------|
| **Method** | HTTP HEAD request (fallback ke GET) |
| **Timeout** | 10 detik per URL |
| **Max Redirects** | 10 hops |
| **Shortener dikenali** | 17+ layanan (bit.ly, tinyurl.com, s.id, t.co, cutt.ly, dll) |

Alur kerja:
1. Deteksi domain shortener (bit.ly, tinyurl.com, s.id, dll)
2. Follow redirect chain sampai destination akhir
3. Return `expanded_url` dan `redirect_chain` untuk analisis lebih lanjut
4. Hasil expansion digunakan untuk pengecekan domain tujuan

**Layer 2 — Trusted Domain Whitelist** (bypass VirusTotal):
Domain yang otomatis dianggap SAFE (risk score = 0.0):
- **Google Services**: google.com, docs.google.com, drive.google.com, meet.google.com, classroom.google.com, forms.google.com, youtube.com
- **Microsoft Services**: microsoft.com, office.com, outlook.com, teams.microsoft.com, sharepoint.com
- **Academic Platforms**: github.com, gitlab.com, zoom.us
- **Indonesian Academic**: uir.ac.id, kemdikbud.go.id, dikti.go.id
- **Communication**: linkedin.com, whatsapp.com, telegram.org

Jika URL (atau expanded URL) mengarah ke domain terpercaya → langsung return SAFE, skip VirusTotal.

**Layer 3 — Heuristic Check** (selalu berjalan, tidak memerlukan API):
- IP address sebagai domain (+0.3 risk)
- TLD mencurigakan dari dataset CSV 130+ entries (+0.1-0.4 berdasarkan severity)
- URL shortener terdeteksi (+0.2)
- Subdomain berlebihan (>3 level) (+0.15)
- Keyword mencurigakan dalam path (+0.1)
- Tidak HTTPS (+0.1)
- Karakter aneh / punycode domain (+0.2-0.25)

**Layer 4 — VirusTotal API v3** (jika API key tersedia dan bukan trusted domain):
- Mengecek URL analysis dan domain reputation
- Rate limiting: batch 4 URL per 15 detik (free tier)
- Hasil digabung dengan heuristic → gunakan risk score tertinggi
- Caching: hasil disimpan dalam memory untuk menghindari panggilan berulang

**URLCheckResult** menyertakan:
```python
@dataclass
class URLCheckResult:
    url: str                    # URL original
    expanded_url: str | None    # URL setelah follow redirect (jika ada)
    is_malicious: bool
    risk_score: float           # 0.0 (safe) - 1.0 (dangerous)
    source: str                 # "whitelist", "virustotal+heuristic", "heuristic"
    details: dict               # redirect_chain, VT stats, risk factors
```

**Dataset TLD mencurigakan** (`dataset/suspicious_tlds_list.csv`):
- Metadata: TLD, category, severity (Critical/High/Medium/Low), popularity
- Dimuat saat module import → tersedia untuk semua pengecekan

### 5.3 Database (Supabase)

**File:** `src/database/client.py`
**Project:** TelePhisDebate (Region: `ap-southeast-1`, PostgreSQL 17)

Menggunakan Supabase (PostgreSQL hosted) dengan 5 tabel. Semua tabel memiliki RLS (Row Level Security) enabled dengan policy `Service role has full access`.

#### Relasi Antar Tabel

```
users (1) ──────< messages (N) ──────< detection_logs (N)
                      │
                      └── url_cache (standalone, cache per URL)
                          api_usage (standalone, agregasi per hari)
```

| Foreign Key | Source | Target |
|-------------|--------|--------|
| `messages_user_id_fkey` | `messages.user_id` | `users.id` |
| `detection_logs_message_id_fkey` | `detection_logs.message_id` | `messages.id` |

#### Tabel `users`

Data pengguna Telegram dan baseline perilaku historis.

| Kolom | Tipe | Constraint | Default | Deskripsi |
|-------|------|-----------|---------|-----------|
| `id` | BIGSERIAL | **PK** | auto | ID internal |
| `telegram_user_id` | BIGINT | **UNIQUE, NOT NULL** | — | ID user Telegram |
| `username` | VARCHAR | nullable | — | Username Telegram |
| `first_name` | VARCHAR | nullable | — | Nama depan |
| `last_name` | VARCHAR | nullable | — | Nama belakang |
| `joined_group_at` | TIMESTAMPTZ | nullable | — | Waktu join grup |
| `baseline_metrics` | JSONB | nullable | *lihat bawah* | Metrik perilaku user |
| `baseline_updated_at` | TIMESTAMPTZ | nullable | — | Terakhir baseline diupdate |
| `created_at` | TIMESTAMPTZ | nullable | `now()` | Waktu record dibuat |
| `updated_at` | TIMESTAMPTZ | nullable | `now()` | Waktu record diupdate |

**Default `baseline_metrics`:**
```json
{
  "typical_hours": [],
  "total_messages": 0,
  "emoji_usage_rate": 0.0,
  "url_sharing_rate": 0.0,
  "total_urls_shared": 0,
  "avg_message_length": null,
  "avg_sentence_length": null,
  "caps_lock_frequency": 0.0
}
```

**Index:** `idx_users_telegram_user_id` (btree on `telegram_user_id`)

#### Tabel `messages`

Setiap pesan yang diproses oleh bot dan hasil klasifikasinya.

| Kolom | Tipe | Constraint | Default | Deskripsi |
|-------|------|-----------|---------|-----------|
| `id` | BIGSERIAL | **PK** | auto | ID internal |
| `telegram_message_id` | BIGINT | NOT NULL | — | ID pesan di Telegram |
| `telegram_chat_id` | BIGINT | NOT NULL | — | ID grup/chat Telegram |
| `user_id` | BIGINT | **FK → users.id**, nullable | — | Referensi ke pengirim |
| `content` | TEXT | nullable | — | Isi pesan (max 1000 chars) |
| `content_length` | INTEGER | nullable | — | Panjang karakter pesan |
| `timestamp` | TIMESTAMPTZ | NOT NULL | — | Waktu pesan dikirim |
| `urls_extracted` | TEXT[] | nullable | `'{}'` | Array URL yang ditemukan |
| `has_shortened_url` | BOOLEAN | nullable | `false` | Apakah ada shortened URL |
| `classification` | VARCHAR | nullable | — | Hasil: SAFE / SUSPICIOUS / PHISHING |
| `confidence` | NUMERIC | nullable | — | Confidence score (0.0–1.0) |
| `decided_by` | VARCHAR | nullable | — | Stage yang memutuskan: triage / single_shot / mad |
| `processing_time_ms` | INTEGER | nullable | — | Waktu proses total (ms) |
| `action_taken` | VARCHAR | nullable | — | Aksi: none / warn / flag_review |
| `created_at` | TIMESTAMPTZ | nullable | `now()` | Waktu record dibuat |

**Unique constraint:** `(telegram_chat_id, telegram_message_id)` — satu pesan per chat

**Index:**
- `idx_messages_timestamp` (btree on `timestamp` DESC)
- `idx_messages_classification` (btree on `classification`)
- `idx_messages_chat_id` (btree on `telegram_chat_id`)
- `idx_messages_user_id` (btree on `user_id`)

#### Tabel `detection_logs`

Log detail analisis per stage untuk setiap pesan, termasuk hasil triage, single-shot, dan MAD.

| Kolom | Tipe | Constraint | Default | Deskripsi |
|-------|------|-----------|---------|-----------|
| `id` | BIGSERIAL | **PK** | auto | ID internal |
| `message_id` | BIGINT | **FK → messages.id**, nullable | — | Referensi ke pesan |
| `stage` | VARCHAR | NOT NULL | — | Stage: triage / single_shot / mad |
| `stage_result` | JSONB | NOT NULL | — | Hasil lengkap semua stage (triage, single_shot, mad) |
| `tokens_input` | INTEGER | nullable | — | Jumlah token input ke LLM |
| `tokens_output` | INTEGER | nullable | — | Jumlah token output dari LLM |
| `processing_time_ms` | INTEGER | nullable | — | Waktu proses (ms) |
| `created_at` | TIMESTAMPTZ | nullable | `now()` | Waktu record dibuat |

**Index:**
- `idx_detection_logs_message_id` (btree on `message_id`)
- `idx_detection_logs_stage` (btree on `stage`)

**Contoh `stage_result` (stage=mad):**
```json
{
  "triage": { "risk_score": 45, "classification": "HIGH_RISK", "flags": [...] },
  "single_shot": { "classification": "PHISHING", "confidence": 0.72, ... },
  "mad": {
    "decision": "PHISHING",
    "confidence": 0.85,
    "rounds_executed": 2,
    "consensus_reached": true,
    "agent_votes": { "content_analyzer": "PHISHING", "security_validator": "PHISHING", "social_context_evaluator": "SUSPICIOUS" },
    "round_1_summary": [...],
    "round_2_summary": [...]
  }
}
```

#### Tabel `url_cache`

Cache hasil pengecekan reputasi URL untuk menghindari panggilan API berulang.

| Kolom | Tipe | Constraint | Default | Deskripsi |
|-------|------|-----------|---------|-----------|
| `id` | BIGSERIAL | **PK** | auto | ID internal |
| `url` | TEXT | **UNIQUE, NOT NULL** | — | URL lengkap |
| `domain` | VARCHAR | nullable | — | Domain yang diekstrak |
| `reputation_score` | NUMERIC | nullable | — | Skor reputasi (0.0=aman, 1.0=berbahaya) |
| `is_shortened` | BOOLEAN | nullable | `false` | Apakah URL shortener |
| `is_whitelisted` | BOOLEAN | nullable | `false` | Apakah domain terpercaya |
| `is_blacklisted` | BOOLEAN | nullable | `false` | Apakah domain blacklisted |
| `virustotal_result` | JSONB | nullable | — | Hasil analisis VirusTotal |
| `safe_browsing_result` | JSONB | nullable | — | Hasil Google Safe Browsing |
| `last_checked` | TIMESTAMPTZ | nullable | `now()` | Terakhir dicek |
| `check_count` | INTEGER | nullable | `1` | Berapa kali URL ini dicek |
| `created_at` | TIMESTAMPTZ | nullable | `now()` | Waktu record dibuat |

**Index:**
- `idx_url_cache_url` (btree on `url`)
- `idx_url_cache_domain` (btree on `domain`)
- `idx_url_cache_last_checked` (btree on `last_checked`)

#### Tabel `api_usage`

Agregasi penggunaan DeepSeek API per hari dengan breakdown per stage.

| Kolom | Tipe | Constraint | Default | Deskripsi |
|-------|------|-----------|---------|-----------|
| `id` | BIGSERIAL | **PK** | auto | ID internal |
| `date` | DATE | **UNIQUE, NOT NULL** | — | Satu record per hari |
| `total_requests` | INTEGER | nullable | `0` | Total request API hari itu |
| `total_tokens_input` | INTEGER | nullable | `0` | Total token input |
| `total_tokens_output` | INTEGER | nullable | `0` | Total token output |
| `triage_requests` | INTEGER | nullable | `0` | Pesan selesai di triage |
| `single_shot_requests` | INTEGER | nullable | `0` | Pesan selesai di single-shot |
| `single_shot_tokens` | INTEGER | nullable | `0` | Token digunakan single-shot |
| `mad_requests` | INTEGER | nullable | `0` | Pesan masuk MAD |
| `mad_tokens` | INTEGER | nullable | `0` | Token digunakan MAD |
| `estimated_cost_usd` | NUMERIC | nullable | `0` | Kolom legacy untuk kompatibilitas historis |
| `created_at` | TIMESTAMPTZ | nullable | `now()` | Waktu record dibuat |
| `updated_at` | TIMESTAMPTZ | nullable | `now()` | Terakhir diupdate |

**Index:** `idx_api_usage_date` (btree on `date` DESC)

---

## 6. Telegram Bot

### 6.1 Bot Core

**File:** `src/bot/bot.py`
**Class:** `TelePhisBot`

Bot utama yang menangani:

| Command | Fungsi |
|---------|--------|
| `/start` | Pesan selamat datang + deskripsi fitur |
| `/help` | Panduan penggunaan lengkap |
| `/status` | Status bot + statistik (session + database + inference activity) |
| `/stats` | Statistik deteksi persisten dari DB (distribusi, stage breakdown, token/request profile) |
| `/check <teks>` | Analisis manual dengan VirusTotal URL check, token breakdown, triage detail, LLM reasoning, MAD votes |

**Detail output `/status`:**
- Session stats (safe/suspicious/phishing/deleted)
- Database all-time stats (total messages, classification breakdown)
- Inference activity (input/output tokens, total requests)
- Config status (logging enabled, admin notifications)

**Detail output `/stats`:**
- Distribusi klasifikasi (persentase) dari database
- Stage breakdown: berapa pesan diproses oleh Triage, Single-Shot LLM, dan MAD
- Inference activity: total requests, token breakdown, avg tokens/msg
- Fallback ke session stats jika database tidak tersedia

**Detail output `/check`:**
- Klasifikasi, confidence, stage (dengan nama yang user-friendly)
- Token breakdown (input + output)
- Triage risk score dan triggered flags
- VirusTotal URL scan results (per URL, jumlah deteksi malicious)
- LLM reasoning (jika melewati Stage 2)
- MAD agent votes (jika melewati Stage 3)

**Message filters yang aktif:**
- `TEXT & ~COMMAND` — semua pesan teks non-command
- `CAPTION` — pesan dengan caption (foto, video, dokumen)
- `FORWARDED` — pesan yang di-forward

### 6.2 Message Handler

**File:** `src/bot/handlers.py`
**Class:** `MessageHandler`

Alur pemrosesan pesan:

1. **Filter**: Skip bot messages, commands, pesan sangat pendek (<10 karakter)
2. **Extract**: Ambil teks (dari text, caption, atau forwarded message)
3. **Context**: Ambil sender info + user baseline dari database
4. **Register User**: Upsert metadata user ke tabel `users` (best-effort)
5. **URL Check**: Cek URL secara async dengan VirusTotal (jika ada URL)
6. **Pipeline**: Jalankan `PhishingDetectionPipeline.process_message()`
7. **Action**: Eksekusi aksi berdasarkan hasil (via `BotActions`)
8. **Log**: Simpan ke Supabase (`messages` + `detection_logs` + `api_usage`)
9. **Stats**: Update statistik internal session

**User Registration (`_ensure_user_registered`):**
- Handler melakukan upsert metadata user (best-effort) agar baseline bisa dikaitkan ke pengirim.
- Jika ada mismatch skema kolom antar environment, proses registrasi user di-skip tanpa menghentikan pipeline deteksi.
- User baru tetap diharapkan memiliki `baseline_metrics` awal kosong.

**Inference Activity Tracking:**
- Setiap pesan yang melewati LLM (Stage 2/3) otomatis dicatat ke tabel `api_usage`
- Token input/output dilacak terpisah dari `DetectionResult`
- Token usage dilacak untuk observability dan evaluasi performa
- Data diagregasi per hari dengan breakdown per stage (triage, single_shot, mad)

### 6.3 Bot Actions

**File:** `src/bot/actions.py`
**Class:** `BotActions`

3 jenis aksi yang dilakukan berdasarkan klasifikasi:

| Aksi | Kondisi | Perilaku |
|------|---------|----------|
| `none` | SAFE | Tidak ada aksi |
| `warn` | SUSPICIOUS (confidence ≥ 60%) | Reply peringatan ke pesan |
| `flag_review` | PHISHING (semua confidence) / SUSPICIOUS (conf < 60%) | Alert di grup + notifikasi detail ke admin |

> **Bot TIDAK melakukan auto-delete.** Semua deteksi PHISHING menggunakan `flag_review` — admin menentukan penghapusan secara manual. Kode auto-delete telah dihapus dari codebase.

**Friendly Stage Names (`STAGE_DISPLAY`):**

| Internal | Display |
|----------|----------|
| `triage` | Rule-Based Triage |
| `single_shot` | Single-Shot LLM |
| `mad` | Multi-Agent Debate |

**Fitur notifikasi admin** menyertakan:
- Identitas pengirim (username, user_id)
- Isi pesan (truncated 500 chars)
- Detail analisis lengkap per stage (dengan HTML formatting)
- **Processing time** (ms)
- **Token breakdown** (input, output, total)
- **Risk/context details** per stage (triage flags, reasoning, votes)
- Link langsung ke pesan di grup
- MAD agent votes (jika ada): `Content Analyzer: X | Security Validator: Y | Social Context: Z`
- Peringatan di grup otomatis dihapus setelah 10 menit

---

## 7. Dashboard Monitoring

**File:** `src/dashboard/app.py`
**Entry Point:** `run_dashboard.py`

Dashboard web berbasis Flask untuk memonitor aktivitas bot secara real-time.

### REST API Endpoints

| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/` | GET | Halaman utama dashboard |
| `/evaluation` | GET | Halaman hasil evaluasi terbaru |
| `/evaluation/compare` | GET | Halaman perbandingan MAD3 vs MAD5 |
| `/evaluation/modes` | GET | Halaman perbandingan mode pipeline vs MAD-only |
| `/api/evaluation` | GET | Ambil run evaluasi terbaru (metrics + details) |
| `/api/evaluation/compare?eval_mode=` | GET | Perbandingan MAD3 vs MAD5 (`pipeline` / `mad_only`) |
| `/api/evaluation/modes?mad_mode=` | GET | Perbandingan mode untuk varian MAD (`mad3` / `mad5`) |
| `/api/evaluation/list` | GET | Daftar semua run evaluasi yang tersedia |
| `/api/stats` | GET | Statistik keseluruhan (total, safe, suspicious, phishing) |
| `/api/stats/today` | GET | Statistik hari ini |
| `/api/stats/activity?range=` | GET | Distribusi aktivitas (range: `24h`, `7d`, `30d`) |
| `/api/stats/stages` | GET | Statistik per stage (count, avg tokens, avg time) |
| `/api/detections/recent` | GET | 50 deteksi terbaru |
| `/api/detections/phishing` | GET | 20 deteksi phishing terbaru |
| `/api/usage` | GET | Aktivitas inferensi (tokens/requests/stage breakdown, termasuk field cost legacy) |
| `/api/debates/recent` | GET | 10 debat MAD terbaru (detail per agen) |
| `/api/debate/<id>` | GET | Detail debat spesifik |
| `/api/messages/recent` | GET | 20 pesan terbaru yang diproses |

### Fitur Dashboard UI

| Section | Fitur |
|---------|-------|
| **Stat Cards** | 4 kartu: Safe, Suspicious, Phishing, Total |
| **Detection Rate** | Persentase pesan terdeteksi mencurigakan/phishing |
| **Activity Chart** | Grafik aktivitas dengan range selector (24 Jam / 1 Minggu / 1 Bulan) |
| **Stage Performance** | 3 kartu stage (Triage, Single-Shot, MAD) dengan avg tokens & time |
| **Recent Phishing** | Tabel deteksi phishing terbaru |
| **Debate History** | Kartu collapsible per debat MAD — klik untuk expand detail agen |
| **Recent Messages** | Tabel scrollable semua pesan yang diproses |
| **Inference Activity** | 3 kartu (Input Tokens, Output Tokens, API Requests) |
| **Evaluation Suite** | Halaman `/evaluation`, `/evaluation/compare`, `/evaluation/modes`, `/evaluation/providers`, dan `/evaluation/runs` |

**Fitur teknis:**
- Auto-refresh setiap 30 detik
- State debate cards yang di-expand dipertahankan saat refresh
- Icon library: Iconoir v7.11.0 (CSS-only, tanpa JavaScript)
- Design: Brutalism black & white, font JetBrains Mono
- Responsive layout untuk mobile

### Resource Profiling

Dashboard menampilkan profil aktivitas inferensi:

| Item | Keterangan |
|------|------------|
| Input tokens | Total token input dari seluruh inferensi |
| Output tokens | Total token output dari seluruh inferensi |
| API requests | Jumlah request inferensi yang tercatat |
| Cost/pricing fields | Tetap tersedia di `/api/usage` sebagai data legacy (tidak ditonjolkan di UI utama) |

---

## 8. Konfigurasi

**File:** `src/config.py`
**Class:** `Config`

Semua konfigurasi dimuat dari environment variables (file `.env`):

```env
# === Wajib ===
TELEGRAM_BOT_TOKEN=         # Token dari @BotFather
LLM_PROVIDER=openrouter     # Pilih provider LLM: openrouter (default) / deepseek
MAD_MODE=mad3               # Mode MAD untuk runtime bot: mad3 (default) / mad5
DEEPSEEK_API_KEY=           # API key DeepSeek (wajib jika LLM_PROVIDER=deepseek)
DEEPSEEK_BASE_URL=          # Default: https://api.deepseek.com
OPENROUTER_API_KEY=         # API key OpenRouter (wajib jika LLM_PROVIDER=openrouter)
OPENROUTER_BASE_URL=        # Default: https://openrouter.ai/api/v1
OPENROUTER_MODEL=           # Default: google/gemini-2.5-flash-lite (support structured output)
OPENROUTER_SITE_URL=        # Opsional (recommended) untuk attribution header
OPENROUTER_APP_NAME=        # Opsional (recommended) untuk attribution header
# OpenRouter throttling (membantu menghindari 429)
OPENROUTER_MAX_RPM=12       # Default 12 request/menit (free tier friendly)
OPENROUTER_PARALLEL=false   # Default false: jalankan debat lebih serial untuk mengurangi burst
SUPABASE_URL=               # URL project Supabase
SUPABASE_KEY=               # Service role key Supabase

# === Opsional ===
ADMIN_CHAT_ID=              # Chat ID admin untuk notifikasi
VIRUSTOTAL_API_KEY=         # API key VirusTotal (free tier)
GOOGLE_SAFE_BROWSING_KEY=   # API key Google Safe Browsing (belum diimplementasi)

# === MAD (Multi-Agent Debate) ===
MAD_MAX_ROUNDS=2            # Default 2. Bisa dinaikkan (mis. 3..5) untuk debat lebih panjang
MAD_EARLY_TERMINATION=true  # Default true. Stop segera jika konsensus tercapai
MAD_MAX_TOTAL_TIME_MS=      # Opsional. Batas waktu total debat (ms). Kosong = tanpa timeout

# === Rate Limiting ===
MAX_REQUESTS_PER_MINUTE=60
DEEPSEEK_MONTHLY_BUDGET_USD=5.0

# === Debug ===
DEBUG=False
LOG_LEVEL=INFO
```

Validasi konfigurasi wajib dilakukan saat startup via `Config.validate()`.

---

## 9. Alur Data End-to-End

```
Pesan masuk di grup Telegram
         │
         ▼
[1] MessageHandler.handle_message()
    ├── Filter: skip bot, command, <10 chars
    ├── Extract: text / caption / forwarded
    ├── Get user baseline dari Supabase
    └── Check URLs async via VirusTotal
         │
         ▼
[2] PhishingDetectionPipeline.process_message()
    │
    ├── Stage 1: RuleBasedTriage.analyze()
    │   ├── URLAnalyzer   → extract URLs
    │   ├── WhitelistChecker → cek domain terpercaya
    │   ├── URLExpander → expand shortened URLs, evaluasi domain tujuan
    │   ├── BlacklistChecker → cek red flags (URL & text)
    │   ├── BehavioralAnomalyDetector → cek deviasi perilaku
    │   └── Hitung risk_score → classify (SAFE/LOW_RISK/HIGH_RISK)
    │       │
    │       ├── SAFE (skip_llm=True) ──────────────────────────→ DONE ✅
    │       └── LOW_RISK / HIGH_RISK ──→ Stage 2
    │
    ├── Stage 2: SingleShotClassifier.classify()  [ROUTER, bukan hakim akhir]
    │   ├── Construct prompt (konteks pengirim + baseline + triage)
    │   ├── LLM API call (provider dari `LLM_PROVIDER`, temperature=0.3, json_mode jika didukung)
    │   ├── Parse JSON response
    │   └── Evaluasi eskalasi
    │       │
    │       ├── High conf SAFE (≥90%) ─────────────────────────→ DONE ✅
    │       ├── PHISHING (any confidence) ─────────────────────→ Stage 3 ⚠️
    │       └── Low conf / SUSPICIOUS / High risk ──→ Stage 3
    │
    └── Stage 3: MultiAgentDebate.run_debate()
        ├── Round 1: analisis independen (paralel)
        │
        ├── Round 2..N: deliberasi (jika belum konsensus)
        │   ├── Early termination: stop segera jika konsensus tercapai
        │   ├── Stop jika mencapai MAD_MAX_ROUNDS
        │   └── Opsional stop jika mencapai MAD_MAX_TOTAL_TIME_MS
        │
        └── VotingAggregator.aggregate_rounds()
            └── Keputusan final dari ronde terakhir + akumulasi token/time lintas ronde
         │
         ▼
[3] BotActions.execute_action()
    ├── SAFE         → none (tidak ada aksi)
    ├── SUSPICIOUS   → warn (peringatan) / flag_review
    └── PHISHING     → flag_review (alert grup + notif admin)
         │
         ▼
[4] Log ke Supabase (messages + detection_logs)
```

---

## 10. Testing

### Test Files

| File | Cakupan | Deskripsi |
|------|---------|-----------|
| `test_connections.py` | Integrasi | Tes koneksi ke Telegram, provider LLM (DeepSeek/OpenRouter), Supabase, VirusTotal |
| `test_bot.py` | Integrasi | Tes inisialisasi bot + koneksi Telegram |
| `test_triage.py` | Unit | Tes Stage 1 (whitelist, blacklist, behavioral) |
| `test_single_shot.py` | Unit | Tes Stage 2 (klasifikasi LLM) |
| `test_mad.py` | Unit | Tes Stage 3 (debat multi-agen) |
| `test_pipeline.py` | End-to-end | Tes alur lengkap 3 stage dengan 7 test cases |
| `tests/test_url_checker.py` | Unit | Tes URL checker (VirusTotal + heuristic) |

### Test Cases Pipeline (`test_pipeline.py`)

| # | Pesan | Expected | Stage |
|---|-------|----------|-------|
| 1 | URL classroom.google.com | SAFE | triage |
| 2 | URL zoom.us | SAFE | triage |
| 3 | "Jangan lupa deadline besok" (tanpa URL) | SAFE | triage |
| 4 | "URGENT!!! Akun diblokir! bit.ly/verify" | PHISHING | single_shot |
| 5 | "MENANG undian 50 JUTA! hadiah.tk" | PHISHING | single_shot |
| 6 | "Lowongan magang, gaji 5jt. bit.ly/magang" | SUSPICIOUS | mad |
| 7 | "Beasiswa S2 Jepang, gratis! scholarship.xyz" | SUSPICIOUS | mad |

### Testing Komparatif: MAD3 vs MAD5

Selain unit/integration test, sistem juga diuji dengan **perbandingan varian debate**:
- `mad3` (3 agent)
- `mad5` (5 agent)

Evaluasi dilakukan pada dua mode:
- `pipeline`: alur lengkap Triage -> Single-Shot -> MAD
- `mad_only`: keputusan akhir langsung oleh MAD (triage hanya sebagai context)

Contoh command:

```bash
# Dataset akademik (format: delimiter ';', kolom: chat/tipe)
DATASET=data/dataset_mixed_akademik.csv
TEXTCOL=chat
LABELCOL=tipe
DELIM=";"
LIMIT=200

# DeepSeek (pipeline)
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/deepseek/mad3
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/deepseek/mad5

# OpenRouter (pipeline) - pastikan OPENROUTER_MODEL diset (mis. google/gemini-2.5-flash-lite)
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/openrouter/mad3
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/openrouter/mad5

# DeepSeek (mad_only)
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/deepseek/mad3_mad_only
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/deepseek/mad5_mad_only

# OpenRouter (mad_only)
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/openrouter/mad3_mad_only
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit "$LIMIT" --output results/openrouter/mad5_mad_only
```

Hasil komparatif dapat dilihat di dashboard:
- `/evaluation/compare` -> MAD3 vs MAD5 (mode yang sama)
- `/evaluation/modes` -> Pipeline vs MAD-only (untuk varian MAD yang dipilih)
- `/evaluation/providers` -> DeepSeek vs OpenRouter
- `/evaluation/runs` -> Browse semua run evaluasi (historical)

### Hasil Evaluasi Terbaru (Dataset Mixed Akademik, 200 pesan)

Dataset: `data/dataset_mixed_akademik.csv` (limit 200)  
Distribusi label: `SAFE=127`, `PHISHING=45`, `SUSPICIOUS=28`

Ringkasan (binary metric: PHISHING vs non-PHISHING, detection_rate = PHISHING|SUSPICIOUS terdeteksi dari PHISHING expected):

| Provider | Model | Mode | MAD | Acc | F1 | Precision | Recall | Avg time/msg |
|---------|-------|------|-----|-----|----|-----------|--------|--------------|
| DeepSeek | `deepseek-chat` | pipeline | mad3 | 90.5% | 87.5% | 82.4% | 93.3% | 4242ms |
| DeepSeek | `deepseek-chat` | pipeline | mad5 | 86.0% | 80.4% | 67.2% | 100% | 6214ms |
| OpenRouter | `google/gemini-2.5-flash-lite` | pipeline | mad3 | 92.5% | 90.1% | 89.1% | 91.1% | 7938ms |
| OpenRouter | `google/gemini-2.5-flash-lite` | pipeline | mad5 | 91.5% | 88.4% | 84.0% | 93.3% | 14539ms |
| DeepSeek | `deepseek-chat` | mad_only | mad3 | 90.5% | 87.2% | 83.7% | 91.1% | 5752ms |
| DeepSeek | `deepseek-chat` | mad_only | mad5 | 85.5% | 82.2% | 71.0% | 97.8% | 7593ms |
| OpenRouter | `google/gemini-2.5-flash-lite` | mad_only | mad3 | 95.0% | 93.2% | 95.4% | 91.1% | 5219ms |
| OpenRouter | `google/gemini-2.5-flash-lite` | mad_only | mad5 | 89.0% | 90.1% | 89.1% | 91.1% | 6481ms |

Sumber run (folder `results/`):
- DeepSeek: `results/deepseek/*`
- OpenRouter: `results/openrouter/*`

---

## 11. Dependencies

| Package | Versi | Kegunaan |
|---------|-------|----------|
| `python-telegram-bot` | 21.10 | Framework bot Telegram (async) |
| `openai` | 1.59.9 | Client LLM (DeepSeek/OpenRouter, OpenAI-compatible API) |
| `supabase` | 2.11.0 | Client database Supabase (PostgreSQL) |
| `requests` | 2.32.3 | HTTP requests (sync) |
| `httpx` | 0.28.1 | HTTP client async (parallel agent calls) |
| `aiohttp` | 3.11.11 | Async HTTP untuk VirusTotal API |
| `python-dotenv` | 1.0.1 | Load environment variables dari `.env` |
| `validators` | 0.34.0 | Validasi URL |
| `tldextract` | 5.1.3 | Ekstraksi komponen domain |
| `pydantic` | 2.10.5 | Data validation |
| `tenacity` | 9.0.0 | Retry logic dengan exponential backoff |
| `python-dateutil` | 2.9.0 | Utilitas datetime untuk baseline analysis |
| `pytest` | 8.3.4 | Framework unit testing |
| `pytest-asyncio` | 0.25.2 | Support testing async |
| `flask` | — | Web framework untuk dashboard |
| `flask-cors` | — | CORS support untuk dashboard API |

---

## 12. Cara Menjalankan

### Prerequisites

1. Python 3.11+
2. Virtual environment (venv)
3. File `.env` dengan konfigurasi lengkap

### Setup

```bash
# Clone dan setup
cd TelePhisDebate
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Menjalankan Bot

```bash
# Pilih mode MAD runtime bot di .env:
# MAD_MODE=mad3  atau  MAD_MODE=mad5

# Normal mode
python main.py

# Debug mode
python main.py --debug

# Tanpa database logging
python main.py --no-db

# Dengan admin chat ID
python main.py --admin-chat 123456789
```

### Menjalankan Dashboard

```bash
# Default (localhost:5000)
python run_dashboard.py

# Custom host/port
python run_dashboard.py --host 0.0.0.0 --port 8080 --debug
```

### Menjalankan Test

```bash
# Test koneksi semua API
python test_connections.py

# Test inisialisasi bot
python test_bot.py

# Test pipeline end-to-end
python test_pipeline.py

# Test per stage
python test_triage.py
python test_single_shot.py
python test_mad.py

# Unit tests
pytest tests/
```

---

## Catatan Pengembangan

### Resource Management
- Fokus utama pada kualitas deteksi dan stabilitas waktu proses
- Stage 2 menggunakan ~300-500 token per pesan
- Stage 3 menggunakan ~2000-4000 token per pesan (6 panggilan API)
- Aggressive caching untuk URL checks

### Keamanan
- Bot TIDAK melakukan auto-delete (kode telah dihapus, semua PHISHING → flag_review)
- Admin memutuskan penghapusan secara manual
- Fallback ke heuristic jika LLM gagal (tidak pernah gagal total)
- Peringatan di grup auto-delete setelah 10 menit untuk menjaga grup tetap bersih

### Limitasi
- Baseline metrics memerlukan data historis sufficient
- VirusTotal free tier: 4 requests/menit
- Tidak mendeteksi phishing via gambar (hanya teks/caption)
- Round 2 MAD menggunakan temperature rendah yang dapat menyebabkan "groupthink"

---

## 13. Perhitungan dan Formula yang Digunakan

Bagian ini menjabarkan **seluruh perhitungan matematis dan logika scoring** yang digunakan dalam sistem deteksi phishing TelePhisDebate, dari Stage 1 hingga Stage 3.

---

### 13.1 Stage 1 — Triage Risk Score

**File:** `src/detection/triage/triage.py`

Risk score dihitung dari akumulasi **bobot red flags** yang terdeteksi. Semakin tinggi risk score, semakin mencurigakan pesan tersebut.

#### Formula Utama

$$
\text{risk\_score} = \sum_{i=1}^{n} W_{\text{flag}_i} + \sum_{j=1}^{m} \left( W_{\text{anomaly}_j} \times D_{\text{anomaly}_j} \right) + \sum_{k=1}^{p} B_k
$$

di mana:
- $W_{\text{flag}_i}$ = bobot red flag ke-$i$ (dari tabel bobot)
- $W_{\text{anomaly}_j}$ = bobot anomali perilaku ke-$j$
- $D_{\text{anomaly}_j}$ = deviation score anomali ke-$j$ (0.0–1.0)
- $B_k$ = bonus/penalti ke-$k$ (bisa negatif, misal shortener → whitelisted)
- $n$ = jumlah red flags terdeteksi
- $m$ = jumlah anomali perilaku terdeteksi
- $p$ = jumlah bonus yang berlaku

Hasil akhir dibatasi:

$$
\text{risk\_score}_{\text{final}} = \max\!\Big(0,\;\min(\text{risk\_score}, 100)\Big)
$$

#### Tabel Bobot Red Flags

| Red Flag | Simbol | Bobot ($W$) |
|----------|--------|-------------|
| Domain di-blacklist | `blacklisted_domain` | +50 |
| Kata kunci phishing terdeteksi | `phishing_keywords` | +20 |
| Impersonasi otoritas | `authority_impersonation` | +20 |
| TLD mencurigakan | `suspicious_tld` | +15 |
| Kata kunci urgensi (≥2 kata) | `urgency_keywords` | +15 |
| Shortener gagal di-expand | `shortened_url_expand_failed` | +15 |
| CAPS LOCK berlebihan (>50%) | `caps_lock_abuse` | +10 |
| Shortened URL (tujuan bukan whitelist) | `shortened_url` | +10 |
| Pertama kali share URL | `first_time_url` | +10 |
| Anomali waktu posting | `time_anomaly` | +10 |
| Anomali panjang pesan | `length_anomaly` | +10 |
| Tanda baca berlebihan | `excessive_punctuation` | +5 |
| Anomali penggunaan emoji | `emoji_anomaly` | +5 |

#### Bonus (Bisa Negatif)

| Kondisi | Bonus ($B$) |
|---------|-------------|
| Shortened URL → domain tujuan whitelisted | −10 (per URL) |

#### Contoh Perhitungan

**Pesan:** `"URGENT!! Buruan klik bit.ly/abc123 sebelum akun diblokir!!!"`

| Deteksi | Bobot |
|---------|-------|
| `shortened_url` (bit.ly terdeteksi, expand berhasil → domain unknown) | +10 |
| `urgency_keywords` ("urgent", "buruan" = 2 kata) | +15 |
| `phishing_keywords` ("akun diblokir") | +20 |
| `caps_lock_abuse` ("URGENT" = sebagian besar caps) | +10 |
| `excessive_punctuation` ("!!" dan "!!!") | +5 |
| **Total** | **60** |

Klasifikasi: $60 \geq 30$ → **HIGH_RISK** → lanjut ke Stage 2.

**Pesan:** `"Cek materi di bit.ly/materi-kuliah"`

| Deteksi | Bobot |
|---------|-------|
| `shortened_url` (bit.ly terdeteksi, expand → `classroom.google.com`) | +10 |
| Bonus: tujuan whitelisted | −10 |
| **Total** | **0** |

Klasifikasi: risk = 0, semua URL whitelisted → **SAFE** → selesai di Stage 1.

#### Threshold Klasifikasi Triage

$$
\text{classification} = 
\begin{cases}
\textbf{SAFE} & \text{if } \text{risk\_score} = 0 \;\wedge\; (\text{all\_whitelisted} \;\vee\; \neg\text{has\_urls}) \\
\textbf{LOW\_RISK} & \text{if } \text{risk\_score} < 30 \\
\textbf{HIGH\_RISK} & \text{if } \text{risk\_score} \geq 30
\end{cases}
$$

---

### 13.2 Deteksi Anomali Perilaku (Behavioral)

**File:** `src/detection/triage/behavioral.py`

Anomali perilaku menghitung **deviation score** ($D$) untuk setiap jenis penyimpangan dari baseline historis user. Deviation score berskala 0.0–1.0 dan dikalikan dengan bobot anomali saat dijumlahkan ke risk score.

#### A. Time Anomaly — Jarak Waktu Posting

Menghitung jarak (dalam jam) antara waktu posting saat ini dan jam posting tipikal user, dengan memperhitungkan circular distance (misal jam 23 dan jam 1 berjarak 2, bukan 22).

$$
d_h = \min_{h_t \in \text{typical\_hours}} \min\Big( |h_c - h_t|, \; 24 - |h_c - h_t| \Big)
$$

di mana $h_c$ = jam posting saat ini, $h_t$ = setiap jam tipikal user.

Anomali terdeteksi jika $d_h \geq 2$ jam.

$$
D_{\text{time}} = \min\!\left(\frac{d_h}{12}, \; 1.0\right)
$$

**Contoh:** User biasa posting jam 8–21. Pesan dikirim jam 3 pagi:
- $d_h = \min(|3-8|, 24-|3-8|) = \min(5, 19) = 5$
- $D_{\text{time}} = \min(5/12, 1.0) = 0.417$
- Kontribusi ke risk: $10 \times 0.417 = 4$ poin

#### B. Length Anomaly — Z-Score Panjang Pesan

Menggunakan z-score untuk mengukur seberapa jauh panjang pesan dari rata-rata historis user.

$$
z = \frac{|L_c - \bar{L}|}{\sigma_L}
$$

di mana:
- $L_c$ = panjang pesan saat ini (karakter)
- $\bar{L}$ = rata-rata panjang pesan user
- $\sigma_L$ = standar deviasi (jika tidak tersedia, diestimasi sebagai $0.3 \times \bar{L}$)

Anomali terdeteksi jika $z \geq 2.0$.

$$
D_{\text{length}} = \min\!\left(\frac{z}{5}, \; 1.0\right)
$$

**Contoh:** User rata-rata 120 karakter ($\sigma = 36$). Pesan saat ini 300 karakter:
- $z = |300 - 120| / 36 = 5.0$
- $D_{\text{length}} = \min(5/5, 1.0) = 1.0$
- Kontribusi ke risk: $10 \times 1.0 = 10$ poin

#### C. First-Time URL — Anomali Tetap

Jika user belum pernah share URL sebelumnya (dari baseline $\geq 10$ pesan):

$$
D_{\text{first\_url}} = 0.7 \quad (\text{konstanta})
$$

Kontribusi ke risk: $10 \times 0.7 = 7$ poin.

#### D. Emoji Anomaly — Deviasi Relatif

$$
\text{diff} = 
\begin{cases}
R_{\text{emoji\_current}} & \text{if } R_{\text{emoji\_baseline}} = 0 \\
\frac{|R_{\text{emoji\_current}} - R_{\text{emoji\_baseline}}|}{\max(R_{\text{emoji\_baseline}}, 0.01)} & \text{otherwise}
\end{cases}
$$

di mana $R$ = emoji rate (jumlah emoji / panjang teks).

Anomali terdeteksi jika $\text{diff} \geq 0.3$ (30% deviasi).

$$
D_{\text{emoji}} = \min(\text{diff}, \; 1.0)
$$

#### E. Emoji Rate — Perhitungan

$$
R_{\text{emoji}} = \frac{\text{jumlah\_karakter\_emoji}}{\text{panjang\_total\_teks}}
$$

Emoji dideteksi menggunakan regex Unicode range: `U+1F600-1F64F`, `U+1F300-1F5FF`, `U+1F680-1F6FF`, `U+1F1E0-1F1FF`, dll.

---

### 13.3 Blacklist — CAPS Lock Ratio

**File:** `src/detection/triage/blacklist.py`

$$
R_{\text{caps}} = \frac{\text{jumlah\_huruf\_besar}}{\text{jumlah\_total\_huruf}}
$$

Red flag `caps_lock_abuse` aktif jika $R_{\text{caps}} > 0.5$ (lebih dari 50% huruf berupa kapital).

**Urgency keywords severity** (dinamis):

$$
\text{severity}_{\text{urgency}} = \min(4 + \text{count}, \; 8)
$$

**Phishing keywords severity:**

$$
\text{severity}_{\text{phishing}} = \min(5 + |\text{matched\_keywords}|, \; 9)
$$

---

### 13.4 URL Heuristic Risk Score

**File:** `src/detection/url_checker.py`

Sistem heuristic menghitung risk score URL tanpa API dengan menjumlahkan skor per indikator:

$$
\text{risk\_score}_{\text{url}} = \sum_{i} s_i
$$

| Indikator | Skor ($s_i$) |
|-----------|-------------|
| IP address sebagai domain | +0.30 |
| Punycode/IDN domain | +0.25 |
| Karakter aneh (`@`, `!`) | +0.20 |
| URL shortener | +0.20 |
| Subdomain berlebihan (>3 level) | +0.15 |
| TLD mencurigakan — Critical | +0.40 |
| TLD mencurigakan — High | +0.30 |
| TLD mencurigakan — Medium | +0.20 |
| TLD mencurigakan — Low | +0.10 |
| Keyword mencurigakan di path | +0.10 |
| Tidak HTTPS (HTTP saja) | +0.10 |
| Pola numerik di domain | +0.10 |

$$
\text{risk\_score}_{\text{url}} = \min\!\left(\sum s_i, \; 1.0\right)
$$

URL dianggap **malicious** jika $\text{risk\_score}_{\text{url}} \geq 0.5$.

---

### 13.5 VirusTotal — Risk Score

**File:** `src/detection/url_checker.py`

#### URL Analysis Risk

$$
\text{risk}_{\text{vt\_url}} = \frac{n_{\text{malicious}} \times 1.0 + n_{\text{suspicious}} \times 0.5}{n_{\text{malicious}} + n_{\text{suspicious}} + n_{\text{harmless}} + n_{\text{undetected}}}
$$

URL dianggap malicious jika $n_{\text{malicious}} \geq 3$ atau $\text{risk} > 0.1$.

#### Domain Reputation Risk

$$
\text{risk}_{\text{analysis}} = \frac{n_{\text{malicious}} \times 1.0 + n_{\text{suspicious}} \times 0.5}{\text{total\_engines}}
$$

$$
\text{reputation\_factor} = 
\begin{cases}
\max\!\left(0, \min\!\left(1, \frac{100 - \text{reputation}}{200}\right)\right) & \text{if reputation} < -20 \\
0 & \text{otherwise}
\end{cases}
$$

$$
\text{risk}_{\text{domain}} = \max(\text{risk}_{\text{analysis}}, \; \text{reputation\_factor})
$$

Domain malicious jika $n_{\text{malicious}} \geq 3$ atau $\text{reputation} < -50$ atau $\text{risk} > 0.15$.

#### Gabungan VT + Heuristic

$$
\text{risk}_{\text{combined}} = \max(\text{risk}_{\text{heuristic}}, \; \text{risk}_{\text{vt}})
$$

$$
\text{is\_malicious}_{\text{combined}} = \text{is\_malicious}_{\text{vt}} \;\lor\; \text{is\_malicious}_{\text{heuristic}}
$$

---

### 13.6 Stage 2 — Logika Eskalasi Single-Shot

**File:** `src/detection/single_shot/classifier.py`

Single-shot menghasilkan klasifikasi ($C$) dan confidence ($\text{conf}$) dari LLM. Logika eskalasi menentukan apakah pesan harus lanjut ke MAD:

$$
\text{escalate} = 
\begin{cases}
\textbf{TRUE} & \text{if } C = \text{PHISHING} \quad \text{(selalu, berapapun conf)} \\
\textbf{TRUE} & \text{if } C = \text{SUSPICIOUS} \\
\textbf{FALSE} & \text{if } C = \text{SAFE} \;\wedge\; \text{conf} \geq 0.90 \\
\textbf{TRUE} & \text{if } \text{conf} < 0.70 \\
\textbf{TRUE} & \text{if } \text{triage\_risk} \geq 50 \;\wedge\; \text{conf} < 0.80 \\
\textbf{FALSE} & \text{otherwise}
\end{cases}
$$

**Threshold Constants:**

| Konstanta | Nilai | Keterangan |
|-----------|-------|------------|
| `HIGH_CONFIDENCE_SAFE` | 0.90 | Minimum confidence untuk finalisasi SAFE |
| `LOW_CONFIDENCE_THRESHOLD` | 0.70 | Di bawah ini = ambigu, harus eskalasi |
| `MODERATE_CONFIDENCE_THRESHOLD` | 0.80 | Threshold menengah |
| `HIGH_TRIAGE_RISK` | 50 | Risk score triage yang dianggap tinggi |

#### Fallback (LLM Gagal)

Jika LLM error (timeout, API down), sistem tetap berfungsi dengan heuristic:

$$
(C_{\text{fallback}}, \text{conf}_{\text{fallback}}) = 
\begin{cases}
(\text{SUSPICIOUS}, \; 0.6) & \text{if triage} = \text{HIGH\_RISK} \\
(\text{SUSPICIOUS}, \; 0.5) & \text{if triage} = \text{LOW\_RISK} \\
(\text{SAFE}, \; 0.7) & \text{if triage} = \text{SAFE}
\end{cases}
$$

Fallback selalu di-escalate ke MAD ($\text{escalate} = \text{TRUE}$).

---

### 13.7 Stage 3 — Multi-Agent Debate

**File:** `src/detection/mad/aggregator.py`

#### A. Consensus Check (Setiap Ronde)

Setelah 3 agen memberikan stance independen:

**Unanimous:**

$$
\text{unanimous} = (|\{s_1, s_2, s_3\}| = 1)
$$

Jika unanimous:

$$
\text{conf}_{\text{consensus}} = \frac{1}{3} \sum_{i=1}^{3} \text{conf}_i
$$

**Strong Majority:**

$$
\text{majority}(s) = \text{count}(s) \geq 2 \;\wedge\; \frac{\sum_{\text{agent } i \text{ with stance } s} \text{conf}_i}{\text{count}(s)} \geq 0.75
$$

Jika unanimous atau strong majority → **konsensus tercapai**. Dengan `MAD_EARLY_TERMINATION=true` (default), debat akan berhenti segera setelah konsensus tercapai; jika tidak, debat berjalan sampai `MAD_MAX_ROUNDS` atau timeout (jika diset).

#### B. Weighted Voting — Formula Inti

Setiap agen memiliki **bobot statis** ($W_a$) dan **confidence dinamis** ($\text{conf}_a$):

| Agen | Tipe | Bobot Statis ($W_a$) | Alasan |
|------|------|---------------------|--------|
| Content Analyzer | `content_analyzer` | 1.0 | Analisis subjektif (linguistik) |
| Security Validator | `security_validator` | 1.5 | Evidence objektif (VirusTotal) — lebih dipercaya |
| Social Context Evaluator | `social_context` | 1.0 | Analisis kontekstual |

**Weighted score** per agen:

$$
w_a = W_a \times \text{conf}_a
$$

**Akumulasi skor:**

$$
S_{\text{phishing}} = \sum_{\text{agen } a \text{ vote PHISHING}} w_a
$$

$$
S_{\text{legitimate}} = \sum_{\text{agen } a \text{ vote LEGITIMATE}} w_a
$$

> **Catatan:** Agen yang vote **SUSPICIOUS** tidak berkontribusi ke $S_{\text{phishing}}$ maupun $S_{\text{legitimate}}$ (netral).

**Probabilitas phishing:**

$$
P_{\text{phishing}} = 
\begin{cases}
\frac{S_{\text{phishing}}}{S_{\text{phishing}} + S_{\text{legitimate}}} & \text{if } (S_{\text{phishing}} + S_{\text{legitimate}}) > 0 \\
0.5 & \text{if semua agen vote SUSPICIOUS}
\end{cases}
$$

#### C. Keputusan Akhir

$$
\text{decision} = 
\begin{cases}
\textbf{PHISHING} & \text{if } P_{\text{phishing}} \geq 0.65 \\
\textbf{LEGITIMATE} & \text{if } P_{\text{phishing}} \leq 0.35 \\
\textbf{SUSPICIOUS} & \text{if } 0.35 < P_{\text{phishing}} < 0.65
\end{cases}
$$

**Confidence akhir:**

$$
\text{confidence}_{\text{final}} = \max(P_{\text{phishing}}, \; 1 - P_{\text{phishing}})
$$

Ini memastikan confidence selalu ≥ 0.5 (semakin jauh dari 0.5 = semakin yakin).

#### D. Contoh Perhitungan MAD

**Skenario:** Pesan `"Hadiah 50 juta! Klik bit.ly/undian"` setelah bit.ly expand ke domain `.tk`.

| Agen | Stance | Confidence | $W_a$ | $w_a$ |
|------|--------|------------|-------|-------|
| Content Analyzer | PHISHING | 0.85 | 1.0 | 0.850 |
| Security Validator | PHISHING | 0.92 | 1.5 | 1.380 |
| Social Context | SUSPICIOUS | 0.70 | 1.0 | 0 (netral) |

$$
S_{\text{phishing}} = 0.850 + 1.380 = 2.230
$$

$$
S_{\text{legitimate}} = 0
$$

$$
P_{\text{phishing}} = \frac{2.230}{2.230 + 0} = 1.0
$$

Decision: $1.0 \geq 0.65$ → **PHISHING**, confidence = $\max(1.0, 0.0) = 1.0$.

---

### 13.8 Pipeline — Penentuan Aksi

**File:** `src/detection/pipeline.py`

Setelah mendapat klasifikasi final dan confidence, pipeline menentukan aksi bot:

$$
\text{action} = 
\begin{cases}
\textbf{none} & \text{if } C = \text{SAFE} \\
\textbf{flag\_review} & \text{if } C = \text{PHISHING} \quad \text{(selalu notif admin)} \\
\textbf{warn} & \text{if } C = \text{SUSPICIOUS} \;\wedge\; \text{conf} \geq 0.60 \\
\textbf{flag\_review} & \text{if } C = \text{SUSPICIOUS} \;\wedge\; \text{conf} < 0.60
\end{cases}
$$

| Aksi | Perilaku |
|------|----------|
| `none` | Tidak ada aksi, pesan aman |
| `warn` | Reply peringatan ke pesan di grup |
| `flag_review` | Alert di grup + notifikasi privat ke admin |

> **Penting:** Bot TIDAK melakukan auto-delete. Semua PHISHING → `flag_review` (admin secara manual menghapus).

---

### 13.9 Ringkasan Konstanta & Threshold

| Konstanta | Lokasi | Nilai | Keterangan |
|-----------|--------|-------|------------|
| `LOW_RISK_THRESHOLD` | triage.py | 30 | Batas risk score untuk LOW_RISK |
| `TIME_ANOMALY_THRESHOLD` | behavioral.py | 2 jam | Jarak minimum untuk anomali waktu |
| `LENGTH_DEVIATION_THRESHOLD` | behavioral.py | 2.0σ | Z-score minimum untuk anomali panjang |
| `STYLE_DEVIATION_THRESHOLD` | behavioral.py | 0.3 | 30% deviasi emoji minimum |
| `HIGH_CONFIDENCE_SAFE` | classifier.py | 0.90 | Minimum confidence SAFE tanpa eskalasi |
| `LOW_CONFIDENCE_THRESHOLD` | classifier.py | 0.70 | Di bawah ini = ambigu |
| `MODERATE_CONFIDENCE_THRESHOLD` | classifier.py | 0.80 | Threshold menengah |
| `HIGH_TRIAGE_RISK` | classifier.py | 50 | Risk triage tinggi |
| `PHISHING_THRESHOLD` | aggregator.py | 0.65 | $P_{\text{phishing}}$ minimum untuk PHISHING |
| `LEGITIMATE_THRESHOLD` | aggregator.py | 0.35 | $P_{\text{phishing}}$ maximum untuk LEGITIMATE |
| `DELETE_CONFIDENCE_THRESHOLD` | pipeline.py | 0.80 | (Tidak dipakai — bot tidak auto-delete) |
| `WARN_CONFIDENCE_THRESHOLD` | pipeline.py | 0.60 | Minimum confidence untuk aksi warn |
| `SHORTENER_WHITELISTED_BONUS` | triage.py | −10 | Bonus jika shortener → domain whitelisted |
| `EXPAND_TIMEOUT` | url_checker.py | 10s | Timeout HTTP request untuk URL expansion |
| `MAX_REDIRECTS` | url_checker.py | 10 | Maksimum redirect hops |
| `URL_SHORTENERS` | url_checker.py | 17 domains | Daftar domain shortener yang di-expand |
| `TRUSTED_DOMAINS` | url_checker.py | 30+ domains | Domain whitelist (Google, Microsoft, akademik) |

---

## Changelog

### v0.4.0 — Dashboard Enhancement & Inference Activity Tracking

**Fitur Baru:**

1. **Inference Activity Tracking** — Token usage otomatis tercatat ke Supabase
   - `DetectionResult` kini menyimpan `tokens_input` dan `tokens_output` terpisah
   - Pipeline melacak token input/output per stage (bukan 50/50 split)
   - Handler menulis ke tabel `api_usage` dengan breakdown per stage
   - Data dipakai untuk profil beban inferensi per stage

2. **Dashboard UI Redesign** — Brutalism black & white design
   - Icon library: Iconoir v7.11.0 (CSS-only, tanpa JS initialization)
   - Font: JetBrains Mono, bold borders, B&W color scheme
   - Responsive layout untuk semua ukuran layar

3. **Activity Chart dengan Range Selector** — Menggantikan hourly chart lama
   - Endpoint `/api/stats/activity?range=24h|7d|30d`
   - 24h: 24 bucket per jam dengan timestamp aktual
   - 7d: 7 bucket harian dengan nama hari Indonesia
   - 30d: 30 bucket harian dengan format dd/mm

4. **Debate History Improvements**
   - Collapsible cards dengan detail per agen
   - State expand dipertahankan saat auto-refresh (30 detik)

5. **Scrollable Sections** — Debate list dan messages table scrollable dengan sticky headers

6. **Inference Activity Section** — 3 kartu (Input Tokens, Output Tokens, API Requests)

**Perubahan:**

| Komponen | Sebelum | Sesudah |
|----------|---------|--------|
| `pipeline.py` `DetectionResult` | Hanya `total_tokens_used` | + `tokens_input`, `tokens_output` terpisah |
| `handlers.py` `_log_detection()` | Token split 50/50 | Token aktual dari API response |
| `handlers.py` | Tidak tulis `api_usage` | + `_log_api_usage()` dengan upsert per hari |
| `/api/stats/hourly` | 24 jam fixed labels | **Diganti** `/api/stats/activity?range=` |
| `/api/usage` response | `total_tokens` | + `tokens_input`, `tokens_output`, `stage_breakdown`, `total_requests` |
| Dashboard icons | Emoji | Iconoir CSS-only |
| Test files metrics | Token total sederhana | Token input/output aktual per stage |
| `updateDebates()` | Re-render reset expand | Preserve expand state via `data-debate-id` |

7. **Bot Commands Enhancement** — Commands kini menggunakan data persisten dari Supabase
   - `/status`: Menampilkan session stats + database all-time stats + inference activity
   - `/stats`: Statistik persisten (distribusi, stage breakdown, token/request profile)
   - `/check`: VirusTotal URL scan, token breakdown (in/out), triage risk score, LLM reasoning, MAD votes
   - Fallback ke session stats jika database tidak tersedia

8. **User Registration (Best-Effort)** — Handler mencoba registrasi/update user di tabel `users`
   - `_ensure_user_registered()` melakukan upsert metadata user untuk baseline linking.
   - Jika ada mismatch skema kolom antar environment, proses registrasi user di-skip tanpa menghentikan deteksi.

9. **Auto-Delete Removed** — Auto-delete pesan phishing dihapus dari `actions.py`
   - Aksi `delete` dan method `_handle_delete()` dihapus
   - Template `phishing_deleted` dan `admin_phishing_alert` dihapus
   - Semua PHISHING menggunakan `flag_review` → admin review manual

10. **Admin Notifications Enriched** — Notifikasi kini menyertakan:
    - Processing time (ms)
    - Token breakdown (input, output, total)
    - Profil token per deteksi
    - MAD agent votes terformat: `Content Analyzer: X | Security Validator: Y`

11. **Friendly Stage Names** — `STAGE_DISPLAY` dict untuk nama stage yang user-friendly
    - `triage` → "Rule-Based Triage"
    - `single_shot` → "Single-Shot LLM"
    - `mad` → "Multi-Agent Debate"

12. **Version Bump** — `__version__` diupdate ke `0.4.0`

| Komponen | Sebelum | Sesudah |
|----------|---------|--------|
| `bot.py` `/status` | Session stats saja | + DB stats + inference activity |
| `bot.py` `/stats` | Session stats saja | Persistent DB stats + stage breakdown + token/request profile |
| `bot.py` `/check` | Tanpa URL check, output minimal | + VirusTotal, token breakdown, reasoning, MAD votes |
| `handlers.py` | Tidak registrasi user | + `_ensure_user_registered()` upsert |
| `actions.py` | 4 aksi (none/warn/flag_review/delete) | **3 aksi** (none/warn/flag_review) |
| `actions.py` templates | 5 templates (termasuk delete flow) | 4 templates (warning + admin review flow) |
| `actions.py` admin notif | Tanpa telemetry | + processing_time, token profile |
| `actions.py` stage names | `result.decided_by.upper()` | `STAGE_DISPLAY[result.decided_by]` |
| `__init__.py` | `0.1.0` | `0.4.0` |

---

### v0.3.1 — Integrasi URL Checker dengan Triage

**Masalah yang diatasi:**
- URL yang sudah di-expand dan di-verify trusted di `URLSecurityChecker` tidak digunakan oleh Triage
- Akibatnya, bit.ly → Google Forms tetap dianggap `shortened_url` (risk +10) dan tidak SAFE

**Perubahan:**

| Komponen | Sebelum | Sesudah |
|----------|---------|--------|
| `triage.py` | Tidak menerima `url_checks` | **Menerima `url_checks`** parameter |
| Trusted URL Detection | Hanya cek whitelist lokal | **Cek `url_checks` untuk `source='whitelist'`** |
| `pipeline.py` | Tidak pass `url_checks` ke triage | **Pass `url_checks` ke `triage.analyze()`** |

**Alur baru:**
```
Handler → check_urls_external_async() → url_checks
Pipeline → triage.analyze(..., url_checks=url_checks)
Triage → if url_checks[url].source == 'whitelist' → whitelisted
```

**Hasil:**
- `bit.ly/PendaftaranSeminarTI` → **SAFE** (decided at Stage 1)
- Tidak ada panggilan LLM untuk shortened URL yang mengarah ke trusted domain

---

### v0.3.0 — URL Expansion & Trusted Domain Whitelist

**Fitur Baru:**

1. **URL Expansion** — Otomatis follow redirect chain untuk shortened URLs
   - Mendukung 17+ layanan shortener (bit.ly, tinyurl.com, s.id, cutt.ly, dll)
   - Max 10 redirect hops, timeout 10 detik
   - Return `expanded_url` dan `redirect_chain` untuk audit trail

2. **Trusted Domain Whitelist** — Skip VirusTotal untuk domain terpercaya
   - Google Services (docs, drive, meet, classroom, forms, youtube)
   - Microsoft Services (office, outlook, teams, sharepoint)
   - Academic Platforms (github, gitlab, zoom)
   - Indonesian Academic (uir.ac.id, kemdikbud.go.id, dikti.go.id)
   - Communication (linkedin, whatsapp, telegram)

3. **URLCheckResult Enhancement** — Menyertakan `expanded_url` field

**Perubahan:**

| Komponen | Sebelum | Sesudah |
|----------|---------|--------|
| `url_checker.py` | 2-layer (heuristic + VT) | **4-layer** (expand → whitelist → heuristic → VT) |
| URL Shortener Check | Langsung +0.2 risk | Expand dulu, cek destination domain |
| Trusted Domain | Tidak ada | Bypass VT, risk score = 0.0 |
| `URLCheckResult` | url, is_malicious, risk_score | **+ expanded_url**, redirect_chain in details |

**Contoh:**
```
Input:  https://bit.ly/PendaftaranSeminarTI
Output: 
  expanded_url: https://docs.google.com/forms/d/e/...
  is_malicious: false
  risk_score: 0.00
  source: whitelist
```

---

### v0.2.0 — Perbaikan False Positive & URL Shortener Handling

**Masalah yang diatasi:**
1. Single-shot LLM bisa "yakin tapi salah" — memberikan label PHISHING dengan confidence tinggi padahal pesan aman
2. URL shortener (bit.ly, s.id) langsung dianggap phishing indicator kuat, padahal dosen/mahasiswa sering menggunakannya
3. False PHISHING = spam notifikasi ke admin (karena bot hanya flag_review, bukan auto-delete)

**Perubahan:**

| Komponen | Sebelum | Sesudah |
|----------|---------|--------|
| `triage.py` scoring | `shortened_url` = +20 | `shortened_url` = +10, `expand_failed` = +15, bonus whitelist = -10 |
| `classifier.py` eskalasi | PHISHING conf ≥85% → Done | PHISHING **selalu** → MAD (berapapun confidence) |
| `pipeline.py` docstring | "High confidence PHISHING → Done" | "PHISHING → Always escalate to Stage 3" |
| Single-shot role | Hakim akhir | **Router** — hanya bisa finalisasi SAFE |
