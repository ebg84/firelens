"use strict";

const BASIS = {
  ingested:    { label: "Ingested — canonical index", color: "#3b82c4" },
  derived:     { label: "Derived by FireLens (count over the ingested FWI)", color: "#e08a2e" },
  cited:       { label: "Cited — published figures", color: "#3fa564" },
  constructed: { label: "FireLens construction", color: "#d64545" },
};
const esc = (s) => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

(async function () {
  let d;
  try { d = await (await fetch("/api/methodology")).json(); }
  catch (e) { document.getElementById("methods-list").innerHTML = "<p>Couldn't load methods.</p>"; return; }
  document.getElementById("framing").innerHTML = `<p>${esc(d.framing)}</p>`;
  document.getElementById("methods-list").innerHTML = d.metrics.map((m) => {
    const b = BASIS[m.basis] || { label: m.basis, color: "#5a6b78" };
    return `<article class="method-card">
      <div class="method-head">
        <h3>${esc(m.name)}</h3>
        <span class="basis" style="background:${b.color}">${esc(b.label)}</span>
      </div>
      <p class="method-meaning">${esc(m.meaning)}</p>
      <p class="method-deriv">${esc(m.derivation)}</p>
      <div class="method-meta">
        <span><strong>Source:</strong> ${esc(m.source)}</span>
        <span><strong>Grain:</strong> ${esc(m.grain)}</span>
        <span><strong>Range:</strong> ${esc(m.time_range)}</span>
      </div>
    </article>`;
  }).join("");
})();
