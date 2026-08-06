"""Prove the attribution screen reports ownership, not mere presence.

The registry's evidence gate confirms a cited phrase is PRESENT in the cited
file, which is why four filing-grade citations to another form's provision pass
it. This screen exists to close that gap, so it is worth exactly as much as its
ability to discriminate — and a screen with no test is the shape this campaign
has spent its length removing.

Every case drives the real detector over synthetic catalogue entries, so the
assertions are about behaviour rather than about the shape of the source.
"""

from __future__ import annotations

import pytest

from ..legal_attribution_screen import Mismatch, approved_modelo_numbers, find_mismatches

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_approval_phrase_binds_its_form_number() -> None:
    """The canonical shape: one approval phrase naming one form."""
    assert approved_modelo_numbers(("Se aprueba el modelo 193",)) == frozenset({"193"})


def test_the_phrases_are_read_jointly_not_one_by_one() -> None:
    """Modelo 848's shape: approval phrase and form number in separate entries.

    A per-phrase reading demotes it, which is a mistake made and corrected
    during the grounding pass that produced this screen. Pinned so the cheaper
    reading cannot come back.
    """
    assert approved_modelo_numbers(("Aprobación del modelo", "modelo 848 del Impuesto")) == frozenset({"848"})


def test_accents_do_not_decide_the_match() -> None:
    """The corpus and the catalogue disagree on accents often enough to matter."""
    assert approved_modelo_numbers(("Aprobacion del modelo 184",)) == frozenset({"184"})
    assert approved_modelo_numbers(("Aprobación del modelo 184",)) == frozenset({"184"})


def test_a_provision_with_no_approval_phrase_makes_no_claim() -> None:
    """A framework or amending article is not an ownership claim.

    Most cited provisions establish an obligation without approving a form, and
    flagging those would bury the real findings. This is also the screen's known
    blind spot: the modelo-296 mis-attribution has exactly this shape, because
    its provision amends an annex rather than approving anything.
    """
    assert approved_modelo_numbers(("El anexo II, modelo 123", "se sustituye por el anexo I")) == frozenset()
    assert approved_modelo_numbers(("Estarán obligados a retener",)) == frozenset()
    assert approved_modelo_numbers(()) == frozenset()


def test_a_citation_to_another_forms_approval_is_reported() -> None:
    """The defect this screen exists for, over injected data."""
    entries = {"orden-x:art-1": ("Se aprueba el modelo 193",)}
    found = find_mismatches({"187": ("orden-x:art-1",)}, entries)

    assert found == [Mismatch("187", "orden-x:art-1", ("193",))]
    assert "modelo 187 cites orden-x:art-1" in found[0].render()
    assert "names modelo 193" in found[0].render()


def test_a_form_citing_its_own_approval_is_not_reported() -> None:
    """The negative control. Without it the screen could flag everything."""
    entries = {"orden-x:art-1": ("Se aprueba el modelo 193",)}

    assert find_mismatches({"193": ("orden-x:art-1",)}, entries) == []


def test_a_provision_approving_several_forms_admits_each_of_them() -> None:
    """One orden may approve a family; citing it from any member is correct."""
    entries = {"orden-x:art-1": ("Se aprueban los modelos 123 y 124",)}

    assert find_mismatches({"123": ("orden-x:art-1",), "124": ("orden-x:art-1",)}, entries) == []
    assert len(find_mismatches({"125": ("orden-x:art-1",)}, entries)) == 1


def test_an_unknown_entry_id_is_not_an_attribution_claim(tmp_path: pytest.TempPathFactory) -> None:
    """A citation to an entry this screen cannot resolve reports nothing.

    Silence here is correct rather than convenient: an unresolvable id is a
    different defect with its own owner, and inventing an attribution verdict
    from a missing entry would be the screen asserting what it does not know.
    """
    assert find_mismatches({"187": ("orden-absent:art-9",)}, {}) == []
