"""Tests for the sensitivity classification primitive."""

from __future__ import annotations

from datetime import timedelta
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from . import (
    AtRestTreatment,
    RedactionRule,
    RedactionStrategy,
    RetentionPolicy,
    SensitivityClass,
    default_policy_for,
    default_policy_table,
)
from ._classification import _DEFAULT_POLICY_TABLE

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestSensitivityClass:
    """The closed enum is the contract for every persisted record."""

    def test_every_member_has_default_policy(self) -> None:
        """The default-policy table covers every enum member exhaustively."""
        for member in SensitivityClass:
            assert member in _DEFAULT_POLICY_TABLE, (
                f"SensitivityClass.{member.name} is missing a default policy. "
                "Add it to _DEFAULT_POLICY_TABLE in _classification.py."
            )

    def test_default_policy_table_has_no_extra_entries(self) -> None:
        """Every default-policy entry corresponds to a real enum member."""
        members = set(SensitivityClass)
        keys = set(_DEFAULT_POLICY_TABLE)
        assert keys == members, f"Default-policy table mismatch: extras={keys - members}, missing={members - keys}"

    def test_string_values_are_lowercase_kebab_case(self) -> None:
        """Wire-format values follow the project's StrEnum convention."""
        for member in SensitivityClass:
            assert member.value == member.name.lower()


class TestDefaultPolicyTreatments:
    """The audit-driven rules govern at-rest treatment per class."""

    @pytest.mark.parametrize(
        "sensitivity",
        [
            SensitivityClass.SECRET,
            SensitivityClass.SESSION,
            SensitivityClass.IDENTITY,
            SensitivityClass.FINANCIAL,
            SensitivityClass.AUDIT,
        ],
    )
    def test_sensitive_classes_require_ciphertext(self, sensitivity: SensitivityClass) -> None:
        """SECRET, SESSION, IDENTITY, FINANCIAL, AUDIT MUST be ciphertext at rest."""
        policy = default_policy_for(sensitivity)
        assert policy.at_rest is AtRestTreatment.CIPHERTEXT_REQUIRED

    @pytest.mark.parametrize(
        "sensitivity",
        [
            SensitivityClass.CACHE,
            SensitivityClass.CORPUS,
            SensitivityClass.OPERATIONAL,
            SensitivityClass.DIAGNOSTIC,
        ],
    )
    def test_low_sensitivity_classes_default_plaintext(
        self,
        sensitivity: SensitivityClass,
    ) -> None:
        """CACHE, CORPUS, OPERATIONAL, DIAGNOSTIC default to plaintext at rest."""
        policy = default_policy_for(sensitivity)
        assert policy.at_rest is AtRestTreatment.PLAINTEXT


class TestRetentionDefaults:
    """Retention defaults align to the secure-persistence-foundation research."""

    def test_secret_requires_explicit_expiry(self) -> None:
        """SECRET-class records MUST carry an ``expires_at`` field."""
        policy = default_policy_for(SensitivityClass.SECRET)
        assert policy.retention.require_explicit_expiry is True

    def test_session_requires_explicit_expiry_and_short_max_age(self) -> None:
        """SESSION-class records expire within 24 hours by default."""
        policy = default_policy_for(SensitivityClass.SESSION)
        assert policy.retention.require_explicit_expiry is True
        assert policy.retention.max_age == timedelta(hours=24)

    def test_financial_retention_aligns_to_fiscal_horizon(self) -> None:
        """FINANCIAL retention covers five fiscal years (statute envelope)."""
        policy = default_policy_for(SensitivityClass.FINANCIAL)
        assert policy.retention.max_age == timedelta(days=365 * 5)

    def test_diagnostic_short_retention(self) -> None:
        """DIAGNOSTIC records expire within seven days by default."""
        policy = default_policy_for(SensitivityClass.DIAGNOSTIC)
        assert policy.retention.max_age == timedelta(days=7)

    def test_corpus_unbounded_retention(self) -> None:
        """CORPUS material has no max-age policy."""
        policy = default_policy_for(SensitivityClass.CORPUS)
        assert policy.retention.max_age is None


class TestRedactionRuleReferences:
    """Default redaction-rule references are stable and audit-driven."""

    def test_secret_references_token_fingerprint(self) -> None:
        policy = default_policy_for(SensitivityClass.SECRET)
        assert "token-fingerprint" in policy.redaction_rules

    def test_audit_references_full_redaction_set(self) -> None:
        """AUDIT-class records strip NIF, URLs, and tokens by default."""
        policy = default_policy_for(SensitivityClass.AUDIT)
        assert set(policy.redaction_rules) == {
            "nif-hash",
            "url-host-only",
            "token-fingerprint",
        }

    def test_corpus_has_no_redaction_rules(self) -> None:
        """Public corpora are not subject to default redaction."""
        policy = default_policy_for(SensitivityClass.CORPUS)
        assert policy.redaction_rules == ()


class TestPolicyImmutability:
    """Default policies are frozen pydantic v2 records."""

    def test_policy_is_frozen(self) -> None:
        """Mutating a default policy raises ``ValidationError``."""
        policy = default_policy_for(SensitivityClass.FINANCIAL)
        with pytest.raises(ValidationError):
            policy.at_rest = AtRestTreatment.PLAINTEXT  # type: ignore[misc]

    def test_default_policy_table_is_mappingproxy(self) -> None:
        """The default-policy mapping itself cannot be mutated.

        :class:`MappingProxyType` raises ``TypeError`` on subscript assignment;
        an isinstance check confirms the immutable container type without
        having to perform a write that the type checker would refuse.
        """
        assert isinstance(_DEFAULT_POLICY_TABLE, MappingProxyType)
        # Public surface returns the same proxy, not a fresh dict copy.
        assert default_policy_table() is _DEFAULT_POLICY_TABLE


class TestRedactionRule:
    """The rule shape itself is a frozen pydantic v2 record."""

    def test_rule_round_trips(self) -> None:
        """A valid rule constructs and round-trips through model_dump."""
        rule = RedactionRule(
            name="nif-hash",
            pattern=r"\b[XYZ]?\d{7,8}[A-Z]\b",
            strategy=RedactionStrategy.SHA256_PREFIX,
            applies_to=(SensitivityClass.AUDIT, SensitivityClass.IDENTITY),
        )
        dump = rule.model_dump()
        restored = RedactionRule.model_validate(dump)
        assert restored == rule

    def test_rule_rejects_blank_name(self) -> None:
        with pytest.raises(ValidationError):
            RedactionRule(
                name="",
                pattern=r".+",
                strategy=RedactionStrategy.ELLIPSIS,
            )

    def test_rule_rejects_blank_pattern(self) -> None:
        with pytest.raises(ValidationError):
            RedactionRule(
                name="any",
                pattern="",
                strategy=RedactionStrategy.ELLIPSIS,
            )

    def test_rule_default_applies_to_is_empty_tuple(self) -> None:
        """When ``applies_to`` is omitted, the rule applies regardless of class."""
        rule = RedactionRule(
            name="any",
            pattern=r".+",
            strategy=RedactionStrategy.ELLIPSIS,
        )
        assert rule.applies_to == ()


class TestRetentionPolicyShape:
    """Retention policy enforces sane field constraints."""

    def test_default_policy_is_unbounded(self) -> None:
        policy = RetentionPolicy()
        assert policy.max_age is None
        assert policy.archive_after is None
        assert policy.require_explicit_expiry is False

    def test_policy_round_trips(self) -> None:
        policy = RetentionPolicy(
            max_age=timedelta(days=30),
            archive_after=timedelta(days=14),
            require_explicit_expiry=True,
        )
        dump = policy.model_dump()
        restored = RetentionPolicy.model_validate(dump)
        assert restored == policy
