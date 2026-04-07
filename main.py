#!/usr/bin/env python3
"""
DemoEdit — Cinematic Demo Video Editor
=======================================
Usage:
    python main.py input.mp4 output.mp4
    python main.py input.mp4 output.mp4 --zoom 2.5 --preview
    python main.py input.mp4 output.mp4 --cursor-log cursors.csv
"""

import argparse
import sys
import time
from pathlib import Path

from core.pipeline import Pipeline
from utils.config import Config
from utils.logger import get_logger


def parse_args():
    p = argparse.ArgumentParser(
        description="Transform a raw screen recording into a cinematic demo video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py demo.mp4 output.mp4
  python main.py demo.mp4 output.mp4 --preview
  python main.py demo.mp4 output.mp4 --zoom 3.0 --cursor-color 255,100,0
  python main.py demo.mp4 output.mp4 --no-chapters --no-letterbox
  python main.py demo.mp4 output.mp4 --cursor-log cursors.csv
        """
    )

    # Positional
    p.add_argument("input",  help="Input screen recording (.mp4 / .mov / .avi)")
    p.add_argument("output", help="Output file path (.mp4)")

    # Optional
    p.add_argument("--config",        default=None,      help="YAML config file path")
    p.add_argument("--zoom",          type=float, default=2.2,
                   help="Maximum zoom level (default: 2.2)")
    p.add_argument("--cursor-log",    default=None,
                   help="CSV cursor log: columns  frame,x,y  (optional but recommended)")
    p.add_argument("--cursor-color",  default="255,220,0",
                   help="Cursor highlight colour as R,G,B  (default: 255,220,0)")
    p.add_argument("--no-letterbox",  action="store_true",
                   help="Disable cinematic letterbox bars")
    p.add_argument("--no-chapters",   action="store_true",
                   help="Disable automatic chapter title cards")
    p.add_argument("--no-ripple",     action="store_true",
                   help="Disable click ripple effect")
    p.add_argument("--no-speed",      action="store_true",
                   help="Disable speed ramping of idle sections")
    p.add_argument("--workers",       type=int, default=4,
                   help="Number of parallel render workers (default: 4)")
    p.add_argument("--preview",       action="store_true",
                   help="Render only the first 10 seconds (quick test)")
    p.add_argument("--verbose",       action="store_true",
                   help="Enable verbose / debug logging")

    return p.parse_args()


def main():
    args = parse_args()
    cfg  = Config.load(args)

    log = get_logger("main", cfg.verbose)

    input_path  = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        log.error(f"Input file not found: {input_path}")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("=" * 55)
    log.info("  DemoEdit — Cinematic Demo Video Editor")
    log.info("=" * 55)
    log.info(f"  Input   : {input_path}")
    log.info(f"  Output  : {output_path}")
    log.info(f"  Zoom    : {cfg.max_zoom}x")
    log.info(f"  Workers : {cfg.workers}")
    log.info(f"  Preview : {cfg.preview_mode}")
    log.info("=" * 55)

    t0 = time.time()

    pipeline = Pipeline(cfg)
    pipeline.run(input_path, output_path)

    elapsed = time.time() - t0
    log.info(f"\n✓  Finished in {elapsed:.1f}s  →  {output_path}")


if __name__ == "__main__":
    main()
