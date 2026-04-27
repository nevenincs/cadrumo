"""Tests for the redaction-rule registry and the ``redact`` helper."""

from __future__ import annotations

import pytest

from . import (
    RedactionRule,
    RedactionStrategy,
    SensitivityClass,
)
from ._redaction import (
    default_rules,
    default_rules_for,
    default_rules_for_class,
    redact,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestDefaultRulesRegistry:
    """The default registry exposes the audit-driven rule set."""

    def test_registry_is_immutable(self) -> None:
        from types import MappingProxyType

        assert isinstance(default_rules(), MappingProxyType)

    def test_known_names(self) -> None:
        keys = set(default_rules())
        assert "nif-hash" in keys
        assert "url-host-only" in keys
        assert "token-fingerprint" in keys

    def test_resolve_for_audit_class(self) -> None:
        rules = default_rules_for_class(SensitivityClass.AUDIT)
        names = {rule.name for rule in rules}
        assert {"nif-hash", "url-host-only", "token-fingerprint"} <= names

    def test_resolve_for_corpus_is_empty(self) -> None:
        assert default_rules_for_class(SensitivityClass.CORPUS) == ()

    def test_resolve_for_policy_skips_unknown_names(self) -> None:
        from ._classification import AtRestTreatment, ClassificationPolicy, RetentionPolicy

        policy = ClassificationPolicy(
            sensitivity=SensitivityClass.OPERATIONAL,
            at_rest=AtRestTreatment.PLAINTEXT,
            retention=RetentionPolicy(),
            redaction_rules=("nif-hash", "not-a-real-rule"),
        )
        rules = default_rules_for(policy)
        assert len(rules) == 1
        assert rules[0].name == "nif-hash"


class TestNifRedaction:
    @pytest.mark.parametrize(
        "candidate",
        [
            "12345678Z",
            "X1234567L",
            "Y8765432B",
        ],
    )
    def test_nif_replaced_with_sha256_prefix(self, candidate: str) -> None:
        rules = (default_rules()["nif-hash"],)
        out = redact(f"NIF: {candidate} on file", rules=rules)
        assert candidate not in out
        assert "sha256:" in out

    def test_same_nif_redacts_to_same_digest(self) -> None:
        rules = (default_rules()["nif-hash"],)
        first = redact("12345678Z", rules=rules)
        second = redact("12345678Z", rules=rules)
        assert first == second

    def test_different_nifs_redact_to_different_digests(self) -> None:
        rules = (default_rules()["nif-hash"],)
        first = redact("12345678Z", rules=rules)
        second = redact("87654321X", rules=rules)
        assert first != second

    def test_no_match_passes_through(self) -> None:
        rules = (default_rules()["nif-hash"],)
        text = "no identity-bearing content here"
        assert redact(text, rules=rules) == text


class TestUrlRedaction:
    def test_path_and_query_dropped(self) -> None:
        rules = (default_rules()["url-host-only"],)
        out = redact("see https://sede.example.com/path?token=abc", rules=rules)
        assert "https://sede.example.com" in out
        assert "/path" not in out
        assert "token=abc" not in out

    def test_multiple_urls_redacted(self) -> None:
        rules = (default_rules()["url-host-only"],)
        out = redact(
            "first https://a.example.com/x?y=1 and second https://b.example.com/z",
            rules=rules,
        )
        assert "https://a.example.com" in out
        assert "https://b.example.com" in out
        assert "/x" not in out
        assert "/z" not in out


class TestTokenRedaction:
    def test_jwt_replaced_with_fingerprint(self) -> None:
        jwt = "eyJ" + "x" * 30 + "." + "y" * 20 + "." + "z" * 20
        rules = (default_rules()["token-fingerprint"],)
        out = redact(f"Authorization: Bearer {jwt}", rules=rules)
        assert jwt not in out
        assert "token:sha256:" in out


class TestOpaqueBearerRedaction:
    """The bearer-token-fingerprint rule covers non-JWT bearer shapes."""

    def test_authorization_header_redacted(self) -> None:
        token = "ABCDEFGHIJ1234567890_abcdefghij"
        rules = (default_rules()["bearer-token-fingerprint"],)
        out = redact(f"Authorization: Bearer {token}", rules=rules)
        assert token not in out
        assert "token:sha256:" in out

    def test_google_ya29_token_redacted(self) -> None:
        ya29 = "ya29." + "x" * 80
        rules = (default_rules()["bearer-token-fingerprint"],)
        out = redact(f"access_token={ya29}", rules=rules)
        assert ya29 not in out
        assert "token:sha256:" in out

    def test_short_value_passes_through(self) -> None:
        """A 'bearer foo' fragment with too-short payload is NOT redacted."""
        rules = (default_rules()["bearer-token-fingerprint"],)
        out = redact("Bearer abc", rules=rules)
        assert "Bearer abc" in out


class TestRuleChaining:
    def test_rules_apply_in_declared_order(self) -> None:
        rules = default_rules_for_class(SensitivityClass.AUDIT)
        text = "NIF 12345678Z fetched from https://sede.example.com/x?y=1"
        out = redact(text, rules=rules)
        assert "12345678Z" not in out
        assert "/x?y=1" not in out


class TestEllipsisStrategy:
    def test_ellipsis_replaces_match(self) -> None:
        rule = RedactionRule(
            name="custom",
            pattern=r"secret-[a-z]+",
            strategy=RedactionStrategy.ELLIPSIS,
        )
        out = redact("secret-payload found here", rules=(rule,))
        assert "..." in out
        assert "secret-payload" not in out


class TestRedactInputs:
    def test_non_string_rejected(self) -> None:
        from typing import cast

        with pytest.raises(TypeError):
            # The function refuses non-string inputs at runtime; the
            # cast keeps the static type-checker happy while exercising
            # the runtime guard.
            redact(cast(str, 12345), rules=())

    def test_empty_rules_passes_through(self) -> None:
        text = "anything goes"
        assert redact(text, rules=()) == text


class TestSettingsAcceptNewDirs:
    """The new audit + blob-store paths normalise correctly."""

    def test_audit_dir_default_under_project_root(self) -> None:
        from ..config import PROJECT_ROOT, Settings

        settings = Settings()
        assert settings.aeat_audit_dir == PROJECT_ROOT / "var" / "audit"
        assert settings.aeat_blob_store_dir == PROJECT_ROOT / "var" / "blobs"
