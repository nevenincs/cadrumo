"""Shared scaffolding for the ledger-income chain oracle modules.

The rated and exempt oracles drive the same chain against different invoices,
so the invoice rows and the expected figures differ and stay in their own
modules. What must NOT differ is which registry revision the last link resolves
against: two oracles reading different revisions would each be internally
consistent while describing different law, and the disagreement would be
invisible because neither asserts anything about the other.

So the revision resolution lives here once, and the filing period both oracles
pin is stated once beside it. Everything else is deliberately left duplicated —
scaffolding that differs by design should look different, not be forced through
a shared helper with a flag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....core import Period
from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

if TYPE_CHECKING:
    from ..schema import ModeloRevision

#: The filing year both oracles pin. Shared because the revision resolved below
#: is law-determined by it: a year that drifted between the two modules would
#: silently point them at different redacciones of the same modelo.
ORACLE_FILING_YEAR = 2026

#: The period both oracles pin, derived from the year rather than restated.
ORACLE_PERIOD = Period.from_year_and_code(ORACLE_FILING_YEAR, "1T")


def modelo_130_revision() -> ModeloRevision:
    """Return the committed Modelo 130 revision the chain's last link resolves against.

    Built through the real snapshot construction rather than a hand-assembled
    revision, so the bindings the oracles resolve are the ones a production
    calculate would load. A hand-built revision could agree with the tests and
    disagree with the filing, which is the failure an oracle module exists to
    rule out rather than reproduce.
    """
    modelo, catalogues = _committed_modelo("130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=ORACLE_FILING_YEAR,
        period=ORACLE_PERIOD.registry_token,
    ).revision
