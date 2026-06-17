"""
Frame Renderer (Upgraded)
=========================
Per-frame effect engine combining all effects:
  1. Zoom + pan         (smooth cursor tracking)
  2. Color grade        (LUT-based cinematic look)
  3. Cursor highlight   (glow ring)
  4. Click ripple       (expanding rings)
  5. Feature callouts   (branded pill labels at dwell points)
  6. Chapter title card (branded)
  7. Gradient bar       (bottom accent)
  8. Logo watermark     (top-right)
  9. Letterbox          (cinematic bars)
 10. Intro / outro card (brand identity frames)
 11. Caption overlays   (optional)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from core.color_grader import ColorGrader
from core.overlay_renderer import OverlayRenderer
from utils.logger import get_logger

FEATURE_LABELS = [
    "Smart Detection",
    "One-Click Action",
    "Real-Time Preview",
    "Seamless Integration",
    "Instant Results",
    "AI-Powered",
    "Lightning Fast",
    "Zero Config",
]


def _ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 2


def _smooth(arr: np.ndarray, kernel: int = 5) -> np.ndarray:
    k = np.ones(kernel, dtype=float) / kernel
    return np.convolve(arr, k, mode="same")


@dataclass
class FramePlan:
    zoom_level:        float = 1.0
    pan_x:             float = 0.5
    pan_y:             float = 0.5
    cursor_x:          Optional[int] = None
    cursor_y:          Optional[int] = None
    ripples:           List[Dict[str, Any]] = field(default_factory=list)
    speed:             float = 1.0
    chapter_text:      Optional[str] = None
    chapter_alpha:     float = 0.0
    chapter_num:       int = 1
    skip:              bool = False
    is_intro:          bool = False
    intro_progress:    float = 0.0
    is_outro:          bool = False
    outro_frame_i:     int = 0
    outro_start:       int = 0
    callout_text:      Optional[str] = None
    callout_alpha:     float = 0.0
    callout_cx:        int = 0
    callout_cy:        int = 0
    caption_text:      Optional[str] = None
    caption_alpha:     float = 0.0


class FrameRenderer:
    def __init__(self, cfg, fps: float, W: int, H: int,
                 events: List[Dict[str, Any]], total_frames: int):
        self.cfg    = cfg
        self.fps    = fps
        self.W      = W
        self.H      = H
        self.events = events
        self.total  = total_frames
        self.log    = get_logger("renderer", cfg.verbose)

        self._dwell_events = {e["frame"]: e for e in events if e["type"] == "dwell"}
        self._click_events = {e["frame"]: e for e in events if e["type"] == "click"}
        self._scene_breaks = {e["frame"]: e for e in events if e["type"] == "scene_break"}
        self._idle_ranges  = [(e["start"], e["end"]) for e in events if e["type"] == "idle"]

        self._grader  = ColorGrader(cfg.color_grade)
        self._overlay = OverlayRenderer(cfg, W, H, total_frames, fps)

        # Intro / outro durations
        self._intro_frames = int(fps * 2.5) if cfg.brand_name else 0
        self._outro_frames = int(fps * 3.0) if cfg.brand_name else 0
        self._outro_start  = max(0, total_frames - self._outro_frames)

    # ───────────────────────────────────────────────────────────────────
    def build_plan(self, total_frames: int) -> List[FramePlan]:
        cfg = self.cfg
        n   = total_frames

        # ── Pan timeline ───────────────────────────────────────────────
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

        # ── Zoom curve ─────────────────────────────────────────────────
        zoom = np.ones(n, dtype=float)
        win  = cfg.zoom_window
        hold = cfg.dwell_frames

        for fi in self._dwell_events:
            for j in range(win):
                idx = fi + j
                if idx < n:
                    t = _ease_in_out(j / max(win, 1))
                    zoom[idx] = max(zoom[idx], 1.0 + (cfg.max_zoom - 1.0) * t)
            for j in range(hold):
                idx = fi + win + j
                if idx < n:
                    zoom[idx] = max(zoom[idx], cfg.max_zoom)
            for j in range(win):
                idx = fi + win + hold + j
                if idx < n:
                    t = _ease_in_out(1.0 - j / max(win, 1))
                    zoom[idx] = max(zoom[idx], 1.0 + (cfg.max_zoom - 1.0) * t)

        zoom = _smooth(zoom, kernel=7)

        # ── Speed ramp ─────────────────────────────────────────────────
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

        # ── Chapter cards ───────────────────────────────────────────────
        chapter_text  = [None] * n
        chapter_alpha = np.zeros(n, dtype=float)
        chapter_nums  = [1] * n

        if cfg.chapters_enabled:
            chapter_num = 1
            fade  = 15
            dur   = cfg.chapter_title_frames
            for fi in sorted(self._scene_breaks):
                label = f"Section {chapter_num:02d}"
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
                        chapter_alpha[idx] = a
                        chapter_text[idx]  = label
                        chapter_nums[idx]  = chapter_num
                chapter_num += 1

        # ── Feature callouts at dwell points ────────────────────────────
        callout_text  = [None] * n
        callout_alpha = np.zeros(n, dtype=float)
        callout_cx    = [self.W // 2] * n
        callout_cy    = [self.H // 2] * n
        label_idx     = 0
        fade_dur      = 12

        for fi, ev in self._dwell_events.items():
            label = FEATURE_LABELS[label_idx % len(FEATURE_LABELS)]
            label_idx += 1
            dur = cfg.dwell_frames + cfg.zoom_window * 2
            for j in range(dur):
                idx = fi + j
                if idx >= n:
                    break
                if j < fade_dur:
                    a = j / fade_dur
                elif j > dur - fade_dur:
                    a = (dur - j) / max(fade_dur, 1)
                else:
                    a = 1.0
                if a > callout_alpha[idx]:
                    callout_alpha[idx] = a
                    callout_text[idx]  = label
                    callout_cx[idx]    = ev.get("x", self.W // 2)
                    callout_cy[idx]    = ev.get("y", self.H // 2)

        # ── Assemble plans ──────────────────────────────────────────────
        plans: List[FramePlan] = []
        for i in range(n):
            is_intro = i < self._intro_frames
            is_outro = i >= self._outro_start

            p = FramePlan(
                zoom_level     = float(np.clip(zoom[i], 1.0, cfg.max_zoom * 1.1)),
                pan_x          = float(np.clip(pan_x[i], 0.0, 1.0)),
                pan_y          = float(np.clip(pan_y[i], 0.0, 1.0)),
                skip           = bool(skip[i]),
                chapter_text   = chapter_text[i],
                chapter_alpha  = float(chapter_alpha[i]),
                chapter_num    = int(chapter_nums[i]),
                is_intro       = is_intro,
                intro_progress = i / max(self._intro_frames - 1, 1) if is_intro else 0.0,
                is_outro       = is_outro,
                outro_frame_i  = i,
                outro_start    = self._outro_start,
                callout_text   = callout_text[i],
                callout_alpha  = float(callout_alpha[i]),
                callout_cx     = callout_cx[i],
                callout_cy     = callout_cy[i],
            )

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

    # ───────────────────────────────────────────────────────────────────
    def render(self, frame: np.ndarray, frame_i: int, plan: FramePlan) -> np.ndarray:
        cfg = self.cfg
        out = frame.copy()

        # 1. Zoom + pan
        if plan.zoom_level > 1.001:
            out = self._apply_zoom(out, plan)

        # 2. Color grade
        out = self._grader.grade(out)

        # 3. Cursor highlight
        cx = int(plan.pan_x * self.W)
        cy = int(plan.pan_y * self.H)
        out = self._draw_cursor_highlight(out, cx, cy)

        # 4. Click ripples
        for ripple in plan.ripples:
            out = self._draw_ripple(out, ripple["x"], ripple["y"], ripple["age"])

        # 5. Feature callout
        if plan.callout_text and plan.callout_alpha > 0.0:
            out = self._overlay.draw_feature_callout(
                out, plan.callout_cx, plan.callout_cy,
                plan.callout_text, plan.callout_alpha
            )

        # 6. Chapter card
        if plan.chapter_text and plan.chapter_alpha > 0.0:
            out = self._overlay.draw_chapter_card(
                out, plan.chapter_text, plan.chapter_alpha, plan.chapter_num
            )

        # 7. Caption
        if plan.caption_text and plan.caption_alpha > 0.0:
            out = self._overlay.draw_caption(out, plan.caption_text, plan.caption_alpha)

        # 8. Gradient bar
        out = self._overlay.draw_gradient_bar(out)

        # 9. Logo watermark
        if cfg.add_logo:
            out = self._overlay.draw_logo_watermark(out, alpha=0.6)

        # 10. Letterbox
        if cfg.letterbox_enabled:
            out = self._apply_letterbox(out)

        # 11. Intro overlay
        if plan.is_intro:
            out = self._overlay.draw_intro(out, frame_i, self._intro_frames)

        # 12. Outro overlay
        if plan.is_outro:
            out = self._overlay.draw_outro(out, plan.outro_frame_i, plan.outro_start)

        return out

    # ── Zoom + pan ──────────────────────────────────────────────────────
    def _apply_zoom(self, frame: np.ndarray, plan: FramePlan) -> np.ndarray:
        H, W = frame.shape[:2]
        z    = max(plan.zoom_level, 1.001)
        cw   = int(W / z)
        ch   = int(H / z)
        cx   = int(plan.pan_x * W)
        cy   = int(plan.pan_y * H)
        x1   = int(np.clip(cx - cw // 2, 0, W - cw))
        y1   = int(np.clip(cy - ch // 2, 0, H - ch))
        crop = frame[y1:y1 + ch, x1:x1 + cw]
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
        cv2.circle(overlay, (cx, cy), radius,                bgr, 2)
        cv2.circle(overlay, (cx, cy), max(1, radius // 2),   bgr, 1)
        return cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)

    # ── Letterbox ───────────────────────────────────────────────────────
    def _apply_letterbox(self, frame: np.ndarray) -> np.ndarray:
        H   = frame.shape[0]
        bar = int(H * self.cfg.letterbox_ratio)
        if bar < 1:
            return frame
        out = frame.copy()
        out[:bar]     = 0
        out[H - bar:] = 0
        return out
