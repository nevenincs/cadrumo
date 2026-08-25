"""Every modelo whose layout carries projection fields must have a plan builder.

A projection-kind export field resolves through a preflighted address:
``_projection_field_value`` (``application/filing/_record_field_renderer.py``) looks the
value up by ``(record id, occurrence, projection_ref)`` and raises when the record has no
render context. Those contexts come from a :class:`FilingProjectionPlan`, and
``_projection_plan_for_layout`` (``application/filing/_export.py``) builds one for M303 and
returns an EMPTY plan for every other modelo.

Modelo 200's generated layout carries 578 projection-kind fields. With an empty plan every
one of them raises, so the Impuesto sobre Sociedades return cannot export at all. It fails
CLOSED, which is the right direction -- it refuses rather than emitting wrong bytes -- but
nothing in the tree detected that the corporate tax return does not file.

This gate is that detector. It reads the shipped layouts, not a list, so a modelo that
gains projection fields later is covered without anyone remembering to add it here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REGISTRY_MODELOS = Path(__file__).resolve().parents[3] / "_data" / "registry" / "aeat" / "modelos"
_EXPORT_SOURCE = Path(__file__).resolve().parents[1] / "_export.py"
_PROJECTION_KIND = re.compile(r"""kind\s*=\s*['"]projection['"]""")


def _modelos_with_projection_fields() -> dict[str, int]:
    """Return every modelo whose shipped export layout carries projection fields."""
    counts: dict[str, int] = {}
    for layout in _REGISTRY_MODELOS.glob("*/revisions/*/export/*.toml"):
        found = len(_PROJECTION_KIND.findall(layout.read_text(encoding="utf-8")))
        if found:
            modelo = layout.relative_to(_REGISTRY_MODELOS).parts[0]
            counts[modelo] = counts.get(modelo, 0) + found
    return counts


def _modelos_with_a_plan_builder() -> set[str]:
    """Return the modelos ``_projection_plan_for_layout`` actually dispatches on.

    Read from the dispatcher's own source rather than from a hand-kept list: a list here
    would be a second copy of the fact, and the two would drift.
    """
    source = _EXPORT_SOURCE.read_text(encoding="utf-8")
    body = source.partition("def _projection_plan_for_layout(")[2].partition("\ndef ")[0]
    return set(re.findall(r"Modelo\.M(\d{3})\b", body))


def test_the_scan_finds_projection_fields_at_all() -> None:
    """Anti-tautology: an empty scan would make the assertion below pass for free.

    The export TOML uses SINGLE quotes; a double-quote pattern returns nothing and every
    modelo then looks covered. That exact mistake produced three wrong measurements while
    the producer-resolution defect was being investigated by hand.
    """
    found = _modelos_with_projection_fields()
    assert found, "no projection-kind field was read at all -- the scan is broken, not the tree"
    assert sum(found.values()) > 100, f"only {sum(found.values())} projection fields found; the parse is suspect"


def test_every_modelo_with_projection_fields_has_a_plan_builder() -> None:
    """Fail with the modelos whose projection fields nothing can resolve."""
    cited = _modelos_with_projection_fields()
    built = _modelos_with_a_plan_builder()
    uncovered = {modelo: count for modelo, count in sorted(cited.items()) if modelo not in built}

    assert not uncovered, (
        f"{len(uncovered)} modelo(s) ship an export layout with projection-kind fields that no "
        "projection plan builder serves. _projection_plan_for_layout returns an empty plan for "
        "them, so _projection_field_value raises 'requires a snapshot-owned render context' and "
        "the modelo CANNOT EXPORT AT ALL. It fails closed rather than emitting wrong bytes, but "
        "it does not file and until now nothing said so.\n"
        + "\n".join(
            f"  modelo {modelo}: {count} projection field(s), no plan builder" for modelo, count in uncovered.items()
        )
    )
