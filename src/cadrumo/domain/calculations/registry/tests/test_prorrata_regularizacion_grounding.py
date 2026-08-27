"""Grounding gate for the M303 regularización por prorrata definitiva casilla.

LIVA grounds the annual prorrata-general regularización in arts. 104
(porcentaje de prorrata general, aplicado provisionalmente durante el año) and
105 (procedimiento de la prorrata general, regularización de la deducción
provisional frente a la definitiva en el último período de liquidación) — NOT
in the generic deduction framework arts. 92/94/95 alone. The official form
casilla 44 ("Regularizacion prorrata por porcentaje definitivo - Cuota") is the
operator-facing, exported carrier of that concept; it must ground in its
binding provisions, consistent with the dedicated
:func:`~domain.iva.compute_regularizacion_prorrata_anual` procedure. This
gate pins that casilla 44 cites arts. 104-105 and never lets the generic
deduction framework stand in for the binding provisions, across both live
M303 revisions.

See Also:
    :class:`~domain.calculations.registry._bindings._ProrrataRegularizacionSelector`
        Registry selector contract for the prorrata regularización source.
    :data:`~core.BindingSourceKind.PRORRATA_REGULARIZACION`
        Source-kind token governing the casilla-44 binding.
    :class:`~application.calculations._prorrata_regularizacion.ProrrataRegularizacionSourceResolver`
        Live resolver that materialises the grounded binding after calculation.
        Deferral rationale and the accepted cross-period regularización model.
"""

from __future__ import annotations

import pytest

from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PRORRATA_REGULARIZACION_CHAPTER = frozenset(
    {
        "ley-37-1992:art-104",
        "ley-37-1992:art-105",
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


# 2020 resolves to the 2022 revision; 2024 to its early-period epoch.
@pytest.mark.parametrize("scope", _M303_SCOPES, ids=[scope[0] for scope in _M303_SCOPES])
def test_official_casilla_44_grounds_in_prorrata_regularizacion_chapter(scope: tuple[str, int, str]) -> None:
    """The official form casilla 44 must cite the binding LIVA arts. 104-105."""
    casilla = _m303_casilla(scope, "44")
    assert casilla is not None, f"M303 {scope[0]} must declare casilla 44"
    refs = set(casilla.legal_refs)
    missing = _PRORRATA_REGULARIZACION_CHAPTER - refs
    assert not missing, (
        f"M303 {scope[0]}: casilla 44 (regularización prorrata por porcentaje "
        f"definitivo) must cite its binding provisions arts. 104-105; "
        f"missing {sorted(missing)} in {sorted(refs)}"
    )


@pytest.mark.parametrize("scope", _M303_SCOPES, ids=[scope[0] for scope in _M303_SCOPES])
def test_official_casilla_44_does_not_stand_on_generic_framework_alone(scope: tuple[str, int, str]) -> None:
    """The generic deduction framework (arts. 92/94/95) must not be the only
    LIVA grounding on casilla 44 — the binding regularización provisions govern."""
    casilla = _m303_casilla(scope, "44")
    assert casilla is not None, f"M303 {scope[0]} must declare casilla 44"
    refs = set(casilla.legal_refs)
    assert _PRORRATA_REGULARIZACION_CHAPTER & refs, (
        f"M303 {scope[0]}: casilla 44 cites only the generic deduction framework "
        f"{sorted(_GENERIC_DEDUCTION_FRAMEWORK & refs)} without the binding "
        f"arts. 104-105: {sorted(refs)}"
    )
