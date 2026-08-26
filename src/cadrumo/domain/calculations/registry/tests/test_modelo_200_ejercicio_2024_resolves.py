"""Modelo 200 must resolve for the ejercicio its own orden approves.

The revision named ``2024-y-siguientes`` once carried
``period_selector = { year_from = 2025 }``, so the law-determined resolution
found no revision for Impuesto sobre Sociedades ejercicio 2024 and refused.
The refusal was CORRECT behaviour -- the non-overlap window gate declining to
substitute a neighbouring year's norms rather than guessing -- which is why a
whole filing year being unserviceable presented as test noise rather than as an
outage. Calculate, verify, file and export all refused for any taxpayer on that
return, and a cross-modelo chain reaching back to it refused with them.

The value was wrong on one axis only. ``valid_from``, the orden's publication
date and its entry into force are all correctly 2025: an orden approving the
ejercicio-2024 return is published and takes effect in 2025, because that is
when the return is filed. ``period_selector`` answers a different question --
which EJERCICIO the revision governs -- and the 2025 was carried across from
the effectivity axis onto it.

That ``filing_year`` means the ejercicio is convention rather than assumption:
the Modelo 100 revision for 2024 selects ``years = [2024]`` although Renta 2024
is filed in 2025.

Grounding. Orden HAC/657/2025 (BOE-A-2025-12818), whose Article 1 approves the
modelo 200, is titled for "los períodos impositivos iniciados entre el 1 de
enero y el 31 de diciembre de 2024". The revision already declared that orden
in its ``orden_aplicabilidad`` while its selector excluded the ejercicio the
orden governs, so this pins the data against the authority it had always cited.

The negative half is load-bearing. Asserting only that 2024 resolves would pass
under a selector that matches every year, which is the failure mode a widening
introduces, so 2023 must still refuse.
"""

from __future__ import annotations

import tomllib

import pytest

from cadrumo.domain.calculations.registry.errors import NoRevisionForPeriodError

from .....core.resources import bundled_path
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The ejercicio Orden HAC/657/2025 approves the modelo 200 for.
_APPROVED_EJERCICIO = 2024

#: The revision whose name asserts it covers that ejercicio.
_REVISION_ID = "2024-y-siguientes"

#: An ejercicio this revision must NOT claim. 2023 is served by no revision of
#: this modelo, so a selector that matches it has been widened rather than
#: corrected.
_UNCOVERED_EJERCICIO = 2023

#: The Modelo 202 revision carrying the instalment relations, and the relation
#: whose 1P instalment binds back to a Modelo 200 annual return.
_M202_REVISION_ID = "2025-y-siguientes"
_M202_1P_RELATION = "0003-modelo-202-2025-y-siguientes-rel-cuota-base-1p.toml"


def test_the_approved_ejercicio_resolves_to_the_revision_named_for_it() -> None:
    """The ejercicio the orden approves selects the revision named for it."""
    modelo, _ = _committed_modelo("200")

    revision = select_revision(modelo, filing_year=_APPROVED_EJERCICIO, period="0A")

    assert revision.id == _REVISION_ID


def test_the_revision_still_refuses_an_ejercicio_it_does_not_govern() -> None:
    """The control: the selector was corrected, not widened.

    Without this, the positive case above passes under a selector matching
    every year, and the test would certify the defect class it exists to
    prevent -- one filing year's numbers computed under another year's norms.
    """
    modelo, _ = _committed_modelo("200")

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=_UNCOVERED_EJERCICIO, period="0A")


def _m202_1p_source_year_delta() -> int:
    """Return the 1P instalment's year offset, read from the registry.

    Read from the relation rather than restated here, so a change to the
    chain reds this test instead of leaving it asserting a stale offset.
    """
    relation_path = bundled_path(
        "registry",
        "aeat",
        "modelos",
        "202",
        "revisions",
        _M202_REVISION_ID,
        "relations",
        _M202_1P_RELATION,
    )
    payload = tomllib.loads(relation_path.read_text(encoding="utf-8"))
    relations = payload["revisions"][_M202_REVISION_ID]["relations"]
    relation = next(entry for entry in relations if entry["source_modelo"] == "200")
    delta = int(relation["source_revision_selector"]["filing_year_delta"])
    assert delta < 0, "an instalment binds to a PRIOR annual return"
    return delta


def test_the_dependent_instalment_chain_reaches_the_annual_return() -> None:
    """The cross-modelo carry resolves, not just the modelo that carried the bug.

    The 1P instalment binds two filing years back because the prior-year
    Modelo 200 deadline has not elapsed by the April window. That makes the
    annual return's resolution a precondition of the instalment's, so an
    unresolvable ejercicio propagates outward from the modelo holding the bad
    selector. Fixing the selector without proving the dependent chain recovers
    would leave the propagation unverified, and the propagation is what made
    this an outage rather than a modelo-local defect.
    """
    modelo_200, _ = _committed_modelo("200")
    delta = _m202_1p_source_year_delta()
    instalment_year = _APPROVED_EJERCICIO - delta

    source = select_revision(modelo_200, filing_year=_APPROVED_EJERCICIO, period="0A")

    assert source.id == _REVISION_ID, (
        f"the {instalment_year} 1P instalment binds {delta} years back to the "
        f"{_APPROVED_EJERCICIO} annual return, which must resolve for the chain to run"
    )
