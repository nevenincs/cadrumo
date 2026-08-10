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
from ..domain.user_profile import (
    NUMERIC_PROFILE_FIELD_TYPES,
    ProfileAlreadyExistsError,
    ProfileFieldType,
    UserProfileFact,
)

if TYPE_CHECKING:
    from ..adapters.persistence.storage import SecureObjectRepository
    from ..domain.user_profile import ProfileFieldDefinition


#: Checksum-valid NIF filler, derived through the canonical check-letter table
#: rather than written out, so it cannot drift from the algorithm that admits it.
_PLACEHOLDER_TAX_ID = f"12345678{nif_check_letter(12345678)}"

#: Calendar-day filler for date fields, in the zero-padded layout the write door
#: requires. Fixed rather than derived from the clock: a filler that moves with
#: today's date makes every test using it non-reproducible, and a suite that
#: passes in one week and fails the next reports the calendar, not the code.
#: The particular day is arbitrary but not careless -- the date fields are mostly
#: birth, marriage, and activity-start dates, so a plausible adult birth year
#: avoids handing anything that later reads an age a taxpayer born last year.
_PLACEHOLDER_DATE = "1990-01-01"

#: Boolean filler. ``false`` rather than ``true`` for two reasons that agree.
#: It is the non-triggering answer -- these flags gate obligations and exemption
#: pathways, so a filler that says yes asserts an obligation the test never meant
#: to claim. And it preserves what the sentinel already meant: every reader of a
#: boolean fact treats an unrecognised token as false, so filling with ``false``
#: changes no consumer's answer while making the stored value honestly a boolean.
_PLACEHOLDER_BOOLEAN = "false"


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

    The tax-identifier field is the one case the field declaration cannot
    answer on its own. Its profile-schema type is a plain ``string``, but the
    projection into ``TaxpayerProfile`` runs the canonical ``SubjectTaxId``
    contract, so the AEAT checksum is a constraint the schema does not express
    and the generic sentinel cannot satisfy. It is keyed on the field key
    rather than added to a table of paths: one field whose downstream contract
    is stricter than its declared type, named where that is true.

    A date field takes a fixed calendar day. The write door enforces
    ``ProfileFieldType.DATE`` as narrowly as it enforces an enum's declared
    set -- a date-typed fact must carry a real ISO-8601 day in the
    zero-padded ``YYYY-MM-DD`` layout -- so the sentinel is refused there
    exactly as it is in an enum field. Unlike the numeric branch there is
    nothing to derive: the schema permits bounds only on numeric fields, so a
    date field declares no range to honour and a constant is the whole answer.

    A boolean field takes a boolean token, and this is the branch the door
    does NOT force. Nothing refuses the sentinel on a boolean fact, so the
    cost of omitting this branch is not a visible refusal but a quiet wrong
    answer: the fact carrier leaves an unrecognised token a ``str`` instead
    of promoting it to a ``bool``, and every consumer asking whether the flag
    is set reads it as false. The branch exists because "the declaration
    admits it" is a claim about the declaration, not about which mistakes
    happen to be caught.

    Args:
        field: The schema definition of the field being filled.

    Returns:
        A value the field's declaration admits.
    """
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
    """Return a number this numeric field's declaration admits.

    The sentinel is not one: a numeric field now refuses the word
    ``placeholder`` the same way an enum field refuses it, so the branch
    that made enums legal has to exist for numbers too.

    The declared bounds are honoured rather than sidestepped, because the
    value has to satisfy the very check this exists to keep tests clear of.
    The minimum is preferred when one is declared -- it is admissible by
    definition and needs no arithmetic -- and the fallbacks stay inside a
    declared ceiling. As with the enum branch, the value means nothing
    beyond being legal; a test needing a PARTICULAR number should say so.
    """
    if field.minimum is not None:
        return str(field.minimum)
    if field.maximum is not None and field.maximum < 1:
        return str(field.maximum)
    return "1"


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
            # Derived, never the bare id. ProfileLabel refuses a UUID-shaped
            # label so an operator label can never be read as a machine
            # identity, and test profile ids are UUIDs — so falling back to the
            # id made this one helper the single root cause of that refusal
            # across every suite that registers a profile.
            display_name=display_name or f"profile-{profile_id}",
            facts=facts,
            secure_objects=secure_objects,
            enforce_unique_tax_id=enforce_unique_tax_id,
        )
    except ProfileAlreadyExistsError:
        selected = select_profile(state, profile_id=profile_id, secure_objects=secure_objects)
        return set_active_fields(selected, facts, secure_objects=secure_objects)


__all__ = ["register_minimal_profile", "schema_valid_placeholder"]
