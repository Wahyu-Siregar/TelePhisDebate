/**
 * TelePhisDebate MAD3 vs MAD5 comparison page.
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

function compareWinner(mad3Value, mad5Value, higherBetter) {
    const EPS = 1e-9;
    if (mad3Value == null || mad5Value == null) {
        return { winner: 'N/A', mad5Better: false, tie: false };
    }

    if (Math.abs(mad5Value - mad3Value) <= EPS) {
        return { winner: 'Tie', mad5Better: false, tie: true };
    }

    if (higherBetter) {
        if (mad5Value > mad3Value) return { winner: 'MAD5', mad5Better: true, tie: false };
        return { winner: 'MAD3', mad5Better: false, tie: false };
    }

    if (mad5Value < mad3Value) return { winner: 'MAD5', mad5Better: true, tie: false };
    return { winner: 'MAD3', mad5Better: false, tie: false };
}

function setRunMeta(modePrefix, runData) {
    const statusEl = document.getElementById(`${modePrefix}Status`);
    const tsEl = document.getElementById(`${modePrefix}Timestamp`);
    const fileEl = document.getElementById(`${modePrefix}File`);

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
    fileEl.textContent = `${runData.files?.metrics || '—'} (${runData.eval_mode || 'pipeline'}, ${runData.run_dir || '-'})`;
}

function renderStageSummary(modePrefix, runData) {
    const metrics = runData?.metrics || {};
    const total = Number(metrics.total || 0);
    const madCount = Number((metrics.stage_distribution || {}).mad || 0);
    const share = total > 0 ? (madCount / total) * 100 : 0;

    document.getElementById(`${modePrefix}StageCount`).textContent = madCount.toLocaleString();
    document.getElementById(`${modePrefix}Total`).textContent = total.toLocaleString();
    document.getElementById(`${modePrefix}MadShare`).textContent = `${share.toFixed(1)}%`;
}

function renderMetricRows(data, requestedEvalMode) {
    const tbody = document.getElementById('compareMetricsBody');
    const mad3 = data.mad3?.metrics;
    const mad5 = data.mad5?.metrics;
    const deltas = data.deltas || {};

    if (!mad3 || !mad5) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="loading">
                    Data belum lengkap untuk mode <strong>${requestedEvalMode}</strong>.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = METRICS_CONFIG.map(cfg => {
        const v3 = mad3[cfg.key];
        const v5 = mad5[cfg.key];
        const delta = deltas[cfg.key];
        const verdict = compareWinner(v3, v5, cfg.higherBetter);
        const deltaClass = verdict.tie
            ? 'neutral'
            : (verdict.mad5Better ? 'better' : 'worse');

        return `
            <tr>
                <td>${cfg.label}</td>
                <td>${formatMetricValue(v3, cfg.type)}</td>
                <td>${formatMetricValue(v5, cfg.type)}</td>
                <td><span class="delta ${deltaClass}">${formatDelta(delta, cfg.type)}</span></td>
                <td><span class="winner-tag ${deltaClass}">${verdict.winner}</span></td>
            </tr>
        `;
    }).join('');
}

function renderSummary(data, requestedEvalMode) {
    const summaryEl = document.getElementById('compareSummary');
    const mad3 = data.mad3?.metrics;
    const mad5 = data.mad5?.metrics;

    if (!mad3 || !mad5) {
        summaryEl.innerHTML = `
            <p class="compare-empty">
                Data perbandingan belum lengkap untuk mode <strong>${requestedEvalMode}</strong>.
                Jalankan evaluasi mad3 dan mad5 dengan eval mode yang sama terlebih dahulu.
            </p>
        `;
        return;
    }

    const f1Winner = compareWinner(mad3.f1_score, mad5.f1_score, true).winner;
    const accWinner = compareWinner(mad3.accuracy, mad5.accuracy, true).winner;
    const timeWinner = compareWinner(mad3.avg_time_ms, mad5.avg_time_ms, false).winner;

    summaryEl.innerHTML = `
        <p><strong>Model quality:</strong> Accuracy winner: <strong>${accWinner}</strong>, F1 winner: <strong>${f1Winner}</strong>.</p>
        <p><strong>Performance:</strong> Time winner: <strong>${timeWinner}</strong>.</p>
        <p><strong>Recommendation:</strong> Prioritaskan model yang menang di F1 jika target utama adalah akurasi deteksi phishing.</p>
    `;
}

async function loadComparison() {
    try {
        const selector = document.getElementById('compareEvalMode');
        const evalMode = selector ? selector.value : 'pipeline';
        const response = await fetch(`${API_BASE}/api/evaluation/compare?eval_mode=${encodeURIComponent(evalMode)}`);
        const tsEl = document.getElementById('compareTimestamp');

        if (!response.ok) {
            tsEl.textContent = 'No comparison data';
            const payload = await response.json().catch(() => ({}));
            document.getElementById('compareSummary').innerHTML = `
                <p class="compare-empty">${payload.error || 'Failed to load comparison data.'}</p>
            `;
            return;
        }

        const data = await response.json();
        setRunMeta('mad3', data.mad3);
        setRunMeta('mad5', data.mad5);
        renderMetricRows(data, data.requested_eval_mode || evalMode);
        renderStageSummary('mad3', data.mad3);
        renderStageSummary('mad5', data.mad5);
        renderSummary(data, data.requested_eval_mode || evalMode);

        const now = new Date();
        tsEl.textContent = `Updated ${now.toLocaleString('id-ID')}`;

        const mad3File = data.mad3?.files?.metrics || '—';
        const mad5File = data.mad5?.files?.metrics || '—';
        document.getElementById('compareFooterInfo').textContent =
            `Mode: ${data.requested_eval_mode || evalMode} | MAD3=${mad3File} | MAD5=${mad5File}`;
    } catch (error) {
        console.error('Error loading MAD comparison:', error);
        document.getElementById('compareTimestamp').textContent = 'Error loading data';
        document.getElementById('compareSummary').innerHTML = `
            <p class="compare-empty">Terjadi error saat memuat data perbandingan.</p>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const selector = document.getElementById('compareEvalMode');
    if (selector) {
        selector.addEventListener('change', loadComparison);
    }
    loadComparison();
});
