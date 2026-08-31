"""Tests for the six Batch-2 declaración-informativa registry foundations.

Modelos 165, 233, 156 (annual, January plazo) and 038, 185, 186 (monthly plazo)
were promoted from :data:`~core.UNMODELED_OBLIGATIONS` to registry-loadable definitions.
Each is approved by a bundled orden whose approval (art 1) and plazo (art 4 or 6)
articles are cross-checked against the bundled BOE corpus at build. These
Several remain scheduling/applicability-grade (declaration-header casillas
only). Modelo 165's filing geometry is explicitly bounded to the two complete
official design eras; Modelo 038's official design is bundled but remains
geometry-recovered, so no numbered form casilla is fabricated from it.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for committed registry definitions and legal catalogues.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Registry validator that checks the authored legal/source references.
    :func:`~domain.calculations.registry.authority.bundled_authority`
        Authority facade used to resolve annual and monthly deadline windows.
    :data:`~core.access_gate.CANONICAL_MODELO_FLEET`
        Canonical fleet membership these six informativas extend.
    :mod:`~domain.calculations.registry.tests.test_modelo_informativas_batch3_registry`
        Follow-on informativa promotion with annual and windowless deadline shapes.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources._boundary import bundled_path
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, revision, approval_ref, plazo_ref, document_id, period_kind)
# Modelos 179, 186, 233, 234 and 238 are deliberately ABSENT from this list.
# AEAT publishes no record design for any of them -- confirmed against every
# current and ejercicios-anteriores Diseno de Registro index page -- and the
# registry's membership criterion is that a modelo earns a definition when AEAT
# publishes a machine-readable submission format for it. They were relocated to
# the recognized out-of-scope obligations, 179 to the suppressed-modelo map
# after DAC7 absorbed it into 238. Listing them here asserted a registry
# membership the tree deliberately does not grant.
_MODELOS = [
    (
        "165",
        "2023-2025",
        "orden-hap-2455-2013:art-1",
        "orden-hap-2455-2013:art-4",
        "BOE-A-2013-13798",
        "annual",
    ),
    (
        "156",
        "2003-y-siguientes",
        "orden-hac-3580-2003:art-1",
        "orden-hac-3580-2003:art-4",
        "BOE-A-2003-23509",
        "annual",
    ),
    ("038", "2025-y-siguientes", "orden-hac-66-2002:art-1", "orden-hac-66-2002:art-6", "BOE-A-2002-1041", "monthly"),
    (
        "185",
        "2025-y-siguientes",
        "orden-hac-1197-2025:art-1",
        "orden-hac-1197-2025:art-4",
        "BOE-A-2025-21726",
        "monthly",
    ),
]


@pytest.mark.parametrize("mid,rev,approval,plazo,doc,kind", _MODELOS)
def test_committed_definition_legal_refs_and_deadlines_are_grounded(
    mid: str, rev: str, approval: str, plazo: str, doc: str, kind: str
) -> None:
    modelo, catalogues = _committed_modelo(mid)
    assert modelo.id == mid
    assert rev in modelo.revisions
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    # Approval (art 1) and plazo (art 4/6) resolve as bundled legal authority.
    # Both required_text sets are cross-checked against the bundled orden corpus
    # at build; here we pin their evidence tier and document id.
    for ref in (approval, plazo):
        entry = catalogues.legal[ref]
        assert entry.evidence_tier == "legal_authority"
        assert entry.document_id == doc

    revision = modelo.revisions[rev]
    assert revision.deadline_windows, f"{mid} must declare deadline windows"
    for window in revision.deadline_windows:
        assert window.period_kind == kind
        assert plazo in window.legal_refs


def test_annual_january_windows_resolve() -> None:
    """165/233/156 file in January of the year following the filing year."""
    authority = bundled_authority()
    for mid in ("165", "156"):
        windows = {w.id: w for _, _, w in authority.deadline_windows(2024, modelos=(mid,))}
        wid = f"modelo-{mid}-2024-0a"
        assert wid in windows
        assert windows[wid].opens_on == date(2025, 1, 1)
        assert windows[wid].closes_on == date(2025, 1, 31)


def test_monthly_windows_resolve_following_month() -> None:
    """038/186 close on the last natural day, 185 on the 10th, of the next month."""
    authority = bundled_authority()
    # January 2025 reference month -> filed in February 2025.
    for mid, close in (("038", date(2025, 2, 28)), ("185", date(2025, 2, 10))):
        windows = {str(w.period): w for _, _, w in authority.deadline_windows(2025, modelos=(mid,))}
        assert len(windows) == 12
        jan = windows["2025 01"]
        assert jan.opens_on == date(2025, 2, 1)
        assert jan.closes_on == close


def test_all_six_are_registry_backed() -> None:
    from .....core.access_gate._authorization import CANONICAL_MODELO_FLEET

    for mid in ("165", "156", "038", "185"):
        assert mid in CANONICAL_MODELO_FLEET
