# Week 4: Game Scene with Virtual Ball and Net

**Goal:** A throw on camera launches a ball into a net on screen.

## Tasks

- [x] Game on `/play`, camera as picture-in-picture
- [x] Scene: court, hoop with net, ball
- [x] Physics: gravity, rim bounces, score when passing down through the hoop
- [x] Map `ThrowEvent` → launch (`v = base + power × scale`, angle from measured angle + arc)
- [x] Ball respawn after each shot
- [x] Keyboard fallback (tap Space = medium shot; hold to charge; ↑↓ arc)
- [x] Sound effects and score counter

**Deviation:** custom deterministic physics + Canvas 2D instead of Phaser 3 / Matter.js, so Week 7's
Python server can re-simulate shots with exact parity. See frontend CHANGELOG.

Extras: post-shot gauge showing your power vs the make zone ("Short, push ~8% harder"), your live
skeleton as the in-game shooter, ghost of the last shot, swish/bank/rim-out detection, streaks.

## Done when

| Criterion | Status |
|---|---|
| A strong, well-aimed throw scores | ✅ unit test: ideal launch swishes at 52–65°; keyboard medium shot scores in-browser |
| A weak throw falls short | ✅ unit test: 80% of ideal speed is short; 125% is long |
| Learnable within a few tries | 🟡 the gauge shows the make zone after every shot; needs a real playtest on camera |

## Playtest checklist (you)

1. Open `/play`, press **Let's play**, stand back until the coach chip says *Raise the ball above your head*.
2. Hands up, pause until the ball glows yellow (*Loaded. Shoot!*), push up and out.
3. Watch the gauge: aim for the green zone. Report if the zone feels unreachable or too easy.
