"""The manager lists every field the taxpayer projection will demand.

Declaring one IVA fact claims the whole IVA block, and the projection then
refuses until the rest of that block is answered. The Profile overview once
reported only schema-required fields, so an operator who set ``iva.regime``
saw nothing outstanding while every surface that projected the profile
refused it one field at a time.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ..overview import build_profile_overview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "22222222-2222-4222-8222-222222222222"
_IVA_BLOCK_OWED = (
    "iva.m303_regime_composition",
    "tax_residence.jurisdiction_scope",
    "iva.redeme_enrolled",
    "iva.cash_accounting_regime_enrolled",
    "iva.voluntary_sii_enrolled",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
)


def _overview(facts: tuple[UserProfileFact, ...]):
    with bundled_indexed_authority().operation() as operation:
        record = create_user_profile_record(
            context=operation.profile_create_context(),
            profile_id=_PROFILE_ID,
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=facts,
        )
        return build_profile_overview(record, label="Perfil", schema=operation.profile_schema())


def test_a_claimed_iva_block_lists_every_path_it_owes() -> None:
    """DISCRIMINATING: the paths the projection refuses without are reported missing."""
    overview = _overview((UserProfileFact(path="iva.regime", value="GENERAL"),))

    assert set(_IVA_BLOCK_OWED) <= set(overview.missing_required)
    rows = {field.path: field for section in overview.sections for field in section.fields}
    assert all(rows[path].required for path in _IVA_BLOCK_OWED)


def test_an_unclaimed_iva_block_owes_nothing() -> None:
    """ANTI-VACUITY: a profile with no IVA fact is not asked for the IVA block."""
    overview = _overview(())

    # ``tax_residence.jurisdiction_scope`` is schema-required on every profile,
    # so only the paths the IVA block alone obliges can show the difference.
    iva_only = {path for path in _IVA_BLOCK_OWED if path.startswith("iva.")}
    assert not iva_only & set(overview.missing_required)
    rows = {field.path: field for section in overview.sections for field in section.fields}
    assert not rows["iva.redeme_enrolled"].required
