import logging
import logging.config
import sys
from pathlib import Path


class LifecycleFilter(logging.Filter):
    """Reclassifica logs do uvicorn para não confundir ciclo de vida com erro.

    Mensagens INFO de 'uvicorn.error' (startup/shutdown) são renomeadas para o
    logger 'server'; erros reais (WARNING+) mantêm o nome 'uvicorn.error' e
    continuam indo para o error.json. Logs de acesso viram 'access'.
    """

    _LIFECYCLE = (
        "Started server process",
        "Waiting for application startup",
        "Application startup complete",
        "Waiting for application shutdown",
        "Application shutdown complete",
        "Finished server process",
        "Uvicorn running on",
        "Started parent process",
        "Shutting down",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith("uvicorn.error"):
            if record.levelno < logging.WARNING and any(
                msg in record.getMessage() for msg in self._LIFECYCLE
            ):
                record.name = "server"
            return True
        if record.name.startswith("uvicorn.access"):
            record.name = "access"
        return True


def setup_logging():
    """Configure structured logging for the application."""

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "lifecycle": {
                "()": LifecycleFilter,
            },
        },
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}',
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
            "access": {
                "format": '%(asctime)s - %(client_addr)s - "%(request_line)s" %(status_code)s',
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": sys.stdout,
                "level": "INFO",
                "filters": ["lifecycle"],
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": log_dir / "app.json",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "level": "INFO",
                "filters": ["lifecycle"],
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": log_dir / "error.json",
                "maxBytes": 10485760,
                "backupCount": 5,
                "level": "ERROR",
                "filters": ["lifecycle"],
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file", "error_file"],
                "level": "INFO",
                "propagate": True,
            },
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console", "file", "error_file"],
                "level": "INFO",
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)
    return logging.getLogger(__name__)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)