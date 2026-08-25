"""Registered-values projection for the setup flow's review overview.

The paged review surface composes three channels; the flow's entire
domain contribution to the overview is the ``registered_values`` mapping
(``page_key -> display string``) this module produces from the active
profile record (:class:`UserProfileRecord`). The string IS the contract — the frontend renders it and
never re-formats it — so every display decision (choice-label resolution,
the localized yes/no pair, the non-official-evidence suffix) is made here,
at projection time.

Four binding properties, per the page-catalogue-mapping reference:

* **Coverage** — every profile-bound page whose fact is on record, not
  only the pages an edit walk changed. The setup flow carries no
  repeating group today, so the projection keys each page by its question
  id (the identity projection where ``domain_key`` equals the fact path).
* **Display-ready strings** — closed-set tokens resolve to their choice
  LABEL through the catalogue's label copy; booleans render as the
  localized yes/no pair; dates and decimals pass through in their stored
  (ISO / decimal) display form. Projection runs AFTER output-language
  activation (the caller invokes it lazily at frontend construction), so
  labels resolve in the operator's chosen language.
* **No pre-masking** — a secret page's registered value is supplied in
  the clear. The review screen owns masking through its widget-kind
  lookup; a second masking authority here could only drift from it.
* **Nothing richer than the string** — no provenance column and no typed
  per-row payload. The one provenance fact worth surfacing — a value
  derived from the G313 censo artefact is non-official evidence — is
  ENCODED into the display string as a localized suffix, appended exactly
  when the underlying fact carries the artefact provenance token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ...core.i18n import tr
from ...core.parsing import parse_bool
from ._format_hints import REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY
from ._models import WizardQuestion

if TYPE_CHECKING:
    from ...domain.user_profile import UserProfileRecord
    from ._models import WizardFlow

#: The localized yes/no pair the CONFIRM widget already renders through the
#: substrate frontend (``flows.confirm.{yes,no}``). Reused here so a boolean
#: registered value reads identically to the page an operator answered.
_CONFIRM_TRUE_LOCALE_KEY = "flows.confirm.yes"
_CONFIRM_FALSE_LOCALE_KEY = "flows.confirm.no"


def _render_choice_label(question: WizardQuestion, raw: str) -> str:
    """Resolve a closed-set token (or comma-joined token set) to its label(s).

    A SELECT stores one token; a CHECKBOX stores a comma-joined token set.
    Each token is mapped to its :class:`WizardChoice` label copy; an
    unknown token (not in the catalogue's choices) falls through as its raw
    token so a stale stored value is shown, never dropped.
    """
    labels_by_value = {choice.value: str(choice.label) for choice in question.choices}
    tokens = [token for token in raw.split(",") if token] if raw else []
    rendered = [tr(labels_by_value[token]) if token in labels_by_value else token for token in tokens]
    return ", ".join(rendered)


def _render_display_value(question: WizardQuestion, raw: str) -> str:
    """Render one on-record token as the display-ready review string.

    Closed-set tokens resolve to their choice label; booleans render as the
    localized yes/no pair; every other value (dates, decimals, free text,
    secrets) passes through in its stored form — the review screen masks
    secrets, so no masking happens here.
    """
    if question.choices:
        return _render_choice_label(question, raw)
    if question.answer_type is bool:
        return tr(_CONFIRM_TRUE_LOCALE_KEY) if parse_bool(raw) is True else tr(_CONFIRM_FALSE_LOCALE_KEY)
    return raw


def project_registered_values(
    flow: WizardFlow,
    record: UserProfileRecord | None,
) -> dict[str, str]:
    """Project the active :class:`UserProfileRecord` into the review overview's page-keyed strings.

    Every profile-bound page whose fact is on record contributes one entry,
    keyed by the question id, whose value is the display-ready string. When
    the underlying fact was sourced from the G313 censo artefact, the
    localized non-official-evidence suffix is appended to the string so the
    operator sees the provenance without a separate channel.
    """
    from ..user_profile.projections import record_to_effective_facts

    effective = record_to_effective_facts(record)
    registered: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            key = question.profile_key
            entry = effective.get(key) if key is not None else None
            # A CLEARED path is present here with a null value, where the
            # value-only projection simply omitted it. Skipping it explicitly
            # keeps the rendered set identical while making the deletion a
            # case the reader can see rather than an accident of filtering.
            if entry is None or entry.value is None:
                continue
            display = _render_display_value(question, entry.value)
            if entry.source == PROVENANCE_SOURCE_CENSO_ARTEFACT:
                display = f"{display} {tr(REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY)}"
            registered[question.id] = display
    return registered


__all__ = ["project_registered_values"]
