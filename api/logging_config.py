"""
Logging configuration for the internal chatbot application.
Provides structured logging with correlation IDs and proper formatting.
"""

import logging
import logging.config
import json
import sys
from datetime import datetime
import uuid


class CorrelationIDFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = getattr(self, '_correlation_id', 'no-id')
        return True


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', 'no-id'),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage',
                          'correlation_id']:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Setup application logging configuration."""

    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure logging format
    if log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationIDFilter())

    root_logger.addHandler(console_handler)

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("psycopg2").setLevel(logging.WARNING)

    # Set correlation ID for the current context
    CorrelationIDFilter._correlation_id = str(uuid.uuid4())[:8]


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with correlation ID support."""
    logger = logging.getLogger(name)
    return logger


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for the current context."""
    CorrelationIDFilter._correlation_id = correlation_id


def log_request(logger: logging.Logger, method: str, path: str,
                status_code: int, duration_ms: float, **kwargs) -> None:
    """Log HTTP request details."""
    logger.info(
        f"{method} {path} - {status_code}",
        extra={
            "event_type": "http_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            **kwargs
        }
    )


def log_embedding_request(logger: logging.Logger, text_length: int,
                         model: str, duration_ms: float, **kwargs) -> None:
    """Log embedding request details."""
    logger.info(
        "Embedding request completed",
        extra={
            "event_type": "embedding_request",
            "text_length": text_length,
            "model": model,
            "duration_ms": duration_ms,
            **kwargs
        }
    )


def log_llm_request(logger: logging.Logger, model: str, prompt_length: int,
                   response_length: int, duration_ms: float, **kwargs) -> None:
    """Log LLM request details."""
    logger.info(
        "LLM request completed",
        extra={
            "event_type": "llm_request",
            "model": model,
            "prompt_length": prompt_length,
            "response_length": response_length,
            "duration_ms": duration_ms,
            **kwargs
        }
    )


def log_file_ingestion(logger: logging.Logger, file_path: str,
                      chunks_created: int, duration_ms: float, **kwargs) -> None:
    """Log file ingestion details."""
    logger.info(
        f"File ingested: {file_path}",
        extra={
            "event_type": "file_ingestion",
            "file_path": str(file_path),
            "chunks_created": chunks_created,
            "duration_ms": duration_ms,
            **kwargs
        }
    )
