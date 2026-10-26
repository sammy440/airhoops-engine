"""Load AirHoops landmark recordings (single clips or "Download all" bundles)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "recordings"

# Landmark indices stored by the recorder (README §7.1).
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_INDEX, R_INDEX = 19, 20
L_HIP, R_HIP = 23, 24
RECORDED = [11, 12, 13, 14, 15, 16, 19, 20, 23, 24]

THROW_LABELS = {"throw"}


@dataclass
class Clip:
    id: str
    label: str
    hand: str  # "left" | "right" (the person's own hand)
    fps: float
    aspect: float  # video width / height
    t: np.ndarray  # (n,) ms since start
    # (n, 33, 4) x, y, z, visibility. NaN where not recorded / no person.
    lm: np.ndarray
    source: str

    @property
    def is_throw(self) -> bool:
        return self.label in THROW_LABELS

    def __repr__(self) -> str:
        return f"Clip({self.label}, {self.hand}, {len(self.t)}f @ {self.fps}fps, {self.id[:4]})"


def _parse(rec: dict, source: str) -> Clip:
    frames = rec["frames"]
    n = len(frames)
    lm = np.full((n, 33, 4), np.nan)
    t = np.empty(n)
    for k, f in enumerate(frames):
        t[k] = f["t"]
        for p in f["landmarks"]:
            lm[k, p["i"]] = (p["x"], p["y"], p["z"], p["v"])
    v = rec.get("video") or {"width": 1280, "height": 720}
    return Clip(
        id=rec["id"],
        label=rec["label"],
        hand=rec.get("hand", "right"),
        fps=rec.get("fps", 0),
        aspect=v["width"] / v["height"],
        t=t,
        lm=lm,
        source=source,
    )


def load_file(path: str | Path) -> list[Clip]:
    path = Path(path)
    data = json.loads(path.read_text())
    recs = data["recordings"] if "recordings" in data else [data]
    return [_parse(r, path.name) for r in recs]


def load_all(directory: str | Path = RECORDINGS_DIR) -> list[Clip]:
    """Loads every .json under `directory`, de-duplicated by recording id."""
    clips: dict[str, Clip] = {}
    for p in sorted(Path(directory).glob("*.json")):
        for c in load_file(p):
            clips.setdefault(c.id, c)
    return list(clips.values())
