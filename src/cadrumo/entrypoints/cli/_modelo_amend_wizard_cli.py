"""Typer registration for the guided ``aeat app modelo work amend-wizard`` command.

An operator discovers a mistake in an already-filed return and knows "casilla 01 was
wrong, it should have been 1100" in plain language, not the raw
``--from-filing-record ... --kind ... --reason ... --set 01=1100`` flag
grammar ``work amend`` demands. The wizard resolves the work unit's current
AEAT-attested filing record, shows every one of its casilla values, asks which
casillas changed and what the corrected value is for each, confirms the legal
amendment kind and a free-text reason, then calls the exact same
:func:`~application.modelo.amend_modelo_revision` composition path
``work amend`` uses. The wizard is a guided front end over that one write
path, not a second one (``composition-service-no-parallel-write-path``).

The baseline casilla values the wizard displays are read from the filing
record's :class:`~domain.modelos.CalculationRevision`, so the operator
edits the exact attested figures rather than a re-computed draft.

Once the amendment is filed, the wizard points the operator at the existing
``aeat app modelo export`` verb for the fichero-BOE artefact; it never writes
an export file itself, mirroring how ``work wizard`` hands off to
``work calculate`` rather than re-deriving casilla values.

A real interactive terminal is required by default, reusing the exact
console-support detection and dynamic-answer protocol
:mod:`_modelo_work_wizard_cli` establishes for the calculation-draft wizard
(``_QuestionaryTextPrompter`` and the ``_TextAnswerPrompter`` protocol).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Annotated, Any

import typer

from ...application.modelo import (
    AmendmentComplementariaLiabilityDecreaseError,
    AmendmentEvidenceMissingError,
    AmendmentKindNotPermittedError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    AmendmentVerificationRefusedError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    get_filing_record,
    registry_casillas_for_registry_scope,
)
from ...core import Period, permitted_amendment_kind_values
from ...core.external_constants import OutputLanguage
from ...core.i18n import output_language, tr
from ...domain.calculations.registry import RegistrySnapshotError, validated_casilla_id
from ...domain.modelos import CalculationRevisionAmendmentKind
from ._modelo_amend_wizard_payloads import AmendWizardCorrectedCasillaPayload, WorkAmendWizardResult
from ._modelo_rendering import filing_record_lines
from ._modelo_work_wizard_cli import (
    _QuestionaryTextPrompter,
    _TextAnswerPrompter,
)

if TYPE_CHECKING:
    from ...domain.modelos import CalculationRevision, ModeloRecord, WorkUnit

__all__ = ["register_amend_wizard_commands"]


@dataclass(frozen=True, slots=True)
class _AmendWizardDeps:
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_work_unit_for_cli: Callable[..., Any]
    resolve_default_actor: Callable[[], str]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]


_WorkUnitIdArg = Annotated[str | None, typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help"))]
_ModeloOpt = Annotated[str | None, typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help"))]
_YearOpt = Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.work.year_help"))]
_PeriodOpt = Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.work.period_help"))]
_RevisionOpt = Annotated[str | None, typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help"))]
_BucketIdOpt = Annotated[str | None, typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help"))]
_ActorOpt = Annotated[str | None, typer.Option("--by", help=tr("cli.app.modelo.work.actor_help"))]


# KWARGS-ANY-RATIONALE-cli: resolve_work_unit_for_cli is a CLI resolver callback injected by the command registrar
def register_amend_wizard_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[
        ..., Any
    ],  # KWARGS-ANY-RATIONALE-cli-callback: work-unit resolver callback injected by the command registrar
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register the guided ``work amend-wizard`` command on the modelo work app."""
    deps = _AmendWizardDeps(
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_default_actor=resolve_default_actor,
        bad_parameter_from_error=bad_parameter_from_error,
    )

    @work_app.command("amend-wizard", help=tr("cli.app.modelo.work.amend_wizard_help"))
    def work_amend_wizard(
        ctx: typer.Context,
        work_unit_id: _WorkUnitIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        actor: _ActorOpt = None,
        output_language_opt: Annotated[
            OutputLanguage | None,
            typer.Option("--output-language", help=tr("cli.app.modelo.work.output_language_help")),
        ] = None,
    ) -> None:
        """Walk the resolved work unit's current AEAT-attested filing through a guided amendment.

        Resolves (or reuses) a work unit exactly as ``work create`` /
        ``work wizard`` do, loads its current filing record (the same
        :class:`~domain.modelos.ModeloRecord` ``work amend``
        requires — it must carry
        :class:`~domain.modelos.ExternalEvidence`), shows every
        baseline casilla value, prompts which casillas changed and their
        corrected values, confirms the amendment kind and reason, then
        calls :func:`~application.modelo.amend_modelo_revision`
        through the identical inputs ``work amend`` builds.
        """
        run_modelo_work_amend_wizard(
            deps=deps,
            ctx=ctx,
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
            actor=actor,
            output_language_opt=output_language_opt,
        )


def run_modelo_work_amend_wizard(
    *,
    deps: _AmendWizardDeps,
    ctx: typer.Context,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    actor: str | None,
    output_language_opt: OutputLanguage | None,
) -> None:
    deps.activate_output_language(ctx, output_language_opt)
    deps.require_active_profile()
    unit = deps.resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )

    if unit.current_filing_record_id is None:
        raise deps.bad_parameter_from_error(
            ModeloRecordNotFoundError(
                translated_message="cli.app.modelo.work.amend_wizard_no_current_filing",
                context={"work_unit_id": unit.work_unit_id},
            ),
        )
    try:
        baseline = get_filing_record(unit.current_filing_record_id)
    except ModeloRecordNotFoundError as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    if baseline.external_evidence is None:
        raise deps.bad_parameter_from_error(
            AmendmentEvidenceMissingError(
                f"filing record {baseline.filing_record_id!r} has no external_evidence; "
                f"the amendment wizard requires an imported AEAT-attested baseline "
                f"(`aeat app modelo filing-record import`). Locally-filed returns are "
                f"corrected through the standard re-file path (calculate -> verify -> file).",
            ),
        ) from None

    active_prompter = _QuestionaryTextPrompter()

    try:
        casilla_rows = _baseline_casilla_rows(unit)
    except RegistrySnapshotError as exc:
        raise deps.bad_parameter_from_error(exc) from exc

    corrections = _prompt_corrections(active_prompter, unit=unit, baseline=baseline, casilla_rows=casilla_rows)
    if not corrections:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.amend_wizard_no_corrections",
                default="No casilla was corrected; the amendment wizard needs at least one changed value.",
            ),
        )

    amendment_kind = _prompt_amendment_kind(active_prompter, modelo=str(baseline.modelo), period=baseline.period)
    reason = _prompt_reason(active_prompter)

    overrides = {row.casilla_id: value for row, _previous, value in corrections}
    try:
        record = amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides=overrides,
            amendment_kind=amendment_kind,
            reason=reason,
            actor=actor or deps.resolve_default_actor(),
        )
    except (
        ModeloRecordNotFoundError,
        AmendmentEvidenceMissingError,
        AmendmentTargetStateError,
        AmendmentOverrideCasillaError,
        AmendmentVerificationRefusedError,
        AmendmentKindNotPermittedError,
        AmendmentComplementariaLiabilityDecreaseError,
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise deps.bad_parameter_from_error(exc) from exc

    _emit_amend_wizard_result(
        ctx,
        record=record,
        unit=unit,
        amendment_kind=amendment_kind,
        reason=reason,
        corrections=corrections,
    )


def _baseline_casilla_rows(unit: WorkUnit) -> tuple[Any, ...]:
    """Return every casilla the registry declares for the unit's revision, for display."""
    report = registry_casillas_for_registry_scope(
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period.registry_token,
    )
    return tuple(report.rows)


# KWARGS-ANY-RATIONALE-cli: casilla prompt rows carry a heterogeneous casilla-id element
def _prompt_corrections(
    prompter: _TextAnswerPrompter,
    *,
    unit: WorkUnit,
    baseline: ModeloRecord,
    casilla_rows: tuple[
        Any, ...
    ],  # KWARGS-ANY-RATIONALE-prompt-row: casilla prompt rows carry a heterogeneous casilla-id element
) -> tuple[tuple[Any, Decimal, Decimal], ...]:
    """Ask which casillas changed, then the corrected value for each.

    First question lists every baseline casilla value and asks for a
    space-or-comma separated list of casilla numbers/ids that changed
    (an empty answer means none). A follow-up question then asks for the
    corrected decimal value of each selected casilla in turn, showing its
    current (baseline) value for context.
    """
    from ._modelo_cli_support import load_calculation_revision

    baseline_revision: CalculationRevision = load_calculation_revision(baseline.calculation_revision_id)
    lang = output_language()
    rows_by_id = {row.casilla_id: row for row in casilla_rows}
    rows_by_number = {row.number: row for row in casilla_rows}

    summary_lines = "\n".join(
        f"  {row.number}\t{row.localized_labels.get(lang, row.label)}\t"
        f"{baseline_revision.casilla_values.get(row.casilla_id, Decimal('0'))}"
        for row in sorted(casilla_rows, key=lambda r: r.number)
        if row.casilla_id in baseline_revision.casilla_values
    )
    selection_prompt = tr(
        "cli.app.modelo.work.amend_wizard_select_prompt",
        modelo=str(unit.modelo),
        year=unit.filing_year,
        period=unit.period.registry_token,
        summary=summary_lines,
        default=(
            "Filed {modelo} {year} {period} — current values:\n{summary}\n"
            "Which casilla numbers changed? (comma/space separated, blank for none)"
        ),
    )
    raw_selection = prompter.ask_text(selection_prompt, help_text=None).strip()
    if not raw_selection:
        return ()

    tokens = [token for token in raw_selection.replace(",", " ").split() if token]
    corrections: list[tuple[Any, Decimal, Decimal]] = []
    for token in tokens:
        row = rows_by_number.get(token)
        if row is None:
            try:
                casilla_id = validated_casilla_id(token, surface="amend-wizard selection")
            except ValueError as exc:
                raise typer.BadParameter(
                    tr(
                        "cli.app.modelo.work.amend_wizard_unknown_casilla",
                        default=(
                            "Casilla {token!r} is not part of the filed {modelo} "
                            "{year} {period} return; choose from the listed casilla numbers."
                        ),
                        token=token,
                        modelo=str(unit.modelo),
                        year=unit.filing_year,
                        period=unit.period.registry_token,
                    ),
                ) from exc
            row = rows_by_id.get(casilla_id)
        if row is None:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.amend_wizard_unknown_casilla",
                    default=(
                        "Casilla {token!r} is not part of the filed {modelo} "
                        "{year} {period} return; choose from the listed casilla numbers."
                    ),
                    token=token,
                    modelo=str(unit.modelo),
                    year=unit.filing_year,
                    period=unit.period.registry_token,
                ),
            )
        previous_value = baseline_revision.casilla_values.get(row.casilla_id, Decimal("0"))
        value_prompt = tr(
            "cli.app.modelo.work.amend_wizard_value_prompt",
            number=row.number,
            label=row.localized_labels.get(lang, row.label),
            previous_value=str(previous_value),
            default="Corrected value for casilla {number} ({label}), currently {previous_value}",
        )
        help_text = row.localized_help.get(lang)
        raw_value = prompter.ask_text(value_prompt, help_text=help_text).strip()
        try:
            corrected_value = Decimal(raw_value)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(
                tr("cli.app.modelo.work.set_not_decimal", value=raw_value),
            ) from exc
        corrections.append((row, previous_value, corrected_value))
    return tuple(corrections)


def _prompt_amendment_kind(
    prompter: _TextAnswerPrompter,
    *,
    modelo: str,
    period: Period,
) -> CalculationRevisionAmendmentKind:
    """Prompt for the amendment kind, restricted to what the period legally permits.

    Reads :func:`~core.resolve_amendment_kind_regime` for
    ``modelo`` and ``period`` so the wizard only offers (and only accepts) the
    kinds legally available for this filing — e.g. it never offers
    ``rectificativa`` for a pre-adoption period. ``amend_modelo_revision``
    re-asserts the same guard downstream, so an answer outside the permitted
    set is refused there too if this prompt is ever bypassed (a scripted
    answer in tests).
    """
    permitted = permitted_amendment_kind_values(modelo, period)
    choices = ", ".join(repr(kind.value) for kind in CalculationRevisionAmendmentKind if kind.value in permitted)
    prompt = tr(
        "cli.app.modelo.work.amend_wizard_kind_prompt",
        choices=choices,
        default="Amendment kind ({choices})",
    )
    help_text = tr(
        "cli.app.modelo.work.amend_wizard_kind_help",
        default=(
            "complementaria adds to the prior tax due; sustitutiva fully replaces the prior "
            "filing; rectificativa is the unified correction mechanism for modelos whose "
            "orden implements it (e.g. Modelo 303 from 2023-y-siguientes). Only the kinds "
            "legally available for this filing's period are accepted."
        ),
    )
    raw = prompter.ask_text(prompt, help_text=help_text).strip()
    try:
        kind = CalculationRevisionAmendmentKind(raw)
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_amendment_kind",
                choices=choices,
                kind=raw,
            ),
        ) from exc
    if kind.value not in permitted:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_amendment_kind",
                choices=choices,
                kind=raw,
            ),
        )
    return kind


def _prompt_reason(prompter: _TextAnswerPrompter) -> str:
    prompt = tr(
        "cli.app.modelo.work.amend_wizard_reason_prompt",
        default="Reason for this amendment (kept in the audit trail)",
    )
    raw = prompter.ask_text(prompt, help_text=None).strip()
    if not raw:
        raise typer.BadParameter(tr("cli.app.modelo.work.amend_wizard_reason_required"))
    return raw


# KWARGS-ANY-RATIONALE-cli: correction tuples carry a heterogeneous casilla-id element
def _emit_amend_wizard_result(
    ctx: typer.Context,
    *,
    record: ModeloRecord,
    unit: WorkUnit,
    amendment_kind: CalculationRevisionAmendmentKind,
    reason: str,
    corrections: tuple[
        tuple[Any, Decimal, Decimal], ...
    ],  # KWARGS-ANY-RATIONALE-prompt-row: correction tuples carry a heterogeneous casilla-id element
) -> None:
    from ._common import _emit_envelope
    from ._modelo_rendering import filing_record_payload

    export_next_action = tr(
        "cli.app.modelo.work.amend_wizard_export_next_action",
        work_unit_id=unit.work_unit_id,
        default=(
            "Amendment filed as a draft internal record. Export the AEAT-importable "
            "fichero-BOE with `aeat app modelo export {work_unit_id} --output PATH`."
        ),
    )
    corrected_payload = tuple(
        AmendWizardCorrectedCasillaPayload(
            casilla_id=row.casilla_id,
            number=row.number,
            label=row.localized_labels.get(output_language(), row.label),
            previous_value=str(previous_value),
            corrected_value=str(corrected_value),
            legal_refs=tuple(row.legal_refs),
            source_refs=tuple(row.source_refs),
        )
        for row, previous_value, corrected_value in corrections
    )
    filing_payload = filing_record_payload(record).model_dump(mode="python")
    result = WorkAmendWizardResult.model_validate(
        {
            **filing_payload,
            "amendment_kind": amendment_kind.value,
            "amendment_reason": reason,
            "corrected_casillas": corrected_payload,
            "export_next_action": export_next_action,
        },
    )
    lines = [
        "operation\tmodelo.work.amend_wizard",
        f"amendment_kind\t{amendment_kind.value}",
        *filing_record_lines(record),
        *(
            f"corrected\t{row.number}\t{previous_value}\t{corrected_value}"
            for row, previous_value, corrected_value in corrections
        ),
        export_next_action,
    ]
    _emit_envelope(ctx, command="modelo.work.amend_wizard", result=result, lines=lines)
