# Risk categories (Milestone 3)

The brief says risk categories must come from dataset labels, validated criteria or a project-defined research protocol, and that thresholds must not be invented. DermAI's protocol therefore contains **no hard-coded clinical numbers**: they are fitted from the model's own out-of-fold validation predictions by `ml/risk_protocol.py` and stored next to the model as `risk.json`.

## Definition
- **Malignant classes** (dataset-defined): BCC, SCC, MEL. Every one of them is biopsy-confirmed in PAD-UFES-20.
- `p_malignant` = sum of the model's calibrated probabilities for those classes.
- **Low Risk**: `p_malignant < t_low`. `t_low` is the lowest cut that keeps at least the target sensitivity (default 90%) of malignant validation images at or above it.
- **High Risk**: `p_malignant >= t_high`. `t_high` is the cut below which at least the high-specificity share (default 90%) of non-malignant validation images fall.
- **Moderate Risk**: in between.
- **Requires Clinical Review**: replaces Low Risk when the lesion could not be located (a reassuring label must not rest on a guess). Worrying results are never softened this way.
- No model, or no `risk.json`: no category. The UI, reports and notifications say it is not available.

## How to produce it
```bash
python risk_protocol.py --runs runs/m2_sampler/convnext_tiny --target-sens 0.90 --high-spec 0.90 --out risk.json
python export_model.py --run runs/final/convnext_tiny --version v1.1-convnext_tiny --models-dir ../backend/models --risk risk.json
```
For an ensemble, point `--runs` at the folder written by `ensemble.py` (for example `runs/m3_ens/ens_equal`) and pass `--risk` to `export_ensemble.py`.

## What to state in the report
- It is a **screening aid**, not a diagnosis. Wording in the app: "likelihood of a skin-cancer pattern", "clinical review recommended".
- Thresholds are fitted on pooled validation predictions and reported on the pooled test predictions of the same runs. Each image is validation for one fold and test for another, so the test figures are slightly optimistic (two scalar thresholds only).
- Melanoma has about 36 patients, so melanoma-specific behaviour has wide uncertainty. Read the cancer-versus-other numbers, not per-class claims.
- Skin-tone coverage is narrow (Fitzpatrick I to III dominate): the protocol is not validated for darker skin.
- The sensitivity target is a project choice. A stricter target lowers `t_low`, so fewer images are labelled Low Risk.

