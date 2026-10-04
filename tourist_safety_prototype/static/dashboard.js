/* Authority dashboard - vanilla JS, inline SVG map (works fully offline, no map tiles needed). */
const KM = 111195;                       // metres per degree of latitude
let S = null, playing = false, view = 'full', origin = [20.8905, 70.4075];
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function xy(lat, lon) { return [(lon - origin[1]) * KM * Math.cos(origin[0] * Math.PI / 180), -(lat - origin[0]) * KM]; }
const SEV = {CRITICAL:'#7b1fa2', HIGH:'#c62828', MEDIUM:'#ef6c00', LOW:'#f9a825'};

async function api(path, method, body) {
  const r = await fetch(path, {method: method || 'GET', headers: {'Content-Type':'application/json'}, body: body ? JSON.stringify(body) : undefined});
  return r.json();
}

function setView(v) { view = v; $('map').setAttribute('viewBox', v === 'full' ? '-1800 -1800 3600 3600' : '-700 -1150 2000 2000'); }

function drawMap() {
  if (!S) return; origin = S.origin;
  let g = '';
  const z = S.zones;
  if ($('lh').checked) S.heat.forEach(h => { g += `<rect x="${h.i*100}" y="${-(h.j+1)*100}" width="100" height="100" fill="#d32f2f" opacity="${Math.min(0.65, 0.12 + h.w*0.06)}"/>`; });
  if ($('lz').checked) {
    const c = xy(z.safe.lat, z.safe.lon);
    g += `<circle cx="${c[0]}" cy="${c[1]}" r="${z.safe.radius_m}" fill="#66bb6a" fill-opacity=".10" stroke="#2e7d32" stroke-width="6"/>`;
    g += `<text x="${c[0]}" y="${c[1]-z.safe.radius_m+60}" text-anchor="middle" font-size="60" fill="#2e7d32">SAFE ZONE</text>`;
    const shape = (zz, col, label) => {
      if (zz.shape === 'circle') { const p = xy(zz.lat, zz.lon);
        return `<circle cx="${p[0]}" cy="${p[1]}" r="${zz.radius_m}" fill="${col}" fill-opacity=".3" stroke="${col}" stroke-width="4"/><text x="${p[0]}" y="${p[1]-zz.radius_m-14}" text-anchor="middle" font-size="44" fill="#333">${label}</text>`; }
      const pts = zz.points.map(q => xy(q[0], q[1]).join(',')).join(' '); const p = xy(zz.lat, zz.lon);
      return `<polygon points="${pts}" fill="${col}" fill-opacity=".3" stroke="${col}" stroke-width="4"/><text x="${p[0]}" y="${p[1]-130}" text-anchor="middle" font-size="44" fill="#333">${label}</text>`; };
    z.caution.forEach(q => g += shape(q, '#f9a825', 'CAUTION ' + esc(q.name)));
    z.restricted.forEach(q => g += shape(q, '#c62828', 'RESTRICTED ' + esc(q.name)));
  }
  if ($('lr').checked) {
    g += `<polyline points="${S.route.map(p => xy(p.lat, p.lon).join(',')).join(' ')}" fill="none" stroke="#1565c0" stroke-width="10" stroke-dasharray="26 14"/>`;
    S.rest_points.forEach(r => { const p = xy(r.lat, r.lon); g += `<circle cx="${p[0]}" cy="${p[1]}" r="${r.radius_m}" fill="none" stroke="#1565c0" stroke-width="3" stroke-dasharray="6 6"/>`; });
  }
  S.tourists.forEach(t => {
    if (!t.track.length) return;
    g += `<polyline points="${t.track.map(p => xy(p.lat, p.lon).join(',')).join(' ')}" fill="none" stroke="#00897b" stroke-width="8" opacity=".85"/>`;
    const l = t.last, p = xy(l.lat, l.lon), col = t.status === 'SOS' ? '#7b1fa2' : t.status === 'ALERT' ? '#e65100' : '#00897b';
    g += `<polygon points="${p[0]},${p[1]-34} ${p[0]-26},${p[1]+22} ${p[0]+26},${p[1]+22}" fill="${col}" stroke="#fff" stroke-width="4"/><text x="${p[0]+34}" y="${p[1]}" font-size="44" font-weight="bold" fill="#00332e">${esc(t.name)}</text>`;
  });
  if ($('li').checked) S.incidents.forEach(i => { if (i.lat == null) return; const p = xy(i.lat, i.lon);
    g += `<circle cx="${p[0]}" cy="${p[1]}" r="18" fill="${SEV[i.severity]}" stroke="#fff" stroke-width="4"><title>${esc(i.incident_type)} - ${esc(i.message)}</title></circle>`; });
  $('map').innerHTML = g;
}

function render() {
  if (!S) return;
  const s = S.stats;
  $('stats').innerHTML = [['Registered tourists', s.tourists, '#1B6CA8'], ['Total incidents', s.incidents, '#555'], ['Open incidents', s.open_incidents, '#C62828'],
    ['High / Critical', s.high_critical, '#7B1FA2'], ['Avg alert latency', s.avg_latency_ms + ' ms', '#E65100'], ['p95 latency', s.p95_latency_ms + ' ms', '#E65100']]
    .map(a => `<div class="stat"><div class="label">${a[0]}</div><div class="value" style="color:${a[2]}">${a[1]}</div></div>`).join('');
  const sel = $('tsel'), cur = sel.value;
  sel.innerHTML = S.tourists.map(t => `<option value="${t.tourist_id}">${esc(t.name)} (${t.tourist_id})</option>`).join('');
  if (cur) sel.value = cur;
  $('ttable').innerHTML = S.tourists.length ? '<table><thead><tr><th>Tourist</th><th>Status</th><th>Risk</th><th>Last fix</th></tr></thead>' +
    S.tourists.map(t => `<tr><td>${esc(t.name)}<br><span class="sub">${t.tourist_id}</span></td><td><span class="badge b-${t.status}">${t.status}</span></td>
    <td><div style="background:#eceff1;border-radius:4px;width:90px;height:10px;"><div style="background:${t.risk>40?'#c62828':t.risk>15?'#ef6c00':'#2e7d32'};width:${t.risk}%;height:10px;border-radius:4px;"></div></div>${t.risk}</td>
    <td>${t.last ? t.last.lat.toFixed(5) + ', ' + t.last.lon.toFixed(5) : '-'}</td></tr>`).join('') + '</table>' : '<p class="sub">No tourists yet - register one first.</p>';
  $('net').innerHTML = '<table><thead><tr><th>Node</th><th>Blocks</th><th>State</th><th>Head</th></tr></thead>' +
    S.network.nodes.map(n => `<tr><td>${n.name}</td><td>${n.blocks}</td><td><span class="badge ${n.state==='OK'?'b-OK':'b-TAMPERED'}">${n.state}</span> <span class="sub">${n.detail}</span></td><td style="font-family:monospace">${n.head}</td></tr>`).join('') +
    `</table><p class="sub" style="margin-top:6px;">Consensus (majority ${S.network.majority}): <b style="color:${S.network.consensus_ok?'#2e7d32':'#c62828'}">${S.network.consensus_ok ? 'OK' : 'LOST'}</b></p>`;
  $('inc').innerHTML = S.incidents.length ? '<table><thead><tr><th>#</th><th>Time</th><th>Tourist</th><th>Type</th><th>Severity</th><th>Message</th><th>Latency</th><th>Status</th><th></th></tr></thead>' +
    S.incidents.map(i => `<tr><td>${i.id}</td><td>${(i.created_at||'').slice(11,19)}</td><td>${i.tourist_id}</td><td>${i.incident_type}</td>
    <td><span class="badge b-${i.severity}">${i.severity}</span></td><td>${esc(i.message)}</td><td>${i.latency_ms != null ? i.latency_ms.toFixed(1) + ' ms' : '-'}</td><td>${i.status}</td>
    <td>${i.status==='OPEN' ? `<button class="btn btn-outline btn-sm" onclick="act(${i.id},'ack')">Ack</button>` : ''}${i.status!=='RESOLVED' ? `<button class="btn btn-success btn-sm" onclick="act(${i.id},'resolve')">Resolve</button>` : ''}</td></tr>`).join('') + '</table>'
    : '<p class="sub">No incidents yet.</p>';
  $('notes').innerHTML = S.notifications.length ? '<table><thead><tr><th>Time</th><th>Channel</th><th>To</th><th>Status</th><th>Delay</th><th>Message</th></tr></thead>' +
    S.notifications.map(n => `<tr><td>${(n.created_at||'').slice(11,19)}</td><td>${n.channel}</td><td>${esc(n.recipient)}</td><td>${n.status}</td><td>${n.sim_delay_ms ? n.sim_delay_ms.toFixed(0) + ' ms (sim)' : '-'}</td><td style="font-size:11px;">${esc(n.body)}</td></tr>`).join('') + '</table>'
    : '<p class="sub">No notifications yet.</p>';
  drawMap();
}

async function refresh() { try { S = await api('/api/state'); render(); } catch (e) { /* server busy */ } }
async function act(id, a) { await api(`/api/incident/${id}/${a}`, 'POST'); refresh(); }
async function net(a, body) { const r = await api('/api/network/' + a, 'POST', body || {}); if (a === 'audit') $('audit').innerHTML = r.issues.length ? '⚠ ' + r.issues.map(esc).join('<br>') : '✓ Ledger audit clean'; refresh(); }
function stopPlay() { playing = false; }
async function sos() { const t = $('tsel').value; if (!t) { alert('Register a tourist first'); return; }
  const r = await api('/api/sos', 'POST', {tourist_id: t, note: 'demo from dashboard', request_id: 'dash-' + Date.now()});
  $('pstat').textContent = r.ok ? 'SOS raised' : 'SOS failed: ' + (r.error || 'unknown'); refresh(); }
async function play(sc) {
  const t = $('tsel').value; if (!t) { alert('Register a tourist first'); return; }
  playing = false; await new Promise(r => setTimeout(r, 50)); playing = true;
  await api('/api/reset/' + t, 'POST');
  const d = await api('/api/demo/' + sc); let n = 0, ev = 0;
  for (const f of d.fixes) {
    if (!playing) break;
    const r = await api('/api/location', 'POST', {tourist_id: t, lat: f.lat, lon: f.lon, timestamp: f.timestamp});
    n++; ev += (r.events || []).length; $('pstat').textContent = `${sc}: fix ${n}/${d.fixes.length} · ${ev} incident(s)`;
    await refresh(); await new Promise(r => setTimeout(r, +$('speed').value));
  }
  playing = false; $('pstat').textContent += ' · done';
}
['lz','lr','lh','li'].forEach(id => $(id).addEventListener('change', drawMap));
/* ---------- automatic, captioned full demo (for screen recording) ---------- */
const sleep = ms => new Promise(r => setTimeout(r, ms));
const cap = t => { const c = $('cap'); c.textContent = t || ''; c.style.display = t ? 'block' : 'none'; };
const goTop = () => window.scrollTo({top: 0, behavior: 'smooth'});
const to = id => $(id).scrollIntoView({behavior: 'smooth', block: 'center'});
let auto = false;
async function autoDemo() {
  if (auto) return; auto = true; $('speed').value = 140; goTop();
  cap('Step 1 - A tourist is registered: a Digital Tourist ID is issued (salted passport hash, hash-chained block, QR).');
  const r = await api('/api/demo_tourist', 'POST'); await refresh(); $('tsel').value = r.tourist_id; await sleep(3500);
  const steps = [
    ['geofence_violation', 'Step 2 - Geo-fencing: the tourist walks towards a restricted zone. Watch the early warning, then the HIGH alert.'],
    ['route_deviation', 'Step 3 - AI: the tourist drifts about 500 m off the planned route - detected without any action by the tourist.'],
    ['prolonged_inactivity', 'Step 4 - AI: no movement for 7 minutes away from any rest point - possible distress.'],
    ['lost_wandering', 'Step 5 - AI (Isolation Forest): erratic wandering that no fixed rule describes is flagged as a behaviour outlier.'],
    ['signal_loss', 'Step 6 - Signal loss: location updates stop for several minutes.']];
  for (const [sc, text] of steps) { goTop(); cap(text); await sleep(2200); await play(sc); await sleep(1500); }
  goTop(); cap('Step 7 - The tourist presses SOS: CRITICAL incident with coordinates, sent to the dashboard and emergency contact.');
  await sleep(2200); await sos(); await sleep(2500);
  cap('Incident log - every alert has type, severity, location and measured latency. Authorities can acknowledge and resolve.'); to('inc'); await sleep(5000);
  cap('Notifications - authority dashboard and SMS to the emergency contact, with a map link (SMS channel simulated).'); to('notes'); await sleep(5000);
  goTop(); cap('Step 8 - Blockchain ledger network: one validator node is tampered with...'); await sleep(2200); to('net'); await sleep(1200);
  await net('tamper', {node: 1}); await sleep(3500);
  cap('...it is detected (TAMPERED) while the majority still agrees. Now the audit and self-healing from the majority.'); await net('audit'); await sleep(3500);
  await net('heal'); await sleep(3000);
  goTop(); cap('Demo complete - geo-fencing, AI anomaly detection, blockchain Digital ID and incident response in one Python system.'); await sleep(5000);
  cap(''); auto = false;
}
if (new URLSearchParams(location.search).get('autodemo') === '1') setTimeout(autoDemo, 1500);

refresh(); setInterval(() => { if (!playing && !auto) refresh(); }, 2000);
