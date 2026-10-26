# Week 5: Calibration, Scoring, Difficulty, and Polish

**Goal:** Make it fair, fun, and understandable for a new player.

## Tasks

- [x] Calibration: 3 practice throws, stores min / max / average in localStorage
- [x] Calibration maps any player's range so their normal throw scores (at any distance)
- [x] "Move into frame" guide: in view, distance, centred, visibility, lighting (dark / backlit)
- [x] Scoring: base points, swish bonus, streak multiplier
- [x] Difficulty: net distance, net size, moving net, wind
- [x] Modes: Free Play, 60-second Timed, Streak Challenge
- [x] Onboarding (first-visit tutorial in the start menu) and pause menu
- [x] Performance: lower-res camera input, lite model, background caching, tab-visibility auto-pause

## Done when

| Criterion | Status |
|---|---|
| 3 friends can play without you explaining it | 🟡 needs real people: hand them `/play` and watch silently |
| Above 30 fps on a mid-range laptop | ✅ in testing: game loop 60 fps with tracking (software GL); check on the target laptop |

## Friend test script (you)

1. Clear site data (or use a private window) so they see the first-visit tutorial.
2. Say only "it's a basketball game". Don't explain anything.
3. Note where they hesitate: setup checklist, calibration, the first shot, the gauge.
4. Tell me what confused them; that's the polish list before multiplayer.
