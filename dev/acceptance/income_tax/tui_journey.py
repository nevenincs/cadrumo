"""Assemble truthful installed income-tax journey receipts from observed cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .authority import IncomeTaxAuthorityResolution
from .scenario import BRIEF_ID, BRIEF_REVISION, SCENARIO_VERSION, AcceptanceOutcome
from .tui_contracts import (
    AcceptanceCaseEvidence,
    ContinuationEvidence,
    InstalledTuiContract,
    LifecycleEvidence,
    LocalXsdValidationEvidence,
    TuiJourneyError,
    TuiJourneyEvidence,
)

if TYPE_CHECKING:
    pass


def _assert_journey_case_population(cases: tuple[AcceptanceCaseEvidence, ...]) -> None:
    """Journey case population."""
    expected_ids = {f"A{number}" for number in range(1, 11)}
    actual_ids = {case.acceptance_id for case in cases}
    if len(cases) != len(actual_ids) or actual_ids != expected_ids:
        raise TuiJourneyError("installed TUI receipt must contain every A1-A10 case exactly once")
    if any(case.lifecycle.submission is not AcceptanceOutcome.NOT_EXERCISED for case in cases):
        raise TuiJourneyError("income acceptance has no authorized AEAT submission outcome")


def _assert_export_case_readiness(
    cases: tuple[AcceptanceCaseEvidence, ...], xsd_validation: LocalXsdValidationEvidence | None
) -> None:
    """Export case readiness."""
    a9 = next(case for case in cases if case.acceptance_id == "A9")
    if a9.outcome is AcceptanceOutcome.PROVEN and (xsd_validation is None or not xsd_validation.xsd_valid):
        raise TuiJourneyError("a proven export case requires a successful local Modelo 100 XSD validation")


def _assert_journey_continuation(
    frontend_path: Literal["tui", "cli_to_tui", "tui_to_cli"],
    continuation: ContinuationEvidence | None,
    cases: tuple[AcceptanceCaseEvidence, ...],
) -> None:
    """Journey continuation."""
    if frontend_path == "tui":
        if continuation is not None:
            raise TuiJourneyError("a TUI-only journey cannot carry continuation evidence")
    elif continuation is not None and continuation.frontend_path != frontend_path:
        raise TuiJourneyError("continuation evidence frontend path does not match its receipt")
    elif next(case for case in cases if case.acceptance_id == "A8").outcome is AcceptanceOutcome.PROVEN:
        raise TuiJourneyError("a proven continuation case requires a persisted-state continuation receipt")


def build_tui_journey_evidence(
    *,
    contract: InstalledTuiContract,
    resolution: IncomeTaxAuthorityResolution,
    frontend_path: Literal["tui", "cli_to_tui", "tui_to_cli"],
    source_state: str,
    cases: tuple[AcceptanceCaseEvidence, ...],
    xsd_validation: LocalXsdValidationEvidence | None = None,
    continuation: ContinuationEvidence | None = None,
) -> TuiJourneyEvidence:
    """Assemble a truthful final receipt from real installed-driver evidence.

    This validates receipt integrity.  It does not turn failed or blocked case
    evidence into a passing campaign; the driver still reports each public
    action's actual outcome.
    """
    missing = contract.missing_controls()
    if missing:
        raise TuiJourneyError(f"cannot assemble an installed TUI receipt with missing controls: {', '.join(missing)}")
    year, m130_revisions, m100_revision = _required_coordinate(resolution)
    if not isinstance(source_state, str) or not source_state:
        raise TuiJourneyError("installed TUI receipt needs a non-empty source-state identity")
    _assert_journey_case_population(cases)
    _assert_export_case_readiness(cases, xsd_validation)
    _assert_journey_continuation(frontend_path, continuation, cases)
    return TuiJourneyEvidence(
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=f"{SCENARIO_VERSION}:{year}:{frontend_path}",
        frontend_path=frontend_path,
        year=year,
        authority_generation=resolution.authority_generation,
        modelo_130_revisions=m130_revisions,
        modelo_100_revision=m100_revision,
        source_state=source_state,
        contract_missing_controls=(),
        cases=cases,
        xsd_validation=xsd_validation,
        continuation=continuation,
    )


def blocked_tui_journey_evidence(
    *,
    contract: InstalledTuiContract,
    resolution: IncomeTaxAuthorityResolution,
    frontend_path: Literal["tui", "cli_to_tui", "tui_to_cli"],
) -> TuiJourneyEvidence:
    """Build a truthful receipt when installed controls are incomplete.

    This is a capability report, not a passing journey.  It preserves the
    existing CLI proof by leaving controls owned by that completed evidence as
    ``not_exercised`` in this TUI receipt.
    """
    year, m130_revisions, m100_revision = _required_coordinate(resolution)
    missing = contract.missing_controls()
    lifecycle = LifecycleEvidence(
        calculation=AcceptanceOutcome.BLOCKED,
        verification=AcceptanceOutcome.BLOCKED,
        export_readiness=AcceptanceOutcome.BLOCKED,
        export_execution=AcceptanceOutcome.BLOCKED,
        local_filing=AcceptanceOutcome.BLOCKED,
        # This campaign has no AEAT submission authority even after the TUI
        # controls exist.
        submission=AcceptanceOutcome.NOT_EXERCISED,
    )
    blocked_cases = {
        "A1",
        "A3",
        "A6",
        "A7",
        "A9",
        "A10",
    }
    if frontend_path in {"cli_to_tui", "tui_to_cli"}:
        blocked_cases.add("A8")
    cases = tuple(
        AcceptanceCaseEvidence(
            acceptance_id=f"A{number}",
            outcome=AcceptanceOutcome.BLOCKED if f"A{number}" in blocked_cases else AcceptanceOutcome.NOT_EXERCISED,
            lifecycle=lifecycle
            if f"A{number}" in blocked_cases
            else LifecycleEvidence(
                calculation=AcceptanceOutcome.NOT_EXERCISED,
                verification=AcceptanceOutcome.NOT_EXERCISED,
                export_readiness=AcceptanceOutcome.NOT_EXERCISED,
                export_execution=AcceptanceOutcome.NOT_EXERCISED,
                local_filing=AcceptanceOutcome.NOT_EXERCISED,
                submission=AcceptanceOutcome.NOT_EXERCISED,
            ),
            source_state="installed_tui_contract_unavailable"
            if f"A{number}" in blocked_cases
            else "not_exercised_by_tui_driver",
            diagnostic_code="acceptance.installed_tui.contract_unavailable" if f"A{number}" in blocked_cases else None,
        )
        for number in range(1, 11)
    )
    return TuiJourneyEvidence(
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=f"{SCENARIO_VERSION}:{year}:{frontend_path}",
        frontend_path=frontend_path,
        year=year,
        authority_generation=resolution.authority_generation,
        modelo_130_revisions=m130_revisions,
        modelo_100_revision=m100_revision,
        source_state="installed_tui_contract_unavailable",
        contract_missing_controls=missing,
        cases=cases,
    )


def write_tui_journey_receipt(*, evidence: TuiJourneyEvidence, path: Path) -> None:
    """Persist one sanitized receipt after its caller owns the output path."""
    rendered = json.dumps(evidence.to_dict(), indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{rendered}\n", encoding="utf-8", newline="\n")


def _required_coordinate(resolution: IncomeTaxAuthorityResolution) -> tuple[int, tuple[str, ...], str]:
    """Return the pinned coordinate or refuse to manufacture one for a receipt."""
    if resolution.selected_year is None or resolution.modelo_100 is None or not resolution.modelo_130:
        raise TuiJourneyError("income acceptance requires a selected M130/M100 authority coordinate")
    return (
        resolution.selected_year,
        tuple(item.revision for item in resolution.modelo_130),
        resolution.modelo_100.revision,
    )
