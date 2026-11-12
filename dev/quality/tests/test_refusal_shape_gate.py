"""Gate: every registered refusal the modelo and filing code builds gives words and a door.

Words: the registered message key and every literal ``translated_message`` key
resolve in es, ca, en and hu, with no allowlist.

Door: a construction passes a next step or a terminal verdict, or its class
carries one by default. Sites that predate the gate are listed in
``dev/quality/metadata/refusal_shape_ratchet.json``; the list may only shrink.
Free English text handed over as the first argument with no catalogue key is a
second shrink-only list. Regenerate both with
``python -m dev.quality.refusal_shape --write``.
"""

from __future__ import annotations

import pytest

from dev.quality.refusal_shape import (
    GOVERNED_TREES,
    Site,
    doorless_site_ids,
    free_text_site_ids,
    missing_words,
    read_ratchet,
    scan_repository,
    scan_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REGENERATE = "regenerate with `python -m dev.quality.refusal_shape --write` after fixing"


@pytest.fixture(scope="module")
def sites() -> list[Site]:
    return scan_repository()


def _shrink_only(current: list[str], recorded: list[str], *, what: str, remedy: str) -> None:
    added = sorted(set(current) - set(recorded))
    stale = sorted(set(recorded) - set(current))
    assert not added, f"new {what} not in the ratchet; {remedy}:\n" + "\n".join(added)
    assert not stale, (
        f"the ratchet lists {what} that now pass or no longer exist; remove them ({_REGENERATE}):\n" + "\n".join(stale)
    )


def test_the_scan_still_sees_every_governed_tree(sites: list[Site]) -> None:
    """A population floor: an unreadable tree would make every assertion below vacuous."""
    assert len(sites) > 100
    for tree in GOVERNED_TREES:
        assert any(site.path.startswith(tree + "/") for site in sites), f"no registered construction under {tree}"


def test_every_registered_and_literal_message_key_is_served_in_all_locales(sites: list[Site]) -> None:
    assert missing_words(sites) == []


def test_no_new_refusal_is_built_without_a_door(sites: list[Site]) -> None:
    _shrink_only(
        doorless_site_ids(sites),
        read_ratchet()["doorless"],
        what="doorless refusal site(s)",
        remedy="give each a next_step, precondition_verdict or precondition_failure (or a class-level default door)",
    )


def test_no_new_refusal_hands_over_free_text(sites: list[Site]) -> None:
    _shrink_only(
        free_text_site_ids(sites),
        read_ratchet()["free_text"],
        what="free-text refusal site(s)",
        remedy="pass a catalogue key as translated_message instead of english text as the first argument",
    )


_FIXTURE = """
from cadrumo.application.filing.errors import ModeloApplicationError
from cadrumo.application.modelo.action_errors import ModeloOperationSubjectNotWorkUnitError, ModeloRecordNotFoundError


class Holder:
    def doorless(self):
        raise ModeloRecordNotFoundError(translated_message="no.such.catalogue.key")

    def doorless_again(self):
        raise ModeloRecordNotFoundError("english words only")

    def doored(self, step):
        raise ModeloOperationSubjectNotWorkUnitError(next_step=step)

    def none_is_no_door(self):
        raise ModeloOperationSubjectNotWorkUnitError(next_step=None)

    def class_default(self):
        raise ModeloApplicationError(translated_message="no.such.catalogue.key")
"""

_FIXTURE_PATH = "synthetic_tree/holder.py"


def test_the_gate_detects_a_doorless_site_a_free_text_site_and_an_unknown_key() -> None:
    """Detector teeth on an isolated synthetic module."""
    found = scan_source(_FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")
    by_scope = {site.qualname: site for site in found}

    assert doorless_site_ids(found) == sorted(
        by_scope[name].site_id for name in ("Holder.doorless", "Holder.doorless_again", "Holder.none_is_no_door")
    )
    assert free_text_site_ids(found) == [by_scope["Holder.doorless_again"].site_id]
    assert by_scope["Holder.doored"].has_door
    assert by_scope["Holder.class_default"].has_door
    missing = missing_words(found)
    assert {entry.split(":", 1)[1] for entry in missing} == {"no.such.catalogue.key"}
    assert len(missing) == 4


def test_site_identity_survives_unrelated_line_shifts() -> None:
    """The ratchet key carries no line number, so blank lines above change nothing."""
    first = scan_source(_FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")
    shifted = scan_source("\n\n\n" + _FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")
    assert [site.site_id for site in first] == [site.site_id for site in shifted]
    assert [site.line + 3 for site in first] == [site.line for site in shifted]
