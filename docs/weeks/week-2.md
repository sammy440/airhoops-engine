# Week 2: Wrist Kinematics and Landmark Recorder

**Goal:** Turn raw landmarks into meaningful motion numbers, and start collecting data for the Python lab.

## Tasks

- [x] Implement `oneEuroFilter.ts` and apply it to wrist, elbow, shoulder landmarks (also hips + index fingers)
- [x] Implement `kinematics.ts`: shoulder-width normalization, wrist velocity (vector and speed), elbow angle, arm extension
- [x] Choose the throwing hand automatically (the wrist that moves fastest) with a manual override
- [x] Show live numbers on screen: speed, direction angle, extension (plus elbow angle and 1.5 s peak)
- [x] Draw a velocity vector arrow from the wrist
- [x] Build a Recorder: Record / Stop saving timestamped landmarks as JSON (no video)
- [x] Add labels when recording: `throw`, `wave`, `scratch_head`, `idle`, `catch`
- [x] Download the recording as a `.json` file (single clip or all clips in one bundle)

Extras: countdown + beeps and auto-stop for hands-free recording, keyboard shortcuts (R/Space, 1–5),
IndexedDB persistence, live speed graph, smoothing sliders with raw comparison, unit tests.

## Done when

- [ ] At least 40 labeled recordings (about 20 throws and 20 non-throws, varied speed, distance,
      lighting, clothing). **This needs real people in front of a camera** — the Lab tracks progress.

## Recording tips

1. Open `/lab`, set countdown 3s and length 3s, pick a label (keys 1–5).
2. Stand back, press **R**, perform the motion when the beeps stop.
3. Vary it: fast/slow throws, near/far from the camera, left hand, bright/dim rooms, sleeves on/off.
4. When done, **Download all** and save the file into `lab/recordings/` for Week 3.

## File format

Single clip (`throw_2026-10-24_09-41-07_3fa2.json`) — README §7.1 plus metadata:

```json
{
  "version": 1, "id": "…", "label": "throw", "hand": "right", "fps": 29.8,
  "createdAt": "2026-10-24T09:41:07.000Z", "durationMs": 3010,
  "video": { "width": 1280, "height": 720 }, "model": "lite",
  "frames": [{ "t": 0, "landmarks": [{ "i": 11, "x": 0.41, "y": 0.52, "z": -0.1, "v": 0.99 }] }]
}
```

Bundle (`airhoops-recordings_2026-10-24.json`): `{ "version": 1, "count": 40, "recordings": [ …clips ] }`.

Landmarks are **raw** (unsmoothed) so smoothing can be re-tuned offline. Frames with nobody in view
have `"landmarks": []`. Use `video.width / video.height` to convert x into square units.
