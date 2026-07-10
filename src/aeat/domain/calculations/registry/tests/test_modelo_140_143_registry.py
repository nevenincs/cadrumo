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

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for committed registry definitions and legal catalogues.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the authored legal catalogue references.
    :class:`~core.TaxDomain`
        Closed tax-family enum whose IRPF member classifies both registrations.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership extended by these IRPF registrations.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Former recognized-unmodeled set reduced by this promotion.
    :mod:`~domain.calculations.registry.tests.test_modelo_592_576_121_122_registry`
        Later windowless final-tail promotion following the same pattern.
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
def test_committed_definition_legal_authority_and_windowless_plazo(
    mid: str, rev: str, approval: str, plazo: str, doc: str
) -> None:
    """Each on-demand solicitud validates without fabricated deadline windows."""
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert rev in modelo.revisions
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc

    assert modelo.revisions[rev].deadline_windows == ()
