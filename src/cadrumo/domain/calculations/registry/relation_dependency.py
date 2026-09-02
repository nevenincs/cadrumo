"""How one modelo's result depends on another's, and how that dependency settles.

Three vocabularies describing the same relation, previously spelled out at six
fields across four modules. One of those sites already carried a comment noting it
was typed to match its siblings rather than widened to a bare string, which is the
job a shared definition does and a copied union only approximates: a member added to
one spelling leaves the others validating the old set.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

from .schema_base import coerce_enum_member


class RelationKind(StrEnum):
    """What kind of upstream result a relation reaches for."""

    PREVIOUS_PERIOD = "previous_period"
    """The same modelo's own prior filing period."""

    ANNUAL_SUMMARY = "annual_summary"
    """The annual declaration that summarises the period filings."""

    CROSS_MODEL_OUTPUT = "cross_model_output"
    """A different modelo's computed output."""


class RelationDependencyRole(StrEnum):
    """The structural role the upstream result plays for the dependent modelo."""

    PERIODIC_TO_ANNUAL_SUMMARY = "periodic_to_annual_summary"
    """Period filings roll up into an annual summary."""

    INSTALMENT_TO_FINAL_SETTLEMENT = "instalment_to_final_settlement"
    """Instalments paid across the year settle against a final liability."""

    DIRECT_CALCULATION = "direct_calculation"
    """The upstream value enters the dependent calculation directly."""

    FACTUAL_EVIDENCE = "factual_evidence"
    """The upstream result evidences a fact without entering the arithmetic."""


class RelationDependencyTreatment(StrEnum):
    """How the dependency is settled once its role is known."""

    DIRECT_ANNUAL_SETTLEMENT = "direct_annual_settlement"
    """Settled against the annual declaration."""

    FACTUAL_EVIDENCE = "factual_evidence"
    """Carried as evidence rather than settled."""

    NON_DEPENDENCY = "non_dependency"
    """Declared explicitly as not a dependency, rather than left absent."""


RelationKindField = Annotated[RelationKind, BeforeValidator(coerce_enum_member(RelationKind))]
"""Registry ``relation_kind`` token hydrated into a member."""

RelationDependencyRoleField = Annotated[
    RelationDependencyRole, BeforeValidator(coerce_enum_member(RelationDependencyRole))
]
"""Registry ``dependency_role`` token hydrated into a member.

Registry schema models validate strictly, which refuses a bare TOML string for an
enum-typed field, so the token is coerced at the boundary.
"""

RelationDependencyTreatmentField = Annotated[
    RelationDependencyTreatment, BeforeValidator(coerce_enum_member(RelationDependencyTreatment))
]
"""Registry ``dependency_treatment`` token hydrated into a member."""


__all__ = [
    "RelationDependencyRole",
    "RelationDependencyRoleField",
    "RelationDependencyTreatment",
    "RelationDependencyTreatmentField",
    "RelationKind",
    "RelationKindField",
]
