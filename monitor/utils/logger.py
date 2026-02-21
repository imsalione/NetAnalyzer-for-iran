"""
Logging Configuration
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_dir: Path = None):
    """Setup application logger."""
    logger.remove()
    
    if log_dir is None:
        log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Console (if available)
    if sys.stderr is not None:
        try:
            logger.add(
                sys.stderr,
                format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
                level="INFO",
                colorize=True
            )
        except:
            pass
    
    # File
    logger.add(
        log_dir / "monitor_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        rotation="5 MB",
        retention="7 days"
    )
    
    return logger
