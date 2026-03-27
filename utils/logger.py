import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import g, request


ANSI_RESET = "\033[0m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def _colorize(text: str, color_code: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{color_code}{text}{ANSI_RESET}"


def setup_logger(name: str = "app", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


class StartupTracker:
    def __init__(self, logger: logging.Logger, name: str = "startup"):
        self.logger = logger
        self.name = name
        self.started_at = time.perf_counter()
        self.active_sections: Dict[str, float] = {}
        self.use_color = _supports_color()
        self.overwrite_enabled = sys.stdout.isatty()
        self._active_line: Optional[str] = None
        self._active_line_len = 0

    def _print_line(self, message: str, replace_active: bool = False) -> None:
        if not self.overwrite_enabled:
            self.logger.info("%s", message)
            return

        if replace_active and self._active_line is not None:
            visible_len = len(message)
            clear_padding = " " * max(0, self._active_line_len - visible_len)
            sys.stdout.write(f"\r{message}{clear_padding}\n")
            sys.stdout.flush()
            self._active_line = None
            self._active_line_len = 0
            return

        if self._active_line is not None:
            sys.stdout.write("\n")

        self._active_line = message
        self._active_line_len = len(message)
        sys.stdout.write(message)
        sys.stdout.flush()

    def start(self, section: str, **extra: Any) -> Dict[str, Any]:
        now = time.perf_counter()
        self.active_sections[section] = now
        payload: Dict[str, Any] = {
            "event": "startup_section_start",
            "startup_name": self.name,
            "section": section,
            "total_ms": round((now - self.started_at) * 1000, 2),
            "ts_utc": _utc_iso_now(),
        }
        if extra:
            payload["extra"] = extra
        line = _colorize(f"START {section}", ANSI_CYAN, self.use_color)
        self._print_line(line, replace_active=False)
        return payload

    def done(self, section: str, **extra: Any) -> Dict[str, Any]:
        now = time.perf_counter()
        section_start = self.active_sections.pop(section, None)
        section_ms = None if section_start is None else round((now - section_start) * 1000, 2)
        payload: Dict[str, Any] = {
            "event": "startup_section_done",
            "startup_name": self.name,
            "section": section,
            "section_ms": section_ms,
            "total_ms": round((now - self.started_at) * 1000, 2),
            "ts_utc": _utc_iso_now(),
        }
        if extra:
            payload["extra"] = extra
        time_suffix = "n/a" if section_ms is None else f"{section_ms}ms"
        line = _colorize(f"DONE  {section} [{time_suffix}]", ANSI_GREEN, self.use_color)
        self._print_line(line, replace_active=True)
        return payload

    def warn_unfinished(self) -> Optional[Dict[str, Any]]:
        if not self.active_sections:
            return None
        if self._active_line is not None and self.overwrite_enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._active_line = None
            self._active_line_len = 0
        payload: Dict[str, Any] = {
            "event": "startup_unfinished_sections",
            "startup_name": self.name,
            "sections": sorted(self.active_sections.keys()),
            "total_ms": round((time.perf_counter() - self.started_at) * 1000, 2),
            "ts_utc": _utc_iso_now(),
        }
        line = _colorize("WARN  startup unfinished sections", ANSI_YELLOW, self.use_color)
        self.logger.warning("%s", line)
        return payload

    def complete(self, **extra: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "event": "startup_complete",
            "startup_name": self.name,
            "total_ms": round((time.perf_counter() - self.started_at) * 1000, 2),
            "ts_utc": _utc_iso_now(),
        }
        if extra:
            payload["extra"] = extra
        if self._active_line is not None and self.overwrite_enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._active_line = None
            self._active_line_len = 0
        line = _colorize(f"DONE", ANSI_GREEN, self.use_color)
        self.logger.info("%s", line)
        return payload


def request_start() -> None:
    g.req_start = time.perf_counter()
    g.request_id = str(uuid.uuid4())


def build_request_payload(
    response_status: int,
    user_id: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    req_start = getattr(g, "req_start", time.perf_counter())
    duration_ms = round((time.perf_counter() - req_start) * 1000, 2)

    payload: Dict[str, Any] = {
        "event": "request",
        "request_id": getattr(g, "request_id", None),
        "method": request.method,
        "path": request.path,
        "query_string": request.query_string.decode("utf-8", errors="replace"),
        "status_code": response_status,
        "duration_ms": duration_ms,
        "remote_addr": request.remote_addr,
        "user_agent": request.user_agent.string,
        "user_id": user_id,
        "content_length": request.content_length,
        "ts_utc": _utc_iso_now(),
    }
    if extra:
        payload["extra"] = extra
    return payload


def _to_section_label(raw: str) -> str:
    cleaned = raw.replace("-", " ").replace("_", " ").strip()
    if not cleaned:
        return "General"
    return cleaned.title()


def _request_scope(path: str) -> tuple[str, str]:
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return "route", "Home"

    root = segments[0].lower()
    if root == "api":
        section = _to_section_label(segments[1]) if len(segments) > 1 else "General"
        return "api", section
    if root == "auth":
        section = _to_section_label(segments[1]) if len(segments) > 1 else "Auth"
        return "auth", section
    if root == "oauth":
        section = _to_section_label(segments[1]) if len(segments) > 1 else "Oauth"
        return "oauth", section
    return "route", _to_section_label(root)


def format_request_log_line(payload: Dict[str, Any]) -> str:
    user_id = payload.get("user_id")
    user_text = "NA" if user_id is None else str(user_id)
    request_type, section = _request_scope(str(payload.get("path", "")))
    duration_ms = payload.get("duration_ms", "n/a")
    status_code = payload.get("status_code", "n/a")
    method = payload.get("method", "NA")
    path = payload.get("path", "/")
    return f"{user_text}:[{section}][{request_type}] {method} {path} {status_code} {duration_ms}ms"


def log_request(logger: logging.Logger, payload: Dict[str, Any]) -> None:
    logger.info("%s", format_request_log_line(payload))
