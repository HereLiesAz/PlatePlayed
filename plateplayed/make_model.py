"""Vehicle make/model recognition (Phase 0: interface + stub).

Fine-grained classification of the vehicle crop. Real backends (a self-hosted
ONNX classifier, or a commercial MMC API) are not implemented yet — see
``docs/scoping-make-model.md``. ``build_make_model_classifier("auto")`` returns
a stub so the field stays null and the rest of the pipeline is unaffected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MakeModelResult:
    """A make/model prediction for a vehicle crop."""

    make: str | None
    model: str | None
    confidence: float


class MakeModelClassifier(Protocol):
    def classify(self, crop: np.ndarray) -> MakeModelResult | None:
        ...


class StubMakeModelClassifier:
    """No-op classifier. Always returns ``None`` (no prediction)."""

    name = "stub"

    def classify(self, crop: np.ndarray) -> MakeModelResult | None:  # noqa: ARG002
        return None


def build_make_model_classifier(
    name: str = "auto",
    model_path: str | None = None,
    min_confidence: float = 0.5,
    region: str | None = None,
) -> MakeModelClassifier:
    """Construct a make/model classifier.

    Phase 0 only ships the stub; ``auto`` returns it. Explicitly requesting an
    unimplemented backend raises so misconfiguration is obvious.
    """
    name = (name or "auto").lower()
    if name in ("stub", "auto"):
        if name == "auto":
            logger.info("Make/model classifier not yet implemented — using stub.")
        return StubMakeModelClassifier()
    if name in ("onnx", "api"):
        raise NotImplementedError(
            f"make/model backend {name!r} is not implemented yet "
            "(see docs/scoping-make-model.md)"
        )
    raise ValueError(f"Unknown make/model backend: {name!r}")
