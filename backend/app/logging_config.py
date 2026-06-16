"""Minimal structured (JSON) logging to stdout.

systemd captures stdout, so `journalctl -u hyzerpath -f` shows the logs. Any
`extra={...}` passed to a log call is merged into the JSON line, e.g.
    logger.info("deploy triggered", extra={"ip": ip})
"""
import json
import logging
import os
import sys
import time

# Attributes the stdlib puts on every LogRecord — anything else is a custom
# field a caller passed via `extra=` and should appear in the JSON output.
_RESERVED = set(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Route the root logger (and uvicorn's) through the JSON formatter."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own handlers; clear them so its logs are JSON too
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        log.handlers = []
        log.propagate = True
