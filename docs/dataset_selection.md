# Dataset selection

## Decision
**PAD-UFES-20** (smartphone photos of skin lesions with clinical metadata, Federal University of Espírito Santo, Brazil).
HAM10000 (dermoscopic images) is kept as an optional extra for pre-training; the scripts support it with `--dataset ham10000`.

## Why PAD-UFES-20
- DermAI analyses **photos taken with a phone**. PAD-UFES-20 is made of exactly that, so there is no dermoscopy-to-phone domain gap to explain away.
- It records useful clinical context per image: patient and lesion IDs, age, sex, body region, Fitzpatrick skin type, symptoms (itch, growth, pain, change, bleeding) and whether the lesion was biopsied.
- Patient IDs allow a leak-free split.

## Target conditions (6)
| Code | Condition |
|---|---|
| ACK | Actinic keratosis |
| BCC | Basal cell carcinoma |
| MEL | Melanoma |
| NEV | Melanocytic nevus |
| SCC | Squamous cell carcinoma (Bowen's disease is merged into this class) |
| SEK | Seborrheic keratosis |

Measured on the metadata in this project (`ml/reports/eda_pad_ufes_20/summary.json`): **2,298 images, 1,373 patients, 1,891 lesions** (a lesion is a patient plus lesion number, since lesion numbers repeat across patients).

| Class | Images | Patients | Biopsy-confirmed |
|---|---|---|---|
| BCC | 845 | 513 | 100% |
| ACK | 730 | 525 | 24% |
| NEV | 244 | 185 | 25% |
| SEK | 235 | 176 | 6% |
| SCC | 192 | 133 | 100% |
| MEL | 52 | 36 | 100% |

## Known limitations (state these in the final report)
1. **Small dataset, rare melanoma.** Melanoma has 52 images from only 36 patients (2.3% of the data). A fixed split leaves about 7 melanoma images in each of validation and test, so report cross-validated results (`--kfold 5`) and per-class metrics, never accuracy alone.
2. **Class imbalance of 16.2 to 1** (BCC 845 vs MEL 52). Use weighted or focal loss, balanced sampling, and macro-F1 / balanced accuracy. Suggested weights are in `summary.json`.
3. **Several images per patient.** Splits are grouped by patient (`prepare_dataset.py` asserts zero overlap), otherwise metrics look better than they are. 179 patients have more than one diagnosis.
4. **Label reliability differs by class.** Every BCC, SCC and melanoma was confirmed by biopsy, but only 24% of actinic keratoses, 25% of nevi and 6% of seborrheic keratoses were. Most benign labels are clinical judgements.
5. **The clinical questionnaire is missing for 804 images (35%).** These are all non-biopsied lesions (447 ACK, 188 SEK, 169 NEV), so missing metadata is itself correlated with the label. Do not feed these fields to the model.
6. **Skin-tone coverage is narrow.** Of the 1,494 images with a recorded Fitzpatrick type: type 1 has 153, type 2 has 876, type 3 has 392, type 4 has 62, type 5 has 10 and type 6 has 1. Do not claim the model works across skin tones; say this limitation plainly.
7. **Variable image size and quality (measured on the images).** All 2,298 files are present and readable. Image sizes range from 147 px to about 3,476 px, with a median of 779 px, and the most common size is 750 x 750. Fifteen images (0.7%) have a shorter side under 224 px, the model input size, so they need upscaling or exclusion in training. Mean brightness is 142 and mean contrast is 25 (grey-level standard deviation). The app's quality check was tuned on test images, so run `quality_audit.py` to see how its thresholds treat these photos before calibrating them in Milestone 2.
8. **Licence.** Check the licence on the dataset's download page before any use beyond coursework.

## Setup
Put the data in `ml/data/pad_ufes_20/` (all three image parts merged into `images/`, plus `metadata.csv`), then follow `ml/README.md`.

## Privacy
Use only public or de-identified data. Never enter names, contact details or identifiable photos (faces, tattoos, distinctive marks) into DermAI cases.

