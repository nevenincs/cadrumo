"""The filer's own IVA territory is a profile fact, and its absence refuses at setup.

Classification needs both parties' :class:`~domain.iva.IvaTerritorialScope`, and
one party on every ingested invoice is the operator. That side is never a
document question: the taxpayer's own establishment is declared once, censo-fed,
and consumed from the profile authority. So the gate under test resolves it from
the profile and refuses when it cannot -- once, at setup, rather than asking the
operator per document about a fact the profile is supposed to carry.

Two properties are separable here and both are load-bearing.

**Absence never resolves to the mainland.** The peninsula is the majority
population, so a default there passes every plausible test while silently placing
Canarian and Ceutan filers inside a territory their operations are not subject
to. The refusal is the safe direction, and the cases below assert the refusal
rather than merely asserting "not Canarias".

**The refusal is actionable.** This CLI's operator is an autonomous agent, so a
refusal that says the profile is incomplete produces a retry loop, while one
naming the missing fact and the verb that supplies it produces a recovery. The
message content is therefore under gate, not just the exception type.

See Also:
    :func:`~domain.iva.territorial_scope_for_spanish_postal_code`
        The territorial derivation this gate delegates to.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed classification the profile fact resolves into.
"""

from __future__ import annotations

import pytest

from ....core import NoRecoveryOutcome
from ....domain.iva import IvaTerritorialScope
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._confirm_establishment import _filer_scope
from .._evidence_draft import PurchaseInvoiceEvidenceInputError
from .._filer_establishment import FILER_POSTCODE_FACT_PATH, resolve_filer_territorial_scope
from .._preconditions import LedgerPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def _profile(postcode: str | None) -> UserProfileRecord:
    """A profile carrying an optional fiscal-address postcode fact."""
    facts = (UserProfileFact(path="identity.tax_id", value="X1234567L"),)
    if postcode is not None:
        facts = (*facts, UserProfileFact(path=FILER_POSTCODE_FACT_PATH, value=postcode))
    return UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_ID, facts=facts)


@pytest.mark.parametrize(
    ("postcode", "expected"),
    [
        ("35001", IvaTerritorialScope.ES_CANARIAS),
        ("38001", IvaTerritorialScope.ES_CANARIAS),
        ("51001", IvaTerritorialScope.ES_CEUTA_MELILLA),
        ("52001", IvaTerritorialScope.ES_CEUTA_MELILLA),
        ("28013", IvaTerritorialScope.ES_MAINLAND),
        # A Barcelona postcode, deliberately leading-zero. The profile fact
        # store has its own guard against a zero-significant identifier being
        # round-tripped through Decimal and losing the zero; a gate that read
        # "8001" would resolve a four-character string to no territory at all.
        ("08001", IvaTerritorialScope.ES_MAINLAND),
    ],
)
def test_a_declared_postcode_resolves_the_filers_own_territory(
    postcode: str,
    expected: IvaTerritorialScope,
) -> None:
    """The whole point of the fact: the operator side is answered without the paper."""
    assert resolve_filer_territorial_scope(profile_record=_profile(postcode)) is expected


@pytest.mark.parametrize(
    "postcode",
    [
        None,
        "",
        "   ",
        "2801",
        "280134",
        "28O13",
        "Madrid",
    ],
)
def test_an_unresolvable_own_territory_refuses_rather_than_defaulting(postcode: str | None) -> None:
    """Absent or unreadable evidence must refuse, never resolve to the peninsula.

    Parameterised across absence and every malformed shape rather than testing
    absence alone, because the failure this guards is not "the fact is missing"
    -- it is "something was present and nobody could read it", which is exactly
    the case a permissive parse turns into a confident mainland answer.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        resolve_filer_territorial_scope(profile_record=_profile(postcode))


def test_no_unresolvable_input_ever_returns_a_territory() -> None:
    """The anti-default property stated once over the whole refusing population.

    The case above proves each input raises. This one proves the stronger thing
    the design actually rules: that no unresolvable input reaches a RETURN at all.
    A future edit adding a fallback would satisfy "raises for None" while
    quietly answering for the malformed shapes, so the absence of any returned
    value is asserted over the set rather than per case.
    """
    returned = []
    for postcode in (None, "", "   ", "2801", "280134", "28O13", "Madrid"):
        try:
            returned.append((postcode, resolve_filer_territorial_scope(profile_record=_profile(postcode))))
        except PurchaseInvoiceEvidenceInputError:
            continue

    assert not returned, f"these unresolvable inputs were answered instead of refused: {returned}"


def test_a_missing_profile_refuses_rather_than_assuming_a_territory() -> None:
    """No profile is not an empty profile, and neither is a territory."""
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        resolve_filer_territorial_scope(profile_record=None)


def test_confirm_boundary_preserves_the_exact_profile_precondition_refusal() -> None:
    """Confirm does not flatten a profile precondition into review-item prose."""
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _filer_scope(_profile(None))

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.FILER_POSTCODE_VALID.value
    assert verdict.evidence[0].values == {"filer_postcode_present": False}
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


class TestTheRefusalIsActionable:
    """A refusal an autonomous operator cannot act on produces a retry loop."""

    def test_the_refusal_names_the_missing_fact(self) -> None:
        """Naming the fact path is what makes the gap addressable rather than abstract."""
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as caught:
            resolve_filer_territorial_scope(profile_record=_profile(None))

        assert FILER_POSTCODE_FACT_PATH in str(caught.value)

    def test_the_refusal_names_the_verb_that_supplies_it(self) -> None:
        """The recovery path travels with the refusal, not in documentation elsewhere."""
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as caught:
            resolve_filer_territorial_scope(profile_record=_profile(None))

        assert caught.value.terminal_precondition_verdict is not None
        assert caught.value.terminal_precondition_verdict.failed_condition_id == (
            LedgerPreconditionCondition.FILER_POSTCODE_VALID.value
        )
        assert caught.value.terminal_precondition_verdict.evidence[0].values == {"filer_postcode_present": False}

    def test_an_unreadable_value_says_so_rather_than_reporting_it_absent(self) -> None:
        """Two different gaps that a single message would make indistinguishable.

        "You never declared a postcode" and "what you declared is not a postcode"
        need different operator actions, and an agent told the fact is missing
        when it is actually malformed will re-supply the same malformed value.
        """
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as caught:
            resolve_filer_territorial_scope(profile_record=_profile("Madrid"))

        assert "Madrid" in str(caught.value)
