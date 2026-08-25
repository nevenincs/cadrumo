"""Anti-tautology proof: a failed atomic create rolls back cleanly.

Profile creation stages a whole capsule and publishes it in one step, so it
has an all-or-nothing contract: a failure anywhere before publication must
leave no committed capsule, no label projection, and no active-profile
pointer, or the operator sees a half-created profile that no verb can finish
and no verb can remove.

These tests force a *real* failure. The trigger is an initial fact at a path
the profile schema does not declare: the create door judges its initial facts
before it stages anything, and raises ``ProfileSchemaValidationError``. No
mock, no patched failure injection — the rejection is the genuine validation
the door runs, and it is the same judgement every later edit passes through.

A missing filing field is deliberately NOT the trigger any more. A profile is
born incomplete on purpose, so an incomplete fact set is legitimate at this
door and would prove nothing about rollback.

The anti-tautology guard is the second test: it proves the rollback
assertions are not vacuously true by showing the *successful* create leaves
exactly the artifacts the failed create must not. If the rollback ever
silently no-ops, the first test's "absent" assertions would still pass
against a phantom bucket — the success-path test is what closes that hole.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from ....adapters.persistence.storage.custody import list_current_profile_custody_capsule_ids
from ....core.bucket_pointer import read_pointer
from ....core.config import load_settings
from ....domain.user_profile import ProfileSchemaValidationError, UserProfileFact
from ....tests.profile_storage_root_fixture import profile_storage_root_fixture
from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket
from cadrumo.application.user_profile.registration import register_profile_with_credentials

__all__ = ["profile_storage_root_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

# The minimum schema-valid fact set the user-profile schema accepts.
_VALID_FACTS: Mapping[str, str] = {
    "identity.tax_id": "00000000T",
    "identity.name": "Test Operator",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    "provenance.source": "manual_cli",
}
# A fact at a path the schema does not declare. Unlike a missing required
# field, this is refused whether or not the profile is complete, so it fails
# the create rather than being deferred to the completion promotion.
_UNDECLARED_FACTS: Mapping[str, str] = {**_VALID_FACTS, "identity.not_a_declared_path": "x"}
_VICTIM_LABEL = "Rollback Victim"
_SURVIVOR_LABEL = "Rollback Survivor"
_PASSPHRASE = "atomic-create-rollback-operator-secret"  # noqa: S105 - synthetic test fixture


def _register(label: str, *, facts: Mapping[str, str]) -> None:
    """Run the real create door for ``label`` against ``facts``."""
    register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        label=label,
        passphrase=_PASSPHRASE,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts.items()),
    )


def test_failed_atomic_create_raises_and_leaves_no_profile(profile_storage_root: Path) -> None:
    """A refused create commits no capsule, no label, and no pointer.

    The undeclared path makes the create door's fact judgement refuse before
    anything is staged. Nothing about the victim may survive: not a committed
    capsule the discovery scan would list, and not an active-profile pointer
    the next command would follow into a bucket that has no record.
    """
    with pytest.raises(ProfileSchemaValidationError):
        _register(_VICTIM_LABEL, facts=_UNDECLARED_FACTS)

    root = load_settings().cadrumo_local_storage_root

    assert list_current_profile_custody_capsule_ids(root=root) == (), "a refused create committed a capsule"
    assert read_pointer(root).bucket_id is None, "a refused create left a dangling active-profile pointer"
    assert read_profile_bucket(_VICTIM_LABEL) is None, "a refused create left a phantom label projection"


def test_successful_atomic_create_lands_the_artifacts_a_failure_clears(profile_storage_root: Path) -> None:
    """Anti-tautology proof: a *successful* create lands what a failure must not.

    If the rollback under test silently no-opped, the absent-artifact
    assertions in :func:`test_failed_atomic_create_raises_and_leaves_no_profile`
    would still pass against a never-created profile. This test pins the
    positive contract — capsule committed, pointer written, label resolvable —
    so the failure test's assertions are proven non-vacuous: the artifacts
    genuinely exist on success and genuinely do not on rollback.
    """
    _register(_SURVIVOR_LABEL, facts=_VALID_FACTS)

    root = load_settings().cadrumo_local_storage_root

    committed = list_current_profile_custody_capsule_ids(root=root)
    assert len(committed) == 1
    pointer = read_pointer(root)
    assert pointer.bucket_id == str(committed[0])
    scanned = read_profile_bucket(_SURVIVOR_LABEL)
    assert scanned is not None
    assert scanned.bucket_id == str(committed[0])
