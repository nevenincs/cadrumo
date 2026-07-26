"""Real user-profile orchestration support shared by tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ..application.user_profile import register_active_profile, select_profile, set_active_fields
from ..application.workflow import WorkflowState
from ..core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI as _PROVENANCE_SOURCE_MANUAL_CLI
from ..core.hashing import sha256_hex
from ..core.identity import nif_check_letter
from ..domain.deadlines import IVARegime
from ..domain.user_profile import ProfileAlreadyExistsError, UserProfileFact

if TYPE_CHECKING:
    from ..adapters.persistence.storage import SecureObjectRepository
    from ..domain.user_profile import ProfileFieldDefinition


def schema_valid_placeholder(field: ProfileFieldDefinition) -> str:
    """Return filler for one field that the field's own schema admits.

    A test building a profile needs SOME value in every field it is not
    testing, and for a long time one sentinel served every field because
    the schema's declared value sets constrained nothing. They constrain
    now, so a sentinel in an enum field asserts a profile that cannot
    exist - and every test using it then fails for a reason unrelated to
    what it was testing.

    The value is derived from the field definition rather than looked up
    in a table keyed by path. A table is a second statement of what the
    schema already says, and nothing makes the two agree: it goes stale
    the moment a field's declared set changes, and stale in the one
    direction that produces an unreachable profile again.

    Declared order is deliberate. Taking the first keeps the choice
    reproducible and makes it plain that the value means nothing beyond
    being legal - a test that needs a PARTICULAR value should say so
    rather than depend on which one happens to be first.

    Args:
        field: The schema definition of the field being filled.

    Returns:
        A value the field's declaration admits.
    """
    if field.enum_values:
        return field.enum_values[0]
    return "placeholder"


def _distinct_valid_nif(profile_id: str) -> str:
    """Return a stable, checksum-valid Spanish NIF for ``profile_id``."""
    digest = sha256_hex(profile_id.encode("utf-8"))
    number = int(digest, 16) % 100_000_000
    return f"{number:08d}{nif_check_letter(number)}"


_REQUIRED_PLACEHOLDERS: Mapping[str, str] = {
    "identity.name": "Test Operator",
    "identity.surnames": "Test Operator",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "activities.description": "economic activity",
    "iva.regime": IVARegime.GENERAL,
    "provenance.source": _PROVENANCE_SOURCE_MANUAL_CLI,
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
    """Register and activate a schema-valid minimal test profile."""
    merged: dict[str, str] = dict(_REQUIRED_PLACEHOLDERS)
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


__all__ = ["register_minimal_profile", "schema_valid_placeholder"]
