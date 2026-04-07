"""Coloured console logger."""

import logging
import sys

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
GRAY   = "\033[90m"


class ColourFormatter(logging.Formatter):
    LEVEL_COLOURS = {
        logging.DEBUG:    GRAY,
        logging.INFO:     CYAN,
        logging.WARNING:  YELLOW,
        logging.ERROR:    RED,
        logging.CRITICAL: RED + BOLD,
    }

    def format(self, record):
        colour = self.LEVEL_COLOURS.get(record.levelno, RESET)
        msg    = super().format(record)
        return f"{colour}{msg}{RESET}"


def get_logger(name: str, verbose: bool = False) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(ColourFormatter(
            "%(asctime)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S"
        ))
        log.addHandler(h)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    return log
