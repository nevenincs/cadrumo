"""Teeth for the one value an export field may write into AEAT-reserved bytes.

Modelo 360's ``Pág. 1`` row 109 is ``@1897+5`` "4. Reservado AEAT." with
contenido "constante '00000'": the administración owns the bytes AND prescribes
their value. The coverage gate refuses any non-filler field over reserved bytes,
except a ``literal`` writing exactly the constant the design declares at exactly
those coordinates. Every case loads a COPY of the shipped Modelo 360 tree through
the real loader and runs the real coverage gate against the bundled design.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ...conformance.stamp import bundled_registry_root
from ..loader import load_modelo_directory, load_shared_catalogues
from ..validate_export_layout_coverage import validate_export_layout_record_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_LAYOUT = Path("revisions") / "2010-y-siguientes" / "export_layouts" / "0001-declarations.toml"
_SHIPPED_CONSTANT = (
    'id = "modelo-360-page-01-constante-1897"\noffset = 1897\nlength = 5\nkind = "literal"\nliteral = "00000"\n'
)


def _modelo_360_with_constant(tmp_path: Path, *, literal: str) -> Path:
    """Copy the shipped Modelo 360 tree, re-declaring the @1897 constant's value."""
    modelo_dir = tmp_path / "360"
    shutil.copytree(bundled_registry_root() / "modelos" / "360", modelo_dir)
    layout = modelo_dir / _LAYOUT
    text = layout.read_text(encoding="utf-8")
    assert _SHIPPED_CONSTANT in text
    layout.write_text(
        text.replace(_SHIPPED_CONSTANT, _SHIPPED_CONSTANT.replace('literal = "00000"', f'literal = "{literal}"')),
        encoding="utf-8",
    )
    return modelo_dir


def _reserved_write_lines(modelo_dir: Path) -> tuple[str, ...]:
    """Return the reserved-bytes intrusions the coverage gate reports for the copied revision.

    Called on the gate itself rather than through the whole validator, whose
    earlier catalogue phases can refuse first and leave the revision checks
    unreached -- a silence that would prove nothing about this rule.
    """
    revision = load_modelo_directory(modelo_dir).revisions["2010-y-siguientes"]
    failures = validate_export_layout_record_coverage(
        prefix="modelo 360 revision 2010-y-siguientes",
        revision=revision,
        source_refs=load_shared_catalogues(bundled_registry_root()).sources,
    )
    return tuple(
        intrusion
        for failure in failures
        for intrusion in failure.split("; ")
        if "which the design reserves for" in intrusion
    )


def test_the_design_prescribed_constant_may_occupy_its_reserved_bytes(tmp_path: Path) -> None:
    """The shipped literal writes exactly what AEAT prescribes, so nothing intrudes."""
    assert _reserved_write_lines(_modelo_360_with_constant(tmp_path, literal="00000")) == ()


def test_any_other_value_in_the_reserved_bytes_is_refused(tmp_path: Path) -> None:
    """One digit off the prescribed constant is data written over AEAT's bytes."""
    lines = _reserved_write_lines(_modelo_360_with_constant(tmp_path, literal="00001"))

    assert len(lines) == 1
    assert "'modelo-360-page-01-constante-1897' (@1897+5) writes data into @1897..1901" in lines[0]
