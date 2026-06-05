# PlatePlayed design docs

Scoping and design notes for proposed work. These are plans, not yet built.

| Doc | Summary | Status |
| --- | --- | --- |
| [scoping-make-model.md](scoping-make-model.md) | Add vehicle **make / model** recognition (fine-grained classification on the vehicle crop). | Proposed |
| [scoping-vehicle-taxonomy.md](scoping-vehicle-taxonomy.md) | Richer vehicle **taxonomy** — emergency / construction / heavy / commercial categories beyond COCO. | Proposed |

Both extend the existing `plateplayed/vehicle.py` analyzer and the same
pluggable-detector-with-stub-fallback pattern used throughout the codebase, so
they slot in without disturbing the streams → detect → track → record → API
pipeline. Each is gated behind config (opt-in, default off) and ships an
evaluation script, because the central risk for both is **accuracy on real
low-resolution street-cam footage** — which must be measured per deployment
before the feature is trusted.
