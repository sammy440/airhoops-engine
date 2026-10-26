"""Lab tests: kinematics invariances, detector behaviour (mirrors throwDetector.test.ts), classifier plumbing."""

import numpy as np
import pandas as pd

from airhoops_lab.classifier import FEATURES, evaluate_models
from airhoops_lab.detector import ThrowDetector
from airhoops_lab.kinematics import arm_features
from airhoops_lab.load import Clip

ASPECT = 16 / 9


def synthetic_clip(vx=0.6, vy=-0.6, scale=1.0, half_width=0.1, frames=10, fps=30):
    """Left wrist moving in a straight line; positions in square units like kinematics.test.ts."""
    t = np.arange(frames) * 1000 / fps
    lm = np.full((frames, 33, 4), np.nan)
    for k, tk in enumerate(t):
        s = tk / 1000
        pts = {11: (0.9 - half_width, 0.4), 12: (0.9 + half_width, 0.4), 13: (0.8, 0.55), 14: (1.0, 0.55),
               15: (0.8 + vx * s, 0.7 + vy * s), 16: (0.9, 0.7),
               23: (0.9 - half_width * 0.8, 0.8), 24: (0.9 + half_width * 0.8, 0.8)}
        for i, (x, y) in pts.items():
            lm[k, i] = (x * scale / ASPECT, y * scale, 0, 1)
    return Clip(id="synthetic", label="throw", hand="left", fps=fps, aspect=ASPECT, t=t, lm=lm, source="test")


def test_speed_in_torso_lengths():
    # 0.6 units/s horizontally with a 0.4 torso → 1.5 torso/s (smoothing lags a little early on)
    df = arm_features(synthetic_clip(vx=0.6, vy=0))
    assert abs(df.speed.iloc[-1] - 1.5) < 0.1


def test_side_on_invariance():
    # Shoulders overlapping on camera must not change the measured speed.
    base = arm_features(synthetic_clip()).speed.iloc[-1]
    side_on = arm_features(synthetic_clip(half_width=0.005)).speed.iloc[-1]
    assert abs(side_on - base) < 1e-9


def test_distance_invariance_within_smoothing_lag():
    # Known limitation (CHANGELOG): One Euro adapts to on-screen speed, so a
    # player twice as far gets slightly more lag while speed ramps up (~5%).
    base = arm_features(synthetic_clip()).speed.iloc[-1]
    far = arm_features(synthetic_clip(scale=0.5)).speed.iloc[-1]
    assert abs(far - base) / base < 0.07


def _f(**kw):
    row = {"speed": 0.0, "vx": 0.0, "vy": 0.0, "extension": 0.45, "above_shoulder": 0.2, "below_hip": -1.0, "visible": True}
    row.update(kw)
    return row


def clean_throw(det, t0):
    frames = [
        _f(speed=0.2, extension=0.45),
        _f(speed=0.3, extension=0.45),
        _f(speed=0.3, extension=0.45),
        _f(speed=2.5, extension=0.55, vx=1.5, vy=-2),
        _f(speed=4.0, extension=0.7, vx=2.5, vy=-3),
        _f(speed=3.5, extension=0.85, vx=2, vy=-2.8, above_shoulder=0.5),
        _f(speed=1.2, extension=0.78, vx=0.5, vy=-1),
    ]
    ev = None
    for i, f in enumerate(frames):
        ev = det.update(t0 + i * 50, f) or ev
    return ev


def test_clean_throw_matches_typescript_expectations():
    det = ThrowDetector()
    ev = clean_throw(det, 0)
    assert ev is not None
    p = det.params
    assert abs(ev.power - (4 - p.power_min_speed) / (p.power_max_speed - p.power_min_speed)) < 1e-9
    assert abs(ev.arc - 0.7 / 1.2) < 1e-9
    assert ev.angle > 40
    assert det.state == "COOLDOWN"


def test_cooldown_then_accepts_again():
    det = ThrowDetector()
    assert clean_throw(det, 0) is not None
    assert clean_throw(det, 300) is None
    assert clean_throw(det, 2000) is not None


def test_wave_is_rejected():
    det = ThrowDetector()
    for i in range(30):
        assert det.update(i * 33, _f(speed=3, vx=3, extension=0.5 + np.sin(i) * 0.02)) is None


def test_continuous_motion_never_starts_a_throw():
    # A big, fast, extending, upward motion — but the hand never paused first (waving).
    det = ThrowDetector()
    for i in range(40):
        ext = 0.5 + 0.35 * abs(np.sin(i / 3))
        assert det.update(i * 50, _f(speed=3.5, vx=1, vy=-3, extension=ext, above_shoulder=0.7)) is None


def test_sideways_swipe_is_rejected():
    det = ThrowDetector()
    frames = [_f(speed=0.2)] * 3 + [
        _f(speed=2.5, extension=0.55, vx=3, vy=0.1),
        _f(speed=4.0, extension=0.7, vx=4, vy=0.1),
        _f(speed=3.5, extension=0.85, vx=3.5, vy=0, above_shoulder=0.6),
        _f(speed=1.0, extension=0.78, vx=1, vy=0),
    ]
    assert all(det.update(i * 50, f) is None for i, f in enumerate(frames))


def test_timeout_does_not_retrigger_every_frame():
    det = ThrowDetector()
    for i in range(40):
        det.update(i * 33, _f(speed=2 + i * 0.1, extension=0.4 + i * 0.01))
    assert det.state == "IDLE"


def test_classifier_trains_when_both_classes_present():
    rng = np.random.default_rng(0)
    rows = []
    for c in range(8):
        y = c % 2
        for w in range(6):
            feats = {f: rng.normal(2.0 if y else 0.5, 0.2) for f in FEATURES}
            rows.append({"clip_id": f"c{c}", "label": "throw" if y else "wave", "y": y, "start": w * 100, **feats})
    result = evaluate_models(pd.DataFrame(rows))
    assert isinstance(result, pd.DataFrame)
    assert (result["clip accuracy"] >= 0.9).all()


def test_classifier_explains_missing_data():
    rows = [{"clip_id": "a", "label": "throw", "y": 1, "start": 0, **{f: 1.0 for f in FEATURES}}]
    assert "Need" in evaluate_models(pd.DataFrame(rows))
