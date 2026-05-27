"""Redaction-rule registry and the :func:`redact` helper family.

The :class:`~aeat.core.classification.RedactionRule` shape lives in
:mod:`aeat.core.classification` so the classification policy table can
reference rule names without a circular import. This module ships:

* a small in-memory registry of default
  :class:`~aeat.core.classification.RedactionRule` instances keyed by
  name (NIF, URL, OAuth bearer token, opaque bearer token);
* :func:`redact`, the flat-string helper that applies a tuple of
  rules in declared order;
* :func:`redact_structured`, the recursive variant that walks dict /
  list / tuple containers and redacts every string leaf in place;
* :func:`redact_for_log`, the convenience wrapper for log lines and
  exception messages;
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

import hashlib
import re
from collections.abc import Mapping
from types import MappingProxyType
from urllib.parse import urlparse

from ..classification import (
    ClassificationPolicy as _ClassificationPolicy,
    RedactionRule as _RedactionRule,
    RedactionStrategy as _RedactionStrategy,
    SensitivityClass as _SensitivityClass,
    default_policy_for as _default_policy_for,
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
    }
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
    :func:`~aeat.core.classification._default_policy_for` and then
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
        TypeError: When ``value`` is not a :class:`str`.
    """
    if not isinstance(value, str):
        raise TypeError(f"redact() expects str; got {type(value).__name__}")
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
    :attr:`~aeat.core.classification._SensitivityClass.IDENTITY`
    class is for ciphertext-at-rest, not log-shaped strings; the
    :attr:`~aeat.core.classification._SensitivityClass.DIAGNOSTIC`
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


__all__ = [
    "default_rules",
    "default_rules_for",
    "default_rules_for_class",
    "redact",
    "redact_for_log",
    "redact_structured",
]
