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
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that cross-checks legal/source catalogue references.
    :func:`~domain.calculations.registry._authority.bundled_authority`
        Authority facade used to inspect generated deadline windows.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership asserted once the foundations are registered.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Legacy unmodeled set these IVA foundations must leave.
    :mod:`~domain.calculations.registry.tests.test_modelo_592_576_121_122_registry`
        Sibling registry-foundation coverage for windowless/unmodeled-tail modelos.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._authority import bundled_authority
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, revision, approval_ref, plazo_ref, document_id, has_windows)
_MODELOS = [
    (
        "341",
        "2000-y-siguientes",
        "orden-min-2000-12-15-m341:art-1",
        "orden-min-2000-12-15-m341:art-2",
        "BOE-A-2000-22794",
        True,
    ),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,has_windows", _MODELOS)
def test_validator_accepts_committed_definition(
    mid: str, rev: str, approval: str, plazo: str, doc: str, has_windows: bool
) -> None:
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert rev in modelo.revisions
    assert modelo.tax_domain == "iva"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,has_windows", _MODELOS)
def test_approval_and_plazo_resolve_as_legal_authority(
    mid: str, rev: str, approval: str, plazo: str, doc: str, has_windows: bool
) -> None:
    _, catalogues = _committed_modelo(mid)
    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc


def test_modelo_341_reagp_quarterly_windows_20_days_with_january_30_day_q4() -> None:
    """Orden de 15/12/2000 art 2: 20 natural days after each quarter; 30 in enero for Q4."""
    authority = bundled_authority()
    windows = {str(w.period): w for _, _, w in authority.deadline_windows(2025, modelos=("341",))}
    assert windows["2025 1T"].opens_on == date(2025, 4, 1)
    assert windows["2025 1T"].closes_on == date(2025, 4, 20)
    assert windows["2025 2T"].closes_on == date(2025, 7, 20)
    assert windows["2025 3T"].closes_on == date(2025, 10, 20)
    # Fourth quarter is filed in the first 30 natural days of the following January.
    assert windows["2025 4T"].opens_on == date(2026, 1, 1)
    assert windows["2025 4T"].closes_on == date(2026, 1, 30)


def test_341_is_registry_backed() -> None:
    """380 relocated out of the registry (web-form-only, no AEAT machine format)."""
    from .....core.access_gate import CANONICAL_MODELO_FLEET

    assert "341" in CANONICAL_MODELO_FLEET
