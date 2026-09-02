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
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import overload
from urllib.parse import urlparse

from ..classification.policies import ClassificationPolicy as _ClassificationPolicy
from ..classification.policies import RedactionRule as _RedactionRule
from ..classification.policies import RedactionStrategy as _RedactionStrategy
from ..classification.policies import SensitivityClass as _SensitivityClass
from ..classification.policies import default_policy_for as _default_policy_for
from ..hashing import sha256_hex as _sha256_hex
from ..iban import IBAN_SHAPE_RE as _IBAN_SHAPE_RE
from ..iban import iban_mod_97 as _iban_mod_97
from ..iban import normalise_iban as _normalise_iban
from ..type_guards import is_object_dict, is_object_list, is_object_tuple

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
        "password",
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
redaction wherever one exists (see :mod:`cadrumo.core.logging`,
:mod:`cadrumo.application.live.remote_state_outcomes` and
:mod:`cadrumo.application.user_profile`), and a base that lives in only one of
those consuming sites is a base only until someone edits the other one.

``password`` sits here rather than in any one consumer because it is a generic
credential name with no domain scope. It was previously declared by the profile
overview alone, so the two other predicates — which redact a NIF, a bearer token
and a PKCS#12 blob — did not treat a key named ``password`` as sensitive at all.
That asymmetry is the exact failure the paragraph below describes, and it
survived because nothing enumerated the third consumer.

Each consuming predicate composes its own set as ``ALWAYS_REDACT_KEY_TERMS |
{domain-specific-additions}`` — never redeclares an overlapping term
independently. A term wrongly added here costs an extra scrubbed log line; a
term silently missing from one composing site can leak a NIF the other site
already knew to redact.
"""

# Separators a document prints INSIDE a tax identity. Admitted between body
# characters and never at an edge, so a run is joined only where real characters
# stand on both sides of the separator and the scan can never consume a leading
# or trailing hyphen belonging to the surrounding text.
#
# **This widens the SCAN, not the RULE.** Both admission gates below already
# normalise the span they are handed -- ``validate_identity`` documents that it
# tolerates dashes and spaces, and the NIF-IVA arm calls ``normalise_nif_iva``
# before asking the per-State table -- so the separator-bearing spelling was
# never rejected by a rule. It simply never reached one, because a scan anchored
# on unbroken word characters cannot produce a span containing a hyphen. The
# tolerant half and the intolerant half were on opposite sides of the same
# funnel.
#
# The alternative shape, matching a wider bare pattern, was rejected on the
# evidence: ``SE-2026-000412`` survives today precisely BECAUSE the hyphen
# breaks the token, so a pattern that simply admits more characters starts
# eating ordinary hyphenated operator output. Normalising and then asking the
# existing gate keeps the shape as weak evidence and the checksum or per-State
# structure as the decision, which is the arrangement this module already
# documents for the CIF and IBAN arms.
#
# **Punctuation only, and the exclusion of the space is measured rather than
# cautious.** A space is what separates TOKENS in prose, so admitting it lets the
# scan join a word to the number beside it. Running the four shipped locale
# catalogues through the funnel with the space admitted produced two real
# false positives on operator text: a Hungarian date range ``A 2020-2024``
# normalised to ``A20202024``, which is a checksum-VALID CIF and was therefore
# admitted by the gate, and ``6 000 000-t`` matched the personal-identity arm.
# Neither survives once the space is out, because no punctuation joins those
# tokens.
_IDENTITY_SEPARATOR = r"[.\-]?"

# The prefixed arm alone admits the space, and only because two things constrain
# it that constrain no other arm: a match must begin with two letters naming a
# real Member State, and the per-State structural table then has to accept the
# whole normalised number. ``SE 556677889901`` -- the printed rendering this row
# exists for -- is caught here; the same string cannot be caught by the arms
# above, since its body carries no leading letter for the CIF shape and no
# trailing one for the personal shape.
#
# Both constraints are GATE-time, and a gate cannot defend against a SCAN that
# swallowed the identity before it ran. A space separates tokens in prose, so
# this arm's scan joins the neighbouring word to the number -- ``ESB12345674 is``
# in one direction, ``de SE556677889901`` in the other -- and the joined span
# normalises to nothing any authority recognises, so the gate correctly refuses
# it and the identity inside is never asked about. The space survives here only
# because :func:`_gated_sub` now re-reads a refused span instead of spending it;
# without that mechanism this separator MUST come out.
_PREFIXED_IDENTITY_SEPARATOR = r"[ .\-]?"

# NIF / NIE — Spanish personal identity numbers. Eight digits + check letter
# with optional leading X / Y / Z for foreigners.
#
# **The personal identity is TWO rules, split by whether the span is broken by
# a separator, because the err-wide justification holds for one population and
# was falsified for the other.**
#
# The unbroken arm below is matched on shape alone and hashes a lookalike
# rather than risk missing a mistyped identity. That is bought by a specific
# claim: a digit-led run this long rarely collides with ordinary text. The
# claim is true of unbroken runs.
#
# Separators falsified it. This app's own canonical work-unit name is
# ``<modelo>-<year>-<period>``, so ``390-2026-0A`` normalises to ``39020260A``
# -- eight digits and a trailing letter, the personal-identity shape exactly.
# Every modelo id and every period token, quarterly and annual alike, lands on
# it, and an operator was handed ``modelo-sha256:44bc266f.boe`` where an export
# filename should be: a path they cannot use. Measured over the recorded
# sequence outputs, the separator-bearing population was more over-redaction
# than redaction.
#
# So the separated arm asks. ``validate_identity`` separates the two
# populations exactly -- it refuses every work-unit name and accepts every real
# printed identity -- and a rule that CAN refuse belongs behind :func:`_gated_sub`
# like the other gated arms. Err-wide is not weakened where its claim still
# holds; it is withdrawn only from the population that disproved it.
#
# The separator after the optional X/Y/Z sits INSIDE the optional group, and
# that placement is load-bearing rather than stylistic. Written outside it, the
# group can match empty and the separator then stands at the START of the
# pattern, so the scan consumes the space in front of the number: "for example
# 12345678Z" was redacted to "for examplesha256:..." and the operator's sentence
# lost a word boundary. Found by running the shipped locale catalogues through
# the funnel, not by reading the regex.
_NIF_PATTERN = r"\b(?:[XYZxyz])?\d{7,8}[A-Za-z]\b"

# The separator-bearing spelling, which a printed invoice and an OCR reading
# both produce. It also matches the unbroken form, harmlessly: the ungated arm
# above runs first and has already hashed anything of that shape, so what
# actually reaches this rule is the broken spelling.
_SEPARATED_NIF_PATTERN = (
    rf"\b(?:[XYZxyz]{_IDENTITY_SEPARATOR})?\d(?:{_IDENTITY_SEPARATOR}\d){{6,7}}{_IDENTITY_SEPARATOR}[A-Za-z]\b"
)

# CIF — the tax identity of a legal entity: a kind letter (A-H, J, N, P-S,
# U, V, W), seven digits, and a check character that is a digit or a letter
# A-J depending on the kind. Unlike the personal shapes above this one is
# LETTER-led over a fifteen-letter class, which is the same shape as an
# ordinary document reference (an invoice ``F1234567B``, a batch id), so it
# is paired with ``SHA256_PREFIX_IF_IDENTITY``: the check character decides.
# Widening the personal pattern's leading class instead would have admitted
# every such reference.
_CIF_PATTERN = (
    rf"\b[A-HJNPQRSUVWa-hjnpqrsuvw]{_IDENTITY_SEPARATOR}"
    rf"\d(?:{_IDENTITY_SEPARATOR}\d){{6}}{_IDENTITY_SEPARATOR}[0-9A-Ja-j]\b"
)

# NIF-IVA — the PREFIXED form of a tax identity, which the two rules above
# cannot see. Both anchor on `\b`, and a country prefix is a word character, so
# `ESB12345674` presents no boundary before the CIF body and the rule that
# redacts the bare `B12345674` does not fire. That is not only the foreign case:
# it is a SPANISH taxpayer's own identifier in the form this app's own
# structured readers recover and its own parsers emit.
#
# Every Member State, not just the foreign ones, for the reason the IBAN arm
# below states in the other direction: an ES-only arm protects the domestic
# spelling and leaks the prefixed one, and both name the same taxpayer.
#
# Deliberately a WIDE scan admitted by a STRICT gate, following the IBAN arm
# rather than the identity arms: two leading letters plus an alphanumeric run
# collides with hashes, opaque ids and document references, so the shape cannot
# be the evidence. `SHA256_PREFIX_IF_NIF_IVA` decides on the per-State
# structure, and a prefix naming no State admits nothing at all.
_NIF_IVA_PATTERN = (
    rf"\b[A-Za-z]{_PREFIXED_IDENTITY_SEPARATOR}[A-Za-z]{_PREFIXED_IDENTITY_SEPARATOR}"
    rf"[0-9A-Za-z](?:{_PREFIXED_IDENTITY_SEPARATOR}[0-9A-Za-z]){{1,12}}\b"
)

# IBAN — a bank account number is sensitive financial data, so it is hashed
# out of operator-facing output by operator decision. That decision is BROADER
# than this module's stated must-handle list, which names the tax-identity
# shapes and does not mention bank accounts: this arm is a deliberate
# extension, not an inference from that list. Do not narrow it back on the
# grounds that the stated list omits it.
#
# Scanning form of the anchored :data:`IBAN_SHAPE_RE` in ``core.iban``, which
# stays the authority on what an IBAN looks like. Two country letters, two
# check digits, then an 11-30 character BBAN.
#
# **The separators are the arm, not a widening of it.** An IBAN is essentially
# always PRINTED in groups of four -- that is how it leaves a bank statement and
# an invoice footer, which is exactly where this app reads one from -- so the
# separator-free spelling the arm used to require is the one that does not
# arrive. The gate does not move: the span is folded onto canonical form with
# ``normalise_iban``, the same function the registry and refund-account
# validators use, and the mod-97 checksum still decides. Admitting a space is
# safe here only because :func:`_gated_sub` re-reads a span the checksum
# refuses; a scan this wide would otherwise carry a neighbouring uppercase word
# into the match and lose the account with it.
#
# Every country, not just ES: foreign accounts are declarable (Modelo 720
# exists for assets held abroad) and refund accounts may be non-SEPA, so an
# ES-only arm would protect the domestic case and leak the foreign one. The
# breadth is safe because the mod-97 checksum, not the shape, admits the
# match — a long alphanumeric run otherwise collides with hashes and opaque
# ids, and a real 32-character hex digest in the bundled corpus is rejected
# by the checksum exactly as intended.
_IBAN_SEPARATOR = r"[ \-]?"
_IBAN_PATTERN = rf"\b[A-Z]{{2}}{_IBAN_SEPARATOR}\d{_IBAN_SEPARATOR}\d(?:{_IBAN_SEPARATOR}[A-Z0-9]){{11,30}}\b"

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
        "nif-separated-hash": _RedactionRule(
            name="nif-separated-hash",
            pattern=_SEPARATED_NIF_PATTERN,
            strategy=_RedactionStrategy.SHA256_PREFIX_IF_IDENTITY,
        ),
        "cif-hash": _RedactionRule(
            name="cif-hash",
            pattern=_CIF_PATTERN,
            strategy=_RedactionStrategy.SHA256_PREFIX_IF_IDENTITY,
        ),
        "nif-iva-hash": _RedactionRule(
            name="nif-iva-hash",
            pattern=_NIF_IVA_PATTERN,
            strategy=_RedactionStrategy.SHA256_PREFIX_IF_NIF_IVA,
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
    from ..errors.hierarchy import RedactionError

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


#: An ISO-8601 instant, matched whole. The fractional-second form is what
#: ``model_dump(mode="json")`` writes, and it collides with the identity
#: shapes: the seconds and microseconds of ``...T09:32:12.345678Z`` are seven
#: digits with separators and a trailing letter, which is a NIF, and
#: ``12345678Z`` even carries a valid check character -- so validating the
#: match cannot tell the two apart. Only the surrounding span can.
_ISO_INSTANT_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|z|[+-]\d{2}:?\d{2})?",
)


def _timestamp_spans(value: str) -> tuple[tuple[int, int], ...]:
    """Return the spans of ``value`` that are complete ISO-8601 instants."""
    return tuple(match.span() for match in _ISO_INSTANT_RE.finditer(value))


def _outside_timestamps(
    replace: Callable[[re.Match[str]], str],
    spans: tuple[tuple[int, int], ...],
) -> Callable[[re.Match[str]], str]:
    """Wrap ``replace`` so a match overlapping a timestamp is left alone.

    A timestamp is not a tax identity, an IBAN or a token, so no rule has
    anything to redact inside one. Exempting the span is safe in a way that
    narrowing the identity patterns would not be: the patterns legitimately
    allow ``.`` and ``-`` separators, and an exclusion tight enough to spare a
    microsecond field would also spare a genuine dotted identity.

    Redacting one was not cosmetic. The rewritten stamp no longer parses, so a
    model that re-validates it on the way to storage refuses the whole record.
    """

    def _replace_outside(match: re.Match[str]) -> str:
        start, end = match.span()
        if any(span_start < end and start < span_end for span_start, span_end in spans):
            return match.group(0)
        return replace(match)

    return _replace_outside


def _is_word_character(character: str) -> bool:
    return character.isalnum() or character == "_"


def _gated_sub(
    pattern: re.Pattern[str],
    value: str,
    protected: tuple[tuple[int, int], ...],
    admit: Callable[[str], str | None],
) -> str:
    """Substitute every span ``admit`` accepts, RE-READING one it refuses.

    Three arms here are deliberately built as a wide scan admitted by a strict
    gate, so that the checksum or the per-State structure decides and the shape
    is only weak evidence. :func:`re.sub` breaks that arrangement: it spends the
    span it matched whether or not the strategy rewrote it. The scan is greedy
    and its separator classes admit characters that also separate WORDS, so a
    match can carry a neighbouring word into the span. The joined span then
    normalises to something no authority recognises, the gate refuses it
    **correctly**, and the identity inside it is already consumed -- no later
    pass reaches it. The gate was never wrong; it was never asked about the
    right string.

    A refusal therefore does not end the span's life here. Candidates are tried
    longest-first from the same start, each required to end where a real token
    ends, and only once every one is refused does the scan advance a single
    character instead of past the whole match -- which lets a start further in
    (``de SE556677889901`` -> ``SE556677889901``) be reached in turn. The gate
    still decides everything; what changed is that it is consulted on every
    plausible reading of the span rather than only the greediest one.

    A span overlapping an ISO-8601 instant keeps the behaviour
    :func:`_outside_timestamps` documents: it is passed over whole, because
    nothing inside a timestamp is an identity and a rewritten stamp no longer
    parses.
    """
    out: list[str] = []
    pos = 0
    length = len(value)
    while pos < length:
        match = pattern.search(value, pos)
        if match is None:
            break
        start, end = match.span()
        if any(span_start < end and start < span_end for span_start, span_end in protected):
            out.append(value[pos:end])
            pos = max(end, start + 1)
            continue
        replacement, stop = _gated_replacement(
            pattern,
            value,
            start=start,
            end=end,
            admit=admit,
        )
        if replacement is None:
            out.append(value[pos : start + 1])
            pos = start + 1
            continue
        out.append(value[pos:start])
        out.append(replacement)
        pos = stop
    out.append(value[pos:])
    return "".join(out)


def _gated_replacement(
    pattern: re.Pattern[str],
    value: str,
    *,
    start: int,
    end: int,
    admit: Callable[[str], str | None],
) -> tuple[str | None, int]:
    """Return the longest token-bounded candidate the authority gate admits."""
    stop = end
    while stop > start:
        # ``endpos`` makes ``\b`` see an end-of-string it does not have, so a
        # candidate may not stop inside a longer opaque token.
        if stop < len(value) and _is_word_character(value[stop]):
            stop -= 1
            continue
        candidate = pattern.match(value, start, stop)
        if candidate is not None and candidate.end() == stop:
            replacement = admit(value[start:stop])
            if replacement is not None:
                return replacement, stop
        stop -= 1
    return None, stop


def _apply_one(rule: _RedactionRule, value: str) -> str:
    pattern = re.compile(rule.pattern, re.MULTILINE)
    protected = _timestamp_spans(value)

    def _sub(replace: Callable[[re.Match[str]], str]) -> str:
        return pattern.sub(_outside_timestamps(replace, protected), value)

    if rule.strategy is _RedactionStrategy.ELLIPSIS:
        return _sub(lambda m: "...")
    if rule.strategy is _RedactionStrategy.SHA256_PREFIX:
        return _sub(lambda m: _sha256_prefix(m.group(0)))
    if rule.strategy is _RedactionStrategy.SHA256_PREFIX_IF_IDENTITY:
        # Imported here, not at module scope: ``core.identity`` reaches
        # ``core.errors``, which reaches this module — the same cycle the
        # lazy ``..errors`` imports below step around.
        from ..identity import IdentityError, normalise_nif_iva, validate_identity

        def _hash_if_identity(span: str) -> str | None:
            # Normalise through the SAME function the codebase's canonical
            # same-bearer predicate uses (``same_tax_identifier``), so pattern
            # and gate agree by construction rather than by coincidence. They
            # did not: this scan admits a dot as an internal separator while
            # ``validate_identity`` strips only spaces and dashes, so the
            # printed ``B.1234567.4`` matched the scan, was refused by the gate
            # and reached the operator raw -- while ``same_tax_identifier``
            # answered that it is the very same bearer as the ``B12345674``
            # this funnel hashes.
            try:
                validate_identity(normalise_nif_iva(span))
            except IdentityError:
                return None
            return _sha256_prefix(span)

        return _gated_sub(pattern, value, protected, _hash_if_identity)
    if rule.strategy is _RedactionStrategy.SHA256_PREFIX_IF_NIF_IVA:
        # Imported at call time for the reason the identity arm above states.
        from ..identity import IdentityError, nif_iva_format_for_country, normalise_nif_iva, validate_identity

        def _hash_if_nif_iva(span: str) -> str | None:
            normalised = normalise_nif_iva(span)
            prefix, body = normalised[:2], normalised[2:]
            if prefix == "ES":
                # Spain is absent from the per-State IVA table, because its own
                # identities are the AEAT control-character authority's. So the
                # ES arm asks that authority about the BODY -- which is the
                # whole of what the prefixed spelling adds.
                try:
                    validate_identity(body)
                except IdentityError:
                    return None
                return _sha256_prefix(span)
            spec = nif_iva_format_for_country(prefix)
            if spec is None or not spec.pattern.match(normalised):
                return None
            return _sha256_prefix(span)

        return _gated_sub(pattern, value, protected, _hash_if_nif_iva)
    if rule.strategy is _RedactionStrategy.SHA256_PREFIX_IF_IBAN:

        def _hash_if_iban(span: str) -> str | None:
            canonical = _normalise_iban(span)
            if _IBAN_SHAPE_RE.match(canonical) and _iban_mod_97(canonical) == 1:
                return _sha256_prefix(span)
            return None

        return _gated_sub(pattern, value, protected, _hash_if_iban)
    if rule.strategy is _RedactionStrategy.HOST_ONLY:
        return _sub(lambda m: _host_only(m.group(0)))
    if rule.strategy is _RedactionStrategy.FINGERPRINT:
        return _sub(lambda m: _fingerprint(m.group(0)))
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
        from ..errors.hierarchy import RedactionError

        raise RedactionError(f"redact() expects str; got {type(value).__name__}")
    result = value
    for rule in rules:
        result = _apply_one(rule, result)
    return result


@overload
def redact_structured(value: dict[str, str], *, rules: tuple[_RedactionRule, ...]) -> dict[str, str]: ...


@overload
def redact_structured(value: Mapping[str, object], *, rules: tuple[_RedactionRule, ...]) -> Mapping[str, object]: ...


@overload
def redact_structured(value: list[str], *, rules: tuple[_RedactionRule, ...]) -> list[str]: ...


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
    if is_object_dict(value):
        redacted: dict[object, object] = {}
        for item_key, item_value in value.items():
            redacted_key = redact_structured(item_key, rules=rules) if isinstance(item_key, str) else item_key
            redacted[_unique_mapping_key(redacted_key, redacted)] = redact_structured(item_value, rules=rules)
        return redacted
    if is_object_list(value):
        return [redact_structured(item, rules=rules) for item in value]
    if is_object_tuple(value):
        return tuple(redact_structured(item, rules=rules) for item in value)
    return value


#: Every run of characters a sensitivity-set key name cannot contain, collapsed
#: to the single ``_`` those names separate their words with.
_REDACTION_KEY_SEPARATOR_RE = re.compile(r"[^a-z0-9]+")


def normalise_redaction_key(key: object | None) -> str:
    """Fold a payload key to the snake-case token the sensitivity sets are written in.

    Every sensitivity decision in this package and its consumers is a membership
    test against a frozenset of lower-snake-case key names, so the key has to be
    folded to that shape first. ``None`` and a key made entirely of separators
    both fold to ``""``, which matches no name in any of those sets -- the sets
    hold only non-empty tokens -- so the empty answer is "not classified" rather
    than a value a caller must branch on.

    Folding is :meth:`str.casefold`, not :meth:`str.lower`: casefold is the more
    aggressive of the two, so more spellings collapse onto the ASCII token a
    sensitivity set names. For a redaction classifier that direction is the safe
    one -- it can only make a key match a *sensitive* name it would otherwise
    have missed, never the reverse.
    """
    if key is None:
        return ""
    return _REDACTION_KEY_SEPARATOR_RE.sub("_", str(key).casefold()).strip("_")


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
    normalised = normalise_redaction_key(key)
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
    normalised = normalise_redaction_key(key)
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
    # Registry source-reference identifiers are public authority keys, not
    # taxpayer identifiers. Their validated kebab-case spelling can contain a
    # modelo/year/period segment that resembles a separated NIF; redacting that
    # segment both corrupts the identifier and violates the SourceRefId schema.
    if key in {"source_refs", "workbook_source"} and isinstance(value, str):
        return value
    placeholder = _cli_placeholder_for_key(key, value, reveal_identifiers=reveal_identifiers)
    if placeholder is not None:
        return placeholder
    # A revealed profile/bucket id is an opaque UUID; emit it verbatim so the
    # free-text redactor does not hash a UUID hex segment as a NIF.
    if reveal_identifiers and _is_revealed_identifier_key(key, value):
        return value
    if isinstance(value, str):
        return _redact_cli_string(value, reveal_identifiers=reveal_identifiers)
    if is_object_dict(value):
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
    if is_object_list(value):
        return [
            _redact_structured_for_cli_output(item, key=key, reveal_identifiers=reveal_identifiers) for item in value
        ]
    if is_object_tuple(value):
        return tuple(
            _redact_structured_for_cli_output(item, key=key, reveal_identifiers=reveal_identifiers) for item in value
        )
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
        from ..errors.hierarchy import RedactionError

        raise RedactionError(f"redact_for_cli_output() expects str; got {type(text).__name__}")
    return _redact_cli_string(text, reveal_identifiers=reveal_identifiers)


@overload
def redact_structured_for_cli_output(value: dict[str, str], *, reveal_identifiers: bool = False) -> dict[str, str]: ...


@overload
def redact_structured_for_cli_output(
    value: Mapping[str, object], *, reveal_identifiers: bool = False
) -> Mapping[str, object]: ...


@overload
def redact_structured_for_cli_output(value: list[str], *, reveal_identifiers: bool = False) -> list[str]: ...


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
