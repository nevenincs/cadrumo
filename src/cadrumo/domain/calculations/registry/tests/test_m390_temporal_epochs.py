"""Modelo 390 source-grounded annual revision boundaries."""

from __future__ import annotations

import re
from datetime import date

import pytest

from .....core import RegistryAuthorityGrade
from .._errors import NoRevisionForPeriodError
from .._temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("filing_year", [2021, 2022, 2023, 2024, 2025])
def test_m390_selects_the_exact_annual_epoch_and_own_record_design(filing_year: int) -> None:
    modelo, catalogues = _committed_modelo("390")

    revision = select_revision(modelo, filing_year=filing_year, period="0A")

    own_source_ref = f"aeat-dr-390-{filing_year}"
    assert revision.id == str(filing_year)
    assert revision.valid_from == date(filing_year, 1, 1)
    assert revision.valid_to == date(filing_year, 12, 31)
    assert revision.period_selector.years == (filing_year,)
    assert revision.source_refs.count(own_source_ref) == 1
    serialized_revision = revision.model_dump_json()
    assert own_source_ref in serialized_revision
    for other_year in {2021, 2022, 2023, 2024, 2025} - {filing_year}:
        assert f"aeat-dr-390-{other_year}" not in serialized_revision
    assert catalogues.sources[own_source_ref].record_design_epoch == str(filing_year)
    assert catalogues.sources[own_source_ref].applies_from == date(filing_year, 1, 1)
    assert catalogues.sources[own_source_ref].applies_to == date(filing_year, 12, 31)


@pytest.mark.parametrize("unsupported_year", [*range(2010, 2021), 2026])
def test_m390_refuses_years_without_enrolled_record_design_authority(unsupported_year: int) -> None:
    modelo, _catalogues = _committed_modelo("390")

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=unsupported_year, period="0A")


def test_m390_rdl_4_2024_is_confined_to_the_2024_epoch() -> None:
    modelo, _catalogues = _committed_modelo("390")
    provision = "real-decreto-ley-4-2024:art-1"

    assert provision in modelo.revisions["2024"].model_dump_json()
    for year in ("2021", "2022", "2023", "2025"):
        assert provision not in modelo.revisions[year].model_dump_json()


def test_m390_has_no_open_compatibility_revision() -> None:
    modelo, _catalogues = _committed_modelo("390")

    assert set(modelo.revisions) == {"2021", "2022", "2023", "2024", "2025"}


def test_m390_2021_parser_epoch_does_not_advertise_filing_capability() -> None:
    modelo, _catalogues = _committed_modelo("390")
    revision = modelo.revisions["2021"]

    surfaces = {link.surface for link in revision.application_links}
    consumers = {link.consumer for link in revision.application_links}

    assert revision.authority_grade == RegistryAuthorityGrade.APPLICABILITY
    assert surfaces == {"extractor"}
    assert "cadrumo.application.filing" not in consumers
    assert not revision.export_layouts


def test_m390_2021_informational_compensation_roles_do_not_claim_filing_constraints() -> None:
    modelo, _catalogues = _committed_modelo("390")
    parser = modelo.revisions["2021"]
    filing = modelo.revisions["2022"]
    identities = (
        ("iva.anual.compensacion-ultimo-periodo-97", "iva_anual_compensacion_ultimo_periodo"),
        ("iva.anual.compensacion-generada-ejercicio-no-97", "iva_anual_compensacion_generada_ejercicio"),
    )

    for casilla_id, filing_role in identities:
        observed = next(c for c in parser.casillas if c.id == casilla_id)
        bound = next(c for c in filing.casillas if c.id == casilla_id)
        assert observed.input_kind == "informational"
        assert observed.constraints is None
        assert observed.semantic_role == f"{filing_role}_2021_informational"
        assert bound.input_kind == "bound"
        assert bound.constraints is not None and bound.constraints.sign == "non_negative"
        assert bound.semantic_role == filing_role
        assert "aeat-dr-390-2021" in observed.source_refs
        assert "aeat-dr-390-2022" in bound.source_refs


#: Binding ids embed the revision year (`modelo-390-2024.page_5.223-239....`),
#: so the same logical binding necessarily has a different id in every epoch.
#: Comparing them raw reports all 175 page-scoped bindings as "dropped" every
#: year, which says nothing about identity stability.
_M390_BINDING_YEAR_TOKEN = re.compile(r"^modelo-390-\d{4}\.")

#: Bindings AEAT RETIRED from the form, so their absence in a later epoch is the
#: registry following the diseno rather than losing an identity. Both are the
#: Lorca reduccion slots (RD-ley 6/2011 earthquake relief): the 2024 diseno drops
#: them and the 2025 diseno marks their positions -- page 5, 223..239 and
#: 543..559 -- "RESERVADO PARA LA A.E.A.T. (Dejar en blanco)".
_M390_RETIRED_BINDINGS: frozenset[str] = frozenset(
    {
        "modelo-390.page_5.223-239.operaciones-reg-simplificado-actividad-1-lorca",
        "modelo-390.page_5.543-559.operaciones-reg-simplificado-actividad-2-lorca",
    },
)


def test_m390_preserves_canonical_casilla_and_calculation_identities_across_epochs() -> None:
    """A later epoch may ADD boxes, but never renames or silently drops one.

    This asserted set EQUALITY across the four epochs, which the tree contradicts
    for a grounded reason: the 2024 diseno added "Pag. 2 bis" and its boxes, so
    the revisions carry 325, 329, 393 and 393 casillas. Equality would forbid
    AEAT's own additions; what must hold is that nothing already canonical
    disappears or is renamed under a filer's feet.
    """
    modelo, _catalogues = _committed_modelo("390")
    baseline = modelo.revisions["2022"]

    def _stripped(bindings: object) -> set[str]:
        return {_M390_BINDING_YEAR_TOKEN.sub("modelo-390.", str(item.id)) for item in bindings}

    for year in ("2023", "2024", "2025"):
        revision = modelo.revisions[year]
        assert {c.id for c in baseline.casillas} <= {c.id for c in revision.casillas}
        assert {f.id for f in baseline.formulas} <= {f.id for f in revision.formulas}
        assert {r.id for r in baseline.relations} <= {r.id for r in revision.relations}
        # Year token normalised, and the two retired Lorca slots excused by name.
        assert _stripped(baseline.bindings) - _M390_RETIRED_BINDINGS <= _stripped(revision.bindings)
