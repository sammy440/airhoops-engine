"""
Optional learned throw classifier (README Week 3, stretch goal).

Slides a window over each clip, summarizes kinematics into a feature vector,
and uses the clip label as a weak label for every window that contains a
candidate peak. Evaluated with GroupKFold by clip so windows from the same
clip never appear in both train and test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .kinematics import arm_features
from .load import Clip

WINDOW_MS = 600
STEP_MS = 100
FEATURES = ["peak_speed", "reach_gain", "max_reach", "max_height", "height_gain", "mean_up", "mean_abs_vx", "elbow_range", "duration_fast"]


def window_features(clip: Clip) -> pd.DataFrame:
    df = arm_features(clip)
    t = df.t.to_numpy()
    rows = []
    for start in np.arange(t[0], max(t[0] + 1, t[-1] - WINDOW_MS + 1), STEP_MS):
        w = df[(df.t >= start) & (df.t < start + WINDOW_MS) & df.visible]
        if len(w) < 4:
            continue
        rows.append({
            "clip_id": clip.id,
            "label": clip.label,
            "y": int(clip.is_throw),
            "start": start,
            "peak_speed": w.speed.max(),
            "reach_gain": w.extension.max() - w.extension.iloc[: max(1, len(w) // 3)].min(),
            "max_reach": w.extension.max(),
            "max_height": w.above_shoulder.max(),
            "height_gain": w.above_shoulder.max() - w.above_shoulder.iloc[: max(1, len(w) // 3)].min(),
            "mean_up": (-w.vy).mean(),
            "mean_abs_vx": w.vx.abs().mean(),
            "elbow_range": w.elbow.max() - w.elbow.min(),
            "duration_fast": (w.speed > 1.5).sum() * (WINDOW_MS / len(w)),
        })
    return pd.DataFrame(rows)


def dataset(clips: list[Clip]) -> pd.DataFrame:
    frames = [window_features(c) for c in clips]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def evaluate_models(data: pd.DataFrame, min_clips_per_class: int = 3) -> pd.DataFrame | str:
    """Cross-validated clip-level accuracy, or an explanation if there isn't enough data."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if data.empty:
        return "No windows to learn from."
    per_class = data.groupby("y").clip_id.nunique()
    if len(per_class) < 2 or per_class.min() < min_clips_per_class:
        have = {("throw" if k else "non-throw"): int(v) for k, v in per_class.items()}
        return f"Need ≥{min_clips_per_class} clips of BOTH throws and non-throws to train; have {have}."

    X, y, groups = data[FEATURES].to_numpy(), data.y.to_numpy(), data.clip_id.to_numpy()
    n_splits = min(5, int(per_class.min()))
    models = {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=0),
    }
    rows = []
    for name, model in models.items():
        correct = total = 0
        for train, test in GroupKFold(n_splits=n_splits).split(X, y, groups):
            model.fit(X[train], y[train])
            proba = model.predict_proba(X[test])[:, 1]
            # A clip is predicted "throw" if any of its windows is confidently a throw.
            test_df = data.iloc[test].assign(p=proba)
            per_clip = test_df.groupby("clip_id").agg(y=("y", "first"), p=("p", "max"))
            correct += int(((per_clip.p >= 0.5).astype(int) == per_clip.y).sum())
            total += len(per_clip)
        rows.append({"model": name, "clip accuracy": correct / total, "clips": total})
    return pd.DataFrame(rows)
