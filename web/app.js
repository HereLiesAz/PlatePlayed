// PlatePlayed dashboard — polls the API and renders detection cards.
const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const search = document.getElementById("search");
const autorefresh = document.getElementById("autorefresh");

let timer = null;

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
}

function fmt(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    return isNaN(d) ? ts : d.toLocaleString();
}

async function refreshStats() {
    try {
        const s = await fetchJSON("/api/stats");
        document.getElementById("stat-plates").textContent = s.unique_plates ?? "0";
        document.getElementById("stat-detections").textContent = s.detections ?? "0";
        document.getElementById("stat-streams").textContent = s.streams ?? "0";
    } catch (_) { /* API may not be up yet */ }
}

async function refreshDetections() {
    const q = search.value.trim();
    const url = "/api/detections?limit=200" + (q ? `&plate=${encodeURIComponent(q)}` : "");
    let rows = [];
    try {
        rows = await fetchJSON(url);
    } catch (_) {
        return;
    }

    empty.hidden = rows.length > 0;
    grid.innerHTML = rows.map(cardHTML).join("");
}

function cardHTML(d) {
    const img = d.plate_url || d.frame_url;
    const thumb = img
        ? `<img loading="lazy" src="${img}" alt="${escapeHTML(d.plate_number)}">`
        : `<div class="card-noimg"></div>`;
    const seen = d.count > 1 ? `${fmt(d.last_seen_at)} · seen ×${d.count}` : fmt(d.seen_at);
    return `
        <article class="card">
            ${thumb}
            <div class="body">
                <div class="plate">${escapeHTML(d.plate_number)}</div>
                <div class="meta">
                    <span class="conf">${Math.round((d.confidence || 0) * 100)}% conf</span><br>
                    ${seen}<br>
                    ${escapeHTML(d.stream_name || ("stream #" + d.stream_id))}
                </div>
            </div>
        </article>`;
}

function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

async function refreshAll() {
    await Promise.all([refreshStats(), refreshDetections()]);
}

function scheduleRefresh() {
    if (timer) clearInterval(timer);
    if (autorefresh.checked) timer = setInterval(refreshAll, 5000);
}

search.addEventListener("input", () => refreshDetections());
autorefresh.addEventListener("change", scheduleRefresh);

refreshAll();
scheduleRefresh();

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
}
