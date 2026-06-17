"""
Ad Pipeline
===========
Full advertising video production pipeline:

  1. Open video
  2. Track cursor
  3. Analyze events
  4. Build render plan (with intro/outro/callouts)
  5. Read raw frames
  6. Parallel render each frame (zoom, grade, overlays)
  7. Generate background music
  8. Write final video with audio

Progress is reported to a JobStore for real-time UI feedback.
"""

import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

import cv2
import numpy as np

from core.cursor_tracker import CursorTracker
from core.event_analyzer import EventAnalyzer
from core.frame_renderer import FrameRenderer
from core.music_generator import generate_music
from core.video_io import VideoReader, VideoWriter
from utils.ad_config import AdConfig
from utils.logger import get_logger


class AdPipeline:
    def __init__(self, cfg: AdConfig, job_store=None, job_id: str = ""):
        self.cfg       = cfg
        self.job_store = job_store
        self.job_id    = job_id
        self.log       = get_logger("pipeline", cfg.verbose)

    def _progress(self, pct: int, msg: str):
        self.log.info(f"[{pct:3d}%] {msg}")
        if self.job_store and self.job_id:
            self.job_store.update(self.job_id, progress=pct, message=msg)

    # ───────────────────────────────────────────────────────────────────
    def run(self, input_path: Path, output_path: Path):
        tmpdir = Path(tempfile.mkdtemp(prefix="adedit_"))
        try:
            self._run(input_path, output_path, tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ───────────────────────────────────────────────────────────────────
    def _run(self, input_path: Path, output_path: Path, tmpdir: Path):
        cfg = self.cfg

        # ── 1. Open video ───────────────────────────────────────────────
        self._progress(2, "Opening video…")
        reader = VideoReader(input_path)
        fps    = reader.fps
        W, H   = reader.width, reader.height
        total  = reader.total_frames

        self.log.info(f"Video: {W}x{H} @ {fps:.2f}fps | {total} frames")

        # ── 2. Track cursor ─────────────────────────────────────────────
        self._progress(8, "Tracking cursor positions…")
        tracker   = CursorTracker(cfg)
        positions = tracker.track(reader, total)
        reader.reset()

        # ── 3. Analyse events ───────────────────────────────────────────
        self._progress(15, "Analyzing video events…")
        analyzer = EventAnalyzer(cfg, fps, W, H)
        events   = analyzer.analyze(positions)

        n_dwell  = sum(1 for e in events if e["type"] == "dwell")
        n_click  = sum(1 for e in events if e["type"] == "click")
        n_scene  = sum(1 for e in events if e["type"] == "scene_break")
        n_idle   = sum(1 for e in events if e["type"] == "idle")
        self.log.info(f"Events → dwells:{n_dwell} clicks:{n_click} "
                      f"scenes:{n_scene} idles:{n_idle}")

        # ── 4. Build render plan ────────────────────────────────────────
        self._progress(20, "Building frame-level render plan…")
        renderer = FrameRenderer(cfg, fps, W, H, events, total)
        plan     = renderer.build_plan(total)

        # ── 5. Read raw frames ──────────────────────────────────────────
        self._progress(25, "Reading raw frames…")
        raw: List[np.ndarray] = []
        for i, frame in enumerate(reader.iter_frames()):
            if i >= total:
                break
            raw.append(frame)

        self._progress(45, f"Read {len(raw)} frames. Rendering…")

        # ── 6. Parallel render ──────────────────────────────────────────
        processed = [None] * total

        def _render(i):
            return i, renderer.render(raw[i], i, plan[i])

        done = 0
        with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
            futs = {pool.submit(_render, i): i for i in range(total)}
            for fut in as_completed(futs):
                i, f = fut.result()
                processed[i] = f
                done += 1
                if done % 100 == 0 or done == total:
                    pct = 45 + int(done / total * 35)
                    self._progress(pct, f"Rendering frames… {done}/{total}")

        self._progress(80, "Render complete. Generating music…")

        # ── 7. Generate background music ────────────────────────────────
        music_path = None
        if cfg.music_style != "none":
            try:
                duration    = total / max(fps, 1)
                music_wav   = tmpdir / "bg_music.wav"
                music_path  = generate_music(cfg.music_style, duration, music_wav)
                self.log.info(f"Music generated: {music_path}")
            except Exception as e:
                self.log.warning(f"Music generation failed: {e}")
                music_path = None

        self._progress(88, "Encoding final video…")

        # ── 8. Write output ─────────────────────────────────────────────
        writer = VideoWriter(output_path, fps, W, H, cfg)
        writer.write_with_audio(processed, plan, music_path)

        self._progress(98, "Finalizing…")
        self.log.info(f"Output: {output_path}")
