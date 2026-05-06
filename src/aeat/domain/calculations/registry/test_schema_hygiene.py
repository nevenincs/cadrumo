"""Cross-modelo schema hygiene tests.

These guards catch generator regressions that bulk-emit casillas from AEAT
data dictionaries or workbook layouts. They run against every committed
registry/aeat/modelos/*.toml so a future deepening pass cannot introduce
duplicate casilla declarations, drop section structure, or leave XML-root
container names like ``DatosEconomicos`` leaking through into the section
taxonomy.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_SECTION_PART_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$")

_FORBIDDEN_XML_ROOT_TOKENS = frozenset(
    {
        "datoseconomicos",
        "datos_economicos",
        "rootnode",
        "root_node",
    }
)


def _all_modelos():
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return modelos


def test_no_duplicate_casilla_ids_within_a_revision() -> None:
    """Within a single modelo revision, every casilla id must be unique."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            counts = Counter(c.id for c in revision.casillas)
            duplicates = {casilla_id: count for casilla_id, count in counts.items() if count > 1}
            for casilla_id, count in duplicates.items():
                offences.append(
                    f"modelo {modelo.id} revision {revision_id} declares casilla id {casilla_id!r} {count} times"
                )
    assert not offences, "duplicate casilla ids per revision:\n  " + "\n  ".join(offences)


def test_no_duplicate_casilla_numbers_within_a_revision() -> None:
    """Within a single modelo revision, every casilla number must be unique."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            counts = Counter(c.number for c in revision.casillas)
            duplicates = {number: count for number, count in counts.items() if count > 1}
            for number, count in duplicates.items():
                offences.append(
                    f"modelo {modelo.id} revision {revision_id} declares casilla number {number!r} {count} times"
                )
    assert not offences, "duplicate casilla numbers per revision:\n  " + "\n  ".join(offences)


def test_section_paths_are_non_empty() -> None:
    """Every casilla must declare at least one section segment so downstream filters never see ``[]``."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                if not casilla.section:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} has empty section path"
                    )
    assert not offences, "empty section paths:\n  " + "\n  ".join(offences)


def test_section_parts_are_snake_case() -> None:
    """Section parts must be lowercase, digits, and underscores only -- no CamelCase XPath leakage."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                for part in casilla.section:
                    if not _SECTION_PART_PATTERN.match(part):
                        offences.append(
                            f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} "
                            f"has non-snake_case section part {part!r}"
                        )
    assert not offences, "non-snake_case section parts:\n  " + "\n  ".join(offences)


def test_section_paths_do_not_leak_xml_root_containers() -> None:
    """Section[0] must not be an AEAT XML container name (DatosEconomicos, etc.)."""

    offences: list[str] = []
    for modelo in _all_modelos():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                if casilla.section and casilla.section[0] in _FORBIDDEN_XML_ROOT_TOKENS:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} casilla {casilla.id!r} "
                        f"has XML root container {casilla.section[0]!r} as section[0]"
                    )
    assert not offences, "XML root containers leaked into section paths:\n  " + "\n  ".join(offences)
