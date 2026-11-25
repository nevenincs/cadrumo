"""Tests for the two Batch-4 IVA autoliquidación registry foundations.

341 (solicitud de reintegro de compensaciones REAGP) is quarterly: the first 20
natural days after each quarter, with the fourth-quarter solicitud extended to the
first 30 natural days of January (grounded verbatim in the Orden de 15/12/2000 art
2). 380 (operaciones asimiladas a las importaciones del IVA) delegates its plazo to
the ordinary IVA declaration plazo (Orden EHA/1308/2005 art 4), whose specific dates
depend on the taxpayer's IVA regime and are not stated in the orden, so it carries
NO calendar deadline windows — a fixed date is not fabricated. Both are
declaration-header grade: no Modelo 341/380 diseño de registro is bundled, so no
money-closure form casilla is fabricated. Each orden's approval (art 1) and plazo
article are cross-checked against the bundled BOE corpus at build.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for committed modelo registry definitions and catalogues.
    :class:`~dev.registry.compiler.validator.RegistryValidator`
        Registry validator that cross-checks legal/source catalogue references.
    :func:`~domain.calculations.registry.authority.compiled_bundled_authority`
        Authority facade used to inspect generated deadline windows.
    :data:`~domain.calculations.registry.modelo_obligation_scope.UNMODELED_OBLIGATIONS`
        Legacy unmodeled set these IVA foundations must leave.
    :mod:`~domain.calculations.registry.tests.test_modelo_592_576_121_122_registry`
        Sibling registry-foundation coverage for windowless/unmodeled-tail modelos.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, filing_year_envelope
from dev.registry.compiler.authority import compiled_bundled_authority

from ..conformance.registry_schema_support import committed_modelo
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

#: The single 2000-y-siguientes revision was narrowed into two eras. Both cite
#: the same Orden of 15 December 2000 as their approval and plazo authority, so
#: each is listed rather than one standing in for the pair: a row per committed
#: definition is what makes the validator run against every one of them.
_REVISIONS_341 = tuple(str(revision.id) for revision in authored_revisions("341"))
_APPROVAL_341 = "orden-min-2000-12-15-m341:art-1"
_PLAZO_341 = "orden-min-2000-12-15-m341:art-2"
_DOCUMENT_341 = "BOE-A-2000-22794"


@pytest.mark.parametrize("rev", _REVISIONS_341)
def test_validator_accepts_committed_definition(rev: str) -> None:
    modelo, catalogues = committed_modelo("341")
    assert modelo.id == "341"
    assert rev in modelo.revisions
    assert modelo.tax_domain == "iva"
    committed_registry_validator(catalogues).validate_modelo(modelo)


def test_approval_and_plazo_resolve_as_legal_authority() -> None:
    _, catalogues = committed_modelo("341")
    for ref in (_APPROVAL_341, _PLAZO_341):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == _DOCUMENT_341


def test_modelo_341_reagp_quarterly_windows_20_days_with_january_30_day_q4() -> None:
    """Orden de 15/12/2000 art 2: 20 natural days after each quarter; 30 in enero for Q4."""
    authority = compiled_bundled_authority()
    year = filing_year_envelope().horizon
    windows = {w.period: w for _, _, w in authority.deadline_windows(year, modelos=("341",))}
    first, second, third, fourth = (Period.from_year_and_code(year, code) for code in ("1T", "2T", "3T", "4T"))
    assert windows[first].opens_on == date(year, 4, 1)
    assert windows[first].closes_on == date(year, 4, 20)
    assert windows[second].closes_on == date(year, 7, 20)
    assert windows[third].closes_on == date(year, 10, 20)
    # Fourth quarter is filed in the first 30 natural days of the following January.
    assert windows[fourth].opens_on == date(year + 1, 1, 1)
    assert windows[fourth].closes_on == date(year + 1, 1, 30)


def test_341_is_registry_backed() -> None:
    """380 relocated out of the registry (web-form-only, no AEAT machine format)."""
    assert compiled_bundled_authority().modelo("341").id == "341"
