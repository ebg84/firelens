"use strict";

// --- reference: CA county FIPS (06xxx) -> name (static lookup, no data dependency) ---
const CA_COUNTY = {
  "001":"Alameda","003":"Alpine","005":"Amador","007":"Butte","009":"Calaveras","011":"Colusa",
  "013":"Contra Costa","015":"Del Norte","017":"El Dorado","019":"Fresno","021":"Glenn","023":"Humboldt",
  "025":"Imperial","027":"Inyo","029":"Kern","031":"Kings","033":"Lake","035":"Lassen","037":"Los Angeles",
  "039":"Madera","041":"Marin","043":"Mariposa","045":"Mendocino","047":"Merced","049":"Modoc","051":"Mono",
  "053":"Monterey","055":"Napa","057":"Nevada","059":"Orange","061":"Placer","063":"Plumas","065":"Riverside",
  "067":"Sacramento","069":"San Benito","071":"San Bernardino","073":"San Diego","075":"San Francisco",
  "077":"San Joaquin","079":"San Luis Obispo","081":"San Mateo","083":"Santa Barbara","085":"Santa Clara",
  "087":"Santa Cruz","089":"Shasta","091":"Sierra","093":"Siskiyou","095":"Solano","097":"Sonoma",
  "099":"Stanislaus","101":"Sutter","103":"Tehama","105":"Trinity","107":"Tulare","109":"Tuolumne",
  "111":"Ventura","113":"Yolo","115":"Yuba",
};
const QUAD = {
  priority: { color:"#d64545", label:"Priority",
    read:"Both the fire-weather hazard and the built exposure here sit above the statewide median — the highest-attention quadrant. The decision: manage fuel <em>and</em> harden structures; this is where both levers matter." },
  monitor: { color:"#e08a2e", label:"Monitor",
    read:"The fire-weather hazard is above the statewide median, but relatively little is built here to lose. The decision: monitor and manage fuel; structural hardening is a lower priority than in high-exposure ZIPs." },
  harden: { color:"#3b82c4", label:"Harden",
    read:"The fire-weather hazard sits below the statewide median, but built exposure is high. The decision: harden structures — the people and property, not the weather, drive the risk here." },
  low_priority: { color:"#3fa564", label:"Low priority",
    read:"Both hazard and exposure sit below the statewide median — a lower relative priority for fire-weather action, though the trend below still applies." },
};
const METRIC_META = {
  fwi: { label:"Fire Weather Index", note:"annual mean", unit:"", decimals:1 },
  season_length: { label:"Fire-season length", note:"days/yr", unit:" d", decimals:0 },
  dc_pctile: { label:"Drought Code", note:"deep-soil dryness", unit:"", decimals:0 },
};

const $ = (id) => document.getElementById(id);
const fmtNum = (v, d=1) => v == null ? "—" : Number(v).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPctChange = (v) => v == null ? "—" : (v>=0?"+":"") + (v*100).toFixed(1) + "%";
const fmtMoney = (v) => v == null ? "—" : "$" + Math.round(v).toLocaleString();
const countyName = (fips) => CA_COUNTY[String(fips).slice(-3)] || ("FIPS " + fips);

function setStatus(msg, isError=false) {
  const el = $("status");
  el.hidden = false; el.textContent = msg; el.classList.toggle("error", isError);
  $("view").hidden = true;
}

async function assess(zip) {
  zip = String(zip).trim();
  if (!/^\d{5}$/.test(zip)) { setStatus("Enter a 5-digit California ZIP code.", true); return; }
  $("zip").value = zip;
  setStatus("Assessing " + zip + "…");
  let res, data;
  try { res = await fetch("/api/place/" + zip); } catch (e) { setStatus("Network error.", true); return; }
  if (res.status === 404) { setStatus("ZIP " + zip + " is not in the California serving layer.", true); return; }
  if (!res.ok) { setStatus("Error " + res.status + " for ZIP " + zip + ".", true); return; }
  data = await res.json();
  render(data);
}

// Search: ZIP, county, or place name -> route to the real ZIP-grain view.
async function doSearch(q) {
  q = (q || "").trim();
  if (!q) return;
  setStatus(`Searching “${q}”…`);
  let res;
  try { res = await (await fetch("/api/search?q=" + encodeURIComponent(q))).json(); }
  catch (e) { setStatus("Search error — try again.", true); return; }

  if (res.type === "zip" && res.resolved) { assess(res.zip); return; }
  if (res.type === "zip") { setStatus(res.message, true); return; }

  const el = $("status");
  if (res.type === "county") {
    const chips = res.zips.slice(0, 80).map((z) =>
      `<button class="chip" data-zip="${z.zip}">${z.zip}</button>`).join(" ");
    el.hidden = false; el.classList.remove("error"); $("view").hidden = true;
    el.innerHTML = `<strong>${res.county} County</strong> — ${res.count} ZIPs. `
      + `<span class="na-note">${res.note}</span><div style="margin-top:10px">${chips}</div>`;
    el.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => assess(c.dataset.zip)));
    return;
  }
  if (res.type === "ambiguous") {
    const chips = res.candidates.map((c) =>
      `<button class="chip" data-c="${c}">${c}</button>`).join(" ");
    el.hidden = false; el.classList.remove("error"); $("view").hidden = true;
    el.innerHTML = `${res.message}<div style="margin-top:8px">${chips}</div>`;
    el.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => doSearch(c.dataset.c)));
    return;
  }
  setStatus(res.message || "Couldn't resolve that.", true);
}

let currentZip = null;
const aiCache = {};

function render(d) {
  $("status").hidden = true;
  $("view").hidden = false;
  currentZip = d.zip;
  renderHeadline(d);
  renderMatrix(d.matrix);
  renderTrends(d.trends, d.zip);
  renderFuel(d.fuel);
  renderNri(d.nri);
  // The interpretation engine: auto-run once per ZIP (cached), follow-ups via the box.
  if (aiCache[d.zip]) showAnswer(aiCache[d.zip].answer, aiCache[d.zip].model);
  else interpret(d.zip, null, true);
}

function mdToHtml(s) {
  const esc = s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  const bold = esc.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return bold.split(/\n\n+/).map((p) => `<p>${p.replace(/\n/g,"<br/>")}</p>`).join("");
}

function showAnswer(answer, model) {
  $("ai-answer").innerHTML = mdToHtml(answer);
  $("ai-model").textContent = model ? "via " + model : "";
}

function interpret(zip, question, cache) {
  $("ai-answer").innerHTML = `<span class="loading">FireLens is reading the record for ${zip}…</span>`;
  $("ai-model").textContent = "";
  let acc = "";
  let url = `/api/ask/stream?zip=${encodeURIComponent(zip)}`;
  if (question) url += `&question=${encodeURIComponent(question)}`;
  const es = new EventSource(url);
  es.addEventListener("delta", (e) => {
    acc += JSON.parse(e.data).text;
    $("ai-answer").innerHTML = mdToHtml(acc);  // progressive render
  });
  es.addEventListener("done", (e) => {
    const d = JSON.parse(e.data);
    $("ai-model").textContent = d.model ? "via " + d.model
      : (d.degraded ? "data live · narrative unavailable" : "");
    if (cache && acc && !d.degraded) aiCache[zip] = { answer: acc, model: d.model };
    es.close();
  });
  es.addEventListener("error", (e) => {
    // SSE connection failure (distinct from a clean degraded 'done'); panels still render.
    if (!acc) $("ai-answer").innerHTML =
      `<span class="loading">Interpretation temporarily unavailable — the data panels below are live.</span>`;
    es.close();
  });
}

function renderHeadline(d) {
  const county = countyName(d.location.county_fips);
  const q = d.matrix.quadrant;
  let html;
  if (q && QUAD[q]) {
    html = `<span class="quad-name">ZIP ${d.zip} (${county})</span> sits in the
      <span class="quad-name" style="color:${QUAD[q].color}">${QUAD[q].label}</span> quadrant —
      hazard <strong class="level-${d.matrix.hazard.level}">${d.matrix.hazard.level}</strong>,
      exposure <strong class="level-${d.matrix.exposure.level}">${d.matrix.exposure.level}</strong>.
      <br/>${QUAD[q].read}`;
  } else {
    html = `<span class="quad-name">ZIP ${d.zip} (${county})</span> —
      <span class="na-note">not in the FEMA NRI residential set (one of 108 such ZIPs), so built exposure
      can't be placed and there is no hazard×exposure quadrant.</span> The fire-weather trend below still applies.`;
  }
  $("headline").innerHTML = html;
}

function renderMatrix(m) {
  const el = $("panel-matrix");
  if (!m.available) {
    el.innerHTML = `<h3>Hazard × Exposure</h3><div class="sub">FEMA NRI × FWI matrix</div>
      <p class="na-note">No quadrant — this ZIP is absent from the FEMA NRI residential layer. Exposure is shown as "—", never zero.</p>`;
    return;
  }
  const q = QUAD[m.quadrant];
  el.innerHTML = `
    <h3>Hazard × Exposure</h3><div class="sub">FEMA NRI exposure × FWI hazard, split at statewide medians</div>
    <span class="quad-badge" style="background:${q.color}">${q.label}</span>
    <div class="axis"><span class="k">Hazard — mean FWI (recent era)</span>
      <span class="v"><strong class="level-${m.hazard.level}">${m.hazard.level}</strong> · ${fmtNum(m.hazard.fwi_level,1)} <span class="unit">(median ${fmtNum(m.hazard.median,1)})</span></span></div>
    <div class="axis"><span class="k">Exposure — expected annual building loss</span>
      <span class="v"><strong class="level-${m.exposure.level}">${m.exposure.level}</strong> · ${fmtMoney(m.exposure.wfir_ealt)} <span class="unit">(median ${fmtMoney(m.exposure.median)})</span></span></div>
    <p class="sub" style="margin-top:12px">${m.note}</p>`;
}

function renderTrends(t, zip) {
  const el = $("panel-trends");
  let rows = "";
  for (const key of Object.keys(t.metrics)) {
    const meta = METRIC_META[key] || { label:key, note:"", decimals:1 };
    const v = t.metrics[key];
    const dir = v.pct_change > 0.005 ? "up" : v.pct_change < -0.005 ? "down" : "flat";
    rows += `<div class="metric-row">
      <span class="name">${meta.label}<br/><span class="unit">${meta.note}</span></span>
      <span class="vals">${fmtNum(v.baseline,meta.decimals)} → ${fmtNum(v.recent,meta.decimals)}</span>
      <span class="delta ${dir}">${fmtPctChange(v.pct_change)}</span></div>`;
  }
  el.innerHTML = `<h3>Atmospheric trend</h3>
    <div class="sub">${t.baseline_era} baseline → ${t.recent_era}</div>${rows}
    <span class="cite"><a href="/api/trends/${zip}" target="_blank">/api/trends/${zip} ↗</a></span>`;
}

function renderFuel(f) {
  const el = $("panel-fuel");
  if (!f.available) {
    el.innerHTML = `<h3>Fuel substrate</h3><div class="sub">LANDFIRE FBFM40</div>
      <p class="na-note">No fuel raster coverage for this ZIP — shown as "—", not zero.</p>`;
    return;
  }
  const pct = (f.burnable_frac*100);
  const comp = f.composition || {};
  const order = Object.entries(comp).sort((a,b)=> (b[1]||0)-(a[1]||0)).filter(([,v])=>v>0.001);
  let rows = order.map(([k,v]) =>
    `<div class="comp-row"><span>${k.replace(/_/g," ")}</span><span class="cv">${(v*100).toFixed(0)}%</span></div>`).join("");
  el.innerHTML = `<h3>Fuel substrate</h3><div class="sub">LANDFIRE FBFM40 — what's here to burn</div>
    <div class="big">${pct.toFixed(0)}%<span class="unit"> burnable</span></div>
    <div class="bar"><span style="width:${pct.toFixed(0)}%"></span></div>
    <p class="sub">Dominant: <strong>${(f.dominant_class||"").replace(/_/g," ")}</strong></p>
    ${rows}`;
}

function renderNri(n) {
  const el = $("panel-nri");
  if (!n.available) {
    el.innerHTML = `<h3>Built exposure (FEMA NRI)</h3><div class="sub">2025 snapshot</div>
      <p class="na-note">Not in the NRI residential set — exposure unavailable ("—"), distinct from a real zero.</p>`;
    return;
  }
  el.innerHTML = `<h3>Built exposure (FEMA NRI)</h3><div class="sub">2025 snapshot · ${n.n_tracts} tract(s)</div>
    <div class="big">${fmtMoney(n.wfir_ealt)}<span class="unit"> expected annual building loss</span></div>
    <div class="axis"><span class="k">Wildfire risk index</span><span class="v">${fmtNum(n.wfir_risks,1)} <span class="unit">/ 100</span></span></div>
    <div class="axis"><span class="k">Annualized burn frequency</span><span class="v">${n.wfir_afreq==null?"—":(n.wfir_afreq*100).toFixed(2)+"% /yr"}</span></div>`;
}

// Free-form questions -> the bounded agentic layer (Opus + get_place/get_fires_near),
// with tool calls shown (investigation made visible). Auto-load stays on the interpreter.
function askAgent(zip, question) {
  $("ai-answer").innerHTML = `<span class="loading">FireLens is investigating…</span>`;
  $("ai-model").textContent = "";
  let acc = "", tools = [];
  const renderAll = () => {
    const tline = tools.length
      ? `<div class="ai-tools">🔎 queried ${tools.map((t) => `${t.name}(${t.input.zip || ""})`).join(" · ")}</div>`
      : "";
    $("ai-answer").innerHTML = tline + (acc ? mdToHtml(acc) : `<span class="loading">…</span>`);
  };
  let url = `/api/agent/stream?q=${encodeURIComponent(question)}`;
  if (zip) url += `&zip=${encodeURIComponent(zip)}`;
  const es = new EventSource(url);
  es.addEventListener("tool", (e) => { tools.push(JSON.parse(e.data)); renderAll(); });
  es.addEventListener("delta", (e) => { acc += JSON.parse(e.data).text; renderAll(); });
  es.addEventListener("done", (e) => {
    const d = JSON.parse(e.data);
    $("ai-model").textContent = d.model ? "via " + d.model + (d.degraded ? " · fallback" : "")
      : "data live · narrative unavailable";
    es.close();
  });
  es.addEventListener("error", () => {
    if (!acc) $("ai-answer").innerHTML =
      `<span class="loading">Investigation unavailable — the data panels below are live.</span>`;
    es.close();
  });
}

// --- wiring ---
document.addEventListener("DOMContentLoaded", () => {
  $("zip-form").addEventListener("submit", (e) => { e.preventDefault(); doSearch($("zip").value); });
  document.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => assess(c.dataset.zip)));
  $("ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("ask-q").value.trim();
    if (q) { askAgent(currentZip, q); $("ask-q").value = ""; }
  });
  const param = new URLSearchParams(location.search).get("zip");
  assess(param && /^\d{5}$/.test(param) ? param : "95404"); // ?zip= from the map, else a real default
});
