import logging
from logging.handlers import RotatingFileHandler

from app.config import BACKEND_DIR


def setup_logging() -> None:
    """Настраивает консоль и файл с ограничением размера и тремя архивами."""
    log_dir = BACKEND_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            ),
        ],
        force=True,
    )
