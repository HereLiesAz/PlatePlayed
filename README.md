# PlatePlayed

Watch several YouTube live streams, detect **license plates** with an ML model,
and log every plate — its number, the time it was seen, and a screenshot of the
plate — to a database. A built-in web dashboard shows detections live.

```
YouTube live streams ──► frame sampler ──► ALPR model ──► recorder ──► SQLite/Postgres
   (yt-dlp + OpenCV)                       (fast-alpr)     (+ screenshots)   │
                                                                            ▼
                                                              FastAPI dashboard (:8000)
```

## What it does

- **Watches multiple streams at once** — one worker thread per stream, each
  reconnecting automatically when a live URL rotates.
- **Detects + reads plates** with [`fast-alpr`](https://github.com/ankandrew/fast-alpr)
  (YOLO plate detector + ONNX OCR, CPU-friendly).
- **Tracks plates across frames** — groups a car's detections over consecutive
  frames, votes on the best OCR read (`ABC123` beats a one-off `ABCl23`), and
  ignores one-frame false positives.
- **Tags the vehicle** — type (car / truck / bus / motorcycle, via a YOLO COCO
  model) and dominant color, linked to each plate by its bounding box.
- **Logs to a database** (SQLite by default, Postgres by config) with three
  tables: `streams`, `plates` (unique plates + counts), and `detections`
  (every sighting, with timestamp and screenshot paths).
- **Saves screenshots** — the full frame plus a cropped close-up of each plate.
- **De-duplicates** — a parked or slow car becomes a single detection row whose
  `last_seen` / `count` update, instead of thousands of rows.
- **Serves a live dashboard** — filter by plate, see thumbnails and confidence;
  protected by HTTP Basic auth when a password is configured.

## Quick start

```bash
# 1. Set up (core deps only; uses a no-op stub detector)
./scripts/setup.sh

# …or include the real ML engine:
./scripts/setup.sh --with-ml

# 2. Add your streams
cp config.example.yaml config.yaml   # then edit `streams:`

# 3. Start watching + logging
plateplayed run

# 4. In another terminal, open the dashboard
plateplayed serve   # http://127.0.0.1:8000
```

### With Docker

```bash
cp config.example.yaml config.yaml   # edit streams first
docker compose up --build            # watcher + dashboard on :8000
```

To bake the ML engine into the image, uncomment the `requirements-ml.txt` line
in the `Dockerfile`.

## Configuration

All behaviour is driven by `config.yaml` (see `config.example.yaml`):

| Key | Meaning |
| --- | --- |
| `database_url` | SQLAlchemy URL. SQLite default; Postgres supported. |
| `screenshot_dir` | Where full frames + plate crops are written. |
| `detector` | `auto` (ML if installed, else stub), `fast-alpr`, or `stub`. |
| `min_confidence` | Minimum OCR confidence (0–1) to log a plate. |
| `sample_interval_seconds` | Seconds between sampled frames per stream. |
| `dedup_cooldown_seconds` | Window for collapsing repeat sightings. |
| `save_plate_crops` | Also save a cropped close-up of each plate. |
| `tracking.enabled` | Multi-frame tracking + best-read voting. |
| `tracking.min_hits` | Frames a plate must appear in before it's logged. |
| `tracking.iou_threshold` | Box overlap to treat detections as the same car. |
| `tracking.max_age_seconds` | Forget a track after this long unseen. |
| `vehicle.enabled` | Tag detections with vehicle type + color. |
| `vehicle.detector` | `auto` (YOLO if installed, else off), `yolo`, or `stub`. |
| `vehicle.model` | ultralytics COCO weights (default `yolov8n.pt`). |
| `vehicle.min_confidence` | Minimum vehicle-detection confidence. |
| `auth.username` / `auth.password` | HTTP Basic creds for the dashboard/API. |
| `streams` | List of `{ name, url, enabled }` YouTube streams. |

Environment overrides: `PLATEPLAYED_DB_URL` (database), and
`PLATEPLAYED_AUTH_USERNAME` / `PLATEPLAYED_AUTH_PASSWORD` (credentials — the
preferred way to supply them, so secrets stay out of `config.yaml`).

## Authentication

The dashboard and API are **unauthenticated by default** (handy for local dev,
which prints a warning). Set a password to require HTTP Basic auth on every
route — API, screenshots, and the dashboard:

```bash
export PLATEPLAYED_AUTH_USERNAME=watcher
export PLATEPLAYED_AUTH_PASSWORD=change-me
plateplayed serve
```

Because it's standard Basic auth, the browser prompts once and reuses the
credentials for the dashboard's API calls. Put it behind HTTPS (a reverse
proxy) before exposing it beyond localhost.

## Database migrations

Schema changes are managed with **Alembic**. For a quick local start,
`plateplayed init-db` just creates the current tables. For anything long-lived,
use migrations so the schema can evolve safely:

```bash
plateplayed migrate          # apply all migrations (alembic upgrade head)
```

## The ML model

The detection engine is `fast-alpr`, which runs two ONNX models on CPU:

1. a **YOLO** license-plate **detector** that finds plate bounding boxes, and
2. an **OCR** model that reads the characters.

Model weights download automatically on first run. The engine sits behind a
small `Detector` interface (`plateplayed/detector.py`), so you can swap in a
different ALPR backend or a custom YOLO+OCR pipeline without touching the rest
of the system. When the ML deps aren't installed, a **stub detector** keeps the
streams, database, API, and dashboard fully functional for development.

On top of raw detection, a per-stream **tracker** (`plateplayed/tracking.py`)
matches detections across consecutive frames by box overlap, accumulates the
reads of each car, and emits a single voted consensus plate — improving
accuracy and cutting duplicate/false rows before anything reaches the database.

**Vehicle attributes** (`plateplayed/vehicle.py`) add a second layer: a YOLO
COCO model detects vehicles in the frame, each plate is linked to the vehicle
box that contains it, the vehicle's **type** (car / truck / bus / motorcycle)
is read from the detector, and its **color** is named from an HSV analysis of
the crop (pure OpenCV — no model needed for color). Type detection needs the ML
extras; without them, plates are still logged, just without type/color. Color
naming and box-association are unit-tested offline.

## Database schema

- **`streams`** — `id, name, url, created_at`
- **`plates`** — `id, plate_number (unique), first_seen, last_seen, sightings`
- **`detections`** — `id, plate_id, stream_id, plate_number, confidence,
  seen_at, last_seen_at, count, frame_path, plate_crop_path,
  vehicle_type, vehicle_color, vehicle_confidence`

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/stats` | Counts of streams, unique plates, detections. |
| `GET /api/detections` | Recent detections (`?plate=`, `?stream_id=`, `?limit=`, `?offset=`). |
| `GET /api/plates` | Unique plates with sighting counts. |
| `GET /api/streams` | Configured streams. |
| `GET /screenshots/{id}/{frame\|plate}` | Screenshot image for a detection. |
| `GET /` | The dashboard (installable PWA). |

## Development

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
pytest                       # 34 tests, no ML or network required
```

The core logic (config, database, de-duplication, tracking/voting, vehicle
color + association, screenshot storage, auth, and migrations) is tested against
in-memory/file SQLite with a stub detector — fast and offline. **GitHub Actions** (`.github/workflows/ci.yml`)
runs the suite on every push and pull request across Python 3.10–3.12.

## Responsible use

PlatePlayed reads plates from **public** video. License-plate data can be
personally identifying and is regulated in many jurisdictions (e.g. GDPR, CCPA,
and ALPR-specific laws). Only run it on streams you are permitted to process,
retain data no longer than necessary, and comply with the platform's terms of
service and applicable law.
