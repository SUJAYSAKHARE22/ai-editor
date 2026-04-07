"""Configuration — loaded from CLI args + optional YAML override."""

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple, Optional


@dataclass
class Config:
    # Zoom settings
    max_zoom: float = 2.2
    zoom_easing: str = "ease_in_out"    # linear | ease_in | ease_out | ease_in_out
    zoom_window: int = 30               # frames to transition in/out of zoom
    dwell_frames: int = 12              # frames cursor must be still to trigger zoom

    # Cursor detection & highlight
    cursor_color: Tuple[int, int, int] = (255, 220, 0)
    cursor_highlight_radius: int = 28
    cursor_highlight_alpha: float = 0.45
    cursor_log: Optional[str] = None

    # Click ripple
    ripple_enabled: bool = True
    ripple_frames: int = 20
    ripple_max_radius: int = 55
    ripple_color: Tuple[int, int, int] = (255, 220, 0)

    # Speed ramping
    speed_ramp_enabled: bool = True
    idle_speed: float = 3.0             # fast-forward multiplier for idle sections
    action_speed: float = 1.0           # normal speed during action
    min_idle_frames: int = 30           # minimum frames of inactivity to speed up

    # Chapter title cards
    chapters_enabled: bool = True
    chapter_title_frames: int = 45      # duration of title card in frames
    chapter_idle_gap: int = 60          # idle frames that trigger a new chapter
    chapter_font_scale: float = 1.4

    # Letterbox
    letterbox_enabled: bool = True
    letterbox_ratio: float = 0.075      # fraction of height per bar

    # Keystroke bubbles
    keystroke_enabled: bool = True
    keystroke_display_frames: int = 35

    # Output
    workers: int = 4
    preview_mode: bool = False
    preview_duration: int = 10          # seconds
    output_crf: int = 18                # ffmpeg CRF (lower = better quality)
    output_fps: Optional[int] = None    # None = match input fps
    verbose: bool = False

    @classmethod
    def load(cls, args) -> "Config":
        cfg = cls()

        # Load YAML if provided
        if hasattr(args, "config") and args.config:
            p = Path(args.config)
            if p.exists():
                with open(p) as f:
                    data = yaml.safe_load(f) or {}
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)

        # Apply CLI overrides
        if hasattr(args, "zoom"):
            cfg.max_zoom = args.zoom
        if hasattr(args, "cursor_log") and args.cursor_log:
            cfg.cursor_log = args.cursor_log
        if hasattr(args, "no_letterbox") and args.no_letterbox:
            cfg.letterbox_enabled = False
        if hasattr(args, "no_chapters") and args.no_chapters:
            cfg.chapters_enabled = False
        if hasattr(args, "no_ripple") and args.no_ripple:
            cfg.ripple_enabled = False
        if hasattr(args, "no_speed") and args.no_speed:
            cfg.speed_ramp_enabled = False
        if hasattr(args, "workers"):
            cfg.workers = args.workers
        if hasattr(args, "preview"):
            cfg.preview_mode = args.preview
        if hasattr(args, "verbose"):
            cfg.verbose = args.verbose

        # Parse cursor color "R,G,B"
        if hasattr(args, "cursor_color"):
            try:
                r, g, b = [int(x) for x in args.cursor_color.split(",")]
                cfg.cursor_color = (r, g, b)
                cfg.ripple_color = (r, g, b)
            except Exception:
                pass

        return cfg
