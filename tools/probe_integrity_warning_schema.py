"""Schema-stability probe for the secure-objects table.

Snapshots the secure-objects table schema at process start and exit and
reports any drift, logging the observing pid and ISO-8601 timestamps on
both ends. The drift report is a JSON document on stdout.

This probe complements ``probe_integrity_warning_determinism`` by ruling
out schema mutation as the cause of phantom ``unreadable_rows`` drift,
per the hypothesis recorded in
``2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr``.

Usage::

    python tools/probe_integrity_warning_schema.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aeat.adapters.persistence.storage.sql.secure_objects import (  # noqa: E402
    SecureObjectRepository,
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _columns() -> tuple[tuple[str, str], ...]:
    repo = SecureObjectRepository()
    engine = repo._engine  # type: ignore[attr-defined]
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT name, type FROM pragma_table_info('secure_objects')"
        ).fetchall()
    return tuple((row[0], row[1]) for row in rows)


def main(argv: list[str] | None = None) -> int:
    self_pid = os.getpid()
    start_at = _now()
    start_schema = _columns()
    # A short window so a concurrent writer has time to mutate the
    # schema if it is going to.
    time.sleep(1.0)
    end_at = _now()
    end_schema = _columns()
    drift = start_schema != end_schema
    payload = {
        "observing_pid": self_pid,
        "start_observed_at": start_at,
        "end_observed_at": end_at,
        "start_schema": [list(item) for item in start_schema],
        "end_schema": [list(item) for item in end_schema],
        "drift_detected": drift,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
