"""Shared workspace key declarations for desktop chrome."""

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import Final

#: The catalogue family that words what a calculation note says about its own subject, one sentence for
#: each :class:`~cadrumo.domain.modelos.calculation_revision_sources.CalculationNoteSentence`, with the
#: values that fill it in.
CALCULATION_NOTE_FACT_FAMILY: Final[str] = "application.modelo.calc_diagnostic_fact."

#: The family of the sentences that say what kind of thing a calculation noticed, one for each reason.
CALCULATION_NOTE_KIND_FAMILY: Final[str] = "application.modelo.calc_diagnostic."


def _calculation_note_kind_members() -> tuple[str, ...]:
    """Return ``<reason>.what`` for each reason whose sentence needs no value of its own.

    A note kept with a revision names no box, so a sentence that prints one cannot be drawn there.
    """
    from cadrumo.application.modelo.calculation_notes import CALCULATION_NOTE_ATTENTION

    from ._paths import LOCALES_DIR, SRC_DIR
    from .locale_tree import _flatten_raw_locale_leaves
    from .locale_yaml import locale_catalogue_source
    from .manager import LocaleManager

    source = locale_catalogue_source(LOCALES_DIR, "en")
    if source is None:
        raise ValueError(f"No source catalogue under {LOCALES_DIR}, so no calculation note could be listed")
    leaves = _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, LOCALES_DIR).load_locale(source))
    members = []
    for reason in CALCULATION_NOTE_ATTENTION:
        text = leaves.get(f"{CALCULATION_NOTE_KIND_FAMILY}{reason}.what")
        if isinstance(text, str) and "{" not in text:
            members.append(f"{reason}.what")
    return tuple(sorted(members))


def _composed_families(
    enumerated: Callable[[str], tuple[str, ...]],
    values: Callable[[Iterable[object]], tuple[str, ...]],
    surfaces: tuple[str, ...],
    filing_copies: Callable[[], tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    from cadrumo.application.modelo.declarations_list import DeclarationListGroup
    from cadrumo.application.modelo.source_policy import SourceFamily
    from cadrumo.application.modelo.work_form_findings import ModeloFormAttention
    from cadrumo.application.modelo.work_form_models import ModeloFormOrigin, ModeloFormSourceState
    from cadrumo.application.modelo.work_form_next_step import ModeloFormNextAction
    from cadrumo.application.modelo.work_form_wording import SOURCE_WORDED_ORIGINS
    from cadrumo.domain.deadlines.festivos import DeadlineHolidayCoverage
    from cadrumo.domain.modelos.calculation_revision_sources import CalculationNoteSentence
    from cadrumo.domain.modelos.verification_report import VerificationCompletenessStatus

    complete = {DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY, DeadlineHolidayCoverage.NOT_SHIFTED}
    return {
        CALCULATION_NOTE_FACT_FAMILY: values(CalculationNoteSentence),
        CALCULATION_NOTE_KIND_FAMILY: _calculation_note_kind_members(),
        "workspace.declarations.holiday_coverage.": values(c for c in DeadlineHolidayCoverage if c not in complete),
        "workspace.declarations.list.group.": values(
            group for group in DeclarationListGroup if group is not DeclarationListGroup.AEAT_UNLINKED
        ),
        "workspace.declarations.value.": ("no", "yes"),
        # The orders the declarations page offers.
        "workspace.declarations.list.sort.": (
            "deadline",
            "declaration",
            "modelo",
            "result",
            "state",
            "work_order",
        ),
        # The prototype's sentences for a withheld file, named by what clears the hold.
        "workspace.modelo.export.": ("confirm_first", "resolve_first", "verify_first"),
        "workspace.modelo.filing.copy.": filing_copies(),
        # The save formats the filing view asks a location for.
        "workspace.modelo.filing.filter.": ("boe", "csv", "pdf", "xlsx", "xml", "zip"),
        "workspace.modelo.issues.verdict.": values(VerificationCompletenessStatus),
        "workspace.modelo.legend.meaning.origin.": values(ModeloFormOrigin),
        "workspace.modelo.level.": values(ModeloFormAttention),
        "workspace.modelo.next_button.": values(
            [action for action in ModeloFormNextAction if action is not ModeloFormNextAction.RECORDED]
            + ["add_receipt", "see_missing"]
        ),
        "workspace.modelo.origin_source.": tuple(
            sorted(
                {
                    *enumerated("workspace.modelo.origin_source."),
                    *(f"{o.value}.named_filing" for o in SOURCE_WORDED_ORIGINS),
                }
            )
        ),
        "workspace.modelo.origin_source.imported.": values(SourceFamily),
        "workspace.modelo.sources.": values(
            state for state in ModeloFormSourceState if state is not ModeloFormSourceState.PRODUCED
        ),
        "workspace.modelo.surface.correct.": surfaces,
        "workspace.modelo.surface.open.": surfaces,
    }


def _workspace_families() -> Mapping[str, tuple[str, ...]]:
    """Return the shared wording families the desktop Modelo workspace composes, as ``prefix -> members``.

    Each member set is the application vocabulary the window renders, read from
    the vocabulary or from the f-string registry that already enumerates it, so
    a member the application adds is generated with it. A new member also needs
    its catalogue key, and a catalogue change regenerates these strings.
    """
    from cadrumo.application.modelo.source_policy import SourceSurface
    from cadrumo.core.modelo_export_artefact import ModeloExportArtefact

    from .fstring_registry import get_registered_keys

    registered = get_registered_keys()

    def enumerated(prefix: str) -> tuple[str, ...]:
        return tuple(sorted(key.removeprefix(prefix) for key in registered if key.startswith(prefix)))

    def values(members: Iterable[object]) -> tuple[str, ...]:
        return tuple(sorted(str(getattr(member, "value", member)) for member in members))

    surfaces = values(surface for surface in SourceSurface if surface is not SourceSurface.NONE)
    copies = [*values(a for a in ModeloExportArtefact if a is not ModeloExportArtefact.FICHERO_BOE), "package"]

    def enumerated_families() -> dict[str, tuple[str, ...]]:
        return {
            prefix: enumerated(prefix)
            for prefix in (
                "workspace.declarations.calendar.aeat.",
                "workspace.declarations.lifecycle.",
                "workspace.declarations.list.state.",
                "workspace.modelo.disclosure.",
                "workspace.modelo.editor.placeholder.",
                "workspace.modelo.editability.",
                "workspace.modelo.not_writable.",
                "workspace.modelo.origin.",
                "workspace.modelo.period.month_",
                "workspace.modelo.period.quarter_",
                "workspace.modelo.review.effect.",
            )
        }

    families = enumerated_families()

    def filing_copies() -> tuple[str, ...]:
        return tuple(sorted(f"{copy}.{part}" for copy in copies for part in ("action", "detail")))

    families |= _composed_families(enumerated, values, surfaces, filing_copies)
    return MappingProxyType(families)


#: The Modelo and declarations wording every frontend shares, as the desktop
#: workspace composes it at runtime. Unlike the shell's own families, the
#: members are not spelled out again: :data:`WORKSPACE_KEYS` expands them.
WORKSPACE_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = _workspace_families()

#: The keys the Modelo workspace names literally, shared and desktop-only,
#: with every family member.
WORKSPACE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "desktop.declarations.close",
        "desktop.declarations.loading",
        "desktop.declarations.maximize",
        "desktop.declarations.position",
        "desktop.declarations.read_failed",
        "desktop.declarations.retry",
        "desktop.declarations.search.label",
        "desktop.declarations.show.label",
        "desktop.declarations.signed_out",
        "desktop.modelo.correction.kind_label",
        "desktop.modelo.correction.motive_label",
        "desktop.modelo.correction.values_label",
        "desktop.modelo.details.close",
        "desktop.modelo.details.hide",
        "desktop.modelo.details.show",
        "desktop.modelo.discard.confirm",
        "desktop.modelo.discard.lead",
        "desktop.modelo.discard.reason",
        "desktop.modelo.form.pages",
        "desktop.modelo.keys.change",
        "desktop.modelo.keys.delete",
        "desktop.modelo.keys.leave",
        "desktop.modelo.keys.move",
        "desktop.modelo.keys.next_attention",
        "desktop.modelo.outline.label",
        "desktop.modelo.rename.name",
        "desktop.modelo.rename.save",
        "desktop.modelo.search.label",
        "desktop.modelo.side.label",
        "desktop.modelo.side.outline",
        "desktop.modelo.view.form",
        "desktop.modelo.views.label",
        "workspace.declarations.calendar.aeat.justificante_verified",
        "workspace.declarations.calendar.evidence.disagrees",
        "workspace.declarations.calendar.legal.due_today",
        "workspace.declarations.destination.overview",
        "workspace.declarations.due.days_late",
        "workspace.declarations.due.days_left",
        "workspace.declarations.due.on",
        "workspace.declarations.hub.holidays_national_only",
        "workspace.declarations.list.all_recorded",
        "workspace.declarations.list.column.deadline",
        "workspace.declarations.list.column.declaration",
        "workspace.declarations.list.column.modelo",
        "workspace.declarations.list.column.period",
        "workspace.declarations.list.column.result",
        "workspace.declarations.list.column.state",
        "workspace.declarations.list.filter.all",
        "workspace.declarations.list.filter.recorded",
        "workspace.declarations.list.filter.todo",
        "workspace.declarations.list.group.maybe",
        "workspace.declarations.list.group.recorded",
        "workspace.declarations.list.key.new",
        "workspace.declarations.list.new.already_started",
        "workspace.declarations.list.new.another",
        "workspace.declarations.list.new.create_declaration",
        "workspace.declarations.list.new.creating",
        "workspace.declarations.list.new.expected",
        "workspace.declarations.list.new.failed",
        "workspace.declarations.list.new.no_match",
        "workspace.declarations.list.new.none",
        "workspace.declarations.list.new.open_count",
        "workspace.declarations.list.new.open_it",
        "workspace.declarations.list.new.other",
        "workspace.declarations.list.new.refused",
        "workspace.declarations.list.new.saved_unread",
        "workspace.declarations.list.new.search_placeholder",
        "workspace.declarations.list.new.unknown",
        "workspace.declarations.list.new.unknown_next",
        "workspace.declarations.list.new.which_modelo",
        "workspace.declarations.list.new.which_period",
        "workspace.declarations.list.new.which_year",
        "workspace.declarations.list.new.year",
        "workspace.declarations.list.next.check_aeat",
        "workspace.declarations.list.next.continue",
        "workspace.declarations.list.next.create_file",
        "workspace.declarations.list.next.fix",
        "workspace.declarations.list.next.link_aeat",
        "workspace.declarations.list.next.start",
        "workspace.declarations.list.no_match",
        "workspace.declarations.list.none_listed",
        "workspace.declarations.list.search.modelo",
        "workspace.declarations.list.sort.amount",
        "workspace.declarations.list.sort.by",
        "workspace.declarations.list.sort.modelo",
        "workspace.declarations.list.sort.work_order",
        "workspace.declarations.list.state.aeat_unlinked",
        "workspace.declarations.list.state.not_started",
        "workspace.declarations.value.result_unknown",
        "workspace.declarations.work_state.descartado",
        "workspace.modelo.about.generated",
        "workspace.modelo.about.official",
        "workspace.modelo.about.title",
        "workspace.modelo.apply_prerequisite.action",
        "workspace.modelo.attention.staged",
        "workspace.modelo.calculate.at_risk_cancel",
        "workspace.modelo.calculate.at_risk_proceed",
        "workspace.modelo.calculate.at_risk_title",
        "workspace.modelo.calculate.operator_entries_unknown",
        "workspace.modelo.correction.confirm",
        "workspace.modelo.correction.kind",
        "workspace.modelo.correction.lead",
        "workspace.modelo.correction.title",
        "workspace.modelo.details.card_unavailable",
        "workspace.modelo.details.choose_box",
        "workspace.modelo.details.constraints",
        "workspace.modelo.details.formula_incomplete",
        "workspace.modelo.details.is_result",
        "workspace.modelo.details.legal_basis",
        "workspace.modelo.details.official_text",
        "workspace.modelo.details.reach",
        "workspace.modelo.details.reach_others",
        "workspace.modelo.details.reading",
        "workspace.modelo.details.retrieved",
        "workspace.modelo.details.undo",
        "workspace.modelo.details.uses_outside_many",
        "workspace.modelo.details.uses_outside_one",
        "workspace.modelo.details.what_it_means",
        "workspace.modelo.details.worked_out_from",
        "workspace.modelo.disclosure.official_spanish",
        "workspace.modelo.editability.no_admission",
        "workspace.modelo.editor.block.where_from",
        "workspace.modelo.editor.cancel",
        "workspace.modelo.editor.confirm",
        "workspace.modelo.editor.new_value_for_box",
        "workspace.modelo.editor.not_checked",
        "workspace.modelo.editor.reading",
        "workspace.modelo.editor.replace_here",
        "workspace.modelo.editor.rules_incomplete",
        "workspace.modelo.editor.unreadable",
        "workspace.modelo.filed.read_only",
        "workspace.modelo.filing.add_receipt_pdf",
        "workspace.modelo.filing.add_receipt_to_confirm",
        "workspace.modelo.filing.after_filed_title",
        "workspace.modelo.filing.after_filing",
        "workspace.modelo.filing.also_other_way",
        "workspace.modelo.filing.at_aeat",
        "workspace.modelo.filing.check_first",
        "workspace.modelo.filing.completeness_unverified",
        "workspace.modelo.filing.export_again",
        "workspace.modelo.filing.export_again_warning",
        "workspace.modelo.filing.export_file",
        "workspace.modelo.filing.file_current",
        "workspace.modelo.filing.file_earlier",
        "workspace.modelo.filing.file_exported",
        "workspace.modelo.filing.file_format",
        "workspace.modelo.filing.file_local",
        "workspace.modelo.filing.file_title",
        "workspace.modelo.filing.filter.receipt",
        "workspace.modelo.filing.how_to_upload",
        "workspace.modelo.filing.kept_locally",
        "workspace.modelo.filing.lead",
        "workspace.modelo.filing.not_confirmed_yet",
        "workspace.modelo.filing.not_yet",
        "workspace.modelo.filing.open_check",
        "workspace.modelo.filing.other_copies",
        "workspace.modelo.filing.receipt_differs",
        "workspace.modelo.filing.receipt_matches",
        "workspace.modelo.filing.receipt_missing",
        "workspace.modelo.filing.record_as_filed",
        "workspace.modelo.filing.record_lead",
        "workspace.modelo.filing.recorded_here",
        "workspace.modelo.filing.saved",
        "workspace.modelo.filing.show_filed_file",
        "workspace.modelo.filing.show_in_folder",
        "workspace.modelo.filing.title",
        "workspace.modelo.filter.empty",
        "workspace.modelo.filter.only_mine",
        "workspace.modelo.grid.records_read_only",
        "workspace.modelo.grid.records_unknown",
        "workspace.modelo.header.file_out_of_date",
        "workspace.modelo.header.own_calculation",
        "workspace.modelo.header.result.failed",
        "workspace.modelo.header.result.negative",
        "workspace.modelo.header.result.no_result_box",
        "workspace.modelo.header.result.not_calculated",
        "workspace.modelo.header.result.out_of_date_until_applied",
        "workspace.modelo.header.result.provisional",
        "workspace.modelo.header.result.to_carry_forward",
        "workspace.modelo.header.result.to_deduct_later",
        "workspace.modelo.header.result.to_pay",
        "workspace.modelo.header.result.to_refund",
        "workspace.modelo.header.result.unknown",
        "workspace.modelo.header.result.zero",
        "workspace.modelo.help.feeds",
        "workspace.modelo.help.no_explanation",
        "workspace.modelo.history.changes_applied",
        "workspace.modelo.history.discard",
        "workspace.modelo.history.lead",
        "workspace.modelo.history.read_from_aeat",
        "workspace.modelo.history.rename",
        "workspace.modelo.history.title",
        "workspace.modelo.issues.title",
        "workspace.modelo.issues.verdict.none",
        "workspace.modelo.key.close",
        "workspace.modelo.key.sources",
        "workspace.modelo.leave.discard",
        "workspace.modelo.legend.group.keys",
        "workspace.modelo.legend.group.needs_you",
        "workspace.modelo.legend.meaning.mark.staged",
        "workspace.modelo.legend.meaning.origin.not_calculated_yet",
        "workspace.modelo.legend.meaning.origin.not_imported_yet",
        "workspace.modelo.legend.meaning.origin.overrides_source",
        "workspace.modelo.legend.name.done",
        "workspace.modelo.modelo_title",
        "workspace.modelo.next.apply",
        "workspace.modelo.next.recorded",
        "workspace.modelo.next.verify",
        "workspace.modelo.next_button.apply",
        "workspace.modelo.notes.lead",
        "workspace.modelo.notes.title",
        "workspace.modelo.notes.unworded",
        "workspace.modelo.operation.checked.complete",
        "workspace.modelo.operation.done",
        "workspace.modelo.operation.not_done",
        "workspace.modelo.origin.calculated",
        "workspace.modelo.origin.calculation_failed",
        "workspace.modelo.origin.default_to_confirm",
        "workspace.modelo.origin_held_zero.optional_empty",
        "workspace.modelo.origin_source.imported.earlier_filings_none",
        "workspace.modelo.outcome.failed",
        "workspace.modelo.outcome.not_done",
        "workspace.modelo.outcome.refused",
        "workspace.modelo.outcome.unknown",
        "workspace.modelo.page.calculation_details",
        "workspace.modelo.page.does_not_apply",
        "workspace.modelo.page.only_if_it_applies",
        "workspace.modelo.page.unplaced",
        "workspace.modelo.page.working_figures",
        "workspace.modelo.period.annual",
        "workspace.modelo.rate.printed_by_form",
        "workspace.modelo.read_again",
        "workspace.modelo.rebase.changed",
        "workspace.modelo.rebase.dropped",
        "workspace.modelo.rebase.moved",
        "workspace.modelo.rebase.still_moving",
        "workspace.modelo.repeating",
        "workspace.modelo.review.acknowledge",
        "workspace.modelo.review.and_more",
        "workspace.modelo.review.apply",
        "workspace.modelo.review.applying",
        "workspace.modelo.review.back",
        "workspace.modelo.review.before_changed",
        "workspace.modelo.review.blocked",
        "workspace.modelo.review.check_again",
        "workspace.modelo.review.check_failed",
        "workspace.modelo.review.checking",
        "workspace.modelo.review.discard",
        "workspace.modelo.review.displacing",
        "workspace.modelo.review.effect.restore",
        "workspace.modelo.review.findings_heading",
        "workspace.modelo.review.none",
        "workspace.modelo.review.nothing_saved",
        "workspace.modelo.review.operator_entries_at_risk",
        "workspace.modelo.review.operator_entries_unknown",
        "workspace.modelo.review.title",
        "workspace.modelo.review.unknown",
        "workspace.modelo.search.placeholder",
        "workspace.modelo.section.box",
        "workspace.modelo.section.pending",
        "workspace.modelo.sources.go_to_box",
        "workspace.modelo.sources.lead",
        "workspace.modelo.sources.title",
        "workspace.modelo.stage_refused.nothing_to_clear",
        "workspace.modelo.staged.clear",
        "workspace.modelo.staged.restore",
        "workspace.modelo.step.review",
        "workspace.modelo.summary.blocked",
        "workspace.modelo.summary.calculated",
        "workspace.modelo.summary.entered",
        "workspace.modelo.summary.imported",
        "workspace.modelo.summary.needs_you",
        "workspace.modelo.summary.not_calculated",
        "workspace.modelo.summary.title",
        "workspace.modelo.todo.failed",
        "workspace.modelo.todo.failed_lead",
        "workspace.modelo.todo.none",
        "workspace.modelo.todo.title",
        "workspace.modelo.value.not_known_yet",
        "workspace.modelo.was",
    }
) | frozenset(f"{prefix}{member}" for prefix, members in WORKSPACE_FAMILIES.items() for member in members)

#: The spending categories the ledger names, and finds by the words a
#: statement prints for them.
