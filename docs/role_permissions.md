# Role permissions

Enforced by the API (`backend/app/core/permissions.py`, `services/access.py`, `services/views.py`). Fields a role may not see are never sent. The web app mirrors the matrix in `frontend/src/lib/permissions.ts` only to decide what to draw. 33 backend tests check this matrix.

## What each role can see

| Information | Patient | Clinician | Researcher | Data Scientist / ML Eng. | Administrator |
|---|---|---|---|---|---|
| Case ID | yes | yes | yes | yes | yes |
| Image ID | no | yes | yes | yes | no |
| Image capture date | yes | yes | yes | no | no |
| Body location | yes | yes | yes | no | no |
| Image source | no | yes | yes | yes | yes |
| Analysis status | yes | yes | yes | yes | yes |
| Model version | no | yes | yes | yes | yes |
| Prediction result | yes | yes | yes | yes | no |
| Patient name, age, history, allergies | own only | yes | no (de-identified) | no | no |
| Clinical notes | no | yes | no | no | no |
| Image quality (label, metrics) | label + tips | yes | yes | yes | no |
| Image files | own | yes | yes | yes | no |

## What each role can do

| Action | Patient | Clinician | Researcher | Data Scientist / ML Eng. | Administrator |
|---|---|---|---|---|---|
| Create case | yes | yes, also on behalf of a patient (verified) | no | no | no |
| Upload / capture image | yes | yes | no | no | no |
| View previous analyses | yes | yes | yes | yes | yes (audit) |
| Compare analysis results | no | yes | yes | yes | no |
| Track prediction history | yes | yes | yes (across shared cases) | yes (across shared cases) | yes (audit) |
| Add clinical notes | no | yes | no | no | no |
| Delete a case | owner | owner or the clinician who opened it | no | no | no |
| Manage users, verify clinicians | no | no | no | no | yes |

## Which cases each role can open
- **Patient:** their own cases (including ones a clinician opened for them).
- **Clinician:** their own cases; **all** cases once an administrator verifies their licence.
- **Researcher and ML engineer:** de-identified cases from patients who ticked "Share my de-identified cases for research" (profile or sign-up). Withdrawing consent removes access immediately. Set `RESEARCH_REQUIRES_CONSENT=false` to show them every case instead (only appropriate for public or synthetic datasets).
- **Administrator:** every case, operational fields only.

## Reports
`GET /api/cases/{id}/report?format=pdf|json|csv[&image_id=]` is built from the same role-shaped views as the rest of the API, so a report holds only what the caller may see (patients: no technical fields; researchers: de-identified; administrators: operational fields only, no images). Every report is audit-logged.

## Milestone 3 additions
- **Attention map and analysis screen** (`/analysis/:id`, image variant `cam`): same visibility as other image files, so everyone except administrators.
- **Risk category**: part of `prediction_result`, visible to the roles that see it (patient, clinician, researcher, ML engineer).
- **Notifications**: patients and clinicians (full set), administrators (failed analyses only), researchers and ML engineers (none).
- **Model registry** (list versions, deploy, roll back, reload, re-analyse): administrators only; deployments are audit-logged.
- Dashboard breakdowns: clinicians also get predicted condition and risk level; researchers and ML engineers get predicted condition.

## Design notes
- Clinicians cannot read other users' cases until verified, and changing a licence number resets verification.
- Researchers never see original file names (they can contain names).
- Filters on a field a role cannot see are ignored, so hidden values cannot be inferred (for example the ML engineer's date filter).
- "Recorded" (upload time) is shown to roles without capture-date access, for ordering and auditing.

