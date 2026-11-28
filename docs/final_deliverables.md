# Final deliverables outline

## User guide (one section per role)
Patient: sign up, take a good photo (tips on the home page), quality check, upload, read the result and risk level, history, reports, research consent. Clinician: verification, opening a case for a patient, notes, comparing analyses, reports. Researcher / ML engineer: what de-identified means, filters, model versions. Administrator: verifying clinicians, models (deploy, roll back, re-analyse), audit log, metrics. Add "What the result does and does not mean" and troubleshooting (poor quality, low confidence, lesion not located).

## Final report
Problem and scope; architecture; dataset and its limits; preprocessing and quality; lesion segmentation (Dice 0.68); classification and model comparison (ml/reports/final_evaluation.md; state the SCC weakness and that CV is not a held-out test); transformer / ensemble results including negative ones; explainability; risk protocol; security and testing; performance table from the benchmark; deployment; limitations (milestone4_checklist.md); future work (React Native, OAuth2, more data and skin tones, prospective validation).

## Demo script (8-10 minutes)
1. Home page, sign up as a patient with research consent. 2. Capture a photo with a quality warning, retake, upload. 3. Analysis screen: original, preprocessed, lesion, attention map, top-3, risk level, disclaimer. 4. PDF report. 5. Clinician: open the case, add a note, compare two analyses. 6. Admin: verify a clinician, model registry, roll back and re-analyse, `/api/metrics`, audit log. 7. A poor-quality rejection and a low-confidence notification. 8. State the limits plainly.
