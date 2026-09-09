"""Every action the workbench can dispatch is named, and an unnamed one says so.

``workbench_action_label`` is the single naming authority for an operator
action: the palette and Home resolve the same identifier to the same words, so
a suggested task and the command that performs it cannot be described
differently.

The map used to fall back to generic "available workbench action" copy for an
identifier it did not hold, which made both failure directions invisible: copy
for an id the catalogue cannot dispatch could never be reached, and an id the
catalogue does dispatch but the map missed rendered as a plausible label rather
than as a gap. The fallback is now the explicit unknown wording, so an unnamed
action is a state an operator -- and a test -- can tell apart from a named one.
"""

from __future__ import annotations

import pytest

from ....application.operator_actions.catalogue import lookup_action
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import I18N_STRICT_MISSING_KEYS
from ..search import _ACTION_LOCALE_KEYS, workbench_action_label

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UNMAPPED_ID = "operator.nothing.maps.here"
_RETIRED_IDS = ("operator.declaration.open", "operator.ledger.open", "operator.not_declared.open")


@pytest.mark.parametrize("action_id", sorted(_ACTION_LOCALE_KEYS))
def test_every_named_action_is_one_the_catalogue_can_dispatch(action_id: str) -> None:
    """Copy for an id the catalogue lacks can never reach an operator.

    ``action_candidate_id`` is an open namespace in general, but THIS map is
    the naming authority for catalogue actions specifically: an entry the
    catalogue cannot resolve names something no workbench surface can offer.
    """
    assert lookup_action(action_id) is not None


def test_the_home_revisions_action_is_named_rather_than_generically_labelled() -> None:
    """The live gap: a production-emitted action the map did not cover.

    Asserted against the unknown wording rather than the expected words, so the
    test states the property (this action is named) instead of pinning one
    locale's wording.
    """
    unknown = workbench_action_label(_UNMAPPED_ID, locale="en")
    named = workbench_action_label("operator.modelo.work.revisions", locale="en")

    assert named != unknown
    assert named.strip()


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_revisions_action_is_named_in_every_supported_locale(locale: str) -> None:
    """A key present in one catalogue and absent in another still falls back."""
    unknown = workbench_action_label(_UNMAPPED_ID, locale=locale)

    assert workbench_action_label("operator.modelo.work.revisions", locale=locale) != unknown


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_an_unnamed_action_reads_as_unknown_in_every_locale(locale: str) -> None:
    """The planted defect: an id no catalogue names must not look like one.

    An unnamed action still renders -- a table row is not the place to raise --
    but it must be distinguishable from every action the map does name, in
    every supported locale, and must not leak the raw identifier. Strict
    missing-key mode makes an untranslated catalogue a failure here rather than
    a humanised echo of the key that would pass every assertion below.
    """
    strict_token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        unknown = workbench_action_label(_UNMAPPED_ID, locale=locale)
        named = {workbench_action_label(action_id, locale=locale) for action_id in _ACTION_LOCALE_KEYS}
    finally:
        I18N_STRICT_MISSING_KEYS.reset(strict_token)

    assert unknown.strip()
    assert unknown not in named
    assert "operator." not in unknown
    assert "tui.search." not in unknown


@pytest.mark.parametrize("action_id", _RETIRED_IDS)
def test_a_retired_action_id_is_reported_unknown_rather_than_available(action_id: str) -> None:
    """The three ids the naming map retired name nothing the workbench offers.

    They survive only in navigation and search fixtures as opaque candidate
    identities, so they must keep rendering -- as the unknown state, never as
    plausible copy for an action an operator could take.
    """
    assert workbench_action_label(action_id, locale="en") == workbench_action_label(_UNMAPPED_ID, locale="en")
