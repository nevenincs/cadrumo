"""Every authored Modelo 100 edition folds the M130/M131 pagos-fraccionados relations into 0604.

Each edition carries the same legal grounding on 0604 and the same annual
settlement shape, so all of them must use one relation-prefill mechanism
rather than leaving the credit as a manual gap. The editions come from the
authored registry, so a new edition is covered without editing this module.
"""

from __future__ import annotations

from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.tests import modelo_100_historical_pagos_fraccionados_scenarios as scenarios

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _authored_years() -> tuple[int, ...]:
    """The ejercicio of every Modelo 100 edition the authored registry declares."""
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100"))
    return tuple(sorted(revision.valid_from.year for revision in modelo.revisions.values()))


@pytest.mark.parametrize("year", _authored_years())
def test_historical_pagos_fraccionados_relation_contract_and_fold(
    registry_authority: ValidatedRegistryAuthority,
    year: int,
) -> None:
    """Each authored edition declares the M130/M131 relation contract and folds it into 0604.

    Years below the supported filing floor keep their authored contract but
    refuse filing selection, so only in-envelope years run the fold.
    """
    support = registry_authority.catalogues.supported_filing_years
    assert support is not None
    if not support.admits_filing_year(year):
        scenarios.check_relation_contract(registry_authority.modelo("100").revisions[str(year)])
        with pytest.raises(FilingYearOutsideSupportEnvelopeError):
            registry_authority.snapshot("100", filing_year=year, period="0A")
        return

    scenarios.check_relation_contract_and_fold(
        registry_authority.snapshot("100", filing_year=year, period="0A"), year=year
    )
