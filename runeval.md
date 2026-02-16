## Dataset Default

Dataset yang dipakai:
- Path: `data/dataset_mixed_safe_suspicious_phishing.csv`
- Header: `chat;tipe`
- Delimiter: `;`

Catatan:
- Jalankan command dari root project (folder yang ada `evaluate.py`).
- Kalau mau evaluasi semua baris dataset, hapus flag `--limit 100` (jangan dikosongkan jadi `--limit ""`).

## Linux (bash) - 8 Run Commands (DeepSeek vs OpenRouter)

```bash
DATASET="data/dataset_mixed_safe_suspicious_phishing.csv"
TEXTCOL="chat"
LABELCOL="tipe"
DELIM=";"
LIMIT=100

# 1) DeepSeek pipeline mad3 -> results/deepseek/mad3
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/deepseek/mad3

# 2) DeepSeek pipeline mad5 -> results/deepseek/mad5
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/deepseek/mad5

# 3) OpenRouter (GPT-5-nano) pipeline mad3 -> results/openrouter/mad3
# pastikan OPENROUTER_API_KEY sudah tersedia (env atau .env)
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/openrouter/mad3

# 4) OpenRouter (GPT-5-nano) pipeline mad5 -> results/openrouter/mad5
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode pipeline --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/openrouter/mad5

# 5) DeepSeek mad_only mad3 -> results/deepseek/mad3_mad_only
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/deepseek/mad3_mad_only

# 6) DeepSeek mad_only mad5 -> results/deepseek/mad5_mad_only
LLM_PROVIDER=deepseek python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/deepseek/mad5_mad_only

# 7) OpenRouter (GPT-5-nano) mad_only mad3 -> results/openrouter/mad3_mad_only
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad3 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/openrouter/mad3_mad_only

# 8) OpenRouter (GPT-5-nano) mad_only mad5 -> results/openrouter/mad5_mad_only
LLM_PROVIDER=openrouter python evaluate.py --dataset "$DATASET" --eval-mode mad_only --mad-mode mad5 --text-col "$TEXTCOL" --label-col "$LABELCOL" --delimiter "$DELIM" --limit $LIMIT --output results/openrouter/mad5_mad_only
```

## Windows (PowerShell)

```powershell
# pastikan berada di root project (yang ada evaluate.py)
# contoh:
# Set-Location "C:\path\to\TelePhisDebate"

$DATASET  = "data/dataset_mixed_akademik.csv"
$TEXTCOL  = "chat"
$LABELCOL = "tipe"
$DELIM    = ";"
$LIMIT    = 200

# 1) DeepSeek pipeline mad3 -> results/deepseek/mad3
$env:LLM_PROVIDER="deepseek"
python evaluate.py --dataset $DATASET --eval-mode pipeline --mad-mode mad3 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/deepseek/mad3

# 2) DeepSeek pipeline mad5 -> results/deepseek/mad5
$env:LLM_PROVIDER="deepseek"
python evaluate.py --dataset $DATASET --eval-mode pipeline --mad-mode mad5 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/deepseek/mad5

# 3) OpenRouter (google/gemini-2.5-flash-lite) pipeline mad3 -> results/openrouter/mad3
# pastikan OPENROUTER_API_KEY sudah tersedia (env atau .env)
$env:LLM_PROVIDER="openrouter"
python evaluate.py --dataset $DATASET --eval-mode pipeline --mad-mode mad3 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/openrouter/mad3

# 4) OpenRouter (google/gemini-2.5-flash-lite) pipeline mad5 -> results/openrouter/mad5
$env:LLM_PROVIDER="openrouter"
python evaluate.py --dataset $DATASET --eval-mode pipeline --mad-mode mad5 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/openrouter/mad5

# 5) DeepSeek mad_only mad3 -> results/deepseek/mad3_mad_only
$env:LLM_PROVIDER="deepseek"
python evaluate.py --dataset $DATASET --eval-mode mad_only --mad-mode mad3 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/deepseek/mad3_mad_only

# 6) DeepSeek mad_only mad5 -> results/deepseek/mad5_mad_only
$env:LLM_PROVIDER="deepseek"
python evaluate.py --dataset $DATASET --eval-mode mad_only --mad-mode mad5 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/deepseek/mad5_mad_only

# 7) OpenRouter (google/gemini-2.5-flash-lite) mad_only mad3 -> results/openrouter/mad3_mad_only
$env:LLM_PROVIDER="openrouter"
python evaluate.py --dataset $DATASET --eval-mode mad_only --mad-mode mad3 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/openrouter/mad3_mad_only

# 8) OpenRouter (google/gemini-2.5-flash-lite) mad_only mad5 -> results/openrouter/mad5_mad_only
$env:LLM_PROVIDER="openrouter"
python evaluate.py --dataset $DATASET --eval-mode mad_only --mad-mode mad5 --text-col $TEXTCOL --label-col $LABELCOL --delimiter $DELIM --limit $LIMIT --output results/openrouter/mad5_mad_only
```
