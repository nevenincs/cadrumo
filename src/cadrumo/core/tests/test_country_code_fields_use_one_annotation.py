"""A field that carries an ISO 3166 alpha-2 code uses the one annotation for it.

The sibling gate for currency exists because the manual search kept succeeding.
This one exists for the same reason and answers a narrower question, because the
country class has something currency did not: a live policy split that is
DELIBERATE on both sides and is not this gate's to settle.

``normalise_iso_3166_alpha2_jurisdiction`` REFUSES a lowercase token, and says
why -- the jurisdiction axis selects a row's regulatory-source treatment, so a
caller supplying ``"es"`` is told to declare the canonical code rather than have
one guessed. ``validate_country_code`` in the invoice domain FOLDS it, and says
why -- a counterparty's country is a label on an invoice, not a treatment
selector. Both are defended in writing.

So this gate is about the SHAPE only: two characters, stated once, through
:obj:`~core.country_code.CountryCodeAlpha2`. Whether a given site then folds or
refuses is a second axis the annotation does not carry and this gate does not
check. The shape being shared is what stops a third length bound appearing;
keeping the policies separate is what stops a de-duplication silently moving one
site onto the other's regime.

:obj:`~core.country_code.CountryCodeAlpha2` is deliberately length-only. Its own
docstring records that adding a charset check would refuse values the tree
accepts today and deserves its own evidence rather than riding in on a
consolidation. That restraint is why the sites which DO check the charset import
``COUNTRY_CODE_ALPHA2_PATTERN`` instead of re-spelling it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent.parent

_CANONICAL = {"CountryCodeAlpha2", "CountryCodeAlpha2 | None"}

#: Field names that carry an ISO 3166 alpha-2 code. Narrow on purpose: a
#: ``jurisdiction`` may be a NATIONAL/CCAA scope enum or the fixed ``ES-AEAT``
#: authority tag, neither of which is a country, and matching the name alone
#: would drag both in.
_COUNTRY_FIELD_NAMES = {
    "country_code",
    "codigo_pais",
    "pais",
    "pais_residencia_fiscal",
    "counterparty_country",
    "member_state_code",
}

#: Fields carrying a country code under a different annotation, each with the
#: reason. Every entry states a REVIEWED difference, never a placeholder.
DECLARED_EXCEPTIONS: dict[str, str] = {
    "domain/modelos/row_models.py::pais": (
        "_IsoCountryCode, the canonical length bound PLUS strip_whitespace, for "
        "the manual-entry detail rows an operator types by hand; no reason was "
        "recorded when it was introduced, so this entry is the reason -- "
        "tolerating a stray space on a typed row, and nothing else"
    ),
    "domain/modelos/row_models.py::codigo_pais": (
        "the same _IsoCountryCode alias and the same manual-entry rows as its "
        "sibling pais field above"
    ),
    "domain/calculations/registry/convenio.py::country_code": (
        "a treaty file keyed by country and authored by hand, so the anchored "
        "uppercase pattern fails the author on a sloppy code rather than "
        "accepting it; the canonical is length-only and would not"
    ),
}


def _country_fields() -> dict[str, set[str]]:
    """Map ``path::field`` -> the set of annotations declared under that name.

    A SET, not a single annotation, because one module can declare the same
    field name on several models -- ``operation_definitions.py`` carries ``pais``
    twice and ``codigo_pais`` twice. Keying to a single value let the later
    declaration overwrite the earlier one, so the gate reported whichever it
    happened to walk last and was blind to the other. A mutation probe caught
    that: a hand-spelled bound introduced on one of the two ``pais`` fields did
    not red the gate at all.

    The key stays ``path::field`` rather than gaining a line number, because an
    exception keyed by line goes stale on the next edit above it.
    """
    found: dict[str, set[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        parts = path.relative_to(_SRC).parts
        if "tests" in parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # a peer's mid-edit file is not this gate's finding
            continue
        relative = path.relative_to(_SRC).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if node.target.id not in _COUNTRY_FIELD_NAMES:
                continue
            annotation = ast.unparse(node.annotation)
            if annotation.startswith("Final["):
                continue
            # A bound can live in the ANNOTATION or in an assigned Field(), and
            # the second spelling is the one this gate would otherwise miss
            # entirely -- `country_code: str = Field(min_length=2, ...)` reads as
            # a bare str to an annotation-only scan while making exactly the
            # competing claim the gate exists to catch.
            assigned = ast.unparse(node.value) if node.value is not None else ""
            declares_a_bound = "min_length" in assigned or "max_length" in assigned or "pattern" in assigned
            # A bare `str` with no bound is a pass-through parameter or an
            # internal accumulator fed from an already-validated field, not a
            # boundary declaring its own shape.
            if annotation in {"str", "str | None"} and not declares_a_bound:
                continue
            declared = annotation if annotation not in {"str", "str | None"} else assigned
            found.setdefault(f"{relative}::{node.target.id}", set()).add(declared)
    return found


def test_every_bounded_country_field_uses_the_canonical_annotation() -> None:
    """A field that states a country-code bound must state the canonical one."""
    offenders = {
        site: sorted(annotations - _CANONICAL)
        for site, annotations in _country_fields().items()
        if not annotations <= _CANONICAL and site not in DECLARED_EXCEPTIONS
    }

    assert not offenders, (
        "these fields spell their own two-character country bound. Use "
        "core.country_code.CountryCodeAlpha2; if the site genuinely needs a "
        "different shape, record it in DECLARED_EXCEPTIONS with the reason. "
        "Note this is the SHAPE only -- whether the site folds or refuses a "
        f"lowercase code is a separate axis the annotation does not carry: {offenders}"
    )


def test_declared_exceptions_still_exist() -> None:
    """An exception whose field moved or adopted the canonical loses its entry."""
    sites = _country_fields()
    stale = sorted(site for site in DECLARED_EXCEPTIONS if site not in sites)

    assert not stale, f"these declared exceptions no longer name a bounded country field: {stale}"


def test_declared_exceptions_have_not_quietly_adopted_the_canonical() -> None:
    """An exception that now uses the canonical is stale, not a standing permission."""
    sites = _country_fields()
    redundant = sorted(site for site in DECLARED_EXCEPTIONS if sites.get(site, set()) <= _CANONICAL and site in sites)

    assert not redundant, f"these fields now use the canonical annotation and need no exception: {redundant}"


def test_every_exception_states_a_reason() -> None:
    """The judgement lives in the reason, so a placeholder is not an entry."""
    unreasoned = sorted(
        site
        for site, reason in DECLARED_EXCEPTIONS.items()
        if len(reason.strip()) < 40 or reason.strip().lower().startswith(("todo", "legacy", "temporary"))
    )

    assert not unreasoned, f"these country exceptions carry no usable reason: {unreasoned}"


def test_the_gate_finds_country_fields_at_all() -> None:
    """Anti-vacuity: an emptied vocabulary must fail rather than pass silently."""
    sites = _country_fields()

    assert len(sites) >= 10, f"only {len(sites)} bounded country fields discovered; the checks above prove little"
    assert any(annotations & _CANONICAL for annotations in sites.values()), (
        "no field uses the canonical annotation, so the gate is measuring the wrong thing"
    )
