"""Where a ledger row's income is sourced, and when the operator must say so.

Two taxpayer conditions make the source jurisdiction an answer nobody may
default. A non-resident taxed under IRNR is taxed on Spanish-source income
alone, so which jurisdiction a row belongs to decides whether it is in scope at
all. An impatriado under the special regime is taxed on Spanish-source income
by the same logic, with foreign-source income segregated out of the base. For
both, a row whose jurisdiction was assumed rather than stated is a row assigned
to a base by accident.

Everyone else has a declared residency, and for them Spain is the ordinary
answer -- but only once a residency HAS been declared. A profile that has
declared none resolves to ``None``, which is the unresolved state rather than a
missing one: :mod:`~application.aggregation._impatriado_income_ledger`
segregates such a row with a typed unresolved-jurisdiction issue, on the stated
invariant that an unresolved jurisdiction "is NEVER silently coerced to ES".

That invariant is why this is a decision and not a default. Coercing to ``ES``
for an undeclared profile performed exactly the coercion the aggregation exists
to refuse, so the ``None`` never reached the layer built to handle it and
foreign-source income folded into the Spanish base. The stamp is persisted on
the transaction, so the mistake outlived the profile later being completed.

The rule lives here rather than at a command boundary because it is tax law
about a taxpayer, not a fact about argv: it answers the same way whichever
surface asks, and its consumer -- the aggregation above -- is in this layer
too. What a surface still owns is how it ASKS and how it words a refusal, which
is why this returns a typed outcome rather than raising a presentation error.

See Also:
    :mod:`~application.aggregation._impatriado_income_ledger`
        The aggregation that segregates an unresolved jurisdiction rather than
        admitting it to the Spanish base.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.contribuyente.renta_codes import FiscalResidency
from ...domain.deadlines.models import IrpfSpecialRegime

__all__ = [
    "OUTCOMES_REQUIRING_AN_OPERATOR_STATEMENT",
    "SPANISH_SOURCE_JURISDICTION",
    "SourceJurisdictionOutcome",
    "SourceJurisdictionResolution",
    "resolve_source_jurisdiction",
]

#: The jurisdiction a declared resident's row is sourced in absent any other
#: statement. Named rather than spelled inline so the default and the refusals
#: that withhold it cannot drift apart.
SPANISH_SOURCE_JURISDICTION = "ES"


class SourceJurisdictionOutcome(StrEnum):
    """What the taxpayer's conditions say about this row's source jurisdiction.

    Five members and not three, because the two refusals are different
    questions to put to an operator and the two answers have different
    provenance. Collapsing either pair would make a surface guess which it
    was holding.
    """

    #: The operator stated it; no profile signal is consulted.
    STATED = "stated"
    #: A declared residency with no special regime; Spain by default.
    DEFAULTED = "defaulted"
    #: No residency declared. NOT a missing answer, and never coerced to Spain.
    UNRESOLVED = "unresolved"
    #: Non-resident under IRNR: the operator must state it.
    REQUIRED_NON_RESIDENT_IRNR = "required_non_resident_irnr"
    #: Impatriado special regime: the operator must state it.
    REQUIRED_IMPATRIADO = "required_impatriado"


#: The outcomes that carry a jurisdiction. Derived from below rather than
#: repeated, so a member added without deciding this side fails the model.
_OUTCOMES_CARRYING_A_JURISDICTION = frozenset(
    {SourceJurisdictionOutcome.STATED, SourceJurisdictionOutcome.DEFAULTED},
)


#: The outcomes that oblige the operator to state a jurisdiction.
#:
#: Derived by subtraction rather than listed, so it cannot fall behind the
#: enum: everything that neither produces a jurisdiction nor is the unresolved
#: state is, by construction, a question somebody has to answer. A surface
#: wording these refusals reads this rather than rebuilding it, which is also
#: why it exists -- learning the set by constructing a resolution per member is
#: not possible, since the ones that carry a value refuse to be built without
#: one.
OUTCOMES_REQUIRING_AN_OPERATOR_STATEMENT = frozenset(
    set(SourceJurisdictionOutcome) - _OUTCOMES_CARRYING_A_JURISDICTION - {SourceJurisdictionOutcome.UNRESOLVED},
)


class SourceJurisdictionResolution(BaseModel):
    """One resolution: what the conditions decided, and the value if there is one."""

    model_config = STRICT_FROZEN_CONFIG

    outcome: SourceJurisdictionOutcome
    jurisdiction: str | None = None

    @model_validator(mode="after")
    def _a_jurisdiction_exists_exactly_when_the_outcome_produces_one(self) -> Self:
        """Refuse a resolution whose value disagrees with its own outcome.

        Both directions are wrong in the same way. A refusal carrying a
        jurisdiction invites a caller to use it and skip the question; a
        resolved outcome carrying none leaves that caller with nothing to
        stamp and no refusal to report.
        """
        carries = self.outcome in _OUTCOMES_CARRYING_A_JURISDICTION
        if carries != (self.jurisdiction is not None):
            raise ValueError("source jurisdiction resolution disagrees with its own outcome")
        return self

    @property
    def requires_operator_statement(self) -> bool:
        """Whether the taxpayer's conditions oblige the operator to state it."""
        return self.outcome in OUTCOMES_REQUIRING_AN_OPERATOR_STATEMENT


def resolve_source_jurisdiction(
    operator_value: str | None,
    *,
    fiscal_residency: FiscalResidency | None,
    irpf_special_regime: IrpfSpecialRegime | None,
) -> SourceJurisdictionResolution:
    """Decide this row's source jurisdiction from the taxpayer's conditions.

    The order is the rule, not a style. An operator statement wins over every
    profile signal, because it is the more specific claim and the profile is
    only ever a default. The two refusals come next and the impatriado refusal
    is reachable for a taxpayer whose residency is undeclared, so it must be
    asked before the undeclared path -- otherwise an impatriado with an
    incomplete profile would resolve to ``UNRESOLVED`` and never be asked the
    question the regime requires.

    Args:
        operator_value: The jurisdiction the operator stated, or ``None``.
        fiscal_residency: The profile's declared residency, or ``None`` when
            the profile has declared none.
        irpf_special_regime: The profile's declared IRPF special regime, if any.

    Returns:
        The resolution, carrying a jurisdiction only where the conditions
        produce one.
    """
    if operator_value is not None:
        return SourceJurisdictionResolution(
            outcome=SourceJurisdictionOutcome.STATED,
            jurisdiction=operator_value,
        )
    if fiscal_residency is FiscalResidency.NON_RESIDENT_IRNR:
        return SourceJurisdictionResolution(outcome=SourceJurisdictionOutcome.REQUIRED_NON_RESIDENT_IRNR)
    if irpf_special_regime is IrpfSpecialRegime.IMPATRIADO:
        return SourceJurisdictionResolution(outcome=SourceJurisdictionOutcome.REQUIRED_IMPATRIADO)
    if fiscal_residency is None:
        return SourceJurisdictionResolution(outcome=SourceJurisdictionOutcome.UNRESOLVED)
    return SourceJurisdictionResolution(
        outcome=SourceJurisdictionOutcome.DEFAULTED,
        jurisdiction=SPANISH_SOURCE_JURISDICTION,
    )
