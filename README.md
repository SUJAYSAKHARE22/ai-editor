# DemoEdit 🎬

**Transform a raw screen recording into a polished, cinematic demo video — automatically.**

DemoEdit analyzes your screen recording, tracks the cursor, detects what's happening (dwells, clicks, idle sections, scene transitions), and applies professional effects just like you'd see in a product advertisement.

---

## Effects applied

| Effect | What it does |
|--------|-------------|
| **Smart zoom** | Detects when the cursor dwells on something important and zooms in smoothly with easing |
| **Pan tracking** | The viewport follows the cursor so the subject always stays centered |
| **Click ripple** | Expanding ring highlight around every mouse click |
| **Cursor highlight** | Soft glowing ring keeps the cursor always visible |
| **Speed ramp** | Idle/boring sections are automatically sped up; action plays at normal speed |
| **Chapter title cards** | Scene breaks (long pauses or large cursor jumps) trigger animated chapter headings |
| **Cinematic letterbox** | Top & bottom bars for that polished ad look |

---

## Installation

```bash
git clone <repo>
cd demo_editor
pip install -r requirements.txt
```

**System requirements:**
- Python 3.9+
- `ffmpeg` in PATH (for final encode): `brew install ffmpeg` / `apt install ffmpeg`
- OpenCV, NumPy, PyYAML (installed via pip)

---

## Quick start

```bash
# Basic usage
python main.py my_demo.mp4 output.mp4

# Preview first 10 seconds quickly
python main.py my_demo.mp4 preview.mp4 --preview

# More aggressive zoom
python main.py my_demo.mp4 output.mp4 --zoom 3.0

# Supply an accurate cursor log (much better tracking)
python main.py my_demo.mp4 output.mp4 --cursor-log cursors.csv

# Minimal — just zoom, no chapters or letterbox
python main.py my_demo.mp4 output.mp4 --no-chapters --no-letterbox

# Custom cursor highlight color (e.g. orange)
python main.py my_demo.mp4 output.mp4 --cursor-color 255,120,0
```

---

## Cursor log format (optional but recommended)

If you record your cursor while screen-recording, supply a CSV for perfect tracking:

```
frame,x,y
0,512,300
1,513,301
...
```

Or with click events:
```
frame,x,y,event
0,512,300,move
45,640,360,click
```

**How to capture cursor positions** (Python snippet for recording alongside your app):

```python
import csv, time
import pynput.mouse as mouse

rows = []
start = time.time()
FPS  = 30

def on_move(x, y):
    frame = int((time.time() - start) * FPS)
    rows.append((frame, x, y, "move"))

def on_click(x, y, button, pressed):
    if pressed:
        frame = int((time.time() - start) * FPS)
        rows.append((frame, x, y, "click"))

with mouse.Listener(on_move=on_move, on_click=on_click) as listener:
    input("Press Enter to stop recording...")

with open("cursors.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["frame", "x", "y", "event"])
    w.writerows(rows)
```

---

## Config file (YAML)

For repeatable settings, create a `config.yaml`:

```yaml
max_zoom: 2.5
zoom_window: 25          # transition frames in/out of zoom
dwell_frames: 15         # frames cursor must be still to zoom
cursor_highlight_radius: 30
ripple_enabled: true
ripple_max_radius: 60
idle_speed: 4.0          # how fast to play idle sections
chapter_idle_gap: 45     # idle frames before showing chapter card
letterbox_ratio: 0.08
output_crf: 18           # ffmpeg quality: 0=lossless, 23=default, 28=small
workers: 6
```

Then:
```bash
python main.py demo.mp4 output.mp4 --config config.yaml
```

---

## CLI options

```
positional arguments:
  input               Input screen recording (.mp4, .mov, .avi)
  output              Output video path (.mp4)

options:
  --config            YAML config file
  --zoom ZOOM         Max zoom level (default 2.2)
  --cursor-log FILE   CSV cursor log (frame,x,y)
  --no-letterbox      Disable cinematic letterbox bars
  --no-chapters       Disable auto chapter title cards
  --no-ripple         Disable click ripple effect
  --no-speed          Disable speed ramping
  --cursor-color R,G,B  Cursor highlight color (default 255,220,0)
  --workers N         Parallel render workers (default 4)
  --preview           Render only first 10s for quick preview
  --verbose           Verbose logging
```

---

## Project structure

```
demo_editor/
├── main.py                  # CLI entry point
├── requirements.txt
├── test_pipeline.py         # End-to-end test with synthetic video
├── core/
│   ├── pipeline.py          # Orchestrates all stages
│   ├── cursor_tracker.py    # Frame-diff cursor detection + CSV import
│   ├── event_analyzer.py    # Dwell / click / idle / scene detection
│   ├── frame_renderer.py    # Per-frame effect engine (zoom, ripple, etc.)
│   └── video_io.py          # VideoReader + VideoWriter (OpenCV + ffmpeg)
└── utils/
    ├── config.py            # Config dataclass (CLI + YAML)
    └── logger.py            # Coloured console logger
```

---

## How the zoom works

```
Cursor stationary for dwell_frames?
        │
        ▼
  Zoom ramp IN  (zoom_window frames, ease-in-out)
        │
        ▼
  Hold at max_zoom  (while cursor stays in dwell zone)
        │
        ▼
  Zoom ramp OUT  (zoom_window frames, ease-in-out)
```

The viewport is cropped to `(W/zoom, H/zoom)` centered on the cursor, then
upscaled back to full resolution. Smooth easing prevents jarring transitions.

---

## Tips for best results

1. **Record at 1080p or higher** — the zoom crops the frame, so more resolution = sharper result.
2. **Use a cursor log** — optical detection works but a log file gives perfect accuracy.
3. **Pause briefly** on features you want to highlight — the dwell detector needs ~0.4s.
4. **Keep raw recordings** — you can re-run with different settings without re-recording.
5. **Use `--preview`** to check settings before rendering the full video.

---

## Running the test

```bash
python test_pipeline.py
```

This generates a synthetic 8-second screen recording, runs the full pipeline,
and validates the output — no real video needed.
