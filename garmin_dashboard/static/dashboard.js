/* DATA is injected by the template as `const DATA = {...};` just above this. */
const C = {ink:'#1c2530',muted:'#67727e',grid:'#e9ecef',run:'#e8663c',bike:'#2f7fd1',swim:'#1aa89a',
           ctl:'#2f7fd1',atl:'#e8663c',tsb:'#5c9e57'};

if (typeof Chart === 'undefined') {
  document.querySelectorAll('.chartbox').forEach(b => {
    b.style.display = 'flex'; b.style.alignItems = 'center'; b.style.justifyContent = 'center';
    b.innerHTML = '<div style="color:var(--muted);font-size:13px;text-align:center">' +
      'Chart library did not load.<br>This page needs an internet connection ' +
      'the first time you open it (Chart.js loads from a CDN).</div>';
  });
  throw new Error('Chart.js failed to load from CDN');
}

Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.color = C.muted;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.maintainAspectRatio = false;

const shortDate = s => { const d = new Date(s+'T00:00'); return d.toLocaleDateString('en-US',{month:'short',day:'numeric'}); };
const everyNth = (arr,n) => arr.map((v,i)=> i%n===0 ? v : '');

/* ---------- countdown ---------- */
(function(){
  const el = document.getElementById('countdown');
  const nr = DATA.next_race;
  const main = document.createElement('div'); main.className='cd-main';
  if(nr){
    main.innerHTML = `<div class="lead">Next race &mdash; ${nr.weeks} weeks out</div>
      <div class="race">${nr.name}</div>
      <div class="big">${nr.days}<span> days</span></div>
      <div class="when">${nr.date_fmt}</div>`;
  } else {
    main.innerHTML = `<div class="lead">No upcoming races configured</div>`;
  }
  const list = document.createElement('ul'); list.className='cd-list';
  DATA.races.forEach(r=>{
    const li = document.createElement('li');
    if(r.past) li.className='past';
    const isNext = nr && r.name===nr.name && r.date===nr.date;
    li.innerHTML = `<span><span class="nm">${r.name}</span><br><span class="meta">${r.date_fmt}</span></span>
      <span class="rt">${ r.past
        ? '<span class="pill">done</span>'
        : `<b>${r.days}d</b> &nbsp;<span class="meta">${r.weeks}w</span><br>`
          + (isNext?'<span class="pill next">next up</span>':'<span class="pill">upcoming</span>') }</span>`;
    list.appendChild(li);
  });
  el.appendChild(main); el.appendChild(list);
})();

/* ---------- snapshot ---------- */
(function(){
  const s = DATA.snapshot, p = DATA.profile || {};
  const tsbNote = s.tsb==null ? '' : (s.tsb<-20 ? 'deep in the work' : s.tsb>5 ? 'fresh' : 'building');
  const cells = [
    ['CTL — fitness', fmt(s.ctl,0), s.ts_phrase ? nicePhrase(s.ts_phrase) : ''],
    ['ATL — fatigue', fmt(s.atl,0), '7-day load'],
    ['TSB — form', (s.tsb>0?'+':'')+fmt(s.tsb,0), tsbNote],
    ['ACWR', fmt(s.acwr,2), 'acute : chronic'],
    ['VO₂ max — run', fmt(s.vo2_run ?? p.vo2_run,1), s.vo2_bike?('bike '+fmt(s.vo2_bike,1)):''],
    ['Resting HR', s.rhr==null?'—':fmt(s.rhr,0)+' bpm', ''],
    ['HRV — 7-day', s.hrv==null?'—':fmt(s.hrv,0)+' ms', s.hrv_status?titleCase(s.hrv_status):''],
    ['Endurance score', fmt(p.endurance,0), p.endurance_class || ''],
    ['Readiness', fmt(p.readiness,0), p.readiness_level?titleCase(p.readiness_level):''],
    ['Cycling FTP', p.ftp?fmt(p.ftp,0)+' W':'—', ''],
    ['Weight', p.weight_kg? (p.weight_kg*2.20462).toFixed(0)+' lb':'—', p.height_cm? htFt(p.height_cm):''],
  ];
  const wrap = document.getElementById('snapshot');
  cells.forEach(([k,v,n])=>{
    const d=document.createElement('div'); d.className='stat';
    d.innerHTML=`<div class="k">${k}</div><div class="v">${v}</div>${n?`<div class="n">${n}</div>`:''}`;
    wrap.appendChild(d);
  });
})();
function fmt(v,dec){ return (v===null||v===undefined||Number.isNaN(v))?'—':Number(v).toFixed(dec); }
function titleCase(s){ return String(s).toLowerCase().replace(/(^|[_\s])\w/g,m=>m.toUpperCase()).replace(/_/g,' '); }
function nicePhrase(s){ return titleCase(String(s).replace(/_\d+$/,'')); }
function htFt(cm){ const t=cm/2.54; return Math.floor(t/12)+"'"+Math.round(t%12)+'"'; }

/* ---------- charts (rebuilt whenever the theme changes) ---------- */
const CHARTS = [];
function themeVars(){
  const cs = getComputedStyle(document.documentElement);
  return {ink:cs.getPropertyValue('--ink').trim(),
          muted:cs.getPropertyValue('--muted').trim(),
          grid:cs.getPropertyValue('--grid').trim()};
}
function drawCharts(){
  CHARTS.forEach(c => c.destroy());
  CHARTS.length = 0;
  const T = themeVars();
  Chart.defaults.color = T.muted;

  /* training load */
  const L = DATA.load;
  CHARTS.push(new Chart(loadChart,{
    type:'line',
    data:{ labels:L.labels, datasets:[
      {type:'line',label:'CTL (fitness)',data:L.ctl,borderColor:C.ctl,backgroundColor:C.ctl,
        borderWidth:2,pointRadius:0,tension:.3,spanGaps:true,yAxisID:'y'},
      {type:'line',label:'ATL (fatigue)',data:L.atl,borderColor:C.atl,backgroundColor:C.atl,
        borderWidth:1.5,borderDash:[4,3],pointRadius:0,tension:.3,spanGaps:true,yAxisID:'y'},
      {type:'line',label:'TSB (form)',data:L.tsb,borderColor:C.tsb,backgroundColor:'rgba(92,158,87,.16)',
        borderWidth:1.5,pointRadius:0,tension:.3,spanGaps:true,fill:'origin',yAxisID:'y1'},
    ]},
    options:{interaction:{mode:'index',intersect:false},
      scales:{
        x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:9,callback:(v,i)=>shortDate(L.labels[i])}},
        y:{position:'left',title:{display:true,text:'CTL / ATL load'},grid:{color:T.grid}},
        y1:{position:'right',title:{display:true,text:'TSB'},grid:{drawOnChartArea:false}},
      }}
  }));

  /* weekly volume + weekly time (same style, Monday-Sunday buckets) */
  const W = DATA.weekly;
  const bars = (cvs,block,color,title)=> CHARTS.push(new Chart(cvs,{
    type:'bar',
    data:{ labels:W.labels, datasets:[
      {label:block.unit+'/wk',data:block.values,backgroundColor:color+'cc',borderRadius:3},
    ]},
    options:{plugins:{legend:{display:false},title:{display:true,text:title},
        tooltip:{callbacks:{label:c=>` ${c.parsed.y} ${block.unit}`}}},
      scales:{x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:7}},
              y:{beginAtZero:true,grid:{color:T.grid}}}}
  }));
  bars(runMi,  W.dist.run,  C.run,  'Run (mi/wk)');
  bars(bikeMi, W.dist.bike, C.bike, 'Bike (mi/wk)');
  bars(swimKm, W.dist.swim, C.swim, 'Swim (km/wk)');
  bars(runHr,  W.time.run,  C.run,  'Run (h/wk)');
  bars(bikeHr, W.time.bike, C.bike, 'Bike (h/wk)');
  bars(swimHr, W.time.swim, C.swim, 'Swim (h/wk)');

  /* recovery */
  const R = DATA.recovery, lab = R.labels;
  const tick = {maxRotation:0,autoSkip:true,maxTicksLimit:6,callback:(v,i)=>shortDate(lab[i])};
  CHARTS.push(new Chart(hrvChart,{
    type:'line',
    data:{labels:lab,datasets:[
      {label:'baseline high',data:R.hrv_hi,borderColor:'transparent',backgroundColor:'rgba(47,127,209,.13)',
        pointRadius:0,fill:'+1',spanGaps:true},
      {label:'baseline low',data:R.hrv_lo,borderColor:'transparent',backgroundColor:'rgba(47,127,209,.13)',
        pointRadius:0,fill:false,spanGaps:true},
      {label:'HRV 7-day avg',data:R.hrv_weekly,borderColor:C.bike,borderWidth:2,pointRadius:0,tension:.3,spanGaps:true},
      {label:'last night',data:R.hrv_last,borderColor:T.muted,borderWidth:1,pointRadius:1.5,showLine:false},
    ]},
    options:{plugins:{legend:{display:false},title:{display:true,text:'HRV (ms)'}},
      scales:{x:{grid:{display:false},ticks:tick},y:{grid:{color:T.grid}}}}
  }));
  CHARTS.push(new Chart(rhrChart,{
    type:'line',
    data:{labels:lab,datasets:[
      {label:'Resting HR',data:R.rhr,borderColor:C.atl,backgroundColor:'rgba(232,102,60,.16)',
        borderWidth:2,pointRadius:0,tension:.3,fill:true,spanGaps:true}]},
    options:{plugins:{legend:{display:false},title:{display:true,text:'Resting HR (bpm)'}},
      scales:{x:{grid:{display:false},ticks:tick},y:{grid:{color:T.grid}}}}
  }));
  CHARTS.push(new Chart(sleepChart,{
    type:'bar',
    data:{labels:lab,datasets:[
      {type:'bar',label:'Sleep (h)',data:R.sleep_h,order:2,borderRadius:3,
        backgroundColor:R.sleep_score.map(sc=> sc==null?T.grid: sc>=85?'#4f9d54': sc>=70?'#c9a227':'#c65b3c')},
    ]},
    options:{plugins:{legend:{display:false},title:{display:true,text:'Sleep (h) — green = good score'}},
      scales:{x:{grid:{display:false},ticks:tick},y:{beginAtZero:true,suggestedMax:10,grid:{color:T.grid}}}}
  }));

  /* VO2 max */
  const V = DATA.vo2, vv = V.values.filter(x=>x!=null);
  const lo = vv.length? Math.floor(Math.min(...vv)-1):0, hi = vv.length? Math.ceil(Math.max(...vv)+1):100;
  CHARTS.push(new Chart(vo2Chart,{
    type:'line',
    data:{labels:V.labels,datasets:[
      {label:'VO₂ max (run)',data:V.values,borderColor:C.tsb,backgroundColor:'rgba(92,158,87,.16)',
        borderWidth:2,pointRadius:0,tension:.3,fill:true,spanGaps:true}]},
    options:{plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:9,callback:(v,i)=>shortDate(V.labels[i])}},
              y:{min:lo,max:hi,grid:{color:T.grid}}}}
  }));
}

/* ---------- table ---------- */
(function(){
  const tb = document.querySelector('#actTable tbody');
  if(!DATA.table.length){ tb.innerHTML='<tr><td colspan="7" style="color:var(--muted)">No activities in window.</td></tr>'; return; }
  DATA.table.forEach(r=>{
    const tr=document.createElement('tr');
    tr.innerHTML = `<td>${shortDate(r.date)}</td>
      <td><span class="tag ${r.sport}">${r.sport}</span></td>
      <td class="name">${r.name}</td>
      <td>${r.dist}</td><td>${r.pace}</td><td>${r.dur}</td><td>${r.hr??'—'}</td>`;
    tb.appendChild(tr);
  });
})();

/* ---------- PRs + predictions ---------- */
(function(){
  const p = DATA.profile||{}, box = document.getElementById('prBlock');
  const groups = [['run','Running PRs'],['tri','Swim / bike PRs']];
  let html='';
  (p.prs||[]).length && groups.forEach(([g,title])=>{
    const items=(p.prs||[]).filter(x=>x.grp===g);
    if(!items.length) return;
    html += `<div style="margin-bottom:14px"><div class="k" style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">${title}</div><div class="prs">`;
    items.forEach(it=> html += `<div class="pr"><div class="k">${it.label}</div><div class="v">${it.value}</div></div>`);
    html += `</div></div>`;
  });
  if(p.predictions){
    html += `<div><div class="k" style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Garmin race predictions (current fitness)</div><div class="prs">`;
    Object.entries(p.predictions).forEach(([k,v])=> v && v!=='--' && (html += `<div class="pr"><div class="k">${k}</div><div class="v">${v}</div></div>`));
    html += `</div></div>`;
  }
  box.innerHTML = html || '<span style="color:var(--muted)">No records returned.</span>';
})();

/* ---------- theme toggle (Auto -> Light -> Dark) ---------- */
(function(){
  const btn = document.getElementById('themeBtn');
  const MODES = [['auto','Auto'],['light','Light'],['dark','Dark']];
  function apply(mode){
    if(mode === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = mode;
    try{ localStorage.setItem('dash-theme', mode); }catch(e){}
    const m = MODES.find(x => x[0] === mode) || MODES[0];
    btn.textContent = m[1];
    btn.dataset.mode = m[0];
  }
  let mode = 'auto';
  try{ mode = localStorage.getItem('dash-theme') || 'auto'; }catch(e){}
  apply(mode);
  drawCharts();
  btn.addEventListener('click', () => {
    const i = MODES.findIndex(x => x[0] === (btn.dataset.mode || 'auto'));
    apply(MODES[(i + 1) % MODES.length][0]);
    drawCharts();
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if((btn.dataset.mode || 'auto') === 'auto') drawCharts();
  });
})();
