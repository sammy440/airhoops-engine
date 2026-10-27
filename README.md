# AirHoops Engine

The motion engine behind **[AirHoops](https://airhoops.vercel.app)**, a basketball game you play by throwing at your webcam.

This repo is where the throw detector is designed, tuned and tested against real recordings. It also holds the
project's build log. The game itself lives in two sister repos:

| Repo | What |
|---|---|
| **airhoops-engine** (this one) | Python lab: throw-detection research, tuning, parity fixtures, recordings, docs |
| [airhoops](https://github.com/sammy440/airhoops) | Next.js frontend: camera, pose tracking, game, multiplayer UI |
| [airhoop-api](https://github.com/sammy440/airhoop-api) | FastAPI backend: guest auth, rooms, server-side physics referee, leaderboards |

> **Privacy:** no video ever reaches this repo or any server. Recordings are body-landmark numbers only.

## How a throw becomes a shot

```
webcam frame
  └─► MediaPipe Pose (in the browser)        33 landmarks per frame
       └─► One Euro filter                    removes jitter, keeps fast motion snappy
            └─► kinematics                    wrist speed, angle, reach, height, in torso lengths
                 └─► throw detector           state machine → ThrowEvent {power, angle, arc}
                      └─► launch mapping      speed + angle (per-player calibration)
                           └─► physics        deterministic 2D sim: rim, backboard, net
```

Everything up to the throw event runs in the player's browser. Multiplayer clients send only
`{power, angle, arc, t}`; the API re-runs the same physics to decide every shot.

### Why torso length

Distances are measured in **torso lengths** (shoulder midpoint → hip midpoint), after converting MediaPipe's
coordinates to square units. In the first recordings, shoulder width swung about 40× as players turned side-on to
throw, while torso length moved about ±10%. So a "fast" throw means the same thing whatever the player's size
or distance from the camera.

### The detector

```
IDLE ⇄ PICKUP ⇄ WINDUP          (informational: where the hand is)
  └─(arm extending fast, wrist ≥ ~shoulder)─► THROW
THROW ─(reach peaks or speed collapses)─► validate ─► ThrowEvent
COOLDOWN ─(800 ms)─► IDLE        THROW ─(> 900 ms)─► IDLE
```

A throw only counts if it looks like a shot, not a gesture:

| Rule | Value | Rejects |
|---|---|---|
| Set point: hand nearly still just before | median speed ≤ 1.2 torso/s over 300 ms | waving |
| Peak wrist speed | ≥ 2.0 torso/s | slow reaches |
| Reach at release / reach gained | ≥ 0.62 / ≥ 0.12 torso | flicks, small pushes |
| Release height | wrist ≥ 0.4 torso above the shoulder | hand raises, scratching your head |
| Direction | ≥ 5° above horizontal | sideways swipes |
| Duration | 100–900 ms | raising hands into position, stalls |

Thresholds live in `lab/airhoops_lab/detector.py` (`Params`) and in the frontend's
`src/lib/pose/throwDetector.ts` (`DEFAULT_THROW_PARAMS`). They must stay identical; the parity fixtures enforce it.

### Current results

On the recordings in `lab/recordings/` (6 labelled clips: 4 throw, 2 non-throw):

| Metric | Result | Target |
|---|---|---|
| Throw clips detected | 4 / 4 (100%) | ≥ 90% |
| Non-throw clips that triggered | 0 / 2 (0%) | < 10% |

That's a small dataset. More recordings (especially different rooms, lighting, clothing and left-handed
shooters) are the most useful contribution you can make. See below.

![Detector replay: wrist speed with detector states and throw events](lab/reports/detection.png)

## Quick start

```bash
cd lab
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python -m airhoops_lab.evaluate          # metrics with the current thresholds
.venv/bin/python -m airhoops_lab.evaluate --tune   # grid search (needs ≥ 5 clips per class)
.venv/bin/python -m pytest tests                   # lab tests
.venv/bin/jupyter lab notebooks/                   # explore visually
```

Full workflow (recording, tuning, exporting parity fixtures): [`lab/README.md`](lab/README.md).

## Contributing recordings

1. Open the [Tracking Lab](https://airhoops.vercel.app/lab) (or `/lab` on a local frontend).
2. Pick a label with keys **1–5** (throw, wave, scratch head, idle, catch) and press **R** to record.
   About 20 throws and 20 non-throws per session is ideal.
3. Press **Download all** and add the JSON file to `lab/recordings/` in a pull request.

A recording is a JSON file of landmark numbers (shoulders, elbows, wrists, index fingers, hips) per frame, plus
the label, the throwing hand, the frame size and the fps. No images.

## Keeping the three repos in sync

| What | Source of truth | Mirror | Checked by |
|---|---|---|---|
| Smoothing, kinematics, detector | `airhoops/src/lib/pose/*.ts` | `lab/airhoops_lab/*.py` | `python -m airhoops_lab.parity` exports fixtures → frontend `npm test` replays them |
| Physics, launch mapping, scoring | `airhoops/src/lib/game/*.ts` | `airhoop-api/app/game/*.py` | 480 shared shot cases (`GEN_PARITY=1 npx vitest run src/lib/game/parity.gen.test.ts` → API `pytest`) |

Change both sides together, regenerate the fixtures, and run both test suites.

## Repo layout

```
lab/
├─ airhoops_lab/
│  ├─ load.py          load clips / "Download all" bundles into numpy arrays
│  ├─ kinematics.py    Python port of the browser pipeline (One Euro + torso-normalized kinematics)
│  ├─ detector.py      Python port of throwDetector.ts
│  ├─ evaluate.py      metrics + grid-search tuning CLI
│  ├─ parity.py        exports fixtures for the frontend replay test
│  ├─ classifier.py    optional learned classifier (does ML beat the state machine?)
│  └─ plots.py         notebook plot helpers
├─ notebooks/          01 explore · 02 release detection · 03 classifier
├─ recordings/         labelled landmark recordings (JSON)
├─ reports/            figures exported from the notebooks
└─ tests/
docs/
├─ weeks/              build log, week by week (what was built, decisions, "done when" checks)
└─ launch-post.md
```

## Known limitations

- **No depth.** A single webcam can't see how far the hand travels toward the screen, so power comes from wrist
  speed in the image plane. Per-player calibration absorbs most of the difference.
- **One Euro lag scales with distance.** Players far from the camera see slightly more smoothing lag while
  speed ramps up (about 5%).
- **Small dataset.** See *Current results*.
