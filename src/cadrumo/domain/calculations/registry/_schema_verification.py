"""What a filed return is reconciled against, and the fold across a snapshot.

Verification asks one question of a filed modelo: do the numbers AEAT received
agree with the numbers this application computes? A revision answers it by
declaring verification expectations, and this module owns both halves of that
answer — the per-expectation declaration and the snapshot-wide fold the
application verification surface actually consumes.

The three casilla axes are deliberately distinct and are the reason the two
models belong together. ``computed_casilla_ids`` are the coverage-gated
reconciliation targets: fail to reconcile enough of them and the filing is
NEEDS_REVIEW. ``reconcile_when_present_casilla_ids`` are reconciled when the
filing prints them but are excluded from the coverage denominator, so enrolling
a situational casilla can never lower coverage and flip a legitimate filing's
verdict. ``externally_grounded_casilla_ids`` is orthogonal to both: of the
casillas a filing reconciles, which are backed by an AEAT-authoritative oracle
rather than only by this application's own engine — the difference between a
number that agrees with itself and a number checked against the authority.

Those relationships are invariants, not conventions, so they are enforced on the
declaration: each tuple is unique, the when-present set is disjoint from the
computed set, and the externally-grounded set is a subset of their union. A
casilla claimed as externally grounded but reconciled by nothing would advertise
oracle backing for a value no filing ever compares.

:class:`RegistryVerificationPolicy` is the fold of those declarations across a
whole snapshot, and it is a frozen dataclass rather than a registry model
because nothing authors it: it is derived by
:meth:`RegistrySnapshot.verification_policy` from the expectations a revision
already declared. Folding it once here keeps the application surface from
re-deriving the union, the strictest tolerance, and the strictest coverage
floor at each call site, where the three could quietly disagree.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ._errors import RegistryValidationError
from ._ids import CasillaId, VerificationExpectationId
from ._schema_base import LegalRefs, RegistryModel, SourceRefs
from ._schema_scalars import DecimalValue

__all__ = [
    "RegistryVerificationPolicy",
    "VerificationExpectationDefinition",
]


class VerificationExpectationDefinition(RegistryModel):
    id: VerificationExpectationId
    computed_casilla_ids: tuple[CasillaId, ...]
    reconcile_when_present_casilla_ids: tuple[CasillaId, ...] = ()
    externally_grounded_casilla_ids: tuple[CasillaId, ...] = ()
    reconciliation_total_casilla_ids: Mapping[Literal["ingresar", "devolver"], CasillaId] = Field(
        default_factory=dict,
    )
    tolerance: DecimalValue
    rounding: str
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    discrepancy_causes: tuple[
        Literal["extraction_unreliable", "unmodelled_rule", "rounding", "correctness_divergence"],
        ...,
    ] = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("computed_casilla_ids")
    @classmethod
    def _computed_casilla_ids_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("verification expectation computed_casilla_ids must be unique")
        return value

    @field_validator("reconcile_when_present_casilla_ids")
    @classmethod
    def _reconcile_when_present_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(
                "verification expectation reconcile_when_present_casilla_ids must be unique",
            )
        return value

    @field_validator("externally_grounded_casilla_ids")
    @classmethod
    def _externally_grounded_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(
                "verification expectation externally_grounded_casilla_ids must be unique",
            )
        return value

    @model_validator(mode="after")
    def _reconcile_when_present_disjoint(self) -> VerificationExpectationDefinition:
        overlap = set(self.reconcile_when_present_casilla_ids) & set(self.computed_casilla_ids)
        if overlap:
            raise RegistryValidationError(
                "verification expectation reconcile_when_present_casilla_ids must be disjoint from "
                f"computed_casilla_ids (overlap: {sorted(overlap)})",
            )
        return self

    @model_validator(mode="after")
    def _externally_grounded_subset(self) -> VerificationExpectationDefinition:
        reconciled = set(self.computed_casilla_ids) | set(self.reconcile_when_present_casilla_ids)
        outside = set(self.externally_grounded_casilla_ids) - reconciled
        if outside:
            raise RegistryValidationError(
                "verification expectation externally_grounded_casilla_ids must be a subset of "
                f"computed_casilla_ids | reconcile_when_present_casilla_ids (outside: {sorted(outside)})",
            )
        return self


@dataclass(frozen=True, slots=True)
class RegistryVerificationPolicy:
    """Folded verification policy across a snapshot's verification expectations.

    Owns the registry-grounded projection (union of computed casilla ids, the
    union of reconcile-when-present casilla ids, the strictest tolerance, the
    strictest coverage floor) so the application verification surface consumes
    it rather than re-deriving the fold.

    ``computed_casilla_ids`` are the coverage-gated reconciliation targets: a
    filing that fails to reconcile them below ``min_coverage`` is NEEDS_REVIEW.
    ``reconcile_when_present_casilla_ids`` are value-reconciled when the filing
    prints them (a filed-vs-computed divergence surfaces a discrepancy) but are
    excluded from the coverage denominator, so enrolling a situational casilla
    can never lower coverage and flip a legitimate filing's verdict.

    ``externally_grounded_casilla_ids`` is the third, orthogonal axis: of the
    casillas a filing reconciles (``computed_casilla_ids`` or
    ``reconcile_when_present_casilla_ids``), which have an AEAT-authoritative
    independent oracle expected value backing their reconciliation, rather than
    only the app's own engine.
    """

    expectation_ids: tuple[VerificationExpectationId, ...]
    computed_casilla_ids: frozenset[CasillaId]
    reconcile_when_present_casilla_ids: frozenset[CasillaId]
    externally_grounded_casilla_ids: frozenset[CasillaId]
    tolerance: Decimal
    min_coverage: Decimal
