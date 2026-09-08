"""Child-pytest probe recording each xdist worker's resolved basetemp."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("ordinal", range(8))
def test_record_worker_basetemp(ordinal: int, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Materialise a real ``tmp_path`` and record the basetemp that produced it."""
    tmp_path.joinpath("occupant.txt").write_text(str(ordinal), encoding="utf-8")
    destination = Path(os.environ["CADRUMO_WORKER_BASETEMP_PROBE"])
    record = destination / f"{uuid.uuid4().hex}.json"
    record.write_text(
        json.dumps(
            {
                "basetemp": str(tmp_path_factory.getbasetemp()),
                "ordinal": ordinal,
                "tmp_path": str(tmp_path),
                "worker": os.environ.get("PYTEST_XDIST_WORKER", ""),
            }
        ),
        encoding="utf-8",
    )
