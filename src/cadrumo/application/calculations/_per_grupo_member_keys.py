"""Shared derivation of the ``per_grupo_member`` cross-member fan-in keys.

A ``previous_filing`` binding whose selector declares
``grouping = "per_grupo_member"`` (the 353<-322 cross-member aggregation) is
satisfied by EVERY grupo member's filing for a
``(modelo, filing_year, period)`` key, not by a single filer's. Both the
binding-prefill gatherer
(:mod:`~application.calculations._binding_prefill`, which must enumerate the
members rather than load one observation by key) and the cross-period
clean-state gate
(:mod:`~application.calculations.cross_period_clean_state`, which must mark the
requirement ``requires_member_fan_in``) need the same key set, so it is derived
once here.

Sister shared module to :mod:`~._revision_carry_gate`.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.aggregation import BindingSourceKind
from ...core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.schema import ModeloRevision

_PER_GRUPO_MEMBER: str = "per_grupo_member"


def per_grupo_member_requirement_keys(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> set[tuple[str, int, str]]:
    """Return the ``(modelo, filing_year, period)`` keys whose binding declares ``per_grupo_member``.

    A structural fold over the revision's declared bindings and the law-determined
    filing coordinate; it never reads validated evidence, so it takes the compiled
    :class:`ModeloRevision` directly rather than a filing-grade
    :class:`~cadrumo.domain.calculations.registry.RegistrySnapshot`.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are scanned for a
            ``previous_filing`` selector declaring ``grouping = "per_grupo_member"``.
        filing_year: The filing coordinate's year.
        period: The filing coordinate's period token.
    """
    grouped_binding_ids = {
        binding.id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.PREVIOUS_FILING
        and _selector_grouping(binding.selector) == _PER_GRUPO_MEMBER
    }
    if not grouped_binding_ids:
        return set()
    keys: set[tuple[str, int, str]] = set()
    for requirement in previous_filing_observation_requirements(
        revision,
        filing_year=filing_year,
        period=period,
    ):
        if any(binding_id in grouped_binding_ids for binding_id in requirement.binding_ids):
            keys.add((requirement.source_modelo, requirement.filing_year, requirement.periods[0]))
    return keys


def _selector_grouping(selector: object) -> object:
    if isinstance(selector, Mapping):
        return STR_KEYED_MAPPING_ADAPTER.validate_python(selector).get("grouping")
    return getattr(selector, "grouping", None)
