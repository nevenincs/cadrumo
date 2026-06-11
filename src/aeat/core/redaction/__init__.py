"""Redaction-rule registry and the :func:`redact` helper family.

The :class:`~aeat.core.classification.RedactionRule` shape lives in
:mod:`aeat.core.classification` so the :class:`SensitivityClass` policy
table can reference rule names without a circular import. This module ships:

* a small in-memory registry of default
  :class:`~aeat.core.classification.RedactionRule` instances keyed by
  name (NIF, URL, OAuth bearer token, opaque bearer token);
* :func:`redact`, the flat-string helper that applies a tuple of
  rules in declared order;
* :func:`redact_structured`, the recursive variant that walks dict /
  list / tuple containers and redacts every string leaf in place;
* :func:`redact_for_log`, the convenience wrapper for log lines and
  exception messages;
* :func:`redact_for_cli_output` and
  :func:`redact_structured_for_cli_output`, the public CLI success-output
  profile for rendered text and JSON-shaped payloads;
* :func:`default_rules_for` and :func:`default_rules_for_class`, the
  resolvers that turn rule names stored on a
  :class:`~aeat.core.classification.ClassificationPolicy` into the
  underlying :class:`~aeat.core.classification.RedactionRule`
  instances.

The redaction strategies, defined in
:class:`~aeat.core.classification.RedactionStrategy`, are:

``SHA256_PREFIX``
    Replace the matched span with ``sha256:<first-8-hex>`` of its
    SHA-256 digest. Used for stable identifiers (NIF / NIE / CIF).

``HOST_ONLY``
    For URL-shaped values, retain only ``<scheme>://<host>``;
    everything else (path, query, fragment) is dropped.

``FINGERPRINT``
    Bearer- / token-shaped values rewrite to
    ``token:sha256:<first-8-hex>``.

``ELLIPSIS``
    Replace the matched span with three ASCII full stops.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from urllib.parse import urlparse

from ..classification import (
    ClassificationPolicy as _ClassificationPolicy,
)
from ..classification import (
    RedactionRule as _RedactionRule,
)
from ..classification import (
    RedactionStrategy as _RedactionStrategy,
)
from ..classification import (
    SensitivityClass as _SensitivityClass,
)
from ..classification import (
    default_policy_for as _default_policy_for,
)
from ..hashing import sha256_hex as _sha256_hex

# NIF / NIE / CIF — Spanish identity numbers. Eight digits + check letter
# with optional leading X / Y / Z for foreigners.
_NIF_PATTERN = r"\b[XYZxyz]?\d{7,8}[A-Za-z]\b"

# Bearer / OAuth tokens commonly start with ``ey`` (JWT).
_BEARER_PATTERN = r"(?i)\b(?:bearer\s+)?(eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})"

# Opaque (non-JWT) bearer tokens — Google's ya29 access tokens, generic
# Authorization-header bearer values, and OAuth refresh-token shapes.
# Matches the entire token (including the optional 'authorization:' /
# 'bearer ' prefix) so consumers can redact a whole header line at once.
_OPAQUE_BEARER_PATTERN = (
    r"(?i)(?:authorization:\s*)?bearer\s+[A-Za-z0-9._~+/=\-]{20,}"
    r"|ya29\.[A-Za-z0-9_\-]{40,}"
)

# Generic URL pattern. Drops everything except the host component.
_URL_PATTERN = r"https?://[^\s\"'<>]+"

CLI_PROFILE_ID_PLACEHOLDER = "<profile-id>"
CLI_BUCKET_ID_PLACEHOLDER = "<bucket-id>"
CLI_OBJECT_KEY_PLACEHOLDER = "<object-key>"

_CLI_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
)
_CLI_IDENTIFIER_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?P<label>\b(?:"
    r"active[_-]?profile(?:[_-]?id)?|"
    r"bucket[_-]?profile[_-]?id|"
    r"profile[_-]?bucket[_-]?id|"
    r"profile[_-]?id|"
    r"repository[_-]?profile[_-]?id|"
    r"source[_-]?profile[_-]?id|"
    r"target[_-]?profile[_-]?id|"
    r"active[_-]?bucket[_-]?id|"
    r"bucket[_-]?id|"
    r"repository[_-]?bucket[_-]?id|"
    r"storage[_-]?bucket[_-]?id|"
    r"object[_-]?key|"
    r"lookup[_-]?key|"
    r"secure[_-]?object[_-]?key|"
    r"storage[_-]?object[_-]?key"
    r")\b)"
    r"(?P<sep>\s*(?::|=|\t)\s*)"
    r"(?P<value>[^\s,;]+)",
)
_CLI_OBJECT_KEY_TOKEN_PATTERN = re.compile(
    r"(?i)\b(?:wallet|transaction-catalogue|invoice|attachment|justificante):[^\s,;]+",
)
_CLI_PROFILE_ID_KEYS = frozenset(
    {
        "active_profile_id",
        "bucket_profile_id",
        "profile_bucket_id",
        "profile_id",
        "repository_profile_id",
        "source_profile_id",
        "target_profile_id",
    },
)
_CLI_PROFILE_REFERENCE_KEYS = frozenset({"active_profile"})
_CLI_BUCKET_ID_KEYS = frozenset(
    {
        "active_bucket_id",
        "bucket_id",
        "repository_bucket_id",
        "storage_bucket_id",
    },
)
_CLI_OBJECT_KEY_KEYS = frozenset(
    {
        "lookup_key",
        "object_key",
        "secure_object_key",
        "storage_object_key",
    },
)


def _sha256_prefix(value: str) -> str:
    digest = _sha256_hex(value.encode("utf-8"))
    return f"sha256:{digest[:8]}"


def _fingerprint(value: str) -> str:
    digest = _sha256_hex(value.encode("utf-8"))
    return f"token:sha256:{digest[:8]}"


def _host_only(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.hostname:
        return "https://[redacted]"
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.hostname}"


_DEFAULT_RULES: Mapping[str, _RedactionRule] = MappingProxyType(
    {
        "nif-hash": _RedactionRule(
            name="nif-hash",
            pattern=_NIF_PATTERN,
            strategy=_RedactionStrategy.SHA256_PREFIX,
            applies_to=(
                _SensitivityClass.IDENTITY,
                _SensitivityClass.FINANCIAL,
                _SensitivityClass.AUDIT,
                _SensitivityClass.DIAGNOSTIC,
            ),
        ),
        "url-host-only": _RedactionRule(
            name="url-host-only",
            pattern=_URL_PATTERN,
            strategy=_RedactionStrategy.HOST_ONLY,
            applies_to=(
                _SensitivityClass.SESSION,
                _SensitivityClass.AUDIT,
                _SensitivityClass.DIAGNOSTIC,
            ),
        ),
        "token-fingerprint": _RedactionRule(
            name="token-fingerprint",
            pattern=_BEARER_PATTERN,
            strategy=_RedactionStrategy.FINGERPRINT,
            applies_to=(
                _SensitivityClass.SECRET,
                _SensitivityClass.SESSION,
                _SensitivityClass.AUDIT,
                _SensitivityClass.DIAGNOSTIC,
            ),
        ),
        "bearer-token-fingerprint": _RedactionRule(
            name="bearer-token-fingerprint",
            pattern=_OPAQUE_BEARER_PATTERN,
            strategy=_RedactionStrategy.FINGERPRINT,
            applies_to=(
                _SensitivityClass.SECRET,
                _SensitivityClass.SESSION,
                _SensitivityClass.AUDIT,
                _SensitivityClass.DIAGNOSTIC,
            ),
        ),
    },
)


def default_rules() -> Mapping[str, _RedactionRule]:
    """Return the immutable default-rule registry keyed by rule name.

    Returns:
        A read-only :class:`~collections.abc.Mapping` from rule name
        to :class:`~aeat.core.classification._RedactionRule`.
    """
    return _DEFAULT_RULES


def default_rules_for(policy: _ClassificationPolicy) -> tuple[_RedactionRule, ...]:
    """Resolve the rule references on a policy to concrete rule instances.

    Args:
        policy: A
            :class:`~aeat.core.classification._ClassificationPolicy`
            whose ``redaction_rules`` field carries rule names.

    Returns:
        A tuple of :class:`~aeat.core.classification._RedactionRule`
        instances in the order they were declared on the policy.
        Names that are not in the default registry are silently
        skipped: this is deliberate so per-domain policies can
        reference custom rules registered by other modules.
    """
    return tuple(_DEFAULT_RULES[name] for name in policy.redaction_rules if name in _DEFAULT_RULES)


def default_rules_for_class(sensitivity: _SensitivityClass) -> tuple[_RedactionRule, ...]:
    """Resolve the default rule set for a sensitivity class.

    Convenience wrapper that goes through
    ``aeat.core.classification._default_policy_for`` and then
    :func:`default_rules_for` so callers do not need to know about
    the policy table.

    Args:
        sensitivity: The
            :class:`~aeat.core.classification._SensitivityClass` whose
            default rules should apply.

    Returns:
        Ordered tuple of rules for that class.
    """
    return default_rules_for(_default_policy_for(sensitivity))


def _apply_one(rule: _RedactionRule, value: str) -> str:
    pattern = re.compile(rule.pattern, re.MULTILINE)
    if rule.strategy is _RedactionStrategy.ELLIPSIS:
        return pattern.sub("...", value)
    if rule.strategy is _RedactionStrategy.SHA256_PREFIX:
        return pattern.sub(lambda m: _sha256_prefix(m.group(0)), value)
    if rule.strategy is _RedactionStrategy.HOST_ONLY:
        return pattern.sub(lambda m: _host_only(m.group(0)), value)
    if rule.strategy is _RedactionStrategy.FINGERPRINT:
        return pattern.sub(lambda m: _fingerprint(m.group(0)), value)
    return value  # pragma: no cover - exhaustive enum


def redact(value: str, *, rules: tuple[_RedactionRule, ...]) -> str:
    """Apply ``rules`` to a flat string in declared order.

    Args:
        value: The candidate string. Non-string inputs raise
            :exc:`TypeError`; consumers must stringify upstream.
        rules: Ordered tuple of rules. Each rule's pattern is
            compiled with :data:`re.MULTILINE` and its strategy is
            applied to every match.

    Returns:
        The redacted string.

    Raises:
        RedactionError: When ``value`` is not a :class:`str`.
    """
    if not isinstance(value, str):
        from ..errors import RedactionError

        raise RedactionError(f"redact() expects str; got {type(value).__name__}")
    result = value
    for rule in rules:
        result = _apply_one(rule, result)
    return result


def redact_structured(value: object, *, rules: tuple[_RedactionRule, ...]) -> object:
    """Recursively apply ``rules`` to every string leaf inside a structure.

    Walks dicts, lists, and tuples; redacts every string at the
    leaves. Non-string non-container values pass through unchanged.
    The container shape is preserved (dict stays dict, list stays
    list, tuple stays tuple). The resulting object is a fresh copy
    at every container level — the input is never mutated.

    This is the load-bearing primitive for nested audit payloads:
    submission audit events and run-trace records are nested dicts,
    and a flat :func:`redact` call would not reach the NIF nested
    under e.g. ``event["payload"]["taxpayer"]["nif"]``.

    Args:
        value: Any JSON-shaped value: :class:`str`, :class:`int`,
            :class:`float`, :class:`bool`, ``None``, :class:`dict`,
            :class:`list`, :class:`tuple`, or a typed model that has
            been dumped via ``model_dump()`` upstream.
        rules: Ordered tuple of rules.

    Returns:
        A redacted copy of ``value`` with the same nested shape.
    """
    if isinstance(value, str):
        result_str = value
        for rule in rules:
            result_str = _apply_one(rule, result_str)
        return result_str
    if isinstance(value, dict):
        return {k: redact_structured(v, rules=rules) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_structured(item, rules=rules) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_structured(item, rules=rules) for item in value)
    return value


def _normalise_cli_key(key: object | None) -> str | None:
    if key is None:
        return None
    return re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")


def _is_cli_profile_reference(value: object) -> bool:
    return isinstance(value, str) and _CLI_UUID_PATTERN.fullmatch(value.strip()) is not None


def _cli_placeholder_for_key(key: object | None, value: object) -> str | None:
    if value is None or value == "":
        return None
    normalised = _normalise_cli_key(key)
    if normalised in _CLI_PROFILE_ID_KEYS:
        return CLI_PROFILE_ID_PLACEHOLDER
    if normalised in _CLI_PROFILE_REFERENCE_KEYS and _is_cli_profile_reference(value):
        return CLI_PROFILE_ID_PLACEHOLDER
    if normalised in _CLI_BUCKET_ID_KEYS:
        return CLI_BUCKET_ID_PLACEHOLDER
    if normalised in _CLI_OBJECT_KEY_KEYS:
        return CLI_OBJECT_KEY_PLACEHOLDER
    return None


def _redact_cli_string(text: str) -> str:
    redacted = _CLI_IDENTIFIER_ASSIGNMENT_PATTERN.sub(
        lambda match: (
            f"{match.group('label')}{match.group('sep')}"
            f"{_cli_placeholder_for_key(match.group('label'), match.group('value')) or match.group('value')}"
        ),
        text,
    )
    redacted = redact_for_log(redacted)
    redacted = _CLI_UUID_PATTERN.sub(CLI_PROFILE_ID_PLACEHOLDER, redacted)
    return _CLI_OBJECT_KEY_TOKEN_PATTERN.sub(CLI_OBJECT_KEY_PLACEHOLDER, redacted)


def _redact_structured_for_cli_output(value: object, *, key: object | None = None) -> object:
    placeholder = _cli_placeholder_for_key(key, value)
    if placeholder is not None:
        return placeholder
    if isinstance(value, str):
        return _redact_cli_string(value)
    if isinstance(value, dict):
        redacted: dict[object, object] = {}
        for item_key, item_value in value.items():
            redacted_key = _redact_cli_string(item_key) if isinstance(item_key, str) else item_key
            unique_key = _unique_mapping_key(redacted_key, redacted)
            redacted[unique_key] = _redact_structured_for_cli_output(item_value, key=item_key)
        return redacted
    if isinstance(value, list):
        return [_redact_structured_for_cli_output(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_structured_for_cli_output(item) for item in value)
    return value


def _unique_mapping_key(candidate: object, existing: Mapping[object, object]) -> object:
    if candidate not in existing:
        return candidate
    base = str(candidate)
    suffix = 2
    while f"{base}#{suffix}" in existing:
        suffix += 1
    return f"{base}#{suffix}"


def redact_for_log(text: str) -> str:
    """Redact a string against the AUDIT-class rule set for log/error use.

    Convenience wrapper for call sites that construct exception
    messages or log lines containing operator-controlled PII
    (NIF / NIE / CIF, OAuth tokens, session URLs). Raised exceptions
    interpolate user-controlled identifiers into ``exc.args[0]``;
    the standard logging filter covers the :mod:`logging` path but
    not ``str(exc)`` flowing through Typer's default error renderer,
    JSON envelopes, or observability sinks that capture exception
    text without going through the filter. Redact at the construction
    site so the secret is never in the exception's message field to
    begin with.

    The AUDIT rule set is the right default for exception text: it
    redacts NIF (sha256-prefix), URL host-only, and bearer-token
    fingerprints. The
    ``aeat.core.classification._SensitivityClass.IDENTITY``
    class is for ciphertext-at-rest, not log-shaped strings; the
    ``aeat.core.classification._SensitivityClass.DIAGNOSTIC``
    class has the same rules but is named for observability sinks
    specifically.
    :attr:`~aeat.core.classification._SensitivityClass.AUDIT` is the
    canonical class for the log/error path.

    Args:
        text: The log-shaped string to redact.

    Returns:
        The redacted string.
    """
    return redact(text, rules=default_rules_for_class(_SensitivityClass.AUDIT))


def redact_for_cli_output(text: str) -> str:
    """Redact a rendered operator-facing CLI output line.

    The CLI public-output profile composes the AUDIT rule set used by
    logs/errors with additional profile, bucket, and secure-object key
    handling. It deliberately keeps display labels untouched and targets
    machine identifiers, storage lookup values, URL paths, bearer tokens,
    and tax identities that should not be emitted as success output.

    Args:
        text: Rendered CLI text.

    Returns:
        Redacted CLI-safe text.

    Raises:
        RedactionError: When ``text`` is not a :class:`str`.
    """
    if not isinstance(text, str):
        from ..errors import RedactionError

        raise RedactionError(f"redact_for_cli_output() expects str; got {type(text).__name__}")
    return _redact_cli_string(text)


def redact_structured_for_cli_output(value: object) -> object:
    """Recursively redact a JSON-shaped value for public CLI output.

    Unlike :func:`redact_structured`, this helper is key-aware so values
    under canonical profile, bucket, and secure-object key fields become
    stable placeholders before JSON serialization. Container shape is
    preserved and the input object is never mutated.

    Args:
        value: JSON-shaped payload to prepare for CLI success output.

    Returns:
        A redacted copy with the same nested shape.
    """
    return _redact_structured_for_cli_output(value)


__all__ = [
    "CLI_BUCKET_ID_PLACEHOLDER",
    "CLI_OBJECT_KEY_PLACEHOLDER",
    "CLI_PROFILE_ID_PLACEHOLDER",
    "default_rules",
    "default_rules_for",
    "default_rules_for_class",
    "redact",
    "redact_for_cli_output",
    "redact_for_log",
    "redact_structured",
    "redact_structured_for_cli_output",
]
