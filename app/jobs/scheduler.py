"""Minimal in-process background scheduler for demo jobs."""
import threading
import time
import logging

from app.jobs.usage_alerts import check_usage_alerts

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Background scheduler started (interval=%ss)", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                check_usage_alerts()
            except Exception:
                logger.exception("Background job failed")
            self._stop_event.wait(self.interval_seconds)


_scheduler = BackgroundScheduler(interval_seconds=60)


def start_scheduler() -> None:
    _scheduler.start()


def stop_scheduler() -> None:
    _scheduler.stop()
