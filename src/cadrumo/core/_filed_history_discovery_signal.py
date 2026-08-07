"""Closed axis for what nominated a ``(modelo, ejercicio)`` pair for a history walk.

One enum, and the asymmetry between its two members is the whole reason it
exists rather than being an implementation detail of the walk grid. A pair
reached by a walk is only as informative as the signal that put it there, so
the signal travels with the pair instead of being discarded once the union is
built: a zero-row result means something different for each member, and code
that cannot tell them apart cannot report either one honestly.

See :class:`FiledHistoryDiscoverySignal`.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "FiledHistoryDiscoverySignal",
]


class FiledHistoryDiscoverySignal(StrEnum):
    """Which signal nominated one ``(modelo, ejercicio)`` pair for a history walk.

    The two members are NOT interchangeable, and treating them as one axis of
    equal weight is the failure this enum exists to prevent. Only
    :attr:`PROFILE_APPLICABILITY` can carry a completeness claim; a report
    measured against :attr:`AEAT_REGISTER_OPTIONS` alone would assert coverage
    over a denominator that may have nothing to do with the taxpayer.

    Attributes:
        PROFILE_APPLICABILITY: Derived from the taxpayer's OWN declared profile
            facts, through the same applicability machinery the overview
            calendar reconciles obligations with. Taxpayer-specific by
            construction: it is the filer's own declared data, it needs no
            authenticated session, and there is no scoping question to settle.
            A pair carrying this signal that yields no declaración is a genuine
            anomaly — the declared facts expected a filing that was not found —
            and earns a warning.
        AEAT_REGISTER_OPTIONS: Read from the declaraciones register's own
            modelo/ejercicio combobox option lists. AEAT-sourced, but whether
            the lists are genuinely scoped to the authenticated NIF or are a
            static universal catalogue the form renders regardless of taxpayer
            is UNCONFIRMED, and settling it needs a live authenticated probe
            nobody has authorised. So this signal is unioned in ADDITIVELY: it
            can only ever widen the walked grid, never narrow it and never
            substitute for the taxpayer-specific one. A pair carrying ONLY this
            signal that yields no declaración is a plain negative and MUST NOT
            be reported as an anomaly, because the signal's informativeness for
            this taxpayer is not established. Report it as "AEAT's offered
            option set", never as "this NIF's confirmed filing history".
    """

    PROFILE_APPLICABILITY = "profile_applicability"
    AEAT_REGISTER_OPTIONS = "aeat_register_options"
