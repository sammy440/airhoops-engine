# Week 8: Leaderboards, Testing, Deployment, and Launch

**Goal:** Ship it.

## Tasks

- [x] Leaderboards: daily, weekly, all-time, plus personal best
      `/leaderboard` page (solo timed/streak boards, multiplayer shootout/race boards, difficulty filter, avatars,
      ties share a rank) · `GET /leaderboard/me` (your best, runs and rank per period) · Game Over posts the run and
      shows your rank (automatic with a guest pass; one-tap opt-in otherwise)
- [x] Persist matches and throws for analytics: `matches`, `throws`, `scores` (since Week 7); solo scores now
      also store `shots` / `makes`
- [x] Unit tests: kinematics, throw detector (replays the Lab recordings via shared fixtures), physics parity
      between client and server (480 cases)
- [x] Integration tests: room lifecycle over WebSocket (presence, ready/start, reconnects, heartbeats, matches,
      live profile updates)
- [ ] Manual test matrix: see below. Needs real devices; fill in as you test
- [x] Accessibility: keyboard **and mouse/touch** fallback (press and hold the court to charge), reduced motion,
      skip link, visible keyboard focus, specific camera-permission messages with a no-camera way to play,
      axe audit (no critical issues)
- [x] Privacy page: `/privacy`, plus "delete my online data" (`DELETE /auth/me`)
- [x] Deploy config: Vercel (frontend), Dockerfile + `railway.json` (API on Railway), Railway Postgres
- [ ] Deploy: Railway (API + Postgres) and Vercel (frontend). Steps below
- [x] Basic monitoring and rate limiting: `/health/ready` for uptime checks, browser crash reports →
      `/telemetry/errors`, optional Sentry (`SENTRY_DSN`), request logs, per-IP rate limits, security headers
- [ ] Record a short demo video: yours to record (shot list below)
- [x] Launch post: draft in [`docs/launch-post.md`](../launch-post.md)

## Anti-cheat for solo scores

Solo games run entirely in the browser, so their scores are self-reported. The server rejects anything impossible:

| Check | Why |
|---|---|
| `makes ≤ shots` | |
| `score ≤ makes × max points per make` (9 rookie/starter, 13.5 all-star, 18 legend) | 2 pts + 1 swish, ×3 streak, × difficulty |
| streak runs: `score ≤ makes` | a streak is a run of makes |
| timed runs: `shots ≤ seconds`, length 30 s – 30 min | a shot (flight + cooldown) takes well over a second |
| 30 posts / min per IP | |

A determined cheater can still post a plausible-but-fake score. Multiplayer boards are fully refereed by the
server (it re-simulates every throw).

## Deploy checklist

1. **Push the backend:** the Week 8 changes must be on GitHub (`sammy440/airhoop-api`) for Railway to build them.
2. **Railway:** new project from the repo, add PostgreSQL, set `DATABASE_URL=${{Postgres.DATABASE_URL}}`,
   `ALLOWED_ORIGINS=https://<app>.vercel.app`, `ENVIRONMENT=production`, then generate a domain.
   Migrations run on start. Check `https://<api>.up.railway.app/health/ready` returns `{"db": "ok"}`.
3. **Frontend:** import the repo in Vercel and set `NEXT_PUBLIC_API_URL=https://<api>`. Deploy.
4. **CORS:** make sure `ALLOWED_ORIGINS` lists the final Vercel URL (and any custom domain).
5. **Monitoring:** add an uptime check on `/health/ready` (1 min). Optionally create a Sentry project and set `SENTRY_DSN`.
6. **Smoke test:** open the public URL on a phone and a laptop: calibrate, play a timed game, post the score,
   create a room on one device, join by link on the other, finish a shootout.

## Manual test matrix

Mark ✅ / ⚠️ (note) / ❌. "Track" = camera tracking + throw detection; "Kbd/Tap" = no-camera play.

| Browser / device | Camera prompt + deny message | Track | Calibrate | Kbd/Tap | Multiplayer match | Notes |
|---|---|---|---|---|---|---|
| Chrome (macOS / Windows) | | | | | | |
| Edge (Windows) | | | | | | |
| Safari (macOS) | | | | | | |
| Firefox (desktop) | | | | | | |
| Safari (iPhone) | | | | | | |
| Chrome (Android) | | | | | | |

| Condition | Expected | Result |
|---|---|---|
| Bright room, plain wall | Coach stays green, throws detected | |
| Dim room / backlit window | Lighting warning in setup; tracking slower but works | |
| Baggy / dark clothing | Shoulders + hips found; may need more distance | |
| Two people in frame | Tracks one person; no phantom throws | |
| Camera blocked / denied | Clear message; Space / tap still plays | |
| Slow laptop (< 15 fps) | "Slow tracking" hint; lite model | |
| Wi-Fi drop mid-match | Reconnects within 30 s and restores the match | |
| `prefers-reduced-motion` on | No smooth scroll, no decorative animation | |
| Keyboard only | Every menu reachable, focus visible, Space shoots | |

## Demo video shot list (~45 s)

1. Landing page hero (3 s)
2. Step back, camera on, skeleton appears, coach turns green (5 s)
3. Calibration: three throws, "calibrated" (6 s)
4. Two swishes in a row, streak multiplier pops (8 s)
5. Customise the player: skin, hair, jersey colour (6 s)
6. Multiplayer: share the link, friend joins, shootout, results screen (12 s)
7. Leaderboard with your rank; end card "Shoot hoops with nothing but air" (5 s)

## Done when

> A stranger can open the link, calibrate, and finish a multiplayer match with a friend.

Everything for this works locally and is covered by tests and browser runs. It's done once the deploy
checklist is complete and the smoke test passes on the public URL.

Tests: backend 544 · frontend 83.
