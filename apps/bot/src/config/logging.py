import logging

from src.config.models import AppConfig


_LOGGER_NAMES = ("tab.latency", "tab.errors", "tab.audit")
_LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s — %(message)s"
_configured = False


def setup_logging(config: AppConfig) -> None:
    global _configured

    formatter = logging.Formatter(_LOG_FORMAT)
    for name in _LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        else:
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setFormatter(formatter)
    _configured = True


def _get_logger(name: str) -> logging.Logger:
    if not _configured:
        raise RuntimeError("Logging has not been initialized; call setup_logging() first")
    return logging.getLogger(name)


def get_latency_logger() -> logging.Logger:
    return _get_logger("tab.latency")


def get_error_logger() -> logging.Logger:
    return _get_logger("tab.errors")


def get_audit_logger() -> logging.Logger:
    return _get_logger("tab.audit")
