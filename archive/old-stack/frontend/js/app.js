const GATEWAY = location.origin;
let currentJob = null;
let logLines = [];

function $(id) { return document.getElementById(id); }

async function loadDocuments() {
  const r = await fetch(GATEWAY + '/api/documents');
  const data = await r.json();
  const container = $('index-status');
  if (!container) return;
  let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
  data.documents.forEach(doc => {
    const status = doc.indexing ? 'INDEXING' : (doc.indexed ? 'INDEXED' : 'NOT INDEXED');
    const color = doc.indexing ? 'var(--yellow)' : (doc.indexed ? 'var(--green)' : 'var(--red)');
    html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border:1px solid var(--ink);border-radius:4px;background:var(--paper);"><div><div style="font-weight:600;font-size:13px;">${doc.name}</div><div style="font-size:11px;color:var(--ink-soft);">${doc.size_human}${doc.chunks ? ' · ' + doc.chunks + ' chunks' : ''}</div></div><div style="font-size:11px;font-weight:600;color:${color};">${status}</div></div>`;
  });
  html += '</div>';
  container.innerHTML = html;
}

async function startIndex(filename) {
  if (currentJob) { alert('Already indexing. Please wait.'); return; }
  currentJob = { filename, cancelled: false };
  try {
    const r = await fetch(GATEWAY + `/api/index/${encodeURIComponent(filename)}`, { method: 'POST' });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const data = await r.json();
    currentJob.jobId = data.job_id;
    pollLogs();
  } catch (e) {
    alert('Failed: ' + e.message);
    currentJob = null;
  }
}

async function pollLogs() {
  if (!currentJob) return;
  try {
    const r = await fetch(GATEWAY + `/api/logs?job_id=${currentJob.jobId}&since=${currentJob.lastLogSeq || 0}`);
    const data = await r.json();
    if (data.done) {
      currentJob = null;
      loadDocuments();
      return;
    }
    if (data.job_id) currentJob.jobId = data.job_id;
    if (data.last_seq) currentJob.lastLogSeq = data.last_seq;
    setTimeout(pollLogs, 500);
  } catch (e) {
    setTimeout(pollLogs, 1000);
  }
}

async function doAsk() {
  const q = $('q').value.trim();
  if (!q) return;
  const out = $('answer-area');
  out.innerHTML = '<span style="color:var(--ink-soft)">Searching...</span>';
  try {
    const body = { query: q, top_k: parseInt($('top-k').value), max_turns: 4 };
    const r = await fetch(GATEWAY + '/ask', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    if (!r.ok) {
      let err = 'Server error';
      const txt = await r.text();
      try { const j = JSON.parse(txt); err = JSON.stringify(j.detail || j); } catch(e) {}
      out.innerHTML = '<span style="color:var(--red)">❌ ' + err + '</span>';
      return;
    }
    const data = await r.json();
    let html = '<div style="margin-bottom:8px"><b>Answer:</b></div>';
    html += '<div>' + escapeHtml(data.answer) + '</div>';
    if (data.sources && data.sources.length) {
      html += '<div style="margin-top:10px;font-size:11px;color:var(--ink-soft);">Sources: ' + data.sources.slice(0, 10).join(', ') + (data.sources.length > 10 ? '...' : '') + '</div>';
    }
    html += '<div style="margin-top:4px;font-size:11px;color:var(--ink-soft);">References used: ' + data.tool_calls_used + '</div>';
    out.innerHTML = html;
  } catch (e) {
    out.innerHTML = '<span style="color:var(--red)">❌ ' + e.message + '</span>';
  }
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

$('search-btn').addEventListener('click', doAsk);
$('q').addEventListener('keydown', e => { if (e.key === 'Enter') doAsk(); });

loadDocuments();
