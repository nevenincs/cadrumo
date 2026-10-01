"""Modelo 182 donor-row surface across every filing year the modelo authors.

The five donor-row bindings and the informative construct that gathers them are
authored once, on the earliest edition, and inherited forward. Their grounding
does not change between editions: the bindings cite the approving orden, and
every record field they carry is printed at the same position by the
ejercicio 2021-2023, 2024 and 2025 designs, which this module reads directly.
What the later edition alone claims -- its verification expectation, workbook
pin, design and deadline window -- stays keyed on it.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as CompiledAuthority
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistrySnapshot

from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "182"
_CONSTRUCT = "modelo-182-informative"
_DONOR_BINDINGS = frozenset(
    {
        "modelo-182-donor-row-nif",
        "modelo-182-donor-row-name",
        "modelo-182-donor-row-amount",
        "modelo-182-donor-row-deduction-percentage",
        "modelo-182-donor-row-recurrencia",
    }
)
#: The tipo 2 fields the donor-row bindings carry, as each design prints them.
_DONOR_RECORD_FIELDS = (
    "18-26 Alfanumérico N.I.F. DEL DECLARADO.",
    "36-75 Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL",
    "79-83 Numérico % DE DEDUCCIÓN",
    "84-96 Numérico IMPORTE O VALORACIÓN DEL DONATIVO,",
    "132 Numérico RECURRENCIA DONATIVOS",
)


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


def _authored_years(modelo: ModeloDefinition) -> tuple[int, ...]:
    """The supported filing years some authored Modelo 182 edition covers."""
    return tuple(
        year
        for year in _supported_years()
        if any(
            revision.valid_from.year <= year and (revision.valid_to is None or revision.valid_to.year >= year)
            for revision in modelo.revisions.values()
        )
    )


@pytest.fixture(scope="module")
def modelo_182(registry_authority: CompiledAuthority) -> ModeloDefinition:
    """Modelo 182 as the development compiler reads it from the authored source."""
    return registry_authority.modelo(_MODELO)


@pytest.fixture(scope="module")
def edition(registry_authority: CompiledAuthority) -> Callable[[int], RegistrySnapshot]:
    def select(filing_year: int) -> RegistrySnapshot:
        return registry_authority.snapshot(
            _MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        )

    return select


def _record_design_text(source_ref: str) -> str:
    source = load_shared_catalogues(bundled_path("registry", "aeat")).sources[source_ref]
    assert source.corpus_path is not None, source_ref
    return bundled_path(*f"{source.corpus_path}.extracted.md".split("/")).read_text(encoding="utf-8")


def test_every_edition_design_prints_the_donor_fields_at_the_same_positions(modelo_182: ModeloDefinition) -> None:
    designs = sorted(
        {
            str(ref)
            for revision in modelo_182.revisions.values()
            for ref in revision.source_refs
            if str(ref).startswith("aeat-dr-182-")
        }
    )
    assert len(designs) == len(modelo_182.revisions), designs
    for design in designs:
        lines = set(_record_design_text(design).splitlines())
        missing = [field for field in _DONOR_RECORD_FIELDS if field not in lines]
        assert not missing, (design, missing)


def test_donor_surface_is_stated_once_on_the_earliest_edition(modelo_182: ModeloDefinition) -> None:
    earliest = min(modelo_182.revisions.values(), key=lambda revision: revision.valid_from)
    assert {str(binding.id) for binding in earliest.bindings} == _DONOR_BINDINGS
    assert {str(construct.id) for construct in earliest.constructs} == {_CONSTRUCT}


def test_the_modelo_authors_more_than_one_supported_year(modelo_182: ModeloDefinition) -> None:
    assert len(_authored_years(modelo_182)) > 1


def test_donor_bindings_and_construct_hydrate_in_every_authored_year(
    modelo_182: ModeloDefinition, edition: Callable[[int], RegistrySnapshot]
) -> None:
    for filing_year in _authored_years(modelo_182):
        revision = edition(filing_year).revision
        bindings = {str(binding.id): binding for binding in revision.bindings}
        construct = next(item for item in revision.constructs if item.id == _CONSTRUCT)

        assert set(bindings) == _DONOR_BINDINGS, filing_year
        for binding in bindings.values():
            assert tuple(map(str, binding.source_refs)) == ("enrolled-modelo-182-procedure",), filing_year
        assert set(map(str, construct.bindings)) == _DONOR_BINDINGS, filing_year
        assert set(map(str, construct.casilla_ids)) == {"decl.ejercicio", "decl.tipo-declaracion"}, filing_year
        assert {str(window) for window in construct.deadline_windows} <= {
            str(window.id) for window in revision.deadline_windows
        }, filing_year
        design = next(str(ref) for ref in revision.source_refs if str(ref).startswith("aeat-dr-182-"))
        assert design in set(map(str, construct.source_refs)), filing_year


def test_only_the_later_edition_claims_verification_and_a_workbook_pin(
    modelo_182: ModeloDefinition, edition: Callable[[int], RegistrySnapshot]
) -> None:
    latest = max(modelo_182.revisions.values(), key=lambda revision: revision.valid_from)
    years = _authored_years(modelo_182)
    assert any(edition(year).revision.id != latest.id for year in years)
    assert any(edition(year).revision.id == latest.id for year in years)
    for filing_year in years:
        revision = edition(filing_year).revision
        construct = next(item for item in revision.constructs if item.id == _CONSTRUCT)
        if revision.id != latest.id:
            assert not revision.verification_expectations, filing_year
            assert not construct.verification_expectations, filing_year
            assert not construct.workbook_parity_refs, filing_year
            continue
        assert tuple(map(str, construct.verification_expectations)) == (
            "modelo-182-informative-summary-verification",
        ), filing_year
        assert tuple(map(str, construct.workbook_parity_refs)) == ("modelo-182-orden-static-layout",), filing_year
        assert tuple(map(str, construct.deadline_windows)) == ("modelo-182-2025-0a",), filing_year
