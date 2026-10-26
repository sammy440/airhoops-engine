"""
Throw detector state machine (README §5.4, adapted to real recordings).

Mirror of airhoops-frontend/src/lib/pose/throwDetector.ts — the TypeScript
version is the source of truth for the game; this port exists so thresholds
can be explored and evaluated in the lab. Keep PARAMS and logic in sync.

Why it differs from the README sketch: in the first recordings the wrist often
never drops below the hip (players hold the "ball" at head height and push),
so PICKUP is tracked but not required. The reliable release signature is:
the arm extends with the wrist at/above shoulder height, then extension peaks
and/or speed falls away.
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
    min_peak_speed: float = 2.0  # torso/s
    min_extension: float = 0.62  # torso, arm reach at release
    min_extension_gain: float = 0.12  # torso, reach gained during the throw
    min_release_height: float = 0.4  # torso, wrist clearly above the shoulder (real throws ≥ 0.63)
    min_angle: float = 5.0  # degrees above horizontal: shots go up; sideways swipes are waves
    # Ending THROW
    extension_drop: float = 0.04  # torso below max → released
    speed_drop_ratio: float = 0.45  # speed below this × peak → released
    min_throw_ms: float = 100  # real throws take ≥ ~100 ms; shorter = raising hands into position
    max_throw_ms: float = 900  # timeout back to IDLE
    lookback_ms: float = 400  # window to find the starting (minimum) extension
    cooldown_ms: float = 800
    # Informational states
    pickup_below_hip: float = -0.25  # wrist within this of the hip line → PICKUP
    windup_height: float = -0.1  # wrist this high and slow → WINDUP
    windup_max_speed: float = 1.5
    pickup_memory_ms: float = 2500
    # Power mapping (Week 5 replaces with per-player calibration)
    # First recordings peaked at 2.2–3.2 torso/s, so 1.5–5 maps them to ~20–50%.
    power_min_speed: float = 1.5
    power_max_speed: float = 5.0


PARAMS = Params()


@dataclass
class ThrowEvent:
    t: float
    power: float  # 0..1
    angle: float  # degrees above horizontal
    arc: float  # 0..1
    hand: str
    peak_speed: float
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
    # False after a timeout until the wrist slows down, so THROW can't re-trigger every frame.
    _armed: bool = True

    def update(self, t: float, f: dict, hand: str = "right") -> ThrowEvent | None:
        p = self.params
        if not f.get("visible", True) or not np.isfinite(f["speed"]):
            self._throw = None
            self.state = "COOLDOWN" if t < self._cooldown_until else "IDLE"
            return None

        ext, height, speed = f["extension"], f["above_shoulder"], f["speed"]
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
            and th.height_at_max >= p.min_release_height
            and angle >= p.min_angle
        )
        if not valid:
            self.state = "IDLE"
            return None

        self.state = "COOLDOWN"
        self._cooldown_until = t + p.cooldown_ms
        return ThrowEvent(
            t=t,
            power=_clamp01((th.peak_speed - p.power_min_speed) / (p.power_max_speed - p.power_min_speed)),
            angle=angle,
            arc=_clamp01((th.height_at_max + 0.2) / 1.2),
            hand=hand,
            peak_speed=th.peak_speed,
            extension=th.ext_max,
            height=th.height_at_max,
            picked_up=t - self._last_pickup_t <= p.pickup_memory_ms,
            duration_ms=elapsed,
        )


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
