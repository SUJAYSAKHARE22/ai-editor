"""
Pipeline
========
Orchestrates every stage:
  1. Open video (VideoReader)
  2. Track cursor positions (CursorTracker)
  3. Analyse events — dwell / click / idle / scene break (EventAnalyzer)
  4. Build per-frame render plan (FrameRenderer.build_plan)
  5. Read all raw frames, parallel-render each one
  6. Write output video (VideoWriter)
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
from core.video_io import VideoReader, VideoWriter
from utils.config import Config
from utils.logger import get_logger


class Pipeline:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.log = get_logger("pipeline", cfg.verbose)

    # -----------------------------------------------------------------------
    def run(self, input_path: Path, output_path: Path):
        tmpdir = Path(tempfile.mkdtemp(prefix="demoedit_"))
        try:
            self._run(input_path, output_path, tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # -----------------------------------------------------------------------
    def _run(self, input_path: Path, output_path: Path, tmpdir: Path):
        cfg = self.cfg
        log = self.log

        # ── 1. Open video ──────────────────────────────────────────────
        reader = VideoReader(input_path)
        fps    = reader.fps
        W, H   = reader.width, reader.height
        total  = reader.total_frames

        if cfg.preview_mode:
            total = min(total, int(fps * cfg.preview_duration))
            log.info(f"Preview mode → first {cfg.preview_duration}s ({total} frames)")

        log.info(f"Video  : {W}x{H}  @  {fps:.2f} fps  |  {total} frames")

        # ── 2. Track cursor ────────────────────────────────────────────
        log.info("Tracking cursor…")
        tracker  = CursorTracker(cfg)
        positions = tracker.track(reader, total)
        reader.reset()

        # ── 3. Analyse events ──────────────────────────────────────────
        log.info("Analysing events…")
        analyzer = EventAnalyzer(cfg, fps, W, H)
        events   = analyzer.analyze(positions)

        log.info(f"  Dwells       : {sum(1 for e in events if e['type']=='dwell')}")
        log.info(f"  Clicks       : {sum(1 for e in events if e['type']=='click')}")
        log.info(f"  Scene breaks : {sum(1 for e in events if e['type']=='scene_break')}")
        log.info(f"  Idle ranges  : {sum(1 for e in events if e['type']=='idle')}")

        # ── 4. Build render plan ───────────────────────────────────────
        log.info("Building render plan…")
        renderer = FrameRenderer(cfg, fps, W, H, events)
        plan     = renderer.build_plan(total)

        # ── 5. Read raw frames ─────────────────────────────────────────
        log.info("Reading frames…")
        raw: List[np.ndarray] = []
        for i, frame in enumerate(reader.iter_frames()):
            if i >= total:
                break
            raw.append(frame)
            if (i + 1) % 100 == 0 or (i + 1) == total:
                _bar(i + 1, total, "read")
        print()

        # ── 6. Parallel render ─────────────────────────────────────────
        log.info(f"Rendering with {cfg.workers} workers…")
        processed = [None] * total

        def _render(i):
            return i, renderer.render(raw[i], i, plan[i])

        done_count = 0
        with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
            futs = {pool.submit(_render, i): i for i in range(total)}
            for fut in as_completed(futs):
                i, frame = fut.result()
                processed[i] = frame
                done_count += 1
                if done_count % 50 == 0 or done_count == total:
                    _bar(done_count, total, "render")
        print()

        # ── 7. Assemble output ─────────────────────────────────────────
        log.info("Assembling output video…")
        writer = VideoWriter(output_path, fps, W, H, cfg)
        writer.write(processed, plan)


# ---------------------------------------------------------------------------
def _bar(done: int, total: int, stage: str):
    filled = int(done / max(total, 1) * 40)
    bar    = "█" * filled + "░" * (40 - filled)
    print(f"\r  [{bar}] {done}/{total} {stage}", end="", flush=True)
