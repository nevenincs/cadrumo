"""Which jurisdiction a row is sourced in is decided once, for every surface.

The rule used to live at the command boundary, where it answered only for
operators typing at a terminal: a second frontend adding a ledger row would
have had to reimplement it, and the likeliest reimplementation is the one that
was wrong before -- default everything to ``ES``. Its consumer was already in
this layer, so the decision now is too.

What these hold is the decision itself, not its wording. Every case is driven
through the real function with real enum members, and the two obligations are
separated from the unresolved state, because the whole point of the rule is
that "nobody has said" and "the operator must say" are different answers and
only one of them is a refusal.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IrpfSpecialRegime
from ..source_jurisdiction import (
    SPANISH_SOURCE_JURISDICTION,
    SourceJurisdictionOutcome,
    SourceJurisdictionResolution,
    resolve_source_jurisdiction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_declared_resident_defaults_to_spain() -> None:
    """The ordinary case, and the only one that may default."""
    resolution = resolve_source_jurisdiction(
        None,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
        irpf_special_regime=IrpfSpecialRegime.GENERAL,
    )

    assert resolution.outcome is SourceJurisdictionOutcome.DEFAULTED
    assert resolution.jurisdiction == SPANISH_SOURCE_JURISDICTION


def test_an_undeclared_residency_is_unresolved_and_never_spain() -> None:
    """The coercion this rule exists to prevent.

    Returning ``ES`` here would stamp the transaction, and the stamp outlives
    the profile later being completed -- so the aggregation built to segregate
    an unresolved row would never see one.
    """
    resolution = resolve_source_jurisdiction(
        None,
        fiscal_residency=None,
        irpf_special_regime=None,
    )

    assert resolution.outcome is SourceJurisdictionOutcome.UNRESOLVED
    assert resolution.jurisdiction is None


def test_an_unresolved_row_is_not_an_obligation_to_state_one() -> None:
    """Unresolved is a state to carry, not a question to put to the operator.

    Conflating the two would refuse an ordinary incomplete profile at the
    point of adding a row, which is not what the aggregation asks for: it
    asks to receive the ``None`` and segregate it.
    """
    resolution = resolve_source_jurisdiction(None, fiscal_residency=None, irpf_special_regime=None)

    assert resolution.requires_operator_statement is False


@pytest.mark.parametrize(
    ("fiscal_residency", "irpf_special_regime", "expected"),
    [
        (
            FiscalResidency.NON_RESIDENT_IRNR,
            None,
            SourceJurisdictionOutcome.REQUIRED_NON_RESIDENT_IRNR,
        ),
        (
            FiscalResidency.RESIDENT_IRPF,
            IrpfSpecialRegime.IMPATRIADO,
            SourceJurisdictionOutcome.REQUIRED_IMPATRIADO,
        ),
    ],
    ids=["non_resident_irnr", "impatriado"],
)
def test_a_taxpayer_taxed_on_spanish_source_income_must_state_it(
    fiscal_residency: FiscalResidency,
    irpf_special_regime: IrpfSpecialRegime | None,
    expected: SourceJurisdictionOutcome,
) -> None:
    """Both regimes are taxed on Spanish-source income, so scope turns on this.

    Each carries its own outcome rather than one shared "must state it",
    because they are different questions to put to an operator and a surface
    that could not tell them apart would have to word both the same.
    """
    resolution = resolve_source_jurisdiction(
        None,
        fiscal_residency=fiscal_residency,
        irpf_special_regime=irpf_special_regime,
    )

    assert resolution.outcome is expected
    assert resolution.jurisdiction is None
    assert resolution.requires_operator_statement is True


def test_the_impatriado_obligation_outranks_the_undeclared_path() -> None:
    """Order is the rule here, not a style choice.

    An impatriado whose residency is not yet declared reaches both branches.
    Asking the undeclared question first would resolve them to ``UNRESOLVED``
    and never put the question the regime actually requires.
    """
    resolution = resolve_source_jurisdiction(
        None,
        fiscal_residency=None,
        irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
    )

    assert resolution.outcome is SourceJurisdictionOutcome.REQUIRED_IMPATRIADO


@pytest.mark.parametrize(
    ("fiscal_residency", "irpf_special_regime"),
    [
        (None, None),
        (FiscalResidency.RESIDENT_IRPF, IrpfSpecialRegime.GENERAL),
        (FiscalResidency.NON_RESIDENT_IRNR, None),
        (FiscalResidency.RESIDENT_IRPF, IrpfSpecialRegime.IMPATRIADO),
    ],
    ids=["undeclared", "ordinary_resident", "non_resident", "impatriado"],
)
def test_a_stated_value_wins_over_every_profile_signal(
    fiscal_residency: FiscalResidency | None,
    irpf_special_regime: IrpfSpecialRegime | None,
) -> None:
    """The operator's claim is the specific one; the profile is only a default.

    Parametrised over every condition INCLUDING the two that would otherwise
    refuse, because those are exactly the cases where a statement has to be
    accepted -- they are the ones that asked for it.
    """
    resolution = resolve_source_jurisdiction(
        "PT",
        fiscal_residency=fiscal_residency,
        irpf_special_regime=irpf_special_regime,
    )

    assert resolution.outcome is SourceJurisdictionOutcome.STATED
    assert resolution.jurisdiction == "PT"


def test_every_outcome_the_enum_declares_is_reachable() -> None:
    """A member no condition produces is a state a consumer must handle for nothing.

    Driven through the real function across the real condition space rather
    than asserted from a list, so a member added without a path here shows up
    as a gap instead of as unreachable code nobody notices.
    """
    conditions = [
        ("PT", None, None),
        (None, FiscalResidency.RESIDENT_IRPF, IrpfSpecialRegime.GENERAL),
        (None, None, None),
        (None, FiscalResidency.NON_RESIDENT_IRNR, None),
        (None, FiscalResidency.RESIDENT_IRPF, IrpfSpecialRegime.IMPATRIADO),
    ]

    produced = {
        resolve_source_jurisdiction(value, fiscal_residency=residency, irpf_special_regime=regime).outcome
        for value, residency, regime in conditions
    }

    assert produced == set(SourceJurisdictionOutcome)


def test_a_refusal_carrying_a_jurisdiction_is_refused() -> None:
    """A value beside an obligation invites a caller to use it and skip the question."""
    with pytest.raises(ValidationError):
        SourceJurisdictionResolution(
            outcome=SourceJurisdictionOutcome.REQUIRED_IMPATRIADO,
            jurisdiction="ES",
        )


def test_a_resolved_outcome_carrying_no_jurisdiction_is_refused() -> None:
    """The other direction: nothing to stamp and no refusal to report.

    Paired with the test above so the invariant reads as an agreement between
    the two fields rather than as a ban on one combination.
    """
    with pytest.raises(ValidationError):
        SourceJurisdictionResolution(outcome=SourceJurisdictionOutcome.DEFAULTED)
