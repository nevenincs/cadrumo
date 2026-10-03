"""Box help content and explanatory wording for the Modelo workbench."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormTextDisclosure,
)
from .....core.i18n.render import lookup_translation, tr
from .casilla_list_models import CasillaListEntry
from .casilla_list_values import description_text, grid_cell_title, rate_note
from .editor import read_only_reason
from .header import (
    is_result_field,
    result_view,
)
from .screen_constants import (
    _FOOTER_PRIORITY,
    _FRAGMENT_SEPARATOR,
    _HELP_ONLY_KEYS,
    _SCREEN_LOCALE_KEYS,
)
from .vocabulary import (
    ATTENTION_MARKS,
    SOURCE_WORDED_ORIGINS,
    aeat_imported_on,
    attention_words_key,
    editability_text,
    origin_explanation,
    origin_text,
)

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchHelpContentMixin:
    """Implement box help content and explanatory wording for the modelo workbench."""

    def _box_help(self: ModeloWorkbenchScreen, entry: CasillaListEntry) -> list[str]:
        """What the band says about one box: its name, its marks in words, its description and its card."""
        field = entry.field
        lines = (
            [self._state_line(entry), self._help_title(entry)]
            if self.has_class("-short")
            else [self._help_title(entry), self._state_line(entry)]
        )
        lines.append(description_text(field) or tr("tui.modelo.workbench.help.no_explanation"))
        note = rate_note(entry, self._language)
        if note is not None:
            lines.append(note)
        explained = origin_explanation(field)
        if explained is not None:
            lines.append(explained)
        card = None
        if isinstance(field.address, ModeloFormCasillaAddressV1):
            card = self._cards.get((str(field.address.casilla_id), self._language))
        if card is not None:
            lines.extend(self._card_lines(card, field))
        form = self.form
        if form is not None and is_result_field(form, field):
            view = result_view(form, self._language, staged=len(self._session.changes), recorded=self.recorded)
            if view is not None:
                lines.extend(view.help)
        return lines

    def _all_keys_text(self: ModeloWorkbenchScreen) -> str:
        """Every key the help and the legend name; on a declaration recorded as filed, none that would change it."""
        descriptions = {**self._list_locale_keys(), **_SCREEN_LOCALE_KEYS}
        hidden = self._hidden_keys()
        return " · ".join(
            self._key_label(key, descriptions[key])
            for key in (*_FOOTER_PRIORITY, *_HELP_ONLY_KEYS)
            if key not in hidden
        )

    def _help_title(self: ModeloWorkbenchScreen, entry: CasillaListEntry) -> str:
        field = entry.field
        box = f"[{field.box}] " if field.box else ""
        title = f"{box}{grid_cell_title(entry) or field.label.text}"
        if field.label.disclosure is not ModeloFormTextDisclosure.LOCALIZED:
            title = f"{title} ({tr(f'tui.modelo.workbench.disclosure.{field.label.disclosure.value}')})"
        return title

    def _state_line(self: ModeloWorkbenchScreen, entry: CasillaListEntry) -> str:
        """Where the box's value stands and what may be done about it, in the words the row uses.

        On a declaration recorded as filed the second half is why it cannot be
        changed, and a state that would ask the filer to act says only what the
        box holds, in the words its row and its panel use.
        """
        field = entry.field
        if self.recorded:
            parts = [
                origin_text(field, recorded=True, aeat_imported=aeat_imported_on(self.form), language=self._language)
            ]
            reason = read_only_reason(field, self._language, recorded=True)
            if reason is not None:
                parts.append(reason)
            return " · ".join(parts)
        parts = (
            []
            if entry.staged_replaces_absence
            else [origin_text(field, aeat_imported=aeat_imported_on(self.form), language=self._language)]
        )
        attention = entry.attention
        if attention is not None:
            parts.append(f"{ATTENTION_MARKS[attention].glyph} {tr(attention_words_key(attention))}")
        parts.append(editability_text(field))
        return " · ".join(parts)

    def _said_by_origin(self: ModeloWorkbenchScreen, field: ModeloFormField) -> frozenset[str]:
        """The sources' sentences the origin words already say: those of the kind of place they name."""
        source = field.source
        if field.origin not in SOURCE_WORDED_ORIGINS or source is None:
            return frozenset[str]()
        said: set[str] = set()
        for binding in field.bindings:
            if binding.policy.family is source.family:
                sentence = lookup_translation(binding.policy.origin_sentence_key, locale=self._language.value)
                if sentence:
                    said.add(sentence)
        return frozenset(said)

    def _card_lines(self: ModeloWorkbenchScreen, card: ModeloCasillaHelpCardV1, field: ModeloFormField) -> list[str]:
        lines: list[str] = []
        if card.formula is not None:
            lines.append(tr("tui.modelo.workbench.help.formula", formula=card.formula.text))
        said = self._said_by_origin(field)
        for origin in card.origins:
            if origin not in said:
                lines.append(tr("tui.modelo.workbench.help.origin", origin=origin))
        if card.feeds:
            lines.append(tr("tui.modelo.workbench.help.feeds", boxes=", ".join(card.feeds)))
        for quote in card.quotes:
            quoted = _FRAGMENT_SEPARATOR.join(quote.fragments)
            lines.append(tr("tui.modelo.workbench.help.official", source=quote.source, text=quoted))
        if card.legal_basis:
            lines.append(
                tr("tui.modelo.workbench.help.legal", citations="; ".join(item.text for item in card.legal_basis))
            )
        lines.extend(card.constraints)
        return lines
