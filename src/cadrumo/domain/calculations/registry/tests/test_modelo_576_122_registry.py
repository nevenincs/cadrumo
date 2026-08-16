"""Registry foundations for the final UNMODELED tail: 576, 121, 122.

576 (IEDMT por matriculacion, Orden EHA/3851/2007), 121 (comunicacion de la
cesion de la deduccion familia numerosa/discapacidad) and 122 (regularizacion de
la misma) - both Orden HFP/105/2017. The two ordenes were NOT bundled: their
corpus excerpts were authored from the BOE fetch during this pass, so each legal
entry carries honest "pending operator re-verification" provenance. All three are
grounded WINDOWLESS: 576's plazo is per-matriculacion (delegated to Orden
EHA/1981/2005) and 121/122 remit to the annual IRPF campaign - none a fixed
calendar window, so no date is fabricated. Scheduling/applicability-grade:
declaration-header casillas only, no bundled diseno de registro.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for the committed registry definitions and legal catalogues.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the authored legal/source references.
    :class:`~core.TaxDomain`
        Closed tax-family enum extended for the plastico and IEDMT registrations.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership reached after this final-tail promotion.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Former residual obligation set that this tail reduces to empty.
    :mod:`~domain.calculations.registry.tests.test_modelo_iva_batch4_registry`
        Sibling registry-foundation coverage for windowless IVA promotions.
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
    (
        "576",
        "2007-y-siguientes",
        "orden-eha-3851-2007:art-1",
        "orden-eha-3851-2007:art-1",
        "BOE-A-2007-22442",
        TaxDomain.IEDMT,
    ),
    (
        "121",
        "2017-y-siguientes",
        "orden-hfp-105-2017:art-1",
        "orden-hfp-105-2017:art-3",
        "BOE-A-2017-1334",
        TaxDomain.IRPF,
    ),
    (
        "122",
        "2017-y-siguientes",
        "orden-hfp-105-2017:art-5",
        "orden-hfp-105-2017:art-7",
        "BOE-A-2017-1334",
        TaxDomain.IRPF,
    ),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,domain", _MODELOS)
def test_committed_definition_legal_authority_and_windowless_plazo(
    mid: str, rev: str, approval: str, plazo: str, doc: str, domain: TaxDomain
) -> None:
    """Each cadence-dependent tail modelo validates without fabricated deadline windows."""
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert modelo.tax_domain is domain
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    for ref in {approval, plazo}:
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc

    assert modelo.revisions[rev].deadline_windows == ()
