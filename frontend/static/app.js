// Disastro dashboard. Every page is rendered from the live API; nothing is hardcoded.
//
//   #/                overview
//   #/news            news feed        (?type= &severity= &source_type= &source= &q=)
//   #/type/<type>     one disaster type
//   #/event/<id>      one event + related reports
//   #/map             all located events
//   #/alerts          high severity alerts
//   #/ask             questions answered from the stored reports (?q=)

const COLORS = { high: "#ff5c5c", medium: "#ffb347", low: "#5fd38d" };
const ICONS = {
  earthquake: "🌐", flood: "🌊", cyclone: "🌀", wildfire: "🔥", volcano: "🌋", tsunami: "🌊",
  landslide: "⛰️", drought: "☀️", tornado: "🌪️", heatwave: "🌡️", storm: "⛈️",
};
const PAGE_SIZE = 30;
const REFRESH_MS = 120000;

const $ = (id) => document.getElementById(id);
const view = $("view");

let currentMap = null;
let renderToken = 0;


// ------------------------------------------------------------ helpers

// Everything shown here was scraped from the web, so it is always escaped.
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function safeUrl(url) {
  return /^https?:\/\//i.test(url || "") ? url : "";
}

function timeAgo(iso) {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso)) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h ago`;
  return `${Math.round(minutes / 1440)} d ago`;
}

function fullTime(iso) {
  return iso ? new Date(iso).toLocaleString() : "";
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = new Error(`${response.status} ${response.statusText}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

function badges(event) {
  return `<span class="badge ${esc(event.severity)}">${esc(event.severity || "?")}</span>` +
    `<a class="badge type" href="#/type/${encodeURIComponent(event.disaster_type)}">${esc(event.disaster_type)}</a>`;
}

function eventHtml(event, { summary = false } = {}) {
  const text = event.summary || "";
  const score = event.score !== undefined ? ` · match ${Math.round(event.score * 100)}%` : "";
  return `<div class="event">
    ${badges(event)}
    <a class="title" href="#/event/${encodeURIComponent(event.id)}">${esc(event.headline || event.text)}</a>
    ${summary && text && text !== event.headline ? `<div class="summary">${esc(text.slice(0, 220))}</div>` : ""}
    <div class="meta">${esc(event.source)} · <span title="${esc(fullTime(event.published_at))}">${esc(timeAgo(event.published_at))}</span>${esc(score)}</div>
  </div>`;
}

function eventList(events, emptyText, options) {
  return events.length
    ? events.map((event) => eventHtml(event, options)).join("")
    : `<div class="empty">${esc(emptyText)}</div>`;
}

function severityBar(counts) {
  const total = counts.total || 1;
  return `<div class="severity-bar">${["high", "medium", "low"].map((level) =>
    `<span class="${level}" style="width:${(counts[level] / total) * 100}%"></span>`).join("")}</div>`;
}

function drawMap(elementId, events, { zoom = 2, center = [20, 10] } = {}) {
  const map = L.map(elementId, { worldCopyJump: true }).setView(center, zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 10, attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  // Draw low severity first so the serious events end up on top.
  const order = { low: 0, medium: 1, high: 2 };
  const located = events
    .filter((event) => typeof event.latitude === "number" && typeof event.longitude === "number")
    .sort((a, b) => (order[a.severity] || 0) - (order[b.severity] || 0));

  for (const event of located) {
    L.circleMarker([event.latitude, event.longitude], {
      radius: event.severity === "high" ? 9 : event.severity === "medium" ? 7 : 5,
      color: COLORS[event.severity] || "#8b98a5", fillOpacity: 0.6, weight: 1,
    }).bindPopup(eventHtml(event)).addTo(map);
  }

  currentMap = map;
  return located.length;
}


// -------------------------------------------------------------- pages

async function overviewPage() {
  const [stats, serious, latest, located, alerts, report] = await Promise.all([
    api("/api/stats"),
    api("/api/events?severity=high&limit=6"),
    api("/api/events?limit=8"),
    api("/api/events?located=true&limit=1000"),
    api("/api/alerts?limit=5"),
    api("/api/report"),
  ]);

  if (!stats.total) {
    return { html: `<div class="panel empty">No events stored yet. Click "Refresh data" to run the pipeline.</div>` };
  }

  const types = Object.entries(stats.by_type).sort((a, b) => b[1].total - a[1].total);
  const days = Object.entries(stats.by_day);
  const busiest = Math.max(...days.map(([, count]) => count), 1);

  const html = `
    <div class="page-head">
      <h1>Current situation</h1>
      <p>${stats.total} reports from the last 7 days · latest ${esc(timeAgo(stats.latest))}</p>
    </div>
    <div class="column">
      <div class="stats">
        <a class="stat" href="#/news"><div class="value">${stats.total}</div><div class="label">Events tracked</div></a>
        ${["high", "medium", "low"].map((level) => `
          <a class="stat" href="#/news?severity=${level}">
            <div class="value ${level}-text">${stats.by_severity[level] || 0}</div>
            <div class="label">${level} severity</div>
          </a>`).join("")}
        <a class="stat" href="#/news?source_type=news"><div class="value">${stats.by_source_type.news || 0}</div><div class="label">News articles</div></a>
        <a class="stat" href="#/news?source_type=api"><div class="value">${stats.by_source_type.api || 0}</div><div class="label">Agency events</div></a>
        <a class="stat" href="#/news?source_type=social"><div class="value">${stats.by_source_type.social || 0}</div><div class="label">Social posts</div></a>
      </div>

      <div class="grid two">
        <div class="column">
          <div class="panel">
            <div class="panel-head"><h2>Most serious right now</h2><a href="#/news?severity=high">All high severity →</a></div>
            ${eventList(serious.events, "No high severity events at the moment.", { summary: true })}
          </div>
          <div class="panel">
            <div class="panel-head"><h2>Event map</h2><a href="#/map">Full map →</a></div>
            <div class="map" id="map"></div>
          </div>
          <div class="panel">
            <div class="panel-head"><h2>Latest reports</h2><a href="#/news">All news →</a></div>
            ${eventList(latest.events, "No reports.")}
          </div>
        </div>

        <div class="column">
          <div class="panel">
            <h2>Situation report</h2>
            ${report.answer
              ? `<div class="answer">${esc(report.answer)}</div>
                 <div class="meta">Generated ${esc(timeAgo(report.generated_at))} by ${esc(report.backend)}</div>`
              : `<div class="empty">No report generated yet.</div>`}
          </div>
          <div class="panel">
            <h2>By disaster type</h2>
            <div class="types">
              ${types.map(([type, counts]) => `
                <a class="type-card" href="#/type/${encodeURIComponent(type)}">
                  <div class="icon">${ICONS[type] || "⚠️"}</div>
                  <div class="name">${esc(type)}</div>
                  <div class="meta">${counts.total} reports${counts.high ? ` · ${counts.high} high` : ""}</div>
                  ${severityBar(counts)}
                </a>`).join("")}
            </div>
          </div>
          <div class="panel">
            <h2>Reports per day</h2>
            <div class="days">
              ${days.map(([day, count]) => `
                <div class="day" title="${esc(day)}: ${count} reports">
                  <div class="meta">${count}</div>
                  <div class="bar" style="height:${(count / busiest) * 100}%"></div>
                  <div class="label">${esc(day.slice(5))}</div>
                </div>`).join("")}
            </div>
          </div>
          <div class="panel">
            <div class="panel-head"><h2>Latest alerts</h2><a href="#/alerts">All alerts →</a></div>
            ${eventList(alerts.alerts, "No alerts.")}
          </div>
          <div class="panel">
            <h2>Top sources</h2>
            ${stats.top_sources.map(([source, count]) => `
              <div class="event"><a class="title" href="#/news${query({ source })}">${esc(source)}</a>
              <span class="meta"> · ${count} reports</span></div>`).join("")}
          </div>
        </div>
      </div>
    </div>`;

  return { html, after: () => drawMap("map", located.events) };
}


// The news feed; also used for the per-type pages with the type fixed.
async function newsPage(params, fixedType) {
  const filters = {
    disaster_type: fixedType || params.get("type") || "",
    severity: params.get("severity") || "",
    source_type: params.get("source_type") || "",
    source: params.get("source") || "",
    q: params.get("q") || "",
  };
  const shown = Number(params.get("shown")) || PAGE_SIZE;

  const requests = [api("/api/stats"), api(`/api/events${query({ ...filters, limit: shown })}`)];
  if (fixedType) requests.push(api(`/api/events${query({ disaster_type: fixedType, located: true, limit: 1000 })}`));
  const [stats, data, located] = await Promise.all(requests);

  const base = fixedType ? `#/type/${encodeURIComponent(fixedType)}` : "#/news";
  const link = (changes) => base + query({
    type: fixedType ? "" : filters.disaster_type, severity: filters.severity,
    source_type: filters.source_type, source: filters.source, q: filters.q, ...changes,
  });
  const option = (value, label, selected) =>
    `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(label)}</option>`;

  const counts = fixedType ? stats.by_type[fixedType] : null;
  const head = fixedType
    ? `<h1>${ICONS[fixedType] || "⚠️"} ${esc(fixedType[0].toUpperCase() + fixedType.slice(1))}</h1>
       <p>${counts ? `${counts.total} reports · ${counts.high} high · ${counts.medium} medium · ${counts.low} low` : "No reports of this type right now."}</p>`
    : `<h1>News</h1><p>${data.count} matching reports, newest first</p>`;

  const html = `
    <div class="page-head">${head}</div>
    <div class="column">
      ${located && located.events.length ? `<div class="panel"><h2>Where</h2><div class="map" id="map"></div></div>` : ""}
      <div class="panel">
        <form class="filters" id="filters">
          <input type="search" name="q" placeholder="Filter by words, e.g. evacuation" value="${esc(filters.q)}">
          ${fixedType ? "" : `<select name="type">${option("", "All types", filters.disaster_type)}${
            Object.entries(stats.by_type).sort((a, b) => b[1].total - a[1].total)
              .map(([type, c]) => option(type, `${type} (${c.total})`, filters.disaster_type)).join("")}</select>`}
          <select name="severity">${[["", "All severities"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]]
            .map(([value, label]) => option(value, label, filters.severity)).join("")}</select>
          <select name="source_type">${[["", "All sources"], ["news", "News"], ["api", "Agencies"], ["social", "Social"]]
            .map(([value, label]) => option(value, label, filters.source_type)).join("")}</select>
          <button>Apply</button>
        </form>
        ${filters.source ? `<p class="meta">Source: ${esc(filters.source)} · <a href="${esc(link({ source: "" }))}">clear</a></p>` : ""}
        ${eventList(data.events, "Nothing matches these filters.", { summary: true })}
        ${data.count > data.events.length
          ? `<div class="more"><a class="button" href="${esc(link({ shown: shown + PAGE_SIZE }))}">Show more (${data.count - data.events.length} left)</a></div>`
          : ""}
      </div>
    </div>`;

  const after = () => {
    if (located && located.events.length) drawMap("map", located.events);

    const form = $("filters");
    const apply = (submit) => {
      if (submit) submit.preventDefault();
      const values = Object.fromEntries(new FormData(form));
      location.hash = base + query({ ...values, source: filters.source });
    };
    form.addEventListener("submit", apply);
    for (const select of form.querySelectorAll("select")) select.addEventListener("change", () => apply());
  };

  return { html, after };
}


async function eventPage(id) {
  let data;
  try {
    data = await api(`/api/events/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error.status !== 404) throw error;
    return { html: `<div class="panel"><h1>Event not found</h1>
      <p class="empty">It may have expired (events are kept for 7 days). <a href="#/news">Back to the news</a></p></div>` };
  }

  const { event, related } = data;
  const hasPlace = typeof event.latitude === "number" && typeof event.longitude === "number";
  const url = safeUrl(event.url);
  const body = event.summary && event.summary !== event.headline ? event.summary : "";

  const facts = [
    ["Source", `<a href="#/news${query({ source: event.source })}">${esc(event.source)}</a>`],
    ["Published", `${esc(fullTime(event.published_at))} (${esc(timeAgo(event.published_at))})`],
    ["Type", `<a href="#/type/${encodeURIComponent(event.disaster_type)}">${esc(event.disaster_type)}</a>`],
    ["Severity", `${esc(event.severity)} <span class="meta">(from ${esc(
      event.severity_method === "structured" ? "agency data" : event.severity_method === "zero-shot" ? "text classifier" : "keyword rules")})</span>`],
    event.location ? ["Location", esc(event.location)] : null,
    typeof event.magnitude === "number" ? ["Magnitude", esc(event.magnitude)] : null,
    typeof event.wind_kts === "number" ? ["Wind speed", `${esc(event.wind_kts)} kt`] : null,
    event.alert_level ? ["Agency alert level", esc(event.alert_level)] : null,
    hasPlace ? ["Coordinates", `${event.latitude.toFixed(3)}, ${event.longitude.toFixed(3)}`] : null,
  ].filter(Boolean);

  const html = `
    <div class="grid two">
      <div class="column">
        <div class="panel detail">
          <a href="#/news">← All news</a>
          <div style="margin-top:10px">${badges(event)}</div>
          <h1>${esc(event.headline)}</h1>
          ${body ? `<div class="body">${esc(body)}</div>` : ""}
          <dl class="facts">${facts.map(([name, value]) => `<dt>${name}</dt><dd>${value}</dd>`).join("")}</dl>
          ${url ? `<a class="button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Read at ${esc(event.source)} ↗</a>` : ""}
          <a class="button" style="background:var(--panel);color:var(--text);border:1px solid var(--border)"
             href="#/ask${query({ q: `What is known about: ${event.headline}` })}">Ask about this</a>
        </div>
        ${hasPlace ? `<div class="panel"><h2>Location</h2><div class="map small" id="map"></div></div>` : ""}
      </div>
      <div class="panel">
        <h2>Related reports</h2>
        ${eventList(related, "No related reports found.")}
      </div>
    </div>`;

  return {
    html,
    after: () => { if (hasPlace) drawMap("map", [event], { zoom: 5, center: [event.latitude, event.longitude] }); },
  };
}


async function mapPage() {
  const data = await api("/api/events?located=true&limit=1000");

  const html = `
    <div class="page-head">
      <h1>Map</h1>
      <p>${data.count} located events from USGS, GDACS and NASA EONET. News articles carry no coordinates.
        <span class="high-text">● high</span> <span class="medium-text">● medium</span> <span class="low-text">● low</span></p>
    </div>
    <div class="panel"><div class="map tall" id="map"></div></div>`;

  return { html, after: () => drawMap("map", data.events) };
}


async function alertsPage() {
  const data = await api("/api/alerts?limit=500");

  const html = `
    <div class="page-head">
      <h1>Alerts</h1>
      <p>${data.count} high severity events from news and agency sources, most recent first</p>
    </div>
    <div class="panel">
      ${data.alerts.length ? data.alerts.map((alert) => `
        <div class="event">
          ${badges(alert)}
          <a class="title" href="#/event/${encodeURIComponent(alert.id)}">${esc(alert.headline)}</a>
          <div class="meta">${esc(alert.source)} · published ${esc(timeAgo(alert.published_at))} · alerted ${esc(fullTime(alert.alerted_at))}</div>
        </div>`).join("") : `<div class="empty">No alerts.</div>`}
    </div>`;

  return { html };
}


async function askPage(params) {
  const stats = await api("/api/stats");
  const question = params.get("q") || "";

  // Suggestions are built from the disaster types that currently have reports.
  const types = Object.entries(stats.by_type).sort((a, b) => b[1].total - a[1].total).slice(0, 4);
  const suggestions = ["What are the most serious disasters right now?"]
    .concat(types.map(([type]) => `What is the latest on ${type} events?`));

  const html = `
    <div class="page-head">
      <h1>Ask</h1>
      <p>Answers are generated only from the ${stats.total} stored reports. A local model can take a minute.</p>
    </div>
    <div class="column">
      <div class="panel">
        <form class="ask" id="ask-form">
          <input type="text" id="question" placeholder="e.g. Where are the worst floods right now?" value="${esc(question)}">
          <button id="ask-button">Ask</button>
          <button type="button" class="secondary" id="search-button">Search only</button>
        </form>
        <div class="suggestions">
          ${suggestions.map((text) => `<a class="badge type" href="#/ask${query({ q: text })}">${esc(text)}</a>`).join("")}
        </div>
      </div>
      <div class="panel" id="result" hidden></div>
    </div>`;

  const after = () => {
    const result = $("result");
    const buttons = [$("ask-button"), $("search-button")];

    const run = async (mode) => {
      const text = $("question").value.trim();
      if (!text) return;

      buttons.forEach((button) => { button.disabled = true; });
      result.hidden = false;
      result.innerHTML = `<div class="empty">${mode === "ask" ? "Thinking..." : "Searching..."}</div>`;

      try {
        if (mode === "ask") {
          const data = await api("/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: text }),
          });
          result.innerHTML = `<h2>Answer</h2><div class="answer">${esc(data.answer)}</div>
            ${data.backend ? `<div class="meta">Generated by ${esc(data.backend)}</div>` : ""}
            <h2 style="margin-top:16px">Reports used</h2>${eventList(data.sources, "None.")}`;
        } else {
          const data = await api(`/api/search${query({ q: text, n: 15 })}`);
          result.innerHTML = `<h2>Closest reports</h2>${eventList(data.results, "Nothing found.")}`;
        }
      } catch (error) {
        result.innerHTML = `<div class="empty">Request failed: ${esc(error.message)}</div>`;
      }

      buttons.forEach((button) => { button.disabled = false; });
    };

    $("ask-form").addEventListener("submit", (submit) => { submit.preventDefault(); run("ask"); });
    $("search-button").addEventListener("click", () => run("search"));

    if (question) run("ask");
  };

  return { html, after };
}


// ------------------------------------------------------------- router

function parseRoute() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [path, search = ""] = hash.split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  return { name: parts[0] || "overview", arg: parts[1], params: new URLSearchParams(search) };
}

function pageFor(route) {
  switch (route.name) {
    case "overview": return overviewPage();
    case "news": return newsPage(route.params);
    case "type": return newsPage(route.params, route.arg);
    case "event": return eventPage(route.arg);
    case "map": return mapPage();
    case "alerts": return alertsPage();
    case "ask": return askPage(route.params);
    default: return Promise.resolve({ html: `<div class="panel"><h1>Page not found</h1><a href="#/">Go to the overview</a></div>` });
  }
}

async function render({ keepScroll = false } = {}) {
  const route = parseRoute();
  const token = ++renderToken;
  const scroll = window.scrollY;

  for (const link of document.querySelectorAll("#nav a")) {
    const active = link.dataset.route === route.name || (link.dataset.route === "news" && ["type", "event"].includes(route.name));
    link.classList.toggle("active", active);
  }

  let page;
  try {
    page = await pageFor(route);
  } catch (error) {
    page = { html: `<div class="panel"><h1>Could not load data</h1><p class="empty">${esc(error.message)}. Is the server running?</p></div>` };
  }

  // A newer navigation started while this one was loading.
  if (token !== renderToken) return;

  if (currentMap) { currentMap.remove(); currentMap = null; }

  view.innerHTML = page.html;
  if (page.after) page.after();

  window.scrollTo(0, keepScroll ? scroll : 0);
}


// ------------------------------------------------- header and refresh

async function updateHeader() {
  const [stats, alerts] = await Promise.all([api("/api/stats"), api("/api/alerts?limit=1")]);

  const running = stats.pipeline.running;
  $("refresh").disabled = running;
  $("nav-alerts").textContent = alerts.count || "";
  $("status").textContent = running
    ? "Collecting new data..."
    : stats.latest ? `Latest report ${timeAgo(stats.latest)}` : "No data yet";

  return running;
}

async function pollPipeline() {
  const running = await updateHeader();
  if (running) setTimeout(pollPipeline, 5000);
  else render({ keepScroll: true });
}

$("refresh").addEventListener("click", async () => {
  $("refresh").disabled = true;
  await api("/api/refresh", { method: "POST" });
  pollPipeline();
});

window.addEventListener("hashchange", () => render());

// Keep the open page current, except where the user is in the middle of something.
setInterval(() => {
  updateHeader().catch(() => {});
  const route = parseRoute().name;
  const typing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName);
  if (route !== "ask" && !typing) render({ keepScroll: true });
}, REFRESH_MS);

render();
updateHeader().then((running) => { if (running) pollPipeline(); }).catch(() => {});
