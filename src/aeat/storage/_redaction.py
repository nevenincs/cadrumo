"""Redaction-rule registry and the ``redact`` helper.

The rule shape is defined in :mod:`aeat.storage._classification` (so the
classification policy table can reference rule names without a circular
import). This module ships:

- a small in-memory registry of default :class:`RedactionRule`
  instances keyed by name (NIF / URL / OAuth bearer token / generic
  ellipsis);
- the :func:`redact` helper that applies a tuple of rules to a value
  in declared order;
- the :func:`default_rules_for` convenience that resolves the rule
  references stored in :class:`ClassificationPolicy.redaction_rules`
  to the actual :class:`RedactionRule` instances.

Strategies:

- ``SHA256_PREFIX`` — replace the matched span with the first 8 hex
  characters of its SHA-256 digest, prefixed with ``sha256:``.
- ``HOST_ONLY`` — for URL-shaped values, retain only the URL host
  component; everything else (path, query, fragment) is dropped.
- ``FINGERPRINT`` — bearer- / token-shaped value rewrites to
  ``token:sha256:<8hex>``.
- ``ELLIPSIS`` — replace the matched span with three ASCII full stops.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from types import MappingProxyType
from urllib.parse import urlparse

from ._classification import (
    ClassificationPolicy,
    RedactionRule,
    RedactionStrategy,
    SensitivityClass,
    default_policy_for,
)

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


def _sha256_prefix(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:8]}"


def _fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"token:sha256:{digest[:8]}"


def _host_only(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.hostname:
        return "https://[redacted]"
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.hostname}"


_DEFAULT_RULES: Mapping[str, RedactionRule] = MappingProxyType(
    {
        "nif-hash": RedactionRule(
            name="nif-hash",
            pattern=_NIF_PATTERN,
            strategy=RedactionStrategy.SHA256_PREFIX,
            applies_to=(
                SensitivityClass.IDENTITY,
                SensitivityClass.FINANCIAL,
                SensitivityClass.AUDIT,
                SensitivityClass.DIAGNOSTIC,
            ),
        ),
        "url-host-only": RedactionRule(
            name="url-host-only",
            pattern=_URL_PATTERN,
            strategy=RedactionStrategy.HOST_ONLY,
            applies_to=(
                SensitivityClass.SESSION,
                SensitivityClass.AUDIT,
                SensitivityClass.DIAGNOSTIC,
            ),
        ),
        "token-fingerprint": RedactionRule(
            name="token-fingerprint",
            pattern=_BEARER_PATTERN,
            strategy=RedactionStrategy.FINGERPRINT,
            applies_to=(
                SensitivityClass.SECRET,
                SensitivityClass.SESSION,
                SensitivityClass.AUDIT,
                SensitivityClass.DIAGNOSTIC,
            ),
        ),
        "bearer-token-fingerprint": RedactionRule(
            name="bearer-token-fingerprint",
            pattern=_OPAQUE_BEARER_PATTERN,
            strategy=RedactionStrategy.FINGERPRINT,
            applies_to=(
                SensitivityClass.SECRET,
                SensitivityClass.SESSION,
                SensitivityClass.AUDIT,
                SensitivityClass.DIAGNOSTIC,
            ),
        ),
    }
)


def default_rules() -> Mapping[str, RedactionRule]:
    """Return the immutable default-rule registry keyed by rule name."""
    return _DEFAULT_RULES


def default_rules_for(policy: ClassificationPolicy) -> tuple[RedactionRule, ...]:
    """Resolve the rule references in ``policy.redaction_rules`` to instances.

    Args:
        policy: A classification policy whose ``redaction_rules`` field
            carries rule names.

    Returns:
        A tuple of :class:`RedactionRule` instances in the order they
        were declared on the policy. Names that are not in the default
        registry are silently skipped — this is deliberate so per-domain
        policies can reference custom rules registered later.
    """
    return tuple(_DEFAULT_RULES[name] for name in policy.redaction_rules if name in _DEFAULT_RULES)


def default_rules_for_class(sensitivity: SensitivityClass) -> tuple[RedactionRule, ...]:
    """Resolve the default rule set for ``sensitivity`` via the policy table."""
    return default_rules_for(default_policy_for(sensitivity))


def _apply_one(rule: RedactionRule, value: str) -> str:
    pattern = re.compile(rule.pattern, re.MULTILINE)
    if rule.strategy is RedactionStrategy.ELLIPSIS:
        return pattern.sub("...", value)
    if rule.strategy is RedactionStrategy.SHA256_PREFIX:
        return pattern.sub(lambda m: _sha256_prefix(m.group(0)), value)
    if rule.strategy is RedactionStrategy.HOST_ONLY:
        return pattern.sub(lambda m: _host_only(m.group(0)), value)
    if rule.strategy is RedactionStrategy.FINGERPRINT:
        return pattern.sub(lambda m: _fingerprint(m.group(0)), value)
    return value  # pragma: no cover - exhaustive enum


def redact(value: str, *, rules: tuple[RedactionRule, ...]) -> str:
    """Apply ``rules`` to ``value`` in declared order.

    Args:
        value: The candidate string. Non-string inputs raise
            :class:`TypeError`; consumers stringify upstream.
        rules: Ordered tuple of rules.

    Returns:
        The redacted string.
    """
    if not isinstance(value, str):
        raise TypeError(f"redact() expects str; got {type(value).__name__}")
    result = value
    for rule in rules:
        result = _apply_one(rule, result)
    return result


def redact_structured(value: object, *, rules: tuple[RedactionRule, ...]) -> object:
    """Apply ``rules`` to every string leaf inside ``value``, recursively.

    Walks dicts, lists, and tuples; redacts every string at the
    leaves. Non-string non-container values pass through unchanged.
    The container shape is preserved (dict stays dict; list stays
    list; tuple stays tuple). The resulting object is a fresh copy at
    every container level — the input is never mutated.

    This is the load-bearing primitive for the audit-sink relocation:
    submission audit events and run-trace records are nested dicts,
    and a flat ``redact()`` call would not reach the NIF nested under
    e.g. ``event["payload"]["taxpayer"]["nif"]``.

    Args:
        value: Any JSON-shaped value (str, int, float, bool, None,
            dict, list, tuple, or a typed model that is dumped via
            ``model_dump()`` upstream).
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


def redact_for_log(text: str) -> str:
    """Redact ``text`` against the AUDIT-class rule set for log/error use.

    Convenience wrapper for the call sites that construct
    exception messages or log lines containing operator-controlled
    PII (NIF / NIE / CIF, OAuth tokens, session URLs). Issue #469
    M-3: raised exceptions previously interpolated raw NIF into
    ``exc.args[0]``; the ``SecretScrubbingFilter`` covers the
    ``logging`` path but not ``str(exc)`` flowing through typer's
    default error renderer / JSON envelope / observability sinks
    that capture exception text without going through the filter.
    Redact at the construction site so the secret is never in the
    exception's message field to begin with.

    The AUDIT rule set is the right default for exception text: it
    redacts NIF (sha256-prefix), URL host-only, and bearer-token
    fingerprints. The IDENTITY class is for ciphertext-at-rest, not
    log-shaped strings; the DIAGNOSTIC class has the same rules but
    is named for observability sinks specifically. AUDIT is the
    log/error path's canonical class.
    """
    return redact(text, rules=default_rules_for_class(SensitivityClass.AUDIT))


__all__ = [
    "default_rules",
    "default_rules_for",
    "default_rules_for_class",
    "redact",
    "redact_for_log",
    "redact_structured",
]
