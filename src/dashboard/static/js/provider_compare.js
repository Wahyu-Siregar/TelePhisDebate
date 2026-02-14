/**
 * TelePhisDebate DeepSeek vs Gemini comparison page.
 */

const API_BASE = '';

const METRICS_CONFIG = [
    { key: 'accuracy', label: 'Accuracy', type: 'percent', higherBetter: true },
    { key: 'precision', label: 'Precision', type: 'percent', higherBetter: true },
    { key: 'recall', label: 'Recall', type: 'percent', higherBetter: true },
    { key: 'f1_score', label: 'F1-Score', type: 'percent', higherBetter: true },
    { key: 'detection_rate', label: 'Detection Rate', type: 'percent', higherBetter: true },
    { key: 'avg_time_ms', label: 'Avg Time / Message', type: 'time', higherBetter: false },
    { key: 'avg_tokens_per_msg', label: 'Avg Tokens / Message', type: 'number', higherBetter: false }
];

function formatMetricValue(value, type) {
    if (value == null) return '—';
    if (type === 'percent') return `${(value * 100).toFixed(2)}%`;
    if (type === 'time') return `${Number(value).toFixed(1)}ms`;
    return Number(value).toLocaleString();
}

function formatDelta(value, type) {
    if (value == null) return '—';
    const sign = value > 0 ? '+' : '';
    if (type === 'percent') return `${sign}${(value * 100).toFixed(2)}%`;
    if (type === 'time') return `${sign}${Number(value).toFixed(1)}ms`;
    return `${sign}${Number(value).toFixed(2)}`;
}

function compareWinner(deepseekValue, geminiValue, higherBetter) {
    const EPS = 1e-9;
    if (deepseekValue == null || geminiValue == null) {
        return { winner: 'N/A', geminiBetter: false, tie: false };
    }
    if (Math.abs(geminiValue - deepseekValue) <= EPS) {
        return { winner: 'Tie', geminiBetter: false, tie: true };
    }

    if (higherBetter) {
        if (geminiValue > deepseekValue) return { winner: 'Gemini', geminiBetter: true, tie: false };
        return { winner: 'DeepSeek', geminiBetter: false, tie: false };
    }

    if (geminiValue < deepseekValue) return { winner: 'Gemini', geminiBetter: true, tie: false };
    return { winner: 'DeepSeek', geminiBetter: false, tie: false };
}

function setRunMeta(prefix, runData) {
    const statusEl = document.getElementById(`${prefix}Status`);
    const tsEl = document.getElementById(`${prefix}Timestamp`);
    const modelEl = document.getElementById(`${prefix}Model`);
    const fileEl = document.getElementById(`${prefix}File`);

    if (!runData || !runData.available) {
        statusEl.textContent = 'Not Found';
        statusEl.className = 'compare-status missing';
        tsEl.textContent = '—';
        modelEl.textContent = '—';
        fileEl.textContent = '—';
        return;
    }

    statusEl.textContent = 'Ready';
    statusEl.className = 'compare-status ready';
    tsEl.textContent = runData.timestamp || '—';
    modelEl.textContent = runData.llm_model || '—';
    fileEl.textContent = `${runData.files?.metrics || '—'} (${runData.eval_mode || 'pipeline'}, ${runData.run_dir || '-'})`;
}

function renderMetricRows(data) {
    const tbody = document.getElementById('providerMetricsBody');
    const deepseek = data.deepseek?.metrics;
    const gemini = data.gemini?.metrics;
    const deltas = data.deltas || {};

    if (!deepseek || !gemini) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="loading">
                    Data belum lengkap. Jalankan evaluasi untuk deepseek dan gemini (mad_mode & eval_mode sama) lalu simpan ke results/.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = METRICS_CONFIG.map(cfg => {
        const vD = deepseek[cfg.key];
        const vG = gemini[cfg.key];
        const delta = deltas[cfg.key];
        const verdict = compareWinner(vD, vG, cfg.higherBetter);
        const deltaClass = verdict.tie
            ? 'neutral'
            : (verdict.geminiBetter ? 'better' : 'worse');

        return `
            <tr>
                <td>${cfg.label}</td>
                <td>${formatMetricValue(vD, cfg.type)}</td>
                <td>${formatMetricValue(vG, cfg.type)}</td>
                <td><span class="delta ${deltaClass}">${formatDelta(delta, cfg.type)}</span></td>
                <td><span class="winner-tag ${deltaClass}">${verdict.winner}</span></td>
            </tr>
        `;
    }).join('');
}

function renderSummary(data) {
    const summaryEl = document.getElementById('providerSummary');
    const deepseek = data.deepseek?.metrics;
    const gemini = data.gemini?.metrics;

    if (!deepseek || !gemini) {
        summaryEl.innerHTML = `
            <p class="compare-empty">
                Data perbandingan belum lengkap. Jalankan evaluasi untuk kedua provider dan simpan hasilnya.
            </p>
        `;
        return;
    }

    const f1Winner = compareWinner(deepseek.f1_score, gemini.f1_score, true).winner;
    const accWinner = compareWinner(deepseek.accuracy, gemini.accuracy, true).winner;
    const timeWinner = compareWinner(deepseek.avg_time_ms, gemini.avg_time_ms, false).winner;

    summaryEl.innerHTML = `
        <p><strong>Model quality:</strong> Accuracy winner: <strong>${accWinner}</strong>, F1 winner: <strong>${f1Winner}</strong>.</p>
        <p><strong>Performance:</strong> Time winner: <strong>${timeWinner}</strong>.</p>
        <p><strong>Note:</strong> Bandingkan run pada dataset yang sama dan setting MAD yang sama (MAD_MAX_ROUNDS, early termination) untuk hasil yang fair.</p>
    `;
}

async function loadProviderComparison() {
    try {
        const evalModeEl = document.getElementById('providerEvalMode');
        const madModeEl = document.getElementById('providerMadMode');
        const evalMode = evalModeEl ? evalModeEl.value : 'pipeline';
        const madMode = madModeEl ? madModeEl.value : 'mad5';

        const response = await fetch(
            `${API_BASE}/api/evaluation/providers?eval_mode=${encodeURIComponent(evalMode)}&mad_mode=${encodeURIComponent(madMode)}`
        );
        const tsEl = document.getElementById('providerCompareTimestamp');

        if (!response.ok) {
            tsEl.textContent = 'No comparison data';
            const payload = await response.json().catch(() => ({}));
            document.getElementById('providerSummary').innerHTML = `
                <p class="compare-empty">${payload.error || 'Failed to load provider comparison data.'}</p>
            `;
            document.getElementById('providerMetricsBody').innerHTML = `
                <tr><td colspan="5" class="loading">No data</td></tr>
            `;
            setRunMeta('deepseek', null);
            setRunMeta('gemini', null);
            return;
        }

        const data = await response.json();
        setRunMeta('deepseek', data.deepseek);
        setRunMeta('gemini', data.gemini);
        renderMetricRows(data);
        renderSummary(data);

        const now = new Date();
        tsEl.textContent = `Updated ${now.toLocaleString('id-ID')}`;

        const dFile = data.deepseek?.files?.metrics || '—';
        const gFile = data.gemini?.files?.metrics || '—';
        document.getElementById('providerCompareFooterInfo').textContent =
            `Mode: ${data.requested_eval_mode || evalMode} | MAD: ${(data.requested_mad_mode || madMode).toUpperCase()} | DeepSeek=${dFile} | Gemini=${gFile}`;
    } catch (error) {
        console.error('Error loading provider comparison:', error);
        document.getElementById('providerCompareTimestamp').textContent = 'Error loading data';
        document.getElementById('providerSummary').innerHTML = `
            <p class="compare-empty">Terjadi error saat memuat data perbandingan provider.</p>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const evalModeEl = document.getElementById('providerEvalMode');
    const madModeEl = document.getElementById('providerMadMode');
    if (evalModeEl) evalModeEl.addEventListener('change', loadProviderComparison);
    if (madModeEl) madModeEl.addEventListener('change', loadProviderComparison);
    loadProviderComparison();
});

