"""The profile facts the export reads the filer's identity from, and the door for one that is missing."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ...core.filing_producer_key import FilingProducerKey
from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import profile_required_facts_missing_verdict
from .errors import FilingPreconditionCondition, filing_no_recovery_verdict

IDENTITY_TAX_ID_PATH = "identity.tax_id"
IDENTITY_NAME_PATH = "identity.name"
IDENTITY_SURNAMES_PATH = "identity.surnames"
IDENTITY_LEGAL_NAME_PATH = "identity.legal_name"

# The operator declares a profile fact and never sees the producer key the
# layout reads, so a refusal for a blank identity field names these.
TAXPAYER_IDENTITY_PROFILE_FACTS: Mapping[FilingProducerKey, tuple[str, ...]] = MappingProxyType(
    {
        FilingProducerKey.TAXPAYER_TAX_ID: (IDENTITY_TAX_ID_PATH,),
        FilingProducerKey.TAXPAYER_LEGAL_NAME: (IDENTITY_LEGAL_NAME_PATH,),
        FilingProducerKey.TAXPAYER_GIVEN_NAME: (IDENTITY_NAME_PATH,),
        FilingProducerKey.TAXPAYER_SURNAMES: (IDENTITY_SURNAMES_PATH,),
        FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME: (IDENTITY_SURNAMES_PATH, IDENTITY_LEGAL_NAME_PATH),
    }
)


def missing_producer_fact_verdict(producer_key: FilingProducerKey) -> PreconditionVerdict:
    """The door for a required producer fact the export found blank.

    An identity fact is stated on the profile, so its door is the profile
    edit that names it. Any other producer fact is stated by no profile
    question, so the outcome is an operator decision rather than an action.
    """
    profile_facts = TAXPAYER_IDENTITY_PROFILE_FACTS.get(producer_key, ())
    if profile_facts:
        return profile_required_facts_missing_verdict(modelo=None, field_paths=profile_facts)
    return filing_no_recovery_verdict(
        FilingPreconditionCondition.OPERATION_ADMISSIBLE,
        facts={"producer_key": producer_key.value},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def missing_producer_fact_names(producer_key: FilingProducerKey) -> str:
    """The profile facts the operator declares for ``producer_key``, or the producer key where none is."""
    profile_facts = TAXPAYER_IDENTITY_PROFILE_FACTS.get(producer_key, ())
    return " or ".join(profile_facts) if profile_facts else producer_key.value


def profile_facts_for_producer_key(producer_key: object) -> tuple[str, ...]:
    """The profile facts a producer key's value is read from, or ``()`` for a key no profile question states."""
    try:
        return TAXPAYER_IDENTITY_PROFILE_FACTS.get(FilingProducerKey(str(producer_key)), ())
    except ValueError:
        return ()
