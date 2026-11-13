"""CLI request and presentation boundary for the profile prorrata register."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Never
from uuid import UUID

import typer
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import submitted_operation_error
from cadrumo_client.contracts.contracts import RefusalCode

from ...application.operations.public_scalar import PublicDecimal
from ...application.prorrata_register.operation_requests import (
    PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID,
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
    PRORRATA_LIST_OPERATION_DEFINITION_ID,
    PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID,
    PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
    ProrrataDeclareGrossRequest,
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataElectGeneralRequest,
    ProrrataListRequest,
    ProrrataRemoveGrossRequest,
    ProrrataRevokeEspecialRequest,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSettleSectorRequest,
)
from ...application.prorrata_register.projection_contracts import (
    ProrrataEntryProjection,
    ProrrataFindingProjection,
    ProrrataGrossDeclarationProjection,
    ProrrataListProjection,
    ProrrataMutationProjection,
    ProrrataRefusalProjection,
    ProrrataSectorDefinitionProjection,
    ProrrataSeedSourceProjection,
)
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    SectorDiferenciadoLetra,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from .common import active_bucket_id_or_refuse, emit_envelope
from .decimal_parsing import parse_decimal_amount
from .operation_ledger_prorrata_register import (
    submit_prorrata_list,
    submit_prorrata_mutation,
    validate_prorrata_list_completion,
    validate_prorrata_mutation_completion,
)
from .prorrata_register_results import (
    ProrrataDeclareGrossResult,
    ProrrataDeclareSectorResult,
    ProrrataElectEspecialResult,
    ProrrataElectGeneralResult,
    ProrrataElectResult,
    ProrrataEntryPayload,
    ProrrataEspecialTransitionPayload,
    ProrrataGrossDeclarationPayload,
    ProrrataListResult,
    ProrrataRemoveGrossResult,
    ProrrataRevokeEspecialResult,
    ProrrataSeedFindingPayload,
    ProrrataSeedResult,
    ProrrataSeedSectorResult,
    ProrrataSeedSourcePayload,
    ProrrataSettleSectorResult,
    SectorDefinitionPayload,
)

_DEFAULT_REFUSAL_MESSAGE = "errors.refused.refused_profile_prorrata_register_validation"
_SEED_LOCAL_AUTHORITY_NOTICE_CODE = "ledger.prorrata.seed.local_authority"
_SEED_ADVISORY_NOTICE_CODE = "ledger.prorrata.seed.advisory"


@dataclass(frozen=True, slots=True)
class _RefusalRoute:
    """The operator message of one refusal reason and where each context value comes from.

    ``context`` maps a context key to the name of the refusal value that fills it.
    A route whose value is absent from the refusal is an invalid refusal.
    """

    message_key: str
    context: Mapping[str, str]


_SEED_BLOCKED = _RefusalRoute(message_key="cli.app.ledger.prorrata.seed_blocked", context={"detail": "blocking_detail"})
_PROVENANCE_ACCEPTED = {"provenance": "provenance", "accepted": "accepted"}
_EJERCICIO = {"ejercicio": "ejercicio"}
_SECTOR_EJERCICIO = {"ejercicio": "ejercicio", "sector_id": "sector_id"}

_REFUSAL_ROUTES: Final[Mapping[str, _RefusalRoute]] = {
    "validation": _RefusalRoute(message_key=_DEFAULT_REFUSAL_MESSAGE, context={"detail": "detail"}),
    "provenance_required": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.provenance_requires_evidence",
        context={"accepted": "accepted"},
    ),
    "provenance_not_electable": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.provenance_not_electable",
        context=_PROVENANCE_ACCEPTED,
    ),
    "reference_required": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.reference_required",
        context={"provenance": "provenance"},
    ),
    "reference_not_permitted": _RefusalRoute(message_key="cli.app.ledger.prorrata.reference_not_permitted", context={}),
    "seed_source_blocked": _SEED_BLOCKED,
    "seed_existing_blocked": _SEED_BLOCKED,
    "seed_source_absent": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.seed_source_absent",
        context={"prior_ejercicio": "prior_ejercicio", "ejercicio": "ejercicio"},
    ),
    "regulated_override_standing": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.seed_regulated_override_standing",
        context={"provenance": "existing_provenance", "ejercicio": "ejercicio"},
    ),
    "sector_prior_definitive_absent": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.seed_sector_prior_definitive_absent",
        context={"prior_ejercicio": "prior_ejercicio", **_SECTOR_EJERCICIO},
    ),
    "sector_settlement_entry_absent": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.settle_sector_entry_absent",
        context=_SECTOR_EJERCICIO,
    ),
    "gross_declaration_duplicate": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.gross_duplicate", context=_EJERCICIO
    ),
    "gross_declaration_absent": _RefusalRoute(message_key="cli.app.ledger.prorrata.gross_absent", context=_EJERCICIO),
    "gross_declaration_sector_unknown": _RefusalRoute(
        message_key="cli.app.ledger.prorrata.gross_sector_unknown",
        context=_SECTOR_EJERCICIO,
    ),
}


def _refusal_values(
    refusal: ProrrataRefusalProjection,
    provenance: ProrrataProvisionalProvenance | None,
) -> dict[str, str | int | None]:
    """Return the named values a refusal route may place in its message context."""
    ejercicio = refusal.ejercicio
    blocking_detail = " | ".join(f"[{item.code}] {item.message}" for item in refusal.findings if item.blocking)
    return {
        "detail": refusal.detail,
        "blocking_detail": blocking_detail or refusal.detail,
        "accepted": ", ".join(refusal.accepted_provenances),
        "provenance": provenance.value if provenance is not None else "",
        "existing_provenance": refusal.existing_provenance,
        "ejercicio": ejercicio,
        "prior_ejercicio": ejercicio - 1 if ejercicio is not None else None,
        "sector_id": refusal.sector_id,
    }


def _route_context(route: _RefusalRoute, values: Mapping[str, str | int | None]) -> dict[str, str | int]:
    context: dict[str, str | int] = {}
    for key, name in route.context.items():
        value = values[name]
        if value is None:
            raise _invalid_refusal_error()
        context[key] = value
    return context


def _unsigned_amount(text: str, *, label: str) -> PublicDecimal:
    return PublicDecimal(decimal=str(parse_decimal_amount(text, label=label, signed=False)))


def _provenance_value(provenance: ProrrataProvisionalProvenance | None) -> str | None:
    return provenance.value if provenance is not None else None


def _invalid_refusal_error() -> CliRefusedBoundaryError:
    return CliRefusedBoundaryError(context={"reason": "invalid_prorrata_refusal"})


def _invalid_projection_error() -> CliRefusedBoundaryError:
    return CliRefusedBoundaryError(context={"reason": "invalid_prorrata_projection"})


def _profile_id() -> UUID:
    return UUID(active_bucket_id_or_refuse())


def _decimal_text(value: PublicDecimal | None) -> str | None:
    return format(Decimal(value.decimal), "f") if value is not None else None


def entry_payload(entry: ProrrataEntryProjection) -> ProrrataEntryPayload:
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
    return SectorDefinitionPayload.model_validate_json(definition.model_dump_json())


def _raise_prorrata_refusal(
    translated_message: str,
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
    raise CliRefusedBoundaryError(translated_message=translated_message, context=context)


def _raise_refusal(
    refusal: ProrrataRefusalProjection,
    *,
    completion: RegisteredOperationCompletion[ProrrataMutationProjection],
    provenance: ProrrataProvisionalProvenance | None = None,
) -> Never:
    operation_id = str(completion.operation_id)
    route = _REFUSAL_ROUTES.get(refusal.reason)
    context = _route_context(route, _refusal_values(refusal, provenance)) if route is not None else {}
    _raise_prorrata_refusal(
        route.message_key if route is not None else _DEFAULT_REFUSAL_MESSAGE,
        operation_id=operation_id,
        refusal=refusal,
        completion=completion,
        **context,
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
            raise _invalid_refusal_error()
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
            RefusalCode.INVALID_FRAME.value
            if isinstance(exc, CliRefusedBoundaryError)
            else RefusalCode.UNAVAILABLE.value
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
        raise _invalid_projection_error()
    return entry_payload(projection.entry)


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
        percentage=_unsigned_amount(percentage, label="percentage"),
        provenance=_provenance_value(provenance),
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
        percentage=_unsigned_amount(percentage, label="percentage"),
        provenance=_provenance_value(provenance),
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
        percentage=_unsigned_amount(percentage, label="percentage"),
        provenance=_provenance_value(provenance),
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
        member_activity_codes=tuple(activity_code),
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
            raise _invalid_projection_error()
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
        message=(
            tr(
                "cli.app.ledger.prorrata.seed_operator_stated",
                modelo=seed.modelo,
                filing_year=seed.filing_year,
            )
            if seed.authority == "operator_stated"
            else tr(
                "cli.app.ledger.prorrata.seed_local_authority",
                modelo=seed.modelo,
                filing_year=seed.filing_year,
                period=seed.period,
            )
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


def prorrata_seed(
    ctx: typer.Context,
    ejercicio: int,
    sector: str | None = None,
    percentage: str | None = None,
) -> None:
    """Carry only the whole-entity prior definitive into an ejercicio.

    ``percentage`` is the taxpayer's statement of the prior definitive, used
    only when neither the prior 390 nor the final-period 303 is held.
    """
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
    request = ProrrataSeedRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        percentage=None if percentage is None else _unsigned_amount(percentage, label="percentage"),
    )
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
            raise _invalid_projection_error()
        findings = [_seed_finding_payload(item) for item in projection.findings]
        payload = ProrrataSeedResult(
            bucket_id=str(profile_id),
            entry=entry,
            source=_seed_source_payload(seed_source),
            findings=findings,
            count=int(projection.count or 0),
        )
        advisories = _seed_advisories(projection)
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
            raise _invalid_projection_error()
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
        con_derecho_volume=_unsigned_amount(con_derecho_volume, label="con-derecho-volume"),
        sin_derecho_volume=_unsigned_amount(sin_derecho_volume, label="sin-derecho-volume"),
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


def _gross_declaration_payload(declaration: ProrrataGrossDeclarationProjection) -> ProrrataGrossDeclarationPayload:
    return ProrrataGrossDeclarationPayload(
        ejercicio=declaration.ejercicio,
        period=declaration.period,
        sector_id=declaration.sector_id,
        gross_cuota=format(Decimal(declaration.gross_cuota.decimal), "f"),
        evidence_reference=declaration.evidence_reference,
        provenance=declaration.provenance,
        declared_at=declaration.declared_at.isoformat(),
    )


def _present_gross_declaration(
    ctx: typer.Context,
    completed: RegisteredOperationCompletion[ProrrataMutationProjection],
    projection: ProrrataMutationProjection,
    *,
    profile_id: UUID,
    result_class: type[ProrrataDeclareGrossResult] | type[ProrrataRemoveGrossResult],
    command: str,
) -> None:
    def render() -> None:
        if projection.gross_declaration is None:
            raise _invalid_projection_error()
        declaration = _gross_declaration_payload(projection.gross_declaration)
        payload = result_class(bucket_id=str(profile_id), declaration=declaration, count=int(projection.count or 0))
        emit_envelope(
            ctx,
            command=command,
            result=payload,
            lines=(
                f"bucket\t{profile_id}",
                f"ejercicio\t{declaration.ejercicio}",
                f"period\t{declaration.period}",
                f"sector_id\t{declaration.sector_id or ''}",
                f"gross_cuota\t{declaration.gross_cuota}",
                f"evidence_reference\t{declaration.evidence_reference}",
                f"provenance\t{declaration.provenance}",
                f"count\t{projection.count}",
            ),
        )

    _present_registered_operation(completed, render)


def prorrata_declare_gross(
    ctx: typer.Context,
    ejercicio: int,
    period: str,
    amount: str,
    evidence: str,
    sector: str | None = None,
    replace: bool = False,
) -> None:
    """Declare an earlier liquidation period's gross deducible cuota before prorrata."""
    profile_id = _profile_id()
    request = ProrrataDeclareGrossRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        period=period,
        sector_id=sector,
        gross_cuota=_unsigned_amount(amount, label="amount"),
        evidence_reference=evidence,
        replace=replace,
    )
    completed, projection = _run_mutation(
        ctx,
        request,
        definition_id=PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID,
        operation_id="declare_gross",
    )
    _present_gross_declaration(
        ctx,
        completed,
        projection,
        profile_id=profile_id,
        result_class=ProrrataDeclareGrossResult,
        command=PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID,
    )


def prorrata_remove_gross(
    ctx: typer.Context,
    ejercicio: int,
    period: str,
    sector: str | None = None,
) -> None:
    """Remove an earlier liquidation period's operator gross declaration."""
    profile_id = _profile_id()
    request = ProrrataRemoveGrossRequest(
        profile_id=profile_id,
        ejercicio=ejercicio,
        period=period,
        sector_id=sector,
    )
    completed, projection = _run_mutation(
        ctx,
        request,
        definition_id=PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID,
        operation_id="remove_gross",
    )
    _present_gross_declaration(
        ctx,
        completed,
        projection,
        profile_id=profile_id,
        result_class=ProrrataRemoveGrossResult,
        command=PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID,
    )


def prorrata_list(ctx: typer.Context) -> None:
    """Read every period and differentiated-sector row through the runtime."""
    profile_id = _profile_id()
    request = ProrrataListRequest(profile_id=profile_id)
    completed: RegisteredOperationCompletion[ProrrataListProjection] = submit_prorrata_list(ctx, request)
    projection = validate_prorrata_list_completion(completed)

    def render() -> None:
        entries = [entry_payload(entry) for entry in projection.entries]
        sectors = [_sector_payload(definition) for definition in projection.sectors]
        gross_declarations = [_gross_declaration_payload(declaration) for declaration in projection.gross_declarations]
        payload = ProrrataListResult(
            bucket_id=str(profile_id),
            entries=entries,
            sectors=sectors,
            gross_declarations=gross_declarations,
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
        for declaration in gross_declarations:
            lines.append(
                f"gross	{declaration.ejercicio}	{declaration.period}	sector={declaration.sector_id or ''}	"
                f"gross_cuota={declaration.gross_cuota}	provenance={declaration.provenance}	"
                f"evidence_reference={declaration.evidence_reference}	declared_at={declaration.declared_at}",
            )
        emit_envelope(
            ctx,
            command=PRORRATA_LIST_OPERATION_DEFINITION_ID,
            result=payload,
            lines=lines,
        )

    _present_registered_operation(completed, render)


__all__ = [
    "prorrata_declare_gross",
    "prorrata_declare_sector",
    "prorrata_elect_especial",
    "prorrata_elect_general",
    "prorrata_list",
    "prorrata_remove_gross",
    "prorrata_revoke_especial",
    "prorrata_seed",
    "prorrata_seed_sector",
    "prorrata_settle_sector",
]


def _seed_advisories(projection: ProrrataMutationProjection) -> tuple[ProrrataFindingProjection, ...]:
    """Project advisories only after excluding every blocking finding."""
    advisories = tuple(item for item in projection.findings if not item.blocking)
    if any(item.blocking for item in projection.findings):
        raise _invalid_projection_error()
    return advisories
