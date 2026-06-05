# Scoping: Make / Model recognition

Status: **proposed** · Owner: TBD · Builds on the existing `vehicle.py` analyzer.

## Goal

For each logged plate, add the vehicle's **make** (e.g. Toyota) and **model**
(e.g. Camry), with a confidence score, alongside the type + color we already
capture. Year is a stretch goal.

## Why this is the hard tier

`fast-alpr` and the COCO YOLO detector don't do make/model — it's a separate
**fine-grained image classification** problem. The accuracy risk is real:
public traffic/scene streams give us low resolution, oblique angles, motion
blur, compression artifacts, and partial occlusion — exactly the conditions
under which fine-grained classifiers degrade most. A model that scores 95% on
clean catalog photos can fall to 50–70% on a 480p street cam. So the plan
treats **measurement before commitment** as the core principle.

## Approaches

| Approach | Pros | Cons |
| --- | --- | --- |
| **A. Commercial MMC API** (Plate Recognizer, Rekor) | Best accuracy, no training, returns make/model/color/year | Per-call cost, sends frames to a third party (privacy/ToS), external dependency |
| **B. Open pretrained classifier** fine-tuned on a surveillance dataset | Self-hosted, free, fits our stub-able interface | We own accuracy + retraining; domain gap to manage |
| **C. Train from scratch** | Full control | Most effort; needs large labeled data; rarely worth it |

**Recommendation: B**, with A available as a drop-in alternate backend for
users who accept the cost/privacy trade. Both hide behind one interface so the
rest of the system doesn't care which is active.

## Data

Order of preference by domain match to street cams:

1. **BoxCars116k** — 116k images from real traffic surveillance cameras,
   make/model/year labels, oblique angles. *Best domain match.*
2. **CompCars (surveillance subset)** — front-view surveillance images, ~280
   models.
3. **VMMRdb** — ~9k make/model/year classes from web photos. Broadest taxonomy
   but web-domain (clean photos) → bigger domain gap; good for pretraining.
4. **Stanford Cars** — 196 classes, clean catalog shots. Useful for a baseline,
   weak for our domain.

Practical recipe: pretrain/transfer from a broad set (VMMRdb / Stanford), then
fine-tune on the surveillance-domain set (BoxCars), then **fine-tune again on a
few thousand crops harvested from our own streams** (the pipeline already saves
vehicle crops — see "Harvesting" below). Regional fleets differ (US vs EU vs
JP); scope the taxonomy to the deployment region first.

## Model

- **Input**: the vehicle crop the `VehicleAnalyzer` already produces (we reuse
  the YOLO vehicle box, so no new detection stage).
- **Backbone**: EfficientNet-B0/B3 or ConvNeXt-Tiny — strong fine-grained
  accuracy at modest CPU cost; export to ONNX to match our runtime.
- **Heads**: hierarchical — predict make, then model conditioned on make
  (reduces the long-tail problem and gives a useful answer even when the model
  head is unsure: "Toyota, model uncertain").
- **Output**: top-1 make + model + confidence, plus optional top-k for review.

## Integration (fits the current architecture)

- New module `plateplayed/make_model.py` mirroring `vehicle.py`:
  `MakeModelClassifier` protocol, `OnnxMakeModelClassifier`, `StubClassifier`,
  `build_make_model_classifier("auto"|"onnx"|"api"|"stub")`.
- `VehicleAnalyzer.associate()` gains an optional classifier; when present it
  runs on the same crop and fills make/model on the returned `VehicleInfo`.
- **Schema** (Alembic migration): add nullable
  `vehicle_make`, `vehicle_model`, `vehicle_make_model_confidence` to
  `detections`. One-file migration, like `c7c8804`.
- **Config**: `make_model:` block — `enabled` (default **false**, opt-in),
  `backend`, `model_path`/`api_key`, `min_confidence`, `region`.
- **API/dashboard**: surface make/model on the detection card and as filters.
- Heavy deps go in `requirements-ml.txt`; absence → stub → fields stay null.

## Harvesting + labeling loop

The running system is its own data engine:

1. Enable vehicle crops (already supported); accumulate crops with type/color.
2. Weak-label with backend A or an open model; sample for human verification
   in a small review UI (could extend the dashboard).
3. Fine-tune on the verified set; re-evaluate; repeat (active learning —
   prioritize low-confidence / disagreement cases).

## Evaluation (gate before shipping)

- Build a **labeled holdout from the actual target streams** (a few hundred
  crops, human-verified). This, not dataset benchmarks, is the acceptance test.
- Report top-1 / top-5 make accuracy, make+model accuracy, per-class
  precision/recall, and a confusion matrix; track calibration so the
  confidence threshold is meaningful.
- Ship `scripts/eval_make_model.py` so accuracy is reproducible per deployment.

## Accuracy expectations & risks

- Expect **make** to be considerably more reliable than **make+model**; lead
  with make and treat model as best-effort with a visible confidence.
- Long tail: new/rare models will be wrong or low-confidence — surface "unknown"
  rather than guess.
- Privacy: make/model + plate meaningfully increases identifiability. Keep it
  behind auth (already implemented), document retention, and make the feature
  opt-in.

## Phased plan & rough effort

| Phase | Work | Effort |
| --- | --- | --- |
| 0 | Interface + schema + config + stub, wired end-to-end (no real model) | ~1 day |
| 1 | Backend A (commercial API) adapter + dashboard surfacing | ~1–2 days |
| 2 | Eval harness + labeled holdout from real streams | ~2 days |
| 3 | Backend B: ONNX classifier fine-tuned on BoxCars, measured vs holdout | ~1–2 weeks |
| 4 | Harvesting/active-learning loop + periodic re-fine-tune | ongoing |

## Open questions

- Which region(s) / fleet to scope the taxonomy to first?
- Is sending frames to a commercial API acceptable, or self-hosted only?
- Is "make only" (dropping model) an acceptable v1 if model accuracy is poor?
