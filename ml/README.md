# ML tooling (Milestone 1: dataset preparation, Milestone 2: training and comparison)

Primary dataset: **PAD-UFES-20** (smartphone photos). See `../docs/dataset_selection.md`.

## Where the data goes
```
ml/data/pad_ufes_20/
  images/        all images from the three zip parts, merged into one folder
  metadata.csv
```

## Run (from the ml/ folder, venv active, `pip install -r ../requirements.txt` done)
```bash
python eda.py --metadata data/pad_ufes_20/metadata.csv --images data/pad_ufes_20/images --out reports/eda --verify-images
python quality_audit.py --images data/pad_ufes_20/images --metadata data/pad_ufes_20/metadata.csv --out reports/quality
python prepare_dataset.py --metadata data/pad_ufes_20/metadata.csv --images data/pad_ufes_20/images --out data/splits --kfold 5
```
- `eda.py` writes charts and `summary.json` to `reports/eda/`: class distribution and imbalance, patients and images per patient, age, sex, body site, Fitzpatrick skin type, biopsy share, missing values, and an image integrity check (missing, unlisted, unreadable files).
- `prepare_dataset.py` refuses to overwrite an existing `train.csv` unless you pass `--force` (earlier splits already exist in `data/splits/`). It writes `train.csv`, `val.csv`, `test.csv`, `folds.csv`, `class_to_idx.json` and `split_report.json` to `data/splits/`. All images of one patient stay in the same split.
- `quality_audit.py` runs the app's own image-quality check over every image and reports the share rated good, acceptable or poor, the most common issues, a per-class breakdown, and the metric distributions with the thresholds drawn on. It writes `quality_scores.csv` for calibration in Milestone 2.
- `quality_review.py` turns the audit into contact sheets of images at chosen percentiles (`--by blur` or `--by contrast`) so you can judge the thresholds by eye. See `../docs/quality_thresholds.md`.
- `--dataset ham10000` switches both scripts to HAM10000 (optional pre-training data).
- `make_demo_metadata.py` creates a **synthetic** file so you can try the scripts first. Never report results from it.

## Milestone 2: lesion ROI, training, comparison, deployment
Install: `pip install -r ../requirements-ml.txt`. Full workflow and what to report: `../docs/milestone2_checklist.md`.

| Script | Purpose |
|---|---|
| `precompute_rois.py` | detect the lesion in every photo and cache the preprocessed ROI crop (same code as the API) |
| `segment_review.py` | contact sheet of lesion detections to judge by eye; Dice/IoU if you supply masks |
| `train.py` | one model, one fold: transfer learning, imbalance options, early stopping, temperature calibration, test predictions |
| `run_experiments.py` | many architectures x folds, resumable |
| `compare_models.py` | pooled out-of-fold metrics, bootstrap CI, charts, confusion matrices, best baseline |
| `export_model.py` | TorchScript package + `meta.json` for the API (`backend/models/<version>/`) |
| `models.py`, `losses.py`, `metrics.py`, `data_module.py` | model zoo, weighted/focal loss, metric suite, dataset and augmentation |
| `train_seg.py`, `seg_models.py`, `seg_metrics.py` | segmentation models (U-Net, Attention U-Net, DeepLabV3) once you have masks; exports to the API |
| `sample_for_annotation.py` | picks a diverse set of photos to annotate with masks |
| `tune.py` | random-search hyperparameter tuning ranked on validation macro-F1 |
| `quality_eval.py` | quality-classification, rejection and blur-detection metrics against your own labels |

## Milestone 3 scripts
| Script | Purpose |
|---|---|
| `models.py` | adds `convnext_small`, `efficientnet_v2_s`, `swin_t`, `vit_b_16` (use `--lr 1e-4` for the transformers) |
| `ensemble.py` | equal and validation-weighted ensembles from saved `val_probs.csv` / `test_probs.csv`, pooled metrics, `evaluation.json` |
| `risk_protocol.py` | fits the risk thresholds from validation predictions and writes `risk.json` (docs/risk_protocol.md) |
| `export_model.py` | now also writes `features.ts.pt` + `head.ts.pt` for Grad-CAM and copies `risk.json` |
| `export_ensemble.py` | packages several `--final` models as one deployable ensemble with averaged attention maps |

`train.py --resume` continues from `last.pt`; `--keep-top-k` keeps the best checkpoints in `checkpoints/`.

