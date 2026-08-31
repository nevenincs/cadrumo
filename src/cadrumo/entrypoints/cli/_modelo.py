"""User-facing modelo registry introspection commands.

These commands read the registry spine and render it for operators: the
:class:`ModeloDefinition` and its :class:`ModeloRevision` revisions for
structure and deadlines, and the :class:`CalculationRevision` produced when a
modelo is evaluated against a profile. Filed declarations are represented by
:class:`ModeloRecord` instances; lifecycle events are recorded to the profile
audit trail through :class:`BucketEventHistoryRepository`. The CLI surfaces
detailed :class:`CasillaObservation` data on command output.
"""

from __future__ import annotations

from decimal import Decimal

import typer

from ...application.modelo._action_errors import (
    AmendmentComplementariaLiabilityDecreaseError,
    AmendmentEvidenceMissingError,
    AmendmentKindNotPermittedError,
    AmendmentM303RectificativaMotiveError,
    AmendmentTargetStateError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    WorkUnitNotFoundError,
)
from ...application.modelo._amendment_actions import amend_modelo_revision
from ...application.modelo._work_lifecycle import lifecycle_continuation_for_work_history
from ...application.modelo.work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
)
from ...core import CasillaId, Modelo, validated_casilla_id
from ...core.decimal import try_parse_canonical_decimal
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.logging import get_logger
from ...domain.modelos.calculation_revision import CalculationRevisionAmendmentKind, M303RectificativaMotive
from ._common import activate_subcommand_output_language
from ._modelo_behavior_support import (
    require_active_profile as _require_active_profile,
)
from ._modelo_behavior_support import (
    resolve_work_unit_for_cli as _resolve_work_unit_for_cli,
)
from ._modelo_behavior_support import (
    work_address_for_cli as _work_address_for_cli,
)
from ._modelo_cli_support import (
    bad_parameter_from_error as _bad_parameter_from_error,
)
from ._modelo_cli_support import (
    parse_kv_spec as _parse_kv_spec,
)
from ._modelo_cli_support import resolve_default_actor as _resolve_default_actor
from ._modelo_cli_support import (
    selector_bad_parameter as _selector_bad_parameter,
)
from ._modelo_cli_support import (
    validate_casilla_key as _validate_casilla_key,
)
from ._modelo_rendering import (
    filing_record_lines as _filing_record_lines,
)
from ._modelo_rendering import (
    filing_record_payload as _filing_record_payload,
)
from ._modelo_rendering import (
    verification_report_lines as _verification_report_lines,
)
from ._modelo_rendering import (
    verification_report_payload as _verification_report_payload,
)

_log = get_logger(__name__)
_HEX_DIGITS = frozenset("0123456789abcdef")


_M200_M202_PAGOS_RELATION_IDS: frozenset[str] = frozenset(
    {
        "modelo-200-2024-rel-202-pagos-fraccionados",
        "modelo-200-2024-rel-202-pagos-fraccionados-40-2",
    },
)


def work_compare_taxation(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Compare conjunta vs. individual IRPF cuota for an existing Modelo 100 work unit.

    Runs the registry formula engine twice — once with
    ``declaration_type=2`` (tributación conjunta) and once with
    ``declaration_type=1`` (tributación individual) — over the
    same casilla inputs and profile bindings derived from the stored
    work unit. Outputs the cuota resultante autoliquidación (0595)
    and cuota diferencial (0610) for each mode plus the delta and a
    recommendation.

    This is an ephemeral operation: no revision is persisted.
    """
    from ._common import activate_subcommand_output_language, emit_envelope

    activate_subcommand_output_language(ctx, output_language)

    from ...application.modelo._action_errors import WorkUnitNotFoundError
    from ...application.modelo._taxation_comparison import (
        TaxationComparisonError,
        compare_taxation_for_work_address,
    )

    try:
        address = _work_address_for_cli(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        )
        comparison = compare_taxation_for_work_address(address)
    except (
        ModeloWorkAddressNotFoundError,
        ModeloWorkVisibleTargetAmbiguousError,
        ModeloWorkRevisionConflictError,
        ModeloWorkSelectorContradictionError,
        ModeloWorkUnitNotFoundError,
    ) as exc:
        raise _selector_bad_parameter(exc) from exc
    except WorkUnitNotFoundError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.compare_taxation_work_unit_not_found",
                work_unit_id=work_unit_id or "",
                default="Work unit {work_unit_id} not found; check 'aeat app modelo work list'.",
            ),
        ) from exc
    except TaxationComparisonError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.compare_taxation_error",
                detail=str(exc),
                default="Taxation comparison failed: {detail}",
            ),
        ) from exc

    from ._modelo_payloads import WorkCompareTaxationResult

    result = WorkCompareTaxationResult(
        filing_year=comparison.filing_year,
        modelo=Modelo(comparison.modelo),
        revision=comparison.revision,
        conjunta_cuota_resultante=str(comparison.conjunta_cuota_resultante),
        individual_cuota_resultante=str(comparison.individual_cuota_resultante),
        conjunta_resultado=str(comparison.conjunta_resultado),
        individual_resultado=str(comparison.individual_resultado),
        delta_resultado=str(comparison.delta_resultado),
        recommendation=comparison.recommendation,
        recommendation_reason=comparison.recommendation_reason,
        individual_branch_single_earner_only=comparison.individual_branch_single_earner_only,
    )
    from ._modelo_rendering import advisory_notice

    # Honesty caveat: the individual branch is faithful only for
    # a single-earner unidad familiar. Surface it on the typed notices channel so
    # an operator is never misled into trusting a two-earner individual figure the
    # comparator cannot compute.
    caveat_notice = (
        advisory_notice(
            "modelo.work.compare_taxation.individual_single_earner_only",
            comparison.individual_branch_caveat,
            context={"individual_branch_single_earner_only": "true"},
        )
        if comparison.individual_branch_single_earner_only
        else None
    )

    lines = [
        "operation\tmodelo.work.compare_taxation",
        f"filing_year\t{comparison.filing_year}",
        f"modelo\t{comparison.modelo}",
        f"revision\t{comparison.revision}",
        f"conjunta_cuota_resultante\t{comparison.conjunta_cuota_resultante}",
        f"individual_cuota_resultante\t{comparison.individual_cuota_resultante}",
        f"conjunta_resultado\t{comparison.conjunta_resultado}",
        f"individual_resultado\t{comparison.individual_resultado}",
        f"delta_resultado\t{comparison.delta_resultado}",
        f"recommendation\t{comparison.recommendation.value}",
        tr(
            "cli.app.modelo.work.compare_taxation_recommendation_line",
            recommendation=comparison.recommendation.value,
            reason=comparison.recommendation_reason,
            default="RECOMENDACIÓN: {recommendation} — {reason}",
        ),
    ]
    if caveat_notice is not None:
        lines.append(f"WARNING\t{comparison.individual_branch_caveat}")
    emit_envelope(
        ctx,
        command="modelo.work.compare_taxation",
        result=result,
        lines=lines,
        notices=[caveat_notice] if caveat_notice is not None else None,
    )


def work_history(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Assemble the chronological event stream for one work unit.

    Read-only aggregate over the bucket-event history catalogue and
    the four catalogues (work unit, calculation revision, verification
    report, filing record). Emits no bucket event.
    """
    activate_subcommand_output_language(ctx, output_language)
    from ...application.modelo._history import assemble_work_unit_history

    _require_active_profile()
    unit = _resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    history = assemble_work_unit_history(unit.work_unit_id)
    from ._common import emit_envelope, resolve_lifecycle_continuation_notice
    from ._modelo_payloads import WorkHistoryResult, WorkUnitHistoryEventPayload

    result = WorkHistoryResult(
        bucket_id=history.bucket_id,
        work_unit_id=history.work_unit_id,
        event_count=len(history.events),
        events=[
            WorkUnitHistoryEventPayload(
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                event_type=event.event_type,
                object_type=event.object_type,
                object_id=event.object_id,
                actor=event.actor,
                payload=event.payload,
            )
            for event in history.events
        ],
    )
    lines = [
        "operation\tmodelo.work.history",
        f"bucket_id\t{history.bucket_id}",
        f"work_unit_id\t{history.work_unit_id}",
        f"event_count\t{len(history.events)}",
        "occurred_at\tevent_type\tobject_type\tobject_id\tactor",
    ]
    lines.extend(
        "\t".join(
            (
                event.occurred_at.isoformat(),
                event.event_type.value,
                event.object_type.value,
                event.object_id,
                event.actor,
            ),
        )
        for event in history.events
    )
    next_step = resolve_lifecycle_continuation_notice(lifecycle_continuation_for_work_history(unit))
    emit_envelope(ctx, command="modelo.work.history", result=result, lines=lines, notices=[next_step])


def _parse_amendment_casilla(spec: str) -> tuple[CasillaId, Decimal]:
    def _to_decimal(value: str) -> Decimal:
        # An amendment restates a casilla on an already-filed declaration, so the
        # canonical euro-amount grammar applies at full strength: a bare Decimal
        # call admitted ``1e3``, ``+140000``, ``1_000``, ``.5``, and the
        # non-finite ``NaN``/``Infinity`` — and a NaN amount compares False to
        # every threshold, so an under-declaration advisory keyed on ``> 0``
        # would never fire for it.
        parsed = try_parse_canonical_decimal(value, max_fraction_digits=2)
        if parsed is None:
            raise typer.BadParameter(tr("cli.app.modelo.work.set_not_decimal", value=value))
        return parsed

    key, value = _parse_kv_spec(
        spec,
        flag="--set",
        key_label="CASILLA",
        value_label="DECIMAL",
        transform=_to_decimal,
        key_validator=_validate_casilla_key,
        strip_key=False,
    )
    return validated_casilla_id(key, surface="--set casilla"), value


def _required_amendment_inputs(
    *,
    from_filing_record_id: str | None,
    kind: CalculationRevisionAmendmentKind | None,
    reason: str | None,
    set_overrides: list[str] | None,
) -> tuple[str, CalculationRevisionAmendmentKind, str, tuple[str, ...]]:
    """Return raw amendment CLI inputs or raise one combined option error."""
    missing: list[str] = []
    if not from_filing_record_id or not from_filing_record_id.strip():
        missing.append("--from-filing-record")
    if kind is None:
        missing.append("--kind")
    if not reason or not reason.strip():
        missing.append("--reason")
    if not set_overrides:
        missing.append("--set")
    if missing:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.amend_missing_options",
                missing=", ".join(missing),
            ),
        )
    assert from_filing_record_id is not None
    assert kind is not None
    assert reason is not None
    return from_filing_record_id, kind, reason, tuple(set_overrides or ())


def _parse_amendment_overrides(set_overrides: tuple[str, ...]) -> dict[CasillaId, Decimal]:
    """Parse ``--set`` values into validated ``CasillaId`` decimal overrides."""
    overrides: dict[CasillaId, Decimal] = {}
    for spec in set_overrides:
        key, value = _parse_amendment_casilla(spec)
        overrides[key] = value
    if not overrides:
        raise typer.BadParameter(tr("cli.app.modelo.work.amend_set_required"))
    return overrides


def work_amend(
    ctx: typer.Context,
    from_filing_record_id: str | None = None,
    kind: CalculationRevisionAmendmentKind | None = None,
    reason: str | None = None,
    m303_rectificativa_motive: M303RectificativaMotive | None = None,
    actor: str | None = None,
    set_overrides: list[str] | None = None,
) -> None:
    """Build a complementaria amendment over an externally-filed return.

    The four required inputs (``--from-filing-record``, ``--kind``,
    ``--reason``, and at least one ``--set``) are batch-validated so a
    run missing several flags reports every absent one in a single
    refusal instead of forcing the operator to rediscover them one
    invocation at a time. The command then parses the requested
    :class:`CalculationRevisionAmendmentKind`, validates each override as a
    ``CasillaId`` decimal, delegates to
    :func:`amend_modelo_revision`, and emits a
    :class:`WorkAmendResult`.

    The application service requires the source
    :class:`ModeloRecord` to carry
    :class:`ExternalEvidence`; locally filed records cannot
    enter this path. The new record is an internal filing envelope and does not
    submit anything to AEAT.
    """
    from_filing_record_id, kind, reason, set_specs = _required_amendment_inputs(
        from_filing_record_id=from_filing_record_id,
        kind=kind,
        reason=reason,
        set_overrides=set_overrides,
    )
    _require_active_profile()
    overrides = _parse_amendment_overrides(set_specs)

    try:
        from ...adapters.persistence.profile.justificante import JustificanteRepository

        record = amend_modelo_revision(
            from_filing_record_id=from_filing_record_id,
            overrides=overrides,
            amendment_kind=kind,
            m303_rectificativa_motive=m303_rectificativa_motive,
            reason=reason,
            actor=actor or _resolve_default_actor(),
            justificante_repository=JustificanteRepository(),
        )
    except (
        ModeloRecordNotFoundError,
        AmendmentEvidenceMissingError,
        AmendmentTargetStateError,
        AmendmentKindNotPermittedError,
        AmendmentM303RectificativaMotiveError,
        AmendmentComplementariaLiabilityDecreaseError,
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import emit_envelope
    from ._modelo_payloads import WorkAmendResult

    result = WorkAmendResult.model_validate(
        {
            "amendment_kind": kind.value,
            "m303_rectificativa_motive": m303_rectificativa_motive,
            "amends_filing_record_id": from_filing_record_id,
            **_filing_record_payload(record).model_dump(mode="python"),
        },
    )
    lines = [
        "operation\tmodelo.work.amend",
        f"amendment_kind\t{kind.value}",
        f"m303_rectificativa_motive\t{m303_rectificativa_motive.value if m303_rectificativa_motive else ''}",
        f"amends_filing_record_id\t{from_filing_record_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    emit_envelope(ctx, command="modelo.work.amend", result=result, lines=lines)


# ─────────────────────────────────────────────────────────────────────────
# History verb
# ─────────────────────────────────────────────────────────────────────────


def modelo_history(
    ctx: typer.Context,
    modelo: str,
    year: int | None = None,
    period: str | None = None,
) -> None:
    """Stream the bucket-event history for one modelo across all lifecycle stages."""
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...domain.buckets import BucketEvent, BucketEventType

    def _event_filing_year(payload: dict[str, str]) -> str:
        return (payload.get("filing_year") or payload.get("year") or "").strip()

    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    modelo_event_types = {
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_VERIFICATION_PASSED,
        BucketEventType.MODELO_VERIFICATION_REFUSED,
        BucketEventType.MODELO_EXPORTED,
        BucketEventType.MODELO_FILED,
        BucketEventType.MODELO_FILED_SUPERSEDED,
        BucketEventType.MODELO_AMENDED,
        BucketEventType.MODELO_FILING_IMPORTED,
        BucketEventType.MODELO_WORK_UNIT_DISCARDED,
        BucketEventType.MODELO_AUDIT_VERIFIED,
        BucketEventType.MODELO_AUDIT_EXPORTED,
    }
    matches: list[BucketEvent] = []
    for event in catalogue.events.values():
        if event.event_type not in modelo_event_types:
            continue
        payload_map = dict(event.payload)
        if payload_map.get("modelo", "") != modelo:
            continue
        if year is not None and _event_filing_year(payload_map) != str(year):
            continue
        if period is not None and payload_map.get("period", "") != period:
            continue
        matches.append(event)
    matches.sort(key=lambda e: e.occurred_at)
    from ._common import emit_envelope
    from ._modelo_payloads import ModeloHistoryResult, ModeloLifecycleEventPayload

    history_result = ModeloHistoryResult(
        modelo=modelo,
        year=year,
        period=period,
        count=len(matches),
        events=[
            ModeloLifecycleEventPayload(
                event_id=e.event_id,
                event_type=e.event_type,
                occurred_at=e.occurred_at,
                actor=e.actor,
                object_type=e.object_type,
                object_id=e.object_id,
                payload=dict(e.payload),
            )
            for e in matches
        ],
    )
    lines = [f"modelo\t{modelo}", f"count\t{len(matches)}"]
    for e in matches:
        lines.append(f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_id}\t{e.actor}")
    emit_envelope(ctx, command="modelo.history", result=history_result, lines=lines)


__all__ = [
    "_verification_report_lines",
    "_verification_report_payload",
    "modelo_history",
    "work_amend",
    "work_compare_taxation",
    "work_history",
]
