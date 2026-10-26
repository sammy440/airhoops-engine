"""
Evaluate and tune the throw detector on labeled recordings.

    python -m airhoops_lab.evaluate          # metrics with current PARAMS
    python -m airhoops_lab.evaluate --tune   # grid search (needs enough data)

Targets (README Week 3): ≥90% of throws detected, <10% of non-throws trigger.
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass, replace

import pandas as pd

from .detector import PARAMS, Params, run
from .kinematics import arm_features
from .load import Clip, load_all

TARGET_RECALL = 0.90
TARGET_FALSE_RATE = 0.10
MIN_CLIPS_TO_TUNE = 5  # per class; below this any "best" params are just overfitting


@dataclass
class Metrics:
    throw_clips: int
    non_throw_clips: int
    detected: int  # throw clips with ≥1 event
    exact: int  # throw clips with exactly 1 event
    false_triggers: int  # non-throw clips with ≥1 event
    extra_events: int  # events beyond the first in throw clips

    @property
    def recall(self) -> float:
        return self.detected / self.throw_clips if self.throw_clips else float("nan")

    @property
    def false_rate(self) -> float:
        return self.false_triggers / self.non_throw_clips if self.non_throw_clips else float("nan")

    @property
    def passes(self) -> bool:
        return (
            self.throw_clips > 0
            and self.non_throw_clips > 0
            and self.recall >= TARGET_RECALL
            and self.false_rate < TARGET_FALSE_RATE
        )

    def score(self) -> float:
        """Higher is better: reward recall, punish false triggers hardest, then duplicates."""
        r = 0 if self.throw_clips == 0 else self.recall
        f = 0 if self.non_throw_clips == 0 else self.false_rate
        extra = self.extra_events / max(1, self.throw_clips)
        return r - 2 * f - 0.5 * extra


def features_for(clips: list[Clip]) -> dict[str, pd.DataFrame]:
    """Kinematics don't depend on detector params, so compute them once."""
    return {c.id: arm_features(c) for c in clips}


def evaluate(clips: list[Clip], params: Params = PARAMS, feats: dict[str, pd.DataFrame] | None = None):
    feats = feats or features_for(clips)
    rows = []
    for c in clips:
        events, _ = run(feats[c.id], c.hand, params)
        rows.append({"clip": c.id[:8], "label": c.label, "hand": c.hand, "fps": c.fps, "events": len(events),
                     "event_t": [round(e.t) for e in events]})
    df = pd.DataFrame(rows)
    throws = df[df.label == "throw"]
    others = df[df.label != "throw"]
    m = Metrics(
        throw_clips=len(throws),
        non_throw_clips=len(others),
        detected=int((throws.events >= 1).sum()),
        exact=int((throws.events == 1).sum()),
        false_triggers=int((others.events >= 1).sum()),
        extra_events=int((throws.events - 1).clip(lower=0).sum()),
    )
    return m, df


GRID = {
    "start_speed": [1.0, 1.5, 2.0],
    "min_peak_speed": [1.5, 2.0, 2.5, 3.0, 4.0],
    "min_extension": [0.55, 0.62, 0.7, 0.78],
    "min_extension_gain": [0.08, 0.12, 0.18, 0.25],
    "min_release_height": [-0.3, -0.15, 0.0],
}


def tune(clips: list[Clip], force: bool = False) -> tuple[Params, Metrics] | None:
    n_throw = sum(c.is_throw for c in clips)
    n_other = len(clips) - n_throw
    if not force and (n_throw < MIN_CLIPS_TO_TUNE or n_other < MIN_CLIPS_TO_TUNE):
        print(f"Not tuning: need ≥{MIN_CLIPS_TO_TUNE} throw and ≥{MIN_CLIPS_TO_TUNE} non-throw clips "
              f"(have {n_throw} / {n_other}). Record more in /lab, or pass --force.")
        return None
    feats = features_for(clips)
    best: tuple[float, float, Params, Metrics] | None = None
    keys = list(GRID)
    for values in itertools.product(*GRID.values()):
        p = replace(PARAMS, **dict(zip(keys, values)))
        m, _ = evaluate(clips, p, feats)
        # Tie-break: stay close to the hand-picked defaults (less overfit).
        drift = sum(abs(getattr(p, k) - getattr(PARAMS, k)) / (max(GRID[k]) - min(GRID[k])) for k in keys)
        cand = (m.score(), -drift, p, m)
        if best is None or cand[:2] > best[:2]:
            best = cand
    assert best
    return best[2], best[3]


def report(m: Metrics, df: pd.DataFrame) -> None:
    print(df.to_string(index=False))
    print()
    print(f"Throw clips:      {m.throw_clips}  detected {m.detected}  (recall {m.recall:.0%}, target ≥{TARGET_RECALL:.0%})")
    print(f"  exactly one:    {m.exact}   extra events: {m.extra_events}")
    print(f"Non-throw clips:  {m.non_throw_clips}  false triggers {m.false_triggers}"
          + (f"  (rate {m.false_rate:.0%}, target <{TARGET_FALSE_RATE:.0%})" if m.non_throw_clips else "  (no negatives recorded yet)"))
    print("PASS ✅" if m.passes else "Not passing yet ❌")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--force", action="store_true", help="tune even with too little data")
    args = ap.parse_args()

    clips = load_all()
    print(f"Loaded {len(clips)} clips\n")
    m, df = evaluate(clips)
    report(m, df)

    if args.tune:
        res = tune(clips, args.force)
        if res:
            p, tm = res
            print("\nBest params:")
            changed = {k: v for k, v in asdict(p).items() if getattr(PARAMS, k) != v}
            print(json.dumps(changed or "(defaults are already best)", indent=2))
            print(f"→ recall {tm.recall:.0%}, false rate {tm.false_rate:.0%}, extra {tm.extra_events}")
            print("Copy changed values into Params (detector.py) and DEFAULT_THROW_PARAMS (throwDetector.ts).")


if __name__ == "__main__":
    main()
