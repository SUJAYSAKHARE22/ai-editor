"""
test_pipeline.py
================
Generates a synthetic 8-second screen recording and runs the full
DemoEdit pipeline on it — no real video required.

Run:
    python test_pipeline.py
"""

import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

# Make sure imports resolve whether run from project root or a sub-dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
def make_synthetic_video(
    path: Path,
    fps: int = 30,
    duration: int = 8,
    W: int = 1280,
    H: int = 720,
):
    """Create a fake screen recording with an animated cursor."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw     = cv2.VideoWriter(str(path), fourcc, fps, (W, H))
    total  = fps * duration
    print(f"  Generating {total} frames ({duration}s @ {fps} fps)…")

    for i in range(total):
        t = i / fps

        # ── Background ──────────────────────────────────────────────
        frame = np.full((H, W, 3), 28, dtype=np.uint8)

        # Sidebar
        cv2.rectangle(frame, (0, 0), (240, H), (42, 42, 48), -1)

        # Title bar
        cv2.rectangle(frame, (0, 0), (W, 36), (58, 58, 68), -1)
        cv2.putText(frame, "My Awesome App  —  Demo",
                    (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 210), 1,
                    cv2.LINE_AA)

        # Content panel
        cv2.rectangle(frame, (256, 48), (W - 16, H - 16), (46, 46, 56), -1)
        cv2.rectangle(frame, (256, 48), (W - 16, H - 16), (72, 72, 82), 1)

        # Fake list rows
        for row in range(6):
            y = 100 + row * 70
            label = f"Module Feature #{row + 1}"
            cv2.putText(frame, label, (280, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (155, 155, 165), 1,
                        cv2.LINE_AA)
            cv2.rectangle(frame, (272, y - 22), (272 + 340, y + 10),
                          (65, 65, 75), 1)

        # ── Cursor path ──────────────────────────────────────────────
        # 0–2 s  : dwell top-left  (zoom trigger)
        # 2–3 s  : move to centre
        # 3–5 s  : dwell centre    (zoom trigger)
        # 5–5.1s : simulated click (ripple trigger)
        # 5.1–6s : fast move to bottom-right
        # 6–8 s  : dwell bottom-right (zoom trigger)
        if t < 2.0:
            cx, cy = 310, 130
        elif t < 3.0:
            frac   = (t - 2.0)
            cx     = int(310 + frac * (640 - 310))
            cy     = int(130 + frac * (360 - 130))
        elif t < 5.0:
            cx, cy = 640, 360
        elif t < 5.1:
            cx = 640 + np.random.randint(-4, 4)
            cy = 360 + np.random.randint(-4, 4)
        elif t < 6.0:
            frac   = (t - 5.1) / 0.9
            cx     = int(640 + frac * (1040 - 640))
            cy     = int(360 + frac * (560 - 360))
        else:
            cx, cy = 1040, 560

        cx, cy = int(cx), int(cy)

        # Draw a simple arrow cursor
        pts = np.array([
            [cx,      cy     ],
            [cx + 13, cy + 19],
            [cx + 5,  cy + 15],
            [cx + 5,  cy + 30],
            [cx + 2,  cy + 30],
            [cx + 2,  cy + 15],
            [cx - 5,  cy + 19],
        ], dtype=np.int32)
        cv2.fillPoly(frame, [pts], (255, 255, 255))
        cv2.polylines(frame, [pts], True, (20, 20, 20), 1)

        vw.write(frame)

    vw.release()
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
def run_test():
    print("\n" + "=" * 52)
    print("  DemoEdit — End-to-end Test")
    print("=" * 52)

    tmpdir      = Path(tempfile.mkdtemp(prefix="demoedit_test_"))
    input_path  = tmpdir / "synthetic_demo.mp4"
    output_path = tmpdir / "cinematic_output.mp4"

    # ── Step 1: synthetic video ──────────────────────────────────────
    print("\n[1/3] Generating synthetic screen recording…")
    make_synthetic_video(input_path, fps=30, duration=8, W=1280, H=720)

    # ── Step 2: run pipeline ─────────────────────────────────────────
    print("\n[2/3] Running DemoEdit pipeline…")
    from utils.config import Config
    from core.pipeline import Pipeline

    class FakeArgs:
        zoom          = 2.2
        cursor_log    = None
        no_letterbox  = False
        no_chapters   = False
        no_ripple     = False
        no_speed      = False
        cursor_color  = "255,220,0"
        workers       = 2
        preview       = True        # render first 10 s only → fast test
        verbose       = True
        config        = None

    cfg      = Config.load(FakeArgs())
    pipeline = Pipeline(cfg)
    pipeline.run(input_path, output_path)

    # ── Step 3: validate ─────────────────────────────────────────────
    print("\n[3/3] Validating output…")
    assert output_path.exists(),                "Output file was not created!"
    size = output_path.stat().st_size
    assert size > 1_000,                        f"Output too small: {size} bytes"

    cap = cv2.VideoCapture(str(output_path))
    assert cap.isOpened(),                      "Output not readable by OpenCV!"
    ok, frame = cap.read()
    assert ok and frame is not None,            "Cannot read first frame!"
    cap.release()

    print(f"\n  ✓  Output : {output_path}")
    print(f"  ✓  Size   : {size / 1024:.1f} KB")
    print(f"  ✓  Shape  : {frame.shape}")
    print("\n  ALL TESTS PASSED ✓\n")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_test()
