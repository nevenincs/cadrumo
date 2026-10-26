"""Modelo 200 editions cite their own record design and their own approving article.

Each Modelo 200 edition names exactly one AEAT record design. Every member the
edition carries -- stated or reached by storage reuse -- that cites a record
design must cite that one: a member of an earlier edition citing the later
design claims a layout AEAT had not published for its exercise. Each edition's
applicability also names a provision that governs its first exercise, and each
box keeps the role and section of the design sheet that prints it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.record_design import extract_record_design
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_PRINTED_BOX = re.compile(r"\[([0-9]{3,6})\]")
_RESERVE_COHORT = re.compile(r" - (?P<reserve>RIC|RIIB) \d{4} - ")


def _record_designs() -> frozenset[str]:
    sources = compiled_bundled_authority().catalogues.sources
    return frozenset(ref for ref, source in sources.items() if source.kind == "record_design")


def _own_design(revision: ModeloRevision) -> str:
    (design,) = [ref for ref in revision.source_refs if ref in _record_designs()]
    return design


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _strings(item)


def foreign_design_citations(members: Mapping[str, object], own: str, designs: frozenset[str]) -> list[str]:
    """Return the members citing a record design other than ``own``, as ``member -> design``."""
    return sorted(
        f"{member} -> {text}"
        for member, payload in members.items()
        for text in set(_strings(payload))
        if text in designs and text != own
    )


_BETWEEN_EDITIONS = frozenset(
    {
        "casilla_continuidad_evolutions",
        "casilla_overrides",
        "casilla_removals",
        "casilla_positions",
        "family_overrides",
        "family_removals",
        "family_positions",
    }
)
"""Records that compare an edition with its baseline, so they cite both editions' designs by nature."""


def _members(revision: ModeloRevision) -> dict[str, object]:
    """Every hydrated member the edition asserts for itself, keyed ``family/id``, as plain data."""
    members: dict[str, object] = {}
    for name in type(revision).model_fields:
        if name in _BETWEEN_EDITIONS:
            continue
        value = getattr(revision, name)
        if isinstance(value, tuple) and value and all(hasattr(item, "model_dump") for item in value):
            for index, item in enumerate(value):
                members[f"{name}/{getattr(item, 'id', index)}"] = item.model_dump(mode="json")
        elif hasattr(value, "model_dump"):
            members[name] = value.model_dump(mode="json")
    return members


def test_every_member_of_an_edition_cites_only_that_editions_record_design() -> None:
    designs = _record_designs()
    for revision in authored_revisions(_MODELO):
        assert foreign_design_citations(_members(revision), _own_design(revision), designs) == [], revision.id


def test_the_design_citation_check_names_a_member_citing_another_editions_design() -> None:
    designs = frozenset({"design-a", "design-b"})
    members = {"application_links/export": {"source_refs": ["design-b"]}, "constructs/x": {"source_refs": ["design-a"]}}
    assert foreign_design_citations(members, "design-a", designs) == ["application_links/export -> design-b"]
    assert foreign_design_citations(members, "design-b", designs) == ["constructs/x -> design-a"]


def test_each_edition_names_an_applicability_provision_governing_its_first_exercise() -> None:
    legal = compiled_bundled_authority().catalogues.legal
    for revision in authored_revisions(_MODELO):
        governing = [
            ref
            for ref in revision.orden_aplicabilidad
            if (reference := legal[ref]).governs_periods_from is not None
            and reference.governs_periods_from <= revision.valid_from
            and (reference.governs_periods_to is None or revision.valid_from <= reference.governs_periods_to)
        ]
        assert governing, f"{revision.id} names no applicability provision governing {revision.valid_from}"
        assert all(ref in revision.legal_refs for ref in governing), revision.id


def _reserve_cohorts(revision: ModeloRevision) -> dict[str, set[str]]:
    """Map each investment reserve the edition's design prints by yearly cohort to the box numbers of every cohort."""
    sources = compiled_bundled_authority().catalogues.sources
    extraction = extract_record_design(bundled_path() / sources[_own_design(revision)].corpus_path)
    cohorts: dict[str, set[str]] = {}
    for sheet in extraction.require_complete():
        for field in sheet.fields:
            match = _RESERVE_COHORT.search(field.description)
            if match is not None:
                cohorts.setdefault(f"{sheet.name.strip()}:{match['reserve']}", set()).update(
                    _PRINTED_BOX.findall(field.description)
                )
    return cohorts


def cohort_disagreements(
    cohorts: Mapping[str, set[str]], rows: Mapping[str, tuple[str | None, tuple[str, ...], tuple[str, ...]]]
) -> list[str]:
    """Return reserves whose declared cohort boxes disagree on semantic role, top section or legal basis.

    ``rows`` maps a declared box number to ``(semantic_role, section, legal_refs)``.
    """
    disagreements = []
    for cohort, numbers in sorted(cohorts.items()):
        shapes = {(rows[n][0], rows[n][1][:1], rows[n][2]) for n in numbers if n in rows}
        if len(shapes) > 1:
            disagreements.append(f"{cohort}: {sorted(map(str, shapes))}")
    return disagreements


def test_every_cohort_box_of_one_reserve_shares_role_section_and_legal_basis() -> None:
    for revision in authored_revisions(_MODELO):
        rows = {
            str(casilla.number): (casilla.semantic_role, tuple(casilla.section), tuple(casilla.legal_refs))
            for casilla in revision.casillas
            if casilla.segmento is None
        }
        cohorts = _reserve_cohorts(revision)
        assert cohorts, f"{revision.id}: no reserve cohort read from its design, so this check proves nothing"
        assert cohort_disagreements(cohorts, rows) == [], revision.id


def test_the_cohort_check_names_a_box_filed_under_another_regime() -> None:
    cohorts = {"DP200022:RIC": {"03312", "03313"}}
    ric = (
        "is_reserva_inversiones_canarias_importe",
        ("reg_especial_reserva_inversiones_canarias",),
        ("ley-19-1994:art-27",),
    )
    cooperativa = ("is_cooperativa_base_imponible", ("reg_cooperativas",), ("ley-27-2014:art-41",))
    assert cohort_disagreements(cohorts, {"03312": ric, "03313": ric}) == []
    assert cohort_disagreements(cohorts, {"03312": cooperativa, "03313": ric}) != []


def misplaced_cohort_boxes(
    printed: Mapping[str, str], sections: Mapping[str, tuple[str, ...]]
) -> list[tuple[str, tuple[str, ...], str]]:
    """Return declared boxes whose second section level is not the cohort the design prints them in.

    ``printed`` maps a box number to its cohort token as the design prints it (``ric_2024``).
    """
    return sorted(
        (number, sections[number], cohort)
        for number, cohort in printed.items()
        if number in sections and sections[number][1:2] != (cohort,)
    )


def test_every_reserve_cohort_box_sits_in_the_cohort_its_design_prints() -> None:
    cohort_box = re.compile(r" - (?P<reserve>RIC|RIIB) (?P<year>\d{4}) - .*\[(?P<number>[0-9]{3,6})\]")
    sources = compiled_bundled_authority().catalogues.sources
    for revision in authored_revisions(_MODELO):
        extraction = extract_record_design(bundled_path() / sources[_own_design(revision)].corpus_path)
        printed = {
            match["number"]: f"{match['reserve'].lower()}_{match['year']}"
            for sheet in extraction.require_complete()
            for field in sheet.fields
            if (match := cohort_box.search(field.description)) is not None
        }
        assert printed, f"{revision.id}: no reserve cohort box read from its design, so this check proves nothing"
        sections = {str(c.number): tuple(c.section) for c in revision.casillas if c.segmento is None}
        assert misplaced_cohort_boxes(printed, sections) == [], revision.id


def test_the_cohort_placement_check_names_a_box_filed_under_the_previous_cohort() -> None:
    printed = {"01708": "riib_2024"}
    assert (
        misplaced_cohort_boxes(printed, {"01708": ("reg_especial_reserva_inversiones_illes_balears", "riib_2024")})
        == []
    )
    assert misplaced_cohort_boxes(
        printed, {"01708": ("reg_especial_reserva_inversiones_illes_balears", "riib_2023")}
    ) == [("01708", ("reg_especial_reserva_inversiones_illes_balears", "riib_2023"), "riib_2024")]
