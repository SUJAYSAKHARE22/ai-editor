"""
Color Grader
============
Applies cinematic LUT-style color grades to frames using OpenCV.
Supports: cinematic, vivid, cool, warm, moody, none.
"""

import numpy as np
import cv2
from typing import Callable


def _build_curve(points: list) -> np.ndarray:
    """Build a 256-element LUT from control points [(in, out), ...]."""
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    xi = np.arange(256, dtype=float)
    return np.clip(np.interp(xi, xs, ys), 0, 255).astype(np.uint8)


# ── Cinematic (teal shadows, orange highlights, slight desaturation) ──
def _cinematic_lut():
    r_curve = _build_curve([(0, 0), (64, 70), (128, 140), (200, 210), (255, 245)])
    g_curve = _build_curve([(0, 0), (64, 60), (128, 128), (200, 195), (255, 240)])
    b_curve = _build_curve([(0, 20), (64, 75), (128, 130), (200, 180), (255, 210)])
    return r_curve, g_curve, b_curve


# ── Vivid (punchy saturation, contrast boost) ──
def _vivid_lut():
    c = _build_curve([(0, 0), (64, 50), (128, 140), (200, 215), (255, 255)])
    return c, c, c


# ── Cool (blue shift, lowered shadows) ──
def _cool_lut():
    r_curve = _build_curve([(0, 0), (128, 115), (255, 230)])
    g_curve = _build_curve([(0, 0), (128, 125), (255, 245)])
    b_curve = _build_curve([(0, 15), (128, 145), (255, 255)])
    return r_curve, g_curve, b_curve


# ── Warm (golden tones) ──
def _warm_lut():
    r_curve = _build_curve([(0, 5), (128, 145), (255, 255)])
    g_curve = _build_curve([(0, 0), (128, 128), (255, 240)])
    b_curve = _build_curve([(0, 0), (128, 110), (255, 210)])
    return r_curve, g_curve, b_curve


# ── Moody (crushed blacks, low saturation) ──
def _moody_lut():
    c = _build_curve([(0, 20), (64, 55), (128, 120), (200, 185), (255, 225)])
    return c, c, c


LUT_MAP = {
    "cinematic": _cinematic_lut,
    "vivid":     _vivid_lut,
    "cool":      _cool_lut,
    "warm":      _warm_lut,
    "moody":     _moody_lut,
}


class ColorGrader:
    def __init__(self, style: str = "cinematic"):
        self.style = style
        self._luts = None
        if style != "none" and style in LUT_MAP:
            self._luts = LUT_MAP[style]()

    def grade(self, frame: np.ndarray) -> np.ndarray:
        if self._luts is None:
            return frame

        r_lut, g_lut, b_lut = self._luts
        out = frame.copy()
        out[:, :, 0] = cv2.LUT(frame[:, :, 0], b_lut)  # B channel
        out[:, :, 1] = cv2.LUT(frame[:, :, 1], g_lut)  # G channel
        out[:, :, 2] = cv2.LUT(frame[:, :, 2], r_lut)  # R channel

        if self.style == "cinematic":
            # Slight desaturation
            hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] *= 0.85
            out = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
        elif self.style == "vivid":
            hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.25, 0, 255)
            out = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)

        return out
