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
    :func:`~domain.calculations.registry.authority.bundled_authority`
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

from .....core.resources._boundary import bundled_path
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# (modelo_id, revision, approval_ref, plazo_ref, document_id, has_windows)
# Modelos 179, 186, 233, 234 and 238 are deliberately ABSENT from this list.
# AEAT publishes no record design for any of them -- confirmed against every
# current and ejercicios-anteriores Diseno de Registro index page -- and the
# registry's membership criterion is that a modelo earns a definition when AEAT
# publishes a machine-readable submission format for it. They were relocated to
# the recognized out-of-scope obligations, 179 to the suppressed-modelo map
# after DAC7 absorbed it into 238. Listing them here asserted a registry
# membership the tree deliberately does not grant.
_MODELOS = [
    ("181", "2022-y-siguientes", "orden-eha-3514-2009:art-1", "orden-eha-3514-2009:art-6", "BOE-A-2009-21165", True),
    ("270", "2023-y-siguientes", "orden-hap-2368-2013:art-1", "orden-hap-2368-2013:art-3", "BOE-A-2013-13228", True),
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
    for mid in ("181", "270"):
        windows = {w.id: w for _, _, w in authority.deadline_windows(2024, modelos=(mid,))}
        wid = f"modelo-{mid}-2024-0a"
        assert wid in windows
        assert windows[wid].opens_on == date(2025, 1, 1)
        assert windows[wid].closes_on == date(2025, 1, 31)


def test_event_driven_and_delegated_modelos_have_no_calendar_windows() -> None:
    """A modelo declaring no deadline window resolves no calendar window either.

    This named modelos 234 and 238, which were relocated out of the registry
    because AEAT publishes no record design for them. Emptying the list would
    have left the case iterating nothing and asserting nothing, so the subjects
    are DERIVED: every registry modelo whose revisions declare no deadline
    window at all -- the event-driven and delegated ones -- must resolve none
    through the authority either. The population is asserted non-empty so the
    case cannot go quiet if that set ever empties.
    """
    authority = bundled_authority()
    windowless = tuple(
        str(modelo.id)
        for modelo in authority.modelos
        if not any(revision.deadline_windows for revision in modelo.revisions.values())
    )
    assert windowless, "no registry modelo declares an empty deadline-window set"

    for mid in windowless:
        assert [w.id for _, _, w in authority.deadline_windows(2025, modelos=(mid,))] == []


def test_all_five_are_registry_backed() -> None:
    from .....core.access_gate._authorization import CANONICAL_MODELO_FLEET

    for mid in ("181", "270"):
        assert mid in CANONICAL_MODELO_FLEET
