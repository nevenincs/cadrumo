"""Contract tests for the hex-64 redeclaration scanner.

The scanner's whole value is that it sees what a hand-listed enrolment gate
cannot, so the tests that matter are the ones proving it does not simply flag
everything (which would be indistinguishable from working, on a tree that has
real violations) and does not miss the variants that made the first census of
this concept short.

Every fixture here is an explicit source snapshot rather than a revision, so
these run independently of whatever happens to be committed.
"""

from __future__ import annotations

import pytest

from dev.identity.hex64_redeclaration_census import (
    ALLOWLIST,
    CANONICAL_HOME,
    DeclarationKind,
    census_sources,
    stale_exemptions,
    unexempted,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _sources(**modules: str) -> tuple[tuple[str, str], ...]:
    """Render keyword fixtures into the (path, source) shape the scanner takes."""
    return tuple((path.replace("__", "/"), source) for path, source in modules.items())


def test_a_redeclared_pattern_is_found() -> None:
    found = census_sources(_sources(**{"src__a.py": 'X = r"^[0-9a-f]{64}$"\n'}))
    assert len(found) == 1
    assert found[0].kind is DeclarationKind.REDECLARED_PATTERN


def test_the_reversed_character_class_is_found_too() -> None:
    # The variant that stayed invisible to the first sweep of this concept. A
    # scanner matching only one ordering answers a narrower question with an
    # identical-looking clean result.
    found = census_sources(_sources(**{"src__a.py": 'X = r"^[a-f0-9]{64}$"\n'}))
    assert len(found) == 1
    assert found[0].kind is DeclarationKind.REDECLARED_PATTERN


def test_the_shape_is_found_through_every_carrier() -> None:
    # Four carriers of this drift ship in the tree: a module constant, an inline
    # Field(pattern=), a re.compile, and a value inside a typed kwargs dict.
    # Matching the string rather than the surrounding call is what makes the
    # scanner carrier-independent, so all four must land.
    source = (
        'CONST = r"^[0-9a-f]{64}$"\n'
        'COMPILED = re.compile(r"^[0-9a-f]{64}$")\n'
        'KWARGS = {"pattern": r"^[0-9a-f]{64}$"}\n'
        "class M:\n"
        '    f: str = Field(pattern=r"^[0-9a-f]{64}$")\n'
    )
    found = census_sources(_sources(**{"src__a.py": source}))
    assert len(found) == 4
    assert {item.kind for item in found} == {DeclarationKind.REDECLARED_PATTERN}


def test_an_unpatterned_length_64_field_is_found() -> None:
    source = "class M:\n    digest: str = Field(min_length=64, max_length=64)\n"
    found = census_sources(_sources(**{"src__a.py": source}))
    assert len(found) == 1
    assert found[0].kind is DeclarationKind.UNPATTERNED_LENGTH
    assert found[0].field == "digest"


def test_the_constraint_is_found_nested_inside_annotated() -> None:
    # The constraint is routinely nested rather than assigned bare; a scanner
    # reading only the immediate value would report a clean result here.
    source = "Alias = Annotated[str, StringConstraints(min_length=64, max_length=64)]\n"
    found = census_sources(_sources(**{"src__a.py": source}))
    assert len(found) == 1
    assert found[0].kind is DeclarationKind.UNPATTERNED_LENGTH


def test_the_canonical_home_is_not_its_own_violation() -> None:
    source = 'HEX_PATTERN_64 = r"^[0-9a-f]{64}$"\n'
    assert census_sources(((CANONICAL_HOME, source),)) == ()


@pytest.mark.parametrize(
    ("label", "source"),
    (
        pytest.param(
            "named-pattern",
            "f: str = Field(min_length=64, max_length=64, pattern=HEX_PATTERN_64)\n",
            id="named-pattern",
        ),
        pytest.param(
            "literal-pattern-present",
            'f: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")\n',
            id="pattern-present",
        ),
        pytest.param("hex-16", 'X = r"^[0-9a-f]{16}$"\n', id="hex-16"),
        pytest.param("hex-128", 'X = r"^[0-9a-f]{128}$"\n', id="hex-128"),
        pytest.param("max-only", "f: str = Field(max_length=64)\n", id="max-length-only"),
        pytest.param("other-width", "f: str = Field(min_length=32, max_length=32)\n", id="other-width"),
    ),
)
def test_sites_that_are_not_violations_are_not_flagged(label: str, source: str) -> None:
    # The negative controls. Without these a scanner that flagged every string
    # or every Field call would pass every positive test above.
    found = census_sources(_sources(**{"src__a.py": source}))
    flagged = [item for item in found if item.kind is DeclarationKind.UNPATTERNED_LENGTH]
    assert flagged == [], f"{label} must not be reported as an unpatterned length-64 field"


def test_a_literal_pattern_is_still_reported_as_a_redeclaration() -> None:
    # Distinct from the case above: carrying the literal SATISFIES the
    # validation question and FAILS the drift question, so exactly one class
    # fires. Proving both at once keeps the two classes from collapsing.
    source = 'f: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")\n'
    found = census_sources(_sources(**{"src__a.py": source}))
    assert [item.kind for item in found] == [DeclarationKind.REDECLARED_PATTERN]


def test_a_module_that_does_not_parse_is_skipped_rather_than_crashing() -> None:
    assert census_sources(_sources(**{"src__a.py": "def broken(\n"})) == ()


def test_an_exemption_excuses_only_its_own_symbol() -> None:
    entry = ALLOWLIST[0]
    source = "class Other:\n    f: str = Field(min_length=64, max_length=64)\n"
    found = census_sources(((entry.path, source),))
    # Same path, different symbol: the exemption is keyed on both, so this must
    # remain open rather than inheriting the excuse of a neighbour.
    assert unexempted(found) == found


@pytest.mark.parametrize(
    ("label", "source"),
    (
        pytest.param(
            "assigned-alias",
            'Alias = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]\n',
            id="assign",
        ),
        pytest.param(
            "pep695-type-alias",
            'type Alias = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]\n',
            id="type-alias",
        ),
        pytest.param("bare-constant", 'Alias = r"^[0-9a-f]{64}$"\n', id="constant"),
    ),
)
def test_a_pattern_declaration_carries_the_name_it_is_bound_to(label: str, source: str) -> None:
    """A pattern occurrence borrows its binding, so an exemption can name it.

    The regression guard for a real bug: the scanner first reported an EMPTY
    symbol for every pattern-kind declaration, because the occurrence is found
    deep inside an expression and has no name of its own. An allowlist keyed by
    ``(path, symbol)`` could therefore never match one -- so both carve-outs
    excused nothing while reading as considered judgements.

    Keying on the line number instead would have "fixed" it and been wrong: a
    line-keyed exemption is invalidated by every edit above it and silently
    moves onto whatever later occupies the line.
    """
    found = census_sources(_sources(**{"src__a.py": source}))
    assert [item.symbol for item in found] == ["Alias"], label


def test_an_exemption_can_actually_excuse_a_pattern_declaration() -> None:
    # The end-to-end proof, and the one that fails if the binding is ever
    # dropped again: an allowlist entry naming an alias must remove that
    # alias's pattern declaration from the open set.
    from dev.identity.hex64_redeclaration_census import Exemption

    source = 'Excused = r"^[0-9a-f]{64}$"\nOpen = r"^[0-9a-f]{64}$"\n'
    found = census_sources(_sources(**{"src__a.py": source}))
    assert len(found) == 2

    excused = Exemption(path="src/a.py", symbol="Excused", reason="x" * 50)
    remaining = tuple(i for i in found if i.key() != excused.key())
    assert [i.symbol for i in remaining] == ["Open"]


def test_every_allowlist_entry_states_a_reason() -> None:
    for entry in ALLOWLIST:
        assert entry.reason.strip(), f"{entry.path}:{entry.symbol} carries no stated reason"
        assert len(entry.reason) > 40, f"{entry.path}:{entry.symbol} reason is too thin to review"


def test_a_stale_exemption_is_reported() -> None:
    # An exemption answering nothing is worse than a missing one: it reads as a
    # considered judgement about code that has moved, and widens to whatever
    # later occupies its key.
    assert stale_exemptions(()) == ALLOWLIST
