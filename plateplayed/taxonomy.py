"""Rich vehicle taxonomy classification (Phase 0: interface + stub).

Classifies a vehicle crop into categories beyond COCO's car/truck/bus —
emergency / construction / heavy / commercial. The real two-stage classifier is
not implemented yet — see ``docs/scoping-vehicle-taxonomy.md``.
``build_taxonomy_classifier("auto")`` returns a stub.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TaxonomyResult:
    """A category prediction for a vehicle crop."""

    category: str | None
    confidence: float


class TaxonomyClassifier(Protocol):
    def classify(self, crop: np.ndarray) -> TaxonomyResult | None:
        ...


class StubTaxonomyClassifier:
    """No-op classifier. Always returns ``None`` (no prediction)."""

    name = "stub"

    def classify(self, crop: np.ndarray) -> TaxonomyResult | None:  # noqa: ARG002
        return None


def build_taxonomy_classifier(
    name: str = "auto",
    model_path: str | None = None,
    version: str = "v1",
    min_confidence: float = 0.5,
) -> TaxonomyClassifier:
    """Construct a taxonomy classifier.

    Phase 0 only ships the stub; ``auto`` returns it. Explicitly requesting an
    unimplemented backend raises so misconfiguration is obvious.
    """
    name = (name or "auto").lower()
    if name in ("stub", "auto"):
        if name == "auto":
            logger.info("Vehicle taxonomy classifier not yet implemented — using stub.")
        return StubTaxonomyClassifier()
    if name == "onnx":
        raise NotImplementedError(
            "taxonomy backend 'onnx' is not implemented yet "
            "(see docs/scoping-vehicle-taxonomy.md)"
        )
    raise ValueError(f"Unknown taxonomy backend: {name!r}")
