"""Plot helpers shared by the notebooks."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from .detector import PARAMS, Params, run
from .kinematics import arm_features
from .load import Clip

STATE_COLORS = {"PICKUP": "#7dd3fc", "WINDUP": "#fde68a", "THROW": "#fca5a5", "COOLDOWN": "#bbf7d0"}
SIDE_COLORS = {"left": "#1f77b4", "right": "#ea3a1d"}


def plot_clip(clip: Clip, axes=None):
    """Speed, wrist height and reach over time for both arms (recorded hand bold)."""
    if axes is None:
        _, axes = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    for side, color in SIDE_COLORS.items():
        df = arm_features(clip, side)
        lw = 2.5 if side == clip.hand else 1
        axes[0].plot(df.t, df.speed, color=color, lw=lw, label=f"{side} wrist")
        axes[1].plot(df.t, df.above_shoulder, color=color, lw=lw)
        axes[2].plot(df.t, df.extension, color=color, lw=lw)
    axes[0].set_ylabel("speed (torso/s)")
    axes[1].set_ylabel("height vs shoulder")
    axes[1].axhline(0, color="k", lw=0.5)
    axes[2].set_ylabel("reach (torso)")
    axes[2].set_xlabel("t (ms)")
    axes[0].set_title(f"{clip.label} · {clip.hand} hand · {clip.fps} fps · {clip.id[:8]}")
    axes[0].legend(loc="upper right")
    for ax in axes:
        ax.grid(alpha=0.3)
    return axes


def plot_detection(clip: Clip, params: Params = PARAMS, ax=None):
    """Recorded-hand speed with detector states shaded and throw events marked."""
    df = arm_features(clip)
    events, states = run(df, clip.hand, params)
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 3))
    t = df.t.to_numpy()
    for k in range(len(t) - 1):
        c = STATE_COLORS.get(states[k])
        if c:
            ax.axvspan(t[k], t[k + 1], color=c, alpha=0.5, lw=0)
    ax.plot(t, df.speed, color="#111", lw=2, label="speed")
    ax2 = ax.twinx()
    ax2.plot(t, df.extension, color="#ea3a1d", lw=1.5, ls="--", label="reach")
    ax2.axhline(params.min_extension, color="#ea3a1d", lw=0.7, ls=":")
    ax2.set_ylabel("reach (torso)", color="#ea3a1d")
    ax.axhline(params.min_peak_speed, color="#111", lw=0.7, ls=":")
    for e in events:
        ax.axvline(e.t, color="#16a34a", lw=2)
        ax.text(e.t, ax.get_ylim()[1] * 0.92, f" power {e.power:.0%}\n {e.angle:.0f}°", fontsize=8, color="#16a34a", va="top")
    ax.set_title(f"{clip.label} · {clip.hand} · {len(events)} event(s) · {clip.id[:8]}")
    ax.set_xlabel("t (ms)")
    ax.set_ylabel("speed (torso/s)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.5) for c in STATE_COLORS.values()]
    ax.legend(handles, STATE_COLORS.keys(), loc="upper left", fontsize=7, ncol=4)
    return ax, events


def scale_stability(clips: list[Clip]):
    """Shoulder width vs torso length variation per clip (why we normalize by torso)."""
    rows = []
    for c in clips:
        a, lm = c.aspect, c.lm

        def sq(i):
            return np.stack([lm[:, i, 0] * a, lm[:, i, 1]], 1)

        sw = np.linalg.norm(sq(11) - sq(12), axis=1)
        torso = np.linalg.norm((sq(11) + sq(12)) / 2 - (sq(23) + sq(24)) / 2, axis=1)
        rows.append({
            "clip": c.id[:8], "label": c.label,
            "shoulder max/min": np.nanmax(sw) / np.nanmin(sw),
            "torso max/min": np.nanmax(torso) / np.nanmin(torso),
        })
    import pandas as pd
    return pd.DataFrame(rows).round(2)
