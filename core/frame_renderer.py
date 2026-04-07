"""
Frame Renderer
==============
Applies all cinematic effects to each frame, in order:

  1. Zoom + pan      (smooth eased crop-and-scale centered on cursor)
  2. Cursor highlight (soft glow ring)
  3. Click ripple    (expanding ring at click location)
  4. Letterbox bars  (top + bottom cinematic black bars)
  5. Chapter card    (fade-in/out title overlay at scene breaks)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from utils.config import Config
from utils.logger import get_logger


# ---------------------------------------------------------------------------
@dataclass
class FramePlan:
    """Everything the renderer needs for one frame."""
    zoom_level:    float = 1.0
    pan_x:         float = 0.5     # normalised centre [0 .. 1]
    pan_y:         float = 0.5
    cursor_x:      Optional[int] = None
    cursor_y:      Optional[int] = None
    ripples:       List[Dict[str, Any]] = field(default_factory=list)
    speed:         float = 1.0
    chapter_text:  Optional[str] = None
    chapter_alpha: float = 0.0
    skip:          bool = False     # True = drop frame (speed ramp)


# ---------------------------------------------------------------------------
class FrameRenderer:
    def __init__(
        self,
        cfg:    Config,
        fps:    float,
        W:      int,
        H:      int,
        events: List[Dict[str, Any]],
    ):
        self.cfg    = cfg
        self.fps    = fps
        self.W      = W
        self.H      = H
        self.events = events
        self.log    = get_logger("renderer", cfg.verbose)

        # Quick-access lookup tables
        self._dwell_events = {e["frame"]: e for e in events if e["type"] == "dwell"}
        self._click_events = {e["frame"]: e for e in events if e["type"] == "click"}
        self._scene_breaks = {e["frame"]: e for e in events if e["type"] == "scene_break"}
        self._idle_ranges  = [(e["start"], e["end"]) for e in events if e["type"] == "idle"]

    # -----------------------------------------------------------------------
    # Build per-frame plan
    # -----------------------------------------------------------------------
    def build_plan(self, total_frames: int) -> List[FramePlan]:
        cfg = self.cfg
        n   = total_frames

        # ── Collect cursor positions from events ───────────────────────
        # Use dwell / click events to build a full pan timeline
        pan_x = np.full(n, 0.5, dtype=float)
        pan_y = np.full(n, 0.5, dtype=float)
        last_nx, last_ny = 0.5, 0.5
        for i in range(n):
            ev = self._dwell_events.get(i) or self._click_events.get(i)
            if ev and ev.get("x") is not None:
                last_nx = ev["x"] / max(self.W, 1)
                last_ny = ev["y"] / max(self.H, 1)
            pan_x[i] = last_nx
            pan_y[i] = last_ny

        # ── Build zoom curve ───────────────────────────────────────────
        zoom = np.ones(n, dtype=float)
        win  = cfg.zoom_window
        hold = cfg.dwell_frames

        for fi in self._dwell_events:
            # Ramp in
            for j in range(win):
                idx = fi + j
                if idx < n:
                    t         = _ease_in_out(j / max(win, 1))
                    zoom[idx] = max(zoom[idx], 1.0 + (cfg.max_zoom - 1.0) * t)
            # Hold
            for j in range(hold):
                idx = fi + win + j
                if idx < n:
                    zoom[idx] = max(zoom[idx], cfg.max_zoom)
            # Ramp out
            ramp_out_start = fi + win + hold
            for j in range(win):
                idx = ramp_out_start + j
                if idx < n:
                    t         = _ease_in_out(1.0 - j / max(win, 1))
                    zoom[idx] = max(zoom[idx], 1.0 + (cfg.max_zoom - 1.0) * t)

        # Smooth the curve to remove jagged transitions
        zoom = _smooth(zoom, kernel=7)

        # ── Speed ramp — mark frames to skip ──────────────────────────
        skip = np.zeros(n, dtype=bool)
        if cfg.speed_ramp_enabled:
            for start, end in self._idle_ranges:
                span   = end - start
                n_keep = max(1, int(span / cfg.idle_speed))
                step   = max(2, span // n_keep)
                for j in range(span):
                    fi = start + j
                    if fi < n and j % step != 0:
                        skip[fi] = True

        # ── Chapter title cards ────────────────────────────────────────
        chapter_text  = [None] * n
        chapter_alpha = np.zeros(n, dtype=float)
        if cfg.chapters_enabled:
            chapter_num = 1
            fade        = 12
            dur         = cfg.chapter_title_frames
            for fi in sorted(self._scene_breaks):
                label = f"Section {chapter_num}"
                chapter_num += 1
                for j in range(dur):
                    idx = fi + j
                    if idx >= n:
                        break
                    if j < fade:
                        a = j / fade
                    elif j > dur - fade:
                        a = (dur - j) / max(fade, 1)
                    else:
                        a = 1.0
                    if a > chapter_alpha[idx]:
                        chapter_alpha[idx]  = a
                        chapter_text[idx]   = label

        # ── Assemble FramePlan list ────────────────────────────────────
        plans: List[FramePlan] = []
        for i in range(n):
            p = FramePlan(
                zoom_level    = float(np.clip(zoom[i], 1.0, cfg.max_zoom * 1.1)),
                pan_x         = float(np.clip(pan_x[i], 0.0, 1.0)),
                pan_y         = float(np.clip(pan_y[i], 0.0, 1.0)),
                skip          = bool(skip[i]),
                chapter_text  = chapter_text[i],
                chapter_alpha = float(chapter_alpha[i]),
            )

            # Active ripples at frame i
            if cfg.ripple_enabled:
                for cf, ev in self._click_events.items():
                    age = i - cf
                    if 0 <= age < cfg.ripple_frames:
                        p.ripples.append({
                            "x":   ev.get("x", self.W // 2),
                            "y":   ev.get("y", self.H // 2),
                            "age": age,
                        })

            plans.append(p)

        return plans

    # -----------------------------------------------------------------------
    # Render a single frame
    # -----------------------------------------------------------------------
    def render(self, frame: np.ndarray, frame_i: int, plan: FramePlan) -> np.ndarray:
        cfg = self.cfg
        out = frame.copy()

        # 1. Zoom + pan
        if plan.zoom_level > 1.001:
            out = self._apply_zoom(out, plan)

        # 2. Cursor highlight  (use plan pan position as cursor centre)
        cx = int(plan.pan_x * self.W)
        cy = int(plan.pan_y * self.H)
        out = self._draw_cursor_highlight(out, cx, cy)

        # 3. Click ripples
        for ripple in plan.ripples:
            out = self._draw_ripple(out, ripple["x"], ripple["y"], ripple["age"])

        # 4. Letterbox
        if cfg.letterbox_enabled:
            out = self._apply_letterbox(out)

        # 5. Chapter card
        if plan.chapter_text and plan.chapter_alpha > 0.0:
            out = self._draw_chapter_card(out, plan.chapter_text, plan.chapter_alpha)

        return out

    # ── Zoom + pan ──────────────────────────────────────────────────────
    def _apply_zoom(self, frame: np.ndarray, plan: FramePlan) -> np.ndarray:
        H, W = frame.shape[:2]
        z    = max(plan.zoom_level, 1.001)

        cw = int(W / z)
        ch = int(H / z)

        cx = int(plan.pan_x * W)
        cy = int(plan.pan_y * H)

        x1 = int(np.clip(cx - cw // 2, 0, W - cw))
        y1 = int(np.clip(cy - ch // 2, 0, H - ch))

        crop   = frame[y1 : y1 + ch, x1 : x1 + cw]
        return cv2.resize(crop, (W, H), interpolation=cv2.INTER_LINEAR)

    # ── Cursor highlight ────────────────────────────────────────────────
    def _draw_cursor_highlight(self, frame: np.ndarray, cx: int, cy: int) -> np.ndarray:
        cfg     = self.cfg
        overlay = frame.copy()
        bgr     = (cfg.cursor_color[2], cfg.cursor_color[1], cfg.cursor_color[0])
        r       = cfg.cursor_highlight_radius
        cv2.circle(overlay, (cx, cy), r,      bgr, 2)
        cv2.circle(overlay, (cx, cy), r // 2, bgr, 1)
        cv2.circle(overlay, (cx, cy), 4,      bgr, -1)
        return cv2.addWeighted(overlay, cfg.cursor_highlight_alpha,
                               frame,   1.0 - cfg.cursor_highlight_alpha, 0)

    # ── Click ripple ────────────────────────────────────────────────────
    def _draw_ripple(self, frame: np.ndarray, cx: int, cy: int, age: int) -> np.ndarray:
        cfg     = self.cfg
        t       = age / max(cfg.ripple_frames, 1)
        alpha   = max(0.0, 1.0 - t) * 0.7
        radius  = max(1, int(cfg.ripple_max_radius * _ease_out(t)))
        bgr     = (cfg.ripple_color[2], cfg.ripple_color[1], cfg.ripple_color[0])
        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy), radius,          bgr, 2)
        cv2.circle(overlay, (cx, cy), max(1, radius // 2), bgr, 1)
        return cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)

    # ── Letterbox ───────────────────────────────────────────────────────
    def _apply_letterbox(self, frame: np.ndarray) -> np.ndarray:
        H = frame.shape[0]
        bar = int(H * self.cfg.letterbox_ratio)
        if bar < 1:
            return frame
        out = frame.copy()
        out[:bar]      = 0
        out[H - bar:]  = 0
        return out

    # ── Chapter title card ──────────────────────────────────────────────
    def _draw_chapter_card(
        self, frame: np.ndarray, text: str, alpha: float
    ) -> np.ndarray:
        H, W    = frame.shape[:2]
        overlay = frame.copy()

        band_h = max(40, int(H * 0.12))
        band_y = H // 2 - band_h // 2
        cv2.rectangle(overlay, (0, band_y), (W, band_y + band_h), (0, 0, 0), -1)

        font      = cv2.FONT_HERSHEY_SIMPLEX
        scale     = max(0.5, self.cfg.chapter_font_scale * W / 1920)
        thickness = max(1, int(2 * scale))

        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        tx = (W - tw) // 2
        ty = band_y + (band_h + th) // 2

        # Shadow
        cv2.putText(overlay, text, (tx + 2, ty + 2),
                    font, scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
        # Main white text
        cv2.putText(overlay, text, (tx, ty),
                    font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

        return cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)


# ---------------------------------------------------------------------------
# Easing + smoothing helpers
# ---------------------------------------------------------------------------
def _ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 2


def _smooth(arr: np.ndarray, kernel: int = 5) -> np.ndarray:
    k = np.ones(kernel, dtype=float) / kernel
    return np.convolve(arr, k, mode="same")
