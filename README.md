# AdEdit ⚡ — AI Advertising Video Editor

**Upload a raw demo video → Get a polished, cinematic advertising video automatically.**

AdEdit upgrades the original DemoEdit with a full advertising production pipeline: brand overlays, color grading, synthetic background music, animated callouts, intro/outro cards, and a modern web UI.

---

## What's new vs the original

| Feature | Original (DemoEdit) | AdEdit |
|---|---|---|
| Interface | CLI only | **Web UI + CLI** |
| Color grading | None | **Cinematic / Vivid / Cool / Warm / Moody LUTs** |
| Background music | None | **AI-synthesized (Corporate / Upbeat / Dramatic / Calm)** |
| Brand overlays | Chapter cards only | **Animated intro + outro + chapter cards + callouts** |
| Feature callouts | None | **Pill bubbles at every dwell point** |
| Gradient accent bar | None | **Brand-colored gradient bar** |
| Logo watermark | None | **Text-based logo watermark** |
| Real-time progress | Terminal bar | **Web SSE stream + progress bar** |
| Color cursor/ripple | Yellow only | **Any hex color, fully customizable** |
| Audio mux | None | **ffmpeg audio mux built-in** |

---

## Installation

```bash
git clone <repo>
cd ad-editor
pip install -r requirements.txt
# System: ffmpeg in PATH
# brew install ffmpeg  /  apt install ffmpeg
```

---

## Web UI (recommended)

```bash
python app.py
# Open http://localhost:5000
```

Upload your video, set your brand name, colors, and style — hit **Generate Ad Video**. Watch real-time progress. Download the result.

---

## CLI

```bash
# Basic
python cli.py demo.mp4 output.mp4 --brand "MyApp" --tagline "Ship faster"

# Full options
python cli.py demo.mp4 output.mp4 \
  --brand "Acme" \
  --tagline "Built for speed" \
  --primary "#00D4FF" \
  --secondary "#FF6B35" \
  --grade cinematic \
  --music upbeat \
  --zoom 2.5 \
  --logo \
  --workers 6

# No music, vivid grade
python cli.py demo.mp4 output.mp4 --no-music --grade vivid

# Minimal (just zoom + cursor)
python cli.py demo.mp4 output.mp4 --no-music --no-chapters --no-letterbox --grade none
```

---

## Effects pipeline (per frame)

```
Raw frame
  │
  ▼ 1. Smart Zoom + Pan (cursor tracking, eased transitions)
  │
  ▼ 2. Color Grade (LUT — cinematic/vivid/cool/warm/moody)
  │
  ▼ 3. Cursor Highlight (glow ring)
  │
  ▼ 4. Click Ripple (expanding rings)
  │
  ▼ 5. Feature Callout Pills (branded label at dwell zones)
  │
  ▼ 6. Chapter Title Card (branded, numbered, with accent bar)
  │
  ▼ 7. Gradient Accent Bar (brand colors, bottom)
  │
  ▼ 8. Logo Watermark (top-right, optional)
  │
  ▼ 9. Cinematic Letterbox (top/bottom bars)
  │
  ▼ 10. Brand Intro Card (animated, first 2.5s)
  │
  ▼ 11. Brand Outro Card (animated CTA, last 3s)
  │
  ▼ + Background Music (WAV synthesized, muxed via ffmpeg)
  │
  ▼ Final MP4 (H.264, yuv420p, fast-start)
```

---

## Project structure

```
ad-editor/
├── app.py                    # Flask web server
├── cli.py                    # CLI entry point
├── requirements.txt
├── core/
│   ├── ad_pipeline.py        # Main orchestrator
│   ├── cursor_tracker.py     # Frame-diff cursor detection
│   ├── event_analyzer.py     # Dwell/click/idle/scene detection
│   ├── frame_renderer.py     # Per-frame effect engine
│   ├── color_grader.py       # LUT-based color grading
│   ├── music_generator.py    # Synthetic background music
│   ├── overlay_renderer.py   # Brand overlays (intro/outro/chapters/callouts)
│   └── video_io.py           # VideoReader + VideoWriter (OpenCV + ffmpeg)
├── utils/
│   ├── ad_config.py          # Config dataclass
│   ├── job_store.py          # Thread-safe job state for web UI
│   └── logger.py             # Coloured console logger
└── templates/
    └── index.html            # Web UI
```

---

## Config reference (CLI flags / web form)

| Setting | Values | Description |
|---|---|---|
| `--brand` | text | Brand name on overlays |
| `--tagline` | text | Subtitle on intro/outro |
| `--primary` | hex | Primary brand color |
| `--secondary` | hex | Secondary brand color |
| `--grade` | cinematic / vivid / cool / warm / moody / none | Color look |
| `--music` | corporate / upbeat / dramatic / calm / none | BG music style |
| `--zoom` | float | Max zoom multiplier (default 2.2) |
| `--logo` | flag | Add logo watermark |
| `--no-music` | flag | Disable background music |
| `--no-chapters` | flag | Disable chapter cards |
| `--no-letterbox` | flag | Disable cinematic bars |
| `--no-ripple` | flag | Disable click ripples |
| `--no-speed` | flag | Disable idle speed ramp |
| `--workers` | int | Parallel render workers |

---

## Tips

1. **Record at 1080p+** — zoom crops frames, higher resolution = sharper output.
2. **Pause 0.5s on key features** — dwell detector triggers zoom + callout.
3. **Brand name matters** — it appears on animated intro + outro cards.
4. **Corporate music** pairs best with product demos; **upbeat** for launch trailers.
5. **Cinematic grade** desaturates slightly — use **vivid** to keep punchy colors.
