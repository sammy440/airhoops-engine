# Week 6: FastAPI Backend, Auth, and WebSocket Rooms

**Goal:** A working server that can create rooms and relay events.

## Tasks

- [x] FastAPI, Pydantic schemas, SQLModel, Alembic migrations (`0001` initial)
- [x] Postgres tables: `users`, `matches`, `throws`, `scores`
- [x] Guest sessions: nickname + bearer token (hash stored)
- [x] REST: `POST /rooms`, `POST /rooms/{code}/join`, `GET /leaderboard` (+ auth, room preview, scores)
- [x] WebSocket `/ws/{room_code}` with a connection manager
- [x] Room lifecycle: lobby, ready, in-progress, finished (+ rematch)
- [x] Heartbeats, reconnect handling (30 s seat grace), cleanup of empty rooms
- [x] CORS and environment config (`.env.example`)
- [x] Frontend `/multiplayer`: guest nickname, create/join by code or invite link, live presence, ready-up

## Done when

| Criterion | Status |
|---|---|
| Two browser tabs join the same room and see each other's presence | ✅ verified with two isolated browser profiles |
| Rooms survive a brief disconnect | ✅ page reload keeps the seat; others see "lost connection" → "is back" |
| Rooms clean up when everyone leaves | ✅ room gone ~32 s after both tabs closed |

Backend: 24 tests (REST, auth, leaderboard, presence, lifecycle, grace, heartbeat, cleanup, second tab, leave).
