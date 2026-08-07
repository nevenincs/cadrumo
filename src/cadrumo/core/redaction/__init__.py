"""Redaction-rule registry and the :func:`redact` helper family.

The :class:`core.classification.RedactionRule` shape lives in
:mod:`core.classification` so the :class:`SensitivityClass` policy
table can reference rule names without a circular import. This module ships:

* a small in-memory registry of default
  :class:`core.classification.RedactionRule` instances keyed by
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
  :class:`core.classification.ClassificationPolicy` into the
  underlying :class:`core.classification.RedactionRule`
  instances.

The redaction strategies, defined in
:class:`core.classification.RedactionStrategy`, are:

``SHA256_PREFIX``
    Replace the matched span with ``sha256:<first-8-hex>`` of its
    SHA-256 digest. Used for the personal identity shapes (NIF / NIE),
    which are matched on shape alone.

``SHA256_PREFIX_IF_IDENTITY``
    As ``SHA256_PREFIX``, but only when the matched span parses as a real
    Spanish tax identity. Used for the CIF shape, whose letter-led form
    collides with ordinary document references; the check character is
    what tells the two apart.

``SHA256_PREFIX_IF_IBAN``
    As ``SHA256_PREFIX``, but only when the matched span passes the ISO
    13616 mod-97 check. Used for bank accounts, by an operator decision
    that deliberately reaches past this module's stated tax-identity
    must-handle list. A BOE citation is the standing negative control: it
    must keep passing through untouched, and a pattern that starts eating
    one is too wide.

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
from typing import overload
from urllib.parse import urlparse

from .._iban import IBAN_SHAPE_RE as _IBAN_SHAPE_RE
from .._iban import iban_mod_97 as _iban_mod_97
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

ALWAYS_REDACT_KEY_TERMS: frozenset[str] = frozenset(
    {
        "authorization",
        "bearer",
        "certificate",
        "cookie",
        "credential",
        "nie",
        "nif",
        "passphrase",
        "pkcs12",
        "secret",
        "tax_id",
        "token",
    },
)
"""Key-name fragments every key-name redaction predicate in this tree must treat
as sensitive, regardless of the domain the predicate otherwise scopes to.

This module owns the SHAPE-based redaction rules (:func:`redact_for_log`,
:func:`default_rules_for_class`); it also owns this minimal NAME-based base
because a key-name predicate is a second, complementary layer over shape-based
redaction wherever one exists (see :mod:`cadrumo.core.logging` and
:mod:`cadrumo.application.live._remote_state_outcomes`), and a base that lives
in only one of those consuming sites is a base only until someone edits the
other one.

Each consuming predicate composes its own set as ``ALWAYS_REDACT_KEY_TERMS |
{domain-specific-additions}`` — never redeclares an overlapping term
independently. A term wrongly added here costs an extra scrubbed log line; a
term silently missing from one composing site can leak a NIF the other site
already knew to redact.
"""

# NIF / NIE — Spanish personal identity numbers. Eight digits + check letter
# with optional leading X / Y / Z for foreigners. Matched on shape alone: a
# digit-led run this long rarely collides with ordinary text, so the rule errs
# wide and hashes a lookalike rather than risk missing a mistyped identity.
_NIF_PATTERN = r"\b[XYZxyz]?\d{7,8}[A-Za-z]\b"

# CIF — the tax identity of a legal entity: a kind letter (A-H, J, N, P-S,
# U, V, W), seven digits, and a check character that is a digit or a letter
# A-J depending on the kind. Unlike the personal shapes above this one is
# LETTER-led over a fifteen-letter class, which is the same shape as an
# ordinary document reference (an invoice ``F1234567B``, a batch id), so it
# is paired with ``SHA256_PREFIX_IF_IDENTITY``: the check character decides.
# Widening the personal pattern's leading class instead would have admitted
# every such reference.
_CIF_PATTERN = r"\b[A-HJNPQRSUVWa-hjnpqrsuvw]\d{7}[0-9A-Ja-j]\b"

# IBAN — a bank account number is sensitive financial data, so it is hashed
# out of operator-facing output by operator decision. That decision is BROADER
# than this module's stated must-handle list, which names the tax-identity
# shapes and does not mention bank accounts: this arm is a deliberate
# extension, not an inference from that list. Do not narrow it back on the
# grounds that the stated list omits it.
#
# Scanning form of the anchored :data:`IBAN_SHAPE_RE` in ``core._iban``, which
# stays the authority on what an IBAN looks like. Two country letters, two
# check digits, then an 11-30 character BBAN. Uppercase and separator-free is
# the canonical form the app itself validates and stores; a grouped
# ``ES79 2100 ...`` rendering is not matched, and no surface here emits one.
#
# Every country, not just ES: foreign accounts are declarable (Modelo 720
# exists for assets held abroad) and refund accounts may be non-SEPA, so an
# ES-only arm would protect the domestic case and leak the foreign one. The
# breadth is safe because the mod-97 checksum, not the shape, admits the
# match — a long alphanumeric run otherwise collides with hashes and opaque
# ids, and a real 32-character hex digest in the bundled corpus is rejected
# by the checksum exactly as intended.
_IBAN_PATTERN = r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"

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
# A tab-delimited column-header row is a list of bare field-name tokens, never a
# ``label<TAB>value`` data pair. The identifier-assignment redactor treats the
# ``<TAB>`` between two header cells as ``label<sep>value`` and rewrites the
# *next column name* (e.g. ``modelo`` after ``bucket_id``) into a placeholder,
# corrupting the header. A header is recognised as three or more cells where
# every cell is a bare snake-case identifier word; any real id / date / numeric /
# enum value (UUID, ``bucket-alpha``, ``2026``, ``FILED``) breaks the shape, and a
# two-cell ``key<TAB>value`` data pair stays below the cell threshold and is still
# redacted.
_CLI_HEADER_CELL_PATTERN = re.compile(r"[a-z][a-z0-9_]*")
_CLI_TABULAR_HEADER_MIN_CELLS = 3
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
        ),
        "cif-hash": _RedactionRule(
            name="cif-hash",
            pattern=_CIF_PATTERN,
            strategy=_RedactionStrategy.SHA256_PREFIX_IF_IDENTITY,
        ),
        "iban-hash": _RedactionRule(
            name="iban-hash",
            pattern=_IBAN_PATTERN,
            strategy=_RedactionStrategy.SHA256_PREFIX_IF_IBAN,
        ),
        "url-host-only": _RedactionRule(
            name="url-host-only",
            pattern=_URL_PATTERN,
            strategy=_RedactionStrategy.HOST_ONLY,
        ),
        "token-fingerprint": _RedactionRule(
            name="token-fingerprint",
            pattern=_BEARER_PATTERN,
            strategy=_RedactionStrategy.FINGERPRINT,
        ),
        "bearer-token-fingerprint": _RedactionRule(
            name="bearer-token-fingerprint",
            pattern=_OPAQUE_BEARER_PATTERN,
            strategy=_RedactionStrategy.FINGERPRINT,
        ),
    },
)


def default_rules() -> Mapping[str, _RedactionRule]:
    """Return the immutable default-rule registry keyed by rule name.

    Returns:
        A read-only :class:`~collections.abc.Mapping` from rule name
        to :class:`core.classification.RedactionRule`.
    """
    return _DEFAULT_RULES


def default_rules_for(policy: _ClassificationPolicy) -> tuple[_RedactionRule, ...]:
    """Resolve the rule references on a policy to concrete rule instances.

    A name the registry cannot resolve is REFUSED, not skipped. Skipping
    was the previous behaviour and it made this fail open: a typo in a
    policy's rule tuple dropped that arm of the policy, and the only
    evidence was sensitive data arriving unredacted somewhere nobody was
    looking. A confidentiality boundary has to fail the other way, so an
    unresolvable name now stops the caller instead of quietly narrowing
    what gets redacted.

    The skip was documented as deliberate — room for per-domain policies
    to name custom rules registered by other modules. That extension
    point has no user and no mechanism: every policy is built in the
    default table in :mod:`core.classification`, this function's only
    caller is :func:`default_rules_for_class`, and the registry is a
    frozen mapping with nothing to register through. It was therefore
    paying a fail-open confidentiality risk for a flexibility nothing
    used. Should per-domain rules ever be wanted, they need a real
    registration path, and this refusal is what would make its absence
    obvious rather than silent.

    Args:
        policy: A :class:`core.classification.ClassificationPolicy`
            whose ``redaction_rules`` field carries rule names.

    Returns:
        A tuple of :class:`core.classification.RedactionRule`
        instances in the order they were declared on the policy.

    Raises:
        RedactionError: If the policy names a rule the registry does not
            declare.
    """
    from ..errors import RedactionError

    unresolvable = [name for name in policy.redaction_rules if name not in _DEFAULT_RULES]
    if unresolvable:
        known = ", ".join(sorted(_DEFAULT_RULES))
        raise RedactionError(
            f"policy for {policy.sensitivity.value!r} names redaction rule(s) that do not exist: "
            f"{', '.join(repr(name) for name in unresolvable)}; declared rules are: {known}"
        )
    return tuple(_DEFAULT_RULES[name] for name in policy.redaction_rules)


def default_rules_for_class(sensitivity: _SensitivityClass) -> tuple[_RedactionRule, ...]:
    """Resolve the default rule set for a sensitivity class.

    Convenience wrapper that goes through
    ``cadrumo.core.classification._default_policy_for`` and then
    :func:`default_rules_for` so callers do not need to know about
    the policy table.

    Args:
        sensitivity: The
            :class:`core.classification.SensitivityClass` whose
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
    if rule.strategy is _RedactionStrategy.SHA256_PREFIX_IF_IDENTITY:
        # Imported here, not at module scope: ``core.identity`` reaches
        # ``core.errors``, which reaches this module — the same cycle the
        # lazy ``..errors`` imports below step around.
        from ..identity import IdentityError, validate_identity

        def _hash_if_identity(match: re.Match[str]) -> str:
            span = match.group(0)
            try:
                validate_identity(span)
            except IdentityError:
                return span
            return _sha256_prefix(span)

        return pattern.sub(_hash_if_identity, value)
    if rule.strategy is _RedactionStrategy.SHA256_PREFIX_IF_IBAN:

        def _hash_if_iban(match: re.Match[str]) -> str:
            span = match.group(0)
            if _IBAN_SHAPE_RE.match(span) and _iban_mod_97(span) == 1:
                return _sha256_prefix(span)
            return span

        return pattern.sub(_hash_if_iban, value)
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
        rules: Ordered tuple of
            :class:`core.classification.RedactionRule` instances.
            Each rule's pattern is compiled with :data:`re.MULTILINE`
            and its strategy is applied to every match.

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


@overload
def redact_structured[T](value: dict[str, T], *, rules: tuple[_RedactionRule, ...]) -> dict[str, T]: ...


@overload
def redact_structured[T](value: list[T], *, rules: tuple[_RedactionRule, ...]) -> list[T]: ...


@overload
def redact_structured(value: object, *, rules: tuple[_RedactionRule, ...]) -> object: ...


def redact_structured(value: object, *, rules: tuple[_RedactionRule, ...]) -> object:
    """Recursively apply ``rules`` to every string **value** inside a structure.

    Walks dicts, lists, and tuples; redacts every string reached as a
    dict value or a list/tuple element. Non-string non-container values
    pass through unchanged. The container shape is preserved (dict stays
    dict, list stays list, tuple stays tuple). The resulting object is a
    fresh copy at every container level — the input is never mutated.

    Dict KEYS are redacted with the same rules as values. They were not,
    until a measurement found a NIF or IBAN written as a key surviving
    the observability sink in cleartext while the value beside it was
    hashed. Nothing exercised that: no payload model on this path
    declares a ``dict[str, ...]`` field today, so the gap was latent
    rather than live, and one innocently-added field would have opened
    it with nothing to catch the change.

    Redacting keys is safe here because the diagnostic rules HASH rather
    than substitute a fixed placeholder, so two distinct keys stay
    distinct. Where a rule does collapse several inputs onto one
    placeholder, :func:`_unique_mapping_key` suffixes the duplicate
    instead of overwriting it — a redacted log may not silently lose an
    entry to a key collision.

    Sets are still not walked, and that one needs no guard: every
    production caller passes ``model_dump(mode="json")``, which
    serialises a set to a LIST before it ever arrives here, and lists are
    walked. A set only reaches this function from a hand-built mapping,
    which no caller constructs.

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
        redacted: dict[object, object] = {}
        for item_key, item_value in value.items():
            redacted_key = redact_structured(item_key, rules=rules) if isinstance(item_key, str) else item_key
            redacted[_unique_mapping_key(redacted_key, redacted)] = redact_structured(item_value, rules=rules)
        return redacted
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


def _cli_placeholder_for_key(
    key: object | None,
    value: object,
    *,
    reveal_identifiers: bool = False,
) -> str | None:
    if value is None or value == "":
        return None
    normalised = _normalise_cli_key(key)
    # The profile/bucket opt-out only un-redacts the opaque profile/bucket
    # identifier surfaces; object keys (which can embed a NIF / period) and
    # every PII / token / URL pass stay redacted unconditionally.
    if not reveal_identifiers:
        if normalised in _CLI_PROFILE_ID_KEYS:
            return CLI_PROFILE_ID_PLACEHOLDER
        if normalised in _CLI_PROFILE_REFERENCE_KEYS and _is_cli_profile_reference(value):
            return CLI_PROFILE_ID_PLACEHOLDER
        if normalised in _CLI_BUCKET_ID_KEYS:
            return CLI_BUCKET_ID_PLACEHOLDER
    if normalised in _CLI_OBJECT_KEY_KEYS:
        return CLI_OBJECT_KEY_PLACEHOLDER
    return None


def _is_revealed_identifier_key(key: object | None, value: object) -> bool:
    """Whether ``key`` is an opaque profile/bucket id the reveal opt-out exposes raw.

    A revealed profile/bucket identifier is an opaque UUID and MUST pass through
    verbatim — running it through the free-text redactor would let the NIF
    pattern hash a UUID hex segment (``1470176e`` reads as 7 digits + letter)
    and corrupt the value the operator opted in to see.
    """
    if value is None or value == "":
        return False
    normalised = _normalise_cli_key(key)
    if normalised in _CLI_PROFILE_ID_KEYS or normalised in _CLI_BUCKET_ID_KEYS:
        return True
    return normalised in _CLI_PROFILE_REFERENCE_KEYS and _is_cli_profile_reference(value)


def _is_cli_tabular_header_line(text: str) -> bool:
    cells = text.split("\t")
    if len(cells) < _CLI_TABULAR_HEADER_MIN_CELLS:
        return False
    return all(_CLI_HEADER_CELL_PATTERN.fullmatch(cell) is not None for cell in cells)


def _redact_cli_string(text: str, *, reveal_identifiers: bool = False) -> str:
    # A column-header row carries no identifier values, only field names; the
    # ``label<TAB>value`` heuristic would otherwise rewrite the *next column
    # name* into a placeholder. Skip the assignment redactor for headers; the
    # remaining UUID / token passes are no-ops on bare field names.
    if _is_cli_tabular_header_line(text):
        redacted = redact_for_log(text)
        if not reveal_identifiers:
            redacted = _CLI_UUID_PATTERN.sub(CLI_PROFILE_ID_PLACEHOLDER, redacted)
        return _CLI_OBJECT_KEY_TOKEN_PATTERN.sub(CLI_OBJECT_KEY_PLACEHOLDER, redacted)
    # Under the reveal opt-out a revealed profile/bucket id is an opaque UUID
    # that must survive the downstream free-text passes verbatim — otherwise the
    # NIF pattern hashes a UUID hex segment (``1470176e`` reads as 7 digits + a
    # letter). Park each revealed value behind a NUL-delimited sentinel that
    # matches no redaction pattern, run the passes, then restore it.
    protected: list[str] = []

    def _substitute_assignment(match: re.Match[str]) -> str:
        label = match.group("label")
        value = match.group("value")
        sep = match.group("sep")
        placeholder = _cli_placeholder_for_key(label, value, reveal_identifiers=reveal_identifiers)
        if placeholder is not None:
            return f"{label}{sep}{placeholder}"
        if reveal_identifiers and _is_revealed_identifier_key(label, value):
            sentinel = f"\x00{len(protected)}\x00"
            protected.append(value)
            return f"{label}{sep}{sentinel}"
        return f"{label}{sep}{value}"

    redacted = _CLI_IDENTIFIER_ASSIGNMENT_PATTERN.sub(_substitute_assignment, text)

    def _protect_revealed_uuid(match: re.Match[str]) -> str:
        sentinel = f"\x00{len(protected)}\x00"
        protected.append(match.group(0))
        return sentinel

    # Handle complete UUIDs before the generic log redactor. Some UUID prefixes
    # also satisfy the NIF pattern (for example ``1470176e``); hashing that
    # prefix first would corrupt the placeholder into ``sha256:<profile-id>``.
    # The reveal opt-out protects the same bare-UUID surface so its value survives
    # the downstream PII pass verbatim.
    if reveal_identifiers:
        redacted = _CLI_UUID_PATTERN.sub(_protect_revealed_uuid, redacted)
    else:
        redacted = _CLI_UUID_PATTERN.sub(CLI_PROFILE_ID_PLACEHOLDER, redacted)
    redacted = redact_for_log(redacted)
    redacted = _CLI_OBJECT_KEY_TOKEN_PATTERN.sub(CLI_OBJECT_KEY_PLACEHOLDER, redacted)
    for index, original in enumerate(protected):
        redacted = redacted.replace(f"\x00{index}\x00", original)
    return redacted


def _redact_structured_for_cli_output(
    value: object,
    *,
    key: object | None = None,
    reveal_identifiers: bool = False,
) -> object:
    placeholder = _cli_placeholder_for_key(key, value, reveal_identifiers=reveal_identifiers)
    if placeholder is not None:
        return placeholder
    # A revealed profile/bucket id is an opaque UUID; emit it verbatim so the
    # free-text redactor does not hash a UUID hex segment as a NIF.
    if reveal_identifiers and _is_revealed_identifier_key(key, value):
        return value
    if isinstance(value, str):
        return _redact_cli_string(value, reveal_identifiers=reveal_identifiers)
    if isinstance(value, dict):
        redacted: dict[object, object] = {}
        for item_key, item_value in value.items():
            redacted_key = (
                _redact_cli_string(item_key, reveal_identifiers=reveal_identifiers)
                if isinstance(item_key, str)
                else item_key
            )
            unique_key = _unique_mapping_key(redacted_key, redacted)
            redacted[unique_key] = _redact_structured_for_cli_output(
                item_value,
                key=item_key,
                reveal_identifiers=reveal_identifiers,
            )
        return redacted
    if isinstance(value, list):
        return [_redact_structured_for_cli_output(item, reveal_identifiers=reveal_identifiers) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_structured_for_cli_output(item, reveal_identifiers=reveal_identifiers) for item in value)
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
    fingerprints. The :class:`core.classification.SensitivityClass`
    identity and diagnostic classes are named for at-rest identity data
    and observability sinks respectively; ``AUDIT`` is the canonical
    class for the log/error path.

    Args:
        text: The log-shaped string to redact.

    Returns:
        The redacted string.
    """
    return redact(text, rules=default_rules_for_class(_SensitivityClass.AUDIT))


def redact_validation_context(context: Mapping[str, object]) -> dict[str, object]:
    """Remove raw validation values while preserving safe diagnostic structure."""
    redacted = dict(context)
    raw = redacted.pop("raw", None)
    if raw is not None:
        redacted["raw_redacted"] = True
        redacted["raw_length"] = len(str(raw))
    detail = redacted.pop("detail", None)
    if detail is not None:
        redacted["detail_redacted"] = True
    return redacted


def redact_for_cli_output(text: str, *, reveal_identifiers: bool = False) -> str:
    """Redact a rendered operator-facing CLI output line.

    The CLI public-output profile composes the AUDIT rule set used by
    logs/errors with additional profile, bucket, and secure-object key
    handling. It deliberately keeps display labels untouched and targets
    machine identifiers, storage lookup values, URL paths, bearer tokens,
    and tax identities that should not be emitted as success output.

    Args:
        text: Rendered CLI text.
        reveal_identifiers: When ``True``, opaque profile and bucket
            identifier surfaces are emitted raw (the operator opt-out for
            multi-client disambiguation). Tax identities, tokens, URLs,
            and secure-object keys stay redacted regardless.

    Returns:
        Redacted CLI-safe text.

    Raises:
        RedactionError: When ``text`` is not a :class:`str`.
    """
    if not isinstance(text, str):
        from ..errors import RedactionError

        raise RedactionError(f"redact_for_cli_output() expects str; got {type(text).__name__}")
    return _redact_cli_string(text, reveal_identifiers=reveal_identifiers)


@overload
def redact_structured_for_cli_output[T](value: dict[str, T], *, reveal_identifiers: bool = False) -> dict[str, T]: ...


@overload
def redact_structured_for_cli_output[T](value: list[T], *, reveal_identifiers: bool = False) -> list[T]: ...


@overload
def redact_structured_for_cli_output(value: object, *, reveal_identifiers: bool = False) -> object: ...


def redact_structured_for_cli_output(value: object, *, reveal_identifiers: bool = False) -> object:
    """Recursively redact a JSON-shaped value for public CLI output.

    Unlike :func:`redact_structured`, this helper is key-aware so values
    under canonical profile, bucket, and secure-object key fields become
    stable placeholders before JSON serialization. Container shape is
    preserved and the input object is never mutated.

    Args:
        value: JSON-shaped payload to prepare for CLI success output.
        reveal_identifiers: When ``True``, opaque profile and bucket
            identifier surfaces are emitted raw (the operator opt-out for
            multi-client disambiguation). Tax identities, tokens, URLs,
            and secure-object keys stay redacted regardless.

    Returns:
        A redacted copy with the same nested shape.
    """
    return _redact_structured_for_cli_output(value, reveal_identifiers=reveal_identifiers)


__all__ = [
    "ALWAYS_REDACT_KEY_TERMS",
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
    "redact_validation_context",
]
