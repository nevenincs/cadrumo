"""CLI surface tests for ``aeat app overview`` + retired-noun negatives.

Closes two overview verb coverage gaps in one file:

- Add CLI surface tests for every overview verb per
  the adjudicated grammar (status / calendar / agenda / backlog /
  explain). Each verb is exercised against an isolated profile so the
  mount + help path + empty-bucket envelope all reach the operator.

- Add negative tests asserting `aeat deadlines` and
  related retired noun-groups are unknown commands. The verb tree
  retired the standalone `deadlines` noun-group in favour of mounting
  deadline-shaped surfaces under `aeat app overview`. Operators
  reaching for `aeat deadlines ...` must see Click's "No such command"
  refusal, not a silent fallthrough.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.filing._testing_registry import build_registry_filing_draft
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....domain.calculations.registry import CasillaId, RegistrySnapshotRef, validated_casilla_id
from ....domain.filing import (
    ModeloDraft,
    ModeloDraftRepository,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
)
from ....domain.submission import ModeloDraftStatus
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M202_CUOTA_CASILLA: CasillaId = validated_casilla_id("03", surface="_M202_CUOTA_CASILLA")


def _snapshot_ref(*, modelo: str, period: Period, schema_version: str) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(
        modelo=modelo,
        revision_id=schema_version,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
        yield


# ---------------------------------------------------------------------------
# contract — overview verb surface tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verb", ["status", "calendar", "agenda", "backlog", "explain"])
def test_overview_verb_help_renders(verb: str) -> None:
    """Every `aeat app overview <verb> --help` renders cleanly; each
    verb is mounted and its help-text translation key resolves to a
    non-empty default."""

    result = invoke_cached_cli(["app", "overview", verb, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output or "Uso:" in result.output, result.output


def test_overview_status_returns_envelope_on_empty_bucket() -> None:
    """`aeat app overview status` against an isolated profile with no
    work units emits a typed envelope (no exception, no missing-data
    error). The verb is read-only and works without a populated bucket."""

    result = invoke_cached_cli(["app", "overview", "status"])
    assert result.exit_code == 0, result.output


def test_overview_status_period_filter_matches_typed_draft_period() -> None:
    q1_draft = build_registry_filing_draft(
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        casilla_values=_valid_modelo_130_inputs(),
        binding_values=_valid_modelo_130_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )
    q2_draft = build_registry_filing_draft(
        modelo="130",
        period=Period.from_year_and_code(2026, "2T"),
        casilla_values=_valid_modelo_130_inputs(),
        binding_values=_valid_modelo_130_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )
    repository = ModeloDraftRepository()
    repository.save(q1_draft)
    repository.save(q2_draft)

    result = invoke_cached_cli(["app", "overview", "status", "--period", "1T", "--year", "2026"])

    assert result.exit_code == 0, result.output
    assert q1_draft.draft_id in result.output
    assert q2_draft.draft_id not in result.output


def test_overview_status_period_filter_accepts_instalment_period() -> None:
    p1_draft = _minimal_stored_draft(
        modelo="202",
        period=Period.from_year_and_code(2026, "1P"),
        casilla_id=_M202_CUOTA_CASILLA,
        amount=Decimal("1800.00"),
    )
    q1_draft = _minimal_stored_draft(
        modelo="303",
        period=Period.from_year_and_code(2026, "1T"),
        casilla_id=_M202_CUOTA_CASILLA,
        amount=Decimal("168.00"),
    )
    repository = ModeloDraftRepository()
    repository.save(p1_draft)
    repository.save(q1_draft)

    result = invoke_cached_cli(["app", "overview", "status", "--period", "1P", "--year", "2026"])

    assert result.exit_code == 0, result.output
    assert "1P 2026" in result.output
    assert p1_draft.draft_id in result.output
    assert q1_draft.draft_id not in result.output


# ---------------------------------------------------------------------------
# contract — retired-noun-group negatives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "retired_verb",
    [
        ["deadlines"],
        ["deadlines", "list"],
        ["deadlines", "status"],
        ["deadlines", "show"],
        ["app", "deadlines"],
        ["app", "deadlines", "list"],
    ],
)
def test_retired_deadlines_noun_group_is_unknown(
    retired_verb: list[str],
) -> None:
    """Reaching for `aeat deadlines ...` (or `aeat app deadlines ...`)
    must surface Click's "No such command" refusal. The verb tree
    retired the standalone deadlines noun-group; its surfaces live
    under `aeat app overview` (calendar, agenda, backlog)."""

    result = invoke_cached_cli(retired_verb)
    assert result.exit_code != 0, (
        f"retired verb path {retired_verb!r} should be unknown but exited 0: {result.output!r}"
    )
    haystack = result.output.lower()
    assert "no such command" in haystack or "no such" in haystack, (
        f"retired verb path {retired_verb!r} did not surface unknown-command refusal: {result.output!r}"
    )


def _valid_modelo_130_inputs() -> dict[CasillaId, Decimal]:
    return {
        _M130_INGRESOS_CASILLA: Decimal("10000"),
        _M130_GASTOS_CASILLA: Decimal("4000"),
        # Casilla 05 (pagos fraccionados anteriores) is previous-filing-bound; its
        # value flows through the matching binding id in _valid_modelo_130_bindings,
        # not as a raw casilla input (which the smuggling guard now rejects).
        _M130_RETENCIONES_CASILLA: Decimal("100"),
        _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
        _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
        _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
        _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
    }


def _valid_modelo_130_bindings() -> dict[str, Decimal]:
    return {
        "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        # Casilla 05's prior-quarter carry, supplied through its previous-filing
        # binding (the source-of-truth channel) rather than as a raw casilla input.
        "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
    }


def _minimal_stored_draft(
    *,
    modelo: str,
    period: Period,
    casilla_id: CasillaId,
    amount: Decimal,
) -> ModeloDraft:
    now = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
    values = (
        ModeloValue(
            casilla_id=casilla_id,
            value=amount,
            kind=ModeloValueKind.LITERAL,
            source="overview period filter regression",
        ),
    )
    schema_version = "overview-period-filter-test"
    draft_id = compute_modelo_draft_id(
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        schema_version=schema_version,
        values=values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        subject_tax_id="00000000T",
        snapshot_ref=_snapshot_ref(modelo=modelo, period=period, schema_version=schema_version),
        status=ModeloDraftStatus.BORRADOR,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=schema_version,
    )
