# UI wireframes (low fidelity)

## Entry page (role carousel, swipe or arrows)
```
+------------------------------+-------------------------------------+
| DermAI                       |  [ Sign in ] [ Create account ]     |
| DERMATOLOGIST / CLINICIAN    |  Create your clinician account      |
| Review cases with clarity    |  Full name  [____________]          |
| and context.                 |  Email      [____________]          |
|  . Review all cases once     |  Password   [____________]          |
|    verified                  |  Hospital   [____________]          |
|  . Compare analyses          |  Licence no.[______] Speciality[__] |
|                              |  (verification notice)              |
| ( < ) [Patient|CLINICIAN|Res] ( > )  [ Create account ]            |
| disclaimer                   |  Staff sign in                      |
+------------------------------+-------------------------------------+
 Patient fields: age, gender, medical history, allergies
 Researcher fields: institution, research area, ORCID
 Theme shifts with the selected role.
```

## Dashboard
```
DermAI  [Dashboard] [Cases] [Admin*]               Name (role) [Sign out]
-----------------------------------------------------------------------
Hello, Asha                                                [ New case ]
[ Cases 4 ] [ Images 9 ] [ Good/Acceptable 7 ] [ Rejected 2 ]
Recent cases
 DRM-261021-A1B2C3   back · 2 images                        [good]
 DRM-261020-9F8E7D   face · 1 image                    [acceptable]
```

## New case
```
New case   (de-identified data only)
 Age [__]  Gender [v]  Body location [v]
 Medical history  [__________]   Known allergies [______]
 Clinical notes   [__________]
 [ Create case ] [ Cancel ]
```

## Case detail and capture flow
```
DRM-261021-A1B2C3                                       [Delete case]
 Age 41 | Gender female | Location back | Images 2
+-- Add a skin image --------------------------------------------+
| [Take photo] [Choose from gallery]                             |
|   after selecting:                                             |
|  +----------+   Quality [acceptable]   1200x1200               |
|  | preview  |   Sharpness   |=====|--|                         |
|  |          |   Brightness  |=====|--|   - Lighting is dim.    |
|  +----------+   Contrast    |===|----|                         |
|  [ Confirm and upload ]  [ Retake ]  (disabled if poor)        |
+----------------------------------------------------------------+
Images
 [original] [preprocessed]  [good] 1200x1200 JPEG  pending
                            meters + issues         Delete image
Compare: tick two images -> side-by-side table with change column
Notes timeline (author, role, time) + [Add note]
```

## Admin
```
Create user: [name] [email] [password] [role v] [Create]
Users table with Activate / Deactivate
Audit log (latest 50 events)
```

## History
```
Prediction history     Captured from [__] to [__]  Status [v]  Quality [v]
[ ] thumb IMG-000002  DRM-...  2026-10-15  back  gallery  [acceptable]  pending  -  Not analysed yet
[ ] thumb IMG-000001  DRM-...  2026-09-01  back  gallery  [acceptable]  pending  -  Not analysed yet
Tick two (even across cases) -> [Compare]
```

