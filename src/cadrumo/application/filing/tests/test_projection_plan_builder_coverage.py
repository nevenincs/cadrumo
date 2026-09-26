"""Every modelo whose layout carries projection fields must have a plan builder.

A projection-kind export field resolves through a preflighted address:
``_projection_field_value`` (``application/filing/_record_field_renderer.py``) looks the
value up by ``(record id, occurrence, projection_ref)`` and raises when the record has no
render context. Those contexts come from a :class:`FilingProjectionPlan`, and
``_projection_plan_for_layout`` (``application/filing/export.py``) builds one only for the
modelos it dispatches on and returns an EMPTY plan for every other modelo.

With an empty plan every projection field of that modelo raises, so the return cannot
export at all. It fails CLOSED, which is the right direction -- it refuses rather than
emitting wrong bytes -- but without this gate nothing detects that the modelo does not file.

The gate reads both sides from the tree: the shipped layouts for the demand and the
dispatcher's own source for the supply, so a modelo that gains projection fields later is
covered without anyone remembering to add it here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REGISTRY_MODELOS = Path(__file__).resolve().parents[3] / "_data" / "registry" / "aeat" / "modelos"
#: Source of the projection-plan dispatcher inspected by this coverage gate.
_EXPORT_SOURCE = Path(__file__).resolve().parents[1] / "export.py"
_PROJECTION_KIND = re.compile(r"""kind\s*=\s*['"]projection['"]""")
#: A dispatch arm names its modelo either as an enum member or as a constructed code.
_DISPATCHED_MODELO = re.compile(r"""Modelo(?:\.M(\d{3})\b|\(\s*['"](\d{3})['"]\s*\))""")


def _modelos_with_projection_fields() -> dict[str, int]:
    """Return every modelo whose shipped export layout carries projection fields."""
    counts: dict[str, int] = {}
    for layout in _REGISTRY_MODELOS.glob("*/revisions/*/export/*.toml"):
        found = len(_PROJECTION_KIND.findall(layout.read_text(encoding="utf-8")))
        if found:
            modelo = layout.relative_to(_REGISTRY_MODELOS).parts[0]
            counts[modelo] = counts.get(modelo, 0) + found
    return counts


def _dispatched_modelos(source: str) -> set[str]:
    """Return the modelos the ``_projection_plan_for_layout`` body in ``source`` dispatches on."""
    body = source.partition("def _projection_plan_for_layout(")[2].partition("\ndef ")[0]
    return {enum_member or constructed for enum_member, constructed in _DISPATCHED_MODELO.findall(body)}


def _modelos_with_a_plan_builder() -> set[str]:
    """Return the modelos ``_projection_plan_for_layout`` actually dispatches on.

    Read from the dispatcher's own source rather than from a hand-kept list: a list here
    would be a second copy of the fact, and the two would drift.
    """
    return _dispatched_modelos(_EXPORT_SOURCE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "arm",
    [
        'if draft.modelo == Modelo("303").value:',
        "if draft.modelo == Modelo('303'):",
        "if draft.modelo == Modelo.M303:",
    ],
)
def test_the_dispatcher_scan_reads_every_spelling_of_a_dispatch_arm(arm: str) -> None:
    """A spelling the scan cannot read reports a served modelo as unserved, or hides a removed arm."""
    source = (
        f"def _projection_plan_for_layout(layout):\n    {arm}\n        return plan\n\ndef after():\n    Modelo('200')\n"
    )

    assert _dispatched_modelos(source) == {"303"}


def test_the_dispatcher_scan_reads_the_shipped_dispatcher() -> None:
    """Anti-tautology for the builder side: the shipped dispatcher must yield at least one modelo."""
    assert _modelos_with_a_plan_builder(), "no dispatch arm was read -- the scan is broken, not the dispatcher"


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
