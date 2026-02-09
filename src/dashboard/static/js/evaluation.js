/**
 * TelePhisDebate Evaluation Page JavaScript — Brutalism Edition
 */

const API_BASE = '';

let stageDistChart = null;
let expectedDistChart = null;
let predictedDistChart = null;

// ============================================================
// Helpers
// ============================================================

function formatNumber(n) {
    return n != null ? n.toLocaleString() : '—';
}

function formatPercent(v) {
    return v != null ? (v * 100).toFixed(2) + '%' : '—';
}

function formatTime(ms) {
    if (ms == null) return '—';
    if (ms >= 60000) return (ms / 60000).toFixed(1) + 'm';
    if (ms >= 1000) return (ms / 1000).toFixed(1) + 's';
    return ms + 'ms';
}

function formatCost(usd) {
    if (usd == null) return '—';
    return '$' + usd.toFixed(6);
}

const STAGE_NAMES = {
    'triage': 'Triage',
    'single_shot': 'Single-Shot',
    'mad': 'MAD'
};

const CHART_COLORS = {
    black: '#000000',
    white: '#ffffff',
    gray300: '#d4d4d4',
    gray500: '#737373',
    gray700: '#404040'
};

// ============================================================
// Data Loading
// ============================================================

async function loadEvaluationData() {
    try {
        const response = await fetch(`${API_BASE}/api/evaluation`);
        if (!response.ok) {
            if (response.status === 404) {
                document.querySelector('.container').innerHTML =
                    '<div class="eval-empty"><h2>No Evaluation Results</h2>' +
                    '<p>Jalankan <code>python evaluate.py</code> terlebih dahulu untuk generate hasil evaluasi.</p></div>';
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        renderAll(data);
    } catch (error) {
        console.error('Error loading evaluation data:', error);
    }
}

// ============================================================
// Render Functions
// ============================================================

function renderAll(data) {
    const m = data.metrics;

    // Timestamp
    document.getElementById('evalTimestamp').textContent = data.eval_timestamp || '—';

    // Primary Metrics
    renderMetricCard('metricAccuracy', 'barAccuracy', m.accuracy);
    renderMetricCard('metricPrecision', 'barPrecision', m.precision);
    renderMetricCard('metricRecall', 'barRecall', m.recall);
    renderMetricCard('metricF1', 'barF1', m.f1_score);

    // Summary stats
    document.getElementById('summaryTotal').textContent = formatNumber(m.total);
    document.getElementById('summaryCorrect').textContent = formatNumber(m.correct);
    document.getElementById('summaryWrong').textContent = formatNumber(m.wrong);
    document.getElementById('summaryDetectionRate').textContent = formatPercent(m.detection_rate);

    // Confusion Matrix
    renderConfusionMatrix(m.confusion_matrix);

    // Stage Distribution
    renderStageDistribution(m.stage_distribution, m.stage_percentage, m.stage_accuracy);

    // Prediction Distribution Charts
    renderDistributionChart('expectedDistChart', m.expected_distribution, 'expected');
    renderDistributionChart('predictedDistChart', m.predicted_distribution, 'predicted');

    // Performance & Cost
    renderPerformance(m);

    // Misclassifications
    renderMisclassifications(data.wrong_predictions);

    // All Details
    renderDetails(data.details);

    // File info
    const fileInfo = data.files;
    if (fileInfo) {
        document.getElementById('evalFileInfo').textContent =
            `Source: ${fileInfo.metrics || '—'}`;
    }
}

function renderMetricCard(valueId, barId, value) {
    const pct = value != null ? (value * 100).toFixed(2) : 0;
    document.getElementById(valueId).textContent = pct + '%';
    const bar = document.getElementById(barId);
    bar.style.width = pct + '%';
    // Color intensity based on value
    if (value >= 0.9) bar.classList.add('high');
    else if (value >= 0.7) bar.classList.add('mid');
    else bar.classList.add('low');
}

function renderConfusionMatrix(cm) {
    if (!cm) return;
    setCMCell('cmTP', cm.tp, 'tp');
    setCMCell('cmFN', cm.fn, 'fn');
    setCMCell('cmFP', cm.fp, 'fp');
    setCMCell('cmTN', cm.tn, 'tn');
}

function setCMCell(id, value, type) {
    const cell = document.getElementById(id);
    cell.querySelector('.cm-value').textContent = value;
    // Highlight non-zero values
    if (value > 0 && (type === 'fn' || type === 'fp')) {
        cell.classList.add('danger');
    } else if (value > 0 && (type === 'tp' || type === 'tn')) {
        cell.classList.add('success');
    }
}

function renderStageDistribution(dist, pct, accuracy) {
    if (!dist) return;

    const labels = [];
    const values = [];
    const bgColors = [];

    const stageColors = {
        'triage': '#6366f1',
        'single_shot': '#f59e0b',
        'mad': '#10b981'
    };

    for (const [stage, count] of Object.entries(dist)) {
        labels.push(STAGE_NAMES[stage] || stage);
        values.push(count);
        bgColors.push(stageColors[stage] || CHART_COLORS.gray500);
    }

    const ctx = document.getElementById('stageDistChart').getContext('2d');
    if (stageDistChart) stageDistChart.destroy();
    stageDistChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: bgColors,
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        font: { family: "'JetBrains Mono'", size: 10, weight: 600 },
                        color: CHART_COLORS.black,
                        padding: 10,
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                }
            }
        }
    });

    // Stage accuracy grid
    const grid = document.getElementById('stageAccuracyGrid');
    grid.innerHTML = '';
    if (accuracy) {
        for (const [stage, acc] of Object.entries(accuracy)) {
            const count = dist[stage] || 0;
            const percentage = pct ? (pct[stage] || 0) : 0;
            grid.innerHTML += `
                <div class="stage-acc-item">
                    <strong>${STAGE_NAMES[stage] || stage}</strong>
                    <span>${count} msgs (${percentage.toFixed(1)}%)</span>
                    <span>Accuracy: ${(acc * 100).toFixed(1)}%</span>
                </div>
            `;
        }
    }
}

function renderDistributionChart(canvasId, dist, type) {
    if (!dist) return;

    const labels = Object.keys(dist);
    const values = Object.values(dist);

    const colorMap = {
        'PHISHING': '#ef4444',
        'SAFE': '#22c55e',
        'SUSPICIOUS': '#f59e0b'
    };

    const bgColors = labels.map(l => colorMap[l] || CHART_COLORS.gray500);

    const ctx = document.getElementById(canvasId).getContext('2d');
    const ref = type === 'expected' ? expectedDistChart : predictedDistChart;
    if (ref) ref.destroy();

    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: bgColors,
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        font: { family: "'JetBrains Mono'", size: 10, weight: 600 },
                        color: CHART_COLORS.black,
                        padding: 10,
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                }
            }
        }
    });

    if (type === 'expected') expectedDistChart = chart;
    else predictedDistChart = chart;
}

function renderPerformance(m) {
    document.getElementById('perfTotalTime').textContent =
        m.total_time_seconds != null ? m.total_time_seconds.toFixed(1) + 's' : '—';
    document.getElementById('perfAvgTime').textContent = formatTime(m.avg_time_ms);
    document.getElementById('perfMinTime').textContent = formatTime(m.min_time_ms);
    document.getElementById('perfMaxTime').textContent = formatTime(m.max_time_ms);
    document.getElementById('perfTokensTotal').textContent = formatNumber(m.total_tokens);
    document.getElementById('perfTokensIn').textContent = formatNumber(m.total_tokens_input);
    document.getElementById('perfTokensOut').textContent = formatNumber(m.total_tokens_output);
    document.getElementById('perfCost').textContent = formatCost(m.total_cost_usd);
}

function renderMisclassifications(wrong) {
    const count = wrong ? wrong.length : 0;
    document.getElementById('misclassCount').textContent = count;

    const tbody = document.getElementById('misclassTableBody');

    if (count === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">Tidak ada misclassification</td></tr>';
        document.getElementById('misclassSection').style.display = 'none';
        return;
    }

    document.getElementById('misclassSection').style.display = '';
    tbody.innerHTML = wrong.map(d => `
        <tr class="misclass-row">
            <td>${d.index}</td>
            <td class="msg-text" title="${escapeHtml(d.text)}">${escapeHtml(d.text)}</td>
            <td><span class="badge badge-${d.expected.toLowerCase()}">${d.expected}</span></td>
            <td><span class="badge badge-${d.predicted.toLowerCase()}">${d.predicted}</span></td>
            <td>${STAGE_NAMES[d.decided_by] || d.decided_by}</td>
            <td>${d.triage_risk_score}</td>
        </tr>
    `).join('');
}

function renderDetails(details) {
    if (!details) return;

    document.getElementById('detailsCount').textContent = details.length;
    const tbody = document.getElementById('detailsTableBody');

    tbody.innerHTML = details.map(d => `
        <tr class="${d.correct ? '' : 'row-wrong'}">
            <td>${d.index}</td>
            <td class="msg-text" title="${escapeHtml(d.text)}">${escapeHtml(d.text)}</td>
            <td><span class="badge badge-${d.expected.toLowerCase()}">${d.expected}</span></td>
            <td><span class="badge badge-${d.predicted.toLowerCase()}">${d.predicted}</span></td>
            <td>${d.correct
                ? '<span class="result-correct"><i class="iconoir-check"></i></span>'
                : '<span class="result-wrong"><i class="iconoir-xmark"></i></span>'
            }</td>
            <td>${(d.confidence * 100).toFixed(0)}%</td>
            <td>${STAGE_NAMES[d.decided_by] || d.decided_by}</td>
            <td>${formatNumber(d.processing_time_ms)}</td>
            <td>${formatNumber(d.tokens_total)}</td>
            <td class="flags-cell">${d.triage_flags || '—'}</td>
        </tr>
    `).join('');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// Init
// ============================================================

document.addEventListener('DOMContentLoaded', loadEvaluationData);
