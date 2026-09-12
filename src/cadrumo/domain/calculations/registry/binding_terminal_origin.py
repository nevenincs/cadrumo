"""The authored expectation of where a binding's value ultimately comes from.

Runtime provenance already records the terminal nodes a resolver actually
reached. What it cannot say on its own is whether those nodes are the ones the
declaration intended: a binding that silently resolves from a derived
calculation instead of the filed casilla it names is still a complete-looking
result. A :class:`TerminalOriginExpectation` is the compile-time half of that
pair -- the authored claim that runtime provenance is audited against, which is
what makes the claim falsifiable rather than decorative.

The expectation states four things per admitted origin: the class of terminal
fact, its role in the provenance graph (reusing the existing
:class:`~cadrumo.core.aggregation.CalculationSourceLineageRole`), how many such
nodes must appear, and whether each must carry an evidence fingerprint. The
cardinality axis is what keeps "no rows found" distinguishable from "rows were
required and are missing": ``zero_or_more`` is a declaration that emptiness is
legitimate, never a default.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BeforeValidator

from ....core.aggregation import CalculationSourceLineageRole
from .schema_base import RegistryModel, coerce_enum_member

__all__ = [
    "TerminalOriginCardinality",
    "TerminalOriginClass",
    "TerminalOriginExpectation",
    "TerminalOriginFingerprint",
]

TerminalOriginCardinality = Literal["exactly_one", "at_least_one", "zero_or_more"]
"""How many terminal nodes of one origin class the resolved graph must carry."""

TerminalOriginFingerprint = Literal["required", "optional"]
"""Whether each terminal node of this class must carry an evidence fingerprint."""


class TerminalOriginClass(StrEnum):
    """The closed set of terminal fact classes a binding value can rest on.

    A terminal origin is where derivation stops: the persisted fact that is not
    itself computed from another registry source within the same resolution.
    """

    OPERATOR_INPUT = "operator_input"
    """A value the operator supplied directly, answerable and attributable."""

    DESIGN_CONSTANT = "design_constant"
    """A byte run AEAT fixes in the diseño de registro; no operator supplies it."""

    PROFILE_FIELD = "profile_field"
    """A field of the taxpayer's censo/profile record."""

    FILED_MODELO_CASILLA = "filed_modelo_casilla"
    """A casilla value of an immutable, already-filed modelo revision."""

    LEDGER_AGGREGATE = "ledger_aggregate"
    """A fold over classified ledger transactions."""

    INVOICE_CATALOGUE = "invoice_catalogue"
    """A fold over the invoice catalogue, in either or both directions."""

    PERCEPTOR_OBSERVATION = "perceptor_observation"
    """A per-perceptor retención observation from its dedicated store."""

    DETAIL_RECORD = "detail_record"
    """A row of an authored or pulled detail-record family."""

    DERIVED_CALCULATION = "derived_calculation"
    """A value produced by another calculation rather than a persisted fact."""


class TerminalOriginExpectation(RegistryModel):
    """One admitted terminal origin and the shape the resolved graph must show."""

    source_class: Annotated[TerminalOriginClass, BeforeValidator(coerce_enum_member(TerminalOriginClass))]
    role: Annotated[
        CalculationSourceLineageRole,
        BeforeValidator(coerce_enum_member(CalculationSourceLineageRole)),
    ]
    cardinality: TerminalOriginCardinality
    fingerprint: TerminalOriginFingerprint
