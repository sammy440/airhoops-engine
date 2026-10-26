# Week 7: Multiplayer Gameplay and Server-Side Physics

**Goal:** Real matches with trustworthy scoring.

## Tasks

- [x] Server physics mirroring the client: `app/game/physics.py` is a line-for-line port of `physics.ts`
      (custom deterministic physics instead of Pymunk, see Week 4), proven by 480 cross-language parity cases
- [x] Client sends only `{power, angle, arc, t}`
- [x] Server validates ranges, rate-limits (cooldown + one ball in flight), enforces turns, picks the wind, re-simulates
- [x] Server broadcasts the authoritative `shot_result` (path samples + scored/missed + points)
- [x] Everyone sees the same outcome: your own shot predicts instantly with identical physics; the server decides;
      shootout shots by others replay from the server's path
- [x] Mode A: turn-based shootout (5 shots each, sudden death on ties; works for 2–4 players)
- [x] Mode B: timed race (30 s – 2 min in the UI, 30–300 s on the server)
- [x] Lobby: create/join by code, ready, synced countdown, results screen, rematch
- [ ] Opponent stick figure streaming (optional, off by default): skipped for now

## Done when

| Criterion | Status |
|---|---|
| Results match on both screens | ✅ identical `shot_result` to every player (tested); full shootout + race played in two browsers with identical boards/results |
| Obviously impossible throws are rejected | ✅ out-of-range / NaN / non-numeric / out-of-turn / too-fast / pre-countdown / post-buzzer throws refused (tested) |
| Dropped players handled gracefully | ✅ 30 s reconnect window with full match restore; turns time out meanwhile; forfeit after that or on leave |

Backend tests: 535 (incl. 24 match-engine, 6 match-over-WebSocket, 481 physics parity).
