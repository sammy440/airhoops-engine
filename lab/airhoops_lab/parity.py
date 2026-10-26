"""
Export recordings + the Python detector's events as fixtures for the frontend
replay test, so the TypeScript and Python pipelines can't silently drift.

    python -m airhoops_lab.parity
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from .detector import PARAMS, run
from .kinematics import arm_features
from .load import RECORDINGS_DIR, load_all

FRONTEND = Path(__file__).resolve().parents[3] / "airhoops-frontend"
FIXTURE_DIR = FRONTEND / "src" / "lib" / "pose" / "__fixtures__"


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.title() for w in rest)


def main() -> None:
    if not FRONTEND.exists():
        raise SystemExit(f"Frontend not found at {FRONTEND}")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    clips = load_all()
    raw = {}
    for p in sorted(RECORDINGS_DIR.glob("*.json")):
        data = json.loads(p.read_text())
        for r in data["recordings"] if "recordings" in data else [data]:
            raw.setdefault(r["id"], r)

    expected = []
    for c in clips:
        events, _ = run(arm_features(c), c.hand)
        expected.append({"id": c.id, "hand": c.hand, "label": c.label,
                         "events": [{_camel(k): v for k, v in asdict(e).items()} for e in events]})

    (FIXTURE_DIR / "recordings.json").write_text(json.dumps({"version": 1, "recordings": [raw[c.id] for c in clips]}))
    (FIXTURE_DIR / "expected-events.json").write_text(json.dumps({
        "generatedBy": "lab/airhoops_lab/parity.py",
        "params": {_camel(f.name): getattr(PARAMS, f.name) for f in fields(PARAMS)},
        "clips": expected,
    }, indent=1))
    n = sum(len(c["events"]) for c in expected)
    print(f"Wrote {len(clips)} clips / {n} expected events to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
