"""The per-casilla parity verdict published across the calculation surfaces.

The type lives in its own public module because it is a CONTRACT rather than a
step of the comparison: the CLI renders it, the parity harness returns it, and
the export preview reads it, while the comparison algorithm that populates it
stays private to this package. Naming the module for the symbol follows
:mod:`cadrumo.core.casilla_id`, which publishes :class:`CasillaId` the same way.

See Also:
    :mod:`~application.storage.calc_sheets.parity_harness`
        The three-way harness that acquires the values and produces these rows.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class CasillaParity(BaseModel):
    """Per-casilla parity verdict across three calculation surfaces.

    Each ``*_vs_*`` flag is ``None`` exactly when one of its two sides carried
    no value, so "not compared" stays distinguishable from "compared and
    disagreed" — collapsing them to ``False`` would report a missing oracle as
    a divergence.

    ``Decimal`` is imported at module scope rather than under ``TYPE_CHECKING``
    because pydantic resolves this model's field annotations at RUNTIME, and
    ``from __future__ import annotations`` has already turned them into strings.
    A type-checking-only import leaves the class undefined and fails on first
    instantiation — while the module still imports, still collects, and still
    satisfies the linter that recommends the narrower form. Only the fields
    below need this; the type-checking block keeps everything used solely in
    function signatures.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    display_number: str
    label: str
    local: Decimal | None = None
    sheets: Decimal | None = None
    aeat: Decimal | None = None
    sheets_vs_local: bool | None = None
    local_vs_aeat: bool | None = None
    sheets_vs_aeat: bool | None = None
