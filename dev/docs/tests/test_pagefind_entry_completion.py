"""The index pass waits for a complete Pagefind entry and refuses one that never completes.

Pagefind acknowledges its write before ``pagefind-entry.json`` is fully on disk,
and closing the service terminates the indexer. Without the wait a loaded host
occasionally produced an empty entry while the build reported success.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from ..pagefind_index import PagefindIndexWriteError, await_complete_pagefind_entry

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_entry_completed_after_the_write_acknowledgement_is_awaited(tmp_path: Path) -> None:
    entry = tmp_path / "pagefind-entry.json"
    entry.write_bytes(b"")
    document = {"version": "1", "languages": {"en": {"hash": "en_x", "page_count": 2}}}

    def _finish_writing() -> None:
        entry.write_text(json.dumps(document), encoding="utf-8")

    timer = threading.Timer(0.3, _finish_writing)
    timer.start()
    try:
        asyncio.run(await_complete_pagefind_entry(entry, deadline_seconds=10))
    finally:
        timer.join()

    assert json.loads(entry.read_text(encoding="utf-8")) == document


def test_an_entry_that_never_completes_is_refused_rather_than_published(tmp_path: Path) -> None:
    entry = tmp_path / "pagefind-entry.json"
    entry.write_bytes(b"")

    with pytest.raises(PagefindIndexWriteError, match="never became a complete JSON document"):
        asyncio.run(await_complete_pagefind_entry(entry, deadline_seconds=0.2))


def test_a_complete_entry_returns_at_once(tmp_path: Path) -> None:
    entry = tmp_path / "pagefind-entry.json"
    entry.write_text('{"version": "1", "languages": {}}', encoding="utf-8")

    asyncio.run(await_complete_pagefind_entry(entry, deadline_seconds=0))
