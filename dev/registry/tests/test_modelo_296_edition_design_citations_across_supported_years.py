"""Modelo 296 editions cite only the record design that governs their own year.

The 2024 edition stores the members it shares with the 2023 edition against that
edition, so each shared member arrives citing aeat-dr-296-2023 unless the 2024
edition overrides the citation. The 2023 design's window closes with ejercicio
2023, so an inherited citation left in place would ground a 2024 or later member
in a design that does not govern it. Each supported year's edition is resolved
through the compiled authority and every record design its members cite is
compared with the one its own export layout is generated from.
"""

from __future__ import annotations

from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.keyed_families import CANONICAL_FAMILY_SPECS
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "296"
_PERIOD = "0A"
_RECORD_DESIGN = "record_design"


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


def _edition(year: int) -> ModeloRevision:
    """The year's edition, snapshotted at the grade it declares rather than at filing grade."""
    authority = compiled_bundled_authority()
    selected = select_revision(
        authority.modelo(_MODELO),
        filing_year=year,
        period=_PERIOD,
        support=authority.catalogues.supported_filing_years,
    )
    return authority.snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=selected.authority_grade).revision


def _is_record_design(source_ref: str) -> bool:
    return compiled_bundled_authority().catalogues.sources[source_ref].kind == _RECORD_DESIGN


def _layout_design(revision: ModeloRevision) -> str:
    designs = {ref for layout in revision.export_layouts for ref in layout.source_refs if _is_record_design(ref)}
    assert len(designs) == 1, f"edition {revision.id} generates its export from record designs {sorted(designs)}"
    (design,) = designs
    return design


def _foreign_design_citations(revision: ModeloRevision, design: str | None) -> list[tuple[str, str, str]]:
    """Return (family, member, design) for every member citing a record design other than ``design``."""
    findings: list[tuple[str, str, str]] = []
    for spec in CANONICAL_FAMILY_SPECS:
        value = getattr(revision, spec.section, None)
        members = (value,) if spec.singleton and value is not None else value if isinstance(value, tuple) else ()
        for member in members:
            identity = str(getattr(member, "id", None) or getattr(member, spec.identity or "id", None))
            findings.extend(
                (spec.section, identity, ref)
                for ref in getattr(member, "source_refs", ())
                if ref != design and _is_record_design(ref)
            )
    return findings


def _export_bearing_years() -> tuple[int, ...]:
    return tuple(year for year in _supported_years() if _edition(year).export_layouts)


@pytest.mark.parametrize("year", _supported_years())
def test_every_member_cites_the_record_design_of_its_own_year(year: int) -> None:
    """A year with no generated layout has no design of its own, so it may cite none.

    Such an edition claims applicability only: the export generator renders AEAT
    record designs, and a year whose design is unpublished or never existed can
    only inherit another year's, which is exactly the citation this test refuses.
    """
    revision = _edition(year)
    if not revision.export_layouts:
        assert revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY, f"{year}: {revision.id}"
        assert _foreign_design_citations(revision, None) == [], f"{year}: edition {revision.id} cites a design"
        return
    design = _layout_design(revision)
    assert _foreign_design_citations(revision, design) == [], f"{year}: edition {revision.id} cites another design"


def test_an_inherited_citation_of_the_earlier_design_is_reported() -> None:
    revision = _edition(max(_export_bearing_years()))
    earlier = _edition(min(_export_bearing_years()))
    design = _layout_design(revision)
    earlier_design = _layout_design(earlier)
    assert earlier_design != design, "the supported years resolve to a single 296 design; nothing to plant"
    endpoint = revision.projection_endpoints[0]
    planted = revision.model_copy(
        update={
            "projection_endpoints": (
                endpoint.model_copy(update={"source_refs": (earlier_design,)}),
                *revision.projection_endpoints[1:],
            ),
        },
    )
    assert _foreign_design_citations(planted, design) == [("projection_endpoints", str(endpoint.id), earlier_design)]
