"""Replay a persona's return history through the CLI: carried balances, own copies, withholding, returns."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
from typing import Any

from pydantic import ValidationError

from cadrumo.entrypoints.tests.persona_materialisation import (
    PersonaMaterialisationError,
    WithholdingCapture,
    history_periods,
    professional_fee_payments,
    professional_withholding_capture,
    rent_payments,
    rent_withholding_capture,
)
from cadrumo.tests.personas import (
    FiledReturns,
    LeasedPremises,
    LedgerRow,
)

from . import commands
from .journey import (
    ACTOR,
    MESSAGE_LIMIT,
    Journey,
    Reply,
    found,
    found_text,
)

# -- history ---------------------------------------------------------------------------------------------------------


def _capture_ids(journey: Journey, step: str, row: LedgerRow) -> tuple[str, str] | None:
    invoice_id = journey.invoices.get(row.ref)
    transaction_id = journey.transactions.get(row.ref)
    if invoice_id is None or transaction_id is None:
        journey.skip(step, f"the row's invoice or transaction is missing for {row.ref}")
        return None
    return invoice_id, transaction_id


def _submit_capture(journey: Journey, step: str, build: Callable[[], WithholdingCapture]) -> None:
    try:
        capture = build()
    except (PersonaMaterialisationError, ValidationError) as error:
        journey.skip(step, f"the capture evidence could not be built: {str(error)[:MESSAGE_LIMIT]}")
        return
    journey.run(step, commands.withholding_capture_arguments(capture))


def _capture_rent(journey: Journey, premises: LeasedPremises, row: LedgerRow) -> None:
    step = f"withholding.rent.{row.ref}"
    ids = _capture_ids(journey, step, row)
    if ids is None:
        return
    _submit_capture(
        journey,
        step,
        partial(
            rent_withholding_capture,
            journey.persona,
            premises,
            row,
            envelope=journey.envelope,
            operation=journey.operation,
            invoice_id=ids[0],
            payment_event_id=ids[1],
        ),
    )


def _capture_professional(journey: Journey, row: LedgerRow) -> None:
    step = f"withholding.professional.{row.ref}"
    ids = _capture_ids(journey, step, row)
    if ids is None:
        return
    _submit_capture(
        journey,
        step,
        partial(
            professional_withholding_capture,
            journey.persona,
            row,
            envelope=journey.envelope,
            operation=journey.operation,
            invoice_id=ids[0],
            payment_event_id=ids[1],
        ),
    )


def capture_withholding(journey: Journey) -> None:
    """Capture the retención the taxpayer withheld on rent and professional fees, as Modelo 115 and 111 evidence."""
    persona = journey.persona
    for premises in persona.leased_premises:
        for row in rent_payments(persona, premises):
            _capture_rent(journey, premises, row)
    for row in professional_fee_payments(persona):
        _capture_professional(journey, row)


def seed_history(journey: Journey) -> None:
    """Seed each filed Modelo 303 block's carried compensation and record the taxpayer's own copies."""
    for filed in journey.persona.filed_returns:
        args = commands.wallet_seed_arguments(filed, journey.envelope)
        if args is not None:
            journey.run(f"history.wallet.{filed.modelo}.{filed.year.resolve(journey.envelope)}", args)
    for observation in journey.persona.local_observations:
        year = observation.year.resolve(journey.envelope)
        step = f"history.observe_local.{observation.modelo}.{year}.{observation.period}"
        journey.run(step, commands.local_observation_arguments(observation, journey.envelope, ACTOR))


def _attestation(
    journey: Journey, step: str, *, modelo: str, year: int, period: str, last: str
) -> tuple[str, str] | None:
    """The Modelo 390 attestation a year's closing Modelo 303 period calculates with; ``None`` for any other."""
    if modelo != "303" or period != "4T" or period != last:
        return None
    attested = journey.run(f"{step}.attest_390", commands.attestation_arguments(year, period, ACTOR))
    attachment_id = found_text(attested.result, "attachment_id")
    sha256 = found_text(attested.result, "sha256")
    return None if attachment_id is None or sha256 is None else (attachment_id, sha256)


def _rows(result: Mapping[str, Any], key: str) -> list[object]:
    rows = found(result, key)
    return [*rows] if isinstance(rows, list) else []


def _unresolved(result: Mapping[str, Any]) -> str:
    names = [str(found(row, "binding_id")) for row in _rows(result, "unresolved_bindings")]
    names += [f"{found(row, 'casilla_id')} ({found(row, 'reason')})" for row in _rows(result, "unresolved_casillas")]
    return ", ".join(names)


def calculate_return(
    journey: Journey, step: str, *, modelo: str, year: int, period: str, last: str
) -> tuple[Reply, str | None]:
    """Create and calculate one return; the reply that settled it and its revision id, if one was minted."""
    created = journey.run(f"{step}.create", commands.work_create_arguments(modelo, year, period, ACTOR))
    work_unit_id = found_text(created.result, "work_unit_id")
    if work_unit_id is None:
        return created, None
    attestation = _attestation(journey, step, modelo=modelo, year=year, period=period, last=last)
    args = commands.calculate_arguments(work_unit_id, modelo=modelo, attestation=attestation, actor=ACTOR)
    calculated = journey.run(f"{step}.calculate", args)
    unresolved = _unresolved(calculated.result)
    if unresolved:
        journey.note(f"{step}: the calculation left without a value: {unresolved}")
    return calculated, found_text(calculated.result, "calculation_revision_id")


def _finding_names(result: Mapping[str, Any]) -> str:
    return "; ".join(
        f"{found(item, 'kind')}/{found(item, 'severity')} "
        f"{found(item, 'casilla_id') or found(item, 'expectation_id')} {found(item, 'message_locale_key')}"
        for item in _rows(result, "findings")
    )


def _file_return(journey: Journey, step: str, revision_id: str) -> None:
    verified = journey.run(f"{step}.verify", ("app", "modelo", "work", "verify", revision_id, "--by", ACTOR))
    if not verified.ok:
        return
    if found(verified.result, "granted_verificado_completo") is not True:
        findings = _finding_names(verified.result)
        journey.skip(f"{step}.file", f"verification did not complete: {findings[: MESSAGE_LIMIT * 2]}")
        return
    journey.run(f"{step}.file", ("app", "modelo", "work", "file", revision_id, "--by", ACTOR))


def replay_returns(journey: Journey) -> None:
    """Calculate each filed and calculated return in the order its window closes; file the filed ones locally."""
    for year, period, block in history_periods(journey.persona, journey.envelope):
        step = f"history.{block.modelo}.{year}.{period}"
        _, revision_id = calculate_return(
            journey, step, modelo=block.modelo, year=year, period=period, last=block.periods[-1]
        )
        if revision_id is None:
            continue
        journey.revisions[block.modelo, year, period] = revision_id
        if isinstance(block, FiledReturns):
            _file_return(journey, step, revision_id)


def replay_history(journey: Journey) -> None:
    """Replay the persona's return history after its setup, as the in-process replay does."""
    persona = journey.persona
    if not (persona.filed_returns or persona.calculated_returns or persona.local_observations):
        return
    if not journey.setup_complete:
        journey.note("history: the setup did not complete, so the returns are replayed against an incomplete profile")
    seed_history(journey)
    capture_withholding(journey)
    replay_returns(journey)
