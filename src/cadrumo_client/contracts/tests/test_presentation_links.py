"""A page link spells exactly the grammar the desktop opens, for every page it can name."""

from __future__ import annotations

import re
from typing import get_args
from uuid import UUID

import pytest

from ..presentation import PresentationDestination, destination_link

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5AA00000-0000-4000-8000-0000000000AA")
# The desktop's own grammar: a lowercase UUID and one page word, with nothing after it.
_DESKTOP_LINK = re.compile(
    r"^cadrumo://profiles/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/([a-z-]+)$"
)


def test_every_page_is_spelled_in_the_desktop_grammar() -> None:
    for destination in get_args(PresentationDestination.__value__):
        match = _DESKTOP_LINK.fullmatch(destination_link(_PROFILE, destination))
        assert match is not None, destination
        assert match.group(1) == "5aa00000-0000-4000-8000-0000000000aa"
        assert match.group(2).replace("-", "_") == destination


def test_two_word_pages_use_hyphens() -> None:
    assert (
        destination_link(_PROFILE, "aeat_sync") == "cadrumo://profiles/5aa00000-0000-4000-8000-0000000000aa/aeat-sync"
    )
    assert (
        destination_link(_PROFILE, "aeat_auth") == "cadrumo://profiles/5aa00000-0000-4000-8000-0000000000aa/aeat-auth"
    )


def test_no_link_names_the_nil_profile() -> None:
    with pytest.raises(ValueError, match="real profile"):
        destination_link(UUID(int=0), "ledger")
