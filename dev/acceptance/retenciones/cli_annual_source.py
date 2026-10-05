"""Annual source-period evidence and explicit public no-duty admission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from dev.acceptance.installed_cli import InstalledCli

from .cli_contracts import _ACTOR, AnnualSourcePeriodEvidence, RetencionesInstalledCliError
from .cli_export_validation import _expected_casillas_from_result
from .cli_observations import _require_result, _required_text
from .scenario import (
    AnnualSourcePeriodInput,
    EvidenceState,
    InstalledAnnualCliSlice,
    InstalledPeriodicCliSlice,
)


def _assert_source_period_coordinates(
    captures: tuple[InstalledPeriodicCliSlice, ...],
    source_modelo: str,
    source_revision: str,
    source_period: AnnualSourcePeriodInput,
    *,
    stage: str,
) -> None:
    """Source period coordinates."""
    if any(
        capture.modelo != source_modelo or capture.revision != source_revision or capture.period != source_period.period
        for capture in captures
    ):
        raise RetencionesInstalledCliError(
            stage=f"{stage}:preflight",
            diagnostic_code="annual_source_period_coordinate_mismatch",
        )


def _source_casilla_identity(captures: tuple[InstalledPeriodicCliSlice, ...], *, stage: str) -> tuple[str, ...]:
    """Source casilla identity."""
    expected_ids = tuple(casilla_id for casilla_id, _value in captures[0].expected_casillas)
    if any(
        tuple(casilla_id for casilla_id, _value in capture.expected_casillas) != expected_ids for capture in captures
    ):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_casilla_shape_mismatch")
    return expected_ids


def _attest_annual_no_activity_periods(
    *,
    cli: InstalledCli,
    slice_: InstalledAnnualCliSlice,
    captures_by_period: Mapping[str, Sequence[InstalledPeriodicCliSlice]],
    year: int,
) -> frozenset[str]:
    """Record the source modelo's explicit public no-activity facts.

    Modelo 111 retains its no-retenciones profile fact rather than creating a
    zero local filing.  Modelo 115's distinct no-relevant-payment fact instead
    authorises its local zero calculation and source filing.  Both are public
    operator evidence and neither invents a payment allocation.
    """
    option_by_modelo = {
        "111": "--modelo-111-no-retenciones-periods",
        "115": "--modelo-115-no-relevant-payment-periods",
    }
    option = option_by_modelo.get(slice_.source_modelo)
    if option is None:
        return frozenset[str]()
    tokens: list[str] = []
    for source_period in slice_.source_periods:
        captures = tuple(captures_by_period.get(source_period.period, ()))
        _assert_source_period_evidence(
            source_period=source_period,
            captures=captures,
            stage=f"{slice_.slice_id}:{slice_.source_modelo}_no_activity_preflight:{source_period.period}",
        )
        if not captures:
            tokens.append(f"{year}:{source_period.period}")
    if not tokens:
        return frozenset[str]()
    _require_result(
        cli,
        (
            "config",
            "profile",
            "edit",
            f"income-{year}",
            "--quiet",
            option,
            ",".join(tokens),
        ),
        stage=f"{slice_.slice_id}:{slice_.source_modelo}_no_activity_attestation",
    )
    return frozenset(tokens)


def _admit_annual_no_capture_source(
    source_modelo: str,
    source_period: AnnualSourcePeriodInput,
    year: int,
    no_activity_attestations: frozenset[str],
    *,
    stage: str,
) -> AnnualSourcePeriodEvidence | None:
    """Admit only the supported public no-duty workflow for an empty annual source."""
    attestation_period = f"{year}:{source_period.period}"
    if source_modelo == "111":
        if attestation_period not in no_activity_attestations:
            raise RetencionesInstalledCliError(
                stage=f"{stage}:preflight",
                diagnostic_code="annual_source_m111_no_retenciones_attestation_missing",
            )
        return AnnualSourcePeriodEvidence(
            modelo=source_modelo,
            period=source_period.period,
            evidence_state=source_period.evidence_state.value,
            source_workflow="m111_no_retenciones_attestation",
            work_unit_id=None,
            calculation_revision_id=None,
            calculated_casillas=None,
            verification_granted=False,
            filing_record_id=None,
            live_submission=False,
            attestation_period=attestation_period,
        )
    if source_modelo != "115":
        raise RetencionesInstalledCliError(
            stage=f"{stage}:preflight",
            diagnostic_code="annual_source_no_activity_workflow_unsupported",
        )
    if attestation_period not in no_activity_attestations:
        raise RetencionesInstalledCliError(
            stage=f"{stage}:preflight",
            diagnostic_code="annual_source_m115_no_relevant_payment_attestation_missing",
        )
    return None


def _materialize_annual_source_period(
    *,
    cli: InstalledCli,
    source_modelo: str,
    source_revision: str,
    source_period: AnnualSourcePeriodInput,
    captures: tuple[InstalledPeriodicCliSlice, ...],
    year: int,
    no_activity_attestations: frozenset[str],
) -> AnnualSourcePeriodEvidence:
    """Materialize a local source record or retain a supported no-duty state.

    ``work file`` is deliberately checked as an internal local record only. It
    is the canonical producer of the ``app_filing`` carry observation; it does
    not contact AEAT or establish external filing evidence.  A no-activity
    Modelo 111 period is represented instead by its profile attestation, with
    no work unit, calculation revision, or local filing record.  Modelo 115's
    public no-relevant-payment attestation authorises a local zero source
    record, which supplies the annual cross-period relation without claiming
    AEAT submission.
    """
    stage = f"{source_modelo}:{source_period.period}:annual_source"
    _assert_source_period_coordinates(captures, source_modelo, source_revision, source_period, stage=stage)
    _assert_source_period_evidence(
        source_period=source_period,
        captures=captures,
        stage=f"{stage}:preflight",
    )
    if not captures:
        no_capture_evidence = _admit_annual_no_capture_source(
            source_modelo, source_period, year, no_activity_attestations, stage=stage
        )
        if no_capture_evidence is not None:
            return no_capture_evidence
    work = _require_result(
        cli,
        (
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            source_modelo,
            "--year",
            str(year),
            "--period",
            source_period.period,
            "--revision",
            source_revision,
            "--by",
            _ACTOR,
        ),
        stage=f"{stage}:work_create",
    )
    work_id = _required_text(work, key="work_unit_id", stage=f"{stage}:work_create")
    calculation = _require_result(
        cli,
        ("app", "modelo", "work", "calculate", work_id, "--by", _ACTOR),
        stage=f"{stage}:work_calculate",
    )
    calculated_casillas = _expected_casillas_from_result(
        calculation,
        expected=source_period.expected_casillas,
        stage=f"{stage}:work_calculate",
    )
    revision_id = _required_text(
        calculation,
        key="calculation_revision_id",
        stage=f"{stage}:work_calculate",
    )
    verification = _require_result(
        cli,
        ("app", "modelo", "work", "verify", revision_id, "--by", _ACTOR),
        stage=f"{stage}:work_verify",
    )
    if verification.get("granted_verificado_completo") is not True:
        raise RetencionesInstalledCliError(
            stage=f"{stage}:work_verify",
            diagnostic_code="annual_source_verification_not_complete",
        )
    filing = _require_result(
        cli,
        ("app", "modelo", "work", "file", revision_id, "--by", _ACTOR),
        stage=f"{stage}:work_file",
    )
    if filing.get("live_submission") is not False or filing.get("aeat_accepted") is not False:
        raise RetencionesInstalledCliError(
            stage=f"{stage}:work_file",
            diagnostic_code="annual_source_filing_not_local",
        )
    filing_id = _required_text(filing, key="filing_record_id", stage=f"{stage}:work_file")
    m115_no_relevant_payment_attestation = not captures and source_modelo == "115"
    return AnnualSourcePeriodEvidence(
        modelo=source_modelo,
        period=source_period.period,
        evidence_state=source_period.evidence_state.value,
        source_workflow=(
            "m115_no_relevant_payment_attested_local_filing_record"
            if m115_no_relevant_payment_attestation
            else "local_filing_record"
        ),
        work_unit_id=work_id,
        calculation_revision_id=revision_id,
        calculated_casillas=calculated_casillas,
        verification_granted=True,
        filing_record_id=filing_id,
        live_submission=False,
        attestation_period=(f"{year}:{source_period.period}" if m115_no_relevant_payment_attestation else None),
    )


def _annual_source_revision(slice_: InstalledAnnualCliSlice, *, stage: str) -> str:
    """Require the annual slice's public captures to share one source revision."""
    revisions = {capture.revision for capture in slice_.captures}
    if len(revisions) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_revision_ambiguous")
    return next(iter(revisions))


def _assert_source_period_evidence(
    *,
    source_period: AnnualSourcePeriodInput,
    captures: tuple[InstalledPeriodicCliSlice, ...],
    stage: str,
) -> None:
    """Keep no-activity zeros distinct from public payment-allocation evidence."""
    observed_count = sum(capture.expected_observation_count for capture in captures)
    if observed_count != source_period.expected_observation_count:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_observation_count_mismatch")
    if captures:
        expected_from_captures = _aggregate_source_casillas(captures=captures, stage=stage)
        if expected_from_captures != source_period.expected_casillas:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_casilla_oracle_mismatch")
        if source_period.evidence_state is not EvidenceState.AVAILABLE:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_payment_state_mismatch")
        return
    if source_period.evidence_state is not EvidenceState.NO_RELEVANT_PAYMENT:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_empty_state_mismatch")
    if any(value != Decimal("0") for _casilla_id, value in source_period.expected_casillas):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_empty_casilla_not_zero")


def _aggregate_source_casillas(
    *, captures: tuple[InstalledPeriodicCliSlice, ...], stage: str
) -> tuple[tuple[str, Decimal], ...]:
    """Combine independent quarterly scenario facts without a second resolver."""
    source_modelo = captures[0].modelo
    count_casilla_by_modelo = {"111": "07", "115": "01"}
    count_casilla = count_casilla_by_modelo.get(source_modelo)
    if count_casilla is None:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_modelo_oracle_unsupported")
    expected_ids = _source_casilla_identity(captures, stage=stage)
    totals = {casilla_id: Decimal("0") for casilla_id in expected_ids}
    for capture in captures:
        for casilla_id, value in capture.expected_casillas:
            totals[casilla_id] += value
    if count_casilla not in totals:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_count_casilla_missing")
    totals[count_casilla] = Decimal(len({capture.counterparty_nif for capture in captures}))
    return tuple((casilla_id, totals[casilla_id]) for casilla_id in expected_ids)
