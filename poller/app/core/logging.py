"""Logging configuration helpers."""
import logging


def configure_logging(debug: bool) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
