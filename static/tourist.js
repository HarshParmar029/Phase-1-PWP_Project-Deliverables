/* Tourist phone view: long-press SOS (prevents accidental alerts), live GPS, offline queue, 3 languages. */
const TID = document.getElementById('app').dataset.tid;
const L = {
  en: {h1: 'Tourist Safety', hold: 'Hold for 3 seconds to send SOS', start: 'Start live GPS', stop: 'Stop GPS', sent: 'SOS sent to authorities and your emergency contact', idle: 'Idle'},
  hi: {h1: 'पर्यटक सुरक्षा', hold: 'SOS भेजने के लिए 3 सेकंड दबाए रखें', start: 'लाइव GPS शुरू करें', stop: 'GPS बंद करें', sent: 'SOS अधिकारियों और आपके आपातकालीन संपर्क को भेजा गया', idle: 'निष्क्रिय'},
  gu: {h1: 'પ્રવાસી સુરક્ષા', hold: 'SOS મોકલવા 3 સેકન્ડ દબાવી રાખો', start: 'લાઇવ GPS શરૂ કરો', stop: 'GPS બંધ કરો', sent: 'SOS અધિકારીઓ અને તમારા કટોકટી સંપર્કને મોકલાયો', idle: 'નિષ્ક્રિય'}
};
let cur = 'en', watchId = null, lastPos = null, timer = null;
const $ = id => document.getElementById(id);
function lang(l) { cur = l; $('h1').textContent = L[l].h1; $('hold').textContent = L[l].hold; $('gpsbtn').textContent = watchId ? L[l].stop : L[l].start; $('status').textContent = L[l].idle; }

/* offline queue: fixes that cannot be sent are stored and flushed when the network returns */
let queue = JSON.parse(localStorage.getItem('q_' + TID) || '[]');
function saveQ() { localStorage.setItem('q_' + TID, JSON.stringify(queue)); $('queue').textContent = queue.length ? `Offline queue: ${queue.length} fix(es) waiting` : ''; }
async function post(path, body) { const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}); return r.json(); }
async function flush() { while (queue.length) { try { await post('/api/location', queue[0]); queue.shift(); saveQ(); } catch (e) { return; } } }
async function sendFix(lat, lon) {
  const fix = {tourist_id: TID, lat, lon, timestamp: new Date().toISOString()}; lastPos = fix;
  try { await flush(); const r = await post('/api/location', fix);
    $('status').textContent = r.ok ? `Fix sent (${r.latency_ms} ms)` + (r.events && r.events.length ? ' · ALERT: ' + r.events.map(e => e.incident_type).join(', ') : '') : 'Error: ' + r.error;
  } catch (e) { queue.push(fix); saveQ(); $('status').textContent = 'Offline - fix queued'; }
}
window.addEventListener('online', flush);
function toggleGps() {
  if (watchId) { clearInterval(watchId); watchId = null; lang(cur); return; }
  if (!navigator.geolocation) { $('status').textContent = 'Geolocation not supported'; return; }
  const tick = () => navigator.geolocation.getCurrentPosition(p => sendFix(p.coords.latitude, p.coords.longitude), e => $('status').textContent = 'GPS: ' + e.message, {enableHighAccuracy: true});
  tick(); watchId = setInterval(tick, 30000); $('gpsbtn').textContent = L[cur].stop;
}
function simFix() { sendFix(20.8880 + (Math.random() - .5) * 0.0004, 70.4010 + (Math.random() - .5) * 0.0004); }

/* long-press SOS (3 s) */
const btn = $('sosbtn'), ring = $('ring'); let t0 = 0, raf = null;
function tickRing() { const p = Math.min(1, (performance.now() - t0) / 3000); ring.setAttribute('stroke-dashoffset', 553 * (1 - p));
  if (p >= 1) { cancelHold(); fireSos(); } else raf = requestAnimationFrame(tickRing); }
function startHold(e) { e.preventDefault(); t0 = performance.now(); raf = requestAnimationFrame(tickRing); }
function cancelHold() { if (raf) cancelAnimationFrame(raf); raf = null; ring.setAttribute('stroke-dashoffset', 553); }
function gpsOnce(ms) {
  return new Promise(res => { if (!navigator.geolocation) return res(null);
    navigator.geolocation.getCurrentPosition(p => res({lat: p.coords.latitude, lon: p.coords.longitude}), () => res(null), {enableHighAccuracy: true, timeout: ms, maximumAge: 60000}); });
}
let pendingSos = JSON.parse(localStorage.getItem('sos_' + TID) || 'null');
function savePending() { if (pendingSos) localStorage.setItem('sos_' + TID, JSON.stringify(pendingSos)); else localStorage.removeItem('sos_' + TID); }
async function sendSos(body) {
  /* returns 'sent' | 'offline' | 'error'. A SERVER error is shown as an error, only a real network failure is "offline". */
  let r;
  try { r = await fetch('/api/sos', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}); }
  catch (e) { return 'offline'; }
  let j = null; try { j = await r.json(); } catch (e) { /* non-JSON body */ }
  if (r.ok && j && j.ok) return 'sent';
  $('status').textContent = 'Server error: ' + ((j && j.error) || ('HTTP ' + r.status));
  return 'error';
}
async function retrySos() {
  if (!pendingSos) return;
  const res = await sendSos(pendingSos);
  if (res === 'sent') { pendingSos = null; savePending(); $('status').textContent = L[cur].sent; }
  else if (res === 'offline') { setTimeout(retrySos, 5000); }
}
async function fireSos() {
  const body = {tourist_id: TID, note: 'from tourist app', request_id: 'sos-' + TID + '-' + Date.now()};
  if (lastPos) { body.lat = lastPos.lat; body.lon = lastPos.lon; }
  else { const g = await gpsOnce(2500); if (g) { body.lat = g.lat; body.lon = g.lon; } }   // else server uses last stored location
  $('status').textContent = 'Sending SOS...';
  const res = await sendSos(body);
  if (res === 'sent') $('status').textContent = L[cur].sent;
  else if (res === 'offline') { pendingSos = body; savePending(); $('status').textContent = 'No network - SOS saved and will be sent automatically'; setTimeout(retrySos, 5000); }
}
window.addEventListener('online', retrySos);
['mousedown', 'touchstart'].forEach(ev => btn.addEventListener(ev, startHold));
['mouseup', 'mouseleave', 'touchend', 'touchcancel'].forEach(ev => btn.addEventListener(ev, cancelHold));
saveQ(); retrySos();
