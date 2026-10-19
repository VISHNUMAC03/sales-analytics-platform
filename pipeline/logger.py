"""
Logging setup.

print() disappears when a program runs in Docker or on a schedule. A logger
writes timestamped, levelled messages (INFO / WARNING / ERROR) to the screen
AND to logs/pipeline.log, so you can find out later what happened and why
a run failed.
"""

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(log_dir: Path, level: int = logging.INFO) -> Path:
    """Send log messages to the console and to <log_dir>/pipeline.log."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline.log"

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()  # avoid duplicate lines if called twice

    formatter = logging.Formatter(LOG_FORMAT)
    for handler in (logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    return log_file
