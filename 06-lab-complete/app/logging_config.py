"""
Structured logging — mỗi dòng log của app là đúng một JSON object.

Cấu hình logger "agent" một lần, ngay khi main.py import module này (trước mọi thứ khác),
để không có đoạn code nào khác kịp gọi logging.basicConfig() và làm mất định dạng JSON.
"""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "lvl": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)  # traceback nằm trong 1 chuỗi JSON
        return json.dumps(payload, default=str)  # ensure_ascii mặc định: an toàn với console cp1252


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("agent")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # không để root logger in thêm dòng không phải JSON
    return logger


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    logging.getLogger("agent").log(level, event, extra={"fields": fields})
