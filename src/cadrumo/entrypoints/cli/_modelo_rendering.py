"""Projection helpers shared by modelo CLI command groups.

This module turns modelo application/domain records such as
:class:`~WorkUnit`,
:class:`~CalculationRevision`,
:class:`~ModeloRecord`,
:class:`~VerificationReport`, and
:class:`~cadrumo.application.modelo.work_plazo.ModeloWorkDeadlinePosture` into CLI text lines
and CommandSpec-declared JSON payload fragments. The payload side feeds
:class:`~cadrumo.entrypoints.cli._modelo_payloads.WorkUnitPayload`,
:class:`~cadrumo.entrypoints.cli._modelo_payloads.CalculationRevisionPayload`,
:class:`~cadrumo.entrypoints.cli._modelo_payloads.ModeloRecordPayload`,
:class:`~cadrumo.entrypoints.cli._modelo_payloads.VerificationReportPayload`,
and uniform :class:`~cadrumo.core.json_contract.Notice` rows into
:func:`~cadrumo.entrypoints.cli.common.emit_envelope`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...application.modelo.lifecycle_advisories import Modelo184SocioHandoffV1
from ...application.modelo.verification_preconditions import VerificationFindingPreconditionProjection
from ...application.modelo.work_plazo import (
    M210PlazoResolution,
    ModeloWorkDeadlinePosture,
    modelo_work_deadline_posture,
)
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity, ResolvedPreconditionAction
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.filing_record import ModeloRecord
from ...domain.modelos.verification_report import ModeloVerificationFinding, VerificationReport
from ...domain.modelos.work_unit import WorkUnit
from ._action_rendering import resolved_precondition_action_json_cell
from ._filing_chain_payloads import aeat_register_lines, aeat_register_payload
from ._modelo_bindings_payloads import BindingEncodedOptionPayload
from ._modelo_payloads import (
    ExternalEvidencePayload,
    FindingPayload,
    ModeloRecordPayload,
    VerificationReportPayload,
    WorkConditionalRecargoPreviewPayload,
    WorkDeadlinePosturePayload,
    WorkUnitPayload,
)
from .common import resolve_cli_precondition_action
from .modelo_revision_rendering import calculation_revision_state_label

if TYPE_CHECKING:
    # Annotation-only: `from __future__ import annotations` keeps this lazy so the
    # state-free CLI surface pays no runtime aggregation-import cost, matching the
    # calculate module's own deferral of the same type.
    from ...application.aggregation.source_mesh import CalculationSourceDiagnostic
    from ...application.modelo.printed_boxes import PrintedBoxes


def _modelo_rendering_value(key: str) -> str:
    """Resolve one registry-owned rendering declaration lazily at the CLI seam."""
    from ...domain.calculations.registry.modelo_rendering import modelo_rendering_value

    return modelo_rendering_value(key)


def m210_plazo_notice(resolution: M210PlazoResolution) -> Notice:
    """Render the resolved Modelo 210 filing window as an operator notice.

    The application layer resolves the window and hands back facts; the
    prose is built here, which is the only layer allowed to localize. The
    notice context is the resolution's own metadata, so the JSON envelope and
    the text line cannot describe different windows.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="modelo.work.m210.plazo_resolved",
        message=tr(
            "cli.app.modelo.work.m210_plazo_resolved",
            closes_on=resolution.closes_on,
        ),
        context=dict(resolution.context),
    )


def m184_socio_handoff_advisory_notices(handoffs: Sequence[Modelo184SocioHandoffV1]) -> list[Notice]:
    """Render the writer's exact grounded handoffs without reopening a revision."""
    return [
        _m184_socio_handoff_notice(
            nif=handoff.nif,
            nombre=handoff.nombre,
            porcentaje=Decimal(handoff.porcentaje),
            importe=Decimal(handoff.importe),
            code=handoff.code,
            target_casilla=handoff.target_casilla,
            legal_refs=handoff.legal_refs,
        )
        for handoff in handoffs
    ]


def _m184_socio_handoff_notice(
    *, nif: str, nombre: str, porcentaje: Decimal, importe: Decimal, code: str, target_casilla: str, legal_refs: str
) -> Notice:
    return Notice(
        severity=NoticeSeverity.INFO,
        code=code,
        message=tr(
            "cli.app.modelo.work.m184_socio_handoff_message",
            nif=nif,
            nombre=nombre,
            importe=importe,
            porcentaje=porcentaje,
            casilla=target_casilla,
        ),
        context={
            "nif": nif,
            "nombre": nombre,
            "porcentaje": str(porcentaje),
            "base_imponible_attributed": str(importe),
            "target_casilla": target_casilla,
            "legal_refs": legal_refs,
        },
    )


def binding_encoded_option_lines(
    binding_id: str,
    options: tuple[BindingEncodedOptionPayload, ...],
) -> list[str]:
    """Render one data-derived text hint enumerating a boolean binding's 0/1 encoding.

    Emitted only for a decimal-channel boolean binding, so the operator can read
    the ``--binding`` decimal-to-meaning mapping (e.g. ``1=true(N)  0=false(S)``)
    straight from the ``bindings list`` / ``bindings resolve`` output. The mapping
    is derived from the binding definition, so no prose is localised here.
    """
    if not options:
        return []
    mapping = "  ".join(
        f"{option.encoded_value}={'true' if option.boolean_meaning else 'false'}({option.registry_value})"
        for option in options
    )
    return [f"encoded_option\t{binding_id}\t{mapping}"]


def advisory_notice(
    code: str,
    message: str,
    *,
    context: dict[str, str] | None = None,
) -> Notice:
    """Project a non-blocking modelo advisory message onto the envelope notices channel.

    The single projection point that turns an incidental, non-blocking
    modelo diagnostic (source-resolution advisory, unauthorized-backend
    advisory, filing-obligation advisory) into a warning-severity
    :class:`~cadrumo.core.json_contract.Notice`. Command groups call this instead
    of re-modelling the advisory as a bespoke ``*_advisory`` payload field, so
    every advisory flows through the one uniform notices surface. ``context``
    carries any structured provenance the former bespoke payload exposed (e.g.
    the source-resolution ``reason`` / ``source_kind``).
    """
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=code,
        message=message,
        context=context,
    )


_LEVEL_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "blocks": "tui.modelo.workbench.level.blocks",
        "missing": "tui.modelo.workbench.origin.needs_input",
        "confirm": "tui.modelo.workbench.origin.default_to_confirm",
        "check": "tui.modelo.workbench.level.check",
        "info": "tui.modelo.workbench.level.info",
    }
)
"""The words of each level, by the level's value, the ones the editor's findings list heads them with."""
_UNNUMBERED_BOX_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.box_unnumbered"


def source_diagnostic_notice(
    diagnostic: CalculationSourceDiagnostic,
    *,
    code: str,
    boxes: PrintedBoxes | None = None,
) -> Notice:
    """Project one source diagnostic onto a notice whose context is routable.

    The message is the catalogue's sentence for the diagnostic's reason, and
    the context carries its place on the same scale the editor's findings list
    uses (``level``), the printed box it names (``box``), and the calculation's
    own technical account (``detail``). ``boxes`` are the boxes the revision's
    form prints, which decide whether the box is one the form prints and its number.

    The single projection for source-resolution advisories, shared by every
    command that emits them so their context cannot diverge per call site.

    Every field an operator would otherwise have to recover by parsing the
    message is carried as a structured context key. That is the point rather than
    a convenience: a machine-readable caller routes on
    fields, and a context of only ``reason`` / ``source_kind`` / ``resolver_id`` is
    IDENTICAL across every carry advisory on a revision, so two advisories about
    two different casillas were indistinguishable except by prose. A typed channel
    whose context never varies is typed in shape only.

    Keys are omitted rather than written empty when the diagnostic does not carry
    them, so absence means "this diagnostic has no such subject" rather than "the
    subject is blank".
    """
    context = {
        "reason": str(diagnostic.reason),
        "source_kind": diagnostic.source_kind,
    }
    optional: dict[str, str | None] = {
        "resolver_id": diagnostic.resolver_id,
        "binding_source": diagnostic.binding_source.value if diagnostic.binding_source else None,
        "binding_id": diagnostic.binding_id,
        "relation_id": diagnostic.relation_id,
        "casilla_id": diagnostic.casilla_id,
        "source_ref": diagnostic.source_ref,
        # Grounding, rendered as the joined registry identifiers rather than
        # dropped. An advisory about a regulated figure carries the provisions
        # that establish it, and this projection is the only surface an operator
        # reads it from -- refs left on the model and not projected here would be
        # grounding that reaches nobody. Empty tuples join to "" and are filtered
        # out below, so an ungrounded advisory omits the keys rather than
        # claiming a blank provision.
        "legal_refs": ", ".join(diagnostic.legal_refs),
        "source_refs": ", ".join(diagnostic.source_refs),
        # Non-command remediation stays distinct from the diagnosis so machine
        # consumers need not recover it from prose. Executable command identity
        # remains reserved for Notice.action by the Notice validator.
        "remedy": diagnostic.remedy,
    }
    from ...application.modelo.calculation_notes import note_attention, what_locale_key
    from ...application.modelo.work_form_models import ModeloFormAttention

    box = None if boxes is None or diagnostic.casilla_id is None else boxes.number(str(diagnostic.casilla_id))
    attention = note_attention(diagnostic.reason, box=box)
    context.update({key: value for key, value in optional.items() if value})
    context.update({"level": attention.value, "detail": diagnostic.message, **({} if box is None else {"box": box})})
    return Notice(
        severity=NoticeSeverity.INFO if attention is ModeloFormAttention.INFO else NoticeSeverity.WARNING,
        code=code,
        message=tr(what_locale_key(diagnostic.reason), box=_box_words(box)),
        context=context,
    )


def _box_words(box: str | None) -> str:
    return box if box is not None else tr(_UNNUMBERED_BOX_LOCALE_KEY)


def source_diagnostic_notice_text(notice: Notice) -> str:
    """Render one diagnosis as the editor's findings list does: its level, what happened, and what to do."""
    from ...application.modelo.calculation_notes import what_to_do_locale_key

    context = notice.context or {}
    action = tr(what_to_do_locale_key(context["reason"]), box=_box_words(context.get("box")))
    return f"{tr(_LEVEL_LOCALE_KEYS[context['level']])}: {notice.message} {action}"


def short_id(value: str | None) -> str | None:
    """Return the display suffix for a content-addressed id."""
    return value[-12:] if value else None


def _short_id_text(value: str | None) -> str:
    """Return the display suffix for a content-addressed id, blank when absent.

    The text-rendering companion to :func:`short_id`, whose ``str | None``
    return otherwise makes every rendering call site restate the same
    blank-for-absent fallback.
    """
    return short_id(value) or ""


def _effective_work_unit_state(unit: WorkUnit) -> str:
    state = unit.state.value
    if state == "descartado":
        return state
    if unit.filed_calculation_revision_id is not None:
        return CalculationRevisionState.PRESENTADO.value
    return state


def work_unit_payload(unit: WorkUnit) -> WorkUnitPayload:
    return WorkUnitPayload(
        work_unit_id=unit.work_unit_id,
        short_work_unit_id=short_id(unit.work_unit_id) or "",
        bucket_id=unit.bucket_id,
        modelo=str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
        revision_id=unit.revision_id,
        name=unit.name,
        state=_effective_work_unit_state(unit),
        current_calculation_revision_id=unit.current_calculation_revision_id,
        short_current_calculation_revision_id=short_id(unit.current_calculation_revision_id),
        filed_calculation_revision_id=unit.filed_calculation_revision_id,
        short_filed_calculation_revision_id=short_id(unit.filed_calculation_revision_id),
        current_filing_record_id=unit.current_filing_record_id,
        created_at=unit.created_at.isoformat(),
        updated_at=unit.updated_at.isoformat(),
        discarded_at=unit.discarded_at.isoformat() if unit.discarded_at else None,
        discarded_by=unit.discarded_by,
        discard_reason=unit.discard_reason,
        causante_ccaa=unit.causante_ccaa.value if unit.causante_ccaa is not None else None,
    )


def work_unit_lines(unit: WorkUnit, *, include_bucket_id: bool = True) -> list[str]:
    lines = [
        f"work_unit_id\t{unit.work_unit_id}",
        f"short_work_unit_id\t{_short_id_text(unit.work_unit_id)}",
        f"modelo\t{unit.modelo}",
        f"filing_year\t{unit.filing_year}",
        f"period\t{unit.period.registry_token}",
        f"revision_id\t{unit.revision_id}",
        f"name\t{unit.name}",
        f"state\t{calculation_revision_state_label(_effective_work_unit_state(unit))}",
        f"current_calculation_revision_id\t{unit.current_calculation_revision_id or ''}",
        f"short_current_calculation_revision_id\t{_short_id_text(unit.current_calculation_revision_id)}",
        f"filed_calculation_revision_id\t{unit.filed_calculation_revision_id or ''}",
        f"short_filed_calculation_revision_id\t{_short_id_text(unit.filed_calculation_revision_id)}",
        f"current_filing_record_id\t{unit.current_filing_record_id or ''}",
        f"created_at\t{unit.created_at.isoformat()}",
        f"updated_at\t{unit.updated_at.isoformat()}",
    ]
    if include_bucket_id:
        lines.insert(2, f"bucket_id\t{unit.bucket_id}")
    if unit.discarded_at is not None:
        lines.append(f"discarded_at\t{unit.discarded_at.isoformat()}")
    if unit.discarded_by is not None:
        lines.append(f"discarded_by\t{unit.discarded_by}")
    if unit.discard_reason is not None:
        lines.append(f"discard_reason\t{unit.discard_reason}")
    if unit.causante_ccaa is not None:
        lines.append(f"causante_ccaa\t{unit.causante_ccaa.value}")
    lines.extend(work_unit_plazo_lines(unit))
    return lines


def work_unit_list_lines(units: Sequence[WorkUnit], *, include_discarded: bool) -> list[str]:
    lines = [
        "operation\tmodelo.work.list",
        f"include_discarded\t{include_discarded}",
        f"work_unit_count\t{len(units)}",
        "short_work_unit_id\twork_unit_id\tmodelo\tyear\tperiod\trevision_id\tstate\tcurrent_revision\tfiled_revision\tname",
    ]
    lines.extend(
        "\t".join(
            (
                short_id(unit.work_unit_id) or "",
                unit.work_unit_id,
                str(unit.modelo),
                str(unit.filing_year),
                unit.period.registry_token,
                unit.revision_id,
                calculation_revision_state_label(_effective_work_unit_state(unit)),
                short_id(unit.current_calculation_revision_id) or "",
                short_id(unit.filed_calculation_revision_id) or "",
                unit.name,
            ),
        )
        for unit in units
    )
    return lines


def work_unit_plazo_lines(unit: WorkUnit) -> list[str]:
    """Render deadline posture and unassessed preview lines for the work unit."""
    return work_plazo_lines_from_posture(modelo_work_deadline_posture(unit))


def work_plazo_lines_from_posture(posture: ModeloWorkDeadlinePosture | None) -> list[str]:
    """Render a deadline posture already resolved by the canonical application."""
    if posture is None:
        return []

    out: list[str] = [
        f"plazo_closes_on\t{posture.closes_on.isoformat()}",
        f"plazo_nominal_closes_on\t{posture.nominal_closes_on.isoformat()}",
        f"plazo_holiday_coverage\t{posture.holiday_coverage.value}",
    ]
    if posture.days_remaining is not None:
        out.append(
            tr(
                "cli.app.modelo.work.plazo_days_remaining",
                days_remaining=posture.days_remaining,
            ),
        )
        return out

    if posture.days_overdue is None:
        return out

    out.append(f"days_overdue\t{posture.days_overdue}")
    preview = posture.conditional_recargo_preview
    if preview is None:
        out.append(
            tr(
                "cli.app.modelo.work.plazo_vencido_sin_previsualizacion_warning",
            ),
        )
        return out

    out.extend(
        [
            f"conditional_recargo_preview_band\t{preview.band_id}",
            f"conditional_recargo_preview_pct\t{preview.surcharge_pct}",
            f"conditional_recargo_preview_interest_applies\t{preview.interest_applies}",
            f"conditional_recargo_preview_reference_on\t{preview.rate_reference_on.isoformat()}",
            f"conditional_recargo_preview_assessment_status\t{preview.assessment_status}",
            f"conditional_recargo_preview_legal_ref\t{preview.legal_ref}",
            tr(
                "cli.app.modelo.work.plazo_vencido_warning",
            ),
        ],
    )
    return out


def _work_unit_deadline_output_from_posture(
    posture: ModeloWorkDeadlinePosture | None,
    *,
    fallback_legal_ref: str | None = None,
) -> tuple[WorkDeadlinePosturePayload | None, list[Notice]]:
    """Project deadline posture onto a payload and unassessed-preview notice.

    Returns the typed
    :class:`~cadrumo.entrypoints.cli._modelo_payloads.WorkDeadlinePosturePayload`
    (structured result data: the voluntary-filing close date and overdue
    posture) and a warning-severity
    :class:`~cadrumo.core.json_contract.Notice` list. An overdue deadline raises
    one notice that says no Article 27 surcharge or interest liability is
    determined. If available, its context carries a rate-only unassessed
    preview. An in-time (or unknown) deadline raises no notice.
    """
    if posture is None:
        return None, []

    preview_payload = None
    preview = posture.conditional_recargo_preview
    if preview is not None:
        preview_payload = WorkConditionalRecargoPreviewPayload(
            band_id=preview.band_id,
            surcharge_pct=str(preview.surcharge_pct),
            interest_applies=preview.interest_applies,
            legal_ref=preview.legal_ref,
            rate_reference_on=preview.rate_reference_on.isoformat(),
            assessment_status=preview.assessment_status,
        )
    deadline_payload = WorkDeadlinePosturePayload(
        closes_on=posture.closes_on,
        nominal_closes_on=posture.nominal_closes_on,
        holiday_coverage=posture.holiday_coverage,
        days_remaining=posture.days_remaining,
        days_overdue=posture.days_overdue,
        conditional_recargo_preview=preview_payload,
    )

    if posture.days_overdue is None or posture.days_overdue < 1:
        return deadline_payload, []

    warning_text = tr(
        (
            "cli.app.modelo.work.plazo_vencido_warning"
            if preview is not None
            else "cli.app.modelo.work.plazo_vencido_sin_previsualizacion_warning"
        ),
    )
    context: dict[str, str] = {
        "closes_on": posture.closes_on.isoformat(),
        "nominal_closes_on": posture.nominal_closes_on.isoformat(),
        "holiday_coverage": posture.holiday_coverage.value,
        "days_overdue": str(posture.days_overdue),
        "article_27_assessment_status": "unassessed",
    }
    if preview is not None:
        context["legal_refs"] = preview.legal_ref
        context["conditional_recargo_preview_band"] = preview.band_id
        context["conditional_recargo_preview_pct"] = str(preview.surcharge_pct)
        context["conditional_recargo_preview_interest_applies"] = str(preview.interest_applies)
        context["conditional_recargo_preview_reference_on"] = preview.rate_reference_on.isoformat()
    else:
        # The deadline posture remains known even when preview resolution fails.
        context["legal_refs"] = fallback_legal_ref or _modelo_rendering_value("extemporaneous_recargo.legal_ref")
    return deadline_payload, [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="modelo.work.calculate.plazo_vencido_unassessed_preview",
            message=warning_text,
            context=context,
        ),
    ]


def work_deadline_output_from_posture(
    posture: ModeloWorkDeadlinePosture | None, *, fallback_legal_ref: str | None
) -> tuple[WorkDeadlinePosturePayload | None, list[Notice]]:
    """Render pinned deadline facts without rereading the registry or the clock."""
    if (
        posture is not None
        and posture.days_overdue is not None
        and posture.conditional_recargo_preview is None
        and fallback_legal_ref is None
    ):
        raise ValueError("an overdue posture without preview requires its pinned legal reference")
    return _work_unit_deadline_output_from_posture(posture, fallback_legal_ref=fallback_legal_ref)


def casilla_inline_trace(obs: CasillaObservation) -> str | None:
    """Render the inline formula trace for one computed casilla observation.

    Returns the ``op(refs) = op(values) = value`` trace string for a formula
    observation (a :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`
    whose ``formula_id`` and ``op`` are set), sourced entirely from the
    already-computed operand lineage on the typed observation. Returns ``None``
    for an input / bound casilla that carries no formula, so those rows render
    their value only, as before.
    """
    if obs.formula_id is None or obs.op is None:
        return None
    value = str(obs.value)
    operation = _formula_operation_label(obs.op)
    if obs.operand_refs:
        symbolic = f"{operation}({', '.join(obs.operand_refs)})"
        evaluated = f"{operation}({', '.join(str(operand) for operand in obs.operand_values)})"
        return f"{symbolic} = {evaluated} = {value}"
    return f"{operation} = {value}"


#: Comparison operations render as their bare relational symbol (never a
#: localised word), so they are resolved before the localised label table.
_FORMULA_COMPARISON_SYMBOLS: dict[str, str] = {
    "less_than": "<",
    "less_equal": "≤",
    "greater_than": ">",
    "greater_equal": "≥",
    "equal": "=",
}

#: Formula operation code -> (translation key, English default) for the
#: localised operation labels. Every ``add``/``sum`` family member shares the
#: single sum label; each remaining operation maps to its own leaf. Named as a
#: ``_LOCALE_KEYS`` registry so the locale scaffold's AST scanner discovers the
#: keys for parity — they are selected from this table rather than passed to
#: ``tr()`` as literals at the call site.
_FORMULA_OPERATION_LABEL_LOCALE_KEYS: dict[str, tuple[str, str]] = {
    "add": ("cli.app.modelo.work.formula_operation_sum", "sum"),
    "sum": ("cli.app.modelo.work.formula_operation_sum", "sum"),
    "previous_period_sum": ("cli.app.modelo.work.formula_operation_sum", "sum"),
    "cross_model_sum": ("cli.app.modelo.work.formula_operation_sum", "sum"),
    "subtract": ("cli.app.modelo.work.formula_operation_subtract", "subtract"),
    "multiply": ("cli.app.modelo.work.formula_operation_multiply", "multiply"),
    "divide": ("cli.app.modelo.work.formula_operation_divide", "divide"),
    "percent": ("cli.app.modelo.work.formula_operation_percent", "percentage"),
    "min": ("cli.app.modelo.work.formula_operation_minimum", "minimum"),
    "max": ("cli.app.modelo.work.formula_operation_maximum", "maximum"),
    "if_then_else": ("cli.app.modelo.work.formula_operation_conditional", "conditional"),
    "copy": ("cli.app.modelo.work.formula_operation_copy", "copy"),
    "negate": ("cli.app.modelo.work.formula_operation_negate", "negation"),
    "clamp": ("cli.app.modelo.work.formula_operation_clamp", "limit"),
    "previous_period_value": ("cli.app.modelo.work.formula_operation_previous_period", "previous period"),
}


def _formula_operation_label(operation: str) -> str:
    symbol = _FORMULA_COMPARISON_SYMBOLS.get(operation)
    if symbol is not None:
        return symbol
    if operation.startswith("lookup_"):
        return tr(
            "cli.app.modelo.work.formula_operation_lookup",
        )
    entry = _FORMULA_OPERATION_LABEL_LOCALE_KEYS.get(operation)
    if entry is None:
        return tr(
            "cli.app.modelo.work.formula_operation_calculation",
        )
    key, _default = entry
    return tr(
        key,
    )


def casilla_trace_verbose_line(obs: CasillaObservation) -> str:
    """Render the full LedgerEntry detail for one computed casilla observation.

    Exposes the complete typed
    :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation` trace -
    ``op``, ``formula_id``, ``operand_refs``, ``operand_casilla_refs`` and
    ``operand_values`` - on a single tab-delimited line beneath its casilla row
    when the operator passes ``--verbose``.
    """
    return "\t".join(
        (
            f"  trace\t{obs.casilla_id}",
            f"op={obs.op or ''}",
            f"formula_id={obs.formula_id or ''}",
            f"operand_refs={','.join(obs.operand_refs)}",
            f"operand_casilla_refs={','.join(obs.operand_casilla_refs)}",
            f"operand_values={','.join(str(operand) for operand in obs.operand_values)}",
        ),
    )


def filing_record_payload(record: ModeloRecord) -> ModeloRecordPayload:
    """Project a :class:`~ModeloRecord` into :class:`ModeloRecordPayload` JSON form.

    When the record carries :class:`~ExternalEvidence`, the
    evidence fields are nested in :class:`ExternalEvidencePayload`; local filing
    records still render with ``live_submission=False``.
    """
    external_evidence: ExternalEvidencePayload | None = None
    if record.external_evidence is not None:
        external_evidence = ExternalEvidencePayload(
            kind=record.external_evidence.kind,
            reference_id=record.external_evidence.reference_id,
            imported_at=record.external_evidence.imported_at,
        )
    return ModeloRecordPayload(
        filing_record_id=record.filing_record_id,
        work_unit_id=record.work_unit_id,
        calculation_revision_id=record.calculation_revision_id,
        bucket_id=record.bucket_id,
        modelo=record.modelo,
        filing_year=record.filing_year,
        period=record.period,
        filed_at=record.filed_at,
        filed_by=record.filed_by,
        member_nif=record.member_nif,
        notes=record.notes,
        origin=record.origin,
        confirmation=record.confirmation,
        declaration_kind=record.declaration_kind,
        aeat_register=aeat_register_payload(record.aeat_register),
        aeat_accepted=record.aeat_accepted,
        status=record.status,
        superseded_at=record.superseded_at,
        superseded_by_filing_record_id=record.superseded_by_filing_record_id,
        external_evidence=external_evidence,
        amends_filing_record_id=record.amends_filing_record_id,
        kind="internal_filing",
        live_submission=False,
    )


def filing_record_lines(record: ModeloRecord | ModeloRecordPayload) -> list[str]:
    """Render a :class:`~ModeloRecord` as stable text lines.

    External evidence, when present, is printed as explicit
    ``external_evidence.*`` fields rather than being folded into local filing
    state.
    """
    lines = [
        f"filing_record_id\t{record.filing_record_id}",
        f"work_unit_id\t{record.work_unit_id}",
        f"calculation_revision_id\t{record.calculation_revision_id}",
        f"bucket_id\t{record.bucket_id}",
        f"modelo\t{record.modelo}",
        f"filing_year\t{record.filing_year}",
        f"period\t{record.period.registry_token}",
        f"filed_at\t{record.filed_at.isoformat()}",
        f"filed_by\t{record.filed_by}",
        f"status\t{record.status.value}",
        f"origin\t{record.origin.value}",
        f"confirmation\t{record.confirmation.value}",
        f"declaration_kind\t{record.declaration_kind.value}",
        f"aeat_accepted\t{str(record.aeat_accepted).lower()}",
    ]
    if record.member_nif is not None:
        lines.append(f"member_nif\t{record.member_nif}")
    lines.extend(aeat_register_lines(record.aeat_register))
    if record.notes is not None:
        lines.append(f"notes\t{record.notes}")
    if record.superseded_at is not None:
        lines.append(f"superseded_at\t{record.superseded_at.isoformat()}")
    if record.superseded_by_filing_record_id is not None:
        lines.append(f"superseded_by_filing_record_id\t{record.superseded_by_filing_record_id}")
    if record.external_evidence is not None:
        lines.append(f"external_evidence.kind\t{record.external_evidence.kind.value}")
        lines.append(f"external_evidence.reference_id\t{record.external_evidence.reference_id}")
        lines.append(f"external_evidence.imported_at\t{record.external_evidence.imported_at.isoformat()}")
    if record.amends_filing_record_id is not None:
        lines.append(f"amends_filing_record_id\t{record.amends_filing_record_id}")
    lines.append("kind\tinternal_filing")
    lines.append("live_submission\tfalse")
    return lines


def verification_findings_notices(findings: Sequence[ModeloVerificationFinding]) -> list[Notice]:
    """Project verification findings onto the envelope notices channel.

    A verify run that is NOT granted ``verificado_completo`` carries
    blocking and/or warning findings; without this projection the JSON
    envelope reported ``status: "success"`` with an empty ``notices`` list
    while the exit code was 1 and ``result.findings`` held blocking findings
    — a contract break against
    :func:`cadrumo.core.json_contract.derive_status`, which derives the
    envelope ``status`` from notice severity in lock-step with the
    core error-category exit mapping. Each
    :class:`~ModeloVerificationFinding` becomes one
    :class:`~cadrumo.core.json_contract.Notice`.

    Severity mapping: both ``BLOCKING`` and ``WARNING`` finding severities
    map to :attr:`NoticeSeverity.WARNING`. ``NoticeSeverity`` carries no
    ``ERROR`` member (success/warning ride the stdout spine; ``error`` is
    reserved for the stderr error envelope), and a single warning notice is
    sufficient to resolve the envelope to :attr:`EnvelopeStatus.WARNING` — a
    non-``success`` status that matches the exit-1 a not-granted verify
    raises. The finding's actual ``severity`` and ``kind`` are preserved on
    :attr:`Notice.context` so a machine consumer can still distinguish a
    blocking finding from an advisory one. ``legal_refs`` / ``source_refs``
    ride on the context too, mirroring the regulatory grounding the
    text-mode ``finding_legal_refs`` lines render. Recovery remains only on the
    typed finding action in the command result; a notice never infers an
    executable action from a finding kind or message. Every validated,
    locale-neutral ``message_facts`` entry is copied onto the same context as a
    string so native blocker codes and their coordinates remain machine-readable
    on the envelope rather than surviving only as interpolation inputs.

    A granted (clean) verify carries no findings, so this returns an empty
    list and the envelope stays :attr:`EnvelopeStatus.SUCCESS`.
    """
    notices: list[Notice] = []
    for finding in findings:
        context: dict[str, str] = {
            "severity": finding.severity.value,
            "kind": finding.kind.value,
        }
        if finding.casilla_id is not None:
            context["casilla_id"] = finding.casilla_id
        if finding.expectation_id is not None:
            context["expectation_id"] = finding.expectation_id
        if finding.legal_refs:
            context["legal_refs"] = ", ".join(finding.legal_refs)
        if finding.source_refs:
            context["source_refs"] = ", ".join(finding.source_refs)
        for key, value in finding.message_facts.items():
            rendered_value = str(value)
            existing_value = context.get(key)
            if existing_value is not None and existing_value != rendered_value:
                raise ValueError(
                    f"verification finding fact {key!r} conflicts with its notice context value",
                )
            context[key] = rendered_value
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=f"modelo.work.verify.finding.{finding.kind.value}",
                message=_render_verification_finding_message(finding),
                context=context,
            ),
        )
    return notices


def verification_report_notices(report: VerificationReport) -> list[Notice]:
    """Project one persisted report's findings through the canonical helper."""
    return verification_findings_notices(report.findings)


def _resolved_finding_actions(
    report: VerificationReport,
    finding_preconditions: Sequence[VerificationFindingPreconditionProjection] | None,
) -> tuple[ResolvedPreconditionAction | None, ...]:
    """Resolve only the application-supplied verdicts paired to ``report``.

    A persisted report intentionally has no recovery projection: its findings
    are audit facts, not a transport for historical command reconstruction.
    When a live verification supplies projections, their exact report order is
    mandatory so the CLI cannot assign an action by matching prose or a kind.
    """
    if finding_preconditions is None:
        return (None,) * len(report.findings)
    if tuple(projection.finding for projection in finding_preconditions) != report.findings:
        raise ValueError("verification finding preconditions must match the report in order")
    return tuple(
        (
            resolve_cli_precondition_action(projection.precondition_failure.verdict)
            if projection.precondition_failure is not None
            else None
        )
        for projection in finding_preconditions
    )


def verification_report_payload(
    report: VerificationReport,
    *,
    finding_preconditions: Sequence[VerificationFindingPreconditionProjection] | None = None,
) -> VerificationReportPayload:
    """Project a domain report into the shared verification JSON payload.

    Both ``aeat app modelo work verify`` and ``verification-report view/list``
    use this function so persisted :class:`~VerificationReport`
    rows expose identical factual
    :class:`~cadrumo.entrypoints.cli._modelo_payloads.VerificationReportPayload`
    fields, including nested
    :class:`~cadrumo.entrypoints.cli._modelo_payloads.FindingPayload` legal and
    source references.
    """
    findings: list[FindingPayload] = []
    actions = _resolved_finding_actions(report, finding_preconditions)
    for finding, action in zip(report.findings, actions, strict=True):
        findings.append(
            FindingPayload(
                kind=finding.kind,
                severity=finding.severity,
                casilla_id=finding.casilla_id,
                expectation_id=finding.expectation_id,
                message=_render_verification_finding_message(finding),
                action=action,
                legal_refs=tuple(finding.legal_refs),
                source_refs=list(finding.source_refs),
            ),
        )
    return VerificationReportPayload(
        verification_report_id=report.verification_report_id,
        calculation_revision_id=report.calculation_revision_id,
        registry_snapshot_ref=report.registry_snapshot_ref,
        completeness_status=report.completeness_status,
        granted_verificado_completo=report.granted_verificado_completo,
        resolved_casilla_ids=list(report.resolved_casilla_ids),
        missing_required_casilla_ids=list(report.missing_required_casilla_ids),
        run_at=report.run_at.isoformat(),
        verified_by=report.verified_by,
        findings=findings,
    )


def verification_report_lines(
    report: VerificationReport,
    *,
    finding_actions: Sequence[ResolvedPreconditionAction | None] | None = None,
) -> list[str]:
    """Render the text transport for a verification report.

    The line shape complements
    :func:`~cadrumo.entrypoints.cli._modelo_rendering.verification_report_payload`:
    text output keeps the report ids, completeness verdict, missing casillas,
    and each finding's legal/source references visible. A live verification may
    additionally append the exact resolved precondition-action DTO; report
    history never recreates recovery instructions from persisted facts.
    """
    lines = [
        f"verification_report_id\t{report.verification_report_id}",
        f"calculation_revision_id\t{report.calculation_revision_id}",
        f"completeness_status\t{report.completeness_status.value}",
        f"granted_verificado_completo\t{str(report.granted_verificado_completo).lower()}",
        f"run_at\t{report.run_at.isoformat()}",
        f"verified_by\t{report.verified_by}",
        f"resolved_casilla_id_count\t{len(report.resolved_casilla_ids)}",
        f"missing_required_casilla_id_count\t{len(report.missing_required_casilla_ids)}",
        f"finding_count\t{len(report.findings)}",
    ]
    for casilla_id in report.missing_required_casilla_ids:
        lines.append(f"missing_casilla_id\t{casilla_id}")
    actions = (None,) * len(report.findings) if finding_actions is None else tuple(finding_actions)
    if len(actions) != len(report.findings):
        raise ValueError("verification finding actions must match the report in order")
    for finding, action in zip(report.findings, actions, strict=True):
        casilla = finding.casilla_id or ""
        lines.append(
            "\t".join(
                (
                    "finding",
                    finding.kind.value,
                    finding.severity.value,
                    casilla,
                    _render_verification_finding_message(finding),
                    resolved_precondition_action_json_cell(action),
                ),
            ),
        )
        if finding.legal_refs:
            lines.append(f"finding_legal_refs\t{casilla}\t{', '.join(finding.legal_refs)}")
        if finding.source_refs:
            lines.append(f"finding_source_refs\t{casilla}\t{', '.join(finding.source_refs)}")
    return lines


def _render_verification_finding_message(finding: ModeloVerificationFinding) -> str:
    """Render one persisted locale key and its typed facts at the CLI boundary."""
    return tr(finding.message_locale_key, **finding.message_facts)
