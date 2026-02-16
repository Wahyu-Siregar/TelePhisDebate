const API_BASE = '';

let allRuns = [];

function qs(id) {
  return document.getElementById(id);
}

function norm(s) {
  return (s || '').toString().trim().toLowerCase();
}

function escapeHtml(s) {
  return (s || '').toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function buildOpenLink(run) {
  // Open run inside the existing Evaluation page via query params.
  const runDir = encodeURIComponent(run.run_dir || '');
  const tsKey = encodeURIComponent((run.file || '').replace('eval_full_', '').replace('.json', ''));
  return `/evaluation?run_dir=${runDir}&timestamp=${tsKey}`;
}

function applyFilters() {
  const evalMode = norm(qs('filterEvalMode').value);
  const madMode = norm(qs('filterMadMode').value);
  const provider = norm(qs('filterProvider').value);
  const q = norm(qs('filterQuery').value);

  const filtered = allRuns.filter(r => {
    if (evalMode && norm(r.eval_mode) !== evalMode) return false;
    if (madMode && norm(r.mad_mode) !== madMode) return false;
    if (provider && norm(r.llm_provider) !== provider) return false;
    if (q) {
      const hay = [
        r.timestamp,
        r.run_dir,
        r.llm_provider,
        r.llm_model,
        r.eval_mode,
        r.mad_mode,
        r.file
      ].map(norm).join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  renderTable(filtered);
  qs('runCount').textContent = `${filtered.length} runs`;
}

function renderTable(runs) {
  const body = qs('runsTableBody');
  if (!runs.length) {
    body.innerHTML = `<tr><td colspan="7" class="loading">No runs found.</td></tr>`;
    return;
  }

  body.innerHTML = runs.map(r => {
    const open = buildOpenLink(r);
    return `
      <tr>
        <td>${escapeHtml(r.timestamp || '—')}</td>
        <td><code>${escapeHtml(r.eval_mode || '—')}</code></td>
        <td><code>${escapeHtml(r.mad_mode || '—')}</code></td>
        <td><code>${escapeHtml(r.llm_provider || '—')}</code></td>
        <td><code>${escapeHtml(r.llm_model || '—')}</code></td>
        <td><code>${escapeHtml(r.run_dir || '—')}</code></td>
        <td><a class="nav-link" href="${open}">Open</a></td>
      </tr>
    `;
  }).join('');
}

async function loadRuns() {
  const res = await fetch(`${API_BASE}/api/evaluation/list`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  allRuns = await res.json();
  qs('runCount').textContent = `${allRuns.length} runs`;
  applyFilters();
}

function wireFilters() {
  ['filterEvalMode', 'filterMadMode', 'filterProvider', 'filterQuery'].forEach(id => {
    qs(id).addEventListener('input', applyFilters);
    qs(id).addEventListener('change', applyFilters);
  });
}

window.addEventListener('DOMContentLoaded', async () => {
  wireFilters();
  try {
    await loadRuns();
  } catch (e) {
    console.error(e);
    qs('runsTableBody').innerHTML =
      `<tr><td colspan="7" class="loading">Failed to load runs: ${escapeHtml(e.message)}</td></tr>`;
    qs('runCount').textContent = 'Error';
  }
});

