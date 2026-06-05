# PlatePlayed design docs

Scoping and design notes. **Phase 0** (interface + schema + config + stub,
wired end-to-end) is built for both; the model-training phases remain proposed.

| Doc | Summary | Status |
| --- | --- | --- |
| [scoping-make-model.md](scoping-make-model.md) | Add vehicle **make / model** recognition (fine-grained classification on the vehicle crop). | Phase 0 built |
| [scoping-vehicle-taxonomy.md](scoping-vehicle-taxonomy.md) | Richer vehicle **taxonomy** — emergency / construction / heavy / commercial categories beyond COCO. | Phase 0 built |

Both extend the existing `plateplayed/vehicle.py` analyzer and the same
pluggable-detector-with-stub-fallback pattern used throughout the codebase, so
they slot in without disturbing the streams → detect → track → record → API
pipeline. Each is gated behind config (opt-in, default off) and ships an
evaluation script, because the central risk for both is **accuracy on real
low-resolution street-cam footage** — which must be measured per deployment
before the feature is trusted.
