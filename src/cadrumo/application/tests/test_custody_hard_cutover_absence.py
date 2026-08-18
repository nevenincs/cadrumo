"""Application composition must not reach the retired shared-master surface.

The per-profile capsule owns exactly one secret lineage: a password envelope
plus an independently domain-separated recovery record.  A shared global
``master.key`` reachable from the same composition would be a second, parallel
custody lifecycle beside it -- one that answers for every profile at once and
that no per-profile refusal can gate.  The two cannot coexist without the
weaker one deciding what a taxpayer's data is protected by.

Absence is the whole assertion here, so it is checked structurally: a
behavioural test can only prove that the route it happened to walk did not take
the retired path.

Scan root
---------
The root is the whole application layer, not one package under it.  A
package-scoped root cannot see the composition move next door, and this gate
previously scanned only ``application/user_profile/`` while three sibling
application modules resolved the process-wide provider directly -- it reported
a clean tree because it never looked at them.

``src/cadrumo/`` entire is deliberately *not* the root.  The retired provider
family still has to be defined somewhere to be deleted, and the persistence
substrate that implements at-rest encryption (rotation, secret store, envelope,
blob store, encrypted columns) is its legitimate in-layer consumer while the
replacement lands.  Rooting at the package tree would make those definition and
substrate sites permanent entries in the declaration below, which is how an
absence gate degrades into an inventory nobody reads.  The application layer is
the composition boundary the assertion is actually about: it is where a caller
*chooses* which custody lifecycle answers for a taxpayer's data.

That choice is made in one other place this root does not cover, and the
exclusion is a real cost rather than a clean line.  Reaches live today in the
outbound AEAT observation store and Clave Movil client, in the outbound Google
OAuth flow, and in the command-line profile-readiness check -- the last of which
composes custody exactly as an application module does.  All four are covered by
the same replacement work; none is exonerated by sitting outside this root, and
a future revision that moves the composition boundary should widen the root
rather than let them stay unnamed.

Two nets catching disjoint sets
------------------------------
Neither net is redundant, and neither is a backstop for the other: each alone is
blind to a whole class of reach that the other is the only thing that sees.
Delete either and the gate keeps passing over real routes into the shared-master
package.

The MODULE net reports any import resolving into
``adapters/persistence/storage/master_key``, whatever symbol it names.  It is
primary because a name list can only ever assert "not these particular names",
which is a far weaker claim than "no route into the shared-master package
remains", and it loses its teeth the moment the surface is renamed or re-wrapped.
The application-owned custody module (``user_profile/_custody_ports.py``, the
successor of the dissolved forwarding port) is the worked example: it forwards
``current_active_bucket_session``, ``BucketSession.open``,
``session_serves_bucket``, ``bind_active_bucket_session`` and
``evaluate_login_throttle``, none of which a provider-family name list
contains, so a name-only gate passes it at any scan width.

The NAME net catches what the module net structurally cannot see: a reach that
imports the provider from the ``storage`` package facade, where no module path
in the source mentions ``master_key`` and only the symbol identifies where the
import resolves to.  ``auth/_sessions.py``, ``diagnostics.py`` and
``repair_integrity.py`` were all built that way, and the module net reported
every one of them clean.

**The name net now matches nothing in the application layer, and that is the
result rather than a reason to retire it.**  All three opened a shared-master
session whenever no per-profile one served the bucket: to read the active
profile's Cl@ve credentials, to print a storage-health report, and to probe
secure-object decryptability.  Each now works from the session the operator
already holds, and answers honestly without one -- empty facts and the settings
surface, a warn row carrying the profile-health verdict, and the substrate's
readiness refusal.  Their declarations expired with the reaches.

A net that currently matches nothing is exactly what an absence gate looks like
when it has succeeded; it stays because the shape it forbids is one import away
from returning, and because a name list is the only thing that would see it.

A dotted module path handed to :func:`importlib.import_module` is a string, so
an AST walk over ``ImportFrom``/``Attribute``/``Name`` cannot see it, and the
forwarding layer is built entirely out of that shape.  Both nets therefore read
string literals passed to ``import_module`` and ``getattr`` as well as static
``Import``/``ImportFrom`` targets.

A third net reports a reach into a *private* submodule anywhere under the
persistence-storage substrate, which the architecture rule binds a string-built
dynamic target to exactly as it binds a static one.

Proving the root, not the matcher
---------------------------------
An absence gate has two independent ways to lie, and only one of them is about
detection.  Proving the detector reds on material it was always going to reach
says nothing about whether it reaches the material that matters, and a scope
proof that derives its expectation from the scan root agrees with itself at any
width -- reproducing the original defect one level up.  The coverage assertion
below therefore anchors to the layer directory, which the scan root cannot
influence.  Keep it that way: it is the only part of this module that fails when
the root is wrong rather than when the matcher is.

Nothing passes here by omission
-------------------------------
``user_profile/_bundle_encryption.py`` imports ``KdfParams`` and
``derive_kek_with_params`` -- raw Argon2id parameters and KEK derivation, not
the provider seam, and arguably the least objectionable reach in the layer.  It
is declared below rather than quietly excused: the per-profile capsule derives
its own KEK, so the primitive is expected to move out of the shared-master
package with the rest of the surviving substrate.  Judging it defensible is a
decision to write down, not a reason to leave it invisible.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, fields
from pathlib import Path

import pytest

from ...core import DirectoryEntryKind, scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_APPLICATION_LAYER = _PACKAGE_ROOT / "application"
_SCAN_ROOT = _APPLICATION_LAYER
_STORAGE_ROOT = _PACKAGE_ROOT / "adapters" / "persistence" / "storage"

# Tracked material in a sibling package, read by the scope proof.  It is
# deliberately not the census of live violations: that evidence disappears when
# the cutover succeeds.
_SCOPE_FIXTURE = _APPLICATION_LAYER / "overview" / "tests" / "_custody_absence_scope_fixture.py"

# The shared-master custody surface: the provider protocol and its
# implementations, the ambient activation/resolution seam that hands a caller
# the process-wide key, and the global recovery facade that re-wrapped it.
_RETIRED_CUSTODY_NAMES = frozenset(
    {
        "MasterKeyProvider",
        "KeyringMasterKeyProvider",
        "FileFallbackMasterKeyProvider",
        "UnsecuredMasterKeyProvider",
        "get_master_key_provider",
        "activate_master_key_provider",
        "get_master_key",
        "begin_recovery",
        "complete_recovery",
    }
)

# The contiguous package segments identifying the persistence-storage substrate,
# matched against both absolute and relative dotted paths, and the shared-master
# package inside it whose every reach is reported regardless of symbol.
_SUBSTRATE_SEGMENTS = ("adapters", "persistence", "storage")
_MASTER_KEY_SEGMENTS = (*_SUBSTRATE_SEGMENTS, "master_key")

_DYNAMIC_IMPORT_CALLS = frozenset({"import_module", "__import__", "find_spec", "find_loader", "module_from_spec"})

# The symbol the module-net proof reaches through the shared-master package, and
# the facade that has to still export it.  It is pinned rather than written into
# each fixture string because the proof's whole claim is that this symbol is one
# the NAME net does not hold: borrow a name the retired list contains and the
# two nets stop being independently provable, while the failure reads as a
# detector bug rather than as a fixture that lost its property.  That is exactly
# how the proof broke -- a sweep deleting ``load_or_mint_bucket_dek`` from the
# tree rewrote its every textual occurrence, including inside this fixture's
# source string, to ``get_master_key``, which the retired list does hold.
# The anchor below asserts both halves of the property, so the next such sweep
# fails naming the symbol instead of naming a set difference.
_MASTER_KEY_FACADE = _STORAGE_ROOT / "master_key" / "__init__.py"
_SURVIVING_SUBSTRATE_SYMBOL = "current_active_bucket_session"


@dataclass(frozen=True)
class _OpenViolation:
    """A reach that is known, owned, and deliberately still standing.

    ``reaches`` is the whole declaration and every one of them must still be
    live, so the entry expires on its own: fix the reach and it reds until
    somebody deletes it.  There is deliberately no second field for reaches that
    are accepted-but-not-required.  An earlier revision carried one, to straddle
    an uncommitted edit removing some names while others stayed -- and because
    nothing checked it for staleness, it would have accepted those names on that
    one path forever once the edit landed, with nothing left that could expire.
    A declaration describes the tree it is read against; it does not hedge across
    two versions of the tree.
    """

    reason: str
    reaches: frozenset[str]


# Known-open reaches, each waiting on the replacement that moves it to the
# per-profile capsule.  These are NOT exemptions: every entry is re-derived from
# the tree on each run and fails the moment it stops describing reality, so an
# entry cannot outlive the violation it declares.
_MASTER_KEY_PACKAGE = "master-key-module:adapters.persistence.storage.master_key"
_MASTER_KEY_PACKAGE_ABSOLUTE = "master-key-module:cadrumo.adapters.persistence.storage.master_key"

_DECLARED_OPEN_VIOLATIONS: dict[str, _OpenViolation] = {
    "auth/_operator_scope.py": _OpenViolation(
        reason=(
            "Operator scoping reads the live bucket session from the shared-master "
            "package; the surviving session substrate is being renamed out of that "
            "package, and this import follows it."
        ),
        reaches=frozenset({_MASTER_KEY_PACKAGE}),
    ),
    "diagnostics.py": _OpenViolation(
        reason=(
            "The storage-health probe no longer resolves the process-wide provider "
            "to read secure state; what remains is its session-error import, which "
            "follows the surviving session substrate out of the shared-master "
            "package as the per-profile capsule takes over composition."
        ),
        reaches=frozenset({_MASTER_KEY_PACKAGE}),
    ),
    "user_profile/_custody_ports.py": _OpenViolation(
        reason=(
            "The forwarding port package was dissolved into this single "
            "application-owned module; its session forwards still reach the "
            "surviving master-key substrate (bucket session open, resume, "
            "activation and binding, the session-serves-bucket predicate, the "
            "unsecured-bucket refusal and the login throttle).  That substrate "
            "follows the per-profile capsule as it takes over composition.  The "
            "provider family and the dynamic string reach are both gone; what "
            "remains is one static import of the master-key module."
        ),
        reaches=frozenset({_MASTER_KEY_PACKAGE}),
    ),
    "user_profile/_bundle_encryption.py": _OpenViolation(
        reason=(
            "Bundle export derives its KEK with the raw Argon2id parameters from the "
            "shared-master package.  This is the primitive, not the provider seam, "
            "but the per-profile capsule derives its own KEK and the primitive moves "
            "with the surviving substrate; declared so the decision is visible."
        ),
        reaches=frozenset({_MASTER_KEY_PACKAGE}),
    ),
    "user_profile/_language_resolver.py": _OpenViolation(
        reason=(
            "Language resolution asks the shared-master package whether a bucket "
            "session is live; the predicate follows the surviving session substrate "
            "out of that package."
        ),
        reaches=frozenset({_MASTER_KEY_PACKAGE}),
    ),
}


def _production_modules(root: Path) -> list[Path]:
    return [
        path
        for path in scan_directory(root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        if "tests" not in path.relative_to(root).parts and path.name != "conftest.py"
    ]


def _tail_after(dotted: str, prefix: tuple[str, ...]) -> list[str] | None:
    """Return the segments following ``prefix``, or ``None`` if it is absent.

    Matched anywhere in the path so a relative import (``...adapters.persistence
    .storage.master_key``) and an absolute one (``cadrumo.adapters...``) resolve
    identically; the leading dots of a relative import carry no segment.
    """
    segments = [segment for segment in dotted.split(".") if segment]
    for index in range(len(segments) - len(prefix) + 1):
        if tuple(segments[index : index + len(prefix)]) == prefix:
            return segments[index + len(prefix) :]
    return None


def _module_finding(dotted: str) -> str | None:
    """Report the strongest module-path finding a dotted import target carries.

    The shared-master package is matched on the SEGMENT rather than on the full
    substrate path, so a relative dynamic target (``".master_key"`` with a
    ``package=`` anchor) reaches the same verdict as an absolute one.  Only one
    package in the tree carries that name, and an import target that names a
    second one is worth reporting anyway.
    """
    if _MASTER_KEY_SEGMENTS[-1] in [segment for segment in dotted.split(".") if segment]:
        return f"master-key-module:{dotted}"
    tail = _tail_after(dotted, _SUBSTRATE_SEGMENTS)
    if tail is not None and any(segment.startswith("_") for segment in tail):
        return f"private-path:{dotted}"
    return None


def _string_arguments(node: ast.Call) -> list[str]:
    """Return every string literal passed positionally or by keyword.

    Keywords are read because ``import_module(name="...")`` and
    ``import_module(".master_key", package="...")`` are the same reach as the
    positional form, and a matcher that scans only ``node.args`` is a spelling
    away from blind.
    """
    supplied: list[ast.expr] = [*node.args, *(keyword.value for keyword in node.keywords)]
    return [
        argument.value
        for argument in supplied
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
    ]


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _retired_references(source: str) -> set[str]:
    """Report every retired custody reach the source imports, reads, or calls.

    Module-path reaches are reported as ``master-key-module:<dotted>`` (any route
    into the shared-master package, whatever symbol it names) or
    ``private-path:<dotted>`` (a private submodule elsewhere under the substrate);
    symbol reaches are reported by bare name.  The prefixes keep the nets
    distinguishable in a failure message and in a declaration.
    """
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found |= {alias.name for alias in node.names} & _RETIRED_CUSTODY_NAMES
            module_finding = _module_finding(node.module or "")
            if module_finding is not None:
                found.add(module_finding)
            else:
                # ``from ...storage import master_key`` names the package as an
                # imported NAME, not in the module path; the most idiomatic form
                # of the reach, and invisible to a module-path-only check.
                found |= {
                    finding
                    for alias in node.names
                    if (finding := _module_finding(f"{node.module or ''}.{alias.name}")) is not None
                }
        elif isinstance(node, ast.Import):
            found |= {finding for alias in node.names if (finding := _module_finding(alias.name)) is not None}
        elif isinstance(node, ast.Call):
            called = _called_name(node)
            for argument in _string_arguments(node):
                if called in _DYNAMIC_IMPORT_CALLS and (finding := _module_finding(argument)) is not None:
                    found.add(finding)
                elif called == "getattr" and argument in _RETIRED_CUSTODY_NAMES:
                    found.add(argument)
        elif isinstance(node, ast.Attribute):
            if node.attr in _RETIRED_CUSTODY_NAMES:
                found.add(node.attr)
            elif node.attr == _MASTER_KEY_SEGMENTS[-1]:
                # ``storage.master_key.X`` after ``import ... as storage``: the
                # package is reached through an attribute chain, so no import
                # target in this file ever spells it.
                found.add(f"master-key-attribute:{node.attr}")
        elif isinstance(node, ast.Name) and node.id in _RETIRED_CUSTODY_NAMES:
            found.add(node.id)
    return found


def _facade_exports(path: Path) -> frozenset[str]:
    """Return the ``__all__`` a package facade declares, read from source.

    Read rather than imported: every other assertion in this module works on
    text, and importing the persistence substrate from an application-layer
    unit test would pull a live storage package in to answer a question about a
    name.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            return frozenset(str(exported) for exported in ast.literal_eval(node.value))
    return frozenset[str]()


def _offenders() -> dict[str, set[str]]:
    modules = _production_modules(_SCAN_ROOT)
    assert modules, "the production application tree must not be empty"
    return {
        module.relative_to(_SCAN_ROOT).as_posix(): names
        for module in modules
        if (names := _retired_references(module.read_text(encoding="utf-8")))
    }


def test_detector_reports_a_module_that_does_use_the_retired_surface() -> None:
    """Anti-tautology: the scanner must red on the shape it exists to forbid."""
    using_provider = (
        "from ...adapters.persistence.storage import get_master_key_provider\n"
        "def unlock() -> bytes:\n"
        "    return get_master_key_provider().get_master_key()\n"
    )
    assert _retired_references(using_provider) == {"get_master_key_provider", "get_master_key"}
    assert _retired_references("from ._custody_transactions import canonical_payload_digest\n") == set()


def test_detector_sees_a_retired_name_reached_through_a_dynamic_import() -> None:
    """The delegate shape hides the module behind a string, not the symbol."""
    delegating = (
        "from importlib import import_module\n"
        "def unlock() -> bytes:\n"
        '    master_key = import_module("cadrumo.adapters.persistence.storage.master_key")\n'
        "    return master_key.get_master_key_provider().get_master_key()\n"
    )
    assert _retired_references(delegating) == {
        "get_master_key_provider",
        "get_master_key",
        _MASTER_KEY_PACKAGE_ABSOLUTE,
    }

    laundered = (
        "from importlib import import_module\n"
        "def unlock() -> object:\n"
        '    module = import_module("cadrumo.adapters.persistence.storage.master_key")\n'
        '    return getattr(module, "get_master_key_provider")()\n'
    )
    assert _retired_references(laundered) == {"get_master_key_provider", _MASTER_KEY_PACKAGE_ABSOLUTE}


def test_the_package_net_fixture_symbol_names_nothing_the_name_net_holds() -> None:
    """The anchor that keeps the two nets independently provable.

    The proof below claims the module net alone catches a reach whose SYMBOL is
    invisible to a provider-family name list.  That claim rests entirely on the
    fixture's chosen symbol being live substrate rather than a retired name, and
    nothing in a set-equality assertion states that requirement -- so when a
    tree-wide sweep rewrote the symbol into the retired list, the proof asserted
    strictly less than its name claims and reported it as a detector mismatch.

    Both halves are asserted here: the symbol is one the shared-master package
    still exports, so the fixture describes a reach that can really exist, and
    it is one the name net does not hold, so the module net is the only thing
    that can see it.
    """
    assert _MASTER_KEY_FACADE.is_file(), (
        f"the shared-master facade is missing at {_MASTER_KEY_FACADE}; the fixture "
        "symbol below can no longer be anchored to a real exported surface"
    )
    exports = _facade_exports(_MASTER_KEY_FACADE)
    assert exports, "the shared-master facade declares no __all__ to anchor the fixture symbol against"
    assert _SURVIVING_SUBSTRATE_SYMBOL in exports, (
        f"{_SURVIVING_SUBSTRATE_SYMBOL} is no longer exported by the shared-master package, so the "
        "module-net proof reaches a symbol that cannot exist; pick a surviving substrate export"
    )
    assert _SURVIVING_SUBSTRATE_SYMBOL not in _RETIRED_CUSTODY_NAMES, (
        f"{_SURVIVING_SUBSTRATE_SYMBOL} is a retired custody name, so the module-net proof would also "
        "trip the name net and the two nets would no longer be independently provable"
    )
    reach = f"from ...adapters.persistence.storage.master_key import {_SURVIVING_SUBSTRATE_SYMBOL}\n"
    assert _retired_references(reach) & _RETIRED_CUSTODY_NAMES == set(), (
        "the module-net fixture trips the name net; the two nets are no longer isolated"
    )


def test_detector_flags_a_master_key_reach_that_names_no_retired_symbol() -> None:
    """The net the name list cannot supply, on every import form.

    Each source below names only surviving session substrate, so a
    provider-family name list reports every one of them clean.  This is the
    shape the forwarding layer is made of, and the reason the module net is
    primary rather than supplementary.

    Every form reaches the one symbol the anchor above holds to that property,
    so a rename cannot separate the fixtures from the requirement they rest on.
    """
    session_only = f"from ...adapters.persistence.storage.master_key import {_SURVIVING_SUBSTRATE_SYMBOL}\n"
    assert _retired_references(session_only) == {_MASTER_KEY_PACKAGE}

    attribute_reach = (
        "from importlib import import_module\n"
        "def serves() -> object:\n"
        '    module = import_module("cadrumo.adapters.persistence.storage.master_key")\n'
        f"    return module.{_SURVIVING_SUBSTRATE_SYMBOL}()\n"
    )
    assert _retired_references(attribute_reach) == {_MASTER_KEY_PACKAGE_ABSOLUTE}

    plain = "import cadrumo.adapters.persistence.storage.master_key as _mk\n"
    assert _retired_references(plain) == {_MASTER_KEY_PACKAGE_ABSOLUTE}

    submodule = "from ...adapters.persistence.storage.master_key._bucket_session import BucketSession\n"
    assert _retired_references(submodule) == {
        "master-key-module:adapters.persistence.storage.master_key._bucket_session"
    }

    sibling = "from ...adapters.persistence.storage.custody import load_capsule\n"
    assert _retired_references(sibling) == set()


def test_detector_flags_a_private_substrate_module_path() -> None:
    """The path axis: a string-built target is bound by the same ownership rule."""
    dynamic = 'import_module("cadrumo.adapters.persistence.storage.custody._capsule_discovery")\n'
    assert _retired_references(dynamic) == {
        "private-path:cadrumo.adapters.persistence.storage.custody._capsule_discovery"
    }

    relative = "from ...adapters.persistence.storage._rotation import rotate_dek\n"
    assert _retired_references(relative) == {"private-path:adapters.persistence.storage._rotation"}

    plain = "import cadrumo.adapters.persistence.storage.crypto._encrypted_columns as _cols\n"
    assert _retired_references(plain) == {"private-path:cadrumo.adapters.persistence.storage.crypto._encrypted_columns"}

    assert _retired_references("from ...adapters.persistence.storage.crypto import encrypt_record\n") == set()
    assert _retired_references("from ._revision_persistence import build_event\n") == set()


def test_scan_root_covers_every_sibling_package_of_the_layer() -> None:
    """Prove the ROOT, not the matcher.

    A detector fired at source it was always going to reach proves only that the
    matcher works.  The defect this gate carried was scope: the root named one
    package, so every sibling was invisible and the assertion passed by never
    looking.

    The expected membership is therefore derived from the layer directory, never
    from ``_SCAN_ROOT``.  A root that supplies its own expectation agrees with
    itself at any width, so a scope proof written that way reproduces the very
    failure it is meant to catch, one level up: it restates the root instead of
    checking it, and stays green while the scan narrows to nothing.  Anchoring
    the expectation to something the root cannot influence is what makes this a
    proof.  Narrow the scan back to any single package and it fails naming every
    package that went dark.
    """
    scanned = {module.resolve() for module in _production_modules(_SCAN_ROOT)}
    # Every package at every depth, not only the layer's direct children: a walk
    # capped at one level below the root leaves nested packages dark while the
    # top-level census still reads complete.
    packages = [
        directory
        for directory in scan_directory(
            _APPLICATION_LAYER,
            recursive=True,
            select=DirectoryEntryKind.DIRECTORIES,
            prune_directories=("__pycache__",),
        )
        if (directory / "__init__.py").exists() and "tests" not in directory.relative_to(_APPLICATION_LAYER).parts
    ]
    assert len(packages) > 1, "the application layer must expose sibling packages"
    uncovered = sorted(
        package.relative_to(_APPLICATION_LAYER).as_posix()
        for package in packages
        if not any(package in module.parents for module in scanned)
    )
    assert uncovered == [], f"scan root misses application packages: {uncovered}"

    top_level = {
        child.resolve()
        for child in scan_directory(_APPLICATION_LAYER)
        if child.suffix == ".py" and child.name != "conftest.py"
    }
    missing = sorted(path.name for path in top_level - scanned)
    assert missing == [], f"scan root misses top-level application modules: {missing}"


def test_scan_root_reaches_a_tracked_fixture_in_a_sibling_package() -> None:
    """The scope proof on real material that survives the cutover succeeding.

    An earlier revision anchored this to the census of live violations, asserting
    at least one declared reach lay outside ``user_profile/``.  That inverts on
    success: empty the declarations to simulate a finished cutover and the proof
    reds, so the gate could not be green in the state it exists to bring about,
    and the standing pressure was to keep one violation alive to hold the proof
    up.  A tracked fixture in a sibling package proves the same reach and does
    not expire.

    The fixture carries one reach of each shape, so a root that reaches it also
    demonstrates both nets firing on real tracked source rather than on a string
    built inside this file.
    """
    assert _SCOPE_FIXTURE.is_file(), (
        f"the scope fixture is missing at {_SCOPE_FIXTURE}; without it nothing here "
        "proves the scan root reaches a sibling package"
    )
    reached = {path.resolve() for path in scan_directory(_SCAN_ROOT, pattern="*.py", recursive=True)}
    assert _SCOPE_FIXTURE.resolve() in reached, (
        "the scan root does not reach the sibling-package fixture, so it is narrower "
        "than the application layer it claims to cover"
    )

    findings = _retired_references(_SCOPE_FIXTURE.read_text(encoding="utf-8"))
    assert any(finding.startswith("master-key-module:") for finding in findings), (
        f"the scope fixture no longer carries a module reach: {sorted(findings)}"
    )
    assert findings & _RETIRED_CUSTODY_NAMES, (
        f"the scope fixture no longer carries a provider-name reach: {sorted(findings)}"
    )

    assert _SCOPE_FIXTURE.resolve() not in {path.resolve() for path in _production_modules(_SCAN_ROOT)}, (
        "the scope fixture must stay out of the production census; it is test "
        "material and would otherwise need declaring as a violation"
    )


def test_production_application_never_reaches_shared_master_custody() -> None:
    undeclared: dict[str, list[str]] = {}
    for path, findings in _offenders().items():
        declared = _DECLARED_OPEN_VIOLATIONS.get(path)
        surplus = findings if declared is None else findings - declared.reaches
        if surplus:
            undeclared[path] = sorted(surplus)
    assert undeclared == {}, (
        "application composition must resolve secrets through the per-profile "
        f"capsule, not the retired shared-master surface: {undeclared}"
    )


def test_declared_open_violations_still_describe_the_tree() -> None:
    """The declaration cannot outlive the violation it declares.

    Each entry is re-derived from source on every run: a reach that is fixed,
    partially fixed, or relocated fails here, so the replacement work deletes the
    entry as a condition of going green rather than leaving a stale exemption
    behind.

    Every declared reach is held to that standard, with no accepted-but-not-
    required class alongside it.  A reach that is accepted without being required
    is never checked for staleness, so it survives its own fix and keeps that name
    tolerated on that path with nothing left that can expire.
    """
    offenders = _offenders()
    drift: dict[str, str] = {}
    for path, declared in _DECLARED_OPEN_VIOLATIONS.items():
        live = offenders.get(path, set())
        if not live:
            drift[path] = "no longer reaches the retired surface -- delete this declaration"
        elif stale := declared.reaches - live:
            drift[path] = f"declared reach(es) {sorted(stale)} are gone -- update or delete this declaration"
    assert drift == {}, f"declared open violations no longer describe the tree: {drift}"


def test_declared_open_violations_state_their_reason() -> None:
    """An entry without a stated replacement is an exemption wearing a reason.

    The reason must name where the reach is going -- the per-profile capsule or
    an authenticated bucket session -- because a declaration that only records
    "still open" gives the next reader nothing to act on and no way to tell a
    deferral from an abandonment.
    """
    unreasoned = {
        path
        for path, declared in _DECLARED_OPEN_VIOLATIONS.items()
        if len(declared.reason.split()) < 12
        or not any(destination in declared.reason for destination in ("capsule", "session"))
    }
    assert unreasoned == set(), f"declared open violations must state their replacement: {sorted(unreasoned)}"


def test_every_declared_reach_is_required_and_can_therefore_expire() -> None:
    """Nothing is accepted here without also being required.

    The staleness check above can only expire what the declaration REQUIRES, so
    any accepted-but-not-required class would be invisible to it and would
    outlive its own fix.  ``_OpenViolation`` carries exactly one field of reaches
    for that reason; this asserts the property directly, so re-introducing a
    second accepting field without also expiring it fails here rather than
    quietly widening the gate.
    """
    accepting_fields = {field.name for field in fields(_OpenViolation)} - {"reason"}
    assert accepting_fields == {"reaches"}, (
        f"every field that widens what the gate accepts must also be expired by the "
        f"staleness check; found {sorted(accepting_fields)}"
    )

    anchorless = sorted(path for path, declared in _DECLARED_OPEN_VIOLATIONS.items() if not declared.reaches)
    assert anchorless == [], f"declarations with no reach can never go stale: {anchorless}"


def test_retired_names_that_still_exist_belong_to_the_retired_package() -> None:
    """Anchor the forbidden names to the surface they are named for.

    Without this, renaming the retired surface would leave the gate above
    matching nothing and passing vacuously.  It is deliberately silent once the
    names are gone entirely: the absence gate still bites on reintroduction.
    """
    misplaced: dict[str, list[str]] = {}
    for path in scan_directory(
        _STORAGE_ROOT.parent.parent, pattern="*.py", recursive=True, prune_directories=("__pycache__",)
    ):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        } & _RETIRED_CUSTODY_NAMES
        if defined and (_STORAGE_ROOT / "master_key") not in path.parents:
            misplaced[path.name] = sorted(defined)
    assert misplaced == {}, f"retired custody names defined outside the retired package: {misplaced}"
