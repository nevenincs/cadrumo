"""Shared derivation of the ``per_grupo_member`` cross-member fan-in keys.

A ``previous_filing`` binding whose selector declares
``grouping = "per_grupo_member"`` (the 353<-322 cross-member aggregation) is
satisfied by EVERY grupo member's filing for a
``(modelo, filing_year, period)`` key, not by a single filer's. Both the
binding-prefill gatherer
(:mod:`~application.calculations._binding_prefill`, which must enumerate the
members rather than load one observation by key) and the cross-period
clean-state gate
(:mod:`~application.calculations._cross_period_clean_state`, which must mark the
requirement ``requires_member_fan_in``) need the same key set, so it is derived
once here.

Sister shared module to :mod:`~._revision_carry_gate`.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core import BindingSourceKind
from ...domain.calculations.registry import RegistrySnapshot, previous_filing_observation_requirements

_PER_GRUPO_MEMBER: str = "per_grupo_member"


def per_grupo_member_requirement_keys(snapshot: RegistrySnapshot) -> set[tuple[str, int, str]]:
    """Return the ``(modelo, filing_year, period)`` keys whose binding declares ``per_grupo_member``.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision bindings are scanned
            for a ``previous_filing`` selector declaring ``grouping = "per_grupo_member"``.
    """
    grouped_binding_ids = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source == BindingSourceKind.PREVIOUS_FILING
        and _selector_grouping(binding.selector) == _PER_GRUPO_MEMBER
    }
    if not grouped_binding_ids:
        return set()
    keys: set[tuple[str, int, str]] = set()
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if any(binding_id in grouped_binding_ids for binding_id in requirement.binding_ids):
            keys.add((requirement.source_modelo, requirement.filing_year, requirement.periods[0]))
    return keys


def _selector_grouping(selector: object) -> object:
    if isinstance(selector, Mapping):
        return next((v for k, v in selector.items() if k == "grouping"), None)
    return getattr(selector, "grouping", None)
