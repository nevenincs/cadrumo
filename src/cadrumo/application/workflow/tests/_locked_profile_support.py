"""Shared capsule publisher for the locked-profile health proofs.

The locked state exists only where no process has authenticated, so the
capsule under test must be published by an interpreter that has since exited:
a publisher running inside the reading process leaves a live record authority
latched and the reader then sees an unlocked profile, which is the one
configuration in which the defect cannot appear.

This lives in a support module rather than inside a test module because the
CHILD interpreter imports it by name through ``python -c``; nothing here may
depend on a pytest fixture or on an already-running test session.
"""

from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from uuid import UUID

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
)
from ....core.bucket_pointer import BucketPointer, write_pointer
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import mint_test_profile_recovery_envelope

PROFILE_ID = "31313131-3131-4313-8313-313131313131"
PROFILE_LABEL = "Operator"
DEK = bytes(range(32))
RECORD_NAMESPACE = "cadrumo.application.user_profile.value"

READY_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def build_envelope() -> ProfileCustodyEnvelope:
    """Return the deterministic password envelope both processes agree on."""
    identity = UUID(PROFILE_ID)
    seed = identity.bytes + identity.bytes
    return ProfileCustodyEnvelope.create(
        profile_id=identity,
        password_generation=1,
        dek_epoch=b64encode(seed[:16]).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(seed[16:]).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(seed[:12]).decode("ascii"),
            ciphertext_b64=b64encode(seed).decode("ascii"),
            tag_b64=b64encode(seed[:16]).decode("ascii"),
        ),
    )


def publish_capsule_and_pointer(root: Path) -> None:
    """Publish one complete capsule at *root* and point the active selector at it."""
    from ...user_profile import ProfileCapsuleLifecycle, ProfileRecordSession

    envelope = build_envelope()
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=DEK)
    try:
        ProfileCapsuleLifecycle(root=root).create(
            label=PROFILE_LABEL,
            profile_id=UUID(PROFILE_ID),
            password_envelope=envelope,
            sentinel=create_profile_custody_sentinel(envelope=envelope, dek=DEK),
            data_files={},
            recovery_envelope=mint_test_profile_recovery_envelope(
                UUID(PROFILE_ID), dek=DEK, dek_epoch=envelope.dek_epoch
            ),
            initial_record=UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE, profile_id=PROFILE_ID, facts=READY_FACTS
            ),
            record_session=session,
        )
    finally:
        session.close()
    write_pointer(root, BucketPointer.selected(bucket_id=PROFILE_ID, transition_revision=1))


__all__ = [
    "DEK",
    "PROFILE_ID",
    "PROFILE_LABEL",
    "READY_FACTS",
    "RECORD_NAMESPACE",
    "build_envelope",
    "publish_capsule_and_pointer",
]
