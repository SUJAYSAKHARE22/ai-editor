"""
Overlay Renderer
================
Draws advertising overlays:
  - Animated brand intro card (fade-in on first frames)
  - Feature callout bubbles at dwell points
  - Chapter title cards (upgraded with brand colors)
  - Brand outro card with tagline
  - Animated gradient bar (bottom)
  - Pill-style caption / subtitle boxes
  - Logo watermark
  - CTA (call-to-action) end card
"""

from typing import Optional, Tuple, List
import cv2
import numpy as np


def _ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 2


class OverlayRenderer:
    def __init__(self, cfg, W: int, H: int, total_frames: int, fps: float):
        self.cfg    = cfg
        self.W      = W
        self.H      = H
        self.total  = total_frames
        self.fps    = fps
        self.font   = cv2.FONT_HERSHEY_SIMPLEX
        self.font_b = cv2.FONT_HERSHEY_DUPLEX

    # ── Public draw methods ──────────────────────────────────────────────

    def draw_intro(self, frame: np.ndarray, frame_i: int,
                   total_intro_frames: int) -> np.ndarray:
        """Full-frame brand intro overlay (first N frames)."""
        if frame_i >= total_intro_frames:
            return frame

        t     = frame_i / max(total_intro_frames, 1)
        alpha = _ease_in_out(min(t * 3, 1.0)) * (1.0 - _ease_out(max((t - 0.7) / 0.3, 0.0)))

        overlay = frame.copy()
        H, W    = frame.shape[:2]

        # Dark gradient overlay
        grad = np.zeros((H, W, 3), dtype=np.uint8)
        for row in range(H):
            g = int(30 + 60 * (1.0 - row / H))
            grad[row] = (g, g, g)
        overlay = cv2.addWeighted(overlay, 0.3, grad, 0.7, 0)

        # Animated accent line
        line_y  = H // 2 - int(60 * H / 1080)
        line_w  = int(W * min(t * 4, 1.0))
        px_col  = self.cfg.primary_bgr
        sx_col  = self.cfg.secondary_bgr
        cv2.line(overlay, (W // 2 - line_w // 2, line_y),
                 (W // 2 + line_w // 2, line_y), px_col, max(2, H // 200))

        # Brand name
        brand   = self.cfg.brand_name
        scale   = max(0.8, 2.2 * W / 1920)
        thick   = max(2, int(3 * W / 1920))
        (tw, th), _ = cv2.getTextSize(brand, self.font_b, scale, thick)
        tx      = (W - tw) // 2
        ty      = H // 2

        slide   = int((1.0 - _ease_out(min(t * 2, 1.0))) * 40)
        cv2.putText(overlay, brand, (tx + 3, ty + slide + 3),
                    self.font_b, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
        cv2.putText(overlay, brand, (tx, ty + slide),
                    self.font_b, scale, (255, 255, 255), thick, cv2.LINE_AA)

        # Tagline
        if self.cfg.tagline and t > 0.25:
            tag_alpha = _ease_out(min((t - 0.25) / 0.3, 1.0))
            tag_scale = max(0.4, 0.85 * W / 1920)
            tag_thick = max(1, int(2 * W / 1920))
            (tlw, tlh), _ = cv2.getTextSize(self.cfg.tagline, self.font, tag_scale, tag_thick)
            tx2 = (W - tlw) // 2
            ty2 = ty + th + max(20, int(30 * H / 1080))
            self._draw_pill(overlay, tx2 - 12, ty2 - tlh - 8, tlw + 24, tlh + 16,
                            color=px_col, alpha=0.6)
            cv2.putText(overlay, self.cfg.tagline, (tx2, ty2),
                        self.font, tag_scale, (255, 255, 255), tag_thick, cv2.LINE_AA)

        return cv2.addWeighted(frame, 1.0 - alpha, overlay, alpha, 0)

    def draw_outro(self, frame: np.ndarray, frame_i: int,
                   outro_start: int) -> np.ndarray:
        """Full-frame CTA outro card."""
        age   = frame_i - outro_start
        dur   = int(self.fps * 3)
        if age < 0 or age >= dur:
            return frame

        t     = age / max(dur, 1)
        alpha = _ease_in_out(min(t * 2, 1.0))

        overlay = np.zeros_like(frame)
        H, W    = frame.shape[:2]

        # Background gradient
        for row in range(H):
            r_val = int(15 + 20 * row / H)
            overlay[row] = (r_val, r_val, r_val)

        px = self.cfg.primary_bgr
        sx = self.cfg.secondary_bgr

        # Horizontal accent lines
        cv2.line(overlay, (0, H // 3),     (W, H // 3),     px, max(2, H // 300))
        cv2.line(overlay, (0, 2 * H // 3), (W, 2 * H // 3), sx, max(2, H // 300))

        # Brand name
        scale = max(1.0, 2.8 * W / 1920)
        thick = max(2, int(4 * W / 1920))
        (tw, th), _ = cv2.getTextSize(self.cfg.brand_name, self.font_b, scale, thick)
        tx = (W - tw) // 2
        ty = H // 2 - th // 2
        cv2.putText(overlay, self.cfg.brand_name, (tx + 3, ty + 3),
                    self.font_b, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
        cv2.putText(overlay, self.cfg.brand_name, (tx, ty),
                    self.font_b, scale, (255, 255, 255), thick, cv2.LINE_AA)

        # Tagline
        if self.cfg.tagline:
            tg_scale = max(0.5, 1.0 * W / 1920)
            tg_thick = max(1, int(2 * W / 1920))
            (tlw, _), _ = cv2.getTextSize(self.cfg.tagline, self.font, tg_scale, tg_thick)
            cv2.putText(overlay, self.cfg.tagline,
                        ((W - tlw) // 2, ty + th + max(30, int(40 * H / 1080))),
                        self.font, tg_scale, px, tg_thick, cv2.LINE_AA)

        return cv2.addWeighted(frame, 1.0 - alpha, overlay, alpha, 0)

    def draw_chapter_card(self, frame: np.ndarray, text: str, alpha: float,
                          chapter_num: int = 1) -> np.ndarray:
        """Branded chapter title card with animated accent."""
        H, W    = frame.shape[:2]
        overlay = frame.copy()
        px      = self.cfg.primary_bgr
        sx      = self.cfg.secondary_bgr

        band_h  = max(50, int(H * 0.14))
        band_y  = H // 2 - band_h // 2

        # Dark semi-transparent band
        band = overlay[band_y:band_y + band_h].copy()
        band = (band * 0.2).astype(np.uint8)
        overlay[band_y:band_y + band_h] = band

        # Accent bar (left side, primary color)
        bar_w = max(4, int(W * 0.004))
        cv2.rectangle(overlay, (0, band_y), (bar_w, band_y + band_h), px, -1)

        # Number badge
        num_str = f"{chapter_num:02d}"
        ns = max(0.5, 0.9 * W / 1920)
        nt = max(1, int(2 * W / 1920))
        (nw, nh), _ = cv2.getTextSize(num_str, self.font_b, ns, nt)
        badge_x = bar_w + max(10, int(16 * W / 1920))
        badge_y = band_y + (band_h + nh) // 2
        cv2.putText(overlay, num_str, (badge_x + 1, badge_y + 1),
                    self.font_b, ns, (0, 0, 0), nt + 1, cv2.LINE_AA)
        cv2.putText(overlay, num_str, (badge_x, badge_y),
                    self.font_b, ns, px, nt, cv2.LINE_AA)

        # Title text
        scale = max(0.5, self.cfg.chapter_font_scale * W / 1920)
        thick = max(1, int(2 * scale))
        (tw, th), _ = cv2.getTextSize(text, self.font_b, scale, thick)
        tx = badge_x + nw + max(20, int(30 * W / 1920))
        ty = band_y + (band_h + th) // 2
        cv2.putText(overlay, text, (tx + 2, ty + 2),
                    self.font_b, scale, (0, 0, 0), thick + 1, cv2.LINE_AA)
        cv2.putText(overlay, text, (tx, ty),
                    self.font_b, scale, (255, 255, 255), thick, cv2.LINE_AA)

        # Thin accent line along bottom of band
        cv2.line(overlay, (0, band_y + band_h - 1),
                 (W, band_y + band_h - 1), sx, max(1, H // 400))

        return cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)

    def draw_feature_callout(self, frame: np.ndarray, cx: int, cy: int,
                              label: str, alpha: float) -> np.ndarray:
        """Animated pill callout near cursor dwell."""
        H, W    = frame.shape[:2]
        overlay = frame.copy()
        px      = self.cfg.primary_bgr

        scale = max(0.35, 0.55 * W / 1920)
        thick = max(1, int(1.5 * W / 1920))
        (tw, th), _ = cv2.getTextSize(label, self.font, scale, thick)

        pad_x, pad_y = max(8, int(12 * W / 1920)), max(5, int(8 * H / 1080))
        bx = cx + max(20, int(30 * W / 1920))
        by = cy - th - pad_y * 2

        # Clamp to frame
        if bx + tw + pad_x * 2 > W:
            bx = cx - tw - pad_x * 2 - max(20, int(30 * W / 1920))
        by = max(0, min(by, H - th - pad_y * 2))

        self._draw_pill(overlay, bx, by, tw + pad_x * 2, th + pad_y * 2,
                        color=px, alpha=0.85)
        cv2.putText(overlay, label, (bx + pad_x, by + th + pad_y),
                    self.font, scale, (255, 255, 255), thick, cv2.LINE_AA)

        # Connector dot
        dot_x = cx + max(10, int(15 * W / 1920))
        cv2.circle(overlay, (dot_x, cy), max(4, int(6 * W / 1920)), px, -1)

        return cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)

    def draw_gradient_bar(self, frame: np.ndarray) -> np.ndarray:
        """Thin animated gradient accent bar at bottom."""
        H, W  = frame.shape[:2]
        bar_h = max(3, int(H * 0.004))
        y     = H - bar_h

        overlay = frame.copy()
        px      = np.array(self.cfg.primary_bgr, dtype=np.float32)
        sx      = np.array(self.cfg.secondary_bgr, dtype=np.float32)

        for x in range(W):
            t   = x / max(W - 1, 1)
            col = (px * (1 - t) + sx * t).astype(np.uint8)
            overlay[y:y + bar_h, x] = col

        return overlay

    def draw_logo_watermark(self, frame: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        """Simple text-based logo watermark (top-right)."""
        H, W    = frame.shape[:2]
        overlay = frame.copy()
        text    = self.cfg.brand_name
        scale   = max(0.3, 0.45 * W / 1920)
        thick   = max(1, int(W / 1920))
        px      = self.cfg.primary_bgr

        (tw, th), _ = cv2.getTextSize(text, self.font, scale, thick)
        margin  = max(10, int(16 * W / 1920))
        tx      = W - tw - margin
        ty      = th + margin

        cv2.putText(overlay, text, (tx + 1, ty + 1),
                    self.font, scale, (0, 0, 0), thick + 1, cv2.LINE_AA)
        cv2.putText(overlay, text, (tx, ty),
                    self.font, scale, px, thick, cv2.LINE_AA)

        return cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)

    def draw_caption(self, frame: np.ndarray, text: str, alpha: float) -> np.ndarray:
        """Subtitle-style caption bar at bottom."""
        H, W    = frame.shape[:2]
        overlay = frame.copy()

        scale = max(0.4, 0.7 * W / 1920)
        thick = max(1, int(2 * W / 1920))
        (tw, th), _ = cv2.getTextSize(text, self.font, scale, thick)

        pad_x, pad_y = max(12, int(18 * W / 1920)), max(6, int(10 * H / 1080))
        bx = (W - tw) // 2 - pad_x
        by = H - th - pad_y * 2 - max(20, int(30 * H / 1080))

        self._draw_pill(overlay, bx, by, tw + pad_x * 2, th + pad_y * 2,
                        color=(0, 0, 0), alpha=0.75)
        cv2.putText(overlay, text, (bx + pad_x, by + th + pad_y),
                    self.font, scale, (255, 255, 255), thick, cv2.LINE_AA)

        return cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _draw_pill(self, img: np.ndarray, x: int, y: int, w: int, h: int,
                   color: Tuple[int, int, int] = (0, 0, 0),
                   alpha: float = 0.75) -> None:
        """Draw a rounded-rect pill with alpha on img (in-place)."""
        H, W = img.shape[:2]
        x  = int(np.clip(x, 0, W - 1))
        y  = int(np.clip(y, 0, H - 1))
        x2 = int(np.clip(x + w, 0, W))
        y2 = int(np.clip(y + h, 0, H))
        if x2 <= x or y2 <= y:
            return
        r  = min(h // 2, max(4, int(8 * W / 1920)))
        cv2.rectangle(img, (x + r, y), (x2 - r, y2), color, -1)
        cv2.rectangle(img, (x, y + r), (x2, y2 - r), color, -1)
        for cx, cy in [(x + r, y + r), (x2 - r, y + r),
                       (x + r, y2 - r), (x2 - r, y2 - r)]:
            cv2.circle(img, (cx, cy), r, color, -1)
