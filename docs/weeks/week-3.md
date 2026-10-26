# Week 3: Throw Detection and the Python Lab

**Goal:** Reliable throw detection, backed by data.

## Tasks (Python lab)

- [x] Set up `lab/` with Jupyter, pandas, matplotlib, scikit-learn (`lab/README.md`)
- [x] Load recordings, plot wrist speed over time (`notebooks/01_explore`)
- [x] Find the release signature (`notebooks/02_release_detection`)
- [x] Choose thresholds and window sizes, evaluate precision and recall (`python -m airhoops_lab.evaluate [--tune]`)
- [x] (Optional) Classifier on windowed features (`notebooks/03_classifier`) — waits for non-throw data

## Tasks (frontend)

- [x] `throwDetector.ts` state machine
- [x] Emit `ThrowEvent { power, angle, arc, hand, t }` (+ diagnostics)
- [x] Debug UI: live state, thresholds (live sliders), last throw, event log, graph markers, THROW! flash
- [x] Cooldown and timeouts (plus re-arm after timeout)
- [x] Replay any saved recording through the live pipeline from the Recorder panel

## What the first recordings taught us

1. **Normalize by torso length, not shoulder width.** Turning side-on to throw shrank shoulder width
   up to 40× on camera; torso length moved ±10%. All units are now torso lengths.
2. **Don't require a pickup below the hip.** Players held the ball at head height and pushed. PICKUP is
   tracked and reported (`pickedUp`) but optional.
3. **Release = reach peak.** The arm extends with the wrist at/above shoulder height, then reach peaks and
   speed falls away. That's what fires the event.
4. **Frame rate was 15–18 fps** on the recording machine. Week 5's performance pass matters.

## Status vs "Done when" (after session 2, 6 clips)

| Target | Now | |
|---|---|---|
| ≥90% of throws detected | 4/4 throw clips; 19/21 throws in the long throw clip | ✅ |
| <10% of non-throws trigger | wave 0, scratch head 0 | ✅ |
| Waves / idle hands | wave clip 20 → 0; hands-in-air clip 21 → 1 | ✅ |

Fixes came from three rules learned from the data: **set point** (hand pauses before a shot),
**upward direction** (≥ 5°), **high release** (≥ 0.4 torso above shoulder). See CHANGELOG 3.1.

Note: clip-level "extra events" is meaningless for long clips with many throws; judge those by eye in
`notebooks/02_release_detection` or with Replay in `/lab`.

**Open question:** clip `f5a0f8e1` (07:43, labelled *throw*) looks like hands held up and wobbling
side to side, not throwing. If so, relabel it to `idle`/`wave` before tuning.

**Still to record:** `idle` (hands down and hands up), `catch`, and a few more of each so
`evaluate --tune` has ≥5 clips per class.
