#!/usr/bin/env python3
"""
AdEdit CLI — AI Advertising Video Editor
=========================================
Usage:
    python cli.py input.mp4 output.mp4 --brand "MyApp" --tagline "Ship faster"
    python cli.py input.mp4 output.mp4 --music upbeat --grade vivid
    python cli.py input.mp4 output.mp4 --no-music --grade cinematic --logo
"""

import argparse
import sys
import time
from pathlib import Path

from core.ad_pipeline import AdPipeline
from utils.ad_config import AdConfig
from utils.logger import get_logger


def parse_args():
    p = argparse.ArgumentParser(
        description="Transform a demo recording into a polished advertising video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py demo.mp4 ad_out.mp4 --brand "Acme" --tagline "Built for speed"
  python cli.py demo.mp4 ad_out.mp4 --music upbeat --grade vivid --logo
  python cli.py demo.mp4 ad_out.mp4 --no-music --zoom 3.0 --verbose
        """
    )

    p.add_argument("input",  help="Input demo video (.mp4/.mov/.avi)")
    p.add_argument("output", help="Output ad video (.mp4)")

    # Brand
    p.add_argument("--brand",      default="Your Brand", help="Brand name for overlays")
    p.add_argument("--tagline",    default="",           help="Tagline shown on intro/outro")
    p.add_argument("--primary",    default="#00D4FF",    help="Primary color hex (default: #00D4FF)")
    p.add_argument("--secondary",  default="#FF6B35",    help="Secondary color hex (default: #FF6B35)")

    # Style
    p.add_argument("--grade",  default="cinematic",
                   choices=["cinematic", "vivid", "cool", "warm", "moody", "none"],
                   help="Color grade style")
    p.add_argument("--music",  default="corporate",
                   choices=["corporate", "upbeat", "dramatic", "calm", "none"],
                   help="Background music style")
    p.add_argument("--zoom",   type=float, default=2.2,  help="Max zoom level")

    # Toggles
    p.add_argument("--logo",        action="store_true",  help="Add logo watermark")
    p.add_argument("--no-music",    action="store_true",  help="Disable background music")
    p.add_argument("--no-chapters", action="store_true",  help="Disable chapter cards")
    p.add_argument("--no-letterbox",action="store_true",  help="Disable letterbox bars")
    p.add_argument("--no-ripple",   action="store_true",  help="Disable click ripples")
    p.add_argument("--no-speed",    action="store_true",  help="Disable speed ramping")

    # Processing
    p.add_argument("--workers",     type=int, default=4, help="Parallel workers")
    p.add_argument("--cursor-log",  default=None,        help="CSV cursor log path")
    p.add_argument("--verbose",     action="store_true", help="Verbose logging")

    return p.parse_args()


def main():
    args = parse_args()

    log        = get_logger("cli", args.verbose)
    input_path = Path(args.input)
    out_path   = Path(args.output)

    if not input_path.exists():
        log.error(f"Input not found: {input_path}")
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cfg = AdConfig(
        brand_name      = args.brand,
        tagline         = args.tagline,
        primary_color   = args.primary,
        secondary_color = args.secondary,
        color_grade     = args.grade,
        music_style     = "none" if args.no_music else args.music,
        max_zoom        = args.zoom,
        add_logo        = args.logo,
        chapters_enabled    = not args.no_chapters,
        letterbox_enabled   = not args.no_letterbox,
        ripple_enabled      = not args.no_ripple,
        speed_ramp_enabled  = not args.no_speed,
        workers         = args.workers,
        cursor_log      = args.cursor_log,
        verbose         = args.verbose,
    )

    log.info("=" * 55)
    log.info("  AdEdit — AI Advertising Video Editor")
    log.info("=" * 55)
    log.info(f"  Input   : {input_path}")
    log.info(f"  Output  : {out_path}")
    log.info(f"  Brand   : {cfg.brand_name}")
    log.info(f"  Grade   : {cfg.color_grade}")
    log.info(f"  Music   : {cfg.music_style}")
    log.info("=" * 55)

    t0 = time.time()
    AdPipeline(cfg).run(input_path, out_path)
    elapsed = time.time() - t0
    log.info(f"\n✓  Done in {elapsed:.1f}s  →  {out_path}")


if __name__ == "__main__":
    main()
