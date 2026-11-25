"""Replay the returns a persona already holds: local observations, AEAT filings and attested returns."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from pydantic import BaseModel

from ...application.live.filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledSingleCapturePublicResultV1,
    FiledSingleCaptureRequest,
)
from ...application.modelo.iva_wallet_override_operation import (
    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletOverrideRequest,
)
from ...application.modelo.iva_wallet_seed_operation import (
    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
    ModeloIvaWalletSeedRequest,
)
from ...application.modelo.local_observation_contracts import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationCasillaValue,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationRequest,
)
from ...application.modelo.m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.operation_shared import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest
from ...application.operations.public_period import PublicPeriod
from ...tests.persona_expectations import values_in_force
from ...tests.persona_sections import filed_period_order
from ...tests.persona_types import CalculatedReturns, FiledReturns, Persona, YearEnvelope
from .persona_aeat_filings import PERSONA_AEAT_REGISTER, recorded_filing
from .persona_operations import enter_return_work_inputs, run_operation, settle_operation
from .persona_prior_values import PriorValueAttestationError, attest_return_prior_values
from .persona_replay_requests import _decimal_text
from .persona_withholding_capture import _capture_professional_withholding, _capture_rent_withholding
from .persona_world import PERSONA_ACTOR, PersonaMaterialisationError, PersonaWorld


def filing_key(modelo: str, year: int, period: str) -> str:
    """The key :attr:`MaterialisedPersona.filings` and :attr:`MaterialisedPersona.calculations` name one return by."""
    return f"{modelo}:{year}:{period}"


def history_periods(
    persona: Persona, envelope: YearEnvelope
) -> list[tuple[int, str, FiledReturns | CalculatedReturns]]:
    """Every filed and calculated return of the persona, in the order the windows of their periods close."""
    blocks: tuple[FiledReturns | CalculatedReturns, ...] = (*persona.filed_returns, *persona.calculated_returns)
    found = [(block.year.resolve(envelope), period, block) for block in blocks for period in block.periods]
    return sorted(found, key=lambda item: (item[0], filed_period_order(item[1])))


def preceding_quarter(year: int, period: str) -> PublicPeriod:
    """The quarter before ``period``, whose compensation balance a Modelo 303 period starts from."""
    quarter = int(period[0])
    if quarter == 1:
        return PublicPeriod(filing_year=year - 1, code="4T")
    return PublicPeriod(filing_year=year, code=f"{quarter - 1}T")


def _m303_evidence(
    world: PersonaWorld, *, work_unit_id: str, year: int, period: str, last_period: str
) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    """The ordinary Modelo 303 filing facts: no joint return, and the Modelo 390 attestation in the year's last period."""
    if period != "4T" or period != last_period:
        return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=False)
    attestation = ModeloWorkM303AttestationRequest(
        profile_id=world.profile_id,
        work_unit_id=work_unit_id,
        observed_at=datetime(year, 12, 31, 12, tzinfo=UTC),
        actor=PERSONA_ACTOR,
    )
    attested = run_operation(
        world,
        MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        attestation,
        ModeloWorkM303AttestationPublicResultV2,
        subject=attestation.subject_ref,
    )
    return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id=attested.attachment_id,
        m303_exonerado_390_sha256=attested.sha256,
    )


def _seed_compensation_carried_in(persona: Persona, world: PersonaWorld) -> None:
    """Declare the Modelo 303 compensation balance each filed block starts from, where the persona states one.

    A balance carried into the first supported quarter comes from a quarter below the registry's support floor,
    which has no Modelo 303 edition to seed; it is stated as the taxpayer's override on the consuming period.
    """
    for filed in persona.filed_returns:
        if filed.iva_compensation_carried_in is None:
            continue
        year = filed.year.resolve(world.envelope)
        amount = _decimal_text(filed.iva_compensation_carried_in.normalize())
        preceding = preceding_quarter(year, filed.periods[0])
        if preceding.filing_year >= world.envelope.floor:
            settle_operation(
                world,
                MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
                ModeloIvaWalletSeedRequest(profile_id=world.profile_id, period=preceding, amount=amount),
            )
            continue
        settle_operation(
            world,
            MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
            ModeloIvaWalletOverrideRequest(
                profile_id=world.profile_id,
                period=PublicPeriod(filing_year=year, code=filed.periods[0]),
                amount=amount,
                reason="Compensation balance carried in from before the first supported period, as the taxpayer states it",
                evidence_locator=f"synthetic:persona:{persona.id}:iva-compensation-carried-in",
            ),
        )


def _record_local_observations(persona: Persona, world: PersonaWorld) -> None:
    """Record the casilla values of each return the taxpayer knows from his own copy, as a local observation."""
    for observation in persona.local_observations:
        run_operation(
            world,
            MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
            ModeloLocalObservationMutationRequest(
                profile_id=world.profile_id,
                action="record",
                modelo=observation.modelo,
                period=PublicPeriod(filing_year=observation.year.resolve(world.envelope), code=observation.period),
                casilla_values=tuple(
                    ModeloLocalObservationCasillaValue(casilla_id=casilla, value=value)
                    for casilla, value in observation.casillas
                ),
                actor=PERSONA_ACTOR,
                reason=observation.reason,
            ),
            ModeloLocalObservationMutationProjection,
        )


def _finding_names(verified: ModeloWorkVerifyPublicResultV2) -> str:
    """The verification findings by kind, severity, casilla and message key, named for a refusal message."""
    return ", ".join(
        f"{finding.kind}/{finding.severity} {finding.casilla_id or finding.expectation_id or '-'} "
        f"{finding.message_locale_key}"
        for finding in verified.verification.report.findings
    )


def _unresolved(calculated: ModeloWorkCalculatePublicResultV3) -> str:
    """The bindings and boxes a calculation left without a value, named for a refusal message; empty when none."""
    names = [f"binding {row.binding_id}" for row in calculated.unresolved_bindings]
    names += [f"casilla {row.casilla_id} ({row.reason})" for row in calculated.unresolved_casillas]
    return ", ".join(names)


def _capture_aeat_filings(persona: Persona, world: PersonaWorld) -> None:
    """Capture each return the taxpayer filed with the AEAT through the registered filed capture.

    The capture reads the persona's filings from the recorded AEAT register
    and admits each through the production receipt checks. A filing whose
    justificante those checks do not take as the return's verified receipt is
    refused with the capture's own notices.
    """
    recorded = tuple(
        recorded_filing(persona, filing, envelope=world.envelope, operation=world.operation)
        for filing in persona.aeat_filings
    )
    with PERSONA_AEAT_REGISTER.serving(world.profile_id, recorded):
        for filing, held in zip(persona.aeat_filings, recorded, strict=True):
            declaration = held.declaration
            where = f"{persona.id} AEAT filing of Modelo {filing.modelo} {declaration.ejercicio} {filing.period}"
            try:
                captured = run_operation(
                    world,
                    FILED_SINGLE_CAPTURE_DEFINITION_ID,
                    FiledSingleCaptureRequest(
                        profile_id=world.profile_id,
                        output_root=world.workdir / "aeat-filed-capture",
                        modelo=filing.modelo,
                        year=declaration.ejercicio,
                        period=filing.period,
                        expediente_id=declaration.expediente_id,
                        limit=1,
                    ),
                    FiledSingleCapturePublicResultV1,
                )
            except PersonaMaterialisationError as error:
                raise PersonaMaterialisationError(f"{where}: {error}") from error
            if (
                captured.captured_count != 1
                or captured.justificante_csvs != (filing.csv,)
                or captured.filing_evidence_stamped_count != 1
                or captured.calculation_observation_count != 1
            ):
                raise PersonaMaterialisationError(
                    f"{where}: the capture did not admit its justificante: {captured.model_dump_json()}"
                )


def _replay_records(
    persona: Persona, world: PersonaWorld, *, transactions: Mapping[str, str], invoices: Mapping[str, str]
) -> None:
    """Record what the persona's returns read: observations, compensation carried in, withholding and AEAT filings."""
    _seed_compensation_carried_in(persona, world)
    _record_local_observations(persona, world)
    _capture_rent_withholding(persona, world, transactions=transactions, invoices=invoices)
    _capture_professional_withholding(persona, world, transactions=transactions, invoices=invoices)
    _capture_aeat_filings(persona, world)


def _replay_history(persona: Persona, world: PersonaWorld) -> tuple[dict[str, str], dict[str, str]]:
    """Replay the persona's returns; returns the filed and the calculated returns, key to revision id.

    The records of :func:`_replay_records` come first. Then each
    filed return is created, calculated, verified and filed locally, and each
    calculated return created and calculated, in the order their windows close.
    Each figure comes from the persona's replayed ledger, profile and recorded
    observations, and from the values the persona's operator enters on it
    (``work_inputs``), entered through the declaration edit before its first
    calculation; nothing else is entered at calculation. A filed return that
    cannot verify or file from that data is refused with the operation's own
    reason, never overridden. Local filing records a PRESENTADO revision whose
    AEAT status stays pending; no receipt is made.
    """
    filings: dict[str, str] = {}
    calculations: dict[str, str] = {}
    for year, period, filed in history_periods(persona, world.envelope):
        where = f"{persona.id} Modelo {filed.modelo} {year} {period}"
        created = settle_operation(
            world,
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            ModeloWorkCreateRequest(
                profile_id=world.profile_id,
                modelo=filed.modelo,
                period=PublicPeriod(filing_year=year, code=period),
                actor=PERSONA_ACTOR,
            ),
        )
        outcome = getattr(created, "outcome", None)
        if not isinstance(outcome, ModeloWorkCreateSuccess):
            raise PersonaMaterialisationError(f"{where}: work creation refused: {outcome}")
        work_unit_id = outcome.unit.work_unit_id
        evidence = (
            _m303_evidence(world, work_unit_id=work_unit_id, year=year, period=period, last_period=filed.periods[-1])
            if filed.modelo == "303"
            else None
        )
        try:
            calculated = run_operation(
                world,
                MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                ModeloWorkCalculateRequest(
                    work_unit_id=work_unit_id, actor=PERSONA_ACTOR, ordinary_m303_filing_evidence=evidence
                ),
                ModeloWorkCalculatePublicResultV3,
                subject=work_unit_id,
            )
        except PersonaMaterialisationError as error:
            raise PersonaMaterialisationError(f"{where}: {error}") from error
        revision_id = calculated.calculation_revision_id
        unresolved = _unresolved(calculated)
        if isinstance(filed, CalculatedReturns):
            if unresolved:
                raise PersonaMaterialisationError(f"{where}: the calculation left {unresolved} without a value")
            calculations[filing_key(filed.modelo, year, period)] = revision_id
            continue
        verified = run_operation(
            world,
            MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=PERSONA_ACTOR),
            ModeloWorkVerifyPublicResultV2,
            subject=work_unit_id,
        )
        if not verified.granted_verificado_completo:
            raise PersonaMaterialisationError(
                f"{where}: verification did not complete ({verified.completeness_status}, "
                f"{verified.finding_count} findings, "
                f"{verified.missing_required_casilla_count} required casillas missing; unresolved: {unresolved or 'none'}; "
                f"findings: {_finding_names(verified)})"
            )
        run_operation(
            world,
            MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
            ModeloWorkFileRequest(
                approval=ModeloWorkFileApproval(
                    calculation_revision_id=revision_id,
                    verification_report_id=verified.verification_report_id,
                ),
                actor=PERSONA_ACTOR,
            ),
            ModeloWorkFilePublicResultV2,
            subject=work_unit_id,
        )
        filings[filing_key(filed.modelo, year, period)] = revision_id
    return filings, calculations


def attested_returns_to_replay(persona: Persona, envelope: YearEnvelope) -> tuple[tuple[str, int, str], ...]:
    """Each ``(modelo, year, period)`` the persona attests a prior value on that nothing else calculates.

    A return of the history is calculated by the history replay, and a return a
    stated value names is calculated where that value is assessed; each attests
    its prior values after that calculation. Any other attested return would
    never be calculated, so its attestation is replayed on its own.
    """
    calculated = {(block.modelo, year, period) for year, period, block in history_periods(persona, envelope)}
    calculated |= {
        (value.modelo, year, value.period) for year, value in values_in_force(persona.expectations.values, envelope)
    }
    attested = {(item.modelo, item.year.resolve(envelope), item.period) for item in persona.attested_prior_values}
    return tuple(sorted(attested - calculated, key=lambda item: (item[1], item[0], item[2])))


def _replay_attested_returns(persona: Persona, world: PersonaWorld) -> dict[str, str]:
    """Create and attest each return of :func:`attested_returns_to_replay`; returns key to calculated revision id.

    The attestation is submitted before any calculation, as a calculating edit:
    such a return may refuse its calculation until the figure is stated. The
    values the persona enters on the return are entered first, as before any
    first calculation. A stated figure the application does not offer to
    attest refuses the replay; it is never skipped.
    """
    calculations: dict[str, str] = {}

    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        return settle_operation(world, definition_id, payload, subject=subject)

    for modelo, year, period in attested_returns_to_replay(persona, world.envelope):
        where = f"{persona.id} Modelo {modelo} {year} {period}"
        created = settle_operation(
            world,
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            ModeloWorkCreateRequest(
                profile_id=world.profile_id,
                modelo=modelo,
                period=PublicPeriod(filing_year=year, code=period),
                actor=PERSONA_ACTOR,
            ),
        )
        outcome = getattr(created, "outcome", None)
        if not isinstance(outcome, ModeloWorkCreateSuccess):
            raise PersonaMaterialisationError(f"{where}: work creation refused: {outcome}")
        work_unit_id = outcome.unit.work_unit_id
        try:
            if world.work_inputs:
                enter_return_work_inputs(world, work_unit_id)
            attested = attest_return_prior_values(
                world.attested_prior_values,
                envelope=world.envelope,
                profile_id=world.profile_id,
                work_unit_id=work_unit_id,
                modelo=modelo,
                filing_year=year,
                period=period,
                settle=settle,
            )
        except (PersonaMaterialisationError, PriorValueAttestationError) as error:
            raise PersonaMaterialisationError(f"{where}: {error}") from error
        if attested.unoffered:
            raise PersonaMaterialisationError(
                f"{where}: the application does not offer the attestation of {', '.join(attested.unoffered)}"
            )
        if attested.applied is None:
            raise PersonaMaterialisationError(f"{where}: the attestation was not applied")
        revision_id = attested.applied.calculation_revision_id
        if revision_id is None:
            raise PersonaMaterialisationError(f"{where}: the attesting edit published no calculation")
        calculations[filing_key(modelo, year, period)] = revision_id
    return calculations


__all__ = [
    "filing_key",
]
