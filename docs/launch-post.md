# Launch post (draft)

Replace `<URL>` and `<VIDEO>` before posting. Short version for X / Threads / LinkedIn at the bottom.

---

## AirHoops: shoot hoops with nothing but air

No controller, no app, no sign-up. Open a link, step back from your laptop, and shoot a basketball by throwing
the way you would on a real court. Your camera watches the throw and the ball flies.

**Play:** <URL>
**Watch:** <VIDEO>

### How it works

A pose model runs inside your browser and turns each camera frame into a skeleton. AirHoops watches your
shooting hand: you hold the ball up (the set point), pause, then push up and out. The speed of the release sets
the power, its direction sets the angle. A quick calibration learns what *your* normal shot feels like, so a
relaxed throw scores whether you're 1.5 m or 3 m from the screen.

### Your video never leaves your device

Everything the camera sees is processed locally and thrown away. Only three numbers per throw (power, angle,
arc) are used to play, and they only go online when you play with friends. There's a privacy page that lists
exactly what's stored and lets you delete it.

### What you can do

- **Solo:** free play, timed runs (30 seconds up to 30 minutes) and streak mode, from Rookie to Legend
  (longer shots, moving hoop, wind)
- **With friends:** send a link, play a turn-based shootout or a race against the clock. The server re-runs the
  physics for every shot, so everyone sees the same result and nobody can fake a swish
- **Your player:** pick your body, skin tone, hair and kit colours. Friends see your look in the lobby and on court
- **Leaderboards:** today, this week and all time
- **No camera?** Hold Space or press the court to shoot

### Built with

Next.js, MediaPipe Pose Landmarker (on-device), a small deterministic physics engine written twice (TypeScript
in the browser, Python on the server) and checked against 480 shared test cases, FastAPI, WebSockets and Postgres.

Tell me your best Timed 1:00 score.

---

### Short version

> I built a basketball game you play by throwing at your webcam. 🏀
> No app, no controller: the pose tracking runs in your browser and your video never leaves your device.
> Solo runs, leaderboards, and 1v1 shootouts with a friend via a link.
> <URL>
