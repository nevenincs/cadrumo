"""Registry foundations for the new-tax autoliquidaciones 490, 604 and 763.

490 (Impuesto sobre Determinados Servicios Digitales, Orden HAC/590/2021,
trimestral), 604 (Impuesto sobre las Transacciones Financieras, Orden
HAC/510/2021, mensual) and 763 (Impuesto sobre actividades de juego, Orden
EHA/1881/2011, trimestral) are new taxes classified under the TaxDomain members
IDSD / ITF / JUEGO. Each orden's approval (art 1) and plazo article are
cross-checked verbatim against the bundled BOE corpus, and the deadline windows
reproduce the verbatim plazo (490/763: month following each quarter; 604: days
10-20 of the month following each month). Scheduling/applicability-grade:
declaration-header casillas only, no bundled diseño de registro, so the base/cuota
money-closure casillas are not fabricated.

See Also:
    :class:`~core.TaxDomain`
        Closed tax-family enum that carries the IDSD, ITF and juego members.
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for committed registry definitions and legal catalogues.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the plazo and legal catalogue references.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership these new-tax registrations extend.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Former recognized-unmodeled set reduced by these promotions.
    :mod:`~domain.calculations.registry.tests.test_modelo_592_576_121_122_registry`
        Companion registry coverage for the remaining new-tax modelos.
"""

from __future__ import annotations

import pytest

from .....core import TaxDomain
from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, revision, approval, plazo, doc, tax_domain, window_count)
_MODELOS = [
    (
        "490",
        "orden-hac-590-2021:art-1",
        "orden-hac-590-2021:art-3",
        "BOE-A-2021-9721",
        TaxDomain.IDSD,
        8,
    ),
    (
        "604",
        "orden-hac-510-2021:art-1",
        "orden-hac-510-2021:art-3",
        "BOE-A-2021-8878",
        TaxDomain.ITF,
        12,
    ),
    (
        "763",
        "orden-eha-1881-2011:art-1",
        "orden-eha-1881-2011:art-4",
        "BOE-A-2011-11704",
        TaxDomain.JUEGO,
        8,
    ),
]


@pytest.mark.parametrize("mid,approval,plazo,doc,domain,windows", _MODELOS)
def test_committed_definition_legal_authority_and_deadline_windows(
    mid: str, approval: str, plazo: str, doc: str, domain: TaxDomain, windows: int
) -> None:
    """Each new-tax autoliquidacion validates and cites its plazo on every window.

    Counted across the modelo's revisions rather than inside one named revision.
    This test used to pin a revision id, and both pinned ids stopped existing
    when modelo 490 and modelo 604 had their spans split -- the windows did not
    move or change, but the lookup raised ``KeyError`` and the modelo went
    unchecked. The orden fixes how many filing windows the tax has; which
    revision declares them is a registry-shape decision that a split may
    legitimately change, so the count is asserted where it is stable.
    """
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert modelo.tax_domain is domain
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc

    declared = [window for revision in modelo.revisions.values() for window in revision.deadline_windows]
    assert len(declared) == windows
    assert all(plazo in window.legal_refs for window in declared)
