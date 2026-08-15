"""Gate: help prose for an enum-typed CLI option must agree with the enum.

Declaring the enum at the Typer boundary makes the *accepted set* derived from
the code, and a derived set cannot drift. The prose beside it stays hand-written,
and it does drift -- silently, because nothing structural can see it. A help
string that is well-formed, translated into four languages, and names values that
do not exist passes every other gate in this tree.

Four such strings were found by hand while adjudicating closed-value axes:

* ``--category`` advertised ``USAGE_RATIO_VEHICLE``, which exists in no casing.
* ``--kind`` on inventory movement advertised ``purchase, sale, adjustment``;
  the enum is ``opening, purchase, cogs, count``.
* ``--kind`` on ``modelo work amend`` advertised ``complementaria or
  sustitutiva`` and omitted ``rectificativa`` -- a legally distinct amendment
  under LGT art. 122 that the engine supports and the operator was told did not
  exist.
* ``--manual`` advertised ``renta, iva, sociedades``; only the first two load.

Three of the four had been wrong long enough to be translated into Catalan and
Hungarian. The omission case is the one that matters most: it does not produce a
refusal an operator can learn from, it just makes a real capability invisible.

**Why this is narrow on purpose.** A first attempt matched any member-shaped
token in the prose and was wrong every time -- English words like "non-resident"
share a stem with ``non_resident_irnr`` without claiming to be a value. What
actually separates a claim from a sentence is a *parenthetical*: ``(a, b, c)``
enumerates, ``(e.g. a)`` illustrates, and ``(a, b, ...)`` deliberately truncates.
This gate reads only parentheticals, and treats those three shapes differently.
It therefore under-detects by design; a prose claim outside a parenthetical is
invisible to it, and that is preferred to a gate authors learn to route around.
"""

from __future__ import annotations

import re
from typing import NamedTuple

import pytest

from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PARENTHETICAL = re.compile(r"\(([^)]*)\)")
#: Separators an author uses between alternatives, across the four catalogues.
_ALTERNATIVES = re.compile(r"\s*(?:,|/|\bor\b|\bo\b|\bvagy\b)\s*", re.IGNORECASE)
#: A bare value token. Hyphens are admitted: ``latest-draft`` is a real member.
_VALUE_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
#: Marks the parenthetical as illustrative rather than exhaustive.
#:
#: No trailing word boundary. Every Spanish and Catalan marker ends in a literal
#: period ("p. ej.", "p. ex."), and ``\b`` after a period only matches when a word
#: character follows immediately -- which never happens before a space. An earlier
#: draft carried that boundary, classified every es/ca example list as an
#: exhaustive enumeration, and would have sent someone off to "correct" four
#: perfectly good translations.
_ILLUSTRATIVE = re.compile(
    r"\b(e\.?g\.?|for example|example|por ejemplo|p\. ?ej\.|p\. ?ex\.|pl\.)",
    re.IGNORECASE,
)
#: Marks the enumeration as deliberately partial.
_TRUNCATED = re.compile(r"\.\.\.|…|\betc\b|\band more\b|\band others\b", re.IGNORECASE)


class ProseClaim(NamedTuple):
    """A claim the help prose makes about the accepted set."""

    kind: str
    tokens: tuple[str, ...]


def prose_claims(description: str) -> list[ProseClaim]:
    """Extract what ``description``'s parentheticals claim about a value set.

    Returns one claim per parenthetical: ``"illustrative"`` for an ``e.g.`` list,
    ``"partial"`` for one ending in an ellipsis, and ``"exhaustive"`` for a plain
    list of two or more value-shaped tokens. Anything else yields no claim, which
    is how ordinary prose stays invisible to this gate.
    """
    claims: list[ProseClaim] = []
    for body in _PARENTHETICAL.findall(description):
        if _ILLUSTRATIVE.search(body):
            tokens = tuple(
                token
                for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", body)
                if ("_" in token or token.isupper()) and len(token) > 3
            )
            if tokens:
                claims.append(ProseClaim("illustrative", tokens))
            continue
        tokens = tuple(
            token.strip(".")
            for token in _ALTERNATIVES.split(body)
            if token.strip() and _VALUE_TOKEN.match(token.strip().strip("."))
        )
        if len(tokens) < 2:
            continue
        claims.append(ProseClaim("partial" if _TRUNCATED.search(body) else "exhaustive", tokens))
    return claims


def _enum_options() -> list[tuple[str, str, tuple[str, ...], str]]:
    found: list[tuple[str, str, tuple[str, ...], str]] = []
    for descriptor in build_tool_descriptors():
        for name, spec in descriptor.input_schema.get("properties", {}).items():
            members = spec.get("enum")
            if not members or spec.get("type") != "string":
                continue
            found.append((descriptor.command_key, name, tuple(members), spec.get("description") or ""))
    return found


def test_no_help_string_names_a_value_the_enum_does_not_admit() -> None:
    """An advertised value that does not exist sends the operator into a refusal."""
    offenders: list[str] = []
    for command_key, name, members, description in _enum_options():
        member_set = {member.lower() for member in members}
        for claim in prose_claims(description):
            lowered = [token.lower() for token in claim.tokens]
            if claim.kind != "illustrative" and not any(token in member_set for token in lowered):
                continue  # a parenthetical about something other than this set
            unknown = sorted(token for token in lowered if token not in member_set)
            if unknown:
                offenders.append(f"{command_key}.{name}: help names {unknown}, accepted set is {sorted(member_set)}")
    assert not offenders, "help prose advertises values the option refuses:\n  " + "\n  ".join(offenders)


def test_an_exhaustive_help_enumeration_names_every_member() -> None:
    """A list that does not signal truncation must not hide a real capability.

    This is the ``rectificativa`` shape, and it is the quiet one: naming a subset
    produces no error for the operator to learn from, it simply makes a supported
    option invisible. An author who means to show only some values writes
    ``e.g.`` or an ellipsis, and both are honoured above.
    """
    offenders: list[str] = []
    for command_key, name, members, description in _enum_options():
        member_set = {member.lower() for member in members}
        for claim in prose_claims(description):
            if claim.kind != "exhaustive":
                continue
            lowered = {token.lower() for token in claim.tokens}
            if not lowered & member_set:
                continue
            missing = sorted(member_set - lowered)
            if missing:
                offenders.append(
                    f"{command_key}.{name}: help enumerates {sorted(lowered)} but the option also accepts {missing}"
                    " -- add them, or mark the list partial with 'e.g.' or an ellipsis"
                )
    assert not offenders, "help prose hides accepted values:\n  " + "\n  ".join(offenders)


@pytest.mark.parametrize(
    ("description", "members", "expect_unknown", "expect_missing"),
    [
        # Every case below reproduces a real mismatch once found between an
        # enum's members and its CLI help prose, kept as a concrete regression case.
        (
            "Spending category id (e.g. USAGE_RATIO_VEHICLE)",
            ("vehiculo_combustible", "asesoria_fiscal"),
            True,
            False,
        ),
        (
            "Movement kind (purchase, sale, adjustment)",
            ("opening", "purchase", "cogs", "count"),
            True,
            True,
        ),
        (
            "Legal kind of the amendment (complementaria or sustitutiva)",
            ("complementaria", "sustitutiva", "rectificativa"),
            False,
            True,
        ),
        (
            "Manual identifier (renta, iva, sociedades)",
            ("renta", "iva"),
            True,
            False,
        ),
        # Legitimate shapes that must stay silent.
        ("Spending category id (e.g. vehiculo_combustible)", ("vehiculo_combustible",), False, False),
        ("Sort by this field (date, amount, ...)", ("date", "amount", "value_date"), False, False),
        (
            "Residency (resident or non-resident) for the filing",
            ("resident_irpf", "non_resident_irnr"),
            False,
            False,
        ),
    ],
)
def test_the_detector_reproduces_the_defects_it_was_built_from(
    description: str,
    members: tuple[str, ...],
    expect_unknown: bool,
    expect_missing: bool,
) -> None:
    """Anti-tautology control: the live tree is clean, so the gate proves nothing on it.

    Both assertions above currently pass over a repaired corpus, which is exactly
    the state in which a broken detector is indistinguishable from a working one.
    These cases replay the four real defects and three legitimate shapes directly
    against the extractor, so a change that stops detecting -- or starts flagging
    ordinary prose -- fails here rather than going quiet.
    """
    member_set = {member.lower() for member in members}
    unknown: set[str] = set()
    missing: set[str] = set()
    for claim in prose_claims(description):
        lowered = {token.lower() for token in claim.tokens}
        if claim.kind == "illustrative" or lowered & member_set:
            unknown |= {token for token in lowered if token not in member_set}
        if claim.kind == "exhaustive" and lowered & member_set:
            missing |= member_set - lowered

    assert bool(unknown) is expect_unknown, f"unknown-token detection wrong for {description!r}: {sorted(unknown)}"
    assert bool(missing) is expect_missing, f"omission detection wrong for {description!r}: {sorted(missing)}"
