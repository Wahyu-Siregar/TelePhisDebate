# Roadmap

## Fase 1: Setup Infrastruktur dan Persiapan (2-3 minggu)

**Environment Setup** install dependencies: python-telegram-bot untuk bot development, requests untuk API calls ke DeepSeek, Supabase untuk database menyimpan message history dan user baselines, python-dotenv untuk environment variables management.[^1]

**DeepSeek API Configuration** daftar akun DeepSeek dan dapatkan API key, setup rate limiting (max requests per minute), implement token counter untuk monitoring usage, create wrapper functions untuk API calls dengan error handling dan retry logic. Test koneksi dengan simple prompt untuk ensure API working properly.[^2]

**Database Schema Design** buat tables untuk: `users` (user_id, username, baseline_metrics), `messages` (message_id, user_id, content, timestamp, urls_extracted, classification, confidence), `detection_logs` (message_id, stage, agent_responses, final_decision, processing_time), dan `url_cache` (url, reputation_score, last_checked) untuk avoid redundant lookups.[^3][^4]

**Telegram Bot Registration** buat bot via BotFather, dapatkan bot token, setup bot sebagai admin di test group dengan permissions untuk read messages dan delete messages. Test basic functionality seperti receive messages dan send responses.[^1]

## Fase 2: Dataset Collection dan User Baseline Building (3-4 minggu)

**Historical Data Collection** koordinasi dengan admin grup TI UIR untuk export chat history (jika possible via Telegram Desktop export feature), manually label 200-300 messages sebagai seed dataset: phishing examples, suspicious messages, legitimate academic messages. Fokus collect contoh phishing yang pernah terjadi di grup.[^4]

**User Baseline Computation** untuk setiap active user di grup, compute baseline metrics: average message length (char count), typical posting hours (histogram of hours), URL sharing frequency (URLs per 100 messages), message style features (avg sentence length, emoji usage rate, caps lock frequency). Store di database untuk real-time comparison.[^5][^6]

**Synthetic Data Augmentation** create 100-150 synthetic phishing messages based on identified patterns dari kasus real untuk augment dataset. Patterns: "Halo kak, ada beasiswa full S2 nih, daftar sebelum besok ya [shortened-url]", "Urgent! Akun telegram kamu akan diblokir, verifikasi di [fake-link]", "Lomba berhadiah 10jt, cuma perlu klik [suspicious-url]".[^7][^8]

## Fase 3: Implementasi Rule-Based Triage (2 minggu)

**Whitelist Module** implementasi exact match untuk trusted patterns: official UIR domains (*.uir.ac.id), known meeting platforms (zoom.us, meet.google.com), academic platforms (classroom.google.com, github.com, gitlab.com), Indonesian government edu domains (*.go.id verified). Messages dengan only whitelisted URLs langsung classify SAFE, bypass LLM stages.[^9]

**Blacklist dan Red Flags Detection** ✅ IMPLEMENTED: integrate suspicious TLD dataset (130+ TLDs dari `dataset/suspicious_tlds_list.csv` dengan severity levels: Critical, High, Medium, Low), VirusTotal API integration untuk real-time URL reputation check, keyword blacklist untuk suspicious keywords ("mendesak", "segera transfer", "hadiah", "verifikasi akun"), URL patterns detection (bit.ly, tinyurl, dan URL shorteners lainnya), excessive urgency markers (!!!, ALL CAPS > 50% of message).[^8][^9][^1]

**Behavioral Anomaly Detection** untuk message dengan URL, check deviation from user baseline: is_first_time_url = check jika user belum pernah share URL sebelumnya, time_anomaly = posting di jam unusual (misal user biasanya post jam 8-22, tiba-tiba post jam 3 pagi), style_deviation = message length atau emoji usage significantly berbeda dari baseline.[^6][^5]

**Triage Decision Logic** implementasi scoring system:

```python
risk_score = 0
if has_blacklisted_domain: risk_score += 50
if has_shortened_url: risk_score += 20
if urgency_keywords > 2: risk_score += 15
if is_first_time_url: risk_score += 10
if time_anomaly: risk_score += 10
if style_deviation > threshold: risk_score += 15

if risk_score == 0 and has_whitelisted_only: return "SAFE"
elif risk_score < 30: return "LOW_RISK" → Single-Shot LLM
else: return "HIGH_RISK" → Single-Shot LLM (lower threshold untuk MAD)
```

Output triage: classification, risk_score, triggered_flags (list of red flags detected).

## Fase 4: Implementasi Single-Shot LLM (2-3 minggu)

**Prompt Engineering untuk Classification** design system prompt yang comprehensive:[^10]

```
You are a phishing detection system for an Indonesian academic Telegram group. 
Analyze if this message from a verified student account shows signs of account compromise.

Context:
- Group: Computer Science students, Universitas Islam Riau
- Typical content: academic discussions, assignments, event announcements
- Threat model: compromised student accounts sending phishing links

Output strict JSON:
{
  "classification": "SAFE" | "SUSPICIOUS" | "PHISHING",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation in Indonesian",
  "risk_factors": ["factor1", "factor2", ...]
}
```

**Input Formatting** untuk setiap message, construct prompt dengan structured information:

```
Message Analysis Request:

Sender: @username (Student, joined: 2023)
Baseline behavior: 
- Avg message length: 120 chars
- Typical hours: 09:00-21:00
- URL sharing rate: 0.05 per message

Current message:
- Timestamp: 2026-02-03 03:15 (ANOMALY: outside typical hours)
- Content: "Halo teman-teman! Ada lowongan magang bayaran tinggi nih, buruan daftar sebelum besok! [bit.ly/xyz123]"
- Length: 95 chars
- Contains URL: Yes (shortened)

Triage flags: shortened_url, time_anomaly, urgency_keywords
Risk score: 45

Analyze this message.
```

**API Call Implementation** dengan error handling:[^2]

```python
def single_shot_classify(message_data, max_retries=3):
    prompt = construct_prompt(message_data)
    for attempt in range(max_retries):
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # lower untuk consistency
                max_tokens=500,   # ✅ Increased untuk full reasoning output
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[^0].message.content)
            log_token_usage(response.usage)
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                return fallback_heuristic(message_data)
            time.sleep(2 ** attempt)  # exponential backoff
```

**Decision Threshold untuk MAD Escalation** implementasi logic:[^11]

```python
def should_escalate_to_mad(single_shot_result, triage_risk_score):
    conf = single_shot_result["confidence"]
    classification = single_shot_result["classification"]
    
    # High confidence decisions: accept immediately
    if conf >= 0.90 and classification == "SAFE": return False
    if conf >= 0.85 and classification == "PHISHING": return False
    
    # Ambiguous cases: escalate
    if conf < 0.70: return True
    
    # High triage risk + moderate LLM uncertainty: escalate
    if triage_risk_score >= 50 and conf < 0.80: return True
    
    # Suspicious classification always escalate for confirmation
    if classification == "SUSPICIOUS": return True
    
    return False
```


## Fase 5: Implementasi Multi-Agent Debate (3-4 minggu)

### URL Security Checker Module ✅ IMPLEMENTED

**File: `src/detection/url_checker.py`**

Modul URL checker yang menggabungkan multiple sources:

```python
# Arsitektur URL Checker
class URLSecurityChecker:
    """
    Aggregates multiple URL checking sources:
    - VirusTotal API v3 (90+ security engines)
    - Heuristic Analysis (130+ suspicious TLDs dari dataset)
    """
    
    async def check_url(self, url: str) -> URLCheckResult:
        # 1. Heuristic analysis (always runs)
        heuristic_result = self._heuristic_check(url)
        
        # 2. VirusTotal API (if configured)
        if self.virustotal.is_configured:
            vt_result = await self.virustotal.check_url(url)
            
            # Combine: use higher risk score
            combined_risk = max(heuristic_result.risk_score, vt_result.risk_score)
            is_malicious = vt_result.is_malicious or heuristic_result.is_malicious
        
        return URLCheckResult(
            url=url,
            is_malicious=is_malicious,
            risk_score=combined_risk,
            source="virustotal+heuristic",
            details={...}
        )

# Suspicious TLD Database dari dataset/suspicious_tlds_list.csv
SUSPICIOUS_TLDS = {
    ".icu": {"severity": "Critical", "category": "Malware"},
    ".ml": {"severity": "Critical", "category": "Phishing - Malware - C2"},
    ".tk": {"severity": "Critical", "category": "Phishing - C2"},
    ".xyz": {"severity": "Critical", "category": "Phishing - Malware"},
    # ... 130+ TLDs dengan severity scoring
}

# Heuristic Risk Scoring
severity_scores = {
    "critical": 0.4,  # .tk, .ml, .xyz, .icu
    "high": 0.3,      # .cf, .ga, .gq, .pw, .info
    "medium": 0.2,    # .cn, .ru, .top, .site
    "low": 0.1        # .shop, .life, .club
}
```

**Integration Flow:**
```
Telegram Message
      ↓
[Bot Handler] _check_urls_async()
   → Extract URLs via regex
   → await check_urls_external_async(urls)
      → VirusTotal API (async)
      → + Heuristic analysis
      ↓
[Pipeline] process_message(url_checks=result)
      ↓
[MAD] Security Validator receives url_checks
   → Analisis hasil untuk voting
```

### Week 1-2: Individual Agent Implementation

**Agent 1: Content Analyzer**[^12][^10]

```python
CONTENT_ANALYZER_PROMPT = """
You are Content Analyzer agent in a phishing detection system.
Your role: Analyze message content, linguistic patterns, and behavioral deviation.

Focus on:
1. Language style consistency with sender's baseline
2. Social engineering tactics (urgency, authority, fear)
3. Contextual relevance to academic group activities
4. Message structure and formatting anomalies

Message data: {message_info}
User baseline: {baseline_info}
Previous stage: {single_shot_result}

Output JSON:
{
  "stance": "PHISHING" | "SUSPICIOUS" | "LEGITIMATE",
  "confidence": 0.0-1.0,
  "key_arguments": ["arg1", "arg2", ...],
  "evidence": {"style_deviation": 0.0-1.0, "urgency_score": 0.0-1.0, ...}
}
"""
```

**Agent 2: Security Validator**[^12] ✅ IMPLEMENTED

Security Validator sekarang menerima hasil dari `url_checker.py` yang menggabungkan:
- **VirusTotal API v3**: Domain/URL reputation check dengan 90+ security engines
- **Heuristic Analysis**: Dataset 130+ suspicious TLDs, URL shortener detection, punycode detection
- **Combined Risk Score**: Gabungan VT + heuristic untuk akurasi maksimal

```python
# url_checker.py - Hasil yang diterima Security Validator:
{
    "url": "https://scam.xyz",
    "is_malicious": True,
    "risk_score": 0.65,
    "source": "virustotal+heuristic",
    "details": {
        "malicious": 5,           # VT engines detecting malicious
        "total_engines": 93,
        "reputation": -15,
        "heuristic_risk_factors": ["Critical TLD (Phishing - Malware)"],
        "tld_info": {"severity": "Critical", "category": "Phishing"}
    }
}
```

**Agent 3: Social Context Evaluator**[^6]

```python
SOCIAL_CONTEXT_PROMPT = """
You are Social Context Evaluator agent in a phishing detection system.
Your role: Evaluate social and behavioral context specific to academic group.

Focus on:
1. Sender's historical behavior patterns
2. Message timing appropriateness
3. Relevance to ongoing academic activities
4. Social dynamics in student group

Message data: {message_info}
User history: {user_history}
Recent group topics: {recent_context}
Previous stage: {single_shot_result}

Output JSON:
{
  "stance": "PHISHING" | "SUSPICIOUS" | "LEGITIMATE",
  "confidence": 0.0-1.0,
  "key_arguments": ["arg1", "arg2", ...],
  "context_evidence": {"behavior_anomaly_score": float, "relevance_score": float, ...}
}
"""
```


### Week 2-3: Debate Orchestration

**Round 1: Independent Analysis**[^13] ✅ IMPLEMENTED

```python
# handlers.py - URL check dipanggil async di bot handler
async def _check_urls_async(self, text_content: str) -> dict | None:
    urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text_content)
    if not urls:
        return None
    
    # Panggil VirusTotal + Heuristic async
    url_checks = await check_urls_external_async(urls)
    return url_checks

# pipeline.py - URL checks diteruskan ke MAD
result = self.pipeline.process_message(
    message_text=text_content,
    url_checks=url_checks  # Pre-computed dari handler
)

# orchestrator.py - Parallel LLM calls
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(content_agent.analyze, ...),
        executor.submit(security_agent.analyze, ..., url_checks=url_checks),
        executor.submit(social_agent.analyze, ...)
    ]
```

**Consensus Check**[^14]

```python
def check_consensus(agents_responses):
    stances = [r["stance"] for r in agents_responses]
    
    # Unanimous agreement
    if len(set(stances)) == 1:
        avg_confidence = sum(r["confidence"] for r in agents_responses) / 3
        return {
            "consensus": True,
            "decision": stances[^0],
            "confidence": avg_confidence,
            "skip_round_2": True
        }
    
    # Check weighted consensus
    weighted_score = calculate_weighted_stance(agents_responses)
    if abs(weighted_score) > 0.7:  # strong weighted agreement
        return {
            "consensus": True,
            "decision": "PHISHING" if weighted_score > 0 else "LEGITIMATE",
            "confidence": abs(weighted_score),
            "skip_round_2": False  # masih lakukan round 2 untuk konfirmasi
        }
    
    return {"consensus": False, "skip_round_2": False}
```

**Round 2: Deliberation dengan Cross-Agent Context**[^13]

```python
def debate_round_2(message_data, round_1_responses):
    # Compile other agents' arguments untuk setiap agent
    def get_other_arguments(current_agent_idx):
        others = [r for i, r in enumerate(round_1_responses) if i != current_agent_idx]
        return format_arguments(others)
    
    round_2_prompts = []
    for i, agent_type in enumerate(["content", "security", "social"]):
        prompt = f"""
        Round 2 Deliberation:
        
        Your Round 1 analysis: {round_1_responses[i]}
        
        Other agents' analyses:
        {get_other_arguments(i)}
        
        Review the arguments. Do you maintain your stance or revise it?
        Consider: Are there blind spots in your analysis? Do other agents present compelling evidence?
        
        Output same JSON format. You may change stance if convinced, or maintain with stronger arguments.
        """
        round_2_prompts.append(prompt)
    
    # Parallel calls untuk round 2
    round_2_responses = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(call_agent, agent_type, prompt) 
            for agent_type, prompt in zip(["content", "security", "social"], round_2_prompts)
        ]
        for future in futures:
            round_2_responses.append(future.result())
    
    return round_2_responses
```


### Week 4: Aggregation dan Final Decision

**Weighted Voting Implementation**[^15][^16]

```python
def aggregate_final_decision(agents_responses):
    # Define weights (tunable via validation)
    WEIGHTS = {
        "content": 1.0,    # subjective analysis
        "security": 1.5,   # objective evidence lebih dipercaya
        "social": 1.0      # contextual analysis
    }
    
    # Calculate weighted scores
    phishing_score = 0
    legit_score = 0
    total_weight = 0
    
    for agent_type, response in zip(["content", "security", "social"], agents_responses):
        weight = WEIGHTS[agent_type] * response["confidence"]
        
        if response["stance"] == "PHISHING":
            phishing_score += weight
        elif response["stance"] == "LEGITIMATE":
            legit_score += weight
        # SUSPICIOUS treated as neutral, tidak contribute ke scores
        
        total_weight += weight
    
    # Normalize
    if total_weight == 0:
        return {"decision": "SUSPICIOUS", "confidence": 0.5}
    
    phishing_prob = phishing_score / (phishing_score + legit_score) if (phishing_score + legit_score) > 0 else 0.5
    
    # Decision threshold
    if phishing_prob >= 0.75:
        decision = "PHISHING"
    elif phishing_prob <= 0.25:
        decision = "LEGITIMATE"
    else:
        decision = "SUSPICIOUS"
    
    confidence = max(phishing_prob, 1 - phishing_prob)
    
    return {
        "decision": decision,
        "confidence": confidence,
        "agent_votes": {agent_type: r["stance"] for agent_type, r in zip(["content", "security", "social"], agents_responses)},
        "weighted_score": phishing_prob
    }
```


## Fase 6: Integrasi Keseluruhan Pipeline (2 minggu)

**Main Detection Pipeline**[^17]

```python
class PhishingDetectionPipeline:
    def __init__(self):
        self.triage = RuleBasedTriage()
        self.single_shot = SingleShotLLM()
        self.mad = MultiAgentDebate()
        self.db = Database()
    
    async def process_message(self, message):
        start_time = time.time()
        
        # Stage 1: Rule-Based Triage
        triage_result = self.triage.analyze(message)
        self.db.log_stage("triage", message.id, triage_result)
        
        if triage_result["classification"] == "SAFE":
            return self._finalize("SAFE", 1.0, "triage", time.time() - start_time)
        
        # Stage 2: Single-Shot LLM
        single_shot_result = await self.single_shot.classify(message, triage_result)
        self.db.log_stage("single_shot", message.id, single_shot_result)
        
        # Check if escalation needed
        if not self.should_escalate_to_mad(single_shot_result, triage_result):
            return self._finalize(
                single_shot_result["classification"],
                single_shot_result["confidence"],
                "single_shot",
                time.time() - start_time
            )
        
        # Stage 3: Multi-Agent Debate
        mad_result = await self.mad.run_debate(message, single_shot_result)
        self.db.log_stage("mad", message.id, mad_result)
        
        return self._finalize(
            mad_result["decision"],
            mad_result["confidence"],
            "mad",
            time.time() - start_time,
            mad_details=mad_result
        )
    
    def _finalize(self, classification, confidence, stage, processing_time, mad_details=None):
        return {
            "classification": classification,
            "confidence": confidence,
            "decided_by": stage,
            "processing_time": processing_time,
            "mad_details": mad_details
        }
```

**Telegram Bot Integration**[^1]

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    # Skip if from bot or admin commands
    if message.from_user.is_bot or message.text.startswith('/'):
        return
    
    # Extract message data
    message_data = extract_message_features(message)
    
    # Run detection pipeline
    result = await pipeline.process_message(message_data)
    
    # Take action based on result
    if result["classification"] == "PHISHING" and result["confidence"] >= 0.80:
        # High confidence phishing: delete + warn
        await message.delete()
        warning = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ **Phishing Terdeteksi**\n\n"
                 f"Pesan dari @{message.from_user.username} telah dihapus.\n"
                 f"Confidence: {result['confidence']:.0%}\n"
                 f"Stage: {result['decided_by']}\n\n"
                 f"Jika ini kesalahan, hubungi admin grup.",
            parse_mode="Markdown"
        )
        # Auto-delete warning after 2 minutes
        await asyncio.sleep(120)
        await warning.delete()
        
    elif result["classification"] == "SUSPICIOUS" or result["confidence"] < 0.80:
        # Suspicious: flag for manual review
        await message.reply_text(
            f"⚠️ Pesan ini ditandai sebagai mencurigakan. "
            f"Admin akan review. Jangan klik link yang dibagikan sebelum dikonfirmasi aman.",
            reply_to_message_id=message.message_id
        )
        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"Manual review needed:\n{format_for_admin(message, result)}"
        )
```


## Fase 7: Testing dan Validasi (3-4 minggu)

**Unit Testing per Component** test setiap stage secara isolated:[^18]

- Test triage dengan known safe/phishing examples
- Test single-shot dengan various confidence scenarios
- Test each MAD agent dengan edge cases
- Test aggregation logic dengan different voting scenarios

**Integration Testing** test full pipeline dengan test cases:

- Clear phishing (should be caught by triage/single-shot)
- Clear legitimate (should pass through quickly)
- Ambiguous cases (should escalate to MAD appropriately)
- Edge cases (empty URLs, very short messages, etc.)

**Pilot Deployment di Test Group** create private test group dengan 10-15 mahasiswa volunteers:[^3]

- Deploy bot dengan full monitoring
- Inject simulated phishing messages at random times
- Measure: detection rate, false positive rate, average processing time per stage
- Collect user feedback via survey

**Performance Optimization** based on pilot results:

- Tune aggregation weights untuk MAD
- Adjust confidence thresholds untuk escalation
- Optimize prompt lengths untuk reduce token usage
- Cache URL reputation checks untuk commonly seen domains


## Fase 8: Production Deployment dan Monitoring (2-3 minggu)

**Gradual Rollout** di grup TI UIR:[^3]

- Week 1: Deploy dalam monitoring-only mode (detect tapi tidak delete, hanya log)
- Week 2: Enable warning mode (flag suspicious tapi tidak delete)
- Week 3: Enable full protection mode (delete phishing dengan high confidence)

**Monitoring Dashboard** buat simple Flask/Streamlit dashboard untuk track:[^2]

- Daily statistics: messages processed, detections per stage, false positive reports
- Agent performance: individual agent accuracy, consensus rate
- Cost tracking: DeepSeek API usage, daily/monthly token consumption
- Alerts: unusual patterns, API errors, high false positive rate

**Feedback Loop** implement mekanisme untuk continuous improvement:

- Admin review interface untuk confirm/reject bot decisions
- User report button untuk false positives
- Weekly review meeting dengan admin grup
- Retrain/update rules based on new phishing patterns


## Fase 9: Evaluasi dan Dokumentasi (3-4 minggu)

**Comprehensive Evaluation** collect metrics selama 4 minggu production:[^18]

- **Accuracy Metrics**: Precision, recall, F1-score per stage dan overall
- **Efficiency Metrics**: Avg processing time, token consumption per message, % messages per stage
- **User Metrics**: False positive rate reported, user satisfaction survey, admin workload reduction

**Ablation Studies** untuk validate hybrid approach:[^12]

- Remove triage: direct semua ke single-shot
- Remove MAD: semua handled by single-shot only
- Compare: baseline rule-based, traditional ML (Random Forest)
- Measure impact of each component

**Thesis Writing** document seluruh process:

- Chapter 1: Introduction (phishing problem di grup TI UIR)
- Chapter 2: Literature Review (phishing detection, multi-agent systems)
- Chapter 3: Methodology (detailed system architecture)
- Chapter 4: Implementation (technical details dengan code snippets)
- Chapter 5: Evaluation (comprehensive results dengan visualizations)
- Chapter 6: Discussion (findings, limitations, implications)
- Chapter 7: Conclusion dan Future Work

**Code dan Documentation** finalize GitHub repository dengan:

- Clean, commented code
- README dengan setup instructions
- Requirements.txt dengan all dependencies
- Sample configurations dan env templates
- Documentation untuk reproduceability


## Timeline Total: 26-32 minggu (6.5-8 bulan)

Breakdown realistis untuk skripsi S1 dengan beberapa fase bisa overlap:

- **Fase 1-2**: Minggu 1-7 (persiapan dan data)
- **Fase 3-5**: Minggu 8-20 (core implementation, bisa paralel)
- **Fase 6-7**: Minggu 21-27 (integrasi dan testing)
- **Fase 8-9**: Minggu 28-32 (deployment dan evaluasi)


## Tips Implementasi

**Version Control** commit frequently ke GitHub dengan descriptive messages untuk track progress. **Cost Management** set DeepSeek API budget alerts di \$5/month threshold, implement local caching aggressively untuk reduce API calls. **Backup Plans** jika DeepSeek API unstable, siapkan fallback ke local model (Llama-3.1-8B via Ollama) untuk continuity.[^2]

**Collaboration** ajak 2-3 teman untuk jadi beta testers dan annotators, ini significantly speed up validation phase. **Documentation** document decisions dan challenges sejak awal dalam research journal, ini akan sangat membantu saat menulis thesis.

Roadmap ini balance antara comprehensiveness dan feasibility untuk level skripsi S1. Good luck dengan penelitian kamu, Wahyu!

<div align="center">⁂</div>

[^1]: https://www.ijrti.org/papers/IJRTI2504096.pdf

[^2]: http://arxiv.org/pdf/2405.11619.pdf

[^3]: https://www.ijecer.org/ijecer/article/view/451

[^4]: https://arxiv.org/pdf/2412.20406.pdf

[^5]: http://arxiv.org/pdf/2406.08084.pdf

[^6]: https://ieeexplore.ieee.org/document/10248275/

[^7]: http://arxiv.org/pdf/2111.13530.pdf

[^8]: https://cloud.google.com/blog/topics/threat-intelligence/phishing-campaign-woff-obfuscation-telegram-communications/

[^9]: https://onlinelibrary.wiley.com/doi/10.1155/2021/8241104

[^10]: https://arxiv.org/html/2505.23803v1

[^11]: https://arxiv.org/abs/2511.11306

[^12]: https://arxiv.org/html/2505.23803

[^13]: https://systems-analysis.ru/eng/Multi-Agent_Debate

[^14]: https://arxiv.org/abs/2511.06396

[^15]: https://www.emergentmind.com/topics/multi-agent-debate-mad-strategies

[^16]: https://www.emergentmind.com/topics/multi-agent-debate-mad-frameworks

[^17]: https://ieeexplore.ieee.org/document/11012305/

[^18]: https://arxiv.org/html/2511.06396v1

