"""Pin the structural facts the inner-envelope equality argument rests on.

Tightening the inner-envelope check from an ordering comparison to an equality
was behaviour-identical only because the below-current region is empty AND
"current" means whatever the registry says. Neither is self-evident, and neither
was pinned anywhere, so a future change to either would silently turn a proven
no-op into a real behaviour change against filed taxpayer data.

Three legs carry the argument. One: the envelope's ``schema_version`` declares a
positive lower bound, so a below-current stamp is unrepresentable rather than
merely unseen. Two: that bound tracks the secure-object durability floor. Three:
every read path takes the version it compares against from its own namespace
definition rather than restating a literal.

Each leg is stated in the direction that can actually FAIL, which is easy to get
backwards and was gotten backwards twice while this module was written. "No
namespace sits below the envelope bound" is unfalsifiable — the namespace
definition's own field carries ``ge=1``, so the comparison is unsatisfiable by
construction. "A reader's constant equals its namespace's version" is likewise a
tautology, because every reader DEFINES its constant as that namespace's version,
so the assertion compares a value against its own definition. Both would report
green forever while proving nothing, which is exactly the vacuous-gate finding
this module's own gate is built to catch reproduced inside itself.

The relations are relations, never the literal ``1``. A per-namespace version
bump is a legitimate, expected change — the durability machinery exists to
support it — and a gate that reds on a correct change trains its reader to edit
the gate rather than read it. Leg two relates the bound to the DURABILITY FLOOR
specifically rather than to the lowest declared namespace version: those coincide
today but come apart precisely when the machinery is used as designed, since
post-flip the floor freezes while namespaces bump. The inventory does not sit on
one shared constant either — 66 namespaces declare the shared secure-object
constant and a 67th declares its own blob-manifest constant — so the value
agreement today is a coincidence rather than a shared authority, and only a
relation survives that.
"""

from __future__ import annotations

import ast
from pathlib import Path

import annotated_types
import pytest
from pydantic import BaseModel, Field

from .....tests import production_python_files, repo_relative
from ..envelope._envelope import Envelope
from ..namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..schema_lineage import SECURE_OBJECT_DURABILITY_FLOOR

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _NoLowerBound(BaseModel):
    """Stand-in whose version field carries no lower bound at all."""

    schema_version: int


class _LooseLowerBound(BaseModel):
    """Stand-in whose version field admits zero and below."""

    schema_version: int = Field(ge=-5)


def _declared_lower_bound(model: type[BaseModel], field: str) -> int:
    """Return the field's declared lower bound, refusing to invent one.

    Raising rather than defaulting is the point: a helper that fell back to a
    literal would keep reporting a healthy floor after the real constraint was
    removed, which is the failure mode this module exists to catch.
    """
    for constraint in model.model_fields[field].metadata:
        if isinstance(constraint, annotated_types.Ge):
            return int(constraint.ge)
    raise AssertionError(
        f"{model.__name__}.{field} declares no lower bound; the inner-envelope "
        "equality argument depends on one, so this is a real regression rather "
        "than a missing test fixture",
    )


def test_the_envelope_version_carries_a_positive_lower_bound() -> None:
    """Leg one: a below-current stamp must be unrepresentable, not merely unseen."""
    assert _declared_lower_bound(Envelope, "schema_version") >= 1


def test_the_envelope_bound_tracks_the_durability_floor() -> None:
    """Leg two, stated so it can actually fail AND cannot fail for the wrong reason.

    The naive form of this test — "no namespace declares a version below the
    envelope bound" — cannot fail and is worthless: the namespace definition's
    own ``schema_version`` field carries ``ge=1``, so with the envelope bound at
    1 the comparison is unsatisfiable by construction. It would report green
    forever while proving nothing.

    The direction that can fail is the opposite one: loosening the bound — to
    zero, to a negative, or by deleting the constraint — makes a below-current
    stamp representable, and the equality check then refuses payloads the old
    ordering comparison silently accepted.

    The right thing to relate that bound to is the DURABILITY FLOOR, not the
    lowest declared namespace version. The two coincide today, but they come
    apart exactly when the machinery is used as designed: post-flip the floor
    freezes while namespaces bump, and a relation against the lowest declared
    version would then red on a correct all-namespace bump — exactly the
    wrong-reason failure a durability gate must never have. The floor is also
    the semantically correct partner: it is the lowest
    version every read path keeps readable, and the field bound is the lowest
    version the payload can represent. Those are one boundary seen from two
    sides, and they must move together.
    """
    floor = _declared_lower_bound(Envelope, "schema_version")
    assert floor == SECURE_OBJECT_DURABILITY_FLOOR, (
        f"the envelope's lower bound ({floor}) no longer tracks the secure-object "
        f"durability floor ({SECURE_OBJECT_DURABILITY_FLOOR}); a bound below the floor "
        "makes a below-current inner stamp representable, and a bound above it makes "
        "rows at the floor unreadable"
    )


def test_the_namespace_inventory_is_not_empty() -> None:
    """Anti-vacuity: an empty registry would pass the inventory reads trivially."""
    assert len(STORAGE_NAMESPACE_REGISTRY.namespaces) > 0


def test_no_registered_namespace_sits_below_the_durability_floor() -> None:
    """The inventory the floor claims to cover really is at or above it."""
    below = {
        definition.namespace: definition.schema_version
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if definition.schema_version < SECURE_OBJECT_DURABILITY_FLOOR
    }
    assert below == {}, f"namespaces declare a version below the durability floor: {below}"


def test_the_bound_is_read_from_the_model_and_not_assumed() -> None:
    """Anti-tautology: prove the helper fails when the constraint is absent.

    Without this, a helper that quietly defaulted to 1 would keep both tests
    above green after someone removed the real constraint — the gate would be
    asserting its own assumption rather than the model's contract.
    """
    with pytest.raises(AssertionError, match="declares no lower bound"):
        _declared_lower_bound(_NoLowerBound, "schema_version")


def test_a_loosened_bound_is_reported_as_loosened() -> None:
    """The helper reports what the model says, including a bound that admits zero."""
    assert _declared_lower_bound(_LooseLowerBound, "schema_version") == -5


def test_a_loosened_envelope_bound_would_fail_the_floor_relation() -> None:
    """Prove the floor relation bites, by driving it with a loosened stand-in.

    Without this the relation could be silently unsatisfiable — the failure mode
    the naive form of it had. Here a model whose bound has been loosened is put
    through the same comparison the real assertion makes, and it must break.
    """
    loosened = _declared_lower_bound(_LooseLowerBound, "schema_version")
    assert loosened != SECURE_OBJECT_DURABILITY_FLOOR, (
        "the loosened stand-in now equals the durability floor, so this proof has "
        "stopped exercising the relation it guards"
    )


# --- Leg three: every reader takes its expected version from the registry ------
#
# The two legs above establish that a below-current inner stamp is
# unrepresentable. That is only half the argument. The other half is that each
# read path compares against its own namespace's DECLARED version, so "current"
# means the registry's answer rather than a number a reader remembered.
#
# This half must be pinned STRUCTURALLY, and getting that wrong is easy in the
# same way leg two was. Every reader defines its constant as
# `<NAMESPACE>.schema_version`, so asserting that the constant EQUALS the
# namespace's version compares a value against its own definition: it passes no
# matter what either holds. What can genuinely regress is the derivation being
# replaced by a restated literal, which decouples the reader from the registry
# and survives a namespace bump silently.

_PREDICATE_NAME = "inner_envelope_version_is_current"


def _module_level_version_constants(tree: ast.AST) -> set[str]:
    """Return module-level names assigned from some ``<...>.schema_version``."""
    derived: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, ast.Attribute) and value.attr == "schema_version":
            derived.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return derived


def _predicate_calls(tree: ast.AST) -> list[ast.Call]:
    """Return every call to the inner-envelope predicate in ``tree``."""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name == _PREDICATE_NAME:
            calls.append(node)
    return calls


def undelegated_version_arguments(source: str) -> list[int]:
    """Return line numbers of predicate calls whose expected version is not registry-derived."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    derived = _module_level_version_constants(tree)
    offenders: list[int] = []
    for call in _predicate_calls(tree):
        if len(call.args) < 2:
            continue
        expected = call.args[1]
        if isinstance(expected, ast.Attribute) and expected.attr == "schema_version":
            continue
        if isinstance(expected, ast.Name) and expected.id in derived:
            continue
        offenders.append(call.lineno)
    return sorted(offenders)


def _reader_sources() -> list[tuple[Path, str]]:
    readers: list[tuple[Path, str]] = []
    for path in production_python_files():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _PREDICATE_NAME in source:
            readers.append((path, source))
    return readers


def test_every_reader_takes_its_expected_version_from_the_registry() -> None:
    """Leg three: no read path restates the version it compares against."""
    offenders = [
        f"{repo_relative(path)}:{lineno}"
        for path, source in _reader_sources()
        for lineno in undelegated_version_arguments(source)
    ]
    assert offenders == [], (
        "every inner-envelope read path must take its expected version from its own "
        "SecureObjectNamespaceDefinition.schema_version, never a restated literal: a "
        "literal decouples the reader from the registry and survives a namespace bump "
        f"silently; offenders: {offenders}"
    )


_LITERAL_EXPECTED_VERSION = """
from ..storage import inner_envelope_version_is_current

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, 1)
"""

_DERIVED_VIA_MODULE_CONSTANT = """
from ..storage import CATALOGUE_NAMESPACE, inner_envelope_version_is_current

_CATALOGUE_VERSION = CATALOGUE_NAMESPACE.schema_version

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, _CATALOGUE_VERSION)
"""

_DERIVED_INLINE = """
from ..storage import CATALOGUE_NAMESPACE, inner_envelope_version_is_current

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, CATALOGUE_NAMESPACE.schema_version)
"""


def test_the_derivation_check_flags_a_restated_literal() -> None:
    """Positive control: the drift leg three exists to refuse."""
    assert undelegated_version_arguments(_LITERAL_EXPECTED_VERSION) == [5]


def test_the_derivation_check_accepts_a_namespace_derived_constant() -> None:
    """Negative control: the shape almost every real reader uses."""
    assert undelegated_version_arguments(_DERIVED_VIA_MODULE_CONSTANT) == []


def test_the_derivation_check_accepts_an_inline_namespace_attribute() -> None:
    """Negative control: the two readers that pass the namespace attribute directly."""
    assert undelegated_version_arguments(_DERIVED_INLINE) == []


def test_the_derivation_check_actually_reaches_the_read_paths() -> None:
    """Anti-vacuity: a scan that inspected nothing would report clean.

    The swept read paths must stay ON the predicate. If the scan stops finding
    them — a rename, a moved facade, a changed scan surface — leg three silently
    stops guarding anything while still passing.

    The floor was 20 when the sweep landed and is 16 now. That drop is
    CONSOLIDATION, not lost coverage, and the distinction is the whole point of
    this gate, so it is recorded rather than silently re-baselined:
    ``sede/_observation_store.py`` hand-rolled the classification-and-version
    pair at four read paths and ``profile/invoices.py`` at one; all five now
    route through :class:`SecureBoundRepository`, whose kernel in
    ``profile/_secure_enveloped_document.py`` performs the one check every
    subclass inherits. Five call sites became one, so the reads are still
    guarded — by a single shared check instead of five copies.

    The gate subsequently caught exactly what it was built for. The count fell
    to 15 because ``storage/attachment.py`` had open-coded its manifest version
    comparison as ``envelope.schema_version != _ATTACHMENT_MANIFEST_VERSION``
    beside a real call to the classification sibling. Nothing had consolidated;
    one read path had simply stopped using the shared predicate, which is
    invisible to leg three -- the expected version there was registry-derived,
    so the drift was the missing DELEGATION rather than a restated literal. The
    site now calls the predicate and keeps its own bespoke refusal, which is
    the contract the predicate is written for, and the count is 16 again.

    Lowering this floor is therefore only ever legitimate alongside evidence
    that the missing calls moved into a shared reader. A drop with no such
    consolidation is the regression this gate exists to catch: verify before
    re-baselining, never the reverse.
    """
    call_sites = sum(len(_predicate_calls(ast.parse(source))) for _, source in _reader_sources())
    assert call_sites >= 16, (
        f"expected the swept inner-envelope read paths to remain on the predicate; found {call_sites} call sites"
    )
