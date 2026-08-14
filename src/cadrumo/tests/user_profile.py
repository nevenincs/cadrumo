"""Real capsule-backed profile setup shared by integration tests.

The application profile is a current encrypted capsule record selected by the
active-profile pointer.  This helper keeps the broad integration-test suite
on that contract: it writes a :class:`UserProfileRecord` through the
production capsule lifecycle, marks setup complete, and selects the resulting
bucket.  It does not build a parallel workflow-state profile aggregate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from ..application.user_profile import conditional_profile_missing_required
from ..application.user_profile._lifecycle import ProfileCapsuleLifecycle
from ..application.workflow import WorkflowState
from ..core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI as _PROVENANCE_SOURCE_MANUAL_CLI
from ..core.hashing import sha256_hex
from ..core.identity import nif_check_letter
from ..domain.deadlines import IVARegime
from ..domain.user_profile import (
    NUMERIC_PROFILE_FIELD_TYPES,
    ProfileFieldType,
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
)
from .profile_capsule import seed_test_profile_record

if TYPE_CHECKING:
    from ..domain.user_profile import ProfileFieldDefinition, ProfileSchemaDefinition


_PLACEHOLDER_TAX_ID = f"12345678{nif_check_letter(12345678)}"
_PLACEHOLDER_DATE = "1990-01-01"
_PLACEHOLDER_BOOLEAN = "false"


def schema_valid_placeholder(field: ProfileFieldDefinition) -> str:
    """Return a value admitted by ``field`` for an unrelated test axis."""
    if field.enum_values:
        return field.enum_values[0]
    if field.key == "tax_id":
        return _PLACEHOLDER_TAX_ID
    if field.type in NUMERIC_PROFILE_FIELD_TYPES:
        return _numeric_placeholder(field)
    if field.type is ProfileFieldType.DATE:
        return _PLACEHOLDER_DATE
    if field.type is ProfileFieldType.BOOLEAN:
        return _PLACEHOLDER_BOOLEAN
    return "placeholder"


def _numeric_placeholder(field: ProfileFieldDefinition) -> str:
    """Return an in-range numeric filler for ``field``."""
    if field.minimum is not None:
        return str(field.minimum)
    if field.maximum is not None and field.maximum < 1:
        return str(field.maximum)
    return "1"


def _distinct_valid_nif(profile_id: str) -> str:
    """Return a stable checksum-valid Spanish NIF for ``profile_id``."""
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
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
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
) -> WorkflowState:
    """Seed and select a complete profile record through the real capsule.

    ``WorkflowState`` no longer owns profile records.  The state argument is
    retained because callers use this function as a repository update
    callback; selection is written through the production pointer transaction
    and the record itself through the current session-bound capsule writer.
    """
    merged: dict[str, str] = dict(_REQUIRED_PLACEHOLDERS)
    merged["identity.tax_id"] = _distinct_valid_nif(profile_id)
    if overrides:
        merged.update(overrides)
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value)
    record = UserProfileRecord(
        profile_id=profile_id,
        facts=facts,
        setup_state=ProfileSetupState.COMPLETE,
    )
    seed_test_profile_record(
        record,
        label=display_name or f"profile-{profile_id}",
    )
    ProfileCapsuleLifecycle().select(profile_id)
    return state


def complete_conditional_facts(
    schema: ProfileSchemaDefinition,
    facts: Iterable[UserProfileFact],
) -> tuple[UserProfileFact, ...]:
    """Append schema-required conditional facts until the set is complete."""
    completed = list(facts)
    fields = {f"{section.key}.{field.key}": field for section in schema.sections for field in section.fields}
    for _ in range(len(fields) + 1):
        values = {fact.path: fact.value for fact in completed if fact.value is not None}
        missing = tuple(path for path in conditional_profile_missing_required(values) if path in fields)
        if not missing:
            break
        completed.extend(UserProfileFact(path=path, value=schema_valid_placeholder(fields[path])) for path in missing)
    return tuple(completed)


__all__ = ["complete_conditional_facts", "register_minimal_profile", "schema_valid_placeholder"]
