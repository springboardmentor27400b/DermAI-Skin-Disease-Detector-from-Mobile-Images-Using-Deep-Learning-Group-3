# Image-quality thresholds

The upload check rates each photo **good**, **acceptable** or **poor** from three measurements on a copy resized to at most 512 px:
sharpness (variance of the Laplacian), brightness (mean grey level) and contrast (standard deviation of grey level).
Poor photos are not processed and must be retaken.

## What the audit found (PAD-UFES-20, 2,298 real phone photos)
With the original cut-offs (blur 40 / 100, contrast 15 / 28) the check was far too strict for real skin photos:

| | Original cut-offs |
|---|---|
| Rated good | 17.0% |
| Rated acceptable | 47.3% |
| Rated **poor** (would be rejected) | **35.7%** |
| Flagged blurred | 32.2% |
| Flagged low or very low contrast | 68.5% |

Measured distributions (5th / 25th / 50th / 75th / 95th percentile): blur 13.5 / 32.6 / 69.4 / 182.7 / 735.6, contrast 13.1 / 18.4 / 23.7 / 30.1 / 42.0, brightness 106.7 / 127.7 / 142.2 / 157.0 / 180.1.
Two causes: skin is smooth, so the Laplacian measure reads ordinary skin photos as soft, and skin photos naturally have low contrast. Brightness was fine (almost nothing flagged dark or overexposed).

## Provisional cut-offs now in use
| Measurement | Poor below | Acceptable below | Source |
|---|---|---|---|
| Sharpness | 13 | 33 | 5th and 25th percentile of the dataset |
| Contrast | 13 | 18 | 5th and 25th percentile of the dataset |
| Brightness (dark) | 35 | 60 | unchanged |
| Brightness (bright) | above 225 | above 205 | unchanged |

Each of the two percentile cuts flags about 5% of the dataset, so at most about 10% of these photos are now rated poor.

## Result after the change (audit re-run on your machine)
| | Original cut-offs | Provisional cut-offs |
|---|---|---|
| Rated good | 17.0% | **61.6%** |
| Rated acceptable | 47.3% | 29.9% |
| Rated poor | 35.7% | **8.5%** |
| Flagged blurred | 32.2% | 4.4% |
| Very low contrast | 10.3% | 5.0% |

Poor stays under the 10% ceiling that two 5th-percentile cut-offs allow.

## These are provisional, and why
Percentile cut-offs assume the dataset is mostly good quality, which is reasonable for a curated clinical dataset but is an assumption. They will always flag the worst 5%, whether or not those photos are really unusable. Before relying on them:
1. Run `python quality_audit.py ...` again and check the new rates (`reports/quality/summary.json`).
2. Run `python quality_review.py --images ... --by blur` (and `--by contrast`) and look at the sheets. The lowest band should look clearly unusable and the top bands fine.
3. In Milestone 2, label a few hundred photos good or poor by hand and choose the cut-offs that best match your labels.

## Changing them
Set environment variables (or edit `backend/app/core/config.py`) and restart the backend:
`QUALITY_BLUR_POOR`, `QUALITY_BLUR_ACCEPTABLE`, `QUALITY_CONTRAST_POOR`, `QUALITY_CONTRAST_ACCEPTABLE`, `QUALITY_DARK_POOR`, `QUALITY_DARK_ACCEPTABLE`, `QUALITY_BRIGHT_ACCEPTABLE`, `QUALITY_BRIGHT_POOR`.
To restore the original behaviour use blur 40 / 100 and contrast 15 / 28. The web app's meters read the live values from the server, so the ticks always match.

## Resolution
Uploads need a shorter side of at least 224 px. Fifteen dataset images (0.7%) are smaller, so they cannot be uploaded to the web app.

