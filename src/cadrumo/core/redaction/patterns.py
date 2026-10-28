"""Shared identity, credential and CLI identifier scan patterns for redaction."""

from __future__ import annotations

import re

# Separators a document prints INSIDE a tax identity. Admitted between body
# characters and never at an edge, so a run is joined only where real characters
# stand on both sides of the separator and the scan can never consume a leading
# or trailing hyphen belonging to the surrounding text.
#
# **This widens the SCAN, not the RULE.** Both admission gates below already
# normalise the span they are handed -- the core identity structural predicate
# tolerates dashes, spaces, and dots, and the NIF-IVA arm calls
# ``normalise_nif_iva`` before asking its admission gate -- so the
# separator-bearing spelling was
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
IDENTITY_SEPARATOR = r"[.\-]?"

# The prefixed arm alone admits the space, and only because two things constrain
# it that constrain no other arm: a match must begin with two letters naming a
# real Member State, and the per-State structural format then has to accept the
# whole normalised number. ``SE 556677889901`` -- the
# printed rendering this row exists for -- is caught here; the same string
# cannot be caught by the arms above, since its body carries no leading letter
# for the CIF shape and no trailing one for the personal shape.
#
# Both constraints are GATE-time, and a gate cannot defend against a SCAN that
# swallowed the identity before it ran. A space separates tokens in prose, so
# this arm's scan joins the neighbouring word to the number -- ``ESB12345674 is``
# in one direction, ``de SE556677889901`` in the other -- and the joined span
# normalises to nothing any authority recognises, so the gate correctly refuses
# it and the identity inside is never asked about. The space survives here only
# because :func:`_gated_sub` now re-reads a refused span instead of spending it;
# without that mechanism this separator MUST come out.
PREFIXED_IDENTITY_SEPARATOR = r"[ .\-]?"

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
# So the separated arm asks the admission gate, whose control-character check
# refuses every work-unit name and accepts every real printed identity, and a
# rule that can refuse belongs behind :func:`_gated_sub` like the other gated
# arms. Err-wide
# is not weakened where its claim still holds; it is withdrawn only from the
# population that disproved it.
#
# The separator after the optional X/Y/Z sits INSIDE the optional group, and
# that placement is load-bearing rather than stylistic. Written outside it, the
# group can match empty and the separator then stands at the START of the
# pattern, so the scan consumes the space in front of the number: "for example
# 12345678Z" was redacted to "for examplesha256:..." and the operator's sentence
# lost a word boundary. Found by running the shipped locale catalogues through
# the funnel, not by reading the regex.
NIF_PATTERN = r"\b(?:[XYZxyz])?\d{7,8}[A-Za-z]\b"

# The separator-bearing spelling, which a printed invoice and an OCR reading
# both produce. It also matches the unbroken form, harmlessly: the ungated arm
# above runs first and has already hashed anything of that shape, so what
# actually reaches this rule is the broken spelling.
SEPARATED_NIF_PATTERN = (
    rf"\b(?:[XYZxyz]{IDENTITY_SEPARATOR})?\d(?:{IDENTITY_SEPARATOR}\d){{6,7}}{IDENTITY_SEPARATOR}[A-Za-z]\b"
)

# CIF — the tax identity of a legal entity: a kind letter, seven digits, and a
# control character. Unlike the personal shapes above this one is LETTER-led,
# which is the same shape as an ordinary document reference (an invoice
# ``F1234567B``, a batch id), so it is paired with
# ``SHA256_PREFIX_IF_IDENTITY``: the control character decides.
# Widening the personal pattern's leading class instead would have admitted
# every such reference.
CIF_PATTERN = (
    rf"\b[A-HJNPQRSUVWa-hjnpqrsuvw]{IDENTITY_SEPARATOR}"
    rf"\d(?:{IDENTITY_SEPARATOR}\d){{6}}{IDENTITY_SEPARATOR}[0-9A-Ja-j]\b"
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
NIF_IVA_PATTERN = (
    rf"\b[A-Za-z]{PREFIXED_IDENTITY_SEPARATOR}[A-Za-z]{PREFIXED_IDENTITY_SEPARATOR}"
    rf"[0-9A-Za-z](?:{PREFIXED_IDENTITY_SEPARATOR}[0-9A-Za-z]){{1,12}}\b"
)

#: The most letters any Member State's IVA body opens with; see the gate in
#: ``_hash_if_nif_iva`` for why a longer leading run is refused.
NIF_IVA_BODY_MAX_LEADING_LETTERS = 2

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
IBAN_SEPARATOR = r"[ \-]?"
IBAN_PATTERN = rf"\b[A-Z]{{2}}{IBAN_SEPARATOR}\d{IBAN_SEPARATOR}\d(?:{IBAN_SEPARATOR}[A-Z0-9]){{11,30}}\b"

# Bearer / OAuth tokens commonly start with ``ey`` (JWT).
BEARER_PATTERN = r"(?i)\b(?:bearer\s+)?(eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})"

# Opaque (non-JWT) bearer tokens — Google's ya29 access tokens, generic
# Authorization-header bearer values, and OAuth refresh-token shapes.
# Matches the entire token (including the optional 'authorization:' /
# 'bearer ' prefix) so consumers can redact a whole header line at once.
OPAQUE_BEARER_PATTERN = (
    r"(?i)(?:authorization:\s*)?bearer\s+[A-Za-z0-9._~+/=\-]{20,}"
    r"|ya29\.[A-Za-z0-9_\-]{40,}"
)

# Generic URL pattern. Drops everything except the host component.
URL_PATTERN = r"https?://[^\s\"'<>]+"

CLI_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
)
CLI_IDENTIFIER_ASSIGNMENT_PATTERN = re.compile(
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
CLI_OBJECT_KEY_TOKEN_PATTERN = re.compile(
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
CLI_HEADER_CELL_PATTERN = re.compile(r"[a-z][a-z0-9_]*")
CLI_TABULAR_HEADER_MIN_CELLS = 3
CLI_PROFILE_ID_KEYS = frozenset(
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
CLI_PROFILE_REFERENCE_KEYS = frozenset({"active_profile"})
CLI_PUBLIC_CONTROL_UUID_KEYS = frozenset(
    {
        "request_id",
        "grant_id",
        "key_id",
        "credential_reference",
        "session_id",
        "parent_session_id",
        "target_session_id",
        "session_ids",
        "reactivated_grants",
    },
)
CLI_BUCKET_ID_KEYS = frozenset(
    {
        "active_bucket_id",
        "bucket_id",
        "repository_bucket_id",
        "storage_bucket_id",
    },
)
CLI_OBJECT_KEY_KEYS = frozenset(
    {
        "lookup_key",
        "object_key",
        "secure_object_key",
        "storage_object_key",
    },
)


#: The hashing strategies' placeholder shape, spelled once. The producers below
#: and :func:`carries_redaction_placeholder` read the same three constants, so a
#: consumer detecting a redacted value cannot drift from what redaction writes.
HASH_PLACEHOLDER_PREFIX = "sha256:"
FINGERPRINT_LABEL = "token:"
HASH_PLACEHOLDER_HEX_LENGTH = 8
HASH_PLACEHOLDER_RE = re.compile(
    rf"\b{re.escape(HASH_PLACEHOLDER_PREFIX)}[0-9a-f]{{{HASH_PLACEHOLDER_HEX_LENGTH}}}\b",
)
