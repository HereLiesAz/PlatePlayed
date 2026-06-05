# Setup & Run Guide

Everything you need to take PlatePlayed from a fresh clone to a running
watcher + dashboard. Two paths: **local** (one machine, virtualenv) and
**Docker** (watcher + web as services). Pick one.

> **Heads-up on responsible use:** license-plate data is regulated PII in many
> jurisdictions. Only watch streams you're allowed to, and set an auth password
> (Step 3) before exposing the dashboard.

---

## Prerequisites

| | Local | Docker |
| --- | --- | --- |
| Python 3.11+ | ✅ required | — (in image) |
| `ffmpeg` (used by yt-dlp/OpenCV) | ✅ for real streams | — (in image) |
| Docker + Compose | — | ✅ required |

Real plate detection also needs the ML extras (`requirements-ml.txt`). Without
them PlatePlayed runs end-to-end on a **stub detector** — the pipeline, DB, API,
and dashboard all work, but no plates are actually read. Good for trying it out.

---

## Path A — Local

### 1. Install

```bash
./scripts/setup.sh            # core deps + editable install + creates config.yaml
# or, to enable real ML plate detection:
./scripts/setup.sh --with-ml  # also installs fast-alpr + onnxruntime (large)

source .venv/bin/activate      # the script created this
```

> The script copies `config.example.yaml` → `config.yaml` if one doesn't exist.

### 2. Configure your streams

Edit **`config.yaml`** (it's gitignored — safe for secrets). At minimum, replace
the `streams:` list with the cameras you want to watch:

```yaml
streams:
  - name: "Main St & 5th"        # friendly label, stored in the DB
    url: "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
    enabled: true
```

To actually read plates, set `detector: "fast-alpr"` (or leave `"auto"` if you
installed with `--with-ml`).

### 3. Set credentials & alerts (recommended)

Auth is **off until a password is set** — anyone who reaches the dashboard sees
all logged plate data. Prefer environment variables over committing secrets:

```bash
export PLATEPLAYED_AUTH_USERNAME="admin"
export PLATEPLAYED_AUTH_PASSWORD="choose-a-strong-password"
# Optional: POST every watchlist alert to a webhook (Slack/Discord/your own):
export PLATEPLAYED_ALERT_WEBHOOK="https://hooks.example.com/..."
```

(Or set `auth.password` / `alerts.webhook_url` in `config.yaml`.)

### 4. Create the database

```bash
plateplayed migrate            # applies all schema migrations (recommended)
# or:  plateplayed init-db     # create tables directly, no migration history
```

### 5. Check your streams resolve (optional but smart)

```bash
plateplayed check              # probes each enabled stream for resolution/FPS
```

### 6. Run

Two processes — the **watcher** and the **dashboard**. In separate terminals
(both need the venv activated and the same env vars):

```bash
plateplayed run                                   # watch streams, log plates
plateplayed serve --host 0.0.0.0 --port 8000      # dashboard + API
```

Open **http://localhost:8000**. Use the ★ button on any detection to add a
plate to the watchlist; matching sightings then fire alerts.

---

## Path B — Docker

### 1. Create `config.yaml`

```bash
cp config.example.yaml config.yaml   # then edit streams/detector as in Path A, Step 2
```

### 2. Set secrets

Compose reads your shell environment. Export before `up`, or add an `env_file`:

```bash
export PLATEPLAYED_AUTH_PASSWORD="choose-a-strong-password"
export PLATEPLAYED_ALERT_WEBHOOK="https://hooks.example.com/..."   # optional
```

### 3. Launch

```bash
docker compose up --build
```

This starts two services sharing a volume:
- **watcher** — runs the pipeline against your streams
- **web** — serves the dashboard/API on **http://localhost:8000**

Migrations run against the shared `plate-data` volume on first start. Stop with
`docker compose down` (data persists in the named volume).

---

## What to edit in `config.yaml` — quick reference

| Field | Why you'd change it |
| --- | --- |
| `streams[]` | **The cameras to watch** — name + YouTube URL each. |
| `detector` | `"fast-alpr"` for real reads, `"stub"` to dry-run, `"auto"` to pick. |
| `min_confidence` | Raise to log fewer, surer plates; lower to catch more. |
| `sample_interval_seconds` | Lower = more thorough, more CPU. |
| `dedup_cooldown_seconds` | How long a parked car stays one row. |
| `auth.password` | **Set this** before exposing the dashboard. |
| `alerts.webhook_url` | Where watchlist alerts are POSTed. |
| `vehicle.enabled` | Tag detections with vehicle type/color (needs ML extras). |

Full annotated reference: **`config.example.yaml`**.

---

## Verify it's working

```bash
pytest                                 # 57 offline tests — no ML or network
curl -s localhost:8000/api/analytics/summary   # counts (add -u user:pass if auth on)
```

A healthy summary returns JSON like
`{"streams": N, "unique_plates": …, "detections": …, "alerts": …}`.

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `check` reports FAIL for a stream | URL isn't a live/playable stream, or `ffmpeg` missing. |
| Plates never appear | Using the stub detector — install ML extras and set `detector: "fast-alpr"`. |
| Dashboard loads but 401s | Auth is on; pass credentials (`-u`) or unset the password. |
| `no such table` errors | Run `plateplayed migrate` before `run`/`serve`. |
| Alerts never fire | Plate not on the watchlist, or within `alerts.cooldown_seconds`. |
