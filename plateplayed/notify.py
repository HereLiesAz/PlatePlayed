"""Alert delivery channels: logging and optional webhook (stdlib only)."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Protocol

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    def notify(self, payload: dict) -> bool:
        ...


class LogNotifier:
    """Writes alerts to the log. Always "delivers"."""

    name = "log"

    def notify(self, payload: dict) -> bool:
        logger.warning("ALERT: %s", payload.get("message", payload))
        return True


class WebhookNotifier:
    """POSTs the alert payload as JSON to a webhook URL."""

    name = "webhook"

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        self.url = url
        self.timeout = timeout

    def notify(self, payload: dict) -> bool:
        data = json.dumps(payload, default=str).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except Exception as exc:
            logger.error("Webhook delivery failed: %s", exc)
            return False


class MultiNotifier:
    """Fan-out to several notifiers; delivered if any succeeds."""

    def __init__(self, notifiers: list[Notifier]) -> None:
        self._notifiers = notifiers

    def notify(self, payload: dict) -> bool:
        results = [n.notify(payload) for n in self._notifiers]
        return any(results)


def build_notifier(webhook_url: str | None = None) -> Notifier:
    """Always log; also POST to a webhook when a URL is configured."""
    notifiers: list[Notifier] = [LogNotifier()]
    if webhook_url:
        notifiers.append(WebhookNotifier(webhook_url))
    return MultiNotifier(notifiers)
