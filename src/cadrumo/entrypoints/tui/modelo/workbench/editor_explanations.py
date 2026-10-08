"""Public source and effect explanations shown by the casilla editor."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.casilla_help_reach import ModeloHelpBoxV1, ModeloHelpReachV1
from .....application.modelo.source_policy import SourceFamily, source_policy
from .....application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormValueSource,
    ModeloWorkForm,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .vocabulary import (
    SOURCE_WORDED_ORIGINS,
    TYPED_EDITABILITIES,
    holds_nothing,
    no_earlier_filing,
    origin_explanation,
    origin_source_words_key,
    origin_words,
    set_by_form,
)
from .wording import period_words

if TYPE_CHECKING:
    from .header import ResultView

_CHAIN_JOIN = " → "
_OTHERS_NAMED = 3


def _source_labels(field: ModeloFormField) -> tuple[str, ...]:
    """Name each source feeding ``field`` once, in the order the form lists them."""
    source = field.source
    keys = [binding.policy.label_key for binding in field.bindings]
    if not keys and source is not None and source.source_kind is not None:
        keys.append(source_policy(source.source_kind).label_key)
    return tuple(dict.fromkeys(tr(key) for key in keys))


def _unreachable_entry(field: ModeloFormField) -> bool:
    """Whether a box fed by the filer's entries cannot be reached and holds nothing."""
    source = field.source
    return (
        source is not None
        and source.family is SourceFamily.YOUR_ENTRIES
        and field.editability not in TYPED_EDITABILITIES
        and holds_nothing(field.value)
    )


def _aeat_where_from_text(
    field: ModeloFormField,
    source: ModeloFormValueSource,
    *,
    aeat_imported: date | None,
    language: OutputLanguage | None,
) -> str | None:
    if source.family is not SourceFamily.AEAT_DRAFT:
        return None
    if aeat_imported is None or language is None:
        return None
    imported = field.model_copy(update={"origin": ModeloFormOrigin.IMPORTED})
    return origin_words(imported, aeat_imported=aeat_imported, language=language)


def _source_where_from_text(field: ModeloFormField, source: ModeloFormValueSource) -> str:
    family_words = tr(origin_source_words_key(ModeloFormOrigin.IMPORTED, source.family))
    worded = field.origin in SOURCE_WORDED_ORIGINS or set_by_form(field)
    lines: list[str] = [] if worded else [family_words]
    if source.family is not SourceFamily.AEAT_DRAFT:
        labels = _source_labels(field)
        if labels:
            lines.append(" · ".join(labels))
        lines.extend(
            tr(
                "tui.modelo.workbench.origin_source.imported.named_filing",
                modelo=filing.modelo,
                period=period_words(filing.period),
            )
            for filing in source.earlier_filings
        )
    return "\n".join(lines or [family_words])


def where_from_text(
    field: ModeloFormField,
    *,
    aeat_imported: date | None = None,
    language: OutputLanguage | None = None,
) -> str | None:
    """Say where a sourced value comes from, beyond the kind of place its "Now" line already names.

    The answer names each source that feeds the box, and the earlier
    declarations a carried value is read from. The kind of place leads only
    when the "Now" line does not already say it, as for an assumed or a typed
    value over a source. A value taken from imported AEAT data names only
    that, with the day it was imported when ``aeat_imported`` gives it, because
    the sources its binding would otherwise read did not supply it. A box fed
    by the filer's entries that none of them can reach here, and that holds
    nothing, names no source: nothing the filer can use puts a value there. A
    carry with no earlier declaration to carry from names no filing either: it
    says why the box holds zero, or nothing when the "Now" line has said it.
    """
    source = field.source
    if source is None or _unreachable_entry(field):
        return None
    if no_earlier_filing(field):
        return origin_explanation(field)
    aeat_words = _aeat_where_from_text(field, source, aeat_imported=aeat_imported, language=language)
    if aeat_words is not None:
        return aeat_words
    return _source_where_from_text(field, source)


def _label(form: ModeloWorkForm | None, step: ModeloHelpBoxV1) -> str | None:
    """The form's own name for the box ``step`` passes through; ``None`` when it does not list it."""
    if form is None:
        return None
    for field in form.fields():
        address = field.address
        if isinstance(address, ModeloFormCasillaAddressV1) and address.casilla_id == step.casilla_id:
            return field.label.text
    return None


def _calculated_result_text(
    form: ModeloWorkForm | None,
    step: ModeloHelpBoxV1,
    result: ResultView | None,
) -> str | None:
    settling = None if form is None else form.result
    calculated = (
        form is not None
        and settling is not None
        and settling.casilla_id == step.casilla_id
        and settling.value is not None
        and form.calculation_revision_id is not None
    )
    if not calculated or result is None or result.failed:
        return None
    if result.settled is not None:
        words, amount = result.settled
        now = tr("tui.modelo.workbench.editor.affects.now", amount=amount)
        return f"{step.box} {words} {now}"
    return f"{step.box} {result.short_text}"


def _result_step(form: ModeloWorkForm | None, step: ModeloHelpBoxV1, result: ResultView | None) -> str:
    """The result box at the chain's end, with what the declaration settles now once calculated."""
    calculated = _calculated_result_text(form, step, result)
    if calculated is not None:
        return calculated
    label = _label(form, step)
    return step.box if label is None else f"{step.box} {label}"


def _non_result_affects_text(card: ModeloCasillaHelpCardV1, reach: ModeloHelpReachV1 | None) -> str | None:
    if reach is None:
        return ", ".join(card.feeds) or None
    lines = [tr("tui.modelo.workbench.editor.affects.not_result")]
    if card.feeds:
        lines.append(tr("tui.modelo.workbench.help.feeds", boxes=", ".join(card.feeds)))
    return "\n".join(lines)


def _reachable_affects_text(
    card: ModeloCasillaHelpCardV1,
    reach: ModeloHelpReachV1,
    form: ModeloWorkForm | None,
    result: ResultView | None,
) -> str:
    steps = [step.box for step in reach.path]
    first = reach.path[0]
    label = _label(form, first)
    if label is not None and len(steps) > 1:
        steps[0] = f"{first.box} {label}"
    steps[-1] = _result_step(form, reach.path[-1], result)
    lines = [_CHAIN_JOIN.join(steps)]
    if reach.others:
        named = ", ".join(box.box for box in reach.others) if len(reach.others) <= _OTHERS_NAMED else len(reach.others)
        lines.append(tr("tui.modelo.workbench.editor.affects.others", count=named))
    return "\n".join(lines)


def affects_text(
    card: ModeloCasillaHelpCardV1 | None,
    form: ModeloWorkForm | None = None,
    *,
    result: ResultView | None = None,
) -> str | None:
    """Say what a change reaches: the chain to the result or that it does not change it.

    An unread card says nothing. The chain follows the fewest calculations
    from this box to the result, using the form's labels and settled result;
    any further boxes follow as names or a count. Where no result is reachable,
    the answer says so and lists what this box feeds.
    """
    if card is None:
        return None
    if card.is_result:
        return tr("tui.modelo.workbench.editor.affects.is_result")
    if card.reach is None or not card.reach.path:
        return _non_result_affects_text(card, card.reach)
    return _reachable_affects_text(card, card.reach, form, result)


__all__ = ["affects_text", "where_from_text"]
