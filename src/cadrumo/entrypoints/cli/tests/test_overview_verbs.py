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
import time
from datetime import UTC, datetime
from decimal import Decimal

import click
import pytest
from click.testing import CliRunner
from dev.ci.perf_measurement import CPU_CONTENTION_MARGIN

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....application.operator_actions import ActionReference
from ....core import CasillaId, Period, validated_casilla_id
from ....core.json_contract import ResolvedNoticeAction
from ....domain.calculations.registry import RegistrySnapshotRef
from ....domain.filing import (
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)
from ....domain.submission import ModeloDraftStatus
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_runner import invoke_cached_cli
from ....tests.filing import build_registry_filing_draft
from .._common import resolve_notice_action

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("overview_cli_backend"),
]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M202_CUOTA_CASILLA: CasillaId = validated_casilla_id("03", surface="_M202_CUOTA_CASILLA")


def _snapshot_ref(*, modelo: str, period: Period, revision_id: str) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(
        modelo=modelo,
        revision_id=revision_id,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )


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


def test_overview_status_actions_match_fresh_resolution_in_one_bounded_invocation() -> None:
    """One real overview invocation shares its inventory without changing actions.

    A sibling test separately proves the one-inventory-per-root lifecycle. This test uses
    the first full invocation as its live baseline and holds the next equivalent
    invocation to the canonical CPU-contention margin. Wall time is reported
    separately for operator diagnostics but deliberately does not decide this
    CPU-bound contract.
    """
    baseline_cpu_started = time.process_time()
    baseline_wall_started = time.perf_counter()
    baseline = invoke_cached_cli(["--format", "json", "app", "overview", "status"])
    baseline_cpu_seconds = time.process_time() - baseline_cpu_started
    baseline_wall_seconds = time.perf_counter() - baseline_wall_started

    candidate_cpu_started = time.process_time()
    candidate_wall_started = time.perf_counter()
    overview = invoke_cached_cli(["--format", "json", "app", "overview", "status"])
    candidate_cpu_seconds = time.process_time() - candidate_cpu_started
    candidate_wall_seconds = time.perf_counter() - candidate_wall_started

    assert baseline.exit_code == 0, baseline.output
    assert overview.exit_code == 0, overview.output
    assert json.loads(baseline.output) == json.loads(overview.output)
    timing = (
        f"baseline_cpu={baseline_cpu_seconds:.3f}s baseline_wall={baseline_wall_seconds:.3f}s "
        f"candidate_cpu={candidate_cpu_seconds:.3f}s candidate_wall={candidate_wall_seconds:.3f}s"
    )
    assert candidate_cpu_seconds <= baseline_cpu_seconds * CPU_CONTENTION_MARGIN, timing
    assert candidate_wall_seconds > 0, timing

    actions = tuple(
        ResolvedNoticeAction.model_validate_json(json.dumps(notice["action"]))
        for notice in unwrap_envelope_notices(overview.output)
        if notice.get("action") is not None
    )
    assert len(actions) >= 2, "the deterministic overview must exercise multiple action-bearing notices"

    fresh: list[ResolvedNoticeAction] = []

    @click.command()
    def fresh_resolution_root() -> None:
        """Resolve the captured actions through one separate real Click root."""
        fresh.extend(
            resolve_notice_action(
                action=ActionReference(action_id=action.action.action_id),
                argument_bindings=action.argument_bindings,
            )
            for action in actions
        )

    fresh_result = CliRunner().invoke(fresh_resolution_root)
    assert fresh_result.exit_code == 0, fresh_result.output
    print(f"overview timing: {timing}")
    fresh_actions = tuple(fresh)
    assert actions == fresh_actions
    assert tuple(action.model_dump_json() for action in actions) == tuple(
        action.model_dump_json() for action in fresh_actions
    )


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
    revision_id = "overview-period-filter-test"
    schema_version = registry_schema_version(modelo=modelo, revision_id=revision_id)
    snapshot_ref = _snapshot_ref(modelo=modelo, period=period, revision_id=revision_id)
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
