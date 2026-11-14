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

// ---------- habitat panel ----------
async function refreshState() {
  state = await api("/api/state");
  const sel = $("scenario");
  if (!sel.options.length) {
    sel.add(new Option("Sensor box (live)", "live"));
    sel.options[0].disabled = true;
    for (const [k, v] of Object.entries(state.scenarios)) sel.add(new Option(v.label, k));
  }
  sel.value = state.live ? "live" : state.scenario;
  sel.disabled = state.live;

  $("source").textContent = state.live ? "Live from sensor box" : "Preset habitat";
  $("source").classList.toggle("live", state.live);

  $("r-o2").textContent = fmt(state.o2_pct);
  $("r-p").textContent = fmt(state.pressure_psi);
  $("r-smoke").textContent = state.smoke == null ? "–" : Math.round(state.smoke);
  $("r-temp").textContent = fmt(state.temp_c);

  const risk = state.risk;
  $("lamp").className = `lamp ${risk.level}`;
  $("lamp-word").textContent = LAMP_WORDS[risk.level];
  $("risk-score").textContent = risk.score;
  $("p-atm").textContent = risk.parts.atmosphere;
  $("p-smoke").textContent = risk.parts.smoke;
  $("p-heat").textContent = risk.parts.heat;
  $("p-flame").textContent = risk.parts.flame;

  const key = `${Math.round(state.o2_pct)}|${state.pressure_psi.toFixed(1)}|${$("area").value}|${showAll}`;
  if (key !== lastKey) {
    lastKey = key;
    markHabitat();
    await refreshRank();
  }
}

$("scenario").addEventListener("change", async (e) => {
  await api("/api/scenario", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: e.target.value }) });
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
  if (near === 0) {
    text = `At ${o2}% oxygen and ${psi} psi, no NASA fire test on the space station comes close to this habitat.`;
  } else if (solidNear === 0) {
    text = `At ${o2}% oxygen and ${psi} psi, NASA has ${near} test runs near these conditions, and none of them burned the fabrics and plastics a cabin is made of.`;
  } else {
    text = `At ${o2}% oxygen and ${psi} psi, NASA has ${near} test runs near these conditions, ${solidNear} of them burning real cabin materials.`;
  }
  $("finding").textContent = text;
}

// ---------- experiments table ----------
async function refreshRank() {
  const d = await api(`/api/rank?area=${$("area").value}&limit=30`);
  writeFinding(d.results);
  const rows = showAll ? d.results : d.results.slice(0, 8);
  $("rank-body").innerHTML = rows.map((r, i) => `
    <tr class="exp-row" tabindex="0" aria-expanded="false" data-i="${i}">
      <td class="pick"><input type="checkbox" data-id="${esc(r.id)}" aria-label="Compare ${esc(r.id)}"
        ${selected.has(r.id) ? "checked" : ""} ${!selected.has(r.id) && selected.size >= 3 ? "disabled" : ""}></td>
      <td>
        <a class="exp-id" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.id)}</a>
        <span class="exp-name">${esc(r.acronym || shortTitle(r.title))}</span>
        <span class="exp-full">${esc(shortTitle(r.title))}</span>
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
  $("dl-near").href = `${API}/api/export?scope=near`;
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
  box.checked ? selected.add(box.dataset.id) : selected.delete(box.dataset.id);
  document.querySelectorAll("#rank-body input[data-id]").forEach((b) => {
    b.disabled = !b.checked && selected.size >= 3;
  });
  updateCompareButton();
});

function updateCompareButton() {
  const n = selected.size;
  $("compare-btn").disabled = n < 2;
  $("compare-btn").textContent = n < 2 ? "Tick up to 3 to compare" : `Compare ${n} experiments`;
}

$("compare-btn").addEventListener("click", showCompare);
$("compare-close").addEventListener("click", () => { $("compare").hidden = true; });

const range = (r, unit, d = 0) => {
  if (!r) return "Not recorded";
  const sep = unit === "%" ? "" : " ";
  return fmt(r[0], d) === fmt(r[1], d) ? `${fmt(r[0], d)}${sep}${unit}` : `${fmt(r[0], d)}–${fmt(r[1], d)}${sep}${unit}`;
};
const list = (xs) => xs && xs.length ? `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "None recorded";

async function showCompare() {
  const d = await api(`/api/compare?ids=${[...selected].join(",")}`);
  const inv = d.investigations;
  const rows = [
    ["Covers", (x) => x.areas.map((a) => AREA_WORDS[a]).join(", ")],
    ["Hardware", (x) => esc(x.hardware || "Not listed")],
    ["What burned", (x) => esc(x.fuel || "Not listed")],
    ["Samples in the data", (x) => list(x.samples)],
    ["What was measured", (x) => esc(x.measured || "Not listed")],
    ["Oxygen tested", (x) => range(x.o2_range, "%")],
    ["Pressure tested", (x) => range(x.pressure_range, "atm", 2)],
    ["Airflow", (x) => range(x.airflow_range, "cm/s")],
    ["Changed between runs", (x) => list(x.varied)],
    ["Held the same", (x) => list(x.fixed)],
    ["Test runs", (x) => `${x.test_rows}`],
    ["Runs near your habitat", (x) => `${x.tests_near}`],
    ["Data", (x) => `<a href="${API}/api/export?scope=ids&ids=${esc(x.id)}">Download all runs (CSV)</a>`],
  ];
  $("compare-table").innerHTML = `
    <thead><tr><th></th>${inv.map((x) => `<th><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.id)}</a> ${esc(x.acronym || "")}<small>${esc(shortTitle(x.title))}</small></th>`).join("")}</tr></thead>
    <tbody>${rows.map(([label, f]) => {
      const cells = inv.map(f);
      const same = inv.length > 1 && cells.every((c) => c === cells[0]) && !/Not (listed|recorded)|None/.test(cells[0]);
      return `<tr class="${same ? "same" : ""}"><th scope="row">${label}</th>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`;
    }).join("")}</tbody>`;
  $("compare-summary").innerHTML = summarizeComparison(inv).map((t) => `<li>${t}</li>`).join("");
  $("compare").hidden = false;
  $("compare").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
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

// ---------- ask ----------
async function ask(q) {
  document.querySelector(".suggest")?.remove();
  addMsg(q, "user");
  const pending = addMsg("Reading the NASA data…", "bot");
  try {
    const d = await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }) });
    pending.textContent = d.answer;
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

function addMsg(text, who) {
  const el = document.createElement("p");
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
