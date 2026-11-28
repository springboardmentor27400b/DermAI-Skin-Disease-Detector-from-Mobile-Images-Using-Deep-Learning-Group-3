# Milestone 3 checklist (Weeks 5-6): advanced AI, explainability and risk analysis

| Task from the brief | Status | Where |
|---|---|---|
| Advanced CNN architecture | Code ready: `convnext_small`, `efficientnet_v2_s` (ConvNeXt-Tiny is already the M2 winner) | ml/models.py |
| Transformer-based model | Code ready: `swin_t`, `vit_b_16` (DeiT not included) | ml/models.py |
| Ensemble | Code ready: validation-weighted or equal averaging from saved predictions, plus one-file deployable export | ml/ensemble.py, ml/export_ensemble.py |
| Optimise hyperparameters | `tune.py` from M2 works with every new architecture | ml/tune.py |
| Confidence estimation | Done: temperature-calibrated probabilities (M2), ECE reported, ensemble keeps calibration | classifier.py, metrics.py |
| Explainable AI | Done in code: Grad-CAM and Grad-CAM++ on the deployed model (ensembles averaged), lesion-overlap score | backend/app/inference/explain.py, ml/export_model.py |
| Grad-CAM visualisations | Done: attention overlay stored per image, shown in case view, analysis screen and PDF report | services/analysis.py, Analysis.tsx |
| Risk classification | Done: protocol fitted from data, 4 categories, see docs/risk_protocol.md | inference/risk.py, ml/risk_protocol.py |
| Analysis dashboard | Done: predicted-condition and risk breakdowns, deployed-model performance card, notifications | Dashboard.tsx, ModelPerformance.tsx |
| Medical image analysis screen | Done: original, preprocessed, lesion mask, attention map, prediction, risk, version, timestamp, comparison toggles | pages/Analysis.tsx |
| Prediction history | Done in M2; now links to the analysis screen | History.tsx |
| Also added (brief sections 17, 18, 15) | Notifications (informational to high), model registry with deploy / roll back, reports with risk and attention map | api/routes/notifications.py, models.py, services/report.py |

**"Code ready" means written and syntax-checked but not yet run on real data.** No new architecture has been trained, no ensemble evaluated and no risk protocol fitted on your real predictions: that needs your GPU runs (commands below).

## What was verified here
- Backend: all tests pass, including 7 new Milestone 3 tests (risk bands, notifications, model registry and rollback, single-analysis authorisation, route shadowing). One test needs the pre-built `frontend_dist`, which is not in the source tree.
- Frontend: `tsc` type-check and `vite build` pass.
- `risk_protocol.py` and `ensemble.py` ran end to end on synthetic predictions.
- **Not verified here:** the PyTorch paths (`export_model.py` split, `export_ensemble.py`, Grad-CAM at inference, training of the new architectures) because PyTorch could not be installed in the build environment. The backend Grad-CAM test is written and runs when torch is installed (`pip install -r backend/requirements-inference.txt`). `export_cam` asserts that the split network reproduces the original output, so a wrong split fails loudly at export time.

## What to run (from `ml/`)
1. **Train the new architectures** (GPU; quick trial first with `--only-folds 0 --epochs 5`)
   `python run_experiments.py --archs swin_t,vit_b_16,convnext_small,efficientnet_v2_s --folds data/splits_v2/folds.csv --cache data/pad_ufes_20/roi256 --out runs/m3 --epochs 30 -- --imbalance sampler --lr 1e-4 --workers 2`
   `python compare_models.py --runs runs/m3 --out reports/m3`
2. **Ensemble from saved predictions** (no GPU)
   `python ensemble.py --out runs/m3_ens --members convnext=runs/m2_sampler/convnext_tiny swin=runs/m3/swin_t densenet=runs/m2/densenet121`
3. **Pick the deployment model** by pooled macro-F1 with its bootstrap interval. If an ensemble is within about 0.02 of the best single model, prefer the single model (simpler, and the gain is not reliable).
4. **Fit the risk protocol** on the chosen model: `python risk_protocol.py --runs <its run folder> --out risk.json`
5. **Train final model(s)** with `train.py --final` for the chosen architecture(s), then export:
   single: `python export_model.py --run runs/final/<arch> --version v1.1-<arch> --models-dir ../backend/models --comparison reports/m3/comparison.json --risk risk.json`
   ensemble: `python export_ensemble.py --runs runs/final/a runs/final/b --version v2.0-ensemble --models-dir ../backend/models --evaluation runs/m3_ens/evaluation.json --eval-key ens_equal --risk risk.json`
6. Restart the API (or Administration > Models > Reload), then **Analyse pending images** or **Re-analyse all** to give earlier uploads attention maps and risk levels.

## Things to state honestly in the Week 6 report
- Same caveats as Milestone 2 (pooled out-of-fold CV, melanoma about 36 patients, label noise in non-biopsied classes, narrow skin-tone coverage).
- ViT-B/16 has about 86M parameters and about 1,600 training images per fold; it may well lose to ConvNeXt. Report negative results plainly.
- Grad-CAM shows where the model looked, not that it is right. The "attention inside lesion" figure is a consistency metric from the brief, not a correctness measure.
- Ensemble weights are chosen on each fold's validation data only; the deployed ensemble uses equal weights unless you pass `--weights`.
- Risk categories are a research protocol (docs/risk_protocol.md), not a validated clinical triage tool. There is no "critical" alert level on purpose.
- ViT has no Grad-CAM export (attention rollout would be needed); a ViT-only deployment would work without attention maps.

## Deferred to Milestone 4
React Native app, Docker/cloud deployment hardening, monitoring and logging, end-to-end and performance testing, user guide, final presentation.

