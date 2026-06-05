"""Watchlist management and alerting on watchlisted plate sightings."""

from __future__ import annotations

import logging
from datetime import timedelta

from .db import Alert, Detection, Watchlist, utcnow
from .notify import Notifier

logger = logging.getLogger(__name__)


# --- Watchlist CRUD (used by the API) -------------------------------------- #
def add_watch(session, plate_number: str, note: str | None = None) -> Watchlist:
    """Add or re-activate a watchlist entry for ``plate_number``."""
    plate_number = plate_number.upper().strip()
    entry = session.query(Watchlist).filter_by(plate_number=plate_number).one_or_none()
    if entry is None:
        entry = Watchlist(plate_number=plate_number, note=note, active=True)
        session.add(entry)
    else:
        entry.active = True
        if note is not None:
            entry.note = note
    session.commit()
    return entry


def remove_watch(session, plate_number: str) -> bool:
    """Deactivate a watchlist entry. Returns True if one was found."""
    plate_number = plate_number.upper().strip()
    entry = session.query(Watchlist).filter_by(plate_number=plate_number).one_or_none()
    if entry is None:
        return False
    entry.active = False
    session.commit()
    return True


def list_watch(session) -> list[Watchlist]:
    return session.query(Watchlist).filter(Watchlist.active.is_(True)).all()


# --- Alerting -------------------------------------------------------------- #
class Alerter:
    """Fires (throttled) alerts when a watchlisted plate is detected."""

    def __init__(
        self, session_factory, notifier: Notifier, cooldown_seconds: int = 300
    ) -> None:
        self._Session = session_factory
        self._notifier = notifier
        self.cooldown = timedelta(seconds=cooldown_seconds)

    def process(self, detection_id: int) -> Alert | None:
        """Check a detection against the watchlist and alert if it matches.

        At most one alert per plate per cooldown window. Returns the Alert row
        (with ``delivered`` set by the notifier) or None if nothing fired.
        """
        with self._Session() as session:
            det = session.get(Detection, detection_id)
            if det is None:
                return None

            watched = (
                session.query(Watchlist)
                .filter(
                    Watchlist.plate_number == det.plate_number,
                    Watchlist.active.is_(True),
                )
                .one_or_none()
            )
            if watched is None:
                return None

            # Throttle: skip if we alerted on this plate within the cooldown.
            cutoff = utcnow() - self.cooldown
            recent = (
                session.query(Alert)
                .filter(Alert.plate_number == det.plate_number, Alert.created_at >= cutoff)
                .first()
            )
            if recent is not None:
                return None

            message = (
                f"Watchlisted plate {det.plate_number} seen on stream "
                f"{det.stream_id}"
                + (f" — {watched.note}" if watched.note else "")
            )
            alert = Alert(
                plate_number=det.plate_number,
                detection_id=det.id,
                stream_id=det.stream_id,
                message=message,
                created_at=utcnow(),
                delivered=False,
            )
            session.add(alert)
            session.commit()

            payload = {
                "plate_number": det.plate_number,
                "stream_id": det.stream_id,
                "detection_id": det.id,
                "seen_at": det.seen_at,
                "message": message,
            }
            alert.delivered = self._notifier.notify(payload)
            session.commit()
            return alert
