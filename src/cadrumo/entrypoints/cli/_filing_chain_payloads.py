"""JSON projections of the filing chain: register refs, reconciliations and observation layers.

Shared by the filing-record commands and the live filed pull, which both report
what an AEAT register entry did to a period's chain. Every projection carries
identifiers and stable tokens only; operator prose is rendered from locale keys.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Literal

from ...application.calculations.observations_repository import (
    ObservationEnvelopePayload,
    ObservationLayers,
    ObservationOverride,
    ObservationSourceKind,
)
from ...application.modelo.filing_chain_reconciliation import (
    FilingReconciliationNotice,
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from ...core.casilla_id import CasillaId
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity, OutputSchema
from ...core.period import Period
from ...domain.modelos.filing_record import AeatRegisterRef
from ._decimal_wire import DecimalWireText

_INFO_NOTICE_CODES = frozenset({FilingReconciliationNoticeCode.RECEIPT_TOTALS_ONLY})

_RECONCILIATION_NOTICE_LOCALE_KEYS: Mapping[FilingReconciliationNoticeCode, str] = {
    FilingReconciliationNoticeCode.CONTENT_UNAVAILABLE: (
        "cli.app.modelo.filing_record.reconciliation_notice.content_unavailable"
    ),
    FilingReconciliationNoticeCode.RECEIPT_TOTALS_NOT_RECONCILED: (
        "cli.app.modelo.filing_record.reconciliation_notice.receipt_totals_not_reconciled"
    ),
    FilingReconciliationNoticeCode.RECEIPT_TOTALS_MISMATCH: (
        "cli.app.modelo.filing_record.reconciliation_notice.receipt_totals_mismatch"
    ),
    FilingReconciliationNoticeCode.RECEIPT_TOTALS_ONLY: (
        "cli.app.modelo.filing_record.reconciliation_notice.receipt_totals_only"
    ),
    FilingReconciliationNoticeCode.DECLARATION_KIND_MISMATCH: (
        "cli.app.modelo.filing_record.reconciliation_notice.declaration_kind_mismatch"
    ),
    FilingReconciliationNoticeCode.DECLARATION_KIND_UNDETERMINED: (
        "cli.app.modelo.filing_record.reconciliation_notice.declaration_kind_undetermined"
    ),
    FilingReconciliationNoticeCode.CORRECTION_WITHOUT_CONFIRMED_BASELINE: (
        "cli.app.modelo.filing_record.reconciliation_notice.correction_without_confirmed_baseline"
    ),
}


class AeatRegisterRefPayload(OutputSchema):
    """JSON projection of :class:`AeatRegisterRef`."""

    expediente_id: str | None = None
    csv: str | None = None
    justificante_number: str | None = None
    tipo_solicitud: str | None = None
    presented_at: datetime | None = None


class FilingReconciliationNoticePayload(OutputSchema):
    """One condition a reconciliation reported, as a stable code and identifier context."""

    code: FilingReconciliationNoticeCode
    context: dict[str, str] = {}


class FilingReconciliationPayload(OutputSchema):
    """JSON projection of one :class:`FilingReconciliationResult`."""

    outcome: FilingReconciliationOutcome
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    member_nif: str | None = None
    filing_record_id: str | None = None
    affected_filing_record_ids: list[str] = []
    differing_casilla_ids: list[CasillaId] = []
    evidence_basis: Literal["casillas", "receipt_totals"] | None = None
    notices: list[FilingReconciliationNoticePayload] = []


class ObservationLayerPayload(OutputSchema):
    """One stored observation layer of a filing coordinate."""

    source_kind: ObservationSourceKind
    official_evidence: bool
    captured_at: datetime
    stamped_revision_id: str
    casilla_values: dict[CasillaId, DecimalWireText]


class ObservationOverridePayload(OutputSchema):
    """Audit of an operator override held on the pending-local layer."""

    actor: str
    reason: str
    recorded_at: datetime
    replaced_source_kind: ObservationSourceKind | None = None
    replaced_values: dict[CasillaId, DecimalWireText] = {}


class ObservationLayersPayload(OutputSchema):
    """Both observation layers of a coordinate and which one readers see."""

    official: ObservationLayerPayload | None = None
    pending_local: ObservationLayerPayload | None = None
    effective_source_kind: ObservationSourceKind | None = None
    override: ObservationOverridePayload | None = None


def aeat_register_payload(register: AeatRegisterRef | None) -> AeatRegisterRefPayload | None:
    """Project an optional register reference."""
    if register is None:
        return None
    return AeatRegisterRefPayload(
        expediente_id=register.expediente_id,
        csv=register.csv,
        justificante_number=register.justificante_number,
        tipo_solicitud=register.tipo_solicitud,
        presented_at=register.presented_at,
    )


def aeat_register_lines(register: AeatRegisterRef | None) -> list[str]:
    """Render an optional register reference as ``aeat_register.*`` lines."""
    if register is None:
        return []
    fields = (
        ("expediente_id", register.expediente_id),
        ("csv", register.csv),
        ("justificante_number", register.justificante_number),
        ("tipo_solicitud", register.tipo_solicitud),
        ("presented_at", register.presented_at.isoformat() if register.presented_at is not None else None),
    )
    return [f"aeat_register.{name}\t{value}" for name, value in fields if value is not None]


def filing_reconciliation_payload(result: FilingReconciliationResult) -> FilingReconciliationPayload:
    """Project one reconciliation result."""
    return FilingReconciliationPayload(
        outcome=result.outcome,
        bucket_id=result.bucket_id,
        modelo=result.modelo,
        filing_year=result.filing_year,
        period=result.period,
        member_nif=result.member_nif,
        filing_record_id=result.filing_record_id,
        affected_filing_record_ids=list(result.affected_filing_record_ids),
        differing_casilla_ids=list(result.differing_casilla_ids),
        evidence_basis=result.evidence_basis,
        notices=[
            FilingReconciliationNoticePayload(code=notice.code, context=dict(notice.context))
            for notice in result.notices
        ],
    )


def filing_reconciliation_lines(results: Sequence[FilingReconciliationResult]) -> list[str]:
    """Render reconciliation outcomes as one tab-separated row per period."""
    lines = [
        f"reconciliation_count\t{len(results)}",
        "reconciliation.outcome\tmodelo\tyear\tperiod\tmember_nif\tfiling_record_id\t"
        "affected_filing_record_ids\tdiffering_casilla_ids\tevidence_basis\tnotice_codes",
    ]
    lines.extend(
        "\t".join(
            (
                result.outcome.value,
                result.modelo,
                str(result.filing_year),
                result.period.registry_token,
                result.member_nif or "",
                result.filing_record_id or "",
                ",".join(result.affected_filing_record_ids),
                ",".join(result.differing_casilla_ids),
                result.evidence_basis or "",
                ",".join(notice.code.value for notice in result.notices),
            )
        )
        for result in results
    )
    return lines


def _reconciliation_notice(result: FilingReconciliationResult, notice: FilingReconciliationNotice) -> Notice:
    context = {
        "outcome": result.outcome.value,
        "modelo": result.modelo,
        "filing_year": str(result.filing_year),
        "period": result.period.registry_token,
        **dict(notice.context),
    }
    if result.filing_record_id is not None:
        context["filing_record_id"] = result.filing_record_id
    return Notice(
        severity=NoticeSeverity.INFO if notice.code in _INFO_NOTICE_CODES else NoticeSeverity.WARNING,
        code=f"modelo.filing_chain.{notice.code.value}",
        message=tr(
            _RECONCILIATION_NOTICE_LOCALE_KEYS[notice.code],
            modelo=result.modelo,
            period=result.period.registry_token,
            filing_year=result.filing_year,
        ),
        context=context,
    )


def _contradiction_notice(result: FilingReconciliationResult) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.filing_chain.contradicted",
        message=tr(
            "cli.app.modelo.filing_record.reconciliation_contradicted",
            modelo=result.modelo,
            period=result.period.registry_token,
            filing_year=result.filing_year,
            casillas=", ".join(result.differing_casilla_ids),
        ),
        context={
            "modelo": result.modelo,
            "filing_year": str(result.filing_year),
            "period": result.period.registry_token,
            "filing_record_id": result.filing_record_id or "",
            "discrepant_filing_record_ids": ",".join(result.affected_filing_record_ids),
            "differing_casilla_ids": ",".join(result.differing_casilla_ids),
        },
    )


def filing_reconciliation_notices(results: Iterable[FilingReconciliationResult]) -> list[Notice]:
    """Project reconciliation conditions onto the envelope notices channel.

    A contradiction is always a warning: the operator's pending entry lost to
    what AEAT holds, and that must stay visible until it is resolved.
    """
    notices: list[Notice] = []
    for result in results:
        if result.outcome is FilingReconciliationOutcome.CONTRADICTED:
            notices.append(_contradiction_notice(result))
        notices.extend(_reconciliation_notice(result, notice) for notice in result.notices)
    return notices


def _layer_payload(envelope: ObservationEnvelopePayload | None) -> ObservationLayerPayload | None:
    if envelope is None:
        return None
    return ObservationLayerPayload(
        source_kind=envelope.source_kind,
        official_evidence=envelope.source_kind.is_official_aeat,
        captured_at=envelope.captured_at,
        stamped_revision_id=envelope.stamped_revision_id,
        casilla_values={
            casilla_id: str(value) for casilla_id, value in sorted(envelope.observation.casilla_values.items())
        },
    )


def _override_payload(override: ObservationOverride | None) -> ObservationOverridePayload | None:
    if override is None:
        return None
    return ObservationOverridePayload(
        actor=override.actor,
        reason=override.reason,
        recorded_at=override.recorded_at,
        replaced_source_kind=override.replaced_source_kind,
        replaced_values={casilla_id: str(value) for casilla_id, value in sorted(override.replaced_values.items())},
    )


def observation_layers_payload(layers: ObservationLayers) -> ObservationLayersPayload:
    """Project both observation layers and the pending layer's override audit."""
    pending = layers.pending_local
    effective = layers.effective
    return ObservationLayersPayload(
        official=_layer_payload(layers.official),
        pending_local=_layer_payload(pending),
        effective_source_kind=effective.source_kind if effective is not None else None,
        override=_override_payload(pending.override if pending is not None else None),
    )


def _layer_lines(name: str, layer: ObservationLayerPayload | None) -> list[str]:
    if layer is None:
        return [f"observation.{name}\tabsent"]
    lines = [
        f"observation.{name}.source_kind\t{layer.source_kind.value}",
        f"observation.{name}.official_evidence\t{str(layer.official_evidence).lower()}",
        f"observation.{name}.captured_at\t{layer.captured_at.isoformat()}",
        f"observation.{name}.stamped_revision_id\t{layer.stamped_revision_id}",
    ]
    lines.extend(
        f"observation.{name}.casilla\t{casilla_id}\t{value}" for casilla_id, value in layer.casilla_values.items()
    )
    return lines


def observation_layers_lines(payload: ObservationLayersPayload) -> list[str]:
    """Render both layers and any override audit as stable text lines."""
    lines = [
        *_layer_lines("official", payload.official),
        *_layer_lines("pending_local", payload.pending_local),
        "observation.effective_source_kind\t"
        + (payload.effective_source_kind.value if payload.effective_source_kind is not None else ""),
    ]
    override = payload.override
    if override is not None:
        lines.extend(
            (
                f"observation.override.actor\t{override.actor}",
                f"observation.override.reason\t{override.reason}",
                f"observation.override.recorded_at\t{override.recorded_at.isoformat()}",
                "observation.override.replaced_source_kind\t"
                + (override.replaced_source_kind.value if override.replaced_source_kind is not None else ""),
            )
        )
        lines.extend(
            f"observation.override.replaced\t{casilla_id}\t{value}"
            for casilla_id, value in override.replaced_values.items()
        )
    return lines
