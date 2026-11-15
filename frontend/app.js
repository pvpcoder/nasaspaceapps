// FlameWatch dashboard. Polls the backend and updates the page.
const $ = (id) => document.getElementById(id);
const API = window.FLAMEWATCH_API || "";
const PSI_PER_ATM = 14.696;
const AREA_WORDS = { prevention: "Preventing fires", detection: "Detecting smoke", suppression: "Putting fires out" };
const AREA_COLORS = { prevention: "#2c5aa0", detection: "#b9741a", suppression: "#2f7d55" };
const LAMP_WORDS = { green: "Nominal", yellow: "Caution", red: "Warning" };

let lastKey = "";
let showAll = false;
let chart;
let state;

// The habitat is per browser (saved in localStorage), not shared on the server.
const HABITAT_KEY = "flamewatch.habitat";
const store = {
  get() { try { return localStorage.getItem(HABITAT_KEY); } catch { return null; } },
  set(v) { try { localStorage.setItem(HABITAT_KEY, v); } catch { /* storage unavailable */ } },
};
let habitatKey = store.get() || "moonbase";
let followLive = true;   // switch to the sensor box automatically when it sends data

// Query string every request carries, so the server knows which habitat we mean.
const hp = () => `scenario=${encodeURIComponent(habitatKey)}&sensor=${followLive}`;
const selected = new Set();   // PSI IDs ticked for comparison (max 3)

async function api(path, opts) {
  try {
    const r = await fetch(API + path, opts);
    if (!r.ok) throw new Error(r.status);
    $("conn-banner").hidden = true;
    return await r.json();
  } catch (e) {
    $("conn-banner").hidden = false;
    throw e;
  }
}

const fmt = (n, d = 1) => (n == null ? "–" : Number(n).toFixed(d));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// ---------- fuel-shape drawings + NASA photo thumbnails ----------
// A small drawing of what burned, used when NASA has no photo of the experiment.
const SHAPE_SVG = {
  "sheet": '<rect x="9" y="8" width="22" height="24" rx="1.5"/><path d="M9 14h22M9 20h22M9 26h22" class="soft"/><path d="M9 32c2-4 5-4 6 0" class="flame"/>',
  "droplet": '<path d="M4 20h10M26 20h10" class="soft"/><circle cx="20" cy="20" r="5"/><circle cx="20" cy="20" r="11" class="flame dash"/>',
  "sphere-burner": '<path d="M20 26v10" /><circle cx="20" cy="18" r="7"/><circle cx="20" cy="18" r="13" class="flame dash"/>',
  "flat-burner": '<path d="M20 26v10"/><ellipse cx="20" cy="24" rx="11" ry="3"/><path d="M10 20c3-9 17-9 20 0" class="flame dash"/>',
  "jet": '<path d="M17 36V24h6v12"/><path d="M20 23c-6-4-6-12 0-18c6 6 6 14 0 18z" class="flame"/>',
  "smoke": '<path d="M12 34c-4-5 4-8 0-13s4-8 0-13M20 34c-4-5 4-8 0-13s4-8 0-13M28 34c-4-5 4-8 0-13s4-8 0-13" class="soft"/>',
  "dust": '<g class="dots"><circle cx="11" cy="12" r="1.6"/><circle cx="24" cy="9" r="1.2"/><circle cx="30" cy="17" r="1.8"/><circle cx="16" cy="21" r="1.3"/><circle cx="26" cy="27" r="1.5"/><circle cx="12" cy="30" r="1.8"/><circle cx="20" cy="32" r="1.1"/><circle cx="32" cy="31" r="1.2"/></g>',
  "model": '<rect x="8" y="8" width="24" height="24" rx="1.5"/><path d="M16 8v24M24 8v24M8 16h24M8 24h24" class="soft"/><path d="M10 30c6-2 8-12 20-18" class="flame"/>',
};
const SHAPE_WORDS = { "sheet": "Solid sample (fabric or plastic)", "droplet": "Fuel droplet", "sphere-burner": "Spherical gas burner",
  "flat-burner": "Flat gas burner", "jet": "Gas jet flame", "smoke": "Smoke from heated materials", "dust": "Dust (no fire)", "model": "Computer model" };

function shapeIcon(shape, size = 40) {
  return `<svg class="shape" width="${size}" height="${size}" viewBox="0 0 40 40" role="img" aria-label="${esc(SHAPE_WORDS[shape] || "Experiment")}">${SHAPE_SVG[shape] || SHAPE_SVG.model}</svg>`;
}

// NASA's photo when PSI has one; the shape drawing otherwise (or if the photo fails).
function thumb(x, size = 40) {
  if (!x.photo) return `<span class="thumb" style="--s:${size}px">${shapeIcon(x.shape, size)}</span>`;
  return `<span class="thumb photo" style="--s:${size}px" data-shape="${esc(x.shape)}"><img src="${API}/api/photo/${esc(x.id)}" alt="NASA image of ${esc(x.acronym || x.id)}" loading="lazy" onerror="this.parentNode.classList.remove('photo');this.replaceWith(document.createRange().createContextualFragment(shapeIcon(this.parentNode.dataset.shape, ${size})))"></span>`;
}

// ---------- habitat panel ----------
async function refreshState() {
  try {
    state = await api(`/api/state?${hp()}`);
  } catch (e) {
    // A saved habitat that no longer exists: fall back to the default.
    if (habitatKey !== "moonbase") { habitatKey = "moonbase"; store.set(habitatKey); }
    throw e;
  }
  const sel = $("scenario");
  if (!sel.options.length) {
    sel.add(new Option("Sensor box (not connected)", "live"));
    for (const [k, v] of Object.entries(state.scenarios)) sel.add(new Option(v.label, k));
  }
  // The sensor option turns on by itself as soon as live readings arrive.
  sel.options[0].textContent = state.live ? "Sensor box (live)" : "Sensor box (not connected)";
  sel.options[0].disabled = !state.live;
  if (document.activeElement !== sel) sel.value = state.source === "sensor" ? "live" : habitatKey;

  const usingSensor = state.source === "sensor";
  $("source").textContent = usingSensor ? "Live from sensor box" : state.live ? "Preset habitat (sensor box connected)" : "Preset habitat";
  $("source").classList.toggle("live", usingSensor);

  $("r-o2").textContent = fmt(state.o2_pct);
  $("r-p").textContent = fmt(state.pressure_psi);
  $("r-smoke").textContent = state.smoke == null ? "–" : Math.round(state.smoke);
  $("r-temp").textContent = fmt(state.temp_c);

  // Sensor-box extras: shown while the box is sending readings.
  const box = state.box;
  $("box-status").hidden = !box;
  let alert = "";
  if (box) {
    $("r-crew").textContent = box.crew == null ? "–" : box.crew ? "Yes" : "No";
    $("r-hatch").textContent = box.hatch_closed == null ? "–" : box.hatch_closed ? "Closed" : "Open";
    $("r-vent").textContent = box.vent === "closed" ? "Closed" : "Open";
    if (box.mode === "suppressing") {
      alert = "Suppression active: CO₂ flood simulated, vent closed. FLEX and FLEX-2 studied putting out flames by diluting the air with CO₂ and helium.";
    } else if (box.level === "red") {
      alert = box.crew ? "Crew detected in the module: evacuate, then close the hatch."
        : box.hatch_closed ? "Module isolated: ready to suppress (press the switch on the box)."
        : "Module empty: close the hatch, then suppress.";
    }
  }
  $("box-alert").textContent = alert;
  $("box-alert").hidden = !alert;

  const risk = state.risk;
  $("lamp").className = `lamp ${risk.level}`;
  $("lamp-word").textContent = LAMP_WORDS[risk.level];
  $("risk-score").textContent = risk.score;
  $("p-atm").textContent = risk.parts.atmosphere;
  $("p-smoke").textContent = risk.parts.smoke;
  $("p-heat").textContent = risk.parts.heat;
  $("p-flame").textContent = risk.parts.flame;
  $("risk-explain").textContent = risk.explain;
  if (!$("formula-list").children.length) {
    const f = risk.formula;
    $("formula-list").innerHTML = [["Oxygen", f.oxygen], ["Smoke", f.smoke], ["Heat", f.heat],
      ["Flame", f.flame], ["Levels", f.levels]].map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
    $("formula-why").textContent = f.why_concentration;
  }

  // Saffire-VI burned cabin materials at 29–31% O2, outside the PSI data.
  $("saffire-note").hidden = state.o2_pct < 28;

  const key = `${Math.round(state.o2_pct)}|${state.pressure_psi.toFixed(1)}|${state.source}|${$("area").value}|${showAll}`;
  if (key !== lastKey) {
    const habitatChanged = key.split("|").slice(0, 3).join() !== lastKey.split("|").slice(0, 3).join();
    lastKey = key;
    markHabitat();
    await refreshRank();
    if (habitatChanged || !mapData) await refreshMap();
    // Keep an open comparison in step with the habitat.
    if (habitatChanged && !$("compare").hidden && selected.size >= 2) await showCompare(false);
  }
}

$("scenario").addEventListener("change", (e) => {
  if (e.target.value === "live") {
    followLive = true;
  } else {
    habitatKey = e.target.value;
    store.set(habitatKey);
    // Picking a preset while the sensor is live means "stop following the sensor".
    if (state && state.live) followLive = false;
  }
  e.target.blur();
  refreshState();
});
$("area").addEventListener("change", () => { lastKey = ""; refreshState(); });
$("show-all").addEventListener("click", () => {
  showAll = !showAll;
  $("show-all").textContent = showAll ? "Show fewer" : "Show all experiments";
  lastKey = "";
  refreshState();
});

// ---------- the finding (headline) ----------
function writeFinding(results) {
  const o2 = Math.round(state.o2_pct);
  const psi = fmt(state.pressure_psi);
  const near = results.reduce((n, r) => n + r.tests_near, 0);
  const solidNear = results.filter((r) => r.fuel_kind === "solid").reduce((n, r) => n + r.tests_near, 0);
  let text;
  const runs = (n) => `${n} test run${n === 1 ? "" : "s"}`;
  if (near === 0) {
    text = `In NASA’s public PSI data, no space station fire test comes close to ${o2}% oxygen at ${psi} psi.`;
  } else if (solidNear === 0) {
    text = `In NASA’s public PSI data, ${runs(near)} come close to ${o2}% oxygen at ${psi} psi, and none of them burned the fabrics and plastics a cabin is made of.`;
  } else {
    text = `In NASA’s public PSI data, ${runs(near)} come close to ${o2}% oxygen at ${psi} psi, ${solidNear} of them burning real cabin materials.`;
  }
  $("finding").textContent = text;
}

// ---------- experiments table ----------
async function refreshRank() {
  const d = await api(`/api/rank?area=${$("area").value}&limit=30&${hp()}`);
  writeFinding(d.results);
  $("near-rule").textContent = `“Runs near you” counts test runs ${d.near_rule} of this habitat. ${d.near_note}`;
  $("near-head").title = `Counts test runs ${d.near_rule} of this habitat`;
  const rows = showAll ? d.results : d.results.slice(0, 8);
  $("rank-body").innerHTML = rows.map((r, i) => `
    <tr class="exp-row" tabindex="0" aria-expanded="false" data-i="${i}">
      <td class="pick"><input type="checkbox" data-id="${esc(r.id)}" aria-label="Compare ${esc(r.id)}"
        ${selected.has(r.id) ? "checked" : ""} ${!selected.has(r.id) && selected.size >= 3 ? "disabled" : ""}></td>
      <td class="exp-cell">
        ${thumb(r, 44)}
        <span class="exp-text">
          <a class="exp-id" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.id)}</a>
          <span class="exp-name">${esc(r.acronym || shortTitle(r.title))}</span>
          <span class="exp-full">${esc(shortTitle(r.title))}</span>
        </span>
      </td>
      <td class="covers">${r.areas.map((a) => `<span class="c-${a}">${AREA_WORDS[a]}</span>`).join("")}</td>
      <td class="num ${r.tests_near ? "" : "near-zero"}">${r.tests_near} of ${r.tests_total}</td>
      <td class="num">${o2Range(r.o2_range)}</td>
    </tr>
    <tr class="detail" hidden>
      <td colspan="5">
        <p class="why">${esc(capital(r.why))}.</p>
        <p>${esc(r.objectives)}${r.objectives.length >= 400 ? "…" : ""}</p>
        ${r.doi ? `<p>DOI <a href="https://doi.org/${esc(r.doi)}" target="_blank" rel="noopener">${esc(r.doi)}</a></p>` : ""}
      </td>
    </tr>`).join("");
  $("show-all").hidden = d.results.length <= 8;
  $("dl-near").href = `${API}/api/export?scope=near&${hp()}`;
}

const o2Range = (r) => !r ? "not recorded"
  : Math.round(r[0]) === Math.round(r[1]) ? `${fmt(r[0], 0)}%` : `${fmt(r[0], 0)}–${fmt(r[1], 0)}%`;
const shortTitle = (t) => (t || "").replace(/^Advanced Combustion via Microgravity Experiments\s*[-/]?\s*/i, "ACME: ");
const capital = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");

$("rank-body").addEventListener("click", (e) => {
  if (e.target.closest("a, .pick")) return;
  toggleRow(e.target.closest(".exp-row"));
});
$("rank-body").addEventListener("keydown", (e) => {
  if (e.target.matches("input")) return;
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleRow(e.target.closest(".exp-row")); }
});
function toggleRow(row) {
  if (!row) return;
  const open = row.getAttribute("aria-expanded") !== "true";
  row.setAttribute("aria-expanded", open);
  row.nextElementSibling.hidden = !open;
}

// ---------- compare ----------
$("rank-body").addEventListener("change", (e) => {
  const box = e.target.closest("input[data-id]");
  if (!box) return;
  setSelected(box.dataset.id, box.checked);
});

// Tick or untick an experiment for comparison from anywhere (table or map).
function setSelected(id, on) {
  if (on && selected.size >= 3 && !selected.has(id)) return false;
  on ? selected.add(id) : selected.delete(id);
  document.querySelectorAll("#rank-body input[data-id]").forEach((b) => {
    b.checked = selected.has(b.dataset.id);
    b.disabled = !b.checked && selected.size >= 3;
  });
  updateCompareButton();
  renderMapSelection();
  return true;
}

function updateCompareButton() {
  const n = selected.size;
  $("compare-btn").disabled = n < 2;
  $("compare-btn").textContent = n < 2 ? "Tick up to 3 to compare" : `Compare ${n} experiments`;
}

$("compare-btn").addEventListener("click", () => showCompare(true));
$("compare-close").addEventListener("click", () => { $("compare").hidden = true; });

const range = (r, unit, d = 0) => {
  if (!r) return "Not recorded";
  const sep = unit === "%" ? "" : " ";
  return fmt(r[0], d) === fmt(r[1], d) ? `${fmt(r[0], d)}${sep}${unit}` : `${fmt(r[0], d)}–${fmt(r[1], d)}${sep}${unit}`;
};
const list = (xs) => xs && xs.length ? `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "None recorded";

async function showCompare(scroll = true) {
  const d = await api(`/api/compare?ids=${[...selected].join(",")}&${hp()}`);
  const inv = d.investigations;
  const rows = [
    ["Covers", (x) => x.areas.map((a) => AREA_WORDS[a]).join(", ")],
    ["Hardware", (x) => esc(x.hardware || "Not listed")],
    ["What burned", (x) => esc(x.fuel || "Not listed")],
    ["Samples in the data", (x) => list(x.samples)],
    ["What was measured", (x) => esc(x.measured || "Not listed")],
    ["Oxygen tested", (x) => range(x.o2_range, "%")],
    ["Pressure tested", (x) => range(x.pressure_range, "atm", 2)],
    ["Airflow", (x) => x.airflow_range ? range(x.airflow_range, "cm/s") : esc(x.airflow_note || "Not recorded")],
    ["Suppressants and diluents", (x) => esc(x.agents || "None listed")],
    ["Changed between runs", (x) => list(x.varied)],
    ["Held the same", (x) => list(x.fixed)],
    ["Test runs", (x) => `${x.test_rows}`],
    ["Runs near your habitat", (x) => `${x.tests_near}`],
    ["Data", (x) => `<a href="${API}/api/export?scope=ids&ids=${esc(x.id)}&${hp()}">Download all runs (CSV)</a>`],
  ];
  $("compare-table").innerHTML = `
    <thead><tr><th></th>${inv.map((x) => `<th>${thumb(x, 64)}<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.id)}</a> ${esc(x.acronym || "")}<small>${esc(shortTitle(x.title))}</small></th>`).join("")}</tr></thead>
    <tbody>${rows.map(([label, f]) => {
      const cells = inv.map(f);
      if (label === "Held the same" && cells.every((c) => c === "None recorded")) return "";
      const same = inv.length > 1 && cells.every((c) => c === cells[0]) && !/Not (listed|recorded)|None|units unclear/.test(cells[0]);
      return `<tr class="${same ? "same" : ""}"><th scope="row">${label}</th>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`;
    }).join("")}</tbody>`;
  $("compare-summary").innerHTML = summarizeComparison(inv).map((t) => `<li>${t}</li>`).join("");
  $("compare").hidden = false;
  if (scroll) $("compare").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

// Plain-language similarities and differences.
function summarizeComparison(inv) {
  const out = [];
  const names = (xs) => xs.map((x) => x.acronym || x.id).join(" and ");

  const hw = new Set(inv.map((x) => x.hardware));
  out.push(hw.size === 1
    ? `<b>Same hardware.</b> All ran on: ${esc(inv[0].hardware)}. Their results are directly comparable.`
    : `<b>Different hardware.</b> ${inv.map((x) => `${esc(x.acronym || x.id)}: ${esc(x.hardware)}`).join("; ")}.`);

  const shared = Object.keys(AREA_WORDS).filter((a) => inv.every((x) => x.areas.includes(a)));
  out.push(shared.length
    ? `<b>Shared focus:</b> ${shared.map((a) => AREA_WORDS[a].toLowerCase()).join(", ")}.`
    : `<b>Different focus.</b> ${inv.map((x) => `${esc(x.acronym || x.id)} covers ${x.areas.map((a) => AREA_WORDS[a].toLowerCase()).join(" and ")}`).join("; ")}.`);

  const withO2 = inv.filter((x) => x.o2_range);
  if (withO2.length === inv.length) {
    const lo = Math.max(...inv.map((x) => x.o2_range[0])), hi = Math.min(...inv.map((x) => x.o2_range[1]));
    out.push(lo <= hi
      ? (fmt(lo, 0) === fmt(hi, 0)
        ? `<b>Oxygen overlap:</b> all tested at about ${fmt(lo, 0)}% oxygen, so results can be compared there.`
        : `<b>Oxygen overlap:</b> all tested between ${fmt(lo, 0)}% and ${fmt(hi, 0)}% oxygen, so results can be compared in that band.`)
      : `<b>No oxygen overlap.</b> They tested different oxygen levels, so they can't be compared directly.`);
  } else if (withO2.length) {
    out.push(`<b>Oxygen:</b> only ${names(withO2)} recorded oxygen levels.`);
  }

  const near = inv.filter((x) => x.tests_near > 0);
  out.push(near.length === 0
    ? `<b>None of these</b> has test runs near your habitat’s conditions.`
    : near.length === inv.length
      ? `<b>All of these</b> have test runs near your habitat’s conditions.`
      : `<b>Only ${names(near)}</b> ${near.length > 1 ? "have" : "has"} test runs near your habitat’s conditions.`);
  return out;
}

// ---------- connection map ----------
// One row per set of hardware. Cards are ordered so linked experiments sit side by side;
// ground studies sit in the row of the flight experiment they studied.
const LANES = [
  { fam: "acme",    ids: ["PSI-20", "PSI-10", "PSI-159", "PSI-21", "PSI-23", "PSI-22"], ground: [] },
  { fam: "duct",    ids: ["PSI-106", "PSI-107", "PSI-26", "PSI-25"], ground: ["PSI-60", "PSI-62"] },
  { fam: "saffire", ids: ["PSI-98", "PSI-99", "PSI-100"], ground: [] },
  { fam: "mdca",    ids: ["PSI-39", "PSI-69", "PSI-68"], ground: ["PSI-117", "PSI-142"] },
  { fam: "smoke",   ids: ["PSI-101", "PSI-102", "PSI-47"], ground: ["PSI-115"] },
];
const SHORT = { "PSI-60": "SPICE soot study", "PSI-62": "BASS flame model", "PSI-115": "SAME smoke model",
  "PSI-117": "FLEX 3-D model", "PSI-142": "FLEX counterflow" };
const ACR = { "PSI-10": "Flame Design", "PSI-20": "ACME BRE", "PSI-21": "CLD Flame", "PSI-22": "E-FIELD",
  "PSI-23": "s-Flame", "PSI-159": "CFI-G", "PSI-47": "DAFT" };
const LINK_WORDS = { series: "Flown again", instrument: "Instrument reused", emulates: "Imitates",
  reanalysis: "Studied on the ground", related: "Related" };
let mapData = null, mapPinned = null, mapHover = null;

const nodeName = (n) => ACR[n.id] || n.acronym || SHORT[n.id] || n.id;
const linkKey = (a, b) => [a, b].sort().join("|");

async function refreshMap() {
  mapData = await api(`/api/map?${hp()}`);
  const byId = Object.fromEntries(mapData.nodes.map((n) => [n.id, n]));
  const links = Object.fromEntries(mapData.links.map((l) => [linkKey(l.from, l.to), l]));
  // A connector between two neighbouring cards, if they're linked.
  const conn = (a, b) => {
    const l = links[linkKey(a, b)];
    if (!l) return '<span class="gap"></span>';
    const dir = l.kind === "series" || l.kind === "instrument" ? (l.from === a ? "arrow-r" : "arrow-l") : "";
    return `<span class="conn k-${l.kind} ${dir}" data-a="${a}" data-b="${b}" title="${esc(l.label)}"></span>`;
  };
  const card = (id, ground) => {
    const n = byId[id];
    if (!n) return "";
    return `<button type="button" class="card ${ground ? "ground" : ""} ${n.tests_near ? "near" : ""}" data-id="${esc(id)}"
      aria-label="${esc(nodeName(n))}, ${esc(id)}">${thumb(n, 30)}
      <span class="n-text"><span class="n-name">${esc(nodeName(n))}</span>
      <span class="n-meta">${ground ? "Ground study" : n.tests_near ? `<b>${n.tests_near} runs near</b>` : esc(id)}</span></span></button>`;
  };
  const row = (ids, ground) => ids.map((id, k) => (k ? conn(ids[k - 1], id) : "") + card(id, ground)).join("");
  $("map-lanes").innerHTML = LANES.map((lane) => {
    const f = mapData.families.find((x) => x.key === lane.fam) || {};
    return `<div class="lane" data-fam="${lane.fam}">
      <div><p class="lane-name">${esc(f.label || "")}</p><p class="lane-where">${esc(f.where || "")}</p></div>
      <div class="lane-cards">
        <div class="lane-row">${row(lane.ids)}</div>
        ${lane.ground.length ? `<div class="lane-row ground-row"><span class="ground-tag">Studied on the ground</span>${row(lane.ground, true)}</div>` : ""}
      </div>
    </div>`;
  }).join("");
  renderMapSelection();
  updateMap();
}

// Focus = the pinned experiment, or the one under the pointer.
const mapFocus = () => mapPinned || mapHover;

function updateMap() {
  const id = mapFocus(), wrap = $("map-wrap");
  wrap.classList.toggle("focused", !!id);
  const mine = id ? mapData.links.filter((l) => l.from === id || l.to === id) : [];
  const lit = new Set([id, ...mine.flatMap((l) => [l.from, l.to])]);
  wrap.querySelectorAll(".card").forEach((c) => {
    c.classList.toggle("lit", lit.has(c.dataset.id));
    c.classList.toggle("pinned", c.dataset.id === mapPinned);
  });
  wrap.querySelectorAll(".conn").forEach((c) => c.classList.toggle("lit", !!id && (c.dataset.a === id || c.dataset.b === id)));
  drawArcs(mine);
  id ? showNode(id) : showSummary();
}

// Draw the links that aren't already shown as neighbour connectors.
function drawArcs(mine) {
  const wrap = $("map-wrap"), svg = $("map-links"), box = wrap.getBoundingClientRect();
  svg.setAttribute("viewBox", `0 0 ${box.width} ${box.height}`);
  const neighbours = new Set([...wrap.querySelectorAll(".conn")].map((c) => linkKey(c.dataset.a, c.dataset.b)));
  const rect = (id) => {
    const el = wrap.querySelector(`.card[data-id="${id}"]`);
    if (!el || !el.offsetParent) return null;
    const r = el.getBoundingClientRect();
    return { l: r.left - box.left, r: r.right - box.left, t: r.top - box.top, b: r.bottom - box.top,
             cx: r.left - box.left + r.width / 2, cy: r.top - box.top + r.height / 2 };
  };
  svg.innerHTML = mine.filter((l) => !neighbours.has(linkKey(l.from, l.to))).map((l) => {
    const a = rect(l.from), b = rect(l.to);
    if (!a || !b) return "";
    let d;
    if (Math.abs(a.cy - b.cy) < 4) {          // same row: an arc over the cards
      const lift = Math.min(46, 18 + Math.abs(a.cx - b.cx) * 0.12);
      d = `M${a.cx},${a.t} C${a.cx},${a.t - lift} ${b.cx},${b.t - lift} ${b.cx},${b.t}`;
    } else {                                    // different rows: leave from the top/bottom edge
      const down = a.cy < b.cy, y1 = down ? a.b : a.t, y2 = down ? b.t : b.b, mid = (y1 + y2) / 2;
      d = `M${a.cx},${y1} C${a.cx},${mid} ${b.cx},${mid} ${b.cx},${y2}`;
    }
    return `<path class="arc k-${l.kind}" d="${d}"/>`;
  }).join("");
  svg.querySelectorAll(".arc").forEach((p) => p.style.setProperty("--len", p.getTotalLength()));
}

function renderMapSelection() {
  document.querySelectorAll("#map-lanes .card").forEach((c) => c.classList.toggle("picked", selected.has(c.dataset.id)));
  if (mapData) mapFocus() ? showNode(mapFocus()) : showSummary();
}

// Nothing selected: what matters for this habitat.
function showSummary() {
  const near = mapData.nodes.filter((n) => n.tests_near).sort((a, b) => b.tests_near - a.tests_near);
  $("map-detail").innerHTML = `<div class="md-summary">
    <h3>For this habitat</h3>
    ${near.length ? `<p>${near.length} of 24 experiments have test runs near these conditions:</p>
      <ul>${near.map((n) => `<li><button type="button" class="as-text" data-goto="${n.id}">${esc(nodeName(n))}</button>: ${n.tests_near} runs</li>`).join("")}</ul>`
      : "<p>No experiment has test runs near these conditions.</p>"}
    <p class="md-hint">Cards with a green edge have runs near your habitat. Hover any card to see how it connects; click to keep it selected.</p>
  </div>`;
}

function showNode(id) {
  const n = mapData.nodes.find((x) => x.id === id);
  if (!n) return;
  const fam = mapData.families.find((f) => f.key === n.family);
  const byId = Object.fromEntries(mapData.nodes.map((x) => [x.id, x]));
  const links = mapData.links.filter((l) => l.from === id || l.to === id);
  const picked = selected.has(id), full = !picked && selected.size >= 3;
  $("map-detail").innerHTML = `
    <div class="md-head">${thumb(n, 64)}
      <div><h3><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(nodeName(n))}</a></h3>
        <p class="md-title">${esc(shortTitle(n.title))}</p>
        <p class="md-meta">${esc(n.id)} · ${esc(fam ? fam.label : "")}</p></div></div>
    ${n.badge ? `<p class="md-badge">${esc(n.badge)}</p>` : ""}
    <p class="md-stat">${n.tests_total
      ? `<b>${n.tests_near}</b> of ${n.tests_total} test runs near this habitat`
      : "A ground study: no flight test runs of its own"}</p>
    ${links.length ? `<ul class="md-links">${links.map((l) => {
      const other = byId[l.from === id ? l.to : l.from];
      return `<li><span class="lk k-${l.kind}"></span><span><b>${LINK_WORDS[l.kind]}.</b> ${esc(l.label)}.
        <button type="button" data-goto="${esc(other.id)}">Go to ${esc(nodeName(other))}</button>
        <small>Source: ${esc(l.source)}</small></span></li>`;
    }).join("")}</ul>` : '<p class="md-hint">No recorded links to other experiments.</p>'}
    <div class="md-actions">
      <button type="button" class="btn" data-pick="${esc(id)}" ${full ? "disabled" : ""}>
        ${picked ? "Remove from comparison" : full ? "Comparison is full (3)" : "Add to comparison"}</button>
      ${selected.size >= 2 ? `<button type="button" class="btn-quiet as-link" data-open-compare>Compare ${selected.size}</button>` : ""}
    </div>
    ${mapPinned ? '<p class="md-hint">Selected. Click it again or press Esc to clear.</p>' : '<p class="md-hint">Click to keep this selected.</p>'}`;
}

// Hover previews; click pins. Keyboard: focus previews, Enter pins.
const lanes = $("map-lanes");
lanes.addEventListener("mouseover", (e) => { const c = e.target.closest(".card"); if (c && c.dataset.id !== mapHover) { mapHover = c.dataset.id; if (!mapPinned) updateMap(); } });
lanes.addEventListener("mouseleave", () => { mapHover = null; if (!mapPinned) updateMap(); });
lanes.addEventListener("focusin", (e) => { const c = e.target.closest(".card"); if (c) { mapHover = c.dataset.id; if (!mapPinned) updateMap(); } });
lanes.addEventListener("click", (e) => {
  const c = e.target.closest(".card");
  if (!c) return;
  mapPinned = mapPinned === c.dataset.id ? null : c.dataset.id;
  updateMap();
});
$("map-detail").addEventListener("click", (e) => {
  const go = e.target.closest("[data-goto]"), pick = e.target.closest("[data-pick]"), open = e.target.closest("[data-open-compare]");
  if (go) { mapPinned = go.dataset.goto; updateMap(); }
  if (pick) setSelected(pick.dataset.pick, !selected.has(pick.dataset.pick));
  if (open) showCompare(true);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && mapPinned) { mapPinned = null; updateMap(); } });
new ResizeObserver(() => mapData && drawArcs(mapFocus() ? mapData.links.filter((l) => l.from === mapFocus() || l.to === mapFocus()) : [])).observe($("map-wrap"));

// ---------- ask ----------
async function ask(q) {
  document.querySelector(".suggest")?.remove();
  addMsg(q, "user");
  const pending = addMsg("Reading the NASA data…", "bot");
  try {
    const d = await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, scenario: habitatKey, sensor: followLive }) });
    pending.innerHTML = renderMarkdown(d.answer);
  } catch {
    pending.textContent = "The server didn’t answer. Check it’s running, then ask again.";
  }
}
$("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("chat-input").value.trim();
  if (!q) return;
  $("chat-input").value = "";
  ask(q);
});
document.querySelectorAll(".q").forEach((b) => b.addEventListener("click", () => ask(b.textContent)));

// Small, safe Markdown renderer for AI answers: escapes HTML first,
// then handles **bold**, *italic*, `code` and "- " / "1. " lists.
function renderMarkdown(md) {
  const inline = (t) => esc(t)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\(?(PSI-\d+)\)?/g, (m, id) => m.replace(id, `<b class="psi">${id}</b>`));
  const out = [];
  let list = null;
  for (const raw of String(md || "").split(/\r?\n/)) {
    const line = raw.trim();
    const ul = line.match(/^[-*•]\s+(.*)/), ol = line.match(/^\d+[.)]\s+(.*)/);
    if (ul || ol) {
      const tag = ul ? "ul" : "ol";
      if (!list || list.tag !== tag) { if (list) out.push(`</${list.tag}>`); list = { tag }; out.push(`<${tag}>`); }
      out.push(`<li>${inline((ul || ol)[1])}</li>`);
      continue;
    }
    if (list) { out.push(`</${list.tag}>`); list = null; }
    if (!line) continue;
    const h = line.match(/^#{1,6}\s+(.*)/);
    out.push(h ? `<p><strong>${inline(h[1])}</strong></p>` : `<p>${inline(line)}</p>`);
  }
  if (list) out.push(`</${list.tag}>`);
  return out.join("");
}

function addMsg(text, who) {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  el.textContent = text;
  $("chat-log").appendChild(el);
  $("chat-log").scrollTop = 1e9;
  return el;
}

// ---------- gaps chart ----------
// Shaded band for the oxygen range planned for Moon bases (30–34%).
const moonBand = {
  id: "moonBand",
  beforeDatasetsDraw(c) {
    const { ctx, chartArea: a, scales: { x } } = c;
    const x0 = x.getPixelForValue(30), x1 = x.getPixelForValue(34);
    ctx.save();
    ctx.fillStyle = "rgba(240, 168, 28, 0.18)";
    ctx.fillRect(x0, a.top, x1 - x0, a.bottom - a.top);
    ctx.fillStyle = "#7a5205";
    ctx.font = "500 12px Barlow, sans-serif";
    ctx.fillText("Moon base oxygen", x1 + 6, a.top + 14);
    ctx.restore();
  },
};

async function buildChart() {
  const pts = await api("/api/points");
  const byArea = { prevention: [], detection: [], suppression: [] };
  for (const p of pts) {
    if ((p.note || "").includes("burner")) continue; // burner gas, not cabin air
    (byArea[p.area] || byArea.prevention).push({ x: p.o2, y: p.p, id: p.id, name: p.acronym });
  }
  Chart.defaults.font.family = "Barlow, sans-serif";
  Chart.defaults.color = "#56627a";
  chart = new Chart($("gap-chart"), {
    type: "scatter",
    data: {
      datasets: [
        ...Object.entries(byArea).filter(([, data]) => data.length).map(([area, data]) => ({
          label: AREA_WORDS[area], data, pointRadius: 3, pointHoverRadius: 5,
          order: area === "detection" ? 0 : 1,   // smoke tests sit at 21% / 1 atm; draw them on top
          backgroundColor: AREA_COLORS[area] + "b3", borderWidth: 0,
        })),
        { label: "Your habitat", data: [], pointRadius: 9, pointHoverRadius: 10,
          backgroundColor: "transparent", borderColor: "#cf2f3f", borderWidth: 3 },
      ],
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: { title: { display: true, text: "Oxygen in the air (%)" }, min: 0, max: 50, grid: { color: "#d8dee5" } },
        y: { title: { display: true, text: "Pressure (atmospheres)" }, min: 0, grace: "5%", grid: { color: "#d8dee5" } },
      },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, pointStyle: "circle", boxWidth: 8, color: "#15233f" } },
        tooltip: { callbacks: { label: (c) => c.raw.id ? `${c.raw.id} ${c.raw.name || ""}: ${c.raw.x}% O₂, ${c.raw.y} atm` : `Your habitat: ${c.raw.x}% O₂` } },
      },
    },
    plugins: [moonBand],
  });
}

function markHabitat() {
  if (!chart || !state) return;
  chart.data.datasets.at(-1).data = [{ x: state.o2_pct, y: +(state.pressure_psi / PSI_PER_ATM).toFixed(2) }];
  // Data sits below ~45% O2; only widen the axis for a spacesuit-style atmosphere.
  chart.options.scales.x.max = state.o2_pct > 45 ? 100 : 50;
  chart.update("none");
}

// ---------- start ----------
async function start() {
  try { await buildChart(); } catch { setTimeout(start, 3000); return; }
  const tick = () => refreshState().catch(() => {});
  tick();
  setInterval(tick, 1000);
}
start();
