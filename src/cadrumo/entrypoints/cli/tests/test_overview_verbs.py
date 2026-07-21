"""CLI surface tests for ``aeat app overview`` + retired-noun negatives.

Closes two overview verb coverage gaps in one file:

- Add CLI surface tests for every overview verb per
  the adjudicated grammar (status / calendar / agenda / backlog /
  explain). Each verb is exercised against an isolated profile so the
  mount + help path + empty-bucket envelope all reach the operator.

- Add negative tests asserting `cadrumo deadlines` and
  related retired noun-groups are unknown commands. The verb tree
  retired the standalone `deadlines` noun-group in favour of mounting
  deadline-shaped surfaces under `aeat app overview`. Operators
  reaching for `cadrumo deadlines ...` must see Click's "No such command"
  refusal, not a silent fallthrough.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core import Period
from ....domain.calculations.registry import CasillaId, RegistrySnapshotRef, validated_casilla_id
from ....domain.filing import (
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
)
from ....domain.submission import ModeloDraftStatus
from ....tests.cli_runner import invoke_cached_cli
from ....tests.filing import build_registry_filing_draft
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

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
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="11111111-1111-4111-8111-111111111111")
        )
        yield


# ---------------------------------------------------------------------------
# contract — overview verb surface tests
# ---------------------------------------------------------------------------


_OVERVIEW_VERBS = ("status", "calendar", "agenda", "backlog", "explain")
_RETIRED_DEADLINES_VERBS = (
    ["deadlines"],
    ["deadlines", "list"],
    ["deadlines", "status"],
    ["deadlines", "show"],
    ["app", "deadlines"],
    ["app", "deadlines", "list"],
)


def test_overview_verb_help_renders() -> None:
    """Every `aeat app overview <verb> --help` renders cleanly; each
    verb is mounted and its help-text translation key resolves to a
    non-empty default."""
    violations: list[str] = []
    for verb in _OVERVIEW_VERBS:
        result = invoke_cached_cli(["app", "overview", verb, "--help"])
        if result.exit_code != 0:
            violations.append(f"{verb}: exit {result.exit_code}: {result.output!r}")
            continue
        if "Usage:" not in result.output and "Uso:" not in result.output:
            violations.append(f"{verb}: help did not render usage: {result.output!r}")

    assert not violations, "\n".join(violations)


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
    assert "2026 1P" in result.output
    assert p1_draft.draft_id in result.output
    assert q1_draft.draft_id not in result.output


def test_overview_status_period_display_matches_typed_period_in_text_and_json() -> None:
    """The real overview CLI renders one canonical typed-period display in both formats."""

    period = Period.from_year_and_code(2026, "1T")
    draft = _minimal_stored_draft(
        modelo="130",
        period=period,
        casilla_id=_M130_INGRESOS_CASILLA,
        amount=Decimal("1000.00"),
    )
    ModeloDraftRepository().save(draft)

    text_result = invoke_cached_cli(["app", "overview", "status", "--period", "1T", "--year", "2026"])
    json_result = invoke_cached_cli(
        ["--format", "json", "app", "overview", "status", "--period", "1T", "--year", "2026"],
    )

    assert text_result.exit_code == 0, text_result.output
    assert json_result.exit_code == 0, json_result.output
    assert str(period) in text_result.output
    assert "1T 2026" not in text_result.output
    assert draft.draft_id in text_result.output
    assert json.loads(json_result.output)["result"]["period"] == str(period)


# ---------------------------------------------------------------------------
# contract — retired-noun-group negatives
# ---------------------------------------------------------------------------


def test_retired_deadlines_noun_group_is_unknown() -> None:
    """Reaching for `cadrumo deadlines ...` (or `aeat app deadlines ...`)
    must surface Click's "No such command" refusal. The verb tree
    retired the standalone deadlines noun-group; its surfaces live
    under `aeat app overview` (calendar, agenda, backlog)."""
    violations: list[str] = []
    for retired_verb in _RETIRED_DEADLINES_VERBS:
        result = invoke_cached_cli(retired_verb)
        if result.exit_code == 0:
            violations.append(f"{retired_verb!r}: unexpectedly exited 0: {result.output!r}")
            continue
        haystack = result.output.lower()
        if "no such command" not in haystack and "no such" not in haystack:
            violations.append(f"{retired_verb!r}: did not surface unknown-command refusal: {result.output!r}")

    assert not violations, "\n".join(violations)


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
    snapshot_ref = _snapshot_ref(modelo=modelo, period=period, schema_version=schema_version)
    draft_id = compute_modelo_draft_id(
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        values=values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        subject_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.BORRADOR,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=schema_version,
    )
