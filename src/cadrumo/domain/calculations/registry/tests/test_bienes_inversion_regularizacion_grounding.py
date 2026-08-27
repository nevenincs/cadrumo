"""Grounding gate for the M303 regularización por bienes de inversión casilla.

LIVA grounds the regularización de deducciones por bienes de inversión in arts.
107 (obligación y período de 4/9 años), 108 (concepto de bien de inversión),
109 (procedimiento de regularización comparando el porcentaje de deducción del
año de adquisición con el del año de regularización) and 110 (entregas durante
el período) — NOT in the general deduction framework arts. 92/94/95. The official
form casilla 43 ("Regularizacion bienes de inversion - Cuota") is the operator-
facing, exported carrier of that concept; it must ground in its binding
provisions, consistent with the dedicated `iva.regularizacion-inversiones`
procedure casilla. This gate pins that casilla 43 cites arts. 107-110 and never
lets the generic deduction framework stand in for the binding provisions, across
both live M303 revisions.
"""

from __future__ import annotations

import pytest

from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BIENES_INVERSION_CHAPTER = frozenset(
    {
        "ley-37-1992:art-107",
        "ley-37-1992:art-108",
        "ley-37-1992:art-109",
        "ley-37-1992:art-110",
    }
)
_GENERIC_DEDUCTION_FRAMEWORK = frozenset(
    {
        "ley-37-1992:art-92",
        "ley-37-1992:art-94",
        "ley-37-1992:art-95",
    }
)


def _m303_revision_scopes() -> list[tuple[str, int, str]]:
    """Yield ``(revision_id, filing_year, period)`` for every committed M303 revision.

    The years were pinned as ``[2020, 2024]`` with a comment reading "2020
    resolves to the 2022 revision" -- true before the revision-span split gave
    2022 an exact-year selector, and false afterwards, so the case raised
    ``NoRevisionForPeriodError`` instead of checking any grounding.

    Deriving the scopes covers all six revisions rather than two and cannot be
    invalidated by the next split. The scope is still resolved through
    ``select_revision`` from ``(modelo, filing_year, period)`` rather than
    indexed by id, and the resolution is asserted to land on the revision it was
    derived from. The period is read per revision because
    ``2024-desde-09-y-3t`` does not carry 1T.
    """
    modelo, _ = _committed_modelo("303")
    scopes = []
    for revision_id, revision in sorted(modelo.revisions.items()):
        selector = revision.period_selector
        year = selector.years[0] if selector.years else selector.year_from
        assert year is not None
        scopes.append((revision_id, int(year), selector.periods[0]))
    return scopes


_M303_SCOPES = _m303_revision_scopes()


def _m303_casilla(scope: tuple[str, int, str], cid: str):
    revision_id, filing_year, period = scope
    modelo, _ = _committed_modelo("303")
    rev = select_revision(modelo, filing_year=filing_year, period=period)
    assert str(rev.id) == revision_id, (
        f"law-determined resolution for {filing_year} {period} landed on {rev.id!r}, "
        f"not the revision the scope was derived from ({revision_id!r})"
    )
    return {c.id: c for c in rev.casillas}.get(cid)


@pytest.mark.parametrize("scope", _M303_SCOPES, ids=[scope[0] for scope in _M303_SCOPES])
def test_official_casilla_43_grounds_in_bienes_inversion_chapter(scope: tuple[str, int, str]) -> None:
    """The official form casilla 43 must cite the binding LIVA arts. 107-110."""
    casilla = _m303_casilla(scope, "43")
    assert casilla is not None, f"M303 {scope[0]} must declare casilla 43"
    refs = set(casilla.legal_refs)
    missing = _BIENES_INVERSION_CHAPTER - refs
    assert not missing, (
        f"M303 {scope[0]}: casilla 43 (regularización bienes de inversión) must cite "
        f"its binding provisions arts. 107-110; missing {sorted(missing)} in {sorted(refs)}"
    )


@pytest.mark.parametrize("scope", _M303_SCOPES, ids=[scope[0] for scope in _M303_SCOPES])
def test_official_casilla_43_does_not_stand_on_generic_framework_alone(scope: tuple[str, int, str]) -> None:
    """The generic deduction framework (arts. 92/94/95) must not be the only
    LIVA grounding on casilla 43 — the binding regularización provisions govern."""
    casilla = _m303_casilla(scope, "43")
    assert casilla is not None, f"M303 {scope[0]} must declare casilla 43"
    refs = set(casilla.legal_refs)
    assert _BIENES_INVERSION_CHAPTER & refs, (
        f"M303 {scope[0]}: casilla 43 cites only the generic deduction framework "
        f"{sorted(_GENERIC_DEDUCTION_FRAMEWORK & refs)} without the binding "
        f"arts. 107-110: {sorted(refs)}"
    )
