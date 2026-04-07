"""
Cursor Tracker
==============
Detects cursor position per frame.

Strategy:
  1. If user supplies a cursor CSV log  -> use that (most accurate).
  2. Otherwise detect via frame-diff:   find small high-contrast moving blob.
"""

import csv
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from utils.config import Config
from utils.logger import get_logger


CursorPos = Tuple[Optional[int], Optional[int]]   # (x, y)  or  (None, None)


class CursorTracker:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.log = get_logger("cursor", cfg.verbose)

    # ------------------------------------------------------------------
    def track(self, reader, total_frames: int) -> List[CursorPos]:
        if self.cfg.cursor_log:
            return self._from_csv(self.cfg.cursor_log, total_frames)
        return self._detect_optical(reader, total_frames)

    # ── CSV import ──────────────────────────────────────────────────────
    def _from_csv(self, path: str, total_frames: int) -> List[CursorPos]:
        self.log.info(f"  Loading cursor log: {path}")
        positions: List[CursorPos] = [(None, None)] * total_frames
        try:
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fi = int(row.get("frame", row.get("Frame", 0)))
                    x  = int(float(row.get("x", row.get("X", 0))))
                    y  = int(float(row.get("y", row.get("Y", 0))))
                    if 0 <= fi < total_frames:
                        positions[fi] = (x, y)
        except Exception as e:
            self.log.warning(f"  CSV error: {e} — falling back to optical detection")
            return [(None, None)] * total_frames

        return self._interpolate(positions)

    # ── Optical detection ───────────────────────────────────────────────
    def _detect_optical(self, reader, total_frames: int) -> List[CursorPos]:
        """
        Frame-diff approach:
          - Compute absolute difference between consecutive frames.
          - Find contours in the diff mask.
          - Score each contour by size, shape, and contrast to pick the cursor.
          - Smooth over a small window to reduce jitter.
        """
        self.log.info("  Detecting cursor via frame-diff (no cursor log provided)")
        positions: List[CursorPos] = []
        prev_gray = None
        history: List[CursorPos] = []          # recent known positions for smoothing

        for i, frame in enumerate(reader.iter_frames()):
            if i >= total_frames:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_gray is None:
                positions.append((None, None))
                prev_gray = gray
                continue

            # --- Frame diff ---
            diff = cv2.absdiff(gray, prev_gray)
            _, mask = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)

            # Morphological cleanup to remove noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Find contours
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            pos = self._pick_cursor_contour(contours, gray)

            if pos is not None:
                history.append(pos)
                if len(history) > 5:
                    history.pop(0)
                # Median smooth
                xs = [c[0] for c in history]
                ys = [c[1] for c in history]
                pos = (int(np.median(xs)), int(np.median(ys)))

            positions.append(pos)          # may be None
            prev_gray = gray

        return self._interpolate(positions)

    # ------------------------------------------------------------------
    def _pick_cursor_contour(
        self,
        contours,
        gray: np.ndarray,
    ) -> Optional[Tuple[int, int]]:
        """
        Among all diff contours pick the one most likely to be the cursor:
          - Small area (cursor is small: 8–2500 px²)
          - Roughly square bounding box (aspect ratio > 0.2)
          - High contrast patch
        """
        H, W = gray.shape
        best_score = -1.0
        best_pos: Optional[Tuple[int, int]] = None

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 8 or area > 2500:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect = min(w, h) / max(w, h, 1)
            if aspect < 0.2:
                continue

            # Penalise contours very close to the frame edges
            edge_penalty = (x / max(W, 1)) * 0.3 + (y / max(H, 1)) * 0.3

            # Contrast inside the patch
            patch    = gray[y : y + h, x : x + w]
            contrast = float(patch.std()) / 128.0

            score = contrast * aspect - edge_penalty
            if score > best_score:
                best_score = score
                best_pos   = (x + w // 2, y + h // 2)

        return best_pos

    # ── Interpolation ───────────────────────────────────────────────────
    @staticmethod
    def _interpolate(positions: List[CursorPos]) -> List[CursorPos]:
        """Linear interpolation between known (non-None) positions."""
        result = list(positions)
        n      = len(result)

        def is_known(p) -> bool:
            return p is not None and p[0] is not None

        # First known index
        first = next((i for i in range(n) if is_known(result[i])), None)
        if first is None:
            # No detections at all — return centre of… we don't know resolution,
            # so just return (0,0) placeholders so downstream code doesn't crash.
            return [(0, 0)] * n

        # Fill everything before the first known with that value
        for i in range(first):
            result[i] = result[first]

        # Walk forward and fill gaps by linear interpolation
        prev = first
        for i in range(first + 1, n):
            if is_known(result[i]):
                if i - prev > 1:
                    x0, y0 = result[prev]   # type: ignore[misc]
                    x1, y1 = result[i]      # type: ignore[misc]
                    for j in range(prev + 1, i):
                        t        = (j - prev) / (i - prev)
                        result[j] = (int(x0 + t * (x1 - x0)),
                                     int(y0 + t * (y1 - y0)))
                prev = i

        # Fill tail
        for i in range(prev + 1, n):
            result[i] = result[prev]

        return result
