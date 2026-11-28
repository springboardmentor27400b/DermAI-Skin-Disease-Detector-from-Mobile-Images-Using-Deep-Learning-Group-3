# Milestone 2 checklist (Weeks 3-4): image processing, lesion detection and classification

| Task from the brief | Status | Where |
|---|---|---|
| Image quality assessment | Done in M1; thresholds still provisional (calibrate in step 1 below) | backend/app/preprocessing/quality.py |
| Preprocessing pipeline | Done: now crops the **lesion ROI** (centre crop only as fallback); `enhance` switch for ablations | preprocessing/pipeline.py |
| Lesion detection | Done (classical, no masks needed): colour-model + GrabCut, extra spots counted, outline overlay | preprocessing/lesion.py, ml/segment_review.py |
| Baseline classification model | Code ready: `simple_cnn` from scratch | ml/models.py |
| Transfer learning | Code ready: head warm-up then fine-tune, lower backbone LR | ml/train.py |
| Train multiple CNN architectures | Code ready: resnet18/50, densenet121, efficientnet_b0, mobilenet_v3_large, convnext_tiny | ml/run_experiments.py |
| Handle class imbalance | Code ready: weighted loss, focal loss, balanced sampler (one flag, compare them) | ml/losses.py, `--imbalance` |
| Data augmentation | Done: crop, flips, 90-degree rotations, mild colour jitter, blur (basic or TrivialAugment) | ml/data_module.py |
| Generate prediction results | Done: upload runs the deployed model; top-3, calibrated confidence, caveats, low-confidence flag; re-analyse endpoints | backend/app/inference, services/analysis.py |
| Compare model performance | Code ready: pooled out-of-fold metrics, patient-level bootstrap CI, charts | ml/compare_models.py |
| Classification reports | Code ready: per-class P/R/F1, sensitivity, specificity, AUC, MCC, ECE, confusion matrices | ml/metrics.py, reports/m2/ |
| Select best baseline | Code ready: `best_baseline.json` | ml/compare_models.py |

**"Code ready" means written and smoke-tested on synthetic data only.** No real model has been trained yet: that needs your PAD-UFES-20 images and ideally a GPU. The real numbers come from step 4 below.

## Added after the module-by-module review
| Module | Added | Where |
|---|---|---|
| 3 Capture & upload | **Crop and rotate editor** (90-degree steps, drag-to-crop, re-checked by the server); blank-border (incomplete photo) check | frontend/src/components/ImageEditor.tsx, preprocessing/skin.py |
| 4 Preprocessing | **Hair removal** (line-closing detector that leaves small round lesions alone, then inpainting); skin-region detection | preprocessing/hair.py, skin.py |
| 5 Segmentation | **Skin region detection**; **U-Net, Attention U-Net, DeepLabV3** trainers with Dice, IoU, pixel accuracy, sensitivity, specificity and Hausdorff; a deployed segmenter automatically replaces the colour model; annotation sampler | ml/seg_models.py, seg_metrics.py, train_seg.py, sample_for_annotation.py, inference/segmenter.py |
| 10 Training | **Checkpoint management** (`last.pt`, `--resume`, top-k checkpoints); **hyperparameter tuning** (random search ranked on validation only) | ml/train.py, ml/tune.py |
| 11 Quality | **Occlusion**, **excessive background** (skin fraction), **hair**, blank-border checks (informational: they can lower good to acceptable, never reject); quality metrics against your own labels | preprocessing/quality.py, ml/quality_eval.py |
| 15 Reports | **PDF, JSON and CSV reports** per case or image: case and image info, quality result, lesion, predicted condition, confidence, top-N, model version, summary, disclaimer. Content follows the caller's role. Risk category and explainability say "not available in this version" until Milestone 3 | backend/app/services/report.py, api/routes/reports.py, CaseDetail buttons |

**Fixing lesion detection (workflow)**
1. Pick photos, half of them cases the old detector missed: `sample_for_annotation.py --n 150 --lesions-csv data/pad_ufes_20/roi256/lesions.csv --hard-frac 0.5`
2. Annotate (on a desktop; about 1 hour): `annotate_masks.py --images data/to_annotate --masks data/masks --prefill` (the old outline is shown first; accept with S or fix it).
3. Train with 5-fold cross-validation (GPU, resumable): `train_seg.py --images data/to_annotate --masks data/masks --out runs/seg/unet_cv --cv 5 --export-dir ../backend/models`
4. Measure old vs new on the same photos: `compare_detectors.py --images data/to_annotate --masks data/masks --unet-cv runs/seg/unet_cv/cv_scores.csv`
4b. Diagnose and tune cheaply (no retraining): `review_segmentation.py --images data/to_annotate --masks data/masks --runs runs/seg/unet_cv --cv 5` re-scores with cleanup and flip averaging and draws the worst photos.
4c. Clean the labels: `annotate_masks.py --images data/to_annotate --masks data/masks --redo reports/segmentation/worst_cases.txt` reopens the photos scoring below Dice 0.5 with their saved masks. Annotation rule used in this project: outline the lesion itself (the raised, crusted, pigmented or ulcerated tissue the diagnosis refers to), tight; exclude surrounding redness, pen-ink rings and separate neighbouring spots; with several spots use the one nearest the centre; skip (K) when the edge cannot be seen. Retrain into a NEW `--out` folder (a finished folder is skipped on resume). Because the re-check was prompted by the first round, report the second-round Dice as somewhat optimistic.
5. Copy `segmentation.ts.pt` and `segmentation.json` into `backend/models/`, restart the API. The classifier does not need retraining (the centre-crop result showed it does not depend on the crop).

**Still not possible without your input or new data**
- Training a segmentation model needs lesion masks: annotate ~150 photos (`sample_for_annotation.py`), then `train_seg.py`.
- Normal/abnormal classification needs healthy-skin photos; PAD-UFES-20 has none.
- Mask R-CNN, YOLO, U-Net++ and transformer segmenters are not implemented.
- The informational quality thresholds (skin fraction 0.5, hair 0.06, occlusion 0.12) are untested on your photos; run `quality_audit.py` and check the new flag rates.
- React Native app: the web app captures through the browser camera; a native app is Milestone 4 scope.
- Explainability visualisation and risk categories in reports: Milestone 3.

## What to run (from `ml/`, after `pip install -r ../requirements-ml.txt`)
1. **Check the quality thresholds** (open item from M1): `quality_review.py`, see docs/quality_thresholds.md.
2. **Fresh splits** (does not touch your old ones): `python prepare_dataset.py --metadata data/pad_ufes_20/metadata.csv --images data/pad_ufes_20/images --out data/splits_v2 --kfold 5`
3. **Cache lesion ROI crops and eyeball the detector**
   `python precompute_rois.py --images data/pad_ufes_20/images --out data/pad_ufes_20/roi256`
   `python segment_review.py --images data/pad_ufes_20/images` then open `reports/segmentation/lesion_detection_sample.png`. Fix or tune the detector before training if outlines are wrong (hair, shadows, rulers, several lesions).
4. **Train and compare** (about 6 models x 5 folds; use a GPU, Colab is fine)
   `python run_experiments.py --archs simple_cnn,resnet50,densenet121,efficientnet_b0,mobilenet_v3_large,convnext_tiny --folds data/splits_v2/folds.csv --cache data/pad_ufes_20/roi256 --out runs/m2 --epochs 30`
   Quick trial first: add `--only-folds 0 --epochs 5`.
   `python compare_models.py --runs runs/m2 --out reports/m2`
5. **Imbalance ablation** on the best architecture: repeat step 4 with `-- --imbalance focal` and `-- --imbalance sampler` into `runs/m2_focal`, `runs/m2_sampler`, and compare.
6. **Deploy the winner**
   `python train.py --arch <best> --folds data/splits_v2/folds.csv --cache data/pad_ufes_20/roi256 --final --out runs/final/<best>`
   `python export_model.py --run runs/final/<best> --version v1.0-<best> --models-dir ../backend/models --comparison reports/m2/comparison.json`
   Restart the API (or `POST /api/models/reload` as admin), then `POST /api/models/reanalyze` to classify earlier uploads.

## Things to state honestly in the Week 4 report
- Results are **pooled out-of-fold, patient-grouped 5-fold CV**; there is no separate untouched test set. The fold used for early stopping and temperature fitting is never the test fold.
- Melanoma has about 36 patients: its per-class numbers have wide uncertainty. Read the bootstrap interval, and do not claim a ranking between models whose intervals overlap.
- The deployment model (`--final`) has no held-out score of its own; its expected performance is the CV estimate.
- Lesion detection is unsupervised and unvalidated against masks (PAD-UFES-20 has none). Report the by-eye review, or Dice/IoU if you annotate ~50 masks (`segment_review.py --masks`).
- 35% of images lack clinical metadata and the non-biopsied labels (ACK, NEV, SEK) are clinical judgements, so the label noise sets a ceiling on accuracy.
- Skin-tone coverage is narrow (Fitzpatrick I-III dominate). Do not claim the model works across skin tones.
- `LOW_CONFIDENCE_THRESHOLD` (0.5) is a provisional flag, not a clinical threshold. Risk categories remain Milestone 3 and must come from dataset labels or an agreed protocol.

## Deferred to Milestone 3
Vision Transformer / Swin, ensembles, Grad-CAM and other explainability, risk categories, confidence dashboards, U-Net segmentation (needs masks).

