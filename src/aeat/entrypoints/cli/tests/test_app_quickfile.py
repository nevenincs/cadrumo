"""Real-behavior CLI tests for ``aeat app quickfile``.

Drives the one-command filing chain through the real ``aeat`` CLI against an
isolated real-session backend (real KEK/DEK, real encrypted SQLite) — no mocks,
no seeded revisions. Each test runs the actual
readiness -> create -> calculate -> verify -> export services in sequence.

Coverage:
- a calculable modelo (115, fed one real retención observation) runs the whole
  chain to a written fichero-BOE file;
- a modelo whose verify gate refuses (130 without clean cross-period evidence)
  halts instructively at ``verify`` with ``export`` skipped and a non-zero exit.

The chain is build + export only: no live AEAT submission path is exercised or
reachable (``aeat-safety-legal-gates``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_envelope_notices as _notices
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Signatures of the concurrent-registry-write race documented by the
# ``aeat-local-execution`` rule: in the shared worktree a peer agent may be
# editing the registry TOML tree while these tests load it, producing a
# transient mid-edit validation/fingerprint error. The rule's guidance is to
# re-run rather than triage as a regression; ``_invoke`` encodes that as a
# bounded retry keyed strictly on these transient markers so a real failure
# (a genuine refusal, a wrong value) is never masked.
_TRANSIENT_REGISTRY_RACE_MARKERS = (
    "registry directory changed during cache fingerprinting",
    "required-role gate",
    "duplicate catalogue ids",
    "references unknown source id",
)


def _invoke(args: Sequence[str], *, attempts: int = 8) -> Result:
    """Invoke the CLI, re-running only on the transient registry-write race."""
    result = invoke_cached_cli(list(args))
    tries = 1
    while (
        tries < attempts
        and result.exit_code != 0
        and any(marker in result.output for marker in _TRANSIENT_REGISTRY_RACE_MARKERS)
    ):
        time.sleep(2)
        dispose_engine()
        result = invoke_cached_cli(list(args))
        tries += 1
    return result


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _create_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Quickfile",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _seed_m115_retencion_observation() -> None:
    """Persist one real URBAN_RENTAL retención observation for M115 2026 1T.

    Modelo 115 aggregates its cuota from persisted retención evidence; with one
    observation seeded the calculate stage resolves and the chain runs to
    completion. This is the source-preflight the ``calculate`` stage reads.
    """
    observation = json.dumps(
        {
            "source_kind": "ledger_transaction",
            "source_object_id": "rent-ledger-row-001",
            "perceptor_nif": "B12345678",
            "perceptor_name": "Arrendador Ejemplo SL",
            "scheme": "arrendamiento_urbano",
            "taxable_base": "2700.00",
            "retencion_amount": "513.00",
            "accrued_on": "2026-03-15",
        },
    )
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "115", "--year", "2026", "--period", "1T",
            "--retencion-observation", observation,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _stage_status(payload: dict[str, object]) -> dict[str, str]:
    return {stage["stage"]: stage["status"] for stage in payload["stages"]}


def test_quickfile_runs_full_chain_to_exported_fichero(tmp_path: Path) -> None:
    """``aeat app quickfile`` for a calculable modelo writes a fichero-BOE file.

    Modelo 115 1T 2026 with one seeded retención observation is calculable, so
    the whole chain — readiness, create, calculate, verify, export — completes in
    one command and leaves a non-empty local artefact on disk.
    """

    _create_profile()
    _seed_m115_retencion_observation()
    out = tmp_path / "modelo-115.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "115", "--year", "2026", "--period", "1T",
            "--casilla", "04=0",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    # The completed chain rides the shared envelope spine under the ``quickfile``
    # command key. Its ``status`` is an exit-0 state (``success``, or ``warning``
    # when the advisory readiness notice fires) — never ``error``; the exit code
    # and ``completed`` flag are the authoritative success signals.
    envelope = json.loads(result.output)
    assert envelope["command"] == "quickfile"
    assert envelope["status"] in {"success", "warning"}, result.output
    payload = _payload(result.output)
    assert payload["completed"] is True, result.output
    assert payload["stopped_at_stage"] is None
    assert payload["granted_verificado_completo"] is True
    assert payload["work_unit_id"]
    assert payload["calculation_revision_id"]

    statuses = _stage_status(payload)
    assert statuses["create"] == "ok"
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "ok"
    assert statuses["export"] == "ok"
    # readiness is advisory and may be ok or warning; it must never refuse.
    assert statuses["readiness"] in {"ok", "warning"}

    # The terminal stage wrote a real fichero-BOE artefact locally.
    assert payload["export"] is not None
    assert payload["export"]["output_path"] == str(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_quickfile_stops_instructively_when_verify_refuses(tmp_path: Path) -> None:
    """A verify refusal halts the chain at ``verify`` with ``export`` skipped.

    Modelo 130 1T 2025 verify refuses without clean cross-period evidence
    (M130 -> M100 dependency). Quickfile must stop at verify, mark export
    skipped, exit non-zero, and surface the blocking cross-period finding on the
    notices channel — never write an export file.
    """

    _create_profile()
    out = tmp_path / "modelo-130.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is False
    assert payload["stopped_at_stage"] == "verify"
    assert payload["granted_verificado_completo"] is False
    assert payload["export"] is None

    statuses = _stage_status(payload)
    assert statuses["create"] == "ok"
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "refused"
    assert statuses["export"] == "skipped"

    # The instructive stop carries the cross-period blocking finding on the shared
    # notices channel (a non-granted verify reads as a warning; NoticeSeverity has
    # no ERROR member), and the export artefact was never written.
    codes = {notice["code"] for notice in _notices(result.output)}
    assert any("cross_period" in code for code in codes), codes
    assert not out.exists()


def test_quickfile_requires_output_flag() -> None:
    """Quickfile refuses without ``--output`` (the export destination is required)."""

    _create_profile()
    result = _invoke(
        ["app", "quickfile", "--modelo", "115", "--year", "2026", "--period", "1T"],
    )
    assert result.exit_code != 0
    assert "output" in result.output.lower()
