// FlameWatch dashboard logic. Polls the backend, updates the four panels.
const $ = (id) => document.getElementById(id);
let lastKey = "";
let chart;

async function api(path, opts) {
  const r = await fetch(path, opts);
  return r.json();
}

// ---- 1. habitat panel ----
async function refreshState() {
  const s = await api("/api/state");
  if (!$("scenario").options.length) {
    $("scenario").add(new Option("Live sensor box", "live"));
    for (const [k, v] of Object.entries(s.scenarios)) $("scenario").add(new Option(v.label, k));
    $("scenario").options[0].disabled = true;
  }
  $("scenario").value = s.live ? "live" : s.scenario;
  $("scenario").disabled = s.live;
  $("source-badge").textContent = s.live ? "live sensor" : "scenario";
  $("source-badge").classList.toggle("live", s.live);
  $("r-o2").textContent = `${s.o2_pct.toFixed(1)}%`;
  $("r-p").textContent = `${s.pressure_psi.toFixed(1)} psi`;
  $("r-smoke").textContent = s.smoke != null ? Math.round(s.smoke) : "-";
  $("r-temp").textContent = s.temp_c != null ? `${s.temp_c.toFixed(1)} °C` : "-";
  $("risk").className = `risk ${s.risk.level}`;
  $("risk-score").textContent = s.risk.score;
  const p = s.risk.parts;
  $("risk-parts").textContent = `atmosphere ${p.atmosphere} · smoke ${p.smoke} · heat ${p.heat} · flame ${p.flame}`;

  // Re-rank only when conditions change meaningfully.
  const key = `${Math.round(s.o2_pct)}|${s.pressure_psi.toFixed(1)}|${$("area").value}`;
  if (key !== lastKey) {
    lastKey = key;
    refreshRank();
    markHabitat(s);
  }
}

$("scenario").addEventListener("change", async (e) => {
  await api("/api/scenario", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: e.target.value }) });
  refreshState();
});
$("area").addEventListener("change", () => { lastKey = ""; refreshState(); });

// ---- 2. ranked experiments ----
async function refreshRank() {
  const d = await api(`/api/rank?area=${$("area").value}`);
  $("rank-list").innerHTML = d.results.map((r) => `
    <li>
      <div class="t"><a href="${r.url}" target="_blank">${r.id}</a> ${r.acronym || ""} · ${r.title}</div>
      <div>${r.areas.map((a) => `<span class="tag ${a}">${a}</span>`).join("")}
        <span class="meta">${r.fuel_kind} · ${r.tests_total} tests${r.o2_range ? ` · O₂ ${r.o2_range[0]}–${r.o2_range[1]}%` : ""} · score ${r.score}</span></div>
      <div class="meta">Why: ${r.why}</div>
    </li>`).join("");
}

// ---- 3. chat ----
$("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("chat-input").value.trim();
  if (!q) return;
  addMsg(q, "user");
  $("chat-input").value = "";
  const thinking = addMsg("Checking NASA data…", "bot");
  const d = await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q }) });
  thinking.textContent = d.answer;
});

function addMsg(text, who) {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  el.textContent = text;
  $("chat-log").appendChild(el);
  $("chat-log").scrollTop = 1e9;
  return el;
}

// ---- 4. knowledge gaps chart ----
const PALETTE = ["#5fa8ff", "#2fbf71", "#f2b33d", "#c77dff", "#4dd4d4", "#ff6b9a", "#a3d65c", "#ffd166", "#8fa3ff", "#ff9f6b"];
async function buildChart() {
  const pts = await api("/api/points");
  const groups = {};
  for (const p of pts) (groups[p.acronym || p.id] ||= []).push({ x: p.o2, y: p.p });
  chart = new Chart($("gap-chart"), {
    type: "scatter",
    data: {
      datasets: [
        ...Object.entries(groups).map(([name, data], i) => ({ label: name, data, pointRadius: 3,
          backgroundColor: PALETTE[i % PALETTE.length], borderColor: PALETTE[i % PALETTE.length] })),
        { label: "Your habitat", data: [], pointStyle: "star", pointRadius: 14,
          borderColor: "#ff7a2f", backgroundColor: "#ff7a2f", borderWidth: 3 },
      ],
    },
    options: {
      scales: {
        x: { title: { display: true, text: "Oxygen (%)", color: "#93a0b8" }, min: 0, max: 100,
             ticks: { color: "#93a0b8" }, grid: { color: "#243047" } },
        y: { title: { display: true, text: "Pressure (atm)", color: "#93a0b8" }, min: 0, grace: "10%",
             ticks: { color: "#93a0b8" }, grid: { color: "#243047" } },
      },
      plugins: { legend: { labels: { color: "#e8edf5", boxWidth: 10 } } },
    },
  });
}

function markHabitat(s) {
  if (!chart) return;
  const star = chart.data.datasets.at(-1);
  star.data = [{ x: s.o2_pct, y: s.pressure_psi / 14.696 }];
  chart.update("none");
}

buildChart().then(refreshState);
setInterval(refreshState, 1000);
