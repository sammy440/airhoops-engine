"""
Python port of the browser pipeline (airhoops-frontend/src/lib/pose):
One Euro smoothing → square units → torso-normalized kinematics.
Keep the constants in sync with the TypeScript versions.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .load import (
    L_ELBOW, L_HIP, L_SHOULDER, L_WRIST,
    R_ELBOW, R_HIP, R_SHOULDER, R_WRIST,
    Clip,
)

# ── oneEuroFilter.ts ──
MIN_CUTOFF = 1.0
BETA = 1.5
D_CUTOFF = 1.0
RESET_GAP_MS = 300
SMOOTHED = [11, 12, 13, 14, 15, 16, 19, 20, 23, 24]

# ── kinematics.ts ──
VELOCITY_WINDOW_MS = 50
SCALE_EMA = 0.15
MIN_VISIBILITY = 0.5
# Torso length ≈ this × shoulder width when facing the camera (median of real data);
# only used before the hips have ever been seen.
SHOULDER_TO_TORSO = 2.3

ARM = {
    "left": (L_SHOULDER, L_ELBOW, L_WRIST, L_HIP),
    "right": (R_SHOULDER, R_ELBOW, R_WRIST, R_HIP),
}


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1 / (2 * math.pi * cutoff)
    return 1 / (1 + tau / dt)


class OneEuro:
    def __init__(self, min_cutoff=MIN_CUTOFF, beta=BETA, d_cutoff=D_CUTOFF):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = 0.0

    def __call__(self, x: float, t_ms: float) -> float:
        if self.x_prev is None:
            self.x_prev, self.t_prev = x, t_ms
            return x
        dt = max((t_ms - self.t_prev) / 1000, 1e-3)
        self.t_prev = t_ms
        dx = (x - self.x_prev) / dt
        a_d = _alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev
        a = _alpha(self.min_cutoff + self.beta * abs(dx_hat), dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev = x_hat, dx_hat
        return x_hat


def smooth(clip: Clip, min_cutoff=MIN_CUTOFF, beta=BETA) -> np.ndarray:
    """Returns a smoothed copy of clip.lm (x, y, z of SMOOTHED landmarks)."""
    out = clip.lm.copy()
    filters: dict[tuple[int, int], OneEuro] = {}
    last_t = -math.inf
    for k, t in enumerate(clip.t):
        frame = clip.lm[k]
        if np.isnan(frame[:, 0]).all() or t - last_t > RESET_GAP_MS:
            filters.clear()
        last_t = t
        for i in SMOOTHED:
            if np.isnan(frame[i, 0]):
                continue
            for c in range(3):
                f = filters.setdefault((i, c), OneEuro(min_cutoff, beta))
                out[k, i, c] = f(frame[i, c], t)
    return out


def arm_features(clip: Clip, side: str | None = None, lm: np.ndarray | None = None) -> pd.DataFrame:
    """
    Per-frame kinematics for one arm, matching KinematicsTracker in TS, plus a
    few extra columns useful for detection (wrist height vs shoulder / hip).

    Everything is normalized by TORSO LENGTH (shoulder midpoint → hip midpoint):
    shoulder width collapses when the player turns side-on to throw.

    Columns: t, speed, vx, vy (torso lengths/s, image orientation, +y down),
    angle (deg above horizontal), elbow (deg), extension (× torso),
    above_shoulder (torso, + = wrist above shoulder), below_hip (torso, + = wrist below hip),
    scale (torso length, square units), visible,
    other_above_shoulder (the other wrist, NaN if not visible), hands_apart (wrist to wrist, torso;
    NaN unless both wrists are visible), body_vx / body_vy (shoulder midpoint velocity, torso/s,
    image orientation; 0 while the shoulders aren't visible), lean (shoulder midpoint sideways
    from the hip midpoint, torso lengths, image x; NaN unless shoulders and hips are visible).
    """
    side = side or clip.hand
    lm = smooth(clip) if lm is None else lm
    s_i, e_i, w_i, h_i = ARM[side]
    a = clip.aspect

    def sq(i):
        return np.stack([lm[:, i, 0] * a, lm[:, i, 1]], axis=1)

    S, E, W, H = sq(s_i), sq(e_i), sq(w_i), sq(h_i)
    LS, RS, LH, RH = sq(L_SHOULDER), sq(R_SHOULDER), sq(L_HIP), sq(R_HIP)
    ok = lambda i: np.nan_to_num(lm[:, i, 3], nan=0.0) >= MIN_VISIBILITY  # noqa: E731
    shoulders_ok = ok(L_SHOULDER) & ok(R_SHOULDER)
    hips_ok = ok(L_HIP) & ok(R_HIP)
    vis = ok(w_i) & ok(s_i)

    torso = np.linalg.norm((LS + RS) / 2 - (LH + RH) / 2, axis=1)
    shoulders = np.linalg.norm(LS - RS, axis=1)

    # Body scale per frame (independent of which arm), same rules as TS bodyScale.
    sw = np.full(len(clip.t), np.nan)
    acc = 0.0
    no_person = np.isnan(lm[:, :, 0]).all(axis=1)
    for k in range(len(sw)):
        if no_person[k]:
            acc = 0.0  # TS KinematicsTracker.reset() when the pose is lost
            continue
        if shoulders_ok[k] and hips_ok[k]:
            raw = torso[k]
        elif acc == 0 and shoulders_ok[k]:
            raw = shoulders[k] * SHOULDER_TO_TORSO
        else:
            raw = acc  # hips out of view: hold the last known scale
        if not raw or raw <= 0:
            continue
        acc = raw if acc == 0 else acc + SCALE_EMA * (raw - acc)
        sw[k] = acc
    vis &= np.isfinite(sw)

    # Velocity: finite difference vs the newest sample at least VELOCITY_WINDOW_MS old,
    # never reaching back across a gap (TS clears the wrist history when the arm is lost).
    vx = np.zeros(len(clip.t))
    vy = np.zeros(len(clip.t))
    seg_start = 0
    for k in range(len(clip.t)):
        if not vis[k]:
            seg_start = k + 1
            continue
        if k == seg_start:
            continue
        j = k - 1
        while j > seg_start and clip.t[k] - clip.t[j] < VELOCITY_WINDOW_MS:
            j -= 1
        dt = (clip.t[k] - clip.t[j]) / 1000
        if dt <= 0:
            continue
        vx[k] = (W[k, 0] - W[j, 0]) / dt / sw[k]
        vy[k] = (W[k, 1] - W[j, 1]) / dt / sw[k]

    u, v = S - E, W - E
    cos = np.sum(u * v, axis=1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1))
    elbow = np.degrees(np.arccos(np.clip(cos, -1, 1)))

    speed = np.hypot(vx, vy)
    angle = np.where(speed > 0, np.degrees(np.arctan2(-vy, np.abs(vx))), 0.0)

    # The other arm (KinematicsTracker computes both arms every frame).
    os_i, _, ow_i, _ = ARM["left" if side == "right" else "right"]
    OS, OW = sq(os_i), sq(ow_i)
    other_vis = ok(ow_i) & ok(os_i) & np.isfinite(sw)
    other_above = np.where(other_vis, (OS[:, 1] - OW[:, 1]) / sw, np.nan)
    hands_apart = np.where(vis & other_vis, np.linalg.norm(W - OW, axis=1) / sw, np.nan)

    # Lean: the shoulders shifted sideways over the hips (the aim control).
    lean = np.where(shoulders_ok & hips_ok & np.isfinite(sw), ((LS[:, 0] + RS[:, 0]) / 2 - (LH[:, 0] + RH[:, 0]) / 2) / sw, np.nan)

    # Body velocity: shoulder midpoint, same finite difference as the wrist, history cleared
    # whenever the shoulders are lost (TS: KinematicsTracker.bodyHistory).
    M = (LS + RS) / 2
    body_ok = shoulders_ok & np.isfinite(sw)
    bvx = np.zeros(len(clip.t))
    bvy = np.zeros(len(clip.t))
    seg_start = 0
    for k in range(len(clip.t)):
        if not body_ok[k]:
            seg_start = k + 1
            continue
        if k == seg_start:
            continue
        j = k - 1
        while j > seg_start and clip.t[k] - clip.t[j] < VELOCITY_WINDOW_MS:
            j -= 1
        dt = (clip.t[k] - clip.t[j]) / 1000
        if dt <= 0:
            continue
        bvx[k] = (M[k, 0] - M[j, 0]) / dt / sw[k]
        bvy[k] = (M[k, 1] - M[j, 1]) / dt / sw[k]

    return pd.DataFrame(
        {
            "t": clip.t,
            "speed": speed,
            "vx": vx,
            "vy": vy,
            "angle": angle,
            "elbow": elbow,
            "extension": np.linalg.norm(W - S, axis=1) / sw,
            "above_shoulder": (S[:, 1] - W[:, 1]) / sw,
            "below_hip": (W[:, 1] - H[:, 1]) / sw,
            "scale": sw,
            "visible": vis,
            "other_above_shoulder": other_above,
            "hands_apart": hands_apart,
            "body_vx": bvx,
            "body_vy": bvy,
            "lean": lean,
        }
    )
