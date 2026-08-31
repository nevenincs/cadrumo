"""Exact scenario-identity coverage for shared profile preconditions."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ...core.profile_session import ProfileSessionRefusalReason
from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions import PreconditionVerdict
from ..profile_preconditions import (
    FormerProductDetectionScope,
    ProfileSelectionFailure,
    former_product_state_verdict,
    inspect_active_profile_precondition,
    inspect_filing_taxpayer_identity_precondition,
    profile_selection_failure_verdict,
    profile_session_failure_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _ExpectedOutcome:
    condition_id: str
    action_id: str | None
    no_recovery: NoRecoveryOutcome | None = None


# Test-owned denominator.  Keys are scenario identities, not an asserted total:
# a branch may join an existing condition while remaining independently covered.
_EXPECTED_SCENARIOS: dict[str, _ExpectedOutcome] = {
    "active.none_registered": _ExpectedOutcome(
        "profile.active.available",
        "operator.profile.create",
    ),
    "active.registered_unselected": _ExpectedOutcome(
        "profile.active.available",
        "operator.profile.login",
    ),
    "filing.tax_id_undeclared": _ExpectedOutcome(
        "taxpayer.identity.tax_id.declared",
        "operator.profile.edit",
    ),
    "selection.explicit_blank": _ExpectedOutcome(
        "profile.selection.nonblank",
        "operator.profile.list",
    ),
    "selection.explicit_unknown": _ExpectedOutcome(
        "profile.selection.known",
        "operator.profile.list",
    ),
    "selection.explicit_ambiguous": _ExpectedOutcome(
        "profile.selection.unambiguous",
        "operator.profile.list",
    ),
    "selection.ambient_ambiguous": _ExpectedOutcome(
        "profile.selection.unambiguous",
        "operator.profile.list",
    ),
    "selection.ambient_tombstoned": _ExpectedOutcome(
        "profile.selection.live",
        "operator.profile.repair_clear_active",
    ),
    "session.absent": _ExpectedOutcome(
        "profile.session.logged_in",
        "operator.profile.login",
    ),
    "session.keychain_entry_missing": _ExpectedOutcome(
        "profile.session.logged_in",
        "operator.profile.login",
    ),
    "session.expired_idle": _ExpectedOutcome(
        "profile.session.current",
        "operator.profile.login",
    ),
    "session.expired_absolute": _ExpectedOutcome(
        "profile.session.current",
        "operator.profile.login",
    ),
    "session.custody_changed": _ExpectedOutcome(
        "profile.session.current",
        "operator.profile.login",
    ),
    "session.keyring_unavailable": _ExpectedOutcome(
        "profile.session.logged_in",
        "operator.profile.login",
    ),
    "session.schema_version_mismatch": _ExpectedOutcome(
        "profile.session.schema_current",
        "operator.profile.login",
    ),
    "session.malformed": _ExpectedOutcome(
        "profile.session.well_formed",
        "operator.profile.login",
    ),
    "session.tampered": _ExpectedOutcome(
        "profile.session.integrity_valid",
        "operator.profile.login",
    ),
    "former_product.root_profile_normalisation": _ExpectedOutcome(
        "storage.former_product_state.absent",
        None,
        NoRecoveryOutcome.SAFETY,
    ),
    "former_product.startup": _ExpectedOutcome(
        "storage.former_product_state.absent",
        None,
        NoRecoveryOutcome.SAFETY,
    ),
}


def _observed_scenarios() -> dict[str, PreconditionVerdict]:
    none_registered = inspect_active_profile_precondition(
        active_profile_present=False,
        registered_profile_count=0,
    )
    registered_unselected = inspect_active_profile_precondition(
        active_profile_present=False,
        registered_profile_count=2,
    )
    filing = inspect_filing_taxpayer_identity_precondition(
        declared_tax_id="",
        profile_name="profile-uuid",
    )
    assert none_registered is not None
    assert registered_unselected is not None
    assert filing is not None
    return {
        "active.none_registered": none_registered,
        "active.registered_unselected": registered_unselected,
        "filing.tax_id_undeclared": filing,
        "selection.explicit_blank": profile_selection_failure_verdict(
            ProfileSelectionFailure.BLANK,
            requested_profile="",
        ),
        "selection.explicit_unknown": profile_selection_failure_verdict(
            ProfileSelectionFailure.UNKNOWN,
            requested_profile="unknown",
        ),
        "selection.explicit_ambiguous": profile_selection_failure_verdict(
            ProfileSelectionFailure.AMBIGUOUS,
            requested_profile="shared-label",
        ),
        "selection.ambient_ambiguous": profile_selection_failure_verdict(
            ProfileSelectionFailure.AMBIGUOUS,
            requested_profile="shared-label",
        ),
        "selection.ambient_tombstoned": profile_selection_failure_verdict(
            ProfileSelectionFailure.INACTIVE,
            requested_profile="profile-uuid",
            lifecycle_status="tombstoned",
        ),
        **{
            f"session.{reason.value}": profile_session_failure_verdict(
                reason,
                profile_name="profile-uuid",
            )
            for reason in ProfileSessionRefusalReason
        },
        "former_product.root_profile_normalisation": former_product_state_verdict(
            FormerProductDetectionScope.ROOT_PROFILE_NORMALISATION,
        ),
        "former_product.startup": former_product_state_verdict(
            FormerProductDetectionScope.STARTUP,
        ),
    }


def test_every_owned_scenario_has_the_expected_typed_outcome() -> None:
    observed = _observed_scenarios()

    assert observed.keys() == _EXPECTED_SCENARIOS.keys()
    for scenario_id, expected in _EXPECTED_SCENARIOS.items():
        verdict = observed[scenario_id]
        assert verdict.failed_condition_id == expected.condition_id, scenario_id
        assert (verdict.action.action_id if verdict.action is not None else None) == expected.action_id, scenario_id
        assert verdict.no_recovery_outcome is expected.no_recovery, scenario_id


def test_repair_recovery_requires_confirmation_but_resolves_the_torn_pointer() -> None:
    verdict = _observed_scenarios()["selection.ambient_tombstoned"]

    assert tuple(binding.model_dump(mode="json") for binding in verdict.argument_bindings) == (
        {
            "argument_name": "clear_active",
            "status": "resolved",
            "value": True,
            "source": "operator_action.request_context",
            "source_key": "clear_active",
            "source_evidence_id": None,
        },
        {
            "argument_name": "profile",
            "status": "resolved",
            "value": "profile-uuid",
            "source": "operator_action.verdict_context",
            "source_key": "profile",
            "source_evidence_id": None,
        },
        {
            "argument_name": "yes",
            "status": "missing",
            "value": None,
            "source": None,
            "source_key": None,
            "source_evidence_id": None,
        },
    )
    assert verdict.missing_argument_names == ("yes",)


def test_satisfied_profile_and_tax_identity_preconditions_do_not_refuse() -> None:
    assert (
        inspect_active_profile_precondition(
            active_profile_present=True,
            registered_profile_count=1,
        )
        is None
    )
    assert (
        inspect_filing_taxpayer_identity_precondition(
            declared_tax_id="12345678Z",
            profile_name="profile-uuid",
        )
        is None
    )
