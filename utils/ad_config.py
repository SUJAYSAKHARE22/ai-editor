"""Ad pipeline configuration."""

from dataclasses import dataclass, field
from typing import Tuple, Optional


def _hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


@dataclass
class AdConfig:
    # Branding
    brand_name:      str   = "Your Brand"
    tagline:         str   = ""
    primary_color:   str   = "#00D4FF"
    secondary_color: str   = "#FF6B35"
    style:           str   = "modern"      # modern | minimal | bold | retro

    # Music
    music_style:     str   = "corporate"  # corporate | upbeat | dramatic | calm | none

    # Voiceover
    add_voiceover:   bool  = False
    voiceover_text:  str   = ""

    # Speed
    speed_boost:     float = 1.0           # applied to boring sections
    output_duration: str   = "auto"        # "auto" | "30s" | "60s" | "90s"

    # Branding overlays
    add_logo:        bool  = False
    color_grade:     str   = "cinematic"   # cinematic | vivid | cool | warm | none

    # Captions
    add_captions:    bool  = False

    # Zoom / cursor (inherited from original)
    max_zoom:                float = 2.2
    zoom_window:             int   = 25
    dwell_frames:            int   = 12
    cursor_color:            Tuple[int, int, int] = (255, 220, 0)
    cursor_highlight_radius: int   = 28
    cursor_highlight_alpha:  float = 0.45
    ripple_enabled:          bool  = True
    ripple_frames:           int   = 20
    ripple_max_radius:       int   = 55
    ripple_color:            Tuple[int, int, int] = (255, 220, 0)
    speed_ramp_enabled:      bool  = True
    idle_speed:              float = 3.5
    min_idle_frames:         int   = 25
    chapters_enabled:        bool  = True
    chapter_title_frames:    int   = 50
    chapter_idle_gap:        int   = 50
    chapter_font_scale:      float = 1.4
    letterbox_enabled:       bool  = True
    letterbox_ratio:         float = 0.075
    output_crf:              int   = 18
    output_fps:              Optional[int] = None
    workers:                 int   = 4
    verbose:                 bool  = False
    cursor_log:              Optional[str] = None

    @property
    def primary_bgr(self) -> Tuple[int, int, int]:
        return _hex_to_bgr(self.primary_color)

    @property
    def secondary_bgr(self) -> Tuple[int, int, int]:
        return _hex_to_bgr(self.secondary_color)
