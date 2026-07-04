"""Registry foundations for the final UNMODELED tail: 592, 576, 121, 122.

592 (Impuesto especial sobre envases de plástico no reutilizables, Orden
HFP/1314/2022), 576 (IEDMT por matriculación, Orden EHA/3851/2007), 121
(comunicación de la cesión de la deducción familia numerosa/discapacidad) and 122
(regularización de la misma) — both Orden HFP/105/2017. The three ordenes were
NOT bundled: their corpus excerpts were authored from the BOE fetch during this
pass, so each legal entry carries honest "pending operator re-verification"
provenance. All four are grounded WINDOWLESS: 592's plazo cadence depends on the
taxpayer's IVA period, 576's is per-matriculación (delegated to Orden
EHA/1981/2005), and 121/122 remit to the annual IRPF campaign — none a fixed
calendar window, so no date is fabricated. Scheduling/applicability-grade:
declaration-header casillas only, no bundled diseño de registro.
"""

from __future__ import annotations

import pytest

from .....core import TaxDomain
from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, revision, approval, plazo, doc, tax_domain)
_MODELOS = [
    ("592", "2022-y-siguientes", "orden-hfp-1314-2022:art-1", "orden-hfp-1314-2022:art-2", "BOE-A-2022-23749", TaxDomain.PLASTICO),
    ("576", "2007-y-siguientes", "orden-eha-3851-2007:art-1", "orden-eha-3851-2007:art-1", "BOE-A-2007-22442", TaxDomain.IEDMT),
    ("121", "2017-y-siguientes", "orden-hfp-105-2017:art-1", "orden-hfp-105-2017:art-3", "BOE-A-2017-1334", TaxDomain.IRPF),
    ("122", "2017-y-siguientes", "orden-hfp-105-2017:art-5", "orden-hfp-105-2017:art-7", "BOE-A-2017-1334", TaxDomain.IRPF),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain", _MODELOS)
def test_validator_accepts_committed_definition(mid: str, rev: str, approval: str, plazo: str, doc: str, domain: TaxDomain) -> None:
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert modelo.tax_domain is domain
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain", _MODELOS)
def test_approval_and_plazo_resolve_as_legal_authority(mid: str, rev: str, approval: str, plazo: str, doc: str, domain: TaxDomain) -> None:
    _, catalogues = _committed_modelo(mid)
    for ref in {approval, plazo}:
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain", _MODELOS)
def test_cadence_dependent_plazo_carries_no_fabricated_windows(mid: str, rev: str, approval: str, plazo: str, doc: str, domain: TaxDomain) -> None:
    """Each plazo is cadence-dependent / delegated / campaign-remitted, so the
    honest state is zero calendar deadline_windows — no fixed date is invented."""
    modelo, _ = _committed_modelo(mid)
    assert modelo.revisions[rev].deadline_windows == ()
