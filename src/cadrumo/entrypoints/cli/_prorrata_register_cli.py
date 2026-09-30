"""CLI request and presentation boundary for the profile prorrata register."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel

from ...application.operations.public_scalar import PublicDecimal
from ...application.prorrata_register.registered_operations import (
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
    PRORRATA_LIST_OPERATION_DEFINITION_ID,
    PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataElectGeneralRequest,
    ProrrataEntryProjection,
    ProrrataFindingProjection,
    ProrrataListProjection,
    ProrrataListRequest,
    ProrrataMutationProjection,
    ProrrataRefusalProjection,
    ProrrataRevokeEspecialRequest,
    ProrrataSectorDefinitionProjection,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSeedSourceProjection,
    ProrrataSettleSectorRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    SectorDiferenciadoLetra,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ._decimal_parsing import parse_decimal_amount
from ._prorrata_register_payloads import (
    ProrrataDeclareSectorResult,
    ProrrataElectEspecialResult,
    ProrrataElectGeneralResult,
    ProrrataElectResult,
    ProrrataEntryPayload,
    ProrrataEspecialTransitionPayload,
    ProrrataListResult,
    ProrrataRevokeEspecialResult,
    ProrrataSeedFindingPayload,
    ProrrataSeedResult,
    ProrrataSeedSectorResult,
    ProrrataSeedSourcePayload,
    ProrrataSettleSectorResult,
    SectorDefinitionPayload,
)
from .common import active_bucket_id_or_refuse as _register_bucket_id
from .common import emit_envelope
from .errors import CliRefusedBoundaryError
from .runtime_ledger_prorrata_register import (
    submit_prorrata_list,
    submit_prorrata_mutation,
    validate_prorrata_list_completion,
    validate_prorrata_mutation_completion,
)
from .runtime_registered_operation import RegisteredOperationCompletion, submitted_operation_error

_SEED_LOCAL_AUTHORITY_NOTICE_CODE = "ledger.prorrata.seed.local_authority"
_SEED_ADVISORY_NOTICE_CODE = "ledger.prorrata.seed.advisory"
_SEED_AUTHORITY = "local_prior_observation"


def _profile_id() -> UUID:
    return UUID(_register_bucket_id())


def _decimal_text(value: PublicDecimal | None) -> str | None:
    return format(Decimal(value.decimal), "f") if value is not None else None


def _entry_payload(entry: ProrrataEntryProjection) -> ProrrataEntryPayload:
    """Map every registered entry field into the established CLI result schema."""
    transition = entry.especial_transition
    return ProrrataEntryPayload(
        ejercicio=entry.ejercicio,
        regime=entry.regime,
        especial_transition=(
            ProrrataEspecialTransitionPayload(
                kind=ProrrataEspecialTransitionKind.from_registry(transition.kind),
                evidence_reference=transition.evidence_reference,
            )
            if transition is not None
            else None
        ),
        sector_id=entry.sector_id,
        interrupted=entry.interrupted,
        provisional_percentage=_decimal_text(entry.provisional_percentage),
        provisional_provenance=entry.provisional_provenance,
        authorisation_reference=entry.authorisation_reference,
        definitive_percentage=_decimal_text(entry.definitive_percentage),
        definitive_volume_con_derecho=_decimal_text(entry.definitive_volume_con_derecho),
        definitive_volume_sin_derecho=_decimal_text(entry.definitive_volume_sin_derecho),
        source_observation_ref=entry.source_observation_ref,
        source_registry_snapshot_refs=tuple(
            RegistrySnapshotRef.model_validate_json(reference.model_dump_json())
            for reference in entry.source_registry_snapshot_refs
        ),
        schema_version=entry.schema_version,
    )


def _sector_payload(definition: ProrrataSectorDefinitionProjection) -> SectorDefinitionPayload:
    return SectorDefinitionPayload(
        sector_id=definition.sector_id,
        letra=definition.letra,
        member_activity_codes=tuple(definition.member_activity_codes),
    )


def _refuse(
    message: str,
    *,
    operation_id: str,
    refusal: ProrrataRefusalProjection,
    completion: RegisteredOperationCompletion[ProrrataMutationProjection] | None = None,
    **context_values: str | int,
) -> Never:
    context: dict[str, object] = {
        "operation_id": str(completion.operation_id) if completion is not None else operation_id,
        "reason": refusal.reason,
    }
    if completion is not None:
        context.update(
            {
                "terminal_condition": completion.terminal_condition.value,
                "effect": completion.effect.value,
                "refusal_code": completion.refusal_code or "",
            }
        )
    if refusal.ejercicio is not None:
        context["ejercicio"] = refusal.ejercicio
    if refusal.sector_id is not None:
        context["sector_id"] = refusal.sector_id
    context.update(context_values)
    raise CliRefusedBoundaryError(translated_message=message, context=context)


def _raise_refusal(
    refusal: ProrrataRefusalProjection,
    *,
    completion: RegisteredOperationCompletion[ProrrataMutationProjection],
    provenance: ProrrataProvisionalProvenance | None = None,
) -> Never:
    operation_id = str(completion.operation_id)
    reason = refusal.reason
    if reason == "validation":
        _refuse(
            "errors.refused.refused_profile_prorrata_register_validation",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            detail=refusal.detail,
        )
    if reason == "provenance_required":
        _refuse(
            "cli.app.ledger.prorrata.provenance_requires_evidence",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            accepted=", ".join(refusal.accepted_provenances),
        )
    if reason == "provenance_not_electable":
        _refuse(
            "cli.app.ledger.prorrata.provenance_not_electable",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            provenance=provenance.value if provenance is not None else "",
            accepted=", ".join(refusal.accepted_provenances),
        )
    if reason == "reference_required":
        _refuse(
            "cli.app.ledger.prorrata.reference_required",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            provenance=provenance.value if provenance is not None else "",
        )
    if reason == "reference_not_permitted":
        _refuse(
            "cli.app.ledger.prorrata.reference_not_permitted",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
        )
    if reason in {"seed_source_blocked", "seed_existing_blocked"}:
        detail = " | ".join(f"[{finding.code}] {finding.message}" for finding in refusal.findings if finding.blocking)
        _refuse(
            "cli.app.ledger.prorrata.seed_blocked",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            detail=detail or refusal.detail,
        )
    if reason == "seed_source_absent":
        ejercicio = refusal.ejercicio
        if ejercicio is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_refusal"})
        _refuse(
            "cli.app.ledger.prorrata.seed_source_absent",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            prior_ejercicio=ejercicio - 1,
            ejercicio=ejercicio,
        )
    if reason == "regulated_override_standing":
        ejercicio = refusal.ejercicio
        if ejercicio is None or refusal.existing_provenance is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_refusal"})
        _refuse(
            "cli.app.ledger.prorrata.seed_regulated_override_standing",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            provenance=refusal.existing_provenance,
            ejercicio=ejercicio,
        )
    if reason == "sector_prior_definitive_absent":
        ejercicio = refusal.ejercicio
        if ejercicio is None or refusal.sector_id is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_refusal"})
        _refuse(
            "cli.app.ledger.prorrata.seed_sector_prior_definitive_absent",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            prior_ejercicio=ejercicio - 1,
            ejercicio=ejercicio,
            sector_id=refusal.sector_id,
        )
    if reason == "sector_settlement_entry_absent":
        ejercicio = refusal.ejercicio
        if ejercicio is None or refusal.sector_id is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_refusal"})
        _refuse(
            "cli.app.ledger.prorrata.settle_sector_entry_absent",
            operation_id=operation_id,
            refusal=refusal,
            completion=completion,
            ejercicio=ejercicio,
            sector_id=refusal.sector_id,
        )
    _refuse(
        "errors.refused.refused_profile_prorrata_register_validation",
        operation_id=operation_id,
        refusal=refusal,
        completion=completion,
    )


def _run_mutation(
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    operation_id: str,
    provenance: ProrrataProvisionalProvenance | None = None,
) -> tuple[RegisteredOperationCompletion[ProrrataMutationProjection], ProrrataMutationProjection]:
    completed = submit_prorrata_mutation(ctx, request, definition_id=definition_id)
    projection = validate_prorrata_mutation_completion(completed, operation_id=operation_id)
    if projection.outcome == "refused":
        refusal = projection.refusal
        if refusal is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_refusal"})
        _raise_refusal(refusal, completion=completed, provenance=provenance)
    return completed, projection


def _present_registered_operation[ProjectionT: BaseModel](
    completed: RegisteredOperationCompletion[ProjectionT],
    render: Callable[[], None],
) -> None:
    """Keep the settled worker receipt if local projection rendering fails."""
    try:
        render()
    except typer.Exit:
        raise
    except Exception as exc:
        code = (
            RuntimeRefusalCode.INVALID_FRAME.value
            if isinstance(exc, CliRefusedBoundaryError)
            else RuntimeRefusalCode.UNAVAILABLE.value
        )
        raise submitted_operation_error(
            completed.operation_id,
            code,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _entry_from_projection(projection: ProrrataMutationProjection) -> ProrrataEntryPayload:
    if projection.entry is None:
        raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_projection"})
    return _entry_payload(projection.entry)


def _manual_election(
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    operation_id: str,
    provenance: ProrrataProvisionalProvenance | None,
    result_class: type[ProrrataElectResult],
    command: str,
) -> None:
    profile_id = _profile_id()
    completed, projection = _run_mutation(
        ctx,
        request,
        definition_id=definition_id,
        operation_id=operation_id,
        provenance=provenance,
    )

    def render() -> None:
        entry = _entry_from_projection(projection)
        payload = result_class(bucket_id=str(profile_id), entry=entry, count=int(projection.count or 0))
        transition = entry.especial_transition
        emit_envelope(
            ctx,
            command=command,
            result=payload,
            lines=(
                f"bucket\t{profile_id}",
                f"ejercicio\t{entry.ejercicio}",
                f"regime\t{entry.regime}",
                f"sector_id\t{entry.sector_id or ''}",
                f"provisional_percentage\t{entry.provisional_percentage}",
                f"provisional_provenance\t{entry.provisional_provenance or ''}",
                f"especial_transition\t{transition.kind.value if transition else ''}",
                f"evidence_reference\t{transition.evidence_reference if transition else ''}",
                f"count\t{projection.count}",
            ),
        )

    _present_registered_operation(completed, render)


def prorrata_elect_especial(
    ctx: typer.Context,
    ejercicio: int,
    percentage: str,
    evidence_reference: str | None = None,
    provenance: ProrrataProvisionalProvenance | None = None,
    reference: str | None = None,
    sector: str | None = None,
) -> None:
    """Submit the special-prorrata election through its registered operation."""
    profile_id = _profile_id()
    request = ProrrataElectEspecialRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        percentage=PublicDecimal(decimal=str(parse_decimal_amount(percentage, label="percentage", signed=False))),
        provenance=provenance.value if provenance is not None else None,
        reference=reference,
        sector_id=sector,
        evidence_reference=evidence_reference,
    )
    _manual_election(
        ctx,
        request,
        definition_id=PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
        operation_id="elect_especial",
        provenance=provenance,
        result_class=ProrrataElectEspecialResult,
        command="ledger.prorrata.elect_especial",
    )


def prorrata_elect_general(
    ctx: typer.Context,
    ejercicio: int,
    percentage: str,
    provenance: ProrrataProvisionalProvenance | None = None,
    reference: str | None = None,
    sector: str | None = None,
) -> None:
    """Submit the general-prorrata election through its registered operation."""
    profile_id = _profile_id()
    request = ProrrataElectGeneralRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        percentage=PublicDecimal(decimal=str(parse_decimal_amount(percentage, label="percentage", signed=False))),
        provenance=provenance.value if provenance is not None else None,
        reference=reference,
        sector_id=sector,
    )
    _manual_election(
        ctx,
        request,
        definition_id=PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
        operation_id="elect_general",
        provenance=provenance,
        result_class=ProrrataElectGeneralResult,
        command="ledger.prorrata.elect_general",
    )


def prorrata_revoke_especial(
    ctx: typer.Context,
    ejercicio: int,
    evidence_reference: str,
    percentage: str,
    provenance: ProrrataProvisionalProvenance | None = None,
    reference: str | None = None,
    sector: str | None = None,
) -> None:
    """Submit an evidence-backed special-prorrata revocation."""
    profile_id = _profile_id()
    request = ProrrataRevokeEspecialRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        percentage=PublicDecimal(decimal=str(parse_decimal_amount(percentage, label="percentage", signed=False))),
        provenance=provenance.value if provenance is not None else None,
        reference=reference,
        sector_id=sector,
        evidence_reference=evidence_reference,
    )
    _manual_election(
        ctx,
        request,
        definition_id=PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
        operation_id="revoke_especial",
        provenance=provenance,
        result_class=ProrrataRevokeEspecialResult,
        command="ledger.prorrata.revoke_especial",
    )


def prorrata_declare_sector(
    ctx: typer.Context,
    sector_id: str,
    letra: SectorDiferenciadoLetra,
    activity_code: tuple[str, ...] = (),
) -> None:
    """Submit one differentiated-sector partition row."""
    profile_id = _profile_id()
    request = ProrrataDeclareSectorRequest(
        profile_id=profile_id,
        sector_id=sector_id,
        letra=letra.value,
        member_activity_codes=activity_code,
    )
    completed, projection = _run_mutation(
        ctx,
        request,
        definition_id=PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
        operation_id="declare_sector",
    )

    def render() -> None:
        definition = projection.sector_definition
        if definition is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_projection"})
        sector = _sector_payload(definition)
        payload = ProrrataDeclareSectorResult(
            bucket_id=str(profile_id),
            sector=sector,
            count=int(projection.count or 0),
        )
        emit_envelope(
            ctx,
            command="ledger.prorrata.declare_sector",
            result=payload,
            lines=(
                f"bucket\t{profile_id}",
                f"sector_id\t{sector.sector_id}",
                f"letra\t{sector.letra}",
                f"member_activity_codes\t{','.join(sector.member_activity_codes)}",
                f"count\t{projection.count}",
            ),
        )

    _present_registered_operation(completed, render)


def _seed_finding_payload(finding: ProrrataFindingProjection) -> ProrrataSeedFindingPayload:
    return ProrrataSeedFindingPayload(
        code=finding.code,
        blocking=finding.blocking,
        message=finding.message,
        source_modelo=finding.source_modelo,
        source_filing_year=finding.source_filing_year,
        source_period=finding.source_period,
        stamped_revision_id=finding.stamped_revision_id,
        selected_revision_id=finding.selected_revision_id,
    )


def _seed_source_payload(seed: ProrrataSeedSourceProjection) -> ProrrataSeedSourcePayload:
    return ProrrataSeedSourcePayload(
        modelo=seed.modelo,
        filing_year=seed.filing_year,
        period=seed.period,
        casilla_id=seed.casilla_id,
        stamped_revision_id=seed.stamped_revision_id,
        authority=seed.authority,
    )


def _seed_notices(
    seed: ProrrataSeedSourceProjection,
    advisories: tuple[ProrrataFindingProjection, ...],
) -> tuple[Notice, ...]:
    origin = Notice(
        severity=NoticeSeverity.INFO,
        code=_SEED_LOCAL_AUTHORITY_NOTICE_CODE,
        message=tr(
            "cli.app.ledger.prorrata.seed_local_authority",
            modelo=seed.modelo,
            filing_year=seed.filing_year,
            period=seed.period,
        ),
        context={
            "source_modelo": seed.modelo,
            "source_filing_year": str(seed.filing_year),
            "source_period": seed.period,
            "stamped_revision_id": seed.stamped_revision_id,
            "authority": seed.authority,
        },
    )
    advisory_notices = tuple(
        Notice(
            severity=NoticeSeverity.WARNING,
            code=_SEED_ADVISORY_NOTICE_CODE,
            message=finding.message,
            context={"finding_code": finding.code},
        )
        for finding in advisories
    )
    return (origin, *advisory_notices)


def prorrata_seed(ctx: typer.Context, ejercicio: int, sector: str | None = None) -> None:
    """Carry only the whole-entity prior definitive into an ejercicio."""
    if sector is not None:
        raise CliRefusedBoundaryError(
            translated_message="cli.app.ledger.prorrata.seed_sector_requires_route",
            context={
                "reason": "sector_requires_seed_sector",
                "sector_id": sector,
                "ejercicio": ejercicio,
            },
        )
    profile_id = _profile_id()
    request = ProrrataSeedRequest(profile_id=profile_id, ejercicio=ejercicio)
    completed, projection = _run_mutation(
        ctx,
        request,
        definition_id=PRORRATA_SEED_OPERATION_DEFINITION_ID,
        operation_id="seed",
    )

    def render() -> None:
        entry = _entry_from_projection(projection)
        seed_source = projection.seed_source
        if seed_source is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_projection"})
        findings = [_seed_finding_payload(item) for item in projection.findings]
        payload = ProrrataSeedResult(
            bucket_id=str(profile_id),
            entry=entry,
            source=_seed_source_payload(seed_source),
            findings=findings,
            count=int(projection.count or 0),
        )
        advisories = tuple(item for item in projection.findings if not item.blocking)
        if any(item.blocking for item in projection.findings):
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_projection"})
        notices = _seed_notices(seed_source, advisories)
        emit_envelope(
            ctx,
            command="ledger.prorrata.seed",
            result=payload,
            lines=(
                f"bucket\t{profile_id}",
                f"ejercicio\t{entry.ejercicio}",
                f"sector_id\t{entry.sector_id or ''}",
                f"provisional_percentage\t{entry.provisional_percentage}",
                f"provisional_provenance\t{entry.provisional_provenance or ''}",
                f"source\t{seed_source.modelo}:{seed_source.filing_year}:{seed_source.period}",
                f"source_casilla_id\t{seed_source.casilla_id}",
                f"stamped_revision_id\t{seed_source.stamped_revision_id}",
                f"authority\t{seed_source.authority}",
                f"findings\t{len(findings)}",
                *(f"notice\t{notice.code}\t{notice.message}" for notice in notices),
                f"count\t{projection.count}",
            ),
            notices=notices,
        )

    _present_registered_operation(completed, render)


def prorrata_seed_sector(ctx: typer.Context, ejercicio: int, sector_id: str) -> None:
    """Carry one differentiated sector's own prior register definitive."""
    profile_id = _profile_id()
    request = ProrrataSeedSectorRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        sector_id=sector_id,
    )
    completed, projection = _run_mutation(
        ctx,
        request,
        definition_id=PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
        operation_id="seed_sector",
    )

    def render() -> None:
        entry = _entry_from_projection(projection)
        if projection.prior_ejercicio is None:
            raise CliRefusedBoundaryError(context={"reason": "invalid_prorrata_projection"})
        payload = ProrrataSeedSectorResult(
            bucket_id=str(profile_id),
            entry=entry,
            prior_ejercicio=projection.prior_ejercicio,
            count=int(projection.count or 0),
        )
        emit_envelope(
            ctx,
            command="ledger.prorrata.seed_sector",
            result=payload,
            lines=(
                f"bucket\t{profile_id}",
                f"ejercicio\t{entry.ejercicio}",
                f"sector_id\t{entry.sector_id or ''}",
                f"prior_ejercicio\t{projection.prior_ejercicio}",
                f"provisional_percentage\t{entry.provisional_percentage}",
                f"provisional_provenance\t{entry.provisional_provenance or ''}",
                f"source_observation_ref\t{entry.source_observation_ref or ''}",
                f"count\t{projection.count}",
            ),
        )

    _present_registered_operation(completed, render)


def prorrata_settle_sector(
    ctx: typer.Context,
    ejercicio: int,
    sector_id: str,
    con_derecho_volume: str,
    sin_derecho_volume: str,
) -> None:
    """Settle one sector's year-end definitive from its annual volumes."""
    profile_id = _profile_id()
    request = ProrrataSettleSectorRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        sector_id=sector_id,
        con_derecho_volume=PublicDecimal(
            decimal=str(parse_decimal_amount(con_derecho_volume, label="con-derecho-volume", signed=False)),
        ),
        sin_derecho_volume=PublicDecimal(
            decimal=str(parse_decimal_amount(sin_derecho_volume, label="sin-derecho-volume", signed=False)),
        ),
    )
    completed, projection = _run_mutation(
        ctx,
        request,
        definition_id=PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
        operation_id="settle_sector",
    )

    def render() -> None:
        entry = _entry_from_projection(projection)
        payload = ProrrataSettleSectorResult(
            bucket_id=str(profile_id),
            entry=entry,
            count=int(projection.count or 0),
        )
        emit_envelope(
            ctx,
            command="ledger.prorrata.settle_sector",
            result=payload,
            lines=(
                f"bucket\t{profile_id}",
                f"ejercicio\t{entry.ejercicio}",
                f"sector_id\t{entry.sector_id or ''}",
                f"definitive_percentage\t{entry.definitive_percentage}",
                f"definitive_volume_con_derecho\t{entry.definitive_volume_con_derecho}",
                f"definitive_volume_sin_derecho\t{entry.definitive_volume_sin_derecho}",
                f"count\t{projection.count}",
            ),
        )

    _present_registered_operation(completed, render)


def prorrata_list(ctx: typer.Context) -> None:
    """Read every period and differentiated-sector row through the runtime."""
    profile_id = _profile_id()
    request = ProrrataListRequest(profile_id=profile_id)
    completed: RegisteredOperationCompletion[ProrrataListProjection] = submit_prorrata_list(ctx, request)
    projection = validate_prorrata_list_completion(completed)

    def render() -> None:
        entries = [_entry_payload(entry) for entry in projection.entries]
        sectors = [_sector_payload(definition) for definition in projection.sectors]
        payload = ProrrataListResult(
            bucket_id=str(profile_id),
            entries=entries,
            sectors=sectors,
            count=projection.count,
        )
        lines = [f"bucket\t{profile_id}", f"count\t{projection.count}"]
        for entry in entries:
            lines.append(
                f"{entry.ejercicio}\t{entry.regime}\tsector={entry.sector_id or ''}\t"
                f"provisional={entry.provisional_percentage}\tdefinitive={entry.definitive_percentage}",
            )
        for definition in sectors:
            lines.append(
                f"sector\t{definition.sector_id}\tletra={definition.letra}\t"
                f"codes={','.join(definition.member_activity_codes)}",
            )
        emit_envelope(
            ctx,
            command=PRORRATA_LIST_OPERATION_DEFINITION_ID,
            result=payload,
            lines=lines,
        )

    _present_registered_operation(completed, render)


__all__ = [
    "prorrata_declare_sector",
    "prorrata_elect_especial",
    "prorrata_elect_general",
    "prorrata_list",
    "prorrata_revoke_especial",
    "prorrata_seed",
    "prorrata_seed_sector",
    "prorrata_settle_sector",
]
