# AirHoops (working title)

A browser-based, camera-controlled basketball-style game. The player stands in front of their webcam, mimes picking up an invisible ball, and throws it toward a virtual net. The camera reads body movement, the game converts the motion into throw power and direction, and a virtual ball flies into (or misses) the net on screen. Multiplayer lets players compete in turn-based or timed rounds.

---

## Table of Contents

1. [Concept](#1-concept)
2. [Tech Stack](#2-tech-stack)
3. [Architecture](#3-architecture)
4. [Repository Structure](#4-repository-structure)
5. [Core Concepts](#5-core-concepts)
6. [Build Plan (8 Weeks)](#6-build-plan-8-weeks)
7. [Data Schemas and Protocols](#7-data-schemas-and-protocols)
8. [Testing Strategy](#8-testing-strategy)
9. [Risks and Mitigations](#9-risks-and-mitigations)
10. [Deployment](#10-deployment)
11. [Backlog and Ideas](#11-backlog-and-ideas)

---

## 1. Concept

**Player experience**

1. Player opens the game URL and grants camera permission.
2. A guide shows them how to stand (full upper body in frame, good light).
3. A short calibration asks for 3 practice throws to learn their power range.
4. Player mimes a pick-up (hand drops to ball zone, then rises) and throws toward the screen.
5. The game launches a virtual ball from the throw data. It arcs toward the net, and the result is scored.
6. In multiplayer, players take turns or race against a timer, and scores sync live.

**Design principles**

- **Instant feedback.** All pose tracking runs in the browser. No video is ever uploaded.
- **Privacy first.** Only small numeric throw data leaves the device, never frames.
- **Server decides outcomes in multiplayer.** The client reports throw power and angle, and the server simulates and scores it.
- **Forgiving input.** Smoothing, calibration, and a generous gesture state machine so the game feels fair.

---

## 2. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend app | Next.js (React), Tailwind CSS | Already in your stack |
| Pose tracking | MediaPipe Tasks Vision (`@mediapipe/tasks-vision`), Pose Landmarker | Runs on-device, GPU accelerated, 30+ fps |
| Game rendering and physics | Phaser 3 with Matter.js | Simple 2D scene, ball, net, collisions |
| Signal smoothing | One Euro filter (small custom module) | Reduces landmark jitter without adding lag |
| Backend | FastAPI (Python), WebSockets | Rooms, turns, score sync, server physics |
| Server physics | Pymunk | Re-simulates throws for anti-cheat |
| Database | PostgreSQL (SQLModel or SQLAlchemy) | Accounts, matches, leaderboards |
| Data lab | Python: NumPy, pandas, matplotlib, scikit-learn, Jupyter | Tune throw detection from recorded data |
| Hosting | Vercel (frontend), Fly.io / Railway / Render (backend), managed Postgres | Simple deploys |

**Optional later:** ONNX Runtime Web to run a trained throw classifier in the browser.

---

## 3. Architecture

```
 Browser (client)                                  Server (Python)
┌─────────────────────────────────────┐          ┌──────────────────────────┐
│ Webcam                              │          │ FastAPI                  │
│   ↓                                 │          │  ├─ REST: auth, stats    │
│ MediaPipe Pose Landmarker           │          │  ├─ WebSocket: rooms     │
│   ↓ landmarks (33 points / frame)   │          │  ├─ Pymunk: re-simulate  │
│ Smoothing (One Euro filter)         │          │  │   throws, score them  │
│   ↓                                 │          │  └─ Postgres             │
│ Gesture state machine               │          └─────────────▲────────────┘
│   Idle → Pickup → Windup → Throw    │                        │
│   ↓ throw = {power, angle, arc}     │   WebSocket (JSON)     │
│ Phaser game scene (ball, net)       ├────────────────────────┘
│   ↓                                 │   throw events only, never video
│ HUD, scoring, calibration           │
└─────────────────────────────────────┘
```

**Key rule:** video frames never leave the browser. The network carries only throw events and game state.

---

## 4. Repository Structure

Monorepo layout (adjust to taste):

```
airhoops/
├─ README.md
├─ apps/
│  ├─ web/                      # Next.js frontend
│  │  ├─ app/
│  │  │  ├─ page.tsx            # landing
│  │  │  ├─ play/page.tsx       # game page
│  │  │  └─ lab/page.tsx        # dev-only: tracking debug + recorder
│  │  ├─ components/
│  │  │  ├─ CameraFeed.tsx
│  │  │  ├─ SkeletonOverlay.tsx
│  │  │  ├─ Hud.tsx
│  │  │  └─ CalibrationModal.tsx
│  │  ├─ lib/
│  │  │  ├─ pose/
│  │  │  │  ├─ poseLandmarker.ts   # MediaPipe setup
│  │  │  │  ├─ oneEuroFilter.ts
│  │  │  │  ├─ kinematics.ts       # velocity, angles, normalization
│  │  │  │  └─ throwDetector.ts    # state machine
│  │  │  ├─ game/
│  │  │  │  ├─ GameScene.ts        # Phaser scene
│  │  │  │  ├─ ballPhysics.ts
│  │  │  │  └─ scoring.ts
│  │  │  └─ net/
│  │  │     └─ socket.ts           # WebSocket client
│  └─ api/                      # FastAPI backend
│     ├─ app/
│     │  ├─ main.py
│     │  ├─ auth.py
│     │  ├─ rooms.py             # room + turn management
│     │  ├─ physics.py           # Pymunk re-simulation
│     │  ├─ models.py            # DB models
│     │  └─ schemas.py           # Pydantic models
│     ├─ tests/
│     └─ pyproject.toml
├─ lab/                          # Python data lab
│  ├─ recordings/                # JSON landmark recordings
│  ├─ notebooks/
│  │  ├─ 01_explore.ipynb
│  │  ├─ 02_release_detection.ipynb
│  │  └─ 03_classifier.ipynb
│  └─ requirements.txt
└─ docs/
   └─ weeks/                     # split each week of this README into its own file
```

---

## 5. Core Concepts

### 5.1 Pose landmarks you will use

MediaPipe Pose returns 33 landmarks per frame. The important ones:

| Index | Landmark |
|---|---|
| 11 / 12 | Left / right shoulder |
| 13 / 14 | Left / right elbow |
| 15 / 16 | Left / right wrist |
| 19 / 20 | Left / right index finger |
| 23 / 24 | Left / right hip |

Coordinates are normalized (0 to 1) relative to the frame. Note that the camera image is usually mirrored for a natural feel, so remember to flip x for display and for handedness logic.

### 5.2 Normalization

Players stand at different distances. Normalize all distances and speeds by **shoulder width** (distance between landmarks 11 and 12). Then a "throw power" of 3.0 shoulder-widths per second means the same thing for everyone.

### 5.3 Smoothing

Raw landmarks jitter. Apply a One Euro filter per coordinate. Tune two parameters:

- `minCutoff`: lower means smoother when moving slowly
- `beta`: higher means less lag when moving fast

### 5.4 Gesture state machine

```
IDLE ──(hand drops below hip line / enters ball zone)──► PICKUP
PICKUP ──(hand rises above shoulder / elbow bends)──► WINDUP
WINDUP ──(wrist velocity exceeds threshold)──► THROW
THROW ──(velocity peaks then drops, arm extended)──► RELEASE (emit throw event)
RELEASE ──(cooldown ~800 ms)──► IDLE
```

Add timeouts so the machine always returns to IDLE if the player stalls.

### 5.5 Throw measurement

At the release frame:

- **Power** = peak wrist speed in the last ~150 ms, in shoulder-widths per second, mapped through the calibrated range to `0..1`
- **Angle** = angle of the wrist velocity vector (degrees above horizontal)
- **Arc bonus** = how high the hand rose above the shoulder before release

The game turns these into an initial ball velocity.

### 5.6 No-depth limitation

A single webcam cannot see motion toward or away from the camera. Use arm extension (shoulder-to-wrist distance growth) as a depth proxy, or design the game so depth does not matter.

---

## 6. Build Plan (8 Weeks)

Each week is self-contained. Copy the section into `docs/weeks/week-N.md` when you start it.

---

### Week 1: Project Setup and Camera with Skeleton Overlay

**Goal:** See yourself on screen with a live skeleton drawn over your body.

**Tasks**

- [ ] Create the monorepo and the Next.js app (TypeScript, Tailwind)
- [ ] Install `@mediapipe/tasks-vision`
- [ ] Build `CameraFeed.tsx`: request webcam via `getUserMedia`, show a mirrored video
- [ ] Build `poseLandmarker.ts`: initialize `PoseLandmarker` with the video running mode
- [ ] Build `SkeletonOverlay.tsx`: draw landmarks and connections on a canvas over the video
- [ ] Add an FPS counter and a "tracking confidence" indicator
- [ ] Add friendly errors for denied permission, no camera, and unsupported browser

**Starter snippet**

```ts
import { PoseLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";

export async function createPoseLandmarker() {
  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm"
  );
  return PoseLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numPoses: 1,
  });
}

// In your render loop:
// const result = landmarker.detectForVideo(videoEl, performance.now());
// result.landmarks[0] is an array of 33 normalized points
```

**Deliverable:** `/lab` page showing mirrored webcam with skeleton at 30+ fps.

**Done when:** it runs smoothly on your laptop and on one other device, and handles permission denial gracefully.

---

### Week 2: Wrist Kinematics and Landmark Recorder

**Goal:** Turn raw landmarks into meaningful motion numbers, and start collecting data for the Python lab.

**Tasks**

- [ ] Implement `oneEuroFilter.ts` and apply it to wrist, elbow, shoulder landmarks
- [ ] Implement `kinematics.ts`: shoulder-width normalization, wrist velocity (vector and speed), elbow angle, arm extension
- [ ] Choose the throwing hand automatically (the wrist that moves fastest) with a manual override
- [ ] Show live numbers on screen: speed, direction angle, extension
- [ ] Draw a velocity vector arrow from the wrist
- [ ] Build a **Recorder**: Record / Stop button saving timestamped landmarks as JSON (no video)
- [ ] Add labels when recording: `throw`, `wave`, `scratch_head`, `idle`, `catch`
- [ ] Download the recording as a `.json` file

**Deliverable:** live kinematics HUD plus a recorder.

**Done when:** you have at least 40 labeled recordings (about 20 throws and 20 non-throws, varied speed, distance, lighting, clothing).

---

### Week 3: Throw Detection and the Python Lab

**Goal:** Reliable throw detection, backed by data.

**Tasks (Python lab)**

- [ ] Set up `lab/` with Jupyter, pandas, matplotlib, scikit-learn
- [ ] Load recordings, plot wrist speed over time for throws vs non-throws
- [ ] Find the release signature (peak speed followed by drop, extension growth)
- [ ] Choose thresholds and window sizes, then evaluate precision and recall
- [ ] (Optional) Train a small classifier on windowed features and compare to the heuristic

**Tasks (frontend)**

- [ ] Implement `throwDetector.ts` as the state machine from section 5.4
- [ ] Emit a `ThrowEvent` `{ power, angle, arc, timestamp, hand }`
- [ ] Add debug UI showing current state, thresholds, and the last throw
- [ ] Add cooldown and timeouts

**Starter snippet**

```ts
export type ThrowEvent = {
  power: number;   // 0..1 after calibration
  angle: number;   // degrees above horizontal
  arc: number;     // 0..1
  hand: "left" | "right";
  t: number;       // ms timestamp
};
```

**Deliverable:** detector that fires a `ThrowEvent` on real throws and ignores waves and scratches.

**Done when:** at least 90 percent of deliberate throws are detected and fewer than 1 in 10 non-throw motions trigger a false throw on your recordings.

---

### Week 4: Game Scene with Virtual Ball and Net

**Goal:** A throw on camera launches a ball into a net on screen.

**Tasks**

- [ ] Add Phaser 3 to the `/play` page, with the camera feed as a small picture-in-picture corner
- [ ] Build `GameScene.ts`: court background, net with a hoop sensor, ball sprite
- [ ] Use Matter.js for ball physics: gravity, bounce on rim, score when passing through the hoop sensor from above
- [ ] Map `ThrowEvent` to initial velocity: `v = base + power * scale`, direction from `angle`
- [ ] Add a ball respawn after each shot
- [ ] Add a keyboard fallback (space bar throws a medium shot) for testing without a camera
- [ ] Add basic sound effects and a score counter

**Deliverable:** you throw an imaginary ball and watch it fly into the net.

**Done when:** a strong, well-aimed throw scores, a weak throw falls short, and the mapping feels learnable within a few tries.

---

### Week 5: Calibration, Scoring, Difficulty, and Polish

**Goal:** Make it fair, fun, and understandable for a new player.

**Tasks**

- [ ] Build `CalibrationModal.tsx`: ask for 3 practice throws, store min, max, and average power in `localStorage`
- [ ] Use calibration to map any player's range to `0..1`
- [ ] "Move into frame" guide, with lighting and distance checks (landmark visibility scores)
- [ ] Scoring: base points, swish bonus (no rim touch), streak multiplier
- [ ] Difficulty levels: net distance, net size, moving net, wind
- [ ] Single-player modes: Free Play, 60-second Timed, Streak Challenge
- [ ] Onboarding tutorial overlay and a pause menu
- [ ] Performance pass: lower resolution input, lite model fallback, tab visibility handling

**Deliverable:** a complete single-player game a stranger can pick up without help.

**Done when:** 3 friends can play without you explaining it, and the game stays above 30 fps on a mid-range laptop.

---

### Week 6: FastAPI Backend, Auth, and WebSocket Rooms

**Goal:** A working server that can create rooms and relay events.

**Tasks**

- [ ] Scaffold FastAPI, Pydantic schemas, SQLModel/SQLAlchemy, Alembic migrations
- [ ] Postgres tables: `users`, `matches`, `throws`, `scores`
- [ ] Auth: guest sessions first (nickname plus token), then optional email or OAuth later
- [ ] REST endpoints: `POST /rooms`, `POST /rooms/{code}/join`, `GET /leaderboard`
- [ ] WebSocket endpoint `/ws/{room_code}` with a connection manager
- [ ] Room lifecycle: lobby, ready, in-progress, finished
- [ ] Heartbeats, reconnect handling, and cleanup of empty rooms
- [ ] CORS and environment config

**Starter snippet**

```py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

class Rooms:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, code: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(code, []).append(ws)

    def disconnect(self, code: str, ws: WebSocket):
        self.rooms[code].remove(ws)

    async def broadcast(self, code: str, message: dict):
        for ws in self.rooms.get(code, []):
            await ws.send_json(message)

rooms = Rooms()

@app.websocket("/ws/{code}")
async def room_ws(ws: WebSocket, code: str):
    await rooms.connect(code, ws)
    try:
        while True:
            data = await ws.receive_json()
            await rooms.broadcast(code, data)
    except WebSocketDisconnect:
        rooms.disconnect(code, ws)
```

**Deliverable:** two browser tabs can join the same room and see each other's presence.

**Done when:** rooms survive a brief disconnect and clean up when everyone leaves.

---

### Week 7: Multiplayer Gameplay and Server-Side Physics

**Goal:** Real matches with trustworthy scoring.

**Tasks**

- [ ] Implement `physics.py` with Pymunk mirroring the client's gravity, ball size, hoop position
- [ ] Client sends only `throw` events `{power, angle, arc, t}`
- [ ] Server validates ranges, rate limits (cannot throw faster than the cooldown), and re-simulates the shot
- [ ] Server broadcasts the authoritative `shot_result` (path samples plus scored or missed)
- [ ] Both clients animate the shot from the server result so everyone sees the same outcome
- [ ] **Mode A: Turn-based 1v1 shootout** (5 shots each, sudden death on ties)
- [ ] **Mode B: Timed race** (60 seconds, everyone throws freely, highest score wins)
- [ ] Lobby UI: create or join by code, ready button, countdown, results screen, rematch
- [ ] Show the opponent's skeleton as a lightweight stick figure by streaming only a few wrist and shoulder points at low rate (optional, off by default)

**Deliverable:** two people on different devices play a full match.

**Done when:** results match on both screens, obviously impossible throws are rejected, and a dropped player is handled gracefully (forfeit or reconnect window).

---

### Week 8: Leaderboards, Testing, Deployment, and Launch

**Goal:** Ship it.

**Tasks**

- [ ] Leaderboards: daily, weekly, all-time, plus personal best
- [ ] Persist matches and throws for analytics
- [ ] Unit tests: kinematics, throw detector (replay recordings), physics parity between client and server
- [ ] Integration tests: room lifecycle over WebSocket
- [ ] Manual test matrix: Chrome, Edge, Safari, Firefox, Android Chrome, different lighting and clothing
- [ ] Accessibility: keyboard and mouse fallback, reduced motion, clear permission messaging
- [ ] Privacy page: explain that video never leaves the device
- [ ] Deploy: frontend on Vercel, API on Fly.io/Railway/Render, managed Postgres
- [ ] Add basic monitoring (error tracking, uptime check) and rate limiting
- [ ] Record a short demo video and write the launch post

**Deliverable:** a public URL anyone can play.

**Done when:** a stranger can open the link, calibrate, and finish a multiplayer match with a friend.

---

## 7. Data Schemas and Protocols

### 7.1 Landmark recording (JSON)

```json
{
  "version": 1,
  "label": "throw",
  "hand": "right",
  "fps": 30,
  "frames": [
    {
      "t": 0,
      "landmarks": [
        { "i": 11, "x": 0.41, "y": 0.52, "z": -0.1, "v": 0.99 },
        { "i": 12, "x": 0.58, "y": 0.52, "z": -0.1, "v": 0.99 },
        { "i": 16, "x": 0.66, "y": 0.61, "z": -0.2, "v": 0.97 }
      ]
    }
  ]
}
```

Only store the landmarks you need (shoulders, elbows, wrists, hips) to keep files small.

### 7.2 WebSocket messages

Client to server:

```json
{ "type": "join", "nickname": "Dayo", "token": "..." }
{ "type": "ready" }
{ "type": "throw", "power": 0.82, "angle": 48.5, "arc": 0.6, "t": 1730000000000 }
{ "type": "ping" }
```

Server to client:

```json
{ "type": "room_state", "players": [...], "phase": "lobby" }
{ "type": "turn", "playerId": "p1", "shotsLeft": 4 }
{ "type": "shot_result", "playerId": "p1", "scored": true, "swish": true,
  "path": [[0,0],[12,-30],[24,-52]], "points": 3 }
{ "type": "scoreboard", "scores": { "p1": 9, "p2": 6 } }
{ "type": "match_end", "winner": "p1" }
{ "type": "error", "code": "invalid_throw", "message": "..." }
```

### 7.3 Database tables (sketch)

| Table | Key columns |
|---|---|
| `users` | id, nickname, created_at, token_hash |
| `matches` | id, room_code, mode, started_at, ended_at, winner_id |
| `throws` | id, match_id, user_id, power, angle, arc, scored, points, created_at |
| `scores` | id, user_id, mode, score, created_at |

---

## 8. Testing Strategy

- **Replay tests:** feed saved landmark recordings into `throwDetector.ts` and assert expected throw counts. This keeps detection stable as you tune.
- **Physics parity:** same `(power, angle, arc)` input must produce the same scored result on client and server within a tolerance. Test a grid of inputs.
- **Property tests:** random landmark noise must never crash the detector or produce NaN.
- **Load test:** 50 concurrent rooms with simulated throw events.
- **Device matrix:** test low light, backlit windows, loose sleeves, short and tall players, left-handed throwers.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Release moment is hard to detect | Use peak-velocity plus extension; tune with recorded data; allow generous windows |
| Landmark jitter and lag | One Euro filter; short frame windows instead of single frames |
| No depth from one camera | Use arm extension as a proxy; design the game so depth is not required |
| Poor lighting or clothing | Visibility checks and an on-screen guide before play |
| Players cheating in multiplayer | Server re-simulates every throw, validates ranges and rate |
| Latency in real-time modes | Start with turn-based; send small events; server-authoritative results |
| Browser or device differences | Lite model fallback, feature detection, keyboard fallback |
| Camera privacy concerns | All tracking on-device; clear privacy messaging; no video upload |

---

## 10. Deployment

- **Frontend:** Vercel. Camera access requires HTTPS, which Vercel provides.
- **Backend:** Containerize FastAPI (Uvicorn) and deploy on Fly.io, Railway, or Render. Make sure WebSockets are supported and use a single instance at first (or add Redis pub/sub when you scale to several).
- **Database:** managed Postgres (Neon, Supabase, Railway).
- **Environment variables:** `DATABASE_URL`, `JWT_SECRET`, `ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`.
- **CI:** run lint, unit tests, and replay tests on every push.

---

## 11. Backlog and Ideas

- Two-hand and catch mechanics
- Different "balls" with different weight (heavy ball needs more power)
- Obstacles, moving hoops, power-ups
- Spectator mode and shareable replays (throw data only)
- Teams and tournaments
- Trained ONNX throw classifier running in the browser
- Cosmetic skins and courts
- Mobile web support with the rear or front camera
- Voice reactions or crowd noise based on throw energy
- Analytics dashboard in Python for balancing difficulty

---

## Suggested Working Rhythm

- Start each week by copying that week's section into `docs/weeks/week-N.md`.
- Finish the **Done when** criteria before moving on, since later weeks depend on earlier ones.
- Keep the `/lab` page alive throughout. It is your debugging and data-collection tool for the whole project.
- Keep a short `CHANGELOG.md` and record every threshold you tune and why.
