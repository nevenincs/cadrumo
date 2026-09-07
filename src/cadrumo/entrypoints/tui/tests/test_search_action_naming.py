"""Every action the workbench can dispatch is named, and only those are.

``workbench_action_label`` is the single naming authority for an operator
action: the palette and Home resolve the same identifier to the same words, so
a suggested task and the command that performs it cannot be described
differently. It falls back to generic copy for an unmapped id, which is the
right runtime behaviour and also why both failure directions were invisible.

Three mapped ids named actions the catalogue does not hold, so their copy could
never be reached by anything the workbench can dispatch. Meanwhile
``operator.modelo.work.revisions`` -- emitted by the real Home generation --
had no entry at all, so a suggested task the operator is offered rendered as
"Available workbench action". The map was simultaneously carrying dead copy and
missing live copy, and the fallback hid both.
"""

from __future__ import annotations

import pytest

from ....application.operator_actions.catalogue import lookup_action
from ..search import _ACTION_LOCALE_KEYS, workbench_action_label

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_GENERIC_FALLBACK_ID = "operator.nothing.maps.here"


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

    Asserted against the fallback string rather than the expected words, so the
    test states the property (this action is named) instead of pinning one
    locale's wording.
    """
    generic = workbench_action_label(_GENERIC_FALLBACK_ID, locale="en")
    named = workbench_action_label("operator.modelo.work.revisions", locale="en")

    assert named != generic
    assert named.strip()


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_the_revisions_action_is_named_in_every_supported_locale(locale: str) -> None:
    """A key present in one catalogue and absent in another still falls back."""
    generic = workbench_action_label(_GENERIC_FALLBACK_ID, locale=locale)

    assert workbench_action_label("operator.modelo.work.revisions", locale=locale) != generic


def test_an_unmapped_action_still_degrades_to_generic_copy() -> None:
    """The fallback stays: an unnamed action must render, not raise.

    Retiring the three dead entries relies on this -- their ids survive in test
    and devtools fixtures, which must keep rendering rather than crash.
    """
    assert workbench_action_label(_GENERIC_FALLBACK_ID, locale="en").strip()
    assert workbench_action_label("operator.ledger.open", locale="en") == workbench_action_label(
        _GENERIC_FALLBACK_ID,
        locale="en",
    )
