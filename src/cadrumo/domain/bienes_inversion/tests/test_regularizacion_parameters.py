"""Teeth for the registry-resolved capital-goods parameter bundle.

The bundle exists so that the LIVA art-107/109 figures reach the calculation
from the validated authority rather than from a Python constant. Two properties
carry that guarantee and are pinned here: the bundle cannot be constructed
without a revision that declares the WHOLE family, and every value it carries
names the declaration it came from.

No test in this module asserts a legal value. Where a figure is needed it is
resolved from the registry and compared against the registry, which is the whole
point of moving it there.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from ...calculations.registry.schema_base import ThresholdComparison
from ..regularizacion_parameters import (
    BienesInversionParameterResolutionError,
    resolve_bienes_inversion_regularizacion_parameters,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    """The bundled validated authority.

    Declared here rather than reused: the registry package's conftest is not
    on this package's fixture path, and reaching across for it would couple
    two test packages through a file neither owns.
    """
    return bundled_authority()


#: Every modelo 303 revision, with a filing-period date inside its own window.
_REVISION_PROBES = (
    ("2022", date(2022, 6, 1)),
    ("2023", date(2023, 6, 1)),
    ("2024-hasta-08-y-2t", date(2024, 3, 1)),
    ("2024-desde-09-y-3t", date(2024, 10, 1)),
    ("2025", date(2025, 6, 1)),
    ("2026-y-siguientes", date(2026, 6, 1)),
)


@pytest.mark.parametrize(("revision_id", "probe"), _REVISION_PROBES)
def test_every_modelo_303_revision_resolves_a_whole_bundle(
    registry_authority: ValidatedRegistryAuthority,
    revision_id: str,
    probe: date,
) -> None:
    """The supported path: each revision supplies the complete figure set."""
    revision = registry_authority.modelo("303").revisions[revision_id]
    bundle = resolve_bienes_inversion_regularizacion_parameters(
        revision,
        modelo_id="303",
        filing_period_date=probe,
    )
    assert bundle.ventana_anos_mueble > 0
    assert bundle.ventana_anos_inmueble > bundle.ventana_anos_mueble
    assert bundle.divisor_inmueble > bundle.divisor_mueble
    assert bundle.umbral_puntos >= Decimal("0")


@pytest.mark.parametrize(("revision_id", "probe"), _REVISION_PROBES)
def test_the_bundle_names_the_declaration_it_came_from(
    registry_authority: ValidatedRegistryAuthority,
    revision_id: str,
    probe: date,
) -> None:
    """Provenance is what keeps a producer and its oracle independent.

    Handing the same bundle to both would otherwise make a WRONG bundle
    self-consistent, so the values must arrive knowing where they came from.
    """
    revision = registry_authority.modelo("303").revisions[revision_id]
    bundle = resolve_bienes_inversion_regularizacion_parameters(
        revision,
        modelo_id="303",
        filing_period_date=probe,
    )
    provenance = bundle.provenance
    assert provenance.modelo_id == "303"
    assert provenance.revision_id == revision_id
    assert provenance.resolved_on == probe
    declared_ids = {parameter.id for parameter in revision.parameters}
    assert set(provenance.parameter_ids) <= declared_ids
    assert len(provenance.parameter_ids) == len(set(provenance.parameter_ids))


def test_the_resolved_values_equal_what_the_registry_declares(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The bundle must not transform the declaration it reads.

    Compared against the registry rather than against a literal, so this test
    holds no legal value of its own and stays true if the law changes.
    """
    revision = registry_authority.modelo("303").revisions["2025"]
    bundle = resolve_bienes_inversion_regularizacion_parameters(
        revision,
        modelo_id="303",
        filing_period_date=date(2025, 6, 1),
    )
    declared = {parameter.id: parameter.values[0].value for parameter in revision.parameters}
    assert bundle.ventana_anos_mueble == declared["m303-bien-inversion-ventana-anos-mueble"]
    assert bundle.ventana_anos_inmueble == declared["m303-bien-inversion-ventana-anos-inmueble"]
    assert bundle.divisor_mueble == declared["m303-bien-inversion-divisor-mueble"]
    assert bundle.divisor_inmueble == declared["m303-bien-inversion-divisor-inmueble"]
    assert bundle.umbral_puntos == declared["m303-bien-inversion-regularizacion-umbral-puntos"]


def test_a_revision_declaring_no_parameters_is_refused(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """TEETH: modelo 390 declares the family not applicable, and must not resolve.

    Every M390 revision declares ``family_dispositions.parameters`` not
    applicable. Constructing a bundle from one would mean regularising a capital
    good on figures that revision never declared.
    """
    revision = registry_authority.modelo("390").revisions["2025"]
    with pytest.raises(BienesInversionParameterResolutionError) as excinfo:
        resolve_bienes_inversion_regularizacion_parameters(
            revision,
            modelo_id="390",
            filing_period_date=date(2025, 6, 1),
        )
    assert "declares no capital-goods regularisation figure" in str(excinfo.value)


def test_a_filing_date_outside_the_revision_window_is_refused(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """TEETH: a value is not borrowed across the window that grounds it."""
    revision = registry_authority.modelo("303").revisions["2025"]
    with pytest.raises(BienesInversionParameterResolutionError) as excinfo:
        resolve_bienes_inversion_regularizacion_parameters(
            revision,
            modelo_id="303",
            filing_period_date=date(2030, 1, 1),
        )
    assert "does not resolve for filing-period date" in str(excinfo.value)


def test_a_partial_family_is_refused(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """TEETH: half a family is worse than none, and must not build a bundle.

    Built by dropping one parameter from a real compiled revision, so the probe
    is a defect this resolver uniquely owns: the registry itself has no rule
    requiring the family to be complete, and a partial set loads cleanly.
    """
    revision = registry_authority.modelo("303").revisions["2025"]
    kept = tuple(p for p in revision.parameters if not p.id.endswith("divisor-inmueble"))
    partial = revision.model_copy(update={"parameters": kept})
    with pytest.raises(BienesInversionParameterResolutionError) as excinfo:
        resolve_bienes_inversion_regularizacion_parameters(
            partial,
            modelo_id="303",
            filing_period_date=date(2025, 6, 1),
        )
    assert "divisor-inmueble" in str(excinfo.value)


def test_the_de_minimis_gate_follows_the_declared_comparison(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The comparison direction is registry data, not a hardcoded operator.

    Probed relative to the resolved threshold rather than to a literal, so the
    boundary case is exercised without this file asserting what the law says.
    """
    revision = registry_authority.modelo("303").revisions["2025"]
    bundle = resolve_bienes_inversion_regularizacion_parameters(
        revision,
        modelo_id="303",
        filing_period_date=date(2025, 6, 1),
    )
    umbral = bundle.umbral_puntos
    assert not bundle.regularizacion_applies(umbral - Decimal("1"))
    assert bundle.regularizacion_applies(umbral + Decimal("1"))
    at_threshold = bundle.regularizacion_applies(umbral)
    assert at_threshold is (bundle.umbral_comparison is ThresholdComparison.INCLUSIVE)
