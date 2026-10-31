"""
Throw detector state machine.

Mirror of airhoops-frontend/src/lib/pose/throwDetector.ts — the TypeScript
version is the source of truth for the game; this port exists so thresholds
can be explored and evaluated in the lab. Keep PARAMS and logic in sync.

Why it differs from the README sketch: in the first recordings the wrist often
never drops below the hip (players hold the "ball" at head height and push),
so PICKUP is tracked but not required. The reliable release signature is:
the arm extends with the wrist at/above shoulder height, then extension peaks
and/or speed falls away.

A second trigger, the elbow snap, catches pushes towards the camera, which look
short in 2D (little reach gained): both hands hold the ball overhead with the
elbow bent and still, then the elbow straightens quickly and the wrist rises.

Power comes from the arm's speed relative to the shoulders; a jump (the
shoulders rising fast just before release) adds to it, so jumping throws further
but isn't needed to throw.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Params:
    # Entering THROW
    start_speed: float = 1.5  # torso/s
    min_height_start: float = -0.35  # wrist vs shoulder (torso), must be at least this high
    # "Set point": a shot starts from a (nearly) still hand. Waving never pauses.
    set_window_ms: float = 300
    max_set_speed: float = 1.2  # torso/s, median over the set window
    # Validating a release
    min_peak_speed: float = 1.8  # torso/s
    # 2D reach: a push towards the camera looks shorter than it is, so keep this modest.
    min_extension: float = 0.5  # torso, arm reach at release
    min_extension_gain: float = 0.12  # torso, reach gained during the throw
    min_release_height: float = 0.4  # torso, wrist clearly above the shoulder (practised throws ≥ 0.63)
    min_angle: float = 5.0  # degrees above horizontal: shots go up; sideways swipes are waves
    # Beginners push from the chest: a lower release counts if it goes clearly up.
    # The waves that pass a lower height alone move at 11–22°, so they still fail.
    low_release_height: float = 0.0  # torso, wrist at least level with the shoulder
    low_release_min_angle: float = 30.0  # degrees
    # Ending THROW
    extension_drop: float = 0.04  # torso below max → released
    speed_drop_ratio: float = 0.7  # speed below this × peak → released (fires ~30 ms sooner than 0.45)
    min_throw_ms: float = 100  # real throws take ≥ ~100 ms; shorter = raising hands into position
    max_throw_ms: float = 900  # timeout back to IDLE
    lookback_ms: float = 400  # window to find the starting (minimum) extension
    cooldown_ms: float = 800
    # Informational states
    pickup_below_hip: float = -0.25  # wrist within this of the hip line → PICKUP
    windup_height: float = -0.1  # wrist this high and slow → WINDUP
    windup_max_speed: float = 1.5
    pickup_memory_ms: float = 2500
    # Power mapping (uncalibrated default), from the arm's speed relative to the shoulders.
    # First recordings peaked at 2.2–3.2 torso/s, so 1.5–5 maps them to ~20–50%.
    power_min_speed: float = 1.5
    power_max_speed: float = 5.0
    # Elbow snap: from a held two-handed set overhead, the elbow straightens fast.
    # Lab, Oct 31: recall on the aimed clips 72% → 94%, still no trigger on head
    # scratching or dribbling; one on a two-handed overhead wave.
    snap_bent: float = 150  # deg, elbow at most this bent at the set …
    snap_straight: float = 145  # … then at least this straight
    snap_set_height: float = 0.2  # torso, both wrists at least this far above the shoulders at the set
    snap_release_height: float = 0.35  # torso, shooting wrist at release
    snap_max_hands_apart: float = 0.8  # torso, both hands on the ball at the set
    snap_min_rise: float = 0.03  # torso, wrist rises from set to release
    snap_min_rate: float = 80  # deg/s of elbow opening
    snap_window_ms: float = 500  # how far back to look for the set
    snap_hold_ms: float = 200  # the hand is still (median speed ≤ max_set_speed) for this long before the set
    # Jump: peak shoulder rise in the last jump_window_ms. Standing throws rose 0.2–0.8 torso/s,
    # jumping ones 1.4–2.7.
    jump_min_rise: float = 0.8
    jump_full_rise: float = 2.4
    jump_window_ms: float = 500
    jump_power: float = 0.2  # power added by a full jump (uncalibrated)


PARAMS = Params()


@dataclass
class ThrowEvent:
    t: float
    power: float  # 0..1
    angle: float  # degrees above horizontal
    arc: float  # 0..1
    hand: str
    peak_speed: float
    arm_speed: float  # peak wrist speed relative to the shoulders
    jump: float  # 0..1
    lean: float | None  # shoulders over hips at release, torso lengths (None if not visible)
    extension: float
    height: float
    picked_up: bool
    duration_ms: float


@dataclass
class _Throw:
    t_start: float
    ext_start: float
    peak_speed: float = 0.0
    ext_max: float = 0.0
    height_at_max: float = -9.0
    vx_sum: float = 0.0
    vy_sum: float = 0.0
    t_max: float = 0.0
    arm_peak: float = 0.0


@dataclass
class _Frame:
    t: float
    elbow: float
    height: float
    other_height: float  # NaN if not visible
    hands_apart: float  # NaN unless both wrists visible
    speed: float
    arm_speed: float
    rise: float
    vx: float
    vy: float
    extension: float
    lean: float


def _clamp01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


@dataclass
class ThrowDetector:
    params: Params = field(default_factory=Params)
    state: str = "IDLE"  # IDLE | PICKUP | WINDUP | THROW | COOLDOWN
    _throw: _Throw | None = None
    _cooldown_until: float = 0.0
    _last_pickup_t: float = -1e9
    _hist: list[tuple[float, float]] = field(default_factory=list)  # (t, extension)
    _speeds: list[tuple[float, float]] = field(default_factory=list)  # (t, speed) for the set check
    _recent: list[_Frame] = field(default_factory=list)  # visible frames, for the elbow snap and jump
    # False after a timeout until the wrist slows down, so THROW can't re-trigger every frame.
    _armed: bool = True

    def update(self, t: float, f: dict, hand: str = "right") -> ThrowEvent | None:
        p = self.params
        if not f.get("visible", True) or not np.isfinite(f["speed"]):
            self._throw = None
            self.state = "COOLDOWN" if t < self._cooldown_until else "IDLE"
            return None

        ext, height, speed = f["extension"], f["above_shoulder"], f["speed"]
        body_vx, body_vy = f.get("body_vx", 0.0), f.get("body_vy", 0.0)
        arm_speed = float(np.hypot(f["vx"] - body_vx, f["vy"] - body_vy))
        self._recent.append(
            _Frame(t, f.get("elbow", np.nan), height, f.get("other_above_shoulder", np.nan), f.get("hands_apart", np.nan),
                   speed, arm_speed, -body_vy, f["vx"], f["vy"], ext, f.get("lean", np.nan))
        )
        keep = max(p.snap_window_ms + p.snap_hold_ms, p.jump_window_ms)
        while self._recent and t - self._recent[0].t > keep:
            self._recent.pop(0)
        self._hist.append((t, ext))
        while self._hist and t - self._hist[0][0] > p.lookback_ms:
            self._hist.pop(0)
        if f["below_hip"] > p.pickup_below_hip:
            self._last_pickup_t = t
        if speed < p.start_speed:
            self._armed = True

        if self.state == "COOLDOWN":
            if t < self._cooldown_until:
                return None
            self.state = "IDLE"

        # Median speed over the set window, *before* this frame.
        before = sorted(s for (ts, s) in self._speeds if t - p.set_window_ms <= ts < t)
        self._speeds.append((t, speed))
        while self._speeds and t - self._speeds[0][0] > p.set_window_ms:
            self._speeds.pop(0)
        settled = len(before) >= 2 and before[len(before) // 2] <= p.max_set_speed

        if self.state != "THROW":
            prev_ext = self._hist[-2][1] if len(self._hist) >= 2 else ext
            if self._armed and settled and speed >= p.start_speed and height >= p.min_height_start and ext > prev_ext:
                self._throw = _Throw(t_start=t, ext_start=min(e for _, e in self._hist))
                self.state = "THROW"
            elif (ev := self._snap(t, hand)) is not None:
                self.state = "COOLDOWN"
                self._cooldown_until = t + p.cooldown_ms
                return ev
            elif f["below_hip"] > p.pickup_below_hip:
                self.state = "PICKUP"
            elif height >= p.windup_height and speed < p.windup_max_speed:
                self.state = "WINDUP"
            else:
                self.state = "IDLE"
            if self.state != "THROW":
                return None

        th = self._throw
        assert th is not None
        if speed > th.peak_speed:
            th.peak_speed = speed
        th.arm_peak = max(th.arm_peak, arm_speed)
        # A snap can complete while the reach-based throw is still deciding (pushes towards the camera
        # often start it, then fail its reach-gained check): take the snap.
        if (ev := self._snap(t, hand)) is not None:
            self._throw = None
            self.state = "COOLDOWN"
            self._cooldown_until = t + p.cooldown_ms
            return ev
        if ext >= th.ext_max:
            th.ext_max, th.height_at_max, th.t_max = ext, height, t
        th.vx_sum += f["vx"]
        th.vy_sum += f["vy"]

        elapsed = t - th.t_start
        if elapsed > p.max_throw_ms:
            self._throw, self.state, self._armed = None, "IDLE", False
            return None
        released = elapsed >= p.min_throw_ms and (
            ext < th.ext_max - p.extension_drop or speed < th.peak_speed * p.speed_drop_ratio
        )
        if not released:
            return None

        self._throw = None
        angle = float(np.degrees(np.arctan2(-th.vy_sum, abs(th.vx_sum)))) if (th.vx_sum or th.vy_sum) else 0.0
        valid = (
            th.peak_speed >= p.min_peak_speed
            and th.ext_max >= p.min_extension
            and th.ext_max - th.ext_start >= p.min_extension_gain
            and angle >= p.min_angle
            and (
                th.height_at_max >= p.min_release_height
                or (th.height_at_max >= p.low_release_height and angle >= p.low_release_min_angle)
            )
        )
        if not valid:
            self.state = "IDLE"
            return None

        self.state = "COOLDOWN"
        self._cooldown_until = t + p.cooldown_ms
        jump = self._jump(t)
        return ThrowEvent(
            t=t,
            power=self._power(th.arm_peak, jump),
            angle=angle,
            arc=_clamp01((th.height_at_max + 0.2) / 1.2),
            hand=hand,
            peak_speed=th.peak_speed,
            arm_speed=th.arm_peak,
            jump=jump,
            lean=self._lean(),
            extension=th.ext_max,
            height=th.height_at_max,
            picked_up=t - self._last_pickup_t <= p.pickup_memory_ms,
            duration_ms=elapsed,
        )


    # ── Elbow snap and jump ──

    def _jump(self, t: float) -> float:
        """0..1: how fast the shoulders rose in the last jump_window_ms (a jump into the shot)."""
        p = self.params
        rise = max((r.rise for r in self._recent if r.t >= t - p.jump_window_ms), default=0.0)
        return _clamp01((rise - p.jump_min_rise) / (p.jump_full_rise - p.jump_min_rise))

    def _lean(self) -> float | None:
        lean = self._recent[-1].lean
        return float(lean) if np.isfinite(lean) else None

    def _power(self, arm_speed: float, jump: float) -> float:
        p = self.params
        return _clamp01((arm_speed - p.power_min_speed) / (p.power_max_speed - p.power_min_speed) + p.jump_power * jump)

    def _snap(self, t: float, hand: str) -> ThrowEvent | None:
        """The current frame ends an elbow snap from a held two-handed set overhead → a throw."""
        p = self.params
        k = self._recent[-1]
        if not (k.elbow >= p.snap_straight and k.height >= p.snap_release_height):
            return None
        window = [r for r in self._recent[:-1] if r.t >= t - p.snap_window_ms and np.isfinite(r.elbow)]
        if len(window) < 2:
            return None
        j = min(window, key=lambda r: r.elbow)  # the set: most bent (first if tied)
        if j.elbow > p.snap_bent or j.height < p.snap_set_height:
            return None
        # Both hands on the ball (NaN, i.e. not visible, fails these)
        if not (j.other_height >= p.snap_set_height and j.hands_apart <= p.snap_max_hands_apart):
            return None
        if k.height - j.height < p.snap_min_rise:
            return None
        seg = [r for r in self._recent if r.t >= j.t]
        peak = max(r.speed for r in seg)
        if peak < p.min_peak_speed:
            return None
        if (k.elbow - j.elbow) / max(1.0, t - j.t) * 1000 < p.snap_min_rate:
            return None
        if _median([r.speed for r in self._recent if j.t - p.snap_hold_ms <= r.t <= j.t]) > p.max_set_speed:
            return None
        vx = sum(r.vx for r in seg)
        vy = sum(r.vy for r in seg)
        angle = float(np.degrees(np.arctan2(-vy, abs(vx)))) if (vx or vy) else 0.0
        if angle < p.min_angle:
            return None
        arm_peak = max(r.arm_speed for r in seg)
        jump = self._jump(t)
        return ThrowEvent(
            t=t,
            power=self._power(arm_peak, jump),
            angle=angle,
            arc=_clamp01((k.height + 0.2) / 1.2),
            hand=hand,
            peak_speed=peak,
            arm_speed=arm_peak,
            jump=jump,
            lean=self._lean(),
            extension=k.extension,
            height=k.height,
            picked_up=t - self._last_pickup_t <= p.pickup_memory_ms,
            duration_ms=t - j.t,
        )


def _median(values: list[float]) -> float:
    """Upper median, like the TS port (sorted[n // 2])."""
    v = sorted(values)
    return v[len(v) // 2]


def run(features: pd.DataFrame, hand: str, params: Params = PARAMS) -> tuple[list[ThrowEvent], list[str]]:
    """Replays a feature table through a fresh detector. Returns (events, state per frame)."""
    det = ThrowDetector(params)
    events, states = [], []
    for row in features.to_dict("records"):
        ev = det.update(row["t"], row, hand)
        if ev:
            events.append(ev)
        states.append(det.state)
    return events, states


def params_dict(p: Params = PARAMS) -> dict:
    return asdict(p)
