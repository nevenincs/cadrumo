"""Shape tests for the ``aeat app modelo m036`` declarative-recording verbs.

Drives the CLI surface introduced by M036 commit 3 of 3: the
``m036_app`` Typer subgroup with ``alta`` / ``modificacion`` / ``baja``
verbs. Asserts each verb advertises the three operator-supplied flags
(``--declared-on``, ``--sede-justificante``, ``--note``), refuses
invocation without an active profile (the existing ``_require_active_profile``
guard), and rejects invalid date input cleanly.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from click.testing import Result
from pydantic import ValidationError

from ....application.modelo import ModeloReconciliationEvidenceKind, ModeloReconciliationVerdict
from ....tests.cli_runner import invoke_cached_cli
from .._modelo_m036_cli import m036_alta, m036_baja, m036_modificacion
from .._modelo_payloads_m036 import (
    ModeloReconciliationHistoryResult,
    ModeloReconciliationHistoryRowPayload,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_M036_VERBS = ("alta", "modificacion", "baja")
_M036_VERB_HANDLERS = (m036_alta, m036_modificacion, m036_baja)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def test_m036_verb_advertises_flag_set() -> None:
    """Each verb's --help surfaces --declared-on / --sede-justificante / --note."""
    for verb in _M036_VERBS:
        result = _invoke(["app", "modelo", "m036", verb, "--help"])
        assert result.exit_code == 0, result.output
        assert "--declared-on" in result.output, verb
        assert "--sede-justificante" in result.output, verb
        assert "--note" in result.output, verb


def test_m036_verb_help_describes_external_routes_and_optional_electronic_justificante() -> None:
    """Each callback docstring keeps office filing separate from electronic evidence."""
    for handler in _M036_VERB_HANDLERS:
        description = " ".join((handler.__doc__ or "").split())
        assert "AEAT Sede" in description, handler.__name__
        assert "competent AEAT office" in description, handler.__name__
        assert "electronic justificante is optional" in description, handler.__name__


def test_m036_group_lists_three_verbs() -> None:
    """``aeat app modelo m036 --help`` lists the three declarative verbs."""
    result = _invoke(["app", "modelo", "m036", "--help"])
    assert result.exit_code == 0, result.output
    assert "alta" in result.output
    assert "modificacion" in result.output
    assert "baja" in result.output


def test_m036_rejects_invalid_declared_on() -> None:
    """An unparseable --declared-on fails cleanly with a non-zero exit."""
    for verb in _M036_VERBS:
        result = _invoke(
            ["app", "modelo", "m036", verb, "--declared-on", "not-a-date"],
        )
        assert result.exit_code != 0, verb


def test_m036_refuses_without_active_profile() -> None:
    """No active profile -> the cold-start guard refuses with a translated message."""
    for verb in _M036_VERBS:
        result = _invoke(
            ["app", "modelo", "m036", verb, "--declared-on", "2026-06-04"],
        )
        assert result.exit_code != 0, verb
        # The translated guard message is locale-dependent; the assertion
        # checks the verb did not silently proceed (non-zero exit) and the
        # output reaches the operator surface. Active-profile presence is
        # required for any actual record write; tests of the service body
        # itself live in ``application/modelo/test_m036_lifecycle_service.py``.
        assert result.output != "", verb


def test_reconciliation_history_row_enforces_the_canonical_entry_contract() -> None:
    """The transport row must not accept values its canonical entry refuses.

    ``ModeloReconciliationHistoryEntry`` closes ``source_kind``/``verdict`` to
    enums, bounds ``event_id``/``actor``, requires a non-negative ``diff_count``
    and a real ``reconciled_at``. The CLI row redeclared all of them as free
    strings and ints, so a malformed reconciliation could cross the
    ``modelo.reconcile.history`` envelope.
    """
    base = dict(
        event_id="e" * 32,
        bucket_id="b" * 64,
        work_unit_id="a1" * 32,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_path="justificante.pdf",
        verdict=ModeloReconciliationVerdict.MATCHES,
        diff_count=0,
        actor="operator",
        reconciled_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    row = ModeloReconciliationHistoryRowPayload.model_validate(base)
    assert row.source_kind is ModeloReconciliationEvidenceKind.JUSTIFICANTE
    assert row.verdict is ModeloReconciliationVerdict.MATCHES

    rendered = json.loads(row.model_dump_json())
    assert rendered["source_kind"] == "justificante"
    assert rendered["verdict"] == "matches"

    for label, override in (
        ("blank event id", {"event_id": ""}),
        ("overlong event id", {"event_id": "e" * 200}),
        ("unknown source kind", {"source_kind": "bogus"}),
        ("unknown verdict", {"verdict": "bogus"}),
        ("negative diff count", {"diff_count": -1}),
        ("blank actor", {"actor": ""}),
        ("overlong actor", {"actor": "a" * 65}),
        ("malformed timestamp", {"reconciled_at": "not-date"}),
    ):
        try:
            ModeloReconciliationHistoryRowPayload.model_validate(base | override)
        except ValidationError:
            continue
        pytest.fail(f"{label} was accepted by the transport row")


def test_reconciliation_history_result_refuses_a_negative_count() -> None:
    """``reconciliation_count`` is a cardinality, so a negative value is not representable."""
    with pytest.raises(ValidationError):
        ModeloReconciliationHistoryResult(
            bucket_id="b" * 64,
            reconciliation_count=-1,
            reconciliations=[],
        )
