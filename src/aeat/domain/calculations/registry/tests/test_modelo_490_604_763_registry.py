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
    ("490", "2021-y-siguientes", "orden-hac-590-2021:art-1", "orden-hac-590-2021:art-3", "BOE-A-2021-9721", TaxDomain.IDSD, 8),
    ("604", "2021-y-siguientes", "orden-hac-510-2021:art-1", "orden-hac-510-2021:art-3", "BOE-A-2021-8878", TaxDomain.ITF, 12),
    ("763", "2011-y-siguientes", "orden-eha-1881-2011:art-1", "orden-eha-1881-2011:art-4", "BOE-A-2011-11704", TaxDomain.JUEGO, 8),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain,windows", _MODELOS)
def test_validator_accepts_committed_definition(mid, rev, approval, plazo, doc, domain, windows) -> None:
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert modelo.tax_domain is domain
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain,windows", _MODELOS)
def test_approval_and_plazo_resolve_as_legal_authority(mid, rev, approval, plazo, doc, domain, windows) -> None:
    _, catalogues = _committed_modelo(mid)
    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain,windows", _MODELOS)
def test_deadline_windows_cite_the_plazo(mid, rev, approval, plazo, doc, domain, windows) -> None:
    """Each window count matches the verbatim plazo cadence and every window cites
    the plazo article — no window is authored without its grounding."""
    modelo, _ = _committed_modelo(mid)
    dw = modelo.revisions[rev].deadline_windows
    assert len(dw) == windows
    assert all(plazo in w.legal_refs for w in dw)
