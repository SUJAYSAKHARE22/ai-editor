"""
Video I/O
=========
VideoReader  — wraps OpenCV VideoCapture, yields BGR frames.
VideoWriter  — writes processed frames (honouring skip mask),
               then re-encodes with ffmpeg for a proper MP4 container.
               Falls back gracefully if ffmpeg is not installed.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator, List

import cv2
import numpy as np

from core.frame_renderer import FramePlan
from utils.config import Config
from utils.logger import get_logger


# ---------------------------------------------------------------------------
class VideoReader:
    def __init__(self, path: Path):
        self.path = path
        self._cap = cv2.VideoCapture(str(path))
        if not self._cap.isOpened():
            raise IOError(f"Cannot open video: {path}")

        self.fps          = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.width        = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height       = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def iter_frames(self) -> Iterator[np.ndarray]:
        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            yield frame

    def reset(self):
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def __del__(self):
        try:
            if self._cap.isOpened():
                self._cap.release()
        except Exception:
            pass


# ---------------------------------------------------------------------------
class VideoWriter:
    def __init__(self, out_path: Path, fps: float, W: int, H: int, cfg: Config):
        self.out_path = out_path
        self.fps      = fps
        self.W        = W
        self.H        = H
        self.cfg      = cfg
        self.log      = get_logger("writer", cfg.verbose)

    # -----------------------------------------------------------------------
    def write(self, frames: List[np.ndarray], plans: List[FramePlan]):
        cfg = self.cfg

        # Write to a temporary .mp4 first (OpenCV mp4v codec)
        tmp_fd, tmp_path_str = tempfile.mkstemp(suffix="_raw.mp4")
        import os; os.close(tmp_fd)
        tmp_path = Path(tmp_path_str)

        out_fps = float(cfg.output_fps) if cfg.output_fps else self.fps
        fourcc  = cv2.VideoWriter_fourcc(*"mp4v")
        vw      = cv2.VideoWriter(str(tmp_path), fourcc, out_fps, (self.W, self.H))

        if not vw.isOpened():
            # Try XVID as fallback
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            tmp_path = tmp_path.with_suffix(".avi")
            vw = cv2.VideoWriter(str(tmp_path), fourcc, out_fps, (self.W, self.H))

        written = 0
        for frame, plan in zip(frames, plans):
            if plan.skip:
                continue
            vw.write(frame)
            written += 1

        vw.release()
        self.log.info(f"  Written {written} / {len(frames)} frames to temp file")

        # Re-encode with ffmpeg (better compression + proper container)
        self._ffmpeg_encode(tmp_path, self.out_path)
        tmp_path.unlink(missing_ok=True)

    # -----------------------------------------------------------------------
    def _ffmpeg_encode(self, src: Path, dst: Path):
        """Encode src → dst with H.264. Falls back to file copy if ffmpeg absent."""
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            self.log.warning(
                "  ffmpeg not found — copying raw video without re-encode.\n"
                "  Install ffmpeg for better quality: https://ffmpeg.org/download.html"
            )
            shutil.copy(src, dst)
            return

        cmd = [
            ffmpeg, "-y",
            "-i",        str(src),
            "-c:v",      "libx264",
            "-crf",      str(self.cfg.output_crf),
            "-preset",   "fast",
            "-pix_fmt",  "yuv420p",
            "-movflags", "+faststart",
            str(dst),
        ]
        self.log.debug(f"  ffmpeg cmd: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.warning(f"  ffmpeg error:\n{result.stderr[-500:]}")
            self.log.warning("  Falling back to raw copy.")
            shutil.copy(src, dst)
        else:
            self.log.info("  ffmpeg encode complete ✓")
