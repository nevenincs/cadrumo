"""Registry foundation for Modelo 848 (comunicación del INCN a efectos del IAE).

848 is the standalone communication of the importe neto de la cifra de negocios
that IAE taxpayers file; the IAE autoliquidación (modelo 840) is a distinct,
out-of-scope obligation and is NOT a dependency here. Approved by Orden
HAC/85/2003 art 1, with a verbatim-grounded January-to-14-February plazo in art 3
(BOE-A-2003-1686). Scheduling/applicability-grade: declaration-header casillas
only, no bundled diseño de registro, so no numbered form casilla is fabricated.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for committed registry definitions and legal catalogues.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the authored legal/source references.
    :class:`~core.TaxDomain`
        Closed tax-family enum whose IAE member classifies the registration.
    :data:`~core.OUT_OF_SCOPE_OBLIGATIONS`
        Scope ledger that keeps Modelo 840 distinct from this communication.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership extended by the Modelo 848 foundation.
    :mod:`~domain.calculations.registry.tests.test_modelo_140_143_registry`
        Later promotion slice using the same legal-authority validation pattern.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = "2003-y-siguientes"
_APPROVAL = "orden-hac-85-2003:art-1"
_PLAZO = "orden-hac-85-2003:art-3"
_DOC = "BOE-A-2003-1686"


def test_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _committed_modelo("848")
    assert modelo.id == "848"
    assert _REVISION in modelo.revisions
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_approval_and_plazo_resolve_as_legal_authority() -> None:
    _, catalogues = _committed_modelo("848")
    for ref in (_APPROVAL, _PLAZO):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == _DOC


def test_deadline_windows_are_january_to_14_february() -> None:
    """848's plazo (orden-hac-85-2003 art 3) runs 1 Jan – 14 Feb of the effects
    year; the authored windows must reproduce that span verbatim, not a fabricated
    January-31 shape copied from a sibling informativa."""
    modelo, _ = _committed_modelo("848")
    revision = modelo.revisions[_REVISION]
    windows = {w.filing_year: w for w in revision.deadline_windows}
    assert set(windows) == {2024, 2025, 2026}
    for year, window in windows.items():
        assert window.opens_on == date(year, 1, 1)
        assert window.closes_on == date(year, 2, 14)
        assert _PLAZO in window.legal_refs
