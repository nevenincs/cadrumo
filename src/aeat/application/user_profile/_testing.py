"""Test conveniences over the canonical user-profile orchestration.

Wraps :func:`register_active_profile` with a curated set of required
schema-validated placeholder facts so unit tests can register a profile
in one call without reciting six placeholder values every time. An
explicit :class:`SecureObjectRepository` may be injected to bind the
helper to an in-process ephemeral store.

This is a TEST helper and lives in the canonical package because it
composes only canonical surfaces.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI as _PROVENANCE_SOURCE_MANUAL_CLI
from ...core.hashing import sha256_hex
from ...core.identity import nif_check_letter
from ...domain.deadlines._models import IVARegime
from ...domain.user_profile import ProfileAlreadyExistsError, UserProfileFact
from ..workflow._models import WorkflowState
from ._orchestration import register_active_profile, select_profile, set_active_fields


def _distinct_valid_nif(profile_id: str) -> str:
    """Return a valid Spanish NIF derived deterministically from ``profile_id``.

    ``ProfileRepository.create`` refuses two profiles that share a tax
    id, so a test registering several profiles needs a distinct — and
    checksum-valid — NIF per profile. The 8-digit body is a stable hash
    of ``profile_id``; the control letter is computed so the result
    passes the NIF checksum validator.
    """
    digest = sha256_hex(profile_id.encode("utf-8"))
    number = int(digest, 16) % 100_000_000
    return f"{number:08d}{nif_check_letter(number)}"


_REQUIRED_PLACEHOLDERS: Mapping[str, str] = {
    "identity.name": "Test Operator",
    "identity.surnames": "Test Operator",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": IVARegime.GENERAL,
    "provenance.source": _PROVENANCE_SOURCE_MANUAL_CLI,
    # A minimal profile declares a minimal taxpayer model: an autónomo
    # en estimación directa (a natural person with rendimientos de
    # actividades económicas). Modelo applicability is derived from this
    # three-axis model; without it the overview engine reports
    # "incomplete" rather than guessing. Tests needing a different
    # taxpayer shape (landlord, sociedad limitada, ...) pass overrides.
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "irpf.estimation_regime": "directa_normal",
}


def register_minimal_profile(
    state: WorkflowState,
    *,
    profile_id: str,
    display_name: str | None = None,
    overrides: Mapping[str, str] | None = None,
    secure_objects: SecureObjectRepository | None = None,
    enforce_unique_tax_id: bool = True,
) -> WorkflowState:
    """Register ``profile_id`` with the minimum required schema facts.

    Args:
        state: Current :class:`WorkflowState`.
        profile_id: Canonical profile identifier (also the bucket id).
        display_name: Operator-visible label. Defaults to ``profile_id``.
        overrides: Optional schema-path → string overrides applied on top
            of the placeholder facts (also accepts paths not in the
            required set; they merge in).
        secure_objects: Optional injected :class:`SecureObjectRepository`.
        enforce_unique_tax_id: When ``False``, skip the cross-bucket
            tax-id uniqueness scan. Use in per-bucket-storage test
            scenarios where each profile's encrypted record lives in its
            own SQLite file and opening a second bucket session to scan
            a previously-created profile is not possible within the
            current active session. Matches the CLI ``profile create``
            behaviour (which also passes ``enforce_unique_tax_id=False``).

    Returns:
        The state with the profile registered + activated and the
        ``profile.created`` / ``profile.selected`` workflow events
        appended.
    """
    merged: dict[str, str] = dict(_REQUIRED_PLACEHOLDERS)
    # Default the tax id to a profile-unique valid NIF so two
    # ``register_minimal_profile`` calls never collide on the
    # duplicate-tax-id refusal; an explicit override still wins.
    merged["identity.tax_id"] = _distinct_valid_nif(profile_id)
    if overrides:
        merged.update(overrides)
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value)
    try:
        return register_active_profile(
            state,
            profile_id=profile_id,
            display_name=display_name or profile_id,
            facts=facts,
            secure_objects=secure_objects,
            enforce_unique_tax_id=enforce_unique_tax_id,
        )
    except ProfileAlreadyExistsError:
        selected = select_profile(state, profile_id=profile_id, secure_objects=secure_objects)
        return set_active_fields(selected, facts, secure_objects=secure_objects)


__all__ = ["register_minimal_profile"]
