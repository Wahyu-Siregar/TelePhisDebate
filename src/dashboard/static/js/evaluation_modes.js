/**
 * TelePhisDebate evaluation mode comparison page.
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

function compareWinner(baseValue, challengerValue, higherBetter) {
    const EPS = 1e-9;
    if (baseValue == null || challengerValue == null) {
        return { winner: 'N/A', challengerBetter: false, tie: false };
    }
    if (Math.abs(challengerValue - baseValue) <= EPS) {
        return { winner: 'Tie', challengerBetter: false, tie: true };
    }

    if (higherBetter) {
        if (challengerValue > baseValue) return { winner: 'MAD_only', challengerBetter: true, tie: false };
        return { winner: 'Pipeline', challengerBetter: false, tie: false };
    }

    if (challengerValue < baseValue) return { winner: 'MAD_only', challengerBetter: true, tie: false };
    return { winner: 'Pipeline', challengerBetter: false, tie: false };
}

function setRunMeta(prefix, runData) {
    const statusEl = document.getElementById(`${prefix}Status`);
    const tsEl = document.getElementById(`${prefix}Timestamp`);
    const fileEl = document.getElementById(`${prefix}File`);

    if (!runData || !runData.available) {
        statusEl.textContent = 'Not Found';
        statusEl.className = 'compare-status missing';
        tsEl.textContent = '—';
        fileEl.textContent = '—';
        return;
    }

    statusEl.textContent = 'Ready';
    statusEl.className = 'compare-status ready';
    tsEl.textContent = runData.timestamp || '—';
    fileEl.textContent = `${runData.files?.metrics || '—'} (${runData.run_dir || '-'})`;
}

function renderMetricRows(data, madMode) {
    const tbody = document.getElementById('modeMetricsBody');
    const pipeline = data.pipeline?.metrics;
    const madOnly = data.mad_only?.metrics;
    const deltas = data.deltas || {};

    if (!pipeline || !madOnly) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="loading">
                    Data belum lengkap untuk ${madMode}. Jalankan evaluasi mode pipeline dan mad_only.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = METRICS_CONFIG.map(cfg => {
        const vPipeline = pipeline[cfg.key];
        const vMadOnly = madOnly[cfg.key];
        const delta = deltas[cfg.key];
        const verdict = compareWinner(vPipeline, vMadOnly, cfg.higherBetter);
        const stateClass = verdict.tie ? 'neutral' : (verdict.challengerBetter ? 'better' : 'worse');

        return `
            <tr>
                <td>${cfg.label}</td>
                <td>${formatMetricValue(vPipeline, cfg.type)}</td>
                <td>${formatMetricValue(vMadOnly, cfg.type)}</td>
                <td><span class="delta ${stateClass}">${formatDelta(delta, cfg.type)}</span></td>
                <td><span class="winner-tag ${stateClass}">${verdict.winner}</span></td>
            </tr>
        `;
    }).join('');
}

function renderSummary(data, madMode) {
    const summaryEl = document.getElementById('modeSummary');
    const pipeline = data.pipeline?.metrics;
    const madOnly = data.mad_only?.metrics;

    if (!pipeline || !madOnly) {
        summaryEl.innerHTML = `
            <p class="compare-empty">
                Belum ada data lengkap untuk <strong>${madMode}</strong>.
                Jalankan:
                <code>python evaluate.py --dataset data/dataset_mixed_safe_suspicious_phishing.csv --eval-mode pipeline --mad-mode ${madMode} --output results/${madMode}</code>
                <code>python evaluate.py --dataset data/dataset_mixed_safe_suspicious_phishing.csv --eval-mode mad_only --mad-mode ${madMode} --output results/${madMode}_mad_only</code>
            </p>
        `;
        return;
    }

    const f1Winner = compareWinner(pipeline.f1_score, madOnly.f1_score, true).winner;
    const accWinner = compareWinner(pipeline.accuracy, madOnly.accuracy, true).winner;
    const timeWinner = compareWinner(pipeline.avg_time_ms, madOnly.avg_time_ms, false).winner;

    summaryEl.innerHTML = `
        <p><strong>${madMode.toUpperCase()} quality:</strong> Accuracy winner: <strong>${accWinner}</strong>, F1 winner: <strong>${f1Winner}</strong>.</p>
        <p><strong>Performance:</strong> Time winner: <strong>${timeWinner}</strong>.</p>
        <p><strong>Interpretation:</strong> Pipeline biasanya lebih realistis untuk deployment karena tetap menggunakan Triage + Single-Shot sebagai context router.</p>
    `;
}

async function loadModeComparison() {
    try {
        const selector = document.getElementById('modeMadSelect');
        const madMode = selector ? selector.value : 'mad5';
        const response = await fetch(`${API_BASE}/api/evaluation/modes?mad_mode=${encodeURIComponent(madMode)}`);
        const tsEl = document.getElementById('modeCompareTimestamp');

        if (!response.ok) {
            tsEl.textContent = 'No comparison data';
            const payload = await response.json().catch(() => ({}));
            document.getElementById('modeSummary').innerHTML = `
                <p class="compare-empty">${payload.error || 'Failed to load mode comparison data.'}</p>
            `;
            return;
        }

        const data = await response.json();
        setRunMeta('pipeline', data.pipeline);
        setRunMeta('madOnly', data.mad_only);
        renderMetricRows(data, data.mad_mode || madMode);
        renderSummary(data, data.mad_mode || madMode);

        const now = new Date();
        tsEl.textContent = `Updated ${now.toLocaleString('id-ID')}`;

        const pipelineFile = data.pipeline?.files?.metrics || '—';
        const madOnlyFile = data.mad_only?.files?.metrics || '—';
        document.getElementById('modeCompareFooterInfo').textContent =
            `${(data.mad_mode || madMode).toUpperCase()} | Pipeline=${pipelineFile} | MAD_only=${madOnlyFile}`;
    } catch (error) {
        console.error('Error loading mode comparison:', error);
        document.getElementById('modeCompareTimestamp').textContent = 'Error loading data';
        document.getElementById('modeSummary').innerHTML = `
            <p class="compare-empty">Terjadi error saat memuat data perbandingan mode.</p>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const selector = document.getElementById('modeMadSelect');
    if (selector) {
        selector.addEventListener('change', loadModeComparison);
    }
    loadModeComparison();
});
