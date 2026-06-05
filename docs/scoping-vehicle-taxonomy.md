# Scoping: Rich vehicle taxonomy (emergency / construction / heavy)

Status: **proposed** · Owner: TBD · Builds on the existing `vehicle.py` analyzer.

## Goal

Classify vehicles into a richer set than COCO's `car / truck / bus /
motorcycle` — specifically the categories that matter operationally:

- **Emergency**: police car, ambulance, fire truck
- **Construction / heavy equipment**: dump truck, cement mixer, excavator,
  loader, flatbed
- **Commercial**: semi/tractor-trailer, box truck, delivery van, pickup

…each with a confidence, attached to the plate like type/color are today.

## Why COCO isn't enough

The COCO detector collapses all of the above into `truck`, `car`, or `bus`.
Getting the finer categories needs a model that actually knows them. Emergency
vehicles are the hardest and the most sensitive: a false "police" tag has
real-world consequences, so this category needs a higher precision bar and
human review before it's trusted.

## Approaches

| Approach | Pros | Cons |
| --- | --- | --- |
| **A. Two-stage: existing YOLO → crop → fine-grained classifier** | Reuses our vehicle detector; image-level labels are cheap; easy to add classes | Two models; depends on the first stage finding the box |
| **B. Custom one-stage detector** (fine-tune YOLOv8/v9 on the taxonomy) | Single pass; localizes + classifies together | Needs bounding-box labels (expensive); retrain to add classes |
| **C. Heuristics / weak signals** (light-bar detection, livery color, OCR of "POLICE"/"AMBULANCE") | Cheap; no training; great as a bridge and as features | Brittle alone; regional livery differences |

**Recommendation: A as the backbone, C as supporting signals.** Two-stage reuses
the YOLO box we already compute, needs only image-level labels (far cheaper than
boxes), and lets us add categories incrementally. Fold in C — especially OCR of
vehicle text, which our plate pipeline can already read — to boost emergency
precision.

## Taxonomy strategy

Start small and high-confidence, expand with data:

- **v1**: `emergency` (binary), `heavy_equipment` (binary), `commercial_truck`,
  plus pass-through of COCO `car/bus/motorcycle`. Coarse but reliable.
- **v2**: split emergency → police / ambulance / fire; split heavy → excavator /
  dump / mixer / loader.

Coarse-first keeps early precision high and avoids confusing rare sub-types.

## Data

- **Construction / heavy equipment** (good open coverage):
  - **MOCS** — Moving Objects in Construction Sites, 13 categories incl.
    excavator, dump truck, concrete mixer. Strong fit.
  - **ACID** — Alberta Construction Image Dataset (heavy equipment).
  - **SODA** — site object detection.
- **Emergency vehicles** (sparse, scattered — expect to collect + label):
  - Kaggle "Emergency vs Non-Emergency" and assorted small fire/ambulance/
    police sets; generally need augmentation + our own harvested data.
- **Commercial trucks**: BDD100K (truck/bus) for context; subtypes need custom
  labeling.

Because emergency data is thin, lean on the **harvesting loop**: the running
pipeline saves vehicle crops; weak-label them (heuristics + any open model),
human-verify a sample, fine-tune, repeat. Active learning prioritizes the
uncertain cases.

## Model

- **Stage 1**: existing `YoloVehicleDetector` (unchanged) → vehicle box + crop.
- **Stage 2**: a compact CNN classifier (EfficientNet-B0 / MobileNetV3),
  ONNX-exported to match our runtime, run on the crop.
- **Supporting features (C)**: light-bar/beacon detector or color-pattern check;
  OCR of large vehicle text via the plate OCR engine. These can gate or boost
  the emergency decision (require classifier *and* a corroborating signal before
  tagging "police").

## Integration (fits the current architecture)

- New module `plateplayed/taxonomy.py`: `TaxonomyClassifier` protocol,
  `OnnxTaxonomyClassifier`, `StubClassifier`, `build_taxonomy_classifier(...)`.
- `VehicleAnalyzer` runs it on the same crop it already extracts and fills a new
  `category` (+ confidence) on `VehicleInfo`.
- **Schema** (Alembic migration): add nullable `vehicle_category`,
  `vehicle_category_confidence` to `detections`.
- **Config**: `taxonomy:` block — `enabled` (default **false**), `backend`,
  `model_path`, `taxonomy_version`, `min_confidence`,
  `emergency_requires_corroboration: true`.
- **API/dashboard**: show the category as a badge; let users filter by it.

## Evaluation (gate before shipping)

- Per-category **precision/recall on a holdout from the real streams**, with a
  confusion matrix. Emergency categories get a **higher precision threshold**
  (favor "unknown" over a wrong "police").
- Ship `scripts/eval_taxonomy.py` for reproducible per-deployment scoring.

## Accuracy expectations & risks

- **Construction/heavy**: distinctive shapes → expected to work reasonably.
- **Emergency**: hardest; livery varies by city/country; false positives are
  sensitive → require corroboration, keep human-in-the-loop, set a high bar.
- **Regional variation**: a model trained on one region's fleet/livery won't
  transfer cleanly; document the training region.
- **Ethics/privacy**: tracking emergency-service movements has surveillance
  implications. Keep behind auth (done), document retention, make opt-in, and
  consider excluding sensitive categories from any export by default.

## Phased plan & rough effort

| Phase | Work | Effort |
| --- | --- | --- |
| 0 | Interface + schema + config + stub, wired end-to-end | ~1 day |
| 1 | v1 coarse classifier on MOCS/ACID (heavy) + heuristics for emergency | ~1 week |
| 2 | Eval harness + real-stream holdout; tune thresholds | ~2 days |
| 3 | Harvesting loop; expand to v2 sub-categories as data allows | ongoing |
| 4 | Emergency corroboration (light-bar / vehicle-text OCR) | ~3–5 days |

## Open questions

- Which categories are actually must-haves vs nice-to-have for the use case?
- Deployment region(s), to scope livery/fleet and training data?
- Acceptable precision floor for emergency tags before they're shown at all?
- Any categories that should be excluded for policy reasons?
