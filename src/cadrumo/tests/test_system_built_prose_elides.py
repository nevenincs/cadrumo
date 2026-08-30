"""Prose the SYSTEM assembles must elide at its cap, never refuse.

A capped prose field has two honest enforcement modes, and which one is correct
depends entirely on who wrote the string.

* **Operator-supplied** text -- a note typed at the CLI, an imported feedback
  package -- should RAISE. The operator can shorten what they wrote, the
  refusal tells them to, and silently swallowing half of a human's sentence
  would be the worse failure.
* **System-assembled** prose has no such author. Its length is a property of
  the taxpayer's data: ids, amounts, and household-sized lists interpolated
  into a sentence nobody can hold to a character budget. Refusing one converts
  a report into a crash at exactly the moment it had something to say -- a
  non-blocking advisory becomes a blocking failure, and the operator loses both
  the message and the reason for it.

So a blanket "every capped prose field elides" assertion would be wrong. This
gate asserts the conditional, and DISCOVERS which side of it each field falls
on rather than carrying a hand-written list that rots the moment a model moves.

The discriminator is measured, not declared: a field is system-assembled if
production source anywhere builds it from an f-string. That is the syntactic
signature of interpolating data into prose, and it separates the tree cleanly
--- every diagnostic, finding, and issue carrier lands on one side, while the
operator ``note`` fields, the curated help text, and the locale-key carriers
land on the other, without any of them being named here.

Elision is then checked by BEHAVIOUR, not by inspecting how a field was
declared. Each field's own annotation is rebuilt into a one-field validator and
fed an over-cap string; whether it elides or raises is the answer. A field that
acquires the property some other way still passes, which is what makes this a
gate on the guarantee rather than on the current spelling of it.

See Also:
    :mod:`cadrumo.tests.test_advisory_message_constructibility`
        The companion gate, and the source of the prose-field vocabulary this
        module reuses. That one asks whether a message can be BUILT at all;
        this one asks what happens when a built one is too long.
    :mod:`cadrumo.core.prose_elision`
        The one clamp every eliding field routes through.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import warnings
from typing import TYPE_CHECKING, Annotated

import pytest
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ..core.prose_elision import elided_prose
from .test_advisory_message_constructibility import _PROSE_FIELDS, _prose_caps

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from pydantic.fields import FieldInfo

#: A probe long enough to cross every cap the tree declares, with word breaks so
#: a boundary-aware clamp has somewhere to cut.
_OVER_CAP_PROBE = "diagnostic detail word " * 400


def _parsed_call(source: str) -> ast.Call:
    """Parse *source* as a single call expression and return it narrowed.

    The tests below read ``.keywords`` off the parsed node, which only a call
    carries. Asserting the shape here narrows the type for the checker and, more
    usefully, makes a malformed fixture fail loudly at the point it is written
    rather than as a missing attribute several lines later.
    """
    node = ast.parse(source, mode="eval").body
    assert isinstance(node, ast.Call), f"fixture is not a call expression: {source!r}"
    return node


def _declared_cap(field: FieldInfo) -> int | None:
    """Return the ``max_length`` a field declares, or ``None``."""
    for meta in getattr(field, "metadata", []) or []:
        declared = getattr(meta, "max_length", None)
        if declared is not None:
            return int(declared)
    return None


def _capped_prose_fields() -> Mapping[tuple[str, str], FieldInfo]:
    """Return ``(model name, field name) -> field`` for every capped prose field.

    Walks the live package rather than a list, so a model added tomorrow is
    covered without anyone remembering to enrol it.
    """
    warnings.filterwarnings("ignore")
    from .. import __path__ as cadrumo_path

    found: dict[tuple[str, str], FieldInfo] = {}
    for module_info in pkgutil.walk_packages(cadrumo_path, "cadrumo."):
        if ".tests" in module_info.name:
            continue
        try:
            module = importlib.import_module(module_info.name)
        except Exception:  # noqa: S112 - see below
            # A module that will not import declares no discoverable field, and
            # an optional-dependency import error is not this gate's business.
            # Swallowed rather than logged because the population and coverage
            # controls below fail loudly if enough modules drop out for the walk
            # to stop being tree-wide, which is the only consequence that matters.
            continue
        for obj in vars(module).values():
            if not (inspect.isclass(obj) and issubclass(obj, BaseModel) and obj is not BaseModel):
                continue
            for field_name, field in obj.model_fields.items():
                if field_name in _PROSE_FIELDS and _declared_cap(field) is not None:
                    found[(obj.__name__, field_name)] = field
    return found


def _builds_from_an_fstring(node: ast.AST) -> bool:
    """Whether an expression assembles a string by interpolation.

    Implicit and explicit concatenation both count: long prose is written as
    adjacent literals, and a chain whose parts include an f-string is still
    interpolated prose. A bare literal, a name, or a call is not -- those carry
    a value from somewhere else rather than composing one here.
    """
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _builds_from_an_fstring(node.left) or _builds_from_an_fstring(node.right)
    return False


def _system_built(source_tree_ast: Mapping[Path, ast.AST]) -> frozenset[tuple[str, str]]:
    """Return every ``(model, field)`` production source assembles from an f-string.

    Reads construction sites, because who writes a string is a fact about the
    call site and cannot be recovered from the model declaration alone. Test
    sources are excluded: a fixture interpolating a value proves nothing about
    what ships.
    """
    system_built: set[tuple[str, str]] = set()
    for path, tree in sorted(source_tree_ast.items()):
        if "/tests/" in path.as_posix() or path.name.startswith("test_"):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            model_name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
            if model_name is None:
                continue
            for keyword in node.keywords:
                if keyword.arg in _PROSE_FIELDS and _builds_from_an_fstring(keyword.value):
                    system_built.add((model_name, keyword.arg))
    return frozenset(system_built)


def _elides(field: FieldInfo) -> bool:
    """Whether *field* shortens an over-cap value instead of refusing it.

    Rebuilds the field's own annotation into a standalone validator so the
    question can be asked of the field alone, without constructing its whole
    model -- most of these carriers have several other required fields, and a
    gate that had to satisfy them would be testing its own fixtures.
    """
    # Built at runtime from a field's own annotation and metadata, so the
    # subscript is not a static type expression and no checker can follow it.
    # The construction is the point: it reproduces the field exactly.
    adapter = TypeAdapter(Annotated[tuple([field.annotation, *field.metadata])])  # ty: ignore[invalid-type-form]
    try:
        adapter.validate_python(_OVER_CAP_PROBE)
    except ValidationError:
        return False
    return True


@pytest.fixture(scope="module")
def capped_prose_fields() -> Mapping[tuple[str, str], FieldInfo]:
    """Every capped prose field in the tree, discovered once."""
    return _capped_prose_fields()


@pytest.fixture(scope="module")
def system_built_fields(source_tree_ast: Mapping[Path, ast.AST]) -> frozenset[tuple[str, str]]:
    """The subset production source assembles from interpolated prose."""
    return _system_built(source_tree_ast)


# ---------------------------------------------------------------------------
# Controls. These run first because every assertion below is only as meaningful
# as the corpus it runs over, and an empty corpus satisfies all of them.
# ---------------------------------------------------------------------------


def test_the_capped_prose_corpus_is_populated(capped_prose_fields: Mapping[tuple[str, str], FieldInfo]) -> None:
    """The model walk finds real fields.

    Without this the gate passes vacuously the moment the walk breaks, an
    import fails, or the prose vocabulary is renamed.
    """
    assert capped_prose_fields, (
        "no capped prose fields were discovered; the model walk is broken and every assertion below "
        "is passing over an empty set"
    )


def test_the_corpus_agrees_with_the_companion_gate(
    capped_prose_fields: Mapping[tuple[str, str], FieldInfo],
) -> None:
    """Two independent walks must see the same fields.

    The companion gate discovers the same corpus for a different question. If
    the two ever disagree, one of them is scanning less of the tree than it
    believes, and neither result can be trusted until that is resolved.
    """
    assert set(capped_prose_fields) == set(_prose_caps())


def test_the_discriminator_selects_a_proper_subset(
    capped_prose_fields: Mapping[tuple[str, str], FieldInfo],
    system_built_fields: frozenset[tuple[str, str]],
) -> None:
    """System-built is narrower than capped-prose, and not empty.

    Both ends matter. An empty set would make the main assertion vacuous; a set
    equal to the whole corpus would mean the discriminator is not discriminating
    and the gate had quietly become the blanket assertion it exists not to be.
    """
    covered = set(capped_prose_fields) & set(system_built_fields)
    assert covered, "no capped prose field was found to be system-assembled; the AST discriminator is broken"
    assert covered != set(capped_prose_fields), (
        "every capped prose field was classified as system-assembled; the discriminator is not "
        "discriminating, so operator-supplied fields would be wrongly required to elide"
    )


def test_a_known_diagnostic_carrier_is_discovered_as_system_built(
    system_built_fields: frozenset[tuple[str, str]],
) -> None:
    """Coverage reaches a member known to belong, not just some arbitrary set.

    ``CalculationSourceDiagnostic.message`` is the canonical assembled-prose
    field. A walk that missed it would still populate the corpus and still pass
    the controls above.
    """
    assert ("CalculationSourceDiagnostic", "message") in system_built_fields


def test_a_known_operator_supplied_field_is_excluded(
    system_built_fields: frozenset[tuple[str, str]],
) -> None:
    """The exclusion side, pinned to a member known to belong on it.

    ``M036DeclarationCommand.note`` is text an operator types. Requiring it to
    elide would silently swallow half of what they wrote, so the gate must not
    reach it.
    """
    assert ("M036DeclarationCommand", "note") not in system_built_fields


# ---------------------------------------------------------------------------
# The instrument, proven against synthetic subjects. These stay valid whatever
# the tree contains, which is what "it can fire" has to mean: a gate that has
# only ever been observed passing is indistinguishable from one that cannot
# fail.
# ---------------------------------------------------------------------------


class _PlainCapped(BaseModel):
    """A capped prose field with no elider -- the shape the gate must catch."""

    message: str = Field(min_length=1, max_length=64)


class _ElidingCapped(BaseModel):
    """The same field declared through the canonical elider."""

    # Declared through the factory deliberately: this class exists to prove the
    # factory form still elides. Rewriting it to the literal annotation would
    # delete the thing under test.
    message: elided_prose(64)  # ty: ignore[invalid-type-form]


def test_the_elision_probe_reports_false_for_a_field_that_refuses() -> None:
    """The negative half of the instrument, independent of the tree.

    If ``_elides`` could never return ``False`` the main assertion below would
    be unfalsifiable, and a tree full of raising fields would report clean.
    """
    assert _elides(_PlainCapped.model_fields["message"]) is False


def test_the_elision_probe_reports_true_for_a_field_that_shortens() -> None:
    """The positive half. Together with the above, the probe is proven to distinguish."""
    assert _elides(_ElidingCapped.model_fields["message"]) is True


def test_the_discriminator_recognises_interpolated_prose() -> None:
    """The AST predicate says yes to composed prose, on a subject of its own.

    Covers the plain f-string and the concatenated form separately, because
    advisory prose is normally written as adjacent literals and a predicate
    that saw only the first fragment would misclassify most of the tree.
    """
    interpolated = _parsed_call('Issue(detail=f"row {row_id} was excluded")')
    concatenated = _parsed_call('Issue(detail="row " + f"{row_id} excluded")')

    assert _builds_from_an_fstring(interpolated.keywords[0].value) is True
    assert _builds_from_an_fstring(concatenated.keywords[0].value) is True


def test_the_discriminator_rejects_prose_it_did_not_compose() -> None:
    """The predicate says no to a value that arrived from elsewhere.

    A literal, a passed-through name, and a call result are all strings the
    call site did not assemble, so none of them is evidence that the field
    carries interpolated taxpayer data.
    """
    literal = _parsed_call('Command(note="fixed text")')
    passed_through = _parsed_call("Command(note=note)")
    called = _parsed_call('Entry(description=tr("some.locale.key"))')

    assert _builds_from_an_fstring(literal.keywords[0].value) is False
    assert _builds_from_an_fstring(passed_through.keywords[0].value) is False
    assert _builds_from_an_fstring(called.keywords[0].value) is False


# ---------------------------------------------------------------------------
# The gate.
# ---------------------------------------------------------------------------


def test_every_system_built_prose_field_elides_rather_than_refusing(
    capped_prose_fields: Mapping[tuple[str, str], FieldInfo],
    system_built_fields: frozenset[tuple[str, str]],
) -> None:
    """Prose assembled from taxpayer data must shorten, never block.

    Each field here is one production code interpolates data into. Its length
    is therefore a property of the household, and no author can be expected to
    bound it in their head. A refusal turns the carrier -- a diagnostic, a
    finding, an exclusion reason -- into a raw validation error that takes the
    surrounding operation down with it, losing the message AND the reason for
    it at once.

    Fix by declaring the field through the canonical elider rather than by
    shortening the prose that tripped it: shortening postpones the failure to
    the next household large enough, while the type removes it for every
    builder present and future.
    """
    offenders = sorted(
        f"{model}.{field}"
        for (model, field), info in capped_prose_fields.items()
        if (model, field) in system_built_fields and not _elides(info)
    )
    assert offenders == [], "\n".join(
        [
            f"{len(offenders)} system-assembled prose field(s) refuse an over-cap value instead of eliding:",
            *(f"  {name}" for name in offenders),
            "Declare the field with core.elided_prose(cap) so the clamp is a property of the type.",
        ],
    )
