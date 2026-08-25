"""The wizard's profile-id resolver refuses a taken label before minting an id.

``create`` addresses a fresh capsule, so a label already bound to a committed
one must be refused here. Without the refusal the wizard mints an id, the
operator answers a whole flow against it, and the collision only surfaces much
later when the capsule cannot be published under a label already in use.

The tests drive the real create door and read the real committed-label
projection: no substitute for the label store, because a substitute is exactly
what would hide the resolver consulting nothing at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from ....core.errors import CoreValidationError
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_storage_root_fixture import profile_storage_root_fixture
from ...user_profile.registration import register_profile_with_credentials
from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket
from .._commands import _resolve_profile_id_for_mode
from .._errors import WizardMissingFlagError
from .._models import WizardFlow

__all__ = ["profile_storage_root_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_FACTS: Mapping[str, str] = {
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
_LABEL = "Gestoría Peñaranda"
_PASSPHRASE = "wizard-profile-id-resolution-operator-secret"  # noqa: S105 - synthetic test fixture


def _flow() -> WizardFlow:
    from ....core.wizard_catalogue import get_setup_flow

    return cast(WizardFlow, get_setup_flow())


def _register(label: str) -> None:
    register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        label=label,
        passphrase=_PASSPHRASE,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in _FACTS.items()),
    )


def test_create_mints_a_fresh_id_for_an_unused_label(profile_storage_root: Path) -> None:
    """Anti-tautology partner: an unused label resolves, so the refusal is not blanket."""
    minted = _resolve_profile_id_for_mode(_flow(), "create", _LABEL)

    assert minted
    assert read_profile_bucket(_LABEL) is None, "resolving an id must not itself commit a capsule"
    assert _resolve_profile_id_for_mode(_flow(), "create", _LABEL) != minted, "each create mints a distinct id"


def test_create_refuses_a_label_already_bound_to_a_committed_capsule(profile_storage_root: Path) -> None:
    """The restored refusal: a taken label is rejected before an id is minted."""
    _register(_LABEL)
    assert read_profile_bucket(_LABEL) is not None

    with pytest.raises(CoreValidationError) as refusal:
        _resolve_profile_id_for_mode(_flow(), "create", _LABEL)

    assert refusal.value.translated_message == "application.wizard.errors.profile_label_taken"
    context = refusal.value.context
    assert context is not None
    assert context["label"] == _LABEL


def test_create_refuses_a_taken_label_case_insensitively(profile_storage_root: Path) -> None:
    """Label uniqueness is casefolded, matching the committed-label projection.

    A refusal that compared exactly would let ``gestoría peñaranda`` through to
    mint an id the capsule layer then refuses, which is the collision this
    check exists to move earlier.
    """
    _register(_LABEL)

    with pytest.raises(CoreValidationError):
        _resolve_profile_id_for_mode(_flow(), "create", _LABEL.upper())


def test_edit_resolves_a_registered_label_to_its_committed_bucket(profile_storage_root: Path) -> None:
    """A non-create mode addresses the existing capsule rather than minting."""
    _register(_LABEL)
    pointer = read_profile_bucket(_LABEL)
    assert pointer is not None

    assert _resolve_profile_id_for_mode(_flow(), "edit", _LABEL) == pointer.bucket_id


def test_edit_refuses_an_unregistered_label(profile_storage_root: Path) -> None:
    """The resolution below is itself the registration check, and it fails closed."""
    with pytest.raises(WizardMissingFlagError):
        _resolve_profile_id_for_mode(_flow(), "edit", "Never Registered")
