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

from cadrumo.application.modelo.action_errors import ModeloOperationSubjectNotWorkUnitError, ModeloRecordNotFoundError
from cadrumo.application.modelo.credit_resolution_repository import CreditResolutionRefusedError
from cadrumo.application.operations.next_step import OperationNextStepWording
from dev.quality.refusal_shape import (
    GOVERNED_TREES,
    Site,
    class_keys_its_words,
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


_KEYED_INITIALIZER_FIXTURE = """
from cadrumo.application.modelo.credit_resolution_repository import CreditResolutionRefusedError


def refuse(reason):
    raise CreditResolutionRefusedError(reason)
"""


def test_a_positional_reason_to_a_class_that_words_itself_is_not_free_text() -> None:
    """A class whose initializer always keys its words is never handed free text by a site."""
    assert class_keys_its_words(CreditResolutionRefusedError)
    assert not class_keys_its_words(ModeloRecordNotFoundError)

    (site,) = scan_source(_KEYED_INITIALIZER_FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")
    assert not site.free_text


_CANONICAL_KEY_FIXTURE = """
from cadrumo.core.errors.hierarchy import InternalInvariantError


def broken():
    raise InternalInvariantError("diagnostic english the renderer never serves")
"""


def test_positional_text_to_a_code_whose_registered_words_always_win_is_not_free_text() -> None:
    """A canonical message key is served whatever the site passes, as the error renderer does."""
    (site,) = scan_source(_CANONICAL_KEY_FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")
    assert ".canonical_" in site.message_key
    assert not site.free_text


def test_site_identity_survives_unrelated_line_shifts() -> None:
    """The ratchet key carries no line number, so blank lines above change nothing."""
    first = scan_source(_FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")
    shifted = scan_source("\n\n\n" + _FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")
    assert [site.site_id for site in first] == [site.site_id for site in shifted]
    assert [site.line + 3 for site in first] == [site.line for site in shifted]


def _doored_factory(
    cls: type[ModeloOperationSubjectNotWorkUnitError], *, step: OperationNextStepWording
) -> ModeloOperationSubjectNotWorkUnitError:
    return cls(next_step=step)


def _doorless_factory(cls: type[ModeloRecordNotFoundError], reason: str) -> ModeloRecordNotFoundError:
    return cls(reason)


def _keyed_doorless_factory(cls: type[ModeloRecordNotFoundError]) -> ModeloRecordNotFoundError:
    return cls(translated_message="no.such.catalogue.key")


def _not_a_factory(cls: type[ModeloRecordNotFoundError]) -> str:
    return cls.__name__


_FACTORY_FIXTURE = """
from cadrumo.application.modelo.action_errors import (
    ModeloOperationSubjectNotWorkUnitError,
    ModeloRecordNotFoundError,
)


def holder(step):
    ModeloRecordNotFoundError.direct_first()
    raise ModeloOperationSubjectNotWorkUnitError.doored(step=step)
    raise ModeloRecordNotFoundError.doorless("words")
    raise ModeloRecordNotFoundError.keyed()
    raise ModeloRecordNotFoundError.doorless("words", next_step=step)
    ModeloRecordNotFoundError.not_a_factory()
    ModeloRecordNotFoundError.__name__.upper()
    ModeloRecordNotFoundError.missing_attribute()
    ModeloRecordNotFoundError("english words only")
"""


def test_the_gate_counts_classmethod_factory_calls_as_construction_sites(monkeypatch: pytest.MonkeyPatch) -> None:
    """A factory call is a site; its own body, the call or the class supplies the door."""
    monkeypatch.setattr(ModeloOperationSubjectNotWorkUnitError, "doored", classmethod(_doored_factory), raising=False)
    for name, function in (
        ("doorless", _doorless_factory),
        ("keyed", _keyed_doorless_factory),
        ("not_a_factory", _not_a_factory),
    ):
        monkeypatch.setattr(ModeloRecordNotFoundError, name, classmethod(function), raising=False)
    # A plain method is not a classmethod, so calling it on the class is no factory either.
    monkeypatch.setattr(ModeloRecordNotFoundError, "direct_first", lambda: None, raising=False)

    found = scan_source(_FACTORY_FIXTURE, path=_FIXTURE_PATH, module="synthetic_tree.holder")

    # Source order, one ordinal sequence per code: the doored site is the only one of its code; the other
    # four (doorless, keyed, call-door, direct) number 0 to 3.
    assert [site.ordinal for site in found] == [0, 0, 1, 2, 3]
    assert {site.qualname for site in found} == {"holder"}
    assert [site.has_door for site in found] == [True, False, False, True, False]
    assert doorless_site_ids(found) == sorted(found[index].site_id for index in (1, 2, 4))
    # Free text: positional words with no key in the factory body, as a direct construction would be.
    assert [site.free_text for site in found] == [False, True, False, True, True]
