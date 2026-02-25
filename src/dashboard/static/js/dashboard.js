/**
 * TelePhisDebate Dashboard JavaScript — Brutalism Edition
 */

// API Base URL
const API_BASE = '';

// Chart instances
let classificationChart = null;
let stageChart = null;
let hourlyChart = null;

// ============================================================
// Data Fetching
// ============================================================

async function fetchData(endpoint) {
    try {
        const response = await fetch(`${API_BASE}/api/${endpoint}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        return null;
    }
}

// ============================================================
// Update Functions
// ============================================================

async function updateStats() {
    const stats = await fetchData('stats');
    if (!stats) return;
    
    document.getElementById('statSafe').textContent = stats.safe.toLocaleString();
    document.getElementById('statSuspicious').textContent = stats.suspicious.toLocaleString();
    document.getElementById('statPhishing').textContent = stats.phishing.toLocaleString();
    document.getElementById('statTotal').textContent = stats.total.toLocaleString();
    document.getElementById('detectionRate').textContent = stats.detection_rate;
    
    updateClassificationChart(stats);
}

async function updateStageStats() {
    const stages = await fetchData('stats/stages');
    if (!stages) return;
    
    document.getElementById('triageCount').textContent = stages.triage.count.toLocaleString();
    document.getElementById('triageTime').textContent = `${stages.triage.avg_time}ms`;
    document.getElementById('triageTokens').textContent = stages.triage.tokens.toLocaleString();
    
    document.getElementById('singleShotCount').textContent = stages.single_shot.count.toLocaleString();
    document.getElementById('singleShotTime').textContent = `${stages.single_shot.avg_time}ms`;
    document.getElementById('singleShotTokens').textContent = stages.single_shot.avg_tokens.toLocaleString();
    
    document.getElementById('madCount').textContent = stages.mad.count.toLocaleString();
    document.getElementById('madTime').textContent = `${stages.mad.avg_time}ms`;
    document.getElementById('madTokens').textContent = stages.mad.avg_tokens.toLocaleString();
    
    updateStageChart(stages);
}

// Current activity range
let activityRange = '24h';

async function updateActivityChart(range) {
    if (range) activityRange = range;
    
    const result = await fetchData(`stats/activity?range=${activityRange}`);
    if (!result || !result.data) return;
    
    const items = result.data;
    const labels = items.map(h => h.label);
    const safeData = items.map(h => h.safe);
    const suspiciousData = items.map(h => h.suspicious);
    const phishingData = items.map(h => h.phishing);
    
    // Update title
    const titles = { '24h': 'Activity (Last 24 Hours)', '7d': 'Activity (Last 1 Week)', '30d': 'Activity (Last 1 Month)' };
    document.getElementById('activityTitle').textContent = titles[activityRange] || titles['24h'];
    
    // Update active button
    document.querySelectorAll('.range-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.range === activityRange);
    });
    
    const xTickConfig = {
        color: '#525252',
        font: { family: 'JetBrains Mono', size: activityRange === '30d' ? 9 : 11 },
        maxRotation: activityRange === '30d' ? 45 : 0
    };
    
    if (hourlyChart) {
        hourlyChart.data.labels = labels;
        hourlyChart.data.datasets[0].data = safeData;
        hourlyChart.data.datasets[1].data = suspiciousData;
        hourlyChart.data.datasets[2].data = phishingData;
        hourlyChart.options.scales.x.ticks = xTickConfig;
        hourlyChart.update();
    } else {
        const ctx = document.getElementById('hourlyChart').getContext('2d');
        hourlyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Safe',
                        data: safeData,
                        backgroundColor: '#22c55e',
                        borderColor: '#16a34a',
                        borderWidth: 1
                    },
                    {
                        label: 'Suspicious',
                        data: suspiciousData,
                        backgroundColor: '#f59e0b',
                        borderColor: '#d97706',
                        borderWidth: 1
                    },
                    {
                        label: 'Phishing',
                        data: phishingData,
                        backgroundColor: '#ef4444',
                        borderColor: '#dc2626',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        stacked: true,
                        grid: { color: '#e5e5e5' },
                        ticks: xTickConfig
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        grid: { color: '#e5e5e5' },
                        ticks: { color: '#525252', font: { family: 'JetBrains Mono' } }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#000000', font: { family: 'JetBrains Mono', weight: 'bold' } }
                    }
                }
            }
        });
    }
}

function updateClassificationChart(stats) {
    const data = [stats.safe, stats.suspicious, stats.phishing];
    
    if (classificationChart) {
        classificationChart.data.datasets[0].data = data;
        classificationChart.update();
    } else {
        const ctx = document.getElementById('classificationChart').getContext('2d');
        classificationChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Safe', 'Suspicious', 'Phishing'],
                datasets: [{
                    data: data,
                    backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
                    borderColor: '#ffffff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: true,
                cutout: '60%',
                plugins: { legend: { display: false } }
            }
        });
    }
}

function updateStageChart(stages) {
    const data = [stages.triage.count, stages.single_shot.count, stages.mad.count];
    
    if (stageChart) {
        stageChart.data.datasets[0].data = data;
        stageChart.update();
    } else {
        const ctx = document.getElementById('stageChart').getContext('2d');
        stageChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Triage', 'Single-Shot', 'MAD'],
                datasets: [{
                    data: data,
                    backgroundColor: ['#6366f1', '#f59e0b', '#10b981'],
                    borderColor: '#ffffff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: true,
                cutout: '60%',
                plugins: { legend: { display: false } }
            }
        });
    }
}

async function updatePhishingTable() {
    const detections = await fetchData('detections/phishing');
    const tbody = document.getElementById('phishingTableBody');
    
    if (!detections || detections.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">No phishing detections yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = detections.map(d => `
        <tr>
            <td>${formatTimestamp(d.timestamp)}</td>
            <td><span class="badge ${d.stage}">${d.stage}</span></td>
            <td>${formatConfidencePercent(d.confidence)}</td>
            <td>${formatFlagsCell(d.triage_flags)}</td>
        </tr>
    `).join('');
}

function formatFlagsCell(flags) {
    if (Array.isArray(flags)) {
        return flags.length > 0 ? escapeHtml(flags.join(', ')) : '-';
    }
    if (typeof flags === 'string') {
        const trimmed = flags.trim();
        return trimmed ? escapeHtml(trimmed) : '-';
    }
    return '-';
}

function formatConfidencePercent(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return '-';
    return `${(num * 100).toFixed(0)}%`;
}

async function updateMessagesTable() {
    const messages = await fetchData('messages/recent');
    const tbody = document.getElementById('messagesTableBody');
    
    if (!messages || messages.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">No messages processed yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = messages.map(m => `
        <tr>
            <td>${formatTimestamp(m.timestamp)}</td>
            <td>${escapeHtml(m.content)}</td>
            <td><span class="badge ${m.classification.toLowerCase()}">${m.classification}</span></td>
            <td>${formatConfidencePercent(m.confidence)}</td>
        </tr>
    `).join('');
}

async function updateApiUsage() {
    const usage = await fetchData('usage');
    if (!usage) return;
    
    document.getElementById('tokensInput').textContent = (usage.tokens_input || 0).toLocaleString();
    document.getElementById('tokensOutput').textContent = (usage.tokens_output || 0).toLocaleString();
    document.getElementById('totalRequests').textContent = (usage.total_requests || 0).toLocaleString();
}

// ============================================================
// Debates — Collapsible Cards
// ============================================================

async function updateDebates() {
    const debates = await fetchData('debates/recent');
    const container = document.getElementById('debatesContainer');
    
    if (!debates || debates.length === 0) {
        container.innerHTML = `
            <div class="no-debates">
                <p>Belum ada debate</p>
                <p>Debate terjadi ketika Single-Shot LLM tidak yakin dengan klasifikasinya</p>
            </div>
        `;
        return;
    }
    
    // Save currently expanded debate IDs before re-render
    const openIds = new Set(
        Array.from(container.querySelectorAll('.debate-card.open'))
            .map(card => card.dataset.debateId)
            .filter(Boolean)
    );
    
    container.innerHTML = debates.map(debate => renderDebateCard(debate)).join('');
    
    // Restore expanded state
    if (openIds.size > 0) {
        container.querySelectorAll('.debate-card').forEach(card => {
            if (openIds.has(card.dataset.debateId)) {
                card.classList.add('open');
            }
        });
    }
}

function renderDebateCard(debate) {
    const decisionClass = debate.decision.toLowerCase();
    const hasRound2 = debate.round_2 && debate.round_2.length > 0;
    const confidenceText = (debate.confidence * 100).toFixed(0) + '%';
    const consensusText = debate.consensus_reached ? 'KONSENSUS' : 'VOTING';
    
    return `
        <div class="debate-card" data-debate-id="${debate.id}" onclick="toggleDebate(this)">
            <button class="debate-toggle" type="button">
                <div class="debate-toggle-left">
                    <span class="toggle-arrow">&#9654;</span>
                    <span class="debate-decision-tag ${decisionClass}">${debate.decision}</span>
                    <span class="debate-info">
                        <span>${debate.rounds_executed} Round${debate.rounds_executed > 1 ? 's' : ''}</span>
                        <span>${consensusText}</span>
                        <span>${formatTimestamp(debate.timestamp)}</span>
                    </span>
                </div>
                <div class="debate-toggle-right">
                    <span class="debate-confidence">${confidenceText}</span>
                </div>
            </button>
            <div class="debate-body">
                <div class="debate-rounds">
                    ${renderDebateRound(1, debate.round_1)}
                    ${hasRound2 ? renderDebateRound(2, debate.round_2) : ''}
                </div>
            </div>
        </div>
    `;
}

function toggleDebate(card) {
    card.classList.toggle('open');
}

function renderDebateRound(roundNumber, agents) {
    if (!agents || agents.length === 0) return '';
    
    const roundLabel = roundNumber === 1 ? 'ROUND 1 — INDEPENDENT ANALYSIS' : 'ROUND 2 — DELIBERATION';
    
    return `
        <div class="debate-round">
            <div class="round-title">${roundLabel}</div>
            <div class="agents-conversation">
                ${agents.map(agent => renderAgentMessage(agent)).join('')}
            </div>
        </div>
    `;
}

function renderAgentMessage(agent) {
    const agentClass = agent.agent.toLowerCase().replace(/ /g, '_');
    const stanceClass = agent.stance.toLowerCase();
    const confidencePercent = (agent.confidence * 100);
    const agentInfo = getAgentInfo(agent.agent);
    
    return `
        <div class="agent-message ${agentClass}">
            <div class="agent-avatar">${agentInfo.icon}</div>
            <div class="agent-content">
                <div class="agent-header">
                    <span class="agent-name">${agentInfo.name}</span>
                    <div class="agent-stance">
                        <span class="stance-badge ${stanceClass}">${agent.stance}</span>
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                        </div>
                        <span style="font-size: 0.625rem; font-weight: 700;">
                            ${confidencePercent.toFixed(0)}%
                        </span>
                    </div>
                </div>
                <div class="agent-arguments">
                    ${agent.arguments && agent.arguments.length > 0 
                        ? `<ul>${agent.arguments.map(arg => `<li>${escapeHtml(arg)}</li>`).join('')}</ul>`
                        : '<em>No detailed arguments provided</em>'
                    }
                </div>
            </div>
        </div>
    `;
}

function getAgentInfo(agentType) {
    const agents = {
        'content_analyzer': { name: 'Content Analyzer', icon: '<i class="iconoir-doc-magnifying-glass"></i>' },
        'security_validator': { name: 'Security Validator', icon: '<i class="iconoir-pc-firewall"></i>' },
        'social_context_evaluator': { name: 'Social Context', icon: '<i class="iconoir-community"></i>' }
    };
    return agents[agentType.toLowerCase()] || { name: agentType, icon: '<i class="iconoir-brain"></i>' };
}

// ============================================================
// Helper Functions
// ============================================================

function formatTimestamp(ts) {
    if (!ts) return '-';
    try {
        const date = new Date(ts);
        return date.toLocaleString('id-ID', {
            day: '2-digit',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return ts;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateLastUpdate() {
    const now = new Date().toLocaleTimeString('id-ID');
    document.getElementById('lastUpdate').textContent = `Last update: ${now}`;
}

// ============================================================
// Initialization
// ============================================================

async function refreshAll() {
    await Promise.all([
        updateStats(),
        updateStageStats(),
        updateActivityChart(),
        updatePhishingTable(),
        updateMessagesTable(),
        updateApiUsage(),
        updateDebates()
    ]);
    updateLastUpdate();
}

document.addEventListener('DOMContentLoaded', () => {
    // Range selector buttons
    document.querySelectorAll('.range-btn').forEach(btn => {
        btn.addEventListener('click', () => updateActivityChart(btn.dataset.range));
    });
    
    refreshAll();
    setInterval(refreshAll, 30000);
});
