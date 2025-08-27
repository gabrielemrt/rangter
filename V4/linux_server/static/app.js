/* ---------- Helpers ---------- */
const $ = (id)=>document.getElementById(id);
const statusEl = $('status');
function setStatus(t){ if(statusEl) statusEl.textContent = t; }
function speed(){ return $('spd')?.value ?? 150; }

/* ---------- Backend ---------- */
async function send(c){
  try {
    const r = await fetch('/cmd', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({c})});
    const j = await r.json();
    setStatus(j.ok ? ('Inviato: ' + c) : ('Errore: ' + (j.err||'')));
    return j.ok;
  } catch(e){
    setStatus('Errore rete');
    return false;
  }
}

/* ---------- SETTINGS persistenti ---------- */
async function loadSettings(){
  try{
    const r = await fetch('/settings', {cache:'no-store'});
    const s = await r.json();

    // LED
    const [cr,cg,cb] = s.led_color || [255,180,100];
    const hex = '#' + [cr,cg,cb].map(x=>x.toString(16).padStart(2,'0')).join('');
    if ($('ledColor')) $('ledColor').value = hex;

    if ($('ledBr')) {
      $('ledBr').value = s.led_brightness ?? 60;
      if ($('brVal')) $('brVal').textContent = $('ledBr').value;
    }

    // velocità default
    if (s.motor_default_speed && $('spd')){
      const sp = String(s.motor_default_speed);
      $('spd').value = sp;
      if ($('spdVal')) $('spdVal').textContent = sp;
    }

    // servi
    const sa = s.servo_angles || [90,90,90,90];
    for (let i=0;i<4;i++){
      if ($('sv'+i)) { $('sv'+i).value = sa[i]; if ($('sv'+i+'Val')) $('sv'+i+'Val').textContent = sa[i]; }
    }
  }catch(e){}
}
async function saveSettings(patch, apply=false){
  try{
    await fetch('/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({...patch, apply})});
  }catch(e){}
}
loadSettings();

/* ---------- MOVIMENTO: hold + tastiera ---------- */
const pressed = new Set();
let lastCmd = 'S';
let tickTimer = null;
const TICK_MS = 300;

function mapKeysToCommand() {
  const up    = pressed.has('KeyW') || pressed.has('ArrowUp');
  const down  = pressed.has('KeyS') || pressed.has('ArrowDown');
  const left  = pressed.has('KeyA') || pressed.has('ArrowLeft');
  const right = pressed.has('KeyD') || pressed.has('ArrowRight');

  if (up && !down && !left && !right) return `F ${speed()}`;
  if (down && !up && !left && !right) return `B ${speed()}`;
  if (left && !right && !up && !down)  return `L ${speed()}`;
  if (right && !left && !up && !down)  return `R ${speed()}`;

  if (up && left)  return `L ${speed()}`;
  if (up && right) return `R ${speed()}`;
  if (down && left)  return `L ${speed()}`;
  if (down && right) return `R ${speed()}`;

  return 'S';
}
function updateMotion(force=false){
  const cmd = mapKeysToCommand();
  if (force || cmd !== lastCmd) {
    lastCmd = cmd;
    send(cmd);
  }
}
function startTick(){ if (!tickTimer) tickTimer = setInterval(()=>updateMotion(true), TICK_MS); }
function stopTick(){ if (tickTimer){ clearInterval(tickTimer); tickTimer=null; } }

function suppressBrowser(e){
  if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'].includes(e.code)) e.preventDefault();
}

/* ---------- SAFETY: ARM/HB/DISARM ---------- */
let hbTimer = null;
async function arm(){
  await send('ARM');
  if (!hbTimer) hbTimer = setInterval(()=> send('HB'), 200);
}
function disarm(){
  if (hbTimer){ clearInterval(hbTimer); hbTimer=null; }
  send('S');
  send('DISARM');
}
document.addEventListener('visibilitychange', ()=>{ if (document.visibilityState==='visible') arm(); else disarm(); });
window.addEventListener('load', arm);
window.addEventListener('beforeunload', disarm);
window.addEventListener('blur', disarm);
window.addEventListener('focus', arm);

/* ---------- Key handlers ---------- */
document.addEventListener('keydown', (e)=>{
  suppressBrowser(e);
  if (e.repeat) return;

  if (e.code === 'Space') { toggleLights(); return; }

  pressed.add(e.code);
  updateMotion();
  startTick();
});
document.addEventListener('keyup', (e)=>{
  suppressBrowser(e);
  pressed.delete(e.code);
  updateMotion();
  if (pressed.size === 0){
    stopTick();
    if (lastCmd !== 'S') { lastCmd='S'; send('S'); }
  }
});

/* ---------- Pulsanti UI (hold) ---------- */
function hold(cmdStart, cmdStop='S'){
  let holding = false, holdTimer = null;
  const start = ()=>{
    if (holding) return;
    holding = true;
    send(cmdStart());
    holdTimer = setInterval(()=> send(cmdStart()), TICK_MS);
  };
  const stop = ()=>{
    if (!holding) return;
    holding = false;
    clearInterval(holdTimer); holdTimer=null;
    send(cmdStop);
  };
  return {start, stop};
}
const mapBtns = {
  btnF: hold(()=>`F ${speed()}`),
  btnB: hold(()=>`B ${speed()}`),
  btnL: hold(()=>`L ${speed()}`),
  btnR: hold(()=>`R ${speed()}`)
};
Object.entries(mapBtns).forEach(([id,h])=>{
  const el = $(id); if (!el) return;
  ['mousedown','touchstart'].forEach(ev=> el.addEventListener(ev, h.start));
  ['mouseup','mouseleave','touchend','touchcancel'].forEach(ev=> el.addEventListener(ev, h.stop));
});
if ($('btnS')) $('btnS').addEventListener('click', ()=> send('S'));

/* ---------- Sliders & color ---------- */
if ($('spd')){
  $('spd').addEventListener('input', ()=> $('spdVal').textContent = $('spd').value);
  $('spd').addEventListener('change', ()=> saveSettings({motor_default_speed: Number($('spd').value)}));
}

function hexToRgb(hex){
  let h = hex.replace('#','');
  if (h.length===3) h = h.split('').map(c=>c+c).join('');
  const r = parseInt(h.slice(0,2),16);
  const g = parseInt(h.slice(2,4),16);
  const b = parseInt(h.slice(4,6),16);
  return {r,g,b};
}

const ledStateEl = $('ledState');
const ledStatusEl = $('ledStatus');
const colorEl = $('ledColor');
const brEl = $('ledBr');
let ledsOn = false;

function setLedStateLabel(on){ ledsOn = on; if (ledStateEl) ledStateEl.textContent = on ? 'accese' : 'spente'; }
async function sendLedOn(){ const ok = await send('LED ON'); if (ok) setLedStateLabel(true); }
async function sendLedOff(){ const ok = await send('LED OFF'); if (ok) setLedStateLabel(false); }
function toggleLights(){ ledsOn ? sendLedOff() : sendLedOn(); }

let colorDebounce=null, brDebounce=null;
function sendColorNow(){
  if (!colorEl) return;
  const {r,g,b} = hexToRgb(colorEl.value);
  send(`LED RGB ${r} ${g} ${b}`);
  setLedStateLabel(true);
  if (ledStatusEl) ledStatusEl.textContent = `Colore RGB: ${r}, ${g}, ${b}`;
  saveSettings({led_color:[r,g,b]});
}
function sendBrightnessNow(){
  if (!brEl) return;
  const v = brEl.value;
  if ($('brVal')) $('brVal').textContent = v;
  send(`LED BR ${v}`);
  if (ledStatusEl) ledStatusEl.textContent = `Potenza: ${v}/255`;
  saveSettings({led_brightness: Number(v)});
}
if (colorEl){
  colorEl.addEventListener('input', ()=> { clearTimeout(colorDebounce); colorDebounce=setTimeout(sendColorNow, 80); });
  colorEl.addEventListener('change', sendColorNow);
}
if (brEl){
  brEl.addEventListener('input', ()=> { clearTimeout(brDebounce); brDebounce=setTimeout(sendBrightnessNow, 60); });
  brEl.addEventListener('change', sendBrightnessNow);
}

/* ---------- Braccio: slider + pulsanti ---------- */
function bindServoSlider(id, idx){
  const slider = $(id);
  const label  = $(id + "Val");
  if (!slider) return;
  let debounce = null;
  const sendNow = ()=>{
    const a = parseInt(slider.value);
    if (label) label.textContent = a;
    send(`SV ${idx} ${a}`);
    const arr = [0,1,2,3].map(i => Number($('sv'+i)?.value || 90));
    saveSettings({servo_angles: arr});
  };
  slider.addEventListener('input', ()=>{ if (label) label.textContent = slider.value; clearTimeout(debounce); debounce=setTimeout(sendNow, 50); });
  slider.addEventListener('change', sendNow);
}
bindServoSlider('sv0', 0);
bindServoSlider('sv1', 1);
bindServoSlider('sv2', 2);
bindServoSlider('sv3', 3);

if ($('svAttach')) $('svAttach').addEventListener('click', ()=> send('SV ATTACH'));
if ($('svDetach')) $('svDetach').addEventListener('click', ()=> send('SV DETACH'));
if ($('svHome'))   $('svHome').addEventListener('click',   ()=> send('SV HOME'));

/* ---------- Banner ALLARMI (/health) ---------- */
const alertsWrap = $('alerts');
const alertList = $('alertList');
async function pollHealth(){
  const items = [];
  try {
    const r = await fetch('/health', {cache:'no-store'});
    if (!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    if (!j.video)  items.push('Video offline: la camera non sta trasmettendo.');
    if (!j.serial) items.push('Seriale Arduino offline: controlla USB/alimentazione.');
    if (!j.ok && j.video && j.serial) items.push('Stato non OK: controlla i log.');
  } catch(e){
    items.push('Backend non raggiungibile: verifica che il server sia in esecuzione.');
  }
  if (!alertList || !alertsWrap) return;
  alertList.innerHTML = '';
  if (items.length){
    items.forEach(t=>{
      const li = document.createElement('li'); li.textContent = t; alertList.appendChild(li);
    });
    alertsWrap.style.display = 'block';
  } else {
    alertsWrap.style.display = 'none';
  }
}
setInterval(pollHealth, 2000);
pollHealth();
