"""Durable auth intents bind identity, ownership, and instant contracts.

Three boundaries on the same persisted records were declared loosely:

- ``operation_id`` was bounded only by length, while every producer derives it
  as ``hashlib.sha256(...).hexdigest()``. An uppercase or non-hex value was
  therefore accepted although no producer can emit one, and a resume path
  keyed on that identity could never match the operation it was continuing.
- ``bucket_id`` was a bare ``str`` rather than the canonical
  :data:`~core.identity.BucketId`, so it inherited neither the whitespace
  normalisation nor the upper bound the rest of the codebase relies on.
- Every timestamp documented UTC and enforced nothing.

These records persist as JSON, which preserves the UTC offset, so the
canonical instant contract is enforceable here. That is not true of the
SQL-column-backed records elsewhere, where SQLite drops the offset on read.

Each refusal is paired with the valid value it rejects, so a test that starts
refusing everything is distinguishable from one that refuses the right thing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ..auth.models import (
    AuthCleanupCertificateSource,
    AuthCleanupIntent,
    AuthCleanupOperationKind,
    AuthState,
    CertificateSecretMutationEventKind,
    CertificateSecretMutationIntent,
    CertificateSourceRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HEX64 = "a" * 64
_AWARE = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)
_NAIVE = datetime(2026, 4, 1, 10, 30)
_OFFSET = datetime(2026, 4, 1, 10, 30, tzinfo=timezone(timedelta(hours=1)))


def _cleanup(**overrides: object) -> AuthCleanupIntent:
    fields: dict[str, object] = {
        "operation_id": _HEX64,
        "operation_kind": AuthCleanupOperationKind.LOGOUT,
        "bucket_id": "bucket-one",
        "provider_ids": (),
        "all_providers": False,
        "started_at": _AWARE,
    }
    fields.update(overrides)
    return AuthCleanupIntent.model_validate(fields)


def _mutation(**overrides: object) -> CertificateSecretMutationIntent:
    fields: dict[str, object] = {
        "operation_id": _HEX64,
        "bucket_id": "bucket-one",
        "source_name": "primary",
        "event_kind": CertificateSecretMutationEventKind.SET,
        "started_at": _AWARE,
        "prior_present": False,
    }
    fields.update(overrides)
    return CertificateSecretMutationIntent.model_validate(fields)


class TestOperationIdentity:
    """``operation_id`` accepts exactly the shape producers emit."""

    def test_producer_shaped_identity_is_accepted(self) -> None:
        assert _cleanup().operation_id == _HEX64
        assert _mutation().operation_id == _HEX64

    @pytest.mark.parametrize("bad", ["A" * 64, "z" * 64, "a" * 63, "a" * 65, ""])
    def test_unproducible_identity_is_refused(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            _cleanup(operation_id=bad)

    def test_mutation_intent_binds_the_same_identity_contract(self) -> None:
        with pytest.raises(ValidationError):
            _mutation(operation_id="A" * 64)


class TestBucketOwnership:
    """``bucket_id`` carries the canonical ownership contract."""

    def test_valid_bucket_is_accepted(self) -> None:
        assert _cleanup().bucket_id == "bucket-one"

    @pytest.mark.parametrize("bad", ["", "   ", "b" * 129])
    def test_out_of_contract_bucket_is_refused(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            _cleanup(bucket_id=bad)

    def test_surrounding_whitespace_is_normalised(self) -> None:
        """The canonical alias strips, where the bare ``str`` preserved."""
        assert _cleanup(bucket_id="  bucket-one  ").bucket_id == "bucket-one"


class TestInstantContracts:
    """Every populated timestamp is UTC-aware."""

    def test_aware_utc_is_accepted(self) -> None:
        assert _cleanup().started_at == _AWARE

    @pytest.mark.parametrize("bad", [_NAIVE, _OFFSET])
    def test_cleanup_start_rejects_naive_and_offset(self, bad: datetime) -> None:
        with pytest.raises(ValidationError):
            _cleanup(started_at=bad)

    @pytest.mark.parametrize("field", ["configured_at_at_start", "authenticated_at_at_start"])
    def test_optional_intent_instants_are_gated_when_present(self, field: str) -> None:
        assert getattr(_cleanup(**{field: _AWARE}), field) == _AWARE
        with pytest.raises(ValidationError):
            _cleanup(**{field: _NAIVE})

    def test_absent_optional_instant_stays_permitted(self) -> None:
        """The gate must not turn an optional field into a required one."""
        assert _cleanup().configured_at_at_start is None

    def test_mutation_start_rejects_naive(self) -> None:
        with pytest.raises(ValidationError):
            _mutation(started_at=_NAIVE)

    def test_certificate_source_registration_rejects_naive(self) -> None:
        assert CertificateSourceRecord(name="n", certificate_path="p", registered_at=_AWARE).registered_at == _AWARE
        with pytest.raises(ValidationError):
            CertificateSourceRecord(name="n", certificate_path="p", registered_at=_NAIVE)

    @pytest.mark.parametrize("field", ["configured_at", "authenticated_at"])
    def test_auth_state_instants_are_gated(self, field: str) -> None:
        assert getattr(AuthState.model_validate({field: _AWARE}), field) == _AWARE
        with pytest.raises(ValidationError):
            AuthState.model_validate({field: _NAIVE})

    def test_empty_auth_state_remains_valid(self) -> None:
        """A state carrying no instants is still constructible."""
        assert AuthState().configured_at is None


class TestCertificateSourceName:
    """One nominal certificate source has exactly one persisted spelling.

    The name is the natural key of three surfaces — the registry dict, the
    active selector, and the secret-store key — each of which used to strip
    for itself. A record persisted as ``" personal "`` therefore kept its
    padding in durable state while the secret backend filed the passphrase
    under ``"personal"``, and exact-dict selection could not resolve the
    padded record from the canonical selector.
    """

    _PADDED = "  personal  "
    _CANONICAL = "personal"

    def test_registered_record_stores_the_canonical_spelling(self) -> None:
        record = CertificateSourceRecord(
            name=self._PADDED,
            certificate_path="p",
            registered_at=_AWARE,
        )
        assert record.name == self._CANONICAL

    def test_blank_after_strip_is_refused(self) -> None:
        """A whitespace-only name is not a name; it must not reach durable state."""
        for blank in ("", "   ", "\t\n"):
            with pytest.raises(ValidationError):
                CertificateSourceRecord(name=blank, certificate_path="p", registered_at=_AWARE)

    def test_overlength_name_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            CertificateSourceRecord(name="x" * 161, certificate_path="p", registered_at=_AWARE)
        assert CertificateSourceRecord(name="x" * 160, certificate_path="p", registered_at=_AWARE).name == "x" * 160

    def test_cleanup_witness_carries_the_same_contract(self) -> None:
        witness = AuthCleanupCertificateSource(name=self._PADDED, registered_at=_AWARE)
        assert witness.name == self._CANONICAL
        with pytest.raises(ValidationError):
            AuthCleanupCertificateSource(name="   ", registered_at=_AWARE)

    def test_secret_mutation_intent_carries_the_same_contract(self) -> None:
        assert _mutation(source_name=self._PADDED).source_name == self._CANONICAL
        with pytest.raises(ValidationError):
            _mutation(source_name="   ")

    def test_active_selector_is_canonical_so_dict_lookup_resolves(self) -> None:
        """The selector and the registry key must be the same string.

        ``active_certificate_source`` is resolved by exact dict lookup against
        ``certificate_sources``. If the two normalise differently, a hydrated
        padded record is unreachable from a canonical selector.
        """
        state = AuthState(
            certificate_sources={
                self._PADDED: CertificateSourceRecord(
                    name=self._PADDED,
                    certificate_path="p",
                    registered_at=_AWARE,
                )
            },
            active_certificate_source=self._PADDED,
        )
        assert state.active_certificate_source == self._CANONICAL
        assert set(state.certificate_sources) == {self._CANONICAL}
        assert state.certificate_sources[state.active_certificate_source].name == self._CANONICAL

    def test_cleanup_intent_source_name_collections_are_canonical(self) -> None:
        intent = _cleanup(
            active_certificate_source_at_start=self._PADDED,
            secret_source_names=(self._PADDED, "other"),
        )
        assert intent.active_certificate_source_at_start == self._CANONICAL
        assert intent.secret_source_names == (self._CANONICAL, "other")
