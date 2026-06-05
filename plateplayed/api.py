"""FastAPI app: query detections, serve screenshots, and host the dashboard."""

from __future__ import annotations

import base64
import logging
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from .config import load_config
from .db import Detection, Plate, Stream, init_db

logger = logging.getLogger(__name__)

config = load_config(os.environ.get("PLATEPLAYED_CONFIG", "config.yaml"))
SessionFactory = init_db(config.database_url)
SCREENSHOT_ROOT = Path(config.screenshot_dir).resolve()
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="PlatePlayed", version="0.1.0")


def _check_basic_auth(header: str) -> bool:
    """Validate an ``Authorization: Basic`` header against configured creds."""
    if not header.startswith("Basic "):
        return False
    try:
        user, _, password = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except Exception:
        return False
    return secrets.compare_digest(user, config.auth_username) and secrets.compare_digest(
        password, config.auth_password or ""
    )


if config.auth_password:
    @app.middleware("http")
    async def require_auth(request: Request, call_next):
        """Gate every route (API, screenshots, dashboard) behind Basic auth."""
        if _check_basic_auth(request.headers.get("Authorization", "")):
            return await call_next(request)
        return Response(
            "Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="PlatePlayed"'},
        )
else:
    logger.warning(
        "API auth is DISABLED — the dashboard and all logged plate data are "
        "publicly accessible. Set auth.password (or PLATEPLAYED_AUTH_PASSWORD)."
    )


@app.get("/api/stats")
def stats():
    with SessionFactory() as session:
        return {
            "streams": session.query(func.count(Stream.id)).scalar(),
            "unique_plates": session.query(func.count(Plate.id)).scalar(),
            "detections": session.query(func.count(Detection.id)).scalar(),
        }


@app.get("/api/streams")
def list_streams():
    with SessionFactory() as session:
        rows = session.query(Stream).all()
        return [
            {"id": s.id, "name": s.name, "url": s.url, "created_at": s.created_at}
            for s in rows
        ]


@app.get("/api/detections")
def list_detections(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    plate: str | None = None,
    stream_id: int | None = None,
):
    with SessionFactory() as session:
        q = (
            session.query(Detection)
            .options(joinedload(Detection.stream))
            .order_by(Detection.last_seen_at.desc())
        )
        if plate:
            q = q.filter(Detection.plate_number.like(f"%{plate.upper()}%"))
        if stream_id is not None:
            q = q.filter(Detection.stream_id == stream_id)
        rows = q.offset(offset).limit(limit).all()
        return [_detection_json(d) for d in rows]


@app.get("/api/plates")
def list_plates(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    with SessionFactory() as session:
        rows = (
            session.query(Plate)
            .order_by(Plate.last_seen.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "plate_number": p.plate_number,
                "first_seen": p.first_seen,
                "last_seen": p.last_seen,
                "sightings": p.sightings,
            }
            for p in rows
        ]


@app.get("/screenshots/{detection_id}/{kind}")
def screenshot(detection_id: int, kind: str):
    """Serve the ``frame`` or ``plate`` crop for a detection, path-traversal safe."""
    if kind not in ("frame", "plate"):
        raise HTTPException(404, "Unknown screenshot kind")
    with SessionFactory() as session:
        det = session.get(Detection, detection_id)
        if det is None:
            raise HTTPException(404, "Detection not found")
        raw = det.frame_path if kind == "frame" else det.plate_crop_path
    if not raw:
        raise HTTPException(404, "No screenshot for this detection")
    # Stored paths are relative to the screenshot root (older absolute paths
    # are still honored). Resolve, then confirm it stays inside the root.
    candidate = Path(raw)
    path = (candidate if candidate.is_absolute() else SCREENSHOT_ROOT / candidate).resolve()
    if SCREENSHOT_ROOT not in path.parents or not path.exists():
        raise HTTPException(404, "Screenshot file missing")
    return FileResponse(path)


def _detection_json(d: Detection) -> dict:
    return {
        "id": d.id,
        "plate_number": d.plate_number,
        "confidence": round(d.confidence, 3),
        "seen_at": d.seen_at,
        "last_seen_at": d.last_seen_at,
        "count": d.count,
        "stream_id": d.stream_id,
        "stream_name": d.stream.name if d.stream else None,
        "stream_url": d.stream.url if d.stream else None,
        "vehicle_type": d.vehicle_type,
        "vehicle_color": d.vehicle_color,
        "vehicle_make": d.vehicle_make,
        "vehicle_model": d.vehicle_model,
        "vehicle_category": d.vehicle_category,
        "frame_url": f"/screenshots/{d.id}/frame" if d.frame_path else None,
        "plate_url": f"/screenshots/{d.id}/plate" if d.plate_crop_path else None,
    }


# Mount the dashboard last so API routes take precedence.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
