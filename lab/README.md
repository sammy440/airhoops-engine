# AirHoops Lab (Python)

Data lab for tuning throw detection from real landmark recordings. No video is ever involved —
recordings are landmark numbers exported from the frontend's `/lab` page.

## Setup

```bash
cd lab
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Workflow

1. Record clips in the frontend at `/lab` (keys **1–6** pick the label, **R** records).
   Aim for ~20 throws and ~20 non-throws (wave, scratch head, idle, catch).
2. **Download all** and drop the file(s) into `lab/recordings/`. Bundles and single clips both work;
   duplicates are ignored by recording id.
3. Evaluate the detector against the targets (≥90% throws detected, <10% false triggers):
   ```bash
   .venv/bin/python -m airhoops_lab.evaluate          # current params
   .venv/bin/python -m airhoops_lab.evaluate --tune   # grid search (needs ≥5 clips per class)
   ```
4. Copy changed values into `Params` (`airhoops_lab/detector.py`) **and** `DEFAULT_THROW_PARAMS`
   (`airhoops-frontend/src/lib/pose/throwDetector.ts`), then lock them in:
   ```bash
   .venv/bin/python -m airhoops_lab.parity   # exports fixtures for the frontend replay test
   cd ../../airhoops-frontend && npm test    # fails if TS and Python disagree
   ```
5. Explore visually: `.venv/bin/jupyter lab notebooks/`

## Contents

| Path | What |
|---|---|
| `airhoops_lab/load.py` | Load clips / bundles into numpy arrays |
| `airhoops_lab/kinematics.py` | Port of the browser pipeline: One Euro smoothing + torso-normalized kinematics |
| `airhoops_lab/detector.py` | Port of `throwDetector.ts` (state machine + `ThrowEvent`) |
| `airhoops_lab/evaluate.py` | Metrics + grid-search tuning CLI |
| `airhoops_lab/parity.py` | Exports fixtures so the TS replay test checks TS == Python |
| `airhoops_lab/classifier.py` | Optional windowed-feature classifier (logistic / random forest, GroupKFold) |
| `notebooks/01_explore` | What throws look like; why torso length beats shoulder width |
| `notebooks/02_release_detection` | Detector replay, states, events, threshold sensitivity |
| `notebooks/03_classifier` | Does a learned model beat the state machine? |
| `tests/` | `.venv/bin/python -m pytest tests` |

Units everywhere: positions in "square" units (x × width/height, y), divided by **torso length**.
Speeds are torso lengths per second.
