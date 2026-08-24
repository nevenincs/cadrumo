"""Real capsule-backed profile setup shared by integration tests.

The application profile is a current encrypted capsule record selected by the
active-profile pointer.  This helper keeps the broad integration-test suite
on that contract: it writes a :class:`UserProfileRecord` through the
production capsule lifecycle, marks setup complete, and selects the resulting
bucket.  It does not build a parallel workflow-state profile aggregate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from ..application.user_profile import (
    COMPLETENESS_ISSUE_CODES,
    ProfileCapsuleLifecycle,
    ProfileValidationService,
    conditional_profile_missing_required,
)
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

#: Identity handed to the validator purely to read back its completeness
#: report. Nothing is persisted under it.
_COMPLETENESS_PROBE_PROFILE_ID = "00000000-0000-4000-8000-000000000000"
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
    *,
    profile_id: str | UUID,
    display_name: str | None = None,
    overrides: Mapping[str, str] | None = None,
    record_empty_legal_hold: bool = False,
) -> UserProfileRecord:
    """Publish a complete profile capsule, and select it, before any bucket read.

    This is the single seeding door for tests that need a real profile.  Call it
    before touching workflow state, a bucket database, or anything else scoped
    to the profile: a capsule is published by an atomic no-replace rename onto
    ``buckets/<profile-id>``, and opening a bucket database engine for a profile
    whose capsule is not yet published is refused outright by the storage layer.
    Seeding first is therefore a precondition of the bucket existing at all, not
    a style preference.

    The state argument this once took was vestigial -- it was handed straight
    back so the function could be passed as a workflow-repository update
    callback, and that callback shape was exactly what inverted the order and
    made every caller read workflow state before the capsule existed.  Taking no
    state removes the trap rather than documenting it, and the seeded record is
    returned because that is what the function actually produces.

    The empty filing catalogue snapshot is recorded here through the same
    recorder production registration uses, because publishing a capsule is only
    half of what being born as a profile means.  A real profile carries the
    recorded fact that its filing owner was asked and had nothing to report; a
    profile seeded without it is indistinguishable from one nobody ever asked,
    and the retention assessment refuses on that absence -- so every deletion
    preflight against a seeded profile failed for a reason unrelated to the
    test's subject.  Recording an EMPTY snapshot asserts nothing stronger than
    the truth about a freshly seeded profile: no filings exist.

    The legal-hold snapshot is NOT recorded here by default, and that is a
    ruling rather than an omission: production registration records no such
    fact -- the legal-case owner has no creation-time writer anywhere in the
    tree, only a projection an operator must someday feed. An absent legal-hold
    snapshot means nobody has been asked, not that no case is open, so a
    profile seeded through this door is left exactly as production leaves it:
    unable to pass a custody-transaction deletion preflight until something
    records that fact. Pass ``record_empty_legal_hold=True`` when a test's
    subject needs a profile that a custody-transaction deletion preflight (the
    one join of the legal and filing owners, distinct from the filing-only
    retention floor above) will actually accept -- it records the same "asked
    and had nothing to report" fact for the legal owner that this door already
    records for the filing owner, through the same production recorder. It
    stays opt-in because unconditionally recording it would make every seeded
    profile deletable regardless of the fact this campaign ruled must be
    supplied by a human, silently erasing the fail-closed gap production still
    has.
    """
    from uuid import UUID

    from ..application.evidence import LegalHoldCaseAuthority
    from ..application.filing import try_record_filing_retention_snapshot
    from ..core.identity import canonical_profile_bucket_id

    # Normalise at the door: the record below constrains its identifier to the
    # canonical UUIDv4 string, so a readable identifier must fail here with one
    # instructive refusal rather than deep inside record construction.
    profile_id = canonical_profile_bucket_id(profile_id)
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
    seeded = seed_test_profile_record(
        record,
        label=display_name or f"profile-{profile_id}",
    )
    try_record_filing_retention_snapshot(
        bucket_id=profile_id,
        records=(),
        observed_at=datetime.now(UTC),
    )
    if record_empty_legal_hold:
        LegalHoldCaseAuthority().record_open_case_snapshot(
            profile_id=UUID(profile_id),
            open_case_ids=(),
            observed_at=datetime.now(UTC),
        )
    ProfileCapsuleLifecycle().select(profile_id)
    return seeded


def register_cli_profile(*, label: str, facts: Mapping[str, str] | None = None, complete: bool = True) -> str:
    """Register a profile a CLI-surface test can afterwards use, and return its id.

    The sibling :func:`register_minimal_profile` seeds a complete record for
    application-layer tests.  A CLI test needs something that door does not
    provide: the custody envelope has to open under the passphrase the isolated
    CLI backend configures, so every ``aeat`` invocation that follows can unlock
    the profile.  Seeding a record writes no such envelope, which is why the two
    doors are not interchangeable and why this one exists.

    Three steps, because the retired scripted-creation flag did all three.  The
    required placeholders are applied first and the caller's ``facts`` win over
    them, so a test that only cares about a tax id need not restate the regimes
    a readiness gate demands.  The profile is then logged in: registration
    closes its own session, so a freshly registered profile is LOCKED, and every
    later bucket read needs an unlocked session rather than a repair.  Setup is
    completed last, through the production compare-and-swap, because the
    credential door leaves a profile incomplete on purpose and a readiness gate
    refuses an incomplete profile before any modelo work.

    A distinct valid tax id is derived from the label, as the sibling seeding
    door derives one from the profile id: a profile with no tax id fails schema
    validation, so a door that omitted it would hand every caller an invalid
    profile unless they happened to supply one.

    Pass ``complete=False`` for a test whose subject is the incomplete state.
    """
    from uuid import UUID as _UUID

    from ..application.user_profile import login_profile, register_profile_with_credentials
    from ..core.config import load_settings, override_settings
    from .profile_capsule import bound_test_profile_record

    merged: dict[str, str] = dict(_REQUIRED_PLACEHOLDERS)
    merged["identity.tax_id"] = _distinct_valid_nif(label)
    if facts:
        merged.update(facts)
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    # Registration calibrates the profile KDF by MEASURING the parameter grid on
    # this host: one supervised child per warmup and per sample, 16.1s of the
    # 19.1s a registration costs here. `calibrate_profile_kdf` already documents
    # that measuring is "the right price for an operator's one-off enrolment and
    # the wrong one for a host that enrols constantly", which is exactly what a
    # test suite is -- this door has 156 call sites across 62 modules.
    #
    # Declining to measure adopts the FIXED fallback point, which that function
    # also returns whenever the grid cannot be measured before its deadline, and
    # which is stronger than the measured band's floor. So the custody envelope
    # every caller then opens is wrapped no more weakly than before; only the
    # host measurement is skipped. `secure_sql` already takes this seam for the
    # same reason.
    #
    # The calibration behaviour itself is proven by
    # `custody/tests/test_kdf_supervision.py`, which drives
    # `calibrate_profile_kdf` directly and never comes through this door, so
    # nothing here can hide a calibration regression.
    with override_settings(cadrumo_profile_kdf_measure_calibration=False):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=label,
            passphrase=passphrase,
            facts=tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value),
        )
    login_profile(name=label, passphrase_callback=lambda: passphrase)
    if complete:
        identity = _UUID(outcome.profile_id)
        with bound_test_profile_record(identity) as repository:
            current = repository.load(identity)
            repository.complete_setup(
                identity,
                expected_revision=current.record_revision,
                expected_content_digest=current.content_digest,
            )
    return outcome.profile_id


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


def complete_profile_facts(
    schema: ProfileSchemaDefinition,
    facts: Iterable[UserProfileFact] = (),
) -> tuple[UserProfileFact, ...]:
    """Return ``facts`` extended until the schema reports nothing required missing.

    Built by asking the validation service what it still considers missing and
    filling exactly that, repeatedly, rather than from a hand-listed set. A
    literal list of required paths is a second authority for the schema's own
    required flags: the moment the schema gains one, every profile assembled
    from the literal is quietly short of complete while still calling itself
    so, which is the failure this helper exists to keep out of tests about
    completeness.

    Unconditional and conditional requirements are filled together because
    answering one can open the other -- declaring an IVA regime opens a block
    of regime-conditional fields -- so a single pass would stop short.

    Args:
        schema: The loaded profile schema whose requirements are satisfied.
        facts: Optional facts to start from; their values are preserved.
    """
    service = ProfileValidationService(schema=schema)
    completed = list(facts)
    fields = {f"{section.key}.{field.key}": field for section in schema.sections for field in section.fields}
    for _ in range(len(fields) + 1):
        report = service.validate_facts(_COMPLETENESS_PROBE_PROFILE_ID, completed)
        missing = tuple(
            issue.path for issue in report.issues if issue.code in COMPLETENESS_ISSUE_CODES and issue.path in fields
        )
        if not missing:
            return tuple(completed)
        completed.extend(UserProfileFact(path=path, value=schema_valid_placeholder(fields[path])) for path in missing)
    raise RuntimeError("profile completeness did not converge; a required field is unfillable")


__all__ = [
    "complete_conditional_facts",
    "complete_profile_facts",
    "register_cli_profile",
    "register_minimal_profile",
    "schema_valid_placeholder",
]
