"""Base package utilities.

Provides get_logger(...) used across the base package.
"""

import logging
from logging import Logger
from typing import Optional

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(
    name: str, level: int = logging.INFO, *, log_file: Optional[str] = None
) -> Logger:
    """Return a configured logger.

    - Ensures handlers are not added multiple times for the same logger name.
    - By default logs to the console. Optionally writes to a file if log_file is provided.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (default INFO)
        log_file: Optional path to a file to also write logs to.

    Returns:
        logging.Logger: configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(fmt)
        logger.addHandler(console)

        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)

    return logger
