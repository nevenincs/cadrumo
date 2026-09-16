"""A session opened before any SQL import is still sealed and disposed at exit.

Opening a bucket session does not import SQLAlchemy; the engine layer loads when
the session first touches storage or is disposed. A process that opens a session
and never reaches storage therefore reaches interpreter shutdown with SQLAlchemy
unimported, and the exit hook must still seal the session and dispose its bucket
engines cleanly from inside shutdown.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

import pytest
from pydantic import TypeAdapter

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_JSON_OBJECT_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])

#: Run in a child interpreter. ``argv[1]`` is the evidence file.
_CHILD: Final = """
import atexit, json, sys
from pathlib import Path

evidence = Path(sys.argv[1])
observed = {}

def _observe_after_the_substrate_hook() -> None:
    observed["sealed_at_exit"] = session.sealed
    observed["sql_loaded_at_exit"] = "sqlalchemy" in sys.modules
    evidence.write_text(json.dumps(observed), encoding="utf-8")

atexit.register(_observe_after_the_substrate_hook)

from datetime import UTC, datetime, timedelta

from cadrumo.adapters.persistence.storage.master_key import active_session as _substrate
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession

_opened_at = datetime.now(UTC)
session = BucketSession.open_resumed(
    bucket_id="exit-hook-sql-probe",
    dek=b"d" * 32,
    idle_minutes=5,
    opened_at=_opened_at,
    idle_deadline=_opened_at + timedelta(minutes=5),
    absolute_deadline=_opened_at + timedelta(minutes=5),
)
observed["sealed_before_exit"] = session.sealed
observed["sql_loaded_before_exit"] = "sqlalchemy" in sys.modules
"""


def test_a_session_opened_without_sql_is_sealed_and_disposed_at_exit(tmp_path: Path) -> None:
    evidence = tmp_path / "exit-observation.json"
    completed = run_audited_process(
        [sys.executable, "-c", _CHILD, str(evidence)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert completed.returncode == 0, f"child failed: {completed.stderr[-800:]}"
    assert "Traceback" not in completed.stderr, completed.stderr[-800:]
    observed = _JSON_OBJECT_ADAPTER.validate_python(json.loads(evidence.read_text(encoding="utf-8")))
    assert observed == {
        "sealed_before_exit": False,
        "sql_loaded_before_exit": False,
        "sealed_at_exit": True,
        "sql_loaded_at_exit": True,
    }
