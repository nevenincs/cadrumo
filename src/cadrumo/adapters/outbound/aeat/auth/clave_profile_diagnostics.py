"""Redacted profile context and identity alignment for Cl@ve authentication diagnostics."""

from __future__ import annotations

from .....core.identity.tax_id import same_tax_identifier
from .clave_movil_support import diagnostic_fingerprint


def active_profile_context_defaults(
    bucket_id: str | None,
    *,
    profile_label_present: bool,
    profile_registered: bool,
) -> dict[str, object]:
    """Build the redacted context shared by every profile-read outcome."""
    return {
        "active_profile_id": "",
        "active_profile_ref": diagnostic_fingerprint(bucket_id),
        "active_profile_label": "",
        "active_profile_label_present": profile_label_present,
        "active_profile_registered": profile_registered,
        "profile_record_present": False,
        "profile_tax_id_present": False,
        "profile_tax_id_fingerprint": "",
        "identity_alignment": "profile_tax_id_missing",
    }


def unavailable_active_profile_context() -> dict[str, object]:
    """Return the fail-closed context when profile diagnostics cannot be read."""
    return {
        "active_profile_id": "",
        "active_profile_ref": "",
        "active_profile_label": "",
        "active_profile_label_present": False,
        "active_profile_registered": False,
        "profile_record_present": False,
        "profile_tax_id_present": False,
        "profile_tax_id_fingerprint": "",
        "identity_alignment": "profile_context_unavailable",
    }


def profile_identity_alignment(provider_identity: str, profile_identity: str) -> str:
    """Classify the redacted provider/profile identity relationship."""
    if not provider_identity:
        return "clave_identity_missing"
    if not profile_identity:
        return "profile_tax_id_missing"
    if same_tax_identifier(profile_identity, provider_identity):
        return "matches"
    return "mismatch"
