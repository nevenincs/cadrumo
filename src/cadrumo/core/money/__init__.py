"""Canonical :class:`~decimal.Decimal` money primitives.

Single authoritative implementation of the half-up euro-cent
rounding convention used across every AEAT calculation surface
(LIRPF art. 23.1 rental net income, IRPF deductions, IVA prorata,
asset depreciation, inventory cost basis). Callers in
``cadrumo.domain.*`` import :func:`round_to_cents` and the ``CENT`` quantum
from here rather than reimplementing the quantize call.

The half-up rounding mode (:data:`~decimal.ROUND_HALF_UP`) matches
the AEAT publication convention: a residual cent of exactly 0.5
rounds away from zero. Python's default banker's rounding
(``ROUND_HALF_EVEN``) does NOT match AEAT and must never be used at
the euro-cent boundary for any operator-facing or filed value.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
