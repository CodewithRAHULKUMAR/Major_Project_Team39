// ========== STATE ==========
let appState = {
    dataLoaded: false,
    currentPage: 'upload',
    trains: [],
    conflicts: [],
    recommendations: [],
    kpis: null,
    networkData: null,
};

// ========== NAVIGATION ==========
function switchPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    const page = document.getElementById('page-' + pageId);
    const tab = document.querySelector(`.nav-tab[data-page="${pageId}"]`);
    if (page) page.classList.add('active');
    if (tab) tab.classList.add('active');
    appState.currentPage = pageId;
    if (pageId === 'network' && appState.dataLoaded) loadNetwork();
    if (pageId === 'conflicts' && appState.dataLoaded) loadConflicts();
    if (pageId === 'performance' && appState.dataLoaded) loadPerformance();
    if (pageId === 'analysis' && appState.dataLoaded) loadTrainList();
    if (pageId === 'simulation' && appState.dataLoaded) loadSimOptions();
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchPage(tab.dataset.page));
    });
    switchPage('overview');
    autoInit();
});

// ========== UTILITIES ==========
function showLoading(msg) {
    const overlay = document.getElementById('loading-overlay');
    overlay.querySelector('.loading-text').textContent = msg || 'Processing...';
    overlay.classList.add('show');
}
function hideLoading() { document.getElementById('loading-overlay').classList.remove('show'); }

function toast(msg, type = 'success') {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<span>${type === 'success' ? '✓' : '✕'}</span> ${msg}`;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
}

function severityTag(severity) {
    const map = { 'CRITICAL': 'tag-red', 'HIGH': 'tag-yellow', 'MEDIUM': 'tag-blue', 'LOW': 'tag-green' };
    return `<span class="tag ${map[severity] || 'tag-blue'}">${severity}</span>`;
}

function statusTag(status) {
    if (status === 'Delayed') return '<span class="tag tag-red">Delayed</span>';
    if (status === 'On Time') return '<span class="tag tag-green">On Time</span>';
    if (status === 'Early') return '<span class="tag tag-green">Early</span>';
    return `<span class="tag tag-blue">${status}</span>`;
}

// ========== AUTO INIT (NO UPLOAD NEEDED) ==========
async function autoInit() {
    try {
        const res = await fetch('/api/init');
        const data = await res.json();

        document.getElementById('overview-loading').style.display = 'none';
        const resultsDiv = document.getElementById('overview-results');
        resultsDiv.style.display = 'block';

        if (!data.success) {
            resultsDiv.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>Data Not Loaded</h3><p>${data.error || 'Check data/ folder'}</p></div>`;
            return;
        }

        appState.dataLoaded = true;
        document.querySelector('.status-dot').classList.add('active');
        document.querySelector('.status-label').textContent = 'System Active';

        renderOverview(data);
        toast('System initialized — data loaded, models trained!');

        const badge = document.querySelector('.nav-tab[data-page="conflicts"] .badge');
        if (badge) badge.textContent = data.conflicts_count;

    } catch (err) {
        document.getElementById('overview-loading').style.display = 'none';
        const resultsDiv = document.getElementById('overview-results');
        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>Init Failed</h3><p>${err.message}</p></div>`;
    }
}

function renderOverview(data) {
    const s = data.summary;
    const m = data.model_metrics;
    const container = document.getElementById('overview-results');
    container.innerHTML = `
    <div class="grid-4" style="margin-bottom:1.5rem">
        <div class="kpi kpi-blue"><div class="kpi-label">Total Blocks</div><div class="kpi-value">${s.total_blocks}</div><div class="kpi-sub">${s.single_line_blocks} single / ${s.double_line_blocks} double</div></div>
        <div class="kpi kpi-green"><div class="kpi-label">Total Trains</div><div class="kpi-value">${s.total_trains}</div><div class="kpi-sub">${s.up_trains} UP / ${s.down_trains} DOWN</div></div>
        <div class="kpi kpi-purple"><div class="kpi-label">Movements</div><div class="kpi-value">${s.total_movements}</div><div class="kpi-sub">${s.conflict_movements} with conflicts</div></div>
        <div class="kpi kpi-yellow"><div class="kpi-label">On-Time %</div><div class="kpi-value">${s.on_time_pct}%</div><div class="kpi-sub">Avg delay: ${s.avg_exit_delay} min</div></div>
    </div>
    <div class="grid-2">
        <div class="card">
            <div class="card-header"><div class="card-title">🤖 Model Performance</div></div>
            <div class="grid-2">
                <div class="kpi kpi-green"><div class="kpi-label">RF Accuracy</div><div class="kpi-value">${m.rf_accuracy}%</div><div class="kpi-sub">Delay classification</div></div>
                <div class="kpi kpi-blue"><div class="kpi-label">XGBoost MAE</div><div class="kpi-value">${m.xgb_mae}</div><div class="kpi-sub">Minutes prediction error</div></div>
            </div>
            <div style="margin-top:1rem;font-size:0.78rem;color:var(--text-secondary)">Training: ${m.train_size} samples · Test: ${m.test_size} samples</div>
        </div>
        <div class="card">
            <div class="card-header"><div class="card-title">📊 Data Summary</div></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:0.82rem">
                <div>Express Trains: <strong>${s.express_trains}</strong></div>
                <div>Passenger Trains: <strong>${s.passenger_trains}</strong></div>
                <div>Freight Trains: <strong>${s.freight_trains}</strong></div>
                <div>Loop Blocks: <strong>${s.loop_blocks}</strong></div>
                <div>Avg Block Length: <strong>${s.avg_block_length} km</strong></div>
                <div>Max Delay: <strong>${s.max_delay} min</strong></div>
            </div>
            <div style="margin-top:1rem">
                <strong style="font-size:0.82rem">${data.conflicts_count}</strong> <span style="font-size:0.78rem;color:var(--text-secondary)">conflicts detected ·</span>
                <strong style="font-size:0.82rem"> ${data.recommendations_count}</strong> <span style="font-size:0.78rem;color:var(--text-secondary)">recommendations generated</span>
            </div>
        </div>
    </div>

    <div class="card" style="margin-top:1.5rem">
        <div class="card-header"><div class="card-title"><span class="icon">⚙️</span> System Pipeline</div></div>
        <div style="font-size:0.82rem;line-height:2.2">
            <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:6px">
                <span class="tag tag-green">✓</span> Data Loaded & Validated (${s.total_blocks} blocks, ${s.total_trains} trains, ${s.total_movements} movements)
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:6px">
                <span class="tag tag-green">✓</span> Feature Engineering Complete (20+ features)
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:6px">
                <span class="tag tag-green">✓</span> Random Forest Classifier — ${m.rf_accuracy}% accuracy
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:6px">
                <span class="tag tag-green">✓</span> XGBoost Regressor — ${m.xgb_mae} MAE
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:6px">
                <span class="tag tag-green">✓</span> Conflict Detection — ${data.conflicts_count} conflicts found
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:6px">
                <span class="tag tag-green">✓</span> AI Recommendations — ${data.recommendations_count} generated
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--green-glow);border:1px solid rgba(34,197,94,0.2);border-radius:var(--radius-sm)">
                <span class="tag tag-green">✓</span> <strong>Dashboard Ready — Navigate tabs above to explore</strong>
            </div>
        </div>
    </div>`;
}

// ========== NETWORK OVERVIEW ==========
async function loadNetwork() {
    try {
        const res = await fetch('/api/network');
        const data = await res.json();
        if (!data.success) return;
        appState.networkData = data;
        renderBlockMap(data);
    } catch (err) { console.error(err); }
}

function renderBlockMap(data) {
    const container = document.getElementById('block-map');
    const details = document.getElementById('block-details');
    container.innerHTML = '';

    let legendHtml = '<div style="display:flex;gap:1.5rem;margin-bottom:1.25rem;font-size:0.78rem;align-items:center;flex-wrap:wrap">';
    legendHtml += '<span style="display:flex;align-items:center;gap:6px"><span style="width:12px;height:12px;border-radius:3px;background:var(--green);display:inline-block"></span> Free</span>';
    legendHtml += '<span style="display:flex;align-items:center;gap:6px"><span style="width:12px;height:12px;border-radius:3px;background:var(--yellow);display:inline-block"></span> Occupied</span>';
    legendHtml += '<span style="display:flex;align-items:center;gap:6px"><span style="width:12px;height:12px;border-radius:3px;background:var(--red);display:inline-block"></span> Conflict</span>';
    legendHtml += '</div>';
    document.getElementById('block-legend').innerHTML = legendHtml;

    data.blocks.forEach((block, i) => {
        const status = data.block_status[block.Block_ID] || {};
        const node = document.createElement('div');
        node.className = `block-node ${status.status || 'free'}`;
        node.innerHTML = `
            <div class="block-id">${block.Block_ID}</div>
            <div class="block-station">${block.From_point} → ${block.To_point}</div>
            <div class="block-trains">${(status.trains || []).length} trains</div>
        `;
        node.addEventListener('click', () => showBlockDetails(block, status));
        container.appendChild(node);

        if (i < data.blocks.length - 1) {
            const conn = document.createElement('div');
            conn.className = 'block-connector';
            container.appendChild(conn);
        }
    });
}

function showBlockDetails(block, status) {
    const d = document.getElementById('block-details');
    d.innerHTML = `
    <div class="card">
        <div class="card-header"><div class="card-title">🔍 ${block.Block_ID} — ${block.From_point} → ${block.To_point}</div></div>
        <div class="grid-4">
            <div class="kpi kpi-blue"><div class="kpi-label">Length</div><div class="kpi-value">${block.Block_length_km} km</div></div>
            <div class="kpi kpi-${status.status === 'conflict' ? 'red' : status.status === 'occupied' ? 'yellow' : 'green'}"><div class="kpi-label">Status</div><div class="kpi-value" style="font-size:1rem;text-transform:uppercase">${status.status}</div></div>
            <div class="kpi kpi-purple"><div class="kpi-label">Line Type</div><div class="kpi-value" style="font-size:1rem">${block.Line_type}</div></div>
            <div class="kpi kpi-blue"><div class="kpi-label">Loop</div><div class="kpi-value" style="font-size:1rem">${block.Has_loop_line ? 'Yes' : 'No'}</div><div class="kpi-sub">Cap: ${block.Loop_capacity}</div></div>
        </div>
        ${status.trains && status.trains.length ? `<div style="margin-top:1rem;font-size:0.82rem"><strong>Trains in block:</strong> ${status.trains.map(t => `<span class="tag tag-blue" style="margin:2px">${t}</span>`).join(' ')}</div>` : ''}
    </div>`;
}

// ========== TRAIN ANALYSIS ==========
async function loadTrainList() {
    try {
        const res = await fetch('/api/trains');
        const data = await res.json();
        if (!data.success) return;
        appState.trains = data.trains;
        const select = document.getElementById('train-select');
        select.innerHTML = '<option value="">— Select a Train —</option>';
        data.trains.forEach(t => {
            select.innerHTML += `<option value="${t.Train_ID}">${t.Train_ID} — ${t.Train_name}</option>`;
        });
    } catch (err) { console.error(err); }
}

async function analyzeTrain() {
    const trainId = document.getElementById('train-select').value;
    if (!trainId) return;
    showLoading('Analyzing Train ' + trainId + '...');
    try {
        const res = await fetch(`/api/train/${trainId}`);
        const data = await res.json();
        hideLoading();
        if (!data.success) { toast(data.error, 'error'); return; }
        renderTrainAnalysis(data);
    } catch (err) {
        hideLoading();
        toast('Analysis failed', 'error');
    }
}

function renderTrainAnalysis(data) {
    const container = document.getElementById('train-analysis-results');
    const info = data.info;
    const pred = data.prediction;

    let html = `
    <div class="grid-4" style="margin-bottom:1.25rem">
        <div class="kpi kpi-blue"><div class="kpi-label">Train Type</div><div class="kpi-value" style="font-size:1rem">${info.Train_type || 'N/A'}</div></div>
        <div class="kpi kpi-purple"><div class="kpi-label">Priority</div><div class="kpi-value">P${info.Priority_level}</div><div class="kpi-sub">${info.Direction} direction</div></div>
        <div class="kpi kpi-${pred.is_delayed ? 'red' : 'green'}"><div class="kpi-label">Prediction</div><div class="kpi-value" style="font-size:1rem">${pred.delay_status}</div></div>
        <div class="kpi kpi-${pred.predicted_delay_min > 2 ? 'red' : pred.predicted_delay_min > 0 ? 'yellow' : 'green'}"><div class="kpi-label">Predicted Delay</div><div class="kpi-value">${parseFloat(pred.predicted_delay_min).toFixed(2)} min</div></div>
    </div>`;

    // Movements table
    if (data.movements && data.movements.length) {
        html += `<div class="card" style="margin-bottom:1.25rem">
            <div class="card-header"><div class="card-title">📋 Block Movements</div></div>
            <div class="table-wrap"><table>
            <thead><tr><th>Block</th><th>Entry Delay</th><th>Exit Delay</th><th>Occupied</th><th>Conflict</th><th>Action</th><th>Conflicting Trains</th><th>Sched. Arrival</th><th>Actual Arrival</th></tr></thead><tbody>`;
        data.movements.forEach(m => {
            const conflictTrains = (m.conflicting_trains && m.conflicting_trains.length > 0)
                ? m.conflicting_trains.map(t => `<span class="tag tag-blue" style="margin:1px;font-size:0.65rem">${t}</span>`).join(' ')
                : '<span style="color:var(--text-muted);font-size:0.75rem">—</span>';
                const actionMap = {'HOLD':'tag-red','CROSSING':'tag-yellow','REGULATE':'tag-yellow','PROCEED_WITH_CAUTION':'tag-blue','PROCEED':'tag-green'};
                const actionClass = actionMap[m.Action_taken] || 'tag-blue';
                html += `<tr>
                <td><strong>${m.Block_id}</strong></td>
                <td>${m.Delay_at_entry_min} min</td>
                <td>${m.Delay_at_exit_min} min</td>
                <td>${m.Block_occupied_flag ? '<span class="tag tag-yellow">Yes</span>' : '<span class="tag tag-green">No</span>'}</td>
                <td>${m.Conflict_flag ? '<span class="tag tag-red">Yes</span>' : '<span class="tag tag-green">No</span>'}</td>
                <td><span class="tag ${actionClass}">${m.Action_taken}</span></td>
                <td style="max-width:200px">${conflictTrains}</td>
                <td>${m.Scheduled_Arrival_Time}</td><td>${m.Actual_Arrival_Time}</td>
            </tr>`;
        });
        html += '</tbody></table></div></div>';
    }

    // Conflicts
    if (data.conflicts && data.conflicts.length) {
        html += `<div class="card" style="margin-bottom:1.25rem">
            <div class="card-header"><div class="card-title">⚠️ Conflicts (${data.conflicts.length})</div></div>`;
        data.conflicts.forEach(c => {
            html += `<div style="padding:0.75rem;margin-bottom:0.5rem;background:var(--bg-input);border-radius:var(--radius-sm);font-size:0.82rem;border-left:3px solid var(--red)">
                ${severityTag(c.severity)} <strong>${c.type}</strong> on ${c.block_id} — ${c.description}
            </div>`;
        });
        html += '</div>';
    }

    // Recommendations
    if (data.recommendations && data.recommendations.length) {
        html += `<div class="card"><div class="card-header"><div class="card-title">💡 AI Recommendations</div></div>`;
        data.recommendations.forEach(r => {
            html += renderRecCard(r);
        });
        html += '</div>';
    }

    container.innerHTML = html;
}

function renderRecCard(r) {
    const actionColors = { 'DETAIN': 'tag-red', 'CROSSING': 'tag-yellow', 'PRIORITIZE': 'tag-purple', 'REGULATE': 'tag-yellow', 'PROCEED_WITH_CAUTION': 'tag-blue' };
    const statusClass = r.status === 'accepted' ? 'accepted' : r.status === 'rejected' ? 'rejected' : '';
    return `
    <div class="rec-card ${statusClass}" id="rec-${r.rec_id}">
        <div class="rec-header">
            <div>
                <span class="tag ${actionColors[r.action] || 'tag-blue'}" style="margin-right:8px">${r.action}</span>
                <span class="rec-action">${r.rec_id}</span>
                ${r.conflict_id ? `<span style="font-size:0.72rem;color:var(--text-muted);margin-left:8px">→ ${r.conflict_id}</span>` : ''}
            </div>
            ${severityTag(r.severity)}
        </div>
        <div class="rec-explain">${r.explanation}</div>
        <div class="rec-impact">📈 Expected: ${r.expected_impact}</div>
        <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.75rem">Trains: ${(r.affected_trains || []).map(t => `<span class="tag tag-blue" style="margin:1px">${t}</span>`).join(' ')}</div>
        ${r.status === 'pending' ? `
        <div class="rec-actions">
            <button class="btn btn-success btn-sm" onclick="makeDecision('${r.rec_id}','accept')">✓ Accept Recommendation</button>
            <button class="btn btn-danger btn-sm" onclick="makeDecision('${r.rec_id}','reject')">✕ Reject Recommendation</button>
        </div>` : `<span class="tag ${r.status === 'accepted' ? 'tag-green' : 'tag-red'}">${r.status.toUpperCase()}</span>`}
        <div id="result-${r.rec_id}"></div>
    </div>`;
}

// ========== DECISIONS ==========
async function makeDecision(recId, action) {
    showLoading(action === 'accept' ? 'Applying recommendation...' : 'Simulating rejection...');
    try {
        const body = { rec_id: recId, action: action };
        if (action === 'reject') {
            body.alternative = { action: 'proceed_all' };
        }
        const res = await fetch('/api/decide', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await res.json();
        hideLoading();
        if (!data.success) { toast(data.error, 'error'); return; }

        const card = document.getElementById('rec-' + recId);
        if (card) card.className = `rec-card ${action === 'accept' ? 'accepted' : 'rejected'}`;

        renderDecisionResult(recId, data.result);
        toast(`Decision ${action}ed for ${recId}`);
    } catch (err) {
        hideLoading();
        toast('Decision failed', 'error');
    }
}

function renderDecisionResult(recId, result) {
    const container = document.getElementById('result-' + recId);
    if (!container) return;

    let delayBars = '';
    const allTrains = new Set([...Object.keys(result.before_delays || {}), ...Object.keys(result.after_delays || {})]);
    allTrains.forEach(tid => {
        const before = result.before_delays[tid] || 0;
        const after = result.after_delays[tid] || 0;
        const maxVal = Math.max(before, after, 1);
        delayBars += `<div style="margin-bottom:0.5rem">
            <div style="font-size:0.75rem;font-weight:600;margin-bottom:3px">Train ${tid}</div>
            <div style="display:flex;gap:8px;align-items:center">
                <div style="flex:1;height:18px;background:var(--bg-secondary);border-radius:4px;overflow:hidden;position:relative">
                    <div style="height:100%;width:${(before/maxVal)*100}%;background:var(--red);border-radius:4px;opacity:0.5"></div>
                    <div style="position:absolute;top:0;height:100%;width:${(after/maxVal)*100}%;background:${after < before ? 'var(--green)' : 'var(--yellow)'};border-radius:4px"></div>
                </div>
                <span style="font-size:0.72rem;font-family:'JetBrains Mono',monospace;min-width:80px">${before} → ${after} min</span>
            </div>
        </div>`;
    });

    container.innerHTML = `
    <div class="result-panel">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:1rem">
            <span class="tag ${result.outcome === 'positive' ? 'tag-green' : result.outcome === 'negative' ? 'tag-red' : 'tag-yellow'}">${result.outcome}</span>
            <span class="tag ${result.safety_status === 'SAFE' ? 'tag-green' : result.safety_status === 'WARNING' ? 'tag-red' : 'tag-yellow'}">${result.safety_status}</span>
        </div>
        <div class="comparison">
            <div class="compare-box before"><div class="value" style="color:var(--red)">${result.total_delay_before} min</div><div class="label">Before (Total Delay)</div></div>
            <div class="arrow">→</div>
            <div class="compare-box after"><div class="value" style="color:var(--green)">${result.total_delay_after} min</div><div class="label">After (Total Delay)</div></div>
        </div>
        <div style="margin:1rem 0;padding:0.75rem;background:var(--bg-input);border-radius:var(--radius-sm);font-size:0.82rem;border-left:3px solid var(--cyan)">${result.explanation}</div>
        <div style="margin-top:1rem"><strong style="font-size:0.82rem">Train Delay Comparison</strong></div>
        <div style="margin-top:0.75rem">${delayBars}</div>
        <div class="grid-2" style="margin-top:1rem">
            <div class="kpi kpi-blue"><div class="kpi-label">Congestion Before</div><div class="kpi-value" style="font-size:1.2rem">${result.congestion_before}%</div></div>
            <div class="kpi kpi-green"><div class="kpi-label">Congestion After</div><div class="kpi-value" style="font-size:1.2rem">${result.congestion_after}%</div></div>
        </div>
    </div>`;
}

// ========== CONFLICTS ==========
async function loadConflicts() {
    try {
        const res = await fetch('/api/conflicts');
        const data = await res.json();
        if (!data.success) return;
        appState.conflicts = data.conflicts;
        renderConflicts(data);
    } catch (err) { console.error(err); }
}

function renderConflicts(data) {
    const container = document.getElementById('conflicts-content');
    const summary = data.summary;

    let html = `<div class="grid-4" style="margin-bottom:1.5rem">
        <div class="kpi kpi-red"><div class="kpi-label">Total Conflicts</div><div class="kpi-value">${summary.total}</div></div>
        <div class="kpi kpi-yellow"><div class="kpi-label">Block Conflicts</div><div class="kpi-value">${summary.by_type['Block Conflict'] || 0}</div></div>
        <div class="kpi kpi-red"><div class="kpi-label">Direction Conflicts</div><div class="kpi-value">${summary.by_type['Direction Conflict'] || 0}</div></div>
        <div class="kpi kpi-purple"><div class="kpi-label">Capacity Violations</div><div class="kpi-value">${summary.by_type['Capacity Violation'] || 0}</div></div>
    </div>`;

    if (data.conflicts.length === 0) {
        html += '<div class="empty-state"><div class="icon">✅</div><h3>No Conflicts Detected</h3><p>All blocks are operating safely.</p></div>';
    } else {
        html += '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Type</th><th>Severity</th><th>Block</th><th>Conflicting Trains</th><th>Description</th></tr></thead><tbody>';
        data.conflicts.forEach(c => {
            const trainsList = (c.trains && c.trains.length > 0)
                ? c.trains.map(t => `<span class="tag tag-blue" style="margin:1px">${t}</span>`).join(' ')
                : `<span class="tag tag-blue">${c.train_1}</span> <span class="tag tag-blue">${c.train_2}</span>`;
            html += `<tr>
                <td><strong>${c.conflict_id}</strong></td>
                <td><span class="tag tag-yellow">${c.type}</span></td>
                <td>${severityTag(c.severity)}</td>
                <td>${c.block_id}</td>
                <td>${trainsList}</td>
                <td style="font-size:0.78rem;max-width:300px">${c.description}</td>
            </tr>`;
        });
        html += '</tbody></table></div>';
    }

    container.innerHTML = html;
}

async function loadRecommendationsPanel(prefixHtml, container) {
    try {
        const res = await fetch('/api/recommendations');
        const data = await res.json();
        if (!data.success) { container.innerHTML = prefixHtml; return; }

        let html = prefixHtml;
        html += `<div style="margin-top:2rem"><div class="section-header"><h2>💡 AI Recommendations (${data.recommendations.length})</h2><p>Review and act on each recommendation</p></div>`;
        data.recommendations.forEach(r => { html += renderRecCard(r); });
        html += '</div>';
        container.innerHTML = html;
    } catch (err) { container.innerHTML = prefixHtml; }
}

// ========== SIMULATION ==========
async function runWhatIf() {
    const trainId = parseInt(document.getElementById('sim-train').value);
    const minutes = parseInt(document.getElementById('sim-minutes').value) || 0;
    const actionType = document.getElementById('sim-action').value;

    if (!trainId) { toast('Select a train', 'error'); return; }

    const scenario = {};
    scenario.modify_detention = { train_id: trainId, minutes: minutes };
    if (actionType) scenario.action_type = actionType;

    showLoading('Running simulation...');
    try {
        const res = await fetch('/api/whatif', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(scenario) });
        const data = await res.json();
        hideLoading();
        if (!data.success) { toast(data.error, 'error'); return; }
        renderWhatIfResult(data.result);
    } catch (err) {
        hideLoading();
        toast('Simulation failed', 'error');
    }
}

function renderWhatIfResult(result) {
    const container = document.getElementById('sim-results');

    // Use train-specific delays if available, otherwise system
    const beforeVal = result.train_before_avg_delay !== undefined ? result.train_before_avg_delay : result.before_avg_delay;
    const afterVal = result.train_after_avg_delay !== undefined ? result.train_after_avg_delay : result.after_avg_delay;
    const impact = round2(afterVal - beforeVal);
    const impactColor = impact > 0 ? 'var(--red)' : impact < 0 ? 'var(--green)' : 'var(--text-secondary)';

    container.innerHTML = `
    <div class="result-panel">
        <div class="comparison">
            <div class="compare-box before"><div class="value" style="color:var(--red)">${beforeVal} min</div><div class="label">Avg Delay Before</div></div>
            <div class="arrow">→</div>
            <div class="compare-box after"><div class="value" style="color:var(--green)">${afterVal} min</div><div class="label">Avg Delay After</div></div>
        </div>
        <div class="kpi kpi-${impact <= 0 ? 'green' : 'red'}" style="margin-top:1rem"><div class="kpi-label">Impact on Selected Train</div><div class="kpi-value" style="font-size:1.2rem;color:${impactColor}">${impact > 0 ? '+' : ''}${impact} min</div></div>
        ${Object.entries(result).filter(([k]) => ['halt','action'].includes(k)).map(([k,v]) => `<div style="margin-top:0.75rem;padding:0.5rem 0.75rem;background:var(--bg-input);border-radius:var(--radius-sm);font-size:0.82rem;border-left:3px solid var(--cyan)">${v}</div>`).join('')}
    </div>`;
}

function round2(n) { return Math.round(n * 100) / 100; }

// ========== PERFORMANCE ==========
async function loadPerformance() {
    try {
        const res = await fetch('/api/performance');
        const data = await res.json();
        if (!data.success) return;
        appState.kpis = data.kpis;
        renderPerformance(data.kpis);
    } catch (err) { console.error(err); }
}

function renderPerformance(kpis) {
    const container = document.getElementById('performance-content');

    let html = `
    <div class="grid-4" style="margin-bottom:1.5rem">
        <div class="kpi kpi-blue"><div class="kpi-label">Avg Delay</div><div class="kpi-value">${kpis.avg_delay} min</div></div>
        <div class="kpi kpi-green"><div class="kpi-label">Punctuality</div><div class="kpi-value">${kpis.punctuality}%</div></div>
        <div class="kpi kpi-purple"><div class="kpi-label">Throughput</div><div class="kpi-value">${kpis.throughput}</div><div class="kpi-sub">trains per block</div></div>
        <div class="kpi kpi-yellow"><div class="kpi-label">Utilization</div><div class="kpi-value">${kpis.utilization}%</div></div>
    </div>
    <div class="grid-2" style="margin-bottom:1.5rem">
        <div class="kpi kpi-red"><div class="kpi-label">Conflict Rate</div><div class="kpi-value">${kpis.conflict_rate}%</div><div class="kpi-sub">${kpis.total_conflicts} conflicts / ${kpis.total_movements} movements</div></div>
        ${kpis.model_metrics ? `<div class="kpi kpi-green"><div class="kpi-label">Model Performance</div><div class="kpi-value" style="font-size:1rem">RF: ${kpis.model_metrics.rf_accuracy}% · XGB MAE: ${kpis.model_metrics.xgb_mae}</div></div>` : ''}
    </div>

    <div class="grid-2">
        <div class="card">
            <div class="card-header"><div class="card-title">📊 Delay Distribution</div></div>
            <div class="chart-container"><canvas id="chart-delay-dist"></canvas></div>
        </div>
        <div class="card">
            <div class="card-header"><div class="card-title">📈 Delay by Block</div></div>
            <div class="chart-container"><canvas id="chart-block-delays"></canvas></div>
        </div>
    </div>
    <div class="grid-2" style="margin-top:1.25rem">
        <div class="card">
            <div class="card-header"><div class="card-title">🚆 Delay by Train Type</div></div>
            <div class="chart-container"><canvas id="chart-type-delays"></canvas></div>
        </div>
        <div class="card">
            <div class="card-header"><div class="card-title">🧠 Model Accuracy</div></div>
            <div style="padding:2rem;text-align:center">
                ${kpis.model_metrics ? `
                <div class="grid-2">
                    <div class="kpi kpi-green"><div class="kpi-label">Random Forest</div><div class="kpi-value" style="font-size:1.5rem">${kpis.model_metrics.rf_accuracy}%</div><div class="kpi-sub">Classification Accuracy</div></div>
                    <div class="kpi kpi-blue"><div class="kpi-label">XGBoost</div><div class="kpi-value" style="font-size:1.5rem">${kpis.model_metrics.xgb_mae}</div><div class="kpi-sub">MAE (minutes)</div></div>
                </div>` : '<div style="color:var(--text-muted)">No model data available</div>'}
            </div>
        </div>
    </div>`;

    if (kpis.model_metrics && kpis.model_metrics.feature_importances && Object.keys(kpis.model_metrics.feature_importances).length > 0) {
        html += `<div class="card" style="margin-top:1.25rem">
            <div class="card-header"><div class="card-title">🧠 Feature Importances (Random Forest)</div></div>
            <div class="chart-container" style="height:500px"><canvas id="chart-features"></canvas></div>
        </div>`;
    }

    container.innerHTML = html;

    // Use a slightly longer timeout to ensure DOM is fully ready
    setTimeout(() => buildCharts(kpis), 200);
}

function buildCharts(kpis) {
    const chartOpts = {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#8899b0', font: { family: 'Outfit' } } } },
        scales: {
            x: { ticks: { color: '#5a6a80', font: { family: 'Outfit', size: 11 } }, grid: { color: 'rgba(30,58,95,0.3)' } },
            y: { ticks: { color: '#5a6a80', font: { family: 'Outfit', size: 11 } }, grid: { color: 'rgba(30,58,95,0.3)' } }
        }
    };

    // Delay distribution (doughnut)
    try {
        const dd = kpis.delay_distribution;
        new Chart(document.getElementById('chart-delay-dist'), {
            type: 'doughnut',
            data: {
                labels: ['On Time', 'Slight (1-2 min)', 'Moderate (3-4 min)', 'Severe (5+ min)'],
                datasets: [{ data: [dd.on_time, dd.slight, dd.moderate, dd.severe],
                    backgroundColor: ['#22c55e', '#eab308', '#f97316', '#ef4444'],
                    borderWidth: 0 }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#8899b0', font: { family: 'Outfit' }, padding: 16 } } } }
        });
    } catch (e) { console.error('Delay dist chart error:', e); }

    // Block delays (bar)
    try {
        const bd = kpis.block_delays;
        new Chart(document.getElementById('chart-block-delays'), {
            type: 'bar',
            data: {
                labels: Object.keys(bd),
                datasets: [{ label: 'Avg Delay (min)', data: Object.values(bd),
                    backgroundColor: Object.values(bd).map(v => v > 2 ? '#ef4444' : v > 1 ? '#eab308' : '#22c55e'),
                    borderRadius: 6, borderSkipped: false }]
            },
            options: { ...chartOpts, plugins: { ...chartOpts.plugins, legend: { display: false } } }
        });
    } catch (e) { console.error('Block delays chart error:', e); }

    // Type delays (horizontal bar)
    try {
        const td = kpis.type_delays;
        if (Object.keys(td).length) {
            new Chart(document.getElementById('chart-type-delays'), {
                type: 'bar',
                data: {
                    labels: Object.keys(td),
                    datasets: [{ label: 'Avg Delay (min)', data: Object.values(td),
                        backgroundColor: ['#3b82f6', '#8b5cf6', '#06b6d4'], borderRadius: 6, borderSkipped: false }]
                },
                options: { ...chartOpts, indexAxis: 'y', plugins: { ...chartOpts.plugins, legend: { display: false } } }
            });
        }
    } catch (e) { console.error('Type delays chart error:', e); }

    // Feature importances (horizontal bar) - FIXED: independent try-catch, robust data handling
    try {
        const canvas = document.getElementById('chart-features');
        if (canvas && kpis.model_metrics && kpis.model_metrics.feature_importances) {
            const fi = kpis.model_metrics.feature_importances;
            const entries = Object.entries(fi)
                .map(([k, v]) => [k, parseFloat(v) || 0])
                .filter(([, v]) => v > 0)
                .sort((a, b) => b[1] - a[1]);

            if (entries.length > 0) {
                const colors = entries.map((_, i) => {
                    const ratio = i / Math.max(entries.length - 1, 1);
                    const r = Math.round(59 + ratio * (6 - 59));
                    const g = Math.round(130 + ratio * (182 - 130));
                    const b = Math.round(246 + ratio * (212 - 246));
                    return `rgb(${r}, ${g}, ${b})`;
                });

                new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: entries.map(x => x[0].replace(/_/g, ' ')),
                        datasets: [{
                            label: 'Importance',
                            data: entries.map(x => x[1]),
                            backgroundColor: colors,
                            borderRadius: 4,
                            borderSkipped: false,
                            barThickness: 18,
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        indexAxis: 'y',
                        plugins: {
                            legend: { display: false },
                            tooltip: { callbacks: { label: (ctx) => `Importance: ${(ctx.parsed.x * 100).toFixed(1)}%` } }
                        },
                        scales: {
                            x: {
                                ticks: { color: '#5a6a80', font: { family: 'Outfit', size: 11 } },
                                grid: { color: 'rgba(30,58,95,0.3)' },
                                title: { display: true, text: 'Feature Importance Score', color: '#8899b0', font: { family: 'Outfit', size: 12 } },
                                beginAtZero: true
                            },
                            y: {
                                ticks: { color: '#8899b0', font: { family: 'JetBrains Mono', size: 10 } },
                                grid: { color: 'rgba(30,58,95,0.15)' },
                            }
                        }
                    }
                });
            } else {
                canvas.parentElement.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)">No feature importance data available</div>';
            }
        }
    } catch (e) { console.error('Feature importance chart error:', e); }
}

// ========== POPULATE SIMULATION DROPDOWNS ==========
async function loadSimOptions() {
    if (!appState.dataLoaded) return;
    try {
        const tRes = await fetch('/api/trains');
        const tData = await tRes.json();

        const trainSel = document.getElementById('sim-train');
        trainSel.innerHTML = '<option value="">Select Train</option>';
        if (tData.success) tData.trains.forEach(t => { trainSel.innerHTML += `<option value="${t.Train_ID}">${t.Train_ID} - ${t.Train_name}</option>`; });
    } catch (err) { console.error(err); }
}
