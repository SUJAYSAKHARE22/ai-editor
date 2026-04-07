"""
Event Analyzer
==============
Analyzes per-frame cursor positions and classifies events:

  dwell       — cursor stationary for N frames  →  trigger smooth zoom-in
  click       — rapid micro-movement then immediate stop  →  ripple effect
  idle        — cursor barely moves for a long stretch  →  speed ramp
  scene_break — long idle OR large cursor teleport  →  chapter title card
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.config import Config
from utils.logger import get_logger


Event = Dict[str, Any]


class EventAnalyzer:
    def __init__(self, cfg: Config, fps: float, W: int, H: int):
        self.cfg = cfg
        self.fps = fps
        self.W   = W
        self.H   = H
        self.log = get_logger("analyzer", cfg.verbose)

    # ------------------------------------------------------------------
    def analyze(self, positions: List[Tuple[Optional[int], Optional[int]]]) -> List[Event]:
        velocities   = self._compute_velocities(positions)
        dwell_starts = self._detect_dwell(positions, velocities)
        click_frames = self._detect_clicks(velocities)
        idle_ranges  = self._detect_idle(velocities)
        scene_breaks = self._detect_scene_breaks(positions, velocities, idle_ranges)

        events: List[Event] = []

        for fi in dwell_starts:
            x, y = self._safe_pos(positions, fi)
            events.append({"type": "dwell", "frame": fi, "x": x, "y": y})

        for fi in click_frames:
            x, y = self._safe_pos(positions, fi)
            events.append({"type": "click", "frame": fi, "x": x, "y": y})

        for start, end in idle_ranges:
            events.append({"type": "idle", "start": start, "end": end})

        for fi in scene_breaks:
            x, y = self._safe_pos(positions, fi)
            events.append({"type": "scene_break", "frame": fi, "x": x, "y": y})

        return events

    # ── Velocity ────────────────────────────────────────────────────────
    def _compute_velocities(self, positions) -> np.ndarray:
        n   = len(positions)
        vel = np.zeros(n, dtype=float)
        for i in range(1, n):
            x0, y0 = self._safe_pos(positions, i - 1)
            x1, y1 = self._safe_pos(positions, i)
            vel[i] = float(np.hypot(x1 - x0, y1 - y0))
        return vel

    # ── Dwell detection ─────────────────────────────────────────────────
    def _detect_dwell(self, positions, velocities) -> List[int]:
        """Returns start frame of each contiguous dwell window."""
        radius   = 8                        # pixels — cursor must stay inside this circle
        min_dur  = self.cfg.dwell_frames
        n        = len(positions)
        starts   = []
        i        = 0
        while i < n:
            x0, y0 = self._safe_pos(positions, i)
            j = i + 1
            while j < n:
                xj, yj = self._safe_pos(positions, j)
                if np.hypot(xj - x0, yj - y0) > radius:
                    break
                j += 1
            if j - i >= min_dur:
                starts.append(i)
                i = j + 1
            else:
                i += 1
        return starts

    # ── Click detection ─────────────────────────────────────────────────
    def _detect_clicks(self, velocities) -> List[int]:
        """
        Heuristic: velocity spike (>15 px/frame) that is preceded
        AND followed by near-zero velocity (< 5 px/frame).
        """
        n      = len(velocities)
        clicks = []
        for i in range(2, n - 2):
            peak   = velocities[i]
            before = velocities[i - 2 : i].mean()
            after  = velocities[i + 1 : i + 3].mean()
            if peak > 15 and before < 5 and after < 5:
                clicks.append(i)
        return clicks

    # ── Idle detection ───────────────────────────────────────────────────
    def _detect_idle(self, velocities) -> List[Tuple[int, int]]:
        """Returns (start, end) frame pairs where cursor velocity < threshold."""
        threshold  = 3.0        # px / frame
        min_frames = self.cfg.min_idle_frames
        n          = len(velocities)
        ranges     = []
        i          = 0
        while i < n:
            if velocities[i] < threshold:
                j = i + 1
                while j < n and velocities[j] < threshold:
                    j += 1
                if j - i >= min_frames:
                    ranges.append((i, j))
                i = j
            else:
                i += 1
        return ranges

    # ── Scene break detection ────────────────────────────────────────────
    def _detect_scene_breaks(
        self,
        positions,
        velocities,
        idle_ranges: List[Tuple[int, int]],
    ) -> List[int]:
        breaks = []

        # Long idle sections
        for start, end in idle_ranges:
            if end - start >= self.cfg.chapter_idle_gap:
                breaks.append(end)

        # Cursor teleports > 30 % of screen width
        for i in range(1, len(positions)):
            x0, y0 = self._safe_pos(positions, i - 1)
            x1, y1 = self._safe_pos(positions, i)
            if np.hypot(x1 - x0, y1 - y0) > 0.3 * self.W:
                breaks.append(i)

        return sorted(set(breaks))

    # ── Helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _safe_pos(positions, idx: int) -> Tuple[int, int]:
        """Return position tuple, defaulting to (0,0) if None."""
        p = positions[idx]
        if p is None or p[0] is None:
            return (0, 0)
        return (int(p[0]), int(p[1]))
