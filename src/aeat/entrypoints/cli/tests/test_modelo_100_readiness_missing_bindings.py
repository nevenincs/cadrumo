"""Modelo 100 readiness must expose every missing calculation binding."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODELO = "100"
_YEAR = "2025"
_PERIOD = "0A"
_REVISION = "2025"


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            yield
        finally:
            dispose_engine()


def _create_natural_person_profile() -> None:
    result = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Readiness",
            "--activity", "design",
            "--irpf-income-categories", "actividad_economica",
            "--irpf-estimation-regime", "directa_normal",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_modelo_100_readiness_matches_bindings_list_missing_blockers() -> None:
    """Profile-ready M100 still blocks when calculation bindings are missing.

    The real CLI surfaces must agree: the readiness report cannot claim or imply
    the operator can calculate while ``bindings list --missing`` still shows
    required manual, ledger, relation, or previous-filing inputs.
    """

    _create_natural_person_profile()

    readiness = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "readiness",
            "--modelo", _MODELO,
            "--revision-id", _REVISION,
            "--year", _YEAR,
            "--period", _PERIOD,
        ],
    )  # fmt: skip
    assert readiness.exit_code == 0, readiness.output
    readiness_payload = _payload(readiness.output)

    missing = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "bindings", "list",
            "--modelo", _MODELO,
            "--year", _YEAR,
            "--period", _PERIOD,
            "--missing",
        ],
    )  # fmt: skip
    assert missing.exit_code == 0, missing.output
    bindings_payload = _payload(missing.output)

    readiness_missing = {row["binding_id"]: row for row in readiness_payload["missing_bindings"]}
    bindings_missing_ids = {row["binding_id"] for row in bindings_payload["bindings"]}

    assert readiness_payload["profile_ready"] is True
    assert readiness_payload["ledger_ready"] is True
    assert readiness_payload["ready"] is False
    assert readiness_payload["binding_ready"] is False
    envelope = json.loads(readiness.output)
    assert envelope["notices"][0]["code"] == "modelo.readiness.ledger_preflight_scope"
    assert envelope["notices"][0]["context"]["missing_bindings"] == str(len(readiness_missing))
    assert readiness_missing.keys() == bindings_missing_ids
    assert {
        "manual_input",
        "ledger_renta_expense_aggregation",
        "relation_prefill",
        "previous_filing",
    } <= {row["source"] for row in readiness_missing.values()}

    text_readiness = invoke_cached_cli(
        [
            "app", "modelo", "readiness",
            "--modelo", _MODELO,
            "--revision-id", _REVISION,
            "--year", _YEAR,
            "--period", _PERIOD,
        ],
    )
    assert text_readiness.exit_code == 0, text_readiness.output
    assert "ready\tFalse" in text_readiness.output
    assert "source_binding_ready\tFalse" in text_readiness.output
    assert "ledger_ready_scope\ttransaction_preflight_only" in text_readiness.output
    assert "readiness_note\tledger_ready only means" in text_readiness.output
    assert (
        "missing_bindings_command\taeat app modelo bindings list "
        "--modelo 100 --year 2025 --period 0A --missing"
    ) in text_readiness.output
