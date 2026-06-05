// PlatePlayed dashboard — polls the API and renders detection cards.
const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const search = document.getElementById("search");
const autorefresh = document.getElementById("autorefresh");
const topPlatesEl = document.getElementById("top-plates");
const hourlyEl = document.getElementById("hourly");

let timer = null;
let watched = new Set();   // plate numbers currently on the watchlist

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

function setText(id, v) {
    const el = document.getElementById(id);
    if (el) el.textContent = v ?? "0";
}

async function refreshStats() {
    try {
        const s = await fetchJSON("/api/analytics/summary");
        setText("stat-plates", s.unique_plates);
        setText("stat-detections", s.detections);
        setText("stat-24h", s.detections_24h);
        setText("stat-streams", s.streams);
        setText("stat-alerts", s.alerts);
    } catch (_) { /* API may not be up yet */ }
}

async function refreshAnalytics() {
    try {
        const top = await fetchJSON("/api/analytics/top-plates?limit=10");
        topPlatesEl.innerHTML = top.map((p) => `
            <li><span class="tp-plate">${escapeHTML(p.plate_number)}</span>
                <span class="tp-count">${p.sightings}× · ${p.streams} stream${p.streams === 1 ? "" : "s"}</span></li>
        `).join("") || `<li class="muted">No data yet</li>`;
    } catch (_) { /* ignore */ }

    try {
        const hours = await fetchJSON("/api/analytics/hourly");
        const max = Math.max(1, ...hours);
        hourlyEl.innerHTML = hours.map((n, h) => `
            <div class="bar" title="${h}:00 — ${n}">
                <div class="bar-fill" style="height:${Math.round((n / max) * 100)}%"></div>
            </div>
        `).join("");
    } catch (_) { /* ignore */ }
}

async function refreshWatchlist() {
    try {
        const list = await fetchJSON("/api/watchlist");
        watched = new Set(list.map((w) => w.plate_number));
    } catch (_) { /* ignore */ }
}

async function toggleWatch(plate) {
    try {
        if (watched.has(plate)) {
            await fetch(`/api/watchlist/${encodeURIComponent(plate)}`, { method: "DELETE" });
            watched.delete(plate);
        } else {
            await fetch("/api/watchlist", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ plate_number: plate }),
            });
            watched.add(plate);
        }
    } catch (_) { /* ignore */ }
    refreshDetections();
    refreshStats();
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
    grid.querySelectorAll("[data-watch]").forEach((btn) => {
        btn.addEventListener("click", () => toggleWatch(btn.dataset.watch));
    });
}

function cardHTML(d) {
    const img = d.plate_url || d.frame_url;
    const thumb = img
        ? `<img loading="lazy" src="${img}" alt="${escapeHTML(d.plate_number)}">`
        : `<div class="card-noimg"></div>`;
    const seen = d.count > 1 ? `${fmt(d.last_seen_at)} · seen ×${d.count}` : fmt(d.seen_at);
    // Prefer make/model when present, else fall back to the coarse type.
    const descParts = [d.vehicle_color, d.vehicle_make, d.vehicle_model];
    if (!d.vehicle_make) descParts.push(d.vehicle_type);
    const vehicle = descParts.filter(Boolean).join(" ");
    const vehicleLine = vehicle ? `<span class="vehicle">${escapeHTML(vehicle)}</span><br>` : "";
    const category = d.vehicle_category
        ? `<span class="category">${escapeHTML(d.vehicle_category)}</span>` : "";
    const on = watched.has(d.plate_number);
    const star = `<button class="watch${on ? " on" : ""}" data-watch="${escapeHTML(d.plate_number)}"
        title="${on ? "Remove from watchlist" : "Add to watchlist"}">${on ? "★" : "☆"}</button>`;
    return `
        <article class="card">
            ${thumb}
            <div class="body">
                <div class="plate">${escapeHTML(d.plate_number)}${category}${star}</div>
                <div class="meta">
                    <span class="conf">${Math.round((d.confidence || 0) * 100)}% conf</span><br>
                    ${vehicleLine}
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
    await refreshWatchlist();
    await Promise.all([refreshStats(), refreshAnalytics(), refreshDetections()]);
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
