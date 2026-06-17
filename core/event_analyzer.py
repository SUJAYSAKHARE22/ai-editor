"""
Event Analyzer
==============
Classifies cursor events: dwell, click, idle, scene_break.
Also detects content regions for smart cropping.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.logger import get_logger

Event = Dict[str, Any]


class EventAnalyzer:
    def __init__(self, cfg, fps: float, W: int, H: int):
        self.cfg = cfg
        self.fps = fps
        self.W   = W
        self.H   = H
        self.log = get_logger("analyzer", cfg.verbose)

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

    def _compute_velocities(self, positions) -> np.ndarray:
        n   = len(positions)
        vel = np.zeros(n, dtype=float)
        for i in range(1, n):
            x0, y0 = self._safe_pos(positions, i - 1)
            x1, y1 = self._safe_pos(positions, i)
            vel[i] = float(np.hypot(x1 - x0, y1 - y0))
        return vel

    def _detect_dwell(self, positions, velocities) -> List[int]:
        radius  = 8
        min_dur = self.cfg.dwell_frames
        n       = len(positions)
        starts  = []
        i       = 0
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

    def _detect_clicks(self, velocities) -> List[int]:
        n      = len(velocities)
        clicks = []
        for i in range(2, n - 2):
            peak   = velocities[i]
            before = velocities[i - 2:i].mean()
            after  = velocities[i + 1:i + 3].mean()
            if peak > 15 and before < 5 and after < 5:
                clicks.append(i)
        return clicks

    def _detect_idle(self, velocities) -> List[Tuple[int, int]]:
        threshold  = 3.0
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

    def _detect_scene_breaks(self, positions, velocities,
                              idle_ranges: List[Tuple[int, int]]) -> List[int]:
        breaks = []
        for start, end in idle_ranges:
            if end - start >= self.cfg.chapter_idle_gap:
                breaks.append(end)
        for i in range(1, len(positions)):
            x0, y0 = self._safe_pos(positions, i - 1)
            x1, y1 = self._safe_pos(positions, i)
            if np.hypot(x1 - x0, y1 - y0) > 0.3 * self.W:
                breaks.append(i)
        return sorted(set(breaks))

    @staticmethod
    def _safe_pos(positions, idx: int) -> Tuple[int, int]:
        p = positions[idx]
        if p is None or p[0] is None:
            return (0, 0)
        return (int(p[0]), int(p[1]))
