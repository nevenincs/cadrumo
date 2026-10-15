"""Operator explanations of the canonical local synchronization requirements."""

from __future__ import annotations

from ...core.i18n.render import tr

_REASON_KEYS = {
    "profile_tax_id_required": "auth.sync.requirement.profile_tax_id_required",
    "auth_method_required": "auth.sync.requirement.auth_method_required",
    "certificate_file_required": "auth.sync.requirement.certificate_file_required",
    "certificate_passphrase_required": "auth.sync.requirement.certificate_passphrase_required",
    "clave_identity_required": "auth.sync.requirement.clave_identity_required",
    "profile_identity_must_match": "auth.sync.requirement.profile_identity_must_match",
    "nie_support_required": "auth.sync.requirement.nie_support_required",
    "dni_validity_required": "auth.sync.requirement.dni_validity_required",
    "clave_password_required": "auth.sync.requirement.clave_password_required",
    "no_path_set": "auth.sync.requirement.certificate_file_required",
    "file_missing": "auth.sync.requirement.file_missing",
    "unreadable": "auth.sync.requirement.unreadable",
    "corrupt": "auth.sync.requirement.corrupt",
    "expired": "auth.sync.requirement.expired",
    "expiring": "auth.sync.requirement.expiring",
    "ok": "auth.sync.requirement.ok",
}


def sync_requirement_reason(reason: str) -> str:
    """Render a safe reason without interpreting it as a translation key."""
    key = _REASON_KEYS.get(reason)
    return tr(key) if key is not None else tr("auth.sync.requirement.unavailable")


__all__ = ["sync_requirement_reason"]
