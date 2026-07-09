"""Projection helpers shared by modelo CLI command groups.

This module turns modelo application/domain records such as
:class:`~aeat.domain.modelos.WorkUnit`,
:class:`~aeat.domain.modelos.CalculationRevision`,
:class:`~aeat.domain.modelos.ModeloRecord`,
:class:`~aeat.domain.modelos.VerificationReport`, and
:class:`~aeat.application.modelo.ModeloWorkPlazoSummary` into CLI text lines
and registered JSON payload fragments. The payload side feeds
:class:`~aeat.entrypoints.cli._modelo_payloads.WorkUnitPayload`,
:class:`~aeat.entrypoints.cli._modelo_payloads.CalculationRevisionPayload`,
:class:`~aeat.entrypoints.cli._modelo_payloads.ModeloRecordPayload`,
:class:`~aeat.entrypoints.cli._modelo_payloads.VerificationReportPayload`,
and uniform :class:`~aeat.core.json_contract.Notice` rows into
:func:`~aeat.entrypoints.cli._common._emit_envelope`.
"""

from __future__ import annotations

from ...application.modelo import (
    ModeloWorkPlazoSummary,
    ResultSummaryRow,
    calculation_result_summary,
    modelo_work_plazo_summary,
)
from ...core.i18n import output_language, tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.calculations.registry import BooleanBindingEncodedValue
from ...domain.modelos import CalculationRevision, CalculationRevisionState, Modelo184MemberRow
from ._modelo_payloads import (
    BindingEncodedOptionPayload,
    CalculationRevisionPayload,
    ExternalEvidencePayload,
    FindingPayload,
    ModeloRecordPayload,
    ObservationPayload,
    ResultSummaryRowPayload,
    VerificationReportPayload,
    WorkPlazoDeadlinePayload,
    WorkRecargoPayload,
    WorkUnitPayload,
)
from ._modelo_revision_payload_parts import DetailRowPayload

_EXTEMPORANEOUS_RECARGO_LEGAL_REF = "ley-58-2003:art-27.2"
_M349_ROW_FIELD_TEMPLATE_PREFIXES = ("op.", "rect.")
_M184_SOCIO_HANDOFF_CODE = "modelo.work.m184_socio_handoff"
# The canonical M100 régimen-de-atribución (actividad económica) income casilla
# the attributed base folds into, per the 2026-07-09-m184-socio-attribution-handoff-adr
# addendum, decision (a): 1577 stays relation-canonical and the cross-bucket value
# enters the socio's own M100 via a documented manual --binding override on 1577.
_M184_ATRIBUCION_ACT_ECO_CASILLA = "1577"
_M184_ATRIBUCION_LEGAL_REFS = "ley-35-2006:art-86, ley-35-2006:art-87, ley-35-2006:art-88, ley-35-2006:art-89"


def m184_socio_handoff_notices(revision: CalculationRevision) -> list[Notice]:
    """Return per-socio Modelo 184 régimen-de-atribución handoff info Notices.

    When a Modelo 184 revision carries typed :class:`Modelo184MemberRow` detail
    rows, the entity operator who files the M184 is handed, per socio, the exact
    attributed base plus the ``attribution_received`` fact keys the socio records
    on their OWN profile, and the exact ``aeat app modelo work calculate
    --binding`` command that folds the base into the socio's Modelo 100 (per the
    ``2026-07-09-m184-socio-attribution-handoff-adr`` addendum, decision (a): the
    cross-bucket value is carried by hand onto the relation-canonical casilla
    1577, not auto-flowed across profiles). Grounded in LIRPF arts. 86-89.
    Returns an empty list for any revision without member rows (non-M184, or an
    M184 with no socios), so the handoff stays silent unless there is a real
    per-socio value to relay.
    """
    notices: list[Notice] = []
    for row in revision.detail_rows:
        if not isinstance(row, Modelo184MemberRow):
            continue
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=_M184_SOCIO_HANDOFF_CODE,
                message=(
                    f"Régimen de atribución de rentas: socio {row.nif} ({row.nombre}) receives an "
                    f"attributed base of {row.importe} EUR ({row.porcentaje}% share). On the socio's own "
                    f"workspace, record it as attribution_received facts (entity_nif, entity_name, "
                    f"share_pct, base_imponible_attributed, filing_year), then fold the base into their "
                    f"Modelo 100 régimen-de-atribución (actividad económica) casilla "
                    f"{_M184_ATRIBUCION_ACT_ECO_CASILLA} (LIRPF arts. 86-89)."
                ),
                suggestion=(
                    f"aeat app modelo work calculate --binding {_M184_ATRIBUCION_ACT_ECO_CASILLA}={row.importe}"
                ),
                context={
                    "nif": row.nif,
                    "nombre": row.nombre,
                    "porcentaje": str(row.porcentaje),
                    "base_imponible_attributed": str(row.importe),
                    "target_casilla": _M184_ATRIBUCION_ACT_ECO_CASILLA,
                    "legal_refs": _M184_ATRIBUCION_LEGAL_REFS,
                },
            ),
        )
    return notices


def binding_encoded_option_payloads(
    options: tuple[BooleanBindingEncodedValue, ...],
) -> tuple[BindingEncodedOptionPayload, ...]:
    """Project registry boolean-encoding rows onto :class:`BindingEncodedOptionPayload` rows."""
    return tuple(
        BindingEncodedOptionPayload(
            encoded_value=option.encoded_value,
            boolean_meaning=option.boolean_meaning,
            registry_value=option.registry_value,
        )
        for option in options
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
    suggestion: str | None = None,
    context: dict[str, str] | None = None,
) -> Notice:
    """Project a non-blocking modelo advisory message onto the envelope notices channel.

    The single projection point that turns an incidental, non-blocking
    modelo diagnostic (source-resolution advisory, unauthorized-backend
    advisory, filing-obligation advisory) into a warning-severity
    :class:`~aeat.core.json_contract.Notice`. Command groups call this instead
    of re-modelling the advisory as a bespoke ``*_advisory`` payload field, so
    every advisory flows through the one uniform notices surface. ``context``
    carries any structured provenance the former bespoke payload exposed (e.g.
    the source-resolution ``reason`` / ``source_kind``).
    """
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=code,
        message=message,
        suggestion=suggestion,
        context=context,
    )


def next_action_notice(
    code: str,
    message: str,
    *,
    suggestion: str | None = None,
    context: dict[str, str] | None = None,
) -> Notice:
    """Project a post-action next-step hint onto the envelope notices channel.

    The :attr:`NoticeSeverity.INFO` sibling of :func:`advisory_notice`: it turns
    the "what should the operator run next" guidance emitted after a work-unit
    read or a verification into an info-severity
    :class:`~aeat.core.json_contract.Notice` whose ``suggestion`` is the
    follow-on ``aeat ...`` command. The lifecycle read verbs (``work list`` /
    ``work status`` / ``work history``) and ``work verify`` call this instead of
    a bespoke ``next`` / ``suggestion`` payload field, so every next-step hint
    rides the one uniform notices surface per the
    ``cli-notices-are-the-only-diagnostic-channel`` rule. Being ``info`` severity
    it never flips the envelope ``status`` away from ``success``.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code=code,
        message=message,
        suggestion=suggestion,
        context=context,
    )


def short_id(value: str | None) -> str | None:
    """Return the display suffix for a content-addressed id."""
    return value[-12:] if value else None


def _has_m349_detail_rows(rev) -> bool:
    return any(getattr(row, "row_type", None) == "operador" for row in rev.detail_rows)


def _is_m349_row_field_template_casilla(casilla_id: str) -> bool:
    return casilla_id.startswith(_M349_ROW_FIELD_TEMPLATE_PREFIXES)


def _visible_calculation_casilla_values(rev):
    if not _has_m349_detail_rows(rev):
        return rev.casilla_values
    return {
        casilla_id: value
        for casilla_id, value in rev.casilla_values.items()
        if not _is_m349_row_field_template_casilla(str(casilla_id))
    }


def _visible_calculation_observations(rev):
    if not _has_m349_detail_rows(rev):
        return rev.observations
    return tuple(
        observation
        for observation in rev.observations
        if not _is_m349_row_field_template_casilla(str(observation.casilla_id))
    )


def _effective_work_unit_state(unit) -> str:
    state = unit.state.value
    if state == "descartado":
        return state
    if unit.filed_calculation_revision_id is not None:
        return CalculationRevisionState.PRESENTADO.value
    return state


def _human_state_label(state: str) -> str:
    if state == CalculationRevisionState.BORRADOR.value:
        return tr("cli.app.modelo.work.state_label_borrador", default="draft")
    if state == CalculationRevisionState.VERIFICADO_COMPLETO.value:
        return tr("cli.app.modelo.work.state_label_verificado_completo", default="verified complete")
    if state == CalculationRevisionState.PRESENTADO.value:
        return tr("cli.app.modelo.work.state_label_presentado", default="filed")
    if state == CalculationRevisionState.PRESENTADO_SUPERSEDIDO.value:
        return tr("cli.app.modelo.work.state_label_presentado_supersedido", default="superseded filing")
    if state == CalculationRevisionState.DESCARTADO.value:
        return tr("cli.app.modelo.work.state_label_descartado", default="discarded")
    return state


def work_unit_payload(unit) -> WorkUnitPayload:
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


def work_unit_lines(unit) -> list[str]:
    lines = [
        f"work_unit_id\t{unit.work_unit_id}",
        f"short_work_unit_id\t{short_id(unit.work_unit_id) or ''}",
        f"bucket_id\t{unit.bucket_id}",
        f"modelo\t{unit.modelo}",
        f"filing_year\t{unit.filing_year}",
        f"period\t{unit.period.registry_token}",
        f"revision_id\t{unit.revision_id}",
        f"name\t{unit.name}",
        f"state\t{_human_state_label(_effective_work_unit_state(unit))}",
        f"current_calculation_revision_id\t{unit.current_calculation_revision_id or ''}",
        f"short_current_calculation_revision_id\t{short_id(unit.current_calculation_revision_id) or ''}",
        f"filed_calculation_revision_id\t{unit.filed_calculation_revision_id or ''}",
        f"short_filed_calculation_revision_id\t{short_id(unit.filed_calculation_revision_id) or ''}",
        f"current_filing_record_id\t{unit.current_filing_record_id or ''}",
        f"created_at\t{unit.created_at.isoformat()}",
        f"updated_at\t{unit.updated_at.isoformat()}",
    ]
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


def work_unit_list_lines(units, *, bucket_id: str | None, include_discarded: bool) -> list[str]:
    lines = [
        "operation\tmodelo.work.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"include_discarded\t{include_discarded}",
        f"work_unit_count\t{len(units)}",
        "short_work_unit_id\twork_unit_id\tbucket_id\tmodelo\tyear\tperiod\trevision_id\tstate\tcurrent_revision\tfiled_revision\tname",
    ]
    lines.extend(
        "\t".join(
            (
                short_id(unit.work_unit_id) or "",
                unit.work_unit_id,
                unit.bucket_id,
                str(unit.modelo),
                str(unit.filing_year),
                unit.period.registry_token,
                unit.revision_id,
                _human_state_label(_effective_work_unit_state(unit)),
                short_id(unit.current_calculation_revision_id) or "",
                short_id(unit.filed_calculation_revision_id) or "",
                unit.name,
            ),
        )
        for unit in units
    )
    return lines


def work_unit_plazo_lines(unit) -> list[str]:
    """Render plazo voluntario and extemporaneidad lines for the work unit."""
    summary = modelo_work_plazo_summary(unit)
    if summary is None:
        return []

    out: list[str] = [f"plazo_closes_on\t{summary.closes_on.isoformat()}"]
    if summary.days_remaining is not None:
        out.append(
            tr(
                "cli.app.modelo.work.plazo_days_remaining",
                default="days_remaining\t{days_remaining}",
                days_remaining=summary.days_remaining,
            ),
        )
        return out

    if summary.days_overdue is None:
        return out

    out.append(f"days_overdue\t{summary.days_overdue}")
    if summary.recargo is None:
        out.append(
            tr(
                "cli.app.modelo.work.plazo_vencido_warning",
                default=(
                    "AVISO: plazo voluntario vencido. Presenta con recargo "
                    "Art. 27 LGT antes de recibir requerimiento de la AEAT."
                ),
            ),
        )
        return out

    out.extend(
        [
            f"recargo_band\t{summary.recargo.band_id}",
            f"recargo_pct\t{summary.recargo.surcharge_pct}",
            f"recargo_interest_applies\t{summary.recargo.interest_applies}",
            f"recargo_legal_ref\t{summary.recargo.legal_ref}",
            tr(
                "cli.app.modelo.work.plazo_vencido_warning",
                default=(
                    "AVISO: plazo voluntario vencido. Presenta con recargo "
                    "Art. 27 LGT antes de recibir requerimiento de la AEAT."
                ),
            ),
        ],
    )
    return out


def _work_unit_deadline_output_from_summary(
    summary: ModeloWorkPlazoSummary | None,
) -> tuple[WorkPlazoDeadlinePayload | None, list[Notice]]:
    """Project a filing-deadline summary onto a payload + notices.

    Returns the typed
    :class:`~aeat.entrypoints.cli._modelo_payloads.WorkPlazoDeadlinePayload`
    (structured result data: the voluntary-filing close date and overdue
    posture) and a warning-severity
    :class:`~aeat.core.json_contract.Notice` list. An overdue deadline raises
    one Art. 27 LGT recargo notice whose ``context`` carries the binding legal
    reference (``legal_refs``) plus the resolved recargo band so the JSON
    surface preserves the regulatory grounding the text-mode plazo lines
    render. An in-time (or unknown) deadline raises no notice.
    """
    if summary is None:
        return None, []

    recargo_payload = None
    if summary.recargo is not None:
        recargo_payload = WorkRecargoPayload(
            band_id=summary.recargo.band_id,
            surcharge_pct=str(summary.recargo.surcharge_pct),
            interest_applies=summary.recargo.interest_applies,
            legal_ref=summary.recargo.legal_ref,
        )
    deadline_payload = WorkPlazoDeadlinePayload(
        closes_on=summary.closes_on.isoformat(),
        days_remaining=summary.days_remaining,
        days_overdue=summary.days_overdue,
        recargo=recargo_payload,
    )

    if summary.days_overdue is None or summary.days_overdue < 1:
        return deadline_payload, []

    warning_text = tr(
        "cli.app.modelo.work.plazo_vencido_warning",
        default=(
            "AVISO: plazo voluntario vencido. Presenta con recargo "
            "Art. 27 LGT antes de recibir requerimiento de la AEAT."
        ),
    )
    context: dict[str, str] = {
        "closes_on": summary.closes_on.isoformat(),
        "days_overdue": str(summary.days_overdue),
    }
    if summary.recargo is not None:
        context["legal_refs"] = summary.recargo.legal_ref
        context["recargo_band"] = summary.recargo.band_id
        context["surcharge_pct"] = str(summary.recargo.surcharge_pct)
        context["interest_applies"] = str(summary.recargo.interest_applies)
    else:
        # No recargo band resolved (e.g. deadline-validation failure), but the
        # filing is still extemporáneo under Art. 27 LGT; carry the binding
        # article so the JSON grounding survives even without a band.
        context["legal_refs"] = _EXTEMPORANEOUS_RECARGO_LEGAL_REF
    return deadline_payload, [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="modelo.work.calculate.plazo_vencido_recargo",
            message=warning_text,
            context=context,
        ),
    ]


def work_unit_deadline_output(unit) -> tuple[WorkPlazoDeadlinePayload | None, list[Notice]]:
    """Project a work unit's filing deadline onto payload and notice rows.

    The JSON branch emits
    :class:`~aeat.entrypoints.cli._modelo_payloads.WorkPlazoDeadlinePayload`
    plus warning-severity :class:`~aeat.core.json_contract.Notice` rows.
    """
    return _work_unit_deadline_output_from_summary(modelo_work_plazo_summary(unit))


def detail_row_payloads(rev) -> tuple[DetailRowPayload, ...]:
    """Return materialised :class:`DetailRowPayload` rows for the JSON calculation payload."""
    rows: list[DetailRowPayload] = []
    for index, detail_row in enumerate(rev.detail_rows, start=1):
        dumped = detail_row.model_dump(mode="json", exclude={"row_type"})
        rows.append(
            DetailRowPayload(
                index=index,
                row_type=str(detail_row.row_type),
                fields={key: None if value is None else str(value) for key, value in dumped.items()},
            ),
        )
    return tuple(rows)


def calculation_revision_payload(rev) -> CalculationRevisionPayload:
    """Project a calculation revision into the shared JSON payload.

    The returned
    :class:`~aeat.entrypoints.cli._modelo_payloads.CalculationRevisionPayload`
    carries visible casilla values, nested
    :class:`~aeat.entrypoints.cli._modelo_revision_payload_parts.ObservationPayload`
    rows, and
    :class:`~aeat.entrypoints.cli._modelo_revision_payload_parts.ResultSummaryRowPayload`
    headline rows for envelope-aware commands.
    """
    observations = tuple(
        ObservationPayload(
            casilla_id=obs.casilla_id,
            value=str(obs.value),
            formula_id=obs.formula_id,
            op=obs.op,
            operand_refs=tuple(obs.operand_refs),
            operand_casilla_refs=tuple(obs.operand_casilla_refs),
            operand_values=tuple(str(v) for v in obs.operand_values),
            legal_refs=tuple(obs.legal_refs),
            source_refs=tuple(obs.source_refs),
        )
        for obs in _visible_calculation_observations(rev)
    )
    return CalculationRevisionPayload(
        calculation_revision_id=rev.calculation_revision_id,
        work_unit_id=rev.work_unit_id,
        state=rev.state.value,
        casilla_values={k: str(v) for k, v in _visible_calculation_casilla_values(rev).items()},
        observations=observations,
        result_summary=result_summary_payload(rev),
        detail_rows=detail_row_payloads(rev),
        binding_overrides={key: str(value) for key, value in rev.binding_overrides.items()},
        relation_overrides={key: str(value) for key, value in rev.relation_overrides.items()},
        input_values_by_casilla_id=dict(rev.input_values_by_casilla_id),
        created_at=rev.created_at.isoformat(),
        updated_at=rev.updated_at.isoformat(),
        verified_at=rev.verified_at.isoformat() if rev.verified_at else None,
        verified_by=rev.verified_by,
        filed_at=rev.filed_at.isoformat() if rev.filed_at else None,
        filed_by=rev.filed_by,
        superseded_at=rev.superseded_at.isoformat() if rev.superseded_at else None,
    )


def _result_summary_row_label(row: ResultSummaryRow, language: str) -> str:
    return row.localized_labels.get(language, row.label)


def result_summary_lines(rev) -> list[str]:
    """Return the headline-result summary block for a calculation revision."""
    summary = calculation_result_summary(rev)
    if summary is None or not summary.rows:
        return []
    language = output_language()
    header = tr(
        "cli.app.modelo.work.result_summary_header",
        default="result summary  %{modelo} %{year} %{period}",
        modelo=summary.modelo,
        year=summary.filing_year,
        period=summary.period.registry_token,
    )
    lines = [header, "role\tcasilla\tvalue\tlabel"]
    for row in summary.rows:
        label = _result_summary_row_label(row, language)
        lines.append(f"{row.role}\t{row.casilla_id}\t{row.value}\t{label}")
    return lines


def result_summary_payload(rev) -> tuple[ResultSummaryRowPayload, ...]:
    """Return headline-result summary rows for the JSON payload.

    Each row is a
    :class:`~aeat.entrypoints.cli._modelo_revision_payload_parts.ResultSummaryRowPayload`.
    """
    summary = calculation_result_summary(rev)
    if summary is None:
        return ()
    language = output_language()
    return tuple(
        ResultSummaryRowPayload(
            role=row.role,
            casilla_id=row.casilla_id,
            value=str(row.value),
            label=_result_summary_row_label(row, language),
            localized_labels=dict(row.localized_labels),
        )
        for row in summary.rows
    )


def casilla_inline_trace(obs) -> str | None:
    """Render the inline formula trace for one computed casilla observation.

    Returns the ``op(refs) = op(values) = value`` trace string for a formula
    observation (a :class:`~aeat.domain.calculations.registry.CasillaObservation`
    whose ``formula_id`` and ``op`` are set), sourced entirely from the
    already-computed operand lineage on the typed observation. Returns ``None``
    for an input / bound casilla that carries no formula, so those rows render
    their value only, as before.
    """
    if obs.formula_id is None or obs.op is None:
        return None
    value = str(obs.value)
    if obs.operand_refs:
        symbolic = f"{obs.op}({', '.join(obs.operand_refs)})"
        evaluated = f"{obs.op}({', '.join(str(operand) for operand in obs.operand_values)})"
        return f"{symbolic} = {evaluated} = {value}"
    return f"{obs.op} = {value}"


def casilla_trace_verbose_line(obs) -> str:
    """Render the full LedgerEntry detail for one computed casilla observation.

    Exposes the complete typed
    :class:`~aeat.domain.calculations.registry.CasillaObservation` trace -
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


def calculation_revision_lines(rev, *, verbose: bool = False) -> list[str]:
    lines = [
        f"calculation_revision_id\t{rev.calculation_revision_id}",
        f"work_unit_id\t{rev.work_unit_id}",
        f"state\t{_human_state_label(rev.state.value)}",
        f"created_at\t{rev.created_at.isoformat()}",
        f"updated_at\t{rev.updated_at.isoformat()}",
    ]
    if rev.verified_at is not None:
        lines.append(f"verified_at\t{rev.verified_at.isoformat()}")
        lines.append(f"verified_by\t{rev.verified_by}")
    if rev.filed_at is not None:
        lines.append(f"filed_at\t{rev.filed_at.isoformat()}")
        lines.append(f"filed_by\t{rev.filed_by}")
    if rev.superseded_at is not None:
        lines.append(f"superseded_at\t{rev.superseded_at.isoformat()}")
    summary_lines = result_summary_lines(rev)
    if summary_lines:
        lines.extend(summary_lines)
    observation_by_casilla = {obs.casilla_id: obs for obs in _visible_calculation_observations(rev)}
    for casilla, value in sorted(_visible_calculation_casilla_values(rev).items()):
        observation = observation_by_casilla.get(casilla)
        trace = casilla_inline_trace(observation) if observation is not None else None
        if trace is None:
            lines.append(f"casilla\t{casilla}\t{value}")
            continue
        lines.append(f"casilla\t{casilla}\t{value}\t{trace}")
        if verbose:
            lines.append(casilla_trace_verbose_line(observation))
    for index, detail_row in enumerate(rev.detail_rows, start=1):
        fields = detail_row.model_dump(mode="json", exclude={"row_type"})
        field_str = " ".join(f"{key}={value}" for key, value in fields.items())
        lines.append(f"detail_row\t{index}\t{detail_row.row_type}\t{field_str}")
    return lines


def calculation_observation_lines(rev) -> list[str]:
    """Return a stable text view of a revision's typed casilla observations."""
    payload = calculation_revision_payload(rev)
    observations = sorted(payload.observations, key=lambda obs: obs.casilla_id)
    lines = [
        f"calculation_revision_id\t{payload.calculation_revision_id}",
        f"work_unit_id\t{payload.work_unit_id}",
        f"state\t{_human_state_label(payload.state)}",
        f"observation_count\t{len(observations)}",
        "casilla_id\tvalue\tformula_id\tlegal_refs\tsource_refs\toperand_refs\toperand_casilla_refs\toperand_values",
    ]
    lines.extend(
        "\t".join(
            (
                obs.casilla_id,
                obs.value,
                obs.formula_id or "",
                ";".join(obs.legal_refs),
                ";".join(obs.source_refs),
                ";".join(obs.operand_refs),
                ";".join(obs.operand_casilla_refs),
                ";".join(obs.operand_values),
            ),
        )
        for obs in observations
    )
    return lines


def filing_record_payload(record) -> ModeloRecordPayload:
    """Project a :class:`~aeat.domain.modelos.ModeloRecord` into :class:`ModeloRecordPayload` JSON form.

    When the record carries :class:`~aeat.domain.modelos.ExternalEvidence`, the
    evidence fields are nested in :class:`ExternalEvidencePayload`; local filing
    records still render with ``live_submission=False``.
    """
    external_evidence: ExternalEvidencePayload | None = None
    if record.external_evidence is not None:
        external_evidence = ExternalEvidencePayload(
            kind=record.external_evidence.kind.value,
            reference_id=record.external_evidence.reference_id,
            imported_at=record.external_evidence.imported_at.isoformat(),
        )
    return ModeloRecordPayload(
        filing_record_id=record.filing_record_id,
        work_unit_id=record.work_unit_id,
        calculation_revision_id=record.calculation_revision_id,
        bucket_id=record.bucket_id,
        modelo=str(record.modelo),
        filing_year=record.filing_year,
        period=record.period,
        filed_at=record.filed_at.isoformat(),
        filed_by=record.filed_by,
        notes=record.notes,
        aeat_accepted=record.aeat_accepted,
        status=record.status.value,
        superseded_at=record.superseded_at.isoformat() if record.superseded_at else None,
        superseded_by_filing_record_id=record.superseded_by_filing_record_id,
        external_evidence=external_evidence,
        amends_filing_record_id=record.amends_filing_record_id,
        kind="internal_filing",
        live_submission=False,
    )


def filing_record_lines(record) -> list[str]:
    """Render a :class:`~aeat.domain.modelos.ModeloRecord` as stable text lines.

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
        f"aeat_accepted\t{str(record.aeat_accepted).lower()}",
    ]
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


def verification_report_notices(report) -> list[Notice]:
    """Project every verification finding onto the envelope notices channel.

    A verify run that is NOT granted ``verificado_completo`` carries
    blocking and/or warning findings; without this projection the JSON
    envelope reported ``status: "success"`` with an empty ``notices`` list
    while the exit code was 1 and ``result.findings`` held blocking findings
    — a contract break against
    :func:`aeat.core.json_contract.derive_status`, which derives the
    envelope ``status`` from notice severity in lock-step with the
    ``ExitCode`` table. Each
    :class:`~aeat.domain.modelos.ModeloVerificationFinding` becomes one
    :class:`~aeat.core.json_contract.Notice`.

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
    text-mode ``finding_legal_refs`` lines render. The finding's
    ``next_action`` becomes the notice ``suggestion``.

    A granted (clean) verify carries no findings, so this returns an empty
    list and the envelope stays :attr:`EnvelopeStatus.SUCCESS`.
    """
    notices: list[Notice] = []
    for finding in report.findings:
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
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=f"modelo.work.verify.finding.{finding.kind.value}",
                message=finding.message,
                suggestion=finding.next_action,
                context=context,
            ),
        )
    return notices


def verification_report_payload(report) -> VerificationReportPayload:
    """Project a domain report into the shared verification JSON payload.

    Both ``aeat app modelo work verify`` and ``verification-report view/list``
    use this function so persisted :class:`aeat.domain.modelos.VerificationReport`
    rows expose identical
    :class:`~aeat.entrypoints.cli._modelo_payloads.VerificationReportPayload`
    fields, including nested
    :class:`~aeat.entrypoints.cli._modelo_payloads.FindingPayload` legal and
    source references.
    """
    return VerificationReportPayload(
        verification_report_id=report.verification_report_id,
        calculation_revision_id=report.calculation_revision_id,
        completeness_status=report.completeness_status.value,
        granted_verificado_completo=report.granted_verificado_completo,
        resolved_casilla_ids=list(report.resolved_casilla_ids),
        missing_required_casilla_ids=list(report.missing_required_casilla_ids),
        run_at=report.run_at.isoformat(),
        verified_by=report.verified_by,
        findings=[
            FindingPayload(
                kind=f.kind.value,
                severity=f.severity.value,
                casilla_id=f.casilla_id,
                expectation_id=f.expectation_id,
                message=f.message,
                next_action=f.next_action,
                legal_refs=list(f.legal_refs),
                source_refs=list(f.source_refs),
            )
            for f in report.findings
        ],
    )


def verification_report_lines(report) -> list[str]:
    """Render the text transport for a verification report.

    The line shape complements
    :func:`~aeat.entrypoints.cli._modelo_rendering.verification_report_payload`:
    text output keeps the report ids, completeness verdict, missing casillas,
    and each finding's legal/source references visible without inventing fields
    outside the persisted :class:`aeat.domain.modelos.VerificationReport`.
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
    for finding in report.findings:
        next_action = finding.next_action or ""
        casilla = finding.casilla_id or ""
        lines.append(
            "\t".join(
                (
                    "finding",
                    finding.kind.value,
                    finding.severity.value,
                    casilla,
                    finding.message,
                    next_action,
                ),
            ),
        )
        if finding.legal_refs:
            lines.append(f"finding_legal_refs\t{casilla}\t{', '.join(finding.legal_refs)}")
        if finding.source_refs:
            lines.append(f"finding_source_refs\t{casilla}\t{', '.join(finding.source_refs)}")
    if not report.granted_verificado_completo:
        lines.append(
            "next_action\taeat app modelo verification-report list "
            f"--calculation-revision-id {report.calculation_revision_id}",
        )
    return lines
