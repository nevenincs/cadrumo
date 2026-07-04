"""Registry foundation for Modelos 140 and 143 (IRPF solicitudes de abono anticipado).

140 (deducción por maternidad, Orden HAC/177/2020) and 143 (deducciones familia
numerosa / discapacidad, Orden HAP/2486/2014) are on-demand advance-payment
requests: art 5 of each sets the plazo as "a partir del momento en que el
contribuyente opte por la modalidad de abono anticipado" — NOT a fixed calendar
window. Both are therefore grounded WINDOWLESS: the approval (art 1) and plazo
(art 5) articles are cross-checked verbatim against the bundled BOE corpus, but no
calendar deadline_windows and no deadline application link are authored, so no
fixed date is fabricated. Scheduling/applicability-grade: declaration-header
casillas only, no bundled diseño de registro, no fabricated form casilla.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, revision, approval_ref, plazo_ref, document_id)
_MODELOS = [
    ("140", "2020-y-siguientes", "orden-hac-177-2020:art-1", "orden-hac-177-2020:art-5", "BOE-A-2020-2901"),
    ("143", "2014-y-siguientes", "orden-hap-2486-2014:art-1", "orden-hap-2486-2014:art-5", "BOE-A-2014-13675"),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc", _MODELOS)
def test_validator_accepts_committed_definition(mid: str, rev: str, approval: str, plazo: str, doc: str) -> None:
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert rev in modelo.revisions
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("mid,rev,approval,plazo,doc", _MODELOS)
def test_approval_and_plazo_resolve_as_legal_authority(mid: str, rev: str, approval: str, plazo: str, doc: str) -> None:
    _, catalogues = _committed_modelo(mid)
    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc


@pytest.mark.parametrize("mid,rev,approval,plazo,doc", _MODELOS)
def test_on_demand_solicitud_carries_no_fabricated_windows(mid: str, rev: str, approval: str, plazo: str, doc: str) -> None:
    """The plazo is on-demand ("opte por la modalidad de abono anticipado"), so the
    honest state is zero calendar deadline_windows — no fixed date is invented."""
    modelo, _ = _committed_modelo(mid)
    assert modelo.revisions[rev].deadline_windows == ()
