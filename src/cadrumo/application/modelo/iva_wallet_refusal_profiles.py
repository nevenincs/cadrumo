"""Declared doors of the refusals the IVA wallet gate raises at calculation, verification, filing and export.

A refusal that says the period's carry has no usable recorded authority opens the
opening-balance declaration; one that says the carry rests on the taxpayer's own
records alone opens the explicit override; any other is the operator's decision.
"""

from __future__ import annotations

from typing import Final

from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference
from ..operator_surface.models import ManifestActionProfile

_IVA_WALLET_BLOCKED_DECISION_SCENARIOS = (
    "filed_history_requires_override",
    "local_calculation_redeme_unstated",
    "local_calculation_refund_undecided",
    "local_evidence_unreadable",
    "local_recurrence_requires_override",
    "no_usable_authority",
    "stale_wallet_local_recurrence_requires_override",
    "stale_wallet_no_local_recurrence",
    "wallet_local_recurrence_divergence",
)

_IVA_WALLET_CALCULATE_SCENARIOS = (
    "backend_casilla_conflict",
    *_IVA_WALLET_BLOCKED_DECISION_SCENARIOS,
    "caller_binding_conflict",
    "caller_casilla_conflict",
    "first_period_zero_ungrounded",
    "not_seeded",
    "registry_snapshot_unavailable",
    "selected_amount_missing",
    "supplied_decision_mismatch",
    "target_mismatch",
    "taxpayer_identity_missing",
    "taxpayer_mismatch",
    "unsupported_decision_type",
)

_IVA_WALLET_REVISION_SCENARIOS = (
    "amount_mismatch",
    *_IVA_WALLET_BLOCKED_DECISION_SCENARIOS,
    "first_period_zero_ungrounded",
    "local_calculation_only",
    "not_seeded",
    "registry_snapshot_unavailable",
    "revision_amount_missing",
    "selected_amount_missing",
    "target_mismatch",
)


IVA_WALLET_OPENING_BALANCE_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "first_period_zero_ungrounded",
        "local_evidence_unreadable",
        "no_usable_authority",
        "not_seeded",
    },
)
"""The wallet refusals the period's opening balance is the way out of.

Each says the period's carry has no usable recorded authority, which is exactly
what declaring the opening balance supplies. A stale wallet, a divergence, or a
correction names a different wallet entry, so it keeps no action here rather
than naming a command that would not settle it. The wallet gate's served step
and these profiles' action read this one set.
"""

IVA_WALLET_OPENING_BALANCE_ACTION_ID: Final[str] = "operator.modelo.iva_wallet.seed"
"""The catalogue action that declares the opening balance of a period's carry."""

IVA_WALLET_OVERRIDE_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "filed_history_requires_override",
        "local_recurrence_requires_override",
        "stale_wallet_local_recurrence_requires_override",
    },
)
"""The wallet refusals an explicit taxpayer override of the period's carry is the way out of.

Each says the carry rests on the taxpayer's own records alone, with no current
AEAT wallet behind it, so it is carried only once the taxpayer states the amount
and the evidence for it. The amount those records give is known, so the action
names it; the reason and the evidence are the taxpayer's to supply.
"""

IVA_WALLET_OVERRIDE_ACTION_ID: Final[str] = "operator.modelo.iva_wallet.override"
"""The catalogue action that records an explicit taxpayer override of a period's carry."""


def _iva_wallet_action_id(scenario_code: str) -> str | None:
    """Name the catalogue action that settles one wallet refusal, or None when none does."""
    if scenario_code in IVA_WALLET_OPENING_BALANCE_SCENARIOS:
        return IVA_WALLET_OPENING_BALANCE_ACTION_ID
    if scenario_code in IVA_WALLET_OVERRIDE_SCENARIOS:
        return IVA_WALLET_OVERRIDE_ACTION_ID
    return None


def _iva_wallet_profiles(
    subject_leaf_key: str,
    scenario_codes: tuple[str, ...],
) -> tuple[ManifestActionProfile, ...]:
    profiles: list[ManifestActionProfile] = []
    for scenario_code in scenario_codes:
        action_id = _iva_wallet_action_id(scenario_code)
        profiles.append(
            ManifestActionProfile(
                subject_leaf_key=subject_leaf_key,
                condition_id=f"{subject_leaf_key}.iva_wallet.ready",
                scenario_id=f"{subject_leaf_key}.iva_wallet.{scenario_code}",
                action=ActionReference(action_id=action_id) if action_id is not None else None,
                no_recovery_outcome=None if action_id is not None else NoRecoveryOutcome.OPERATOR_DECISION,
                alternative_actions=(),
            )
        )
    return tuple(profiles)


IVA_WALLET_REFUSAL_PROFILES: Final[tuple[ManifestActionProfile, ...]] = (
    *_iva_wallet_profiles("modelo.work.calculate", _IVA_WALLET_CALCULATE_SCENARIOS),
    *_iva_wallet_profiles("modelo.work.verify", _IVA_WALLET_REVISION_SCENARIOS),
    *_iva_wallet_profiles("modelo.work.file", _IVA_WALLET_REVISION_SCENARIOS),
    *_iva_wallet_profiles("modelo.export", _IVA_WALLET_REVISION_SCENARIOS),
)
"""The declared doors of every IVA wallet refusal, at each verb the wallet gate guards."""


__all__ = [
    "IVA_WALLET_OPENING_BALANCE_ACTION_ID",
    "IVA_WALLET_OPENING_BALANCE_SCENARIOS",
    "IVA_WALLET_OVERRIDE_ACTION_ID",
    "IVA_WALLET_OVERRIDE_SCENARIOS",
    "IVA_WALLET_REFUSAL_PROFILES",
]
