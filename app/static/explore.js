"use strict";

const QUAD = {
  priority: { color:"#d64545", label:"Priority", tip:"Priority — high weather + high stakes",
    read:"hazard and exposure both above the statewide median — manage fuel <em>and</em> harden structures." },
  monitor: { color:"#e08a2e", label:"Monitor", tip:"Monitor — high weather, less built",
    read:"hazard elevated, little built to lose — monitor and manage fuel." },
  harden: { color:"#3b82c4", label:"Harden", tip:"Harden — structures drive the risk",
    read:"hazard below median but exposure high — harden structures; people, not weather, drive the risk." },
  low_priority: { color:"#3fa564", label:"Low priority", tip:"Lower priority — both below median",
    read:"hazard and exposure both below the statewide median — lower relative priority." },
};
const NA_COLOR = "#5a6b78";

// CA county FIPS (3-digit suffix) -> name, for tooltips.
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
const countyName = (fips) => fips ? (CA_COUNTY[String(fips).slice(-3)] || "") : "";

// 3-line glanceable tooltip: ZIP · County / plain quadrant / FWI era-trend (honest label).
function tipHtml(p) {
  const cty = countyName(p.county_fips);
  const l1 = `<strong>${p.zip}</strong>${cty ? ` · ${cty} County` : ""}`;
  const q = p.quadrant;
  const l2 = q && QUAD[q] ? QUAD[q].tip : "Not in FEMA NRI — no quadrant";
  let l3 = "";
  if (p.fwi_pct_change != null) {
    const v = p.fwi_pct_change * 100;
    l3 = `<span style="color:#9fb0bd">FWI ${v >= 0 ? "+" : ""}${v.toFixed(1)}% vs 1980–2000 baseline</span>`;
  }
  return `${l1}<br/>${l2}${l3 ? "<br/>" + l3 : ""}`;
}

const zipLatLng = {};   // zip -> [lat,lon] (for search pan)
const zipLayer = {};    // zip -> polygon layer (for search fit/highlight)
const quadColor = (q) => (QUAD[q] && QUAD[q].color) || NA_COLOR;
const fmtMoney = (v) => v == null ? "—" : "$" + Math.round(v).toLocaleString();
const fmtNum = (v, d=1) => v == null ? "—" : Number(v).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPct = (v) => v == null ? "—" : (v>=0?"+":"") + (v*100).toFixed(1) + "%";

// --- metric views: quadrant (categorical) + viridis-by-value (continuous) ---
const VIEWS = {
  quadrant:       { label: "Quadrant", kind: "cat" },
  fwi_recent:     { label: "Fire-weather (FWI)", kind: "viridis",
                    gloss: "how dangerous fire-weather conditions are — heat, wind, dryness",
                    fmt: (v) => Number(v).toFixed(1) },
  wfir_ealt:      { label: "Exposure ($/yr)", kind: "viridis", log: true,
                    gloss: "FEMA's estimate of building value lost to wildfire each year",
                    fmt: (v) => "$" + Math.round(v).toLocaleString() },
  extreme_recent: { label: "Extreme days", kind: "viridis",
                    gloss: "days per year of extreme fire-weather conditions (recent era)",
                    fmt: (v) => Number(v).toFixed(1) },
};
const VIEW_ORDER = ["quadrant", "fwi_recent", "wfir_ealt", "extreme_recent"];
const VIRIDIS = [[68,1,84],[72,40,120],[62,74,137],[49,104,142],[38,130,142],[31,158,137],[53,183,121],[110,206,88],[181,222,43],[253,231,37]];
function viridis(t) {
  t = Math.max(0, Math.min(1, t));
  const n = VIRIDIS.length - 1, i = Math.min(n - 1, Math.floor(t * n)), f = t * n - i;
  const a = VIRIDIS[i], b = VIRIDIS[i + 1], c = (k) => Math.round(a[k] + (b[k] - a[k]) * f);
  return `rgb(${c(0)},${c(1)},${c(2)})`;
}
let currentView = "quadrant";
const featureProps = [];
const domains = {};

function computeDomain(view) {
  const vs = featureProps.map((p) => p[view]).filter((v) => v != null);
  return { min: Math.min(...vs), max: Math.max(...vs), log: VIEWS[view].log };
}
function fillFor(p, view) {
  if (view === "quadrant") return quadColor(p.quadrant);
  const v = p[view];
  if (v == null) return NA_COLOR;  // NRI-absent etc. — distinct gray, never a fake viridis value
  const d = domains[view] || computeDomain(view);
  const t = d.log
    ? (Math.log(v + 1) - Math.log(d.min + 1)) / ((Math.log(d.max + 1) - Math.log(d.min + 1)) || 1)
    : (v - d.min) / ((d.max - d.min) || 1);
  return viridis(t);
}
function tooltipFor(p, view) {
  const cty = countyName(p.county_fips);
  const l1 = `<strong>${p.zip}</strong>${cty ? ` · ${cty} County` : ""}`;
  let l2;
  if (view === "quadrant") {
    l2 = p.quadrant && QUAD[p.quadrant] ? QUAD[p.quadrant].tip : "Not in FEMA NRI — no quadrant";
  } else {
    const m = VIEWS[view], v = p[view];
    l2 = v == null ? `${m.label}: no data`
      : `${m.label}: ${m.fmt(v)} — <span style="color:#9fb0bd">${m.gloss}</span>`;
  }
  return `${l1}<br/>${l2}`;
}
function renderLegend(view) {
  const el = document.getElementById("map-legend");
  if (view === "quadrant") {
    el.innerHTML =
      [["priority","Priority"],["monitor","Monitor"],["harden","Harden"],["low_priority","Low priority"]]
        .map(([k,l]) => `<span><span class="sw" style="background:${QUAD[k].color}"></span>${l}</span>`).join("")
      + `<span><span class="sw" style="background:${NA_COLOR}"></span>No NRI</span>`;
    return;
  }
  const d = domains[view] || computeDomain(view), m = VIEWS[view];
  const grad = "linear-gradient(to right," + VIRIDIS.map((c) => `rgb(${c[0]},${c[1]},${c[2]})`).join(",") + ")";
  el.innerHTML =
    `<div style="width:100%"><div style="height:10px;border-radius:4px;background:${grad}"></div>`
    + `<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-top:3px">`
    + `<span>${m.fmt(d.min)}</span><span>${m.fmt(d.max)}</span></div>`
    + `<span style="font-size:11px;color:var(--muted)"><span class="sw" style="background:${NA_COLOR}"></span>no data</span></div>`;
}
function buildViewControl() {
  const el = document.getElementById("map-views");
  el.innerHTML = VIEW_ORDER.map((v) =>
    `<button data-v="${v}" class="${v === currentView ? "active" : ""}">${VIEWS[v].label}</button>`).join("");
  el.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => applyView(b.dataset.v)));
}
function applyView(view) {
  currentView = view;
  if (view !== "quadrant") domains[view] = computeDomain(view);
  Object.values(zipLayer).forEach((lyr) => {
    const p = lyr.feature.properties, c = fillFor(p, view);
    lyr.setStyle({ fillColor: c, color: c });
    lyr.bindTooltip(tooltipFor(p, view), { sticky: true });
  });
  if (selected) selected.setStyle({ weight: 3, color: "#fff" });  // keep selection highlight on top
  buildViewControl();
  renderLegend(view);
}

// --- basemaps ---
const esri = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 18, attribution: "Imagery © Esri" });
const positron = L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  { maxZoom: 19, subdomains: "abcd", attribution: "© OpenStreetMap, © CARTO" });

const map = L.map("map", { center: [37.3, -119.3], zoom: 6, layers: [esri] });
L.control.layers({ "Satellite (Esri)": esri, "Light (Positron)": positron }, null,
  { position: "topright", collapsed: false }).addTo(map);

let selected = null;

function panelFor(d) {
  const q = d.matrix.quadrant;
  const head = q && QUAD[q]
    ? `<span style="color:${QUAD[q].color};font-weight:700">${QUAD[q].label}</span> — ${QUAD[q].read}`
    : `<span class="na-note">Not in the FEMA NRI residential set — no quadrant; the fire-weather trend still applies.</span>`;
  const fwi = d.trends.metrics.fwi;
  const fuel = d.fuel.available ? `${(d.fuel.burnable_frac*100).toFixed(0)}% burnable, ${(d.fuel.dominant_class||"").replace(/_/g," ")}` : "—";
  return `
    <div class="ex-head"><strong>ZIP ${d.zip}</strong><br/>${head}</div>
    <div class="axis"><span class="k">Hazard — mean FWI</span><span class="v">${fmtNum(d.matrix.hazard.fwi_level,1)}</span></div>
    <div class="axis"><span class="k">Exposure — annual building loss</span><span class="v">${fmtMoney(d.matrix.exposure.wfir_ealt)}</span></div>
    <div class="axis"><span class="k">FWI trend (baseline→recent)</span><span class="v">${fmtNum(fwi.baseline,1)} → ${fmtNum(fwi.recent,1)} (${fmtPct(fwi.pct_change)})</span></div>
    <div class="axis"><span class="k">Fuel</span><span class="v">${fuel}</span></div>
    <div class="ex-cta"><a href="/?zip=${d.zip}">Open full assessment ↗</a></div>`;
}

async function loadPanel(zip) {
  const el = document.getElementById("ex-panel");
  el.innerHTML = `<div class="hint">Loading ${zip}…</div>`;
  try {
    const r = await fetch("/api/place/" + zip);
    if (!r.ok) { el.innerHTML = `<div class="na-note">No data for ${zip}.</div>`; return; }
    el.innerHTML = panelFor(await r.json());
  } catch (e) { el.innerHTML = `<div class="na-note">Network error.</div>`; }
}

// --- overlay: polygons, fallback to centroids ---
let geoLayer = null;

function selectZip(zip) {
  const lyr = zipLayer[zip];
  if (lyr && geoLayer) {
    if (selected) {  // restore the previous selection to the CURRENT view's color, not quadrant
      const c = fillFor(selected.feature.properties, currentView);
      selected.setStyle({ weight: 1, color: c });
    }
    lyr.setStyle({ weight: 3, color: "#fff" }); lyr.bringToFront(); selected = lyr;
    map.fitBounds(lyr.getBounds(), { maxZoom: 12 });
  } else if (zipLatLng[zip]) {
    map.setView(zipLatLng[zip], 11);
  }
  loadPanel(zip);
}

function addPolygons(fc) {
  geoLayer = L.geoJSON(fc, {
    style: (f) => ({ fillColor: quadColor(f.properties.quadrant), fillOpacity: 0.6,
      color: quadColor(f.properties.quadrant), weight: 1, opacity: 0.9 }),
    onEachFeature: (f, lyr) => {
      const p = f.properties;
      featureProps.push(p);
      zipLayer[p.zip] = lyr;
      lyr.on("click", () => selectZip(p.zip));
    },
  }).addTo(map);
  applyView(currentView);  // sets fill + tooltips + view selector + legend
}

function addCentroids(points) {
  points.forEach((p) => {
    zipLatLng[p.zip] = [p.lat, p.lon];
    L.circleMarker([p.lat, p.lon], { radius: 5, fillColor: quadColor(p.quadrant),
      fillOpacity: 0.85, color: "#0b0f12", weight: 1 })
      .bindTooltip(tipHtml(p)).on("click", () => loadPanel(p.zip)).addTo(map);
  });
  renderLegend("quadrant");  // fallback path stays categorical (no per-ZIP viridis values)
}

// --- search: ZIP -> select+zoom; county -> fit bounds + list; else message ---
async function doSearch(q) {
  const el = document.getElementById("ex-panel");
  el.innerHTML = `<div class="hint">Searching “${q}”…</div>`;
  let res;
  try { res = await (await fetch("/api/search?q=" + encodeURIComponent(q))).json(); }
  catch (e) { el.innerHTML = `<div class="na-note">Search error.</div>`; return; }

  if (res.type === "zip" && res.resolved) { selectZip(res.zip); return; }
  if (res.type === "county") {
    const pts = res.zips.filter((z) => z.lat != null);
    if (pts.length) map.fitBounds(pts.map((z) => [z.lat, z.lon]), { maxZoom: 11 });
    const chips = res.zips.slice(0, 60).map((z) =>
      `<button class="chip" data-zip="${z.zip}">${z.zip}</button>`).join(" ");
    el.innerHTML = `<div class="ex-head"><strong>${res.county} County</strong> — ${res.count} ZIPs</div>
      <div class="ai-note">${res.note}</div><div style="margin-top:10px">${chips}</div>`;
    el.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => selectZip(c.dataset.zip)));
    return;
  }
  if (res.type === "ambiguous") {
    const chips = res.candidates.map((c) =>
      `<button class="chip" data-c="${c}">${c}</button>`).join(" ");
    el.innerHTML = `<div class="hint">${res.message}</div><div style="margin-top:8px">${chips}</div>`;
    el.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => doSearch(c.dataset.c)));
    return;
  }
  el.innerHTML = `<div class="na-note">${res.message || "Couldn't resolve that."}</div>`;
}

(async function init() {
  document.getElementById("ex-search").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = document.getElementById("ex-q").value.trim();
    if (q) doSearch(q);
  });
  document.getElementById("ex-panel").innerHTML = `<div class="hint">Loading the map…</div>`;
  try {
    const r = await fetch("/api/geo/zcta");
    if (r.ok) { addPolygons(await r.json()); }
    else {
      const c = await fetch("/api/geo/centroids");
      addCentroids((await c.json()).points);
    }
  } catch (e) {
    const c = await fetch("/api/geo/centroids");
    addCentroids((await c.json()).points);
  }
  document.getElementById("ex-panel").innerHTML = `<div class="hint">Click a ZIP on the map to read its assessment.</div>`;
  loadPanel("95404");
})();
