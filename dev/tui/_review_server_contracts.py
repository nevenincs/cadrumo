"""Shared review transport bounds and page location."""

from __future__ import annotations

from pathlib import Path
from typing import Final

DEFAULT_REVIEW_PORT: Final[int] = 8740


WATCH_INTERVAL_SECONDS: Final[float] = 1.0


KEEPALIVE_SECONDS: Final[float] = 15.0
"""Idle gap between comment lines on the event stream, so a mobile network or
a sleeping tab notices a dead connection and reconnects."""


REQUEST_BODY_LIMIT: Final[int] = 64 * 1024


PAGE_PATH: Final[Path] = Path(__file__).with_name("review_page.html")
"""Read on every request, so an edit to the page shows on the next reload."""


_IMMUTABLE: Final[str] = "public, max-age=31536000, immutable"
