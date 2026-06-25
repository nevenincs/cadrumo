"""Encrypted-SQL persistence-boundary roundtrip for the refund-account facts.

The Modelo 303 cuenta-devolución refund account AEAT pays a refund into
is SENSITIVE FINANCIAL IDENTITY DATA: per the
``sensitive-financial-data-secure-storage-only`` invariant the IBAN,
SWIFT-BIC, and foreign-bank block persist ONLY in the encrypted
secure-object store (``sensitivity="financial"`` on the profile schema),
are read transiently into memory at export, and are NEVER written to
plaintext, logs, or a side store.

This file locks the secure-storage boundary for those new financial
fields with the discipline ``aeat-roundtrip-discipline`` mandates:

- A populated roundtrip: every refund-account fact at a NON-DEFAULT
  value survives a real encrypted save/load cycle with strict pydantic
  equality on the full :class:`UserProfileRecord`, plus per-fact
  witnesses.
- An anti-tautology proof: a surgical on-disk mutation that corrupts
  the persisted IBAN fact, reloaded through the real decrypt/parse
  pipeline, surfaces strict inequality — proving the load side genuinely
  reads the persisted IBAN rather than re-deriving the save-side value.
- The :class:`RefundAccount` domain-model IBAN field validator rejects a
  malformed IBAN at the boundary (ISO 13616 shape + mod-97), so a
  malformed account is refused on input rather than at fichero-write
  time, and accepts a known-valid IBAN canonicalised.

Real adapters only — a real runtime profile and a real
:class:`SecureObjectRepository`. The test exercises
:class:`UserProfileLifecycleRepository` directly because it is the
canonical user-profile encrypted boundary.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import SensitivityClass
from ....domain.deadlines import RefundAccount
from ....domain.deadlines._errors import DeadlineValidationError
from ....domain.user_profile import (
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._repository import (
    USER_PROFILE_VALUE_NAMESPACE,
    UserProfileLifecycleRepository,
    user_profile_value_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "refund-account-roundtrip"
_PROFILE_UUID = "3f1c8d2a-7b4e-4a6c-8d9f-1e2a3b4c5d6e"

# A real, mod-97-valid Spanish IBAN (the canonical ISO 13616 form). Used
# both as the persisted refund-account fact and as the known-valid input
# to the RefundAccount IBAN validator.
_IBAN_VALUE = "ES9121000418450200051332"

# Every refund-account fact carries a NON-DEFAULT value so a
# save-drops-field / load-re-defaults-field regression surfaces as
# inequality. The values model a non-SEPA (Resto Países) refund account
# so the full foreign-bank block is exercised.
#
# ``sepa_marca`` is intentionally NOT a persisted operator fact: per the
# ADR it is DERIVED at export from the account country (España / UE SEPA
# / Resto Países), not entered or stored. Its schema field carries only
# the DID export-header mapping the P02 composer writes into. Persisting
# it here is therefore out of scope; the stored set is the genuine
# operator-supplied refund-account data.
_REFUND_ACCOUNT_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="filing_export.iban", value=_IBAN_VALUE, source="manual_cli"),
    UserProfileFact(path="filing_export.swift_bic", value="CHASUS33XXX", source="manual_cli"),
    UserProfileFact(path="filing_export.bank_name", value="J.P. Morgan Chase Bank", source="manual_cli"),
    UserProfileFact(path="filing_export.bank_address", value="383 Madison Avenue", source="manual_cli"),
    UserProfileFact(path="filing_export.bank_city", value="New York", source="manual_cli"),
    UserProfileFact(path="filing_export.bank_country_code", value="US", source="manual_cli"),
)


def _populated_record() -> UserProfileRecord:
    """A UserProfileRecord populated with the refund-account facts.

    Every defaultable lifecycle field carries a non-default value so a
    save-drops-field / load-re-defaults-field regression surfaces as
    inequality.
    """

    created = datetime(2024, 2, 1, 8, 30, 0, tzinfo=UTC)
    updated = datetime(2024, 7, 9, 11, 15, 42, tzinfo=UTC)
    return UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=2,
        profile_id=_PROFILE_UUID,
        display_name="IVA refund operator (cuenta-devolución roundtrip)",
        status=UserProfileStatus.ACTIVE,
        facts=_REFUND_ACCOUNT_FACTS,
        created_at=created,
        updated_at=updated,
    )


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label="Refund account roundtrip",
    ) as profile:
        yield profile


@pytest.fixture
def lifecycle(runtime_profile: TestRuntimeProfile) -> UserProfileLifecycleRepository:
    """A real lifecycle repository over a real runtime profile."""

    return UserProfileLifecycleRepository(
        bucket_id=_BUCKET_ID,
        objects=runtime_profile.repository,
    )


def _fact_value(record: UserProfileRecord, path: str) -> object:
    matches = [fact.value for fact in record.facts if fact.path == path]
    assert len(matches) == 1, f"expected exactly one fact at {path!r}, found {len(matches)}"
    return matches[0]


def test_refund_account_facts_survive_encrypted_sql_roundtrip(
    lifecycle: UserProfileLifecycleRepository,
) -> None:
    """Every refund-account financial fact survives the real encrypted-SQL cycle.

    Persists a populated :class:`UserProfileRecord` carrying the IBAN,
    SWIFT-BIC, and the full foreign-bank block at non-default values,
    reloads it through the real encrypted boundary, and asserts strict
    pydantic equality on the full record plus per-fact witnesses for
    every refund-account field. A save-drops / load-re-defaults
    regression on any of the seven financial fields would surface here.
    """

    original = _populated_record()
    lifecycle.save(original)
    loaded = lifecycle.load(original.profile_id)

    # Strict pydantic equality across the full lifecycle record.
    assert loaded == original

    # Per-fact witnesses: every refund-account financial field survives
    # the encrypted boundary with its exact persisted string value.
    assert _fact_value(loaded, "filing_export.iban") == _IBAN_VALUE
    assert _fact_value(loaded, "filing_export.swift_bic") == "CHASUS33XXX"
    assert _fact_value(loaded, "filing_export.bank_name") == "J.P. Morgan Chase Bank"
    assert _fact_value(loaded, "filing_export.bank_address") == "383 Madison Avenue"
    assert _fact_value(loaded, "filing_export.bank_city") == "New York"
    assert _fact_value(loaded, "filing_export.bank_country_code") == "US"


def test_corrupting_the_persisted_iban_surfaces_on_reload(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Anti-tautology proof: a corrupted on-disk IBAN surfaces as inequality.

    The pattern follows ``aeat-roundtrip-discipline``: save a populated
    record through the real encrypted boundary, surgically mutate the
    JSON envelope to corrupt the persisted IBAN fact value, reload
    through the real decrypt/parse pipeline, and assert the reloaded
    IBAN no longer equals the originally-persisted value. If the load
    side still surfaced the original IBAN, the persistence boundary
    would be tautological — the save side would be carrying the value
    through a path the load side does not actually depend on.
    """

    lifecycle = UserProfileLifecycleRepository(
        bucket_id=_BUCKET_ID,
        objects=runtime_profile.repository,
    )

    original = _populated_record()
    lifecycle.save(original)

    # Sanity: the populated record carries the IBAN fact before the
    # persisted mutation. A reload that fails this assertion means the
    # save path is the regression, not the load path.
    pre_mutation = lifecycle.load(original.profile_id)
    assert _fact_value(pre_mutation, "filing_export.iban") == _IBAN_VALUE

    stored = runtime_profile.repository.load(
        USER_PROFILE_VALUE_NAMESPACE,
        user_profile_value_object_key(original.profile_id),
        expected_class=SensitivityClass.IDENTITY,
        max_supported_version=1,
    )
    assert stored is not None
    envelope = json.loads(stored.payload.decode("utf-8"))
    payload = envelope["payload"]

    corrupted_iban = "ES0000000000000000000000"
    mutated_count = 0
    for fact in payload["facts"]:
        if fact.get("path") == "filing_export.iban":
            fact["value"] = corrupted_iban
            mutated_count += 1
    assert mutated_count == 1, (
        "fixture must persist exactly one IBAN fact for this anti-tautology proof to be meaningful"
    )

    runtime_profile.repository.save(
        namespace=stored.namespace,
        object_key=user_profile_value_object_key(original.profile_id),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    reloaded = lifecycle.load(original.profile_id)

    # Strict inequality: the load side reads the corrupted on-disk IBAN,
    # so the reloaded fact value is the corruption, not the original.
    assert _fact_value(reloaded, "filing_export.iban") == corrupted_iban
    assert _fact_value(reloaded, "filing_export.iban") != _IBAN_VALUE

    # The full-record equality also breaks — the reloaded record carries
    # the corrupted IBAN and is therefore != the in-memory original.
    assert reloaded != original


class TestRefundAccountIbanValidator:
    """The RefundAccount IBAN field validator gates the secure-storage boundary."""

    def test_valid_iban_accepted_and_canonicalised(self) -> None:
        """A known-valid IBAN is accepted and normalised to canonical form.

        Whitespace and hyphens are stripped and the value upper-cased so
        the persisted form is the canonical ISO 13616 string, regardless
        of operator-entry punctuation.
        """
        account = RefundAccount(iban="es91 2100 0418 4502 0005 1332")
        assert account.iban == _IBAN_VALUE

    def test_none_iban_passes_through(self) -> None:
        """A ``None`` IBAN means no refund account on file and is accepted.

        The refusal of a refund disposition with no account is a P02
        export-time concern; the model itself permits an unset IBAN so a
        profile that has not configured a refund account is valid.
        """
        account = RefundAccount()
        assert account.iban is None

    def test_blank_iban_normalises_to_none(self) -> None:
        """An empty / whitespace IBAN normalises to ``None``, not a blank string."""
        account = RefundAccount(iban="   ")
        assert account.iban is None

    @pytest.mark.parametrize(
        "malformed",
        [
            "ES",  # too short for the ISO 13616 shape
            "ES91",  # no BBAN
            "1234567890",  # no country prefix
            "ES9121000418450200051333",  # wrong mod-97 checksum
            "ES9921000418450200051332",  # wrong check digits
            "ES9121000418450200051332EXTRA",  # too long
        ],
    )
    def test_malformed_iban_rejected_at_boundary(self, malformed: str) -> None:
        """A malformed IBAN is rejected on input, not deferred to fichero-write.

        Pydantic wraps the field validator's :class:`DeadlineValidationError`
        (a ``ValueError`` subclass) in a :class:`ValidationError`.
        """
        with pytest.raises(ValidationError):
            RefundAccount(iban=malformed)

    def test_validator_raises_deadline_validation_error_directly(self) -> None:
        """The underlying validator raises the typed domain error.

        Asserts the boundary error is the deadlines-domain
        :class:`DeadlineValidationError`, not a generic message, so the
        failure carries the domain's catchable root.
        """
        with pytest.raises(DeadlineValidationError, match="mod-97"):
            RefundAccount._validate_iban("ES9921000418450200051332")
