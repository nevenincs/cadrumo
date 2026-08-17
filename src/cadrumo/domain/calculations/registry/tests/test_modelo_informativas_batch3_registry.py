"""Tests for the five Batch-3 declaración-informativa registry foundations.

179, 181, 270 are annual (January plazo, verbatim) and carry calendar deadline
windows. 234 (DAC6) and 238 (DAC7) carry NO calendar deadline windows: 234's plazo
is event-driven (30 días per RGAT art 46.3) and 238's annual window is delegated to
RGAT art 54.6 — neither RGAT article is bundled, so no fixed date is fabricated.
All five are scheduling/applicability-grade: declaration-header casillas only, no
bundled diseño de registro, no fabricated form casilla. Each orden's approval (art
1) and plazo article are cross-checked against the bundled BOE corpus at build.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for the committed registry definitions and legal catalogues.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the authored legal/source references.
    :func:`~domain.calculations.registry._authority.bundled_authority`
        Authority facade used to resolve the annual windows and windowless cases.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership these five informativas extend.
    :data:`~core.UNMODELED_OBLIGATIONS`
        Former recognized-unmodeled set reduced by this Batch-3 promotion.
    :mod:`~domain.calculations.registry.tests.test_modelo_informativas_batch2_registry`
        Sibling M182-template informativa promotion with annual/monthly windows.
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
    ("179", "2021-y-siguientes", "orden-hac-612-2021:art-1", "orden-hac-612-2021:art-4", "BOE-A-2021-10163", True),
    ("181", "2009-2022", "orden-eha-3514-2009:art-1", "orden-eha-3514-2009:art-6", "BOE-A-2009-21165", True),
    ("270", "2013-y-siguientes", "orden-hap-2368-2013:art-1", "orden-hap-2368-2013:art-3", "BOE-A-2013-13228", True),
    ("234", "2021-y-siguientes", "orden-hac-342-2021:art-1", "orden-hac-342-2021:art-4", "BOE-A-2021-5780", False),
    ("238", "2024-y-siguientes", "orden-hac-72-2024:art-1", "orden-hac-72-2024:art-9", "BOE-A-2024-2092", False),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,has_windows", _MODELOS)
def test_committed_definition_legal_authority_and_deadline_shape(
    mid: str, rev: str, approval: str, plazo: str, doc: str, has_windows: bool
) -> None:
    """Each Batch-3 informativa validates and carries only grounded deadline windows."""
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert rev in modelo.revisions
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc

    revision = modelo.revisions[rev]
    if has_windows:
        assert revision.deadline_windows
        for window in revision.deadline_windows:
            assert window.period_kind == "annual"
            assert plazo in window.legal_refs
    else:
        assert not revision.deadline_windows


def test_annual_january_windows_resolve() -> None:
    authority = bundled_authority()
    for mid in ("179", "181", "270"):
        windows = {w.id: w for _, _, w in authority.deadline_windows(2024, modelos=(mid,))}
        wid = f"modelo-{mid}-2024-0a"
        assert wid in windows
        assert windows[wid].opens_on == date(2025, 1, 1)
        assert windows[wid].closes_on == date(2025, 1, 31)


def test_event_driven_and_delegated_modelos_have_no_calendar_windows() -> None:
    authority = bundled_authority()
    for mid in ("234", "238"):
        assert [w.id for _, _, w in authority.deadline_windows(2025, modelos=(mid,))] == []


def test_all_five_are_registry_backed() -> None:
    from .....core.access_gate import CANONICAL_MODELO_FLEET

    for mid in ("179", "181", "270", "234", "238"):
        assert mid in CANONICAL_MODELO_FLEET
