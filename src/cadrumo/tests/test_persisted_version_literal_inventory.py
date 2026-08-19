"""Versioned-record literal gate: a fixture must bind the constant, not restate it.

A persisted record whose schema version the caller must supply has exactly one
correct source for that number: the canonical constant the writer reads. A test
that restates it as a literal is correct on the day it is written and silently
wrong on the day the version moves — and the wrongness does not announce itself,
because the read paths that reject an off-version record are the same paths that
degrade gracefully for a missing or unreadable one.

That is not hypothetical. The bucket-manifest durability floor moved to 2 while
two fixtures kept writing ``schema_version=1``. ``read_manifest`` raised for both,
and both callers treated the raise as an ordinary degraded state: the sandbox
indicator silently stopped appearing, and the profile-health probe silently
answered ``manifest_unreadable`` instead of reaching the profile record its test
was actually about. Neither failed loudly, and neither would have drifted had it
read :data:`BUCKET_MANIFEST_SCHEMA_VERSION`.

This gate closes that family rather than those two instances. It scans the test
surface for constructions of an enrolled record that pass an integer literal for
its version field, and demands the constant instead.

**Enrolment is the extension point.** :data:`VERSIONED_RECORDS` maps
``(class, field)`` to the constant that owns the number. A new persisted format
enrols here when it is born, per the compatibility-lifecycle discipline, so its
first stale fixture fails here rather than in whichever gate happens to read the
record next.

**What is deliberately NOT enrolled.** A version that is not owned by a single
canonical constant is out of scope, because there is nothing to bind to:
per-namespace secure-object versions vary by namespace, ``UserProfileRecord``
carries an inline field default, and ``ManifestKdfParams.version`` is argon2's
own protocol number (19 = ``0x13``), not a schema version at all. Enrolling any
of those would demand a binding that does not exist.

**Deliberate off-version writes are legitimate.** A lineage or refusal probe
that writes a version the reader must reject has to use a literal — binding the
constant would make it assert that the current version is rejected, which is
both false and vacuous. Those are exempt by ``(path, enclosing function)`` with
a stated reason, and :func:`test_every_exemption_names_a_live_site` fails when
an exemption stops naming a real site, so a fixed site's entry cannot rot into a
rubber stamp.

See Also:
    the UTF-8 enrollment inventory ratchet
        The same shape for bare encoding literals.
    :mod:`~tests.test_override_seam_singularity`
        The same anti-vacuity discipline: detectors are pure functions so a
        synthetic violator can prove each one still bites.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, NamedTuple

import pytest

from ._inventory import discover_test_control_modules, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path


#: ``(constructed class, version keyword)`` -> the constant that owns the number.
#:
#: Every pair is verified live by :func:`test_versioned_record_anchors_resolve`:
#: both the class and the constant must exist in the production tree, so a
#: rename cannot leave this table quietly enforcing nothing.
VERSIONED_RECORDS: dict[tuple[str, str], str] = {
    # The field carries NO default, so a caller must supply the number and can
    # therefore supply a stale one. This is where the drift that motivated the
    # gate actually happened -- the bucket manifest carried the same shape
    # until the format itself was retired, and its entry retired with it
    # rather than outliving the class :func:`test_versioned_record_anchors_resolve`
    # now has nothing to check it against.
    ("PersistedProfileSession", "schema_version"): "PROFILE_SESSION_SCHEMA_VERSION",
    # Enrolled at birth though their fields default to the constant today: a
    # later change that makes the field required would otherwise open the same
    # hole with no gate watching it.
    ("PersistedSessionMetadata", "schema_version"): "AEAT_STORAGE_STATE_SCHEMA_VERSION",
    ("ClaveMovilSessionMetadata", "schema_version"): "AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION",
    ("ClavePermanenteSessionMetadata", "schema_version"): "AEAT_CLAVE_PERMANENTE_METADATA_SCHEMA_VERSION",
}

#: ``(test path, enclosing function)`` -> why that site must write a literal.
#:
#: Keyed by enclosing function rather than by line number so an unrelated edit
#: above the site does not silently move the exemption onto a different
#: construction. A module-scope site keys on the empty string.
LITERAL_VERSION_EXEMPTIONS: dict[tuple[str, str], str] = {}
"""Empty, and that is the honest state rather than an oversight.

Every off-version write the tree currently needs already derives its number from
the constant it is testing against -- lineage probes across the enrolled formats
write forms like ``PROFILE_SESSION_SCHEMA_VERSION + 1`` rather than hardcoding
the drifted number, so they track the format exactly as a fixture should and
need no exemption.

The mechanism ships empty for the case that has not arrived yet: a probe that
genuinely must name a fixed historical version, where deriving it from the
current constant would change what the test asserts as the format moves.
"""


class LiteralVersionSite(NamedTuple):
    """One construction of an enrolled record with a literal version."""

    display_path: str
    function: str
    class_name: str
    field: str
    lineno: int
    value: int

    @property
    def exemption_key(self) -> tuple[str, str]:
        return (self.display_path, self.function)

    def format(self) -> str:
        return (
            f"  {self.display_path}:{self.lineno} (in {self.function or '<module>'}): "
            f"{self.class_name}({self.field}={self.value}) -- bind "
            f"{VERSIONED_RECORDS[self.class_name, self.field]} instead"
        )


def _enclosing_functions(tree: ast.AST) -> dict[ast.AST, str]:
    """Map every node to the name of the function lexically enclosing it.

    Innermost wins, and a nested helper reports its own name rather than its
    parent's, so an exemption keyed on a function cannot silently cover a
    different construction defined inside it.
    """
    enclosing: dict[ast.AST, str] = {}

    def descend(node: ast.AST, current: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else current
            enclosing[child] = name
            descend(child, name)

    descend(tree, "")
    return enclosing


def literal_version_sites(display_path: str, tree: ast.AST) -> list[LiteralVersionSite]:
    """Return every enrolled-record construction passing an integer-literal version.

    A pure ``(display_path, tree) -> sites`` function so the discrimination test
    below can feed it synthetic source and prove it still fires. ``True`` is an
    ``int`` in Python and is excluded explicitly; a version is never a flag.
    """
    enclosing = _enclosing_functions(tree)
    sites: list[LiteralVersionSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        class_name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", None)
        if class_name is None:
            continue
        for keyword in node.keywords:
            key = (class_name, keyword.arg)
            if keyword.arg is None or key not in VERSIONED_RECORDS:
                continue
            value = keyword.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, int) or isinstance(value.value, bool):
                continue
            sites.append(
                LiteralVersionSite(
                    display_path=display_path,
                    function=enclosing.get(node, ""),
                    class_name=class_name,
                    field=keyword.arg,
                    lineno=keyword.lineno,
                    value=value.value,
                )
            )
    return sites


def _scan(paths: Iterable[Path]) -> list[LiteralVersionSite]:
    sites: list[LiteralVersionSite] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):  # pragma: no cover - a broken module fails its own collection
            continue
        sites.extend(literal_version_sites(repo_relative(path), tree))
    return sites


def _production_names(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[set[str], set[str]]:
    """Return the class names and module-level constant names production declares."""
    classes: set[str] = set()
    constants: set[str] = set()
    for _path, tree in production_ast_items(source_tree_ast):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.add(node.name)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                constants.add(node.target.id)
            elif isinstance(node, ast.Assign):
                constants.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return classes, constants


def test_versioned_record_anchors_resolve(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every enrolled ``(class, field) -> constant`` names things production really ships.

    Pins the table to live anchors. A renamed record or constant would otherwise
    leave the gate scanning for a class nobody constructs and demanding a
    constant nobody can import -- passing while enforcing nothing.
    """
    assert VERSIONED_RECORDS, "the enrolled-record table is empty; this gate would enforce nothing"
    classes, constants = _production_names(source_tree_ast)

    missing_classes = sorted({name for name, _field in VERSIONED_RECORDS if name not in classes})
    missing_constants = sorted({constant for constant in VERSIONED_RECORDS.values() if constant not in constants})

    assert not missing_classes, f"enrolled record class(es) absent from the production tree: {missing_classes}"
    assert not missing_constants, f"enrolled version constant(s) absent from the production tree: {missing_constants}"


def test_scan_surface_is_non_empty() -> None:
    """The scan walks real test modules; an empty surface would pass vacuously."""
    assert list(discover_test_control_modules()), "test-module surface is empty; the gate would enforce nothing"


def test_no_test_constructs_a_versioned_record_with_a_literal_version() -> None:
    """A fixture must bind the canonical constant rather than restate its value."""
    offenders = [
        site for site in _scan(discover_test_control_modules()) if site.exemption_key not in LITERAL_VERSION_EXEMPTIONS
    ]

    assert not offenders, (
        f"{len(offenders)} test site(s) construct a versioned persisted record with a literal version.\n"
        "Bind the constant the writer reads, so the fixture tracks the format instead of drifting from it:\n"
        + "\n".join(sorted(site.format() for site in offenders))
        + "\n\nIf the literal IS the subject of the test (a lineage or refusal probe that must write an "
        "off-version record), add a (path, enclosing function) entry to LITERAL_VERSION_EXEMPTIONS stating why."
    )


def test_every_exemption_names_a_live_site() -> None:
    """A stale exemption is deleted, not left standing as a rubber stamp.

    An exemption that stops naming a real site is indistinguishable in the diff
    from one that still earns its place, and it silently pre-authorises the next
    literal that lands in that function.
    """
    live = {site.exemption_key for site in _scan(discover_test_control_modules())}
    stale = sorted(key for key in LITERAL_VERSION_EXEMPTIONS if key not in live)

    assert not stale, (
        "LITERAL_VERSION_EXEMPTIONS entries naming no live literal-version site:\n"
        + "\n".join(f"  {path} :: {function}" for path, function in stale)
        + "\nThe site was fixed or moved; delete the entry rather than leaving it to authorise the next one."
    )


_SYNTHETIC_VIOLATOR = """
def make_session():
    return PersistedProfileSession(bucket_id="b", schema_version=1)
"""

_SYNTHETIC_BOUND = """
def make_session():
    return PersistedProfileSession(bucket_id="b", schema_version=PROFILE_SESSION_SCHEMA_VERSION)
"""

_SYNTHETIC_UNENROLLED = """
def make_params():
    return ManifestKdfParams(version=19)
"""


def test_detector_fires_on_a_literal_and_stays_silent_on_the_bound_form() -> None:
    """The detector discriminates; it does not merely return whatever it is given.

    Fed the violating form it reports the site with its enclosing function; fed
    the bound form it reports nothing. A detector that could not distinguish the
    two would pin a false green no matter what the tree contained.
    """
    violations = literal_version_sites("synthetic.py", ast.parse(_SYNTHETIC_VIOLATOR))
    assert [(site.class_name, site.field, site.value, site.function) for site in violations] == [
        ("PersistedProfileSession", "schema_version", 1, "make_session")
    ]

    assert literal_version_sites("synthetic.py", ast.parse(_SYNTHETIC_BOUND)) == []


def test_detector_ignores_a_version_with_no_canonical_constant() -> None:
    """An unenrolled version field is not flagged, because there is nothing to bind.

    ``ManifestKdfParams.version`` is argon2's protocol number, not a schema
    version. Flagging it would demand a binding that does not exist and would
    train authors to read this gate's failures as noise.
    """
    assert literal_version_sites("synthetic.py", ast.parse(_SYNTHETIC_UNENROLLED)) == []
