"use strict";

const QUAD = {
  priority: { color:"#d64545", label:"Priority",
    read:"hazard and exposure both above the statewide median — manage fuel <em>and</em> harden structures." },
  monitor: { color:"#e08a2e", label:"Monitor",
    read:"hazard elevated, little built to lose — monitor and manage fuel." },
  harden: { color:"#3b82c4", label:"Harden",
    read:"hazard below median but exposure high — harden structures; people, not weather, drive the risk." },
  low_priority: { color:"#3fa564", label:"Low priority",
    read:"hazard and exposure both below the statewide median — lower relative priority." },
};
const NA_COLOR = "#5a6b78";
const quadColor = (q) => (QUAD[q] && QUAD[q].color) || NA_COLOR;
const fmtMoney = (v) => v == null ? "—" : "$" + Math.round(v).toLocaleString();
const fmtNum = (v, d=1) => v == null ? "—" : Number(v).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPct = (v) => v == null ? "—" : (v>=0?"+":"") + (v*100).toFixed(1) + "%";

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
function addPolygons(fc) {
  const layer = L.geoJSON(fc, {
    style: (f) => ({ fillColor: quadColor(f.properties.quadrant), fillOpacity: 0.55,
      color: quadColor(f.properties.quadrant), weight: 1, opacity: 0.9 }),
    onEachFeature: (f, lyr) => {
      const q = f.properties.quadrant;
      lyr.bindTooltip(`${f.properties.zip} · ${q ? (QUAD[q]||{}).label || q : "no NRI"}`, { sticky: true });
      lyr.on("click", () => {
        if (selected) layer.resetStyle(selected);
        lyr.setStyle({ weight: 3, color: "#fff" }); lyr.bringToFront(); selected = lyr;
        loadPanel(f.properties.zip);
      });
    },
  }).addTo(map);
}

function addCentroids(points) {
  points.forEach((p) => {
    L.circleMarker([p.lat, p.lon], { radius: 5, fillColor: quadColor(p.quadrant),
      fillOpacity: 0.85, color: "#0b0f12", weight: 1 })
      .bindTooltip(`${p.zip} · ${p.quadrant ? (QUAD[p.quadrant]||{}).label || p.quadrant : "no NRI"}`)
      .on("click", () => loadPanel(p.zip)).addTo(map);
  });
}

(async function init() {
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
