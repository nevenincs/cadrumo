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
*chooses* which custody lifecycle answers for a taxpayer's data.  Outbound AEAT
adapters reach the retired surface too and are outside this root; they are
covered by the same replacement work and are not silently exonerated here.

Dynamic reach
-------------
A dotted module path handed to :func:`importlib.import_module` is a string, so
an AST walk over ``ImportFrom``/``Attribute``/``Name`` cannot see it, and a
delegate layer of mirror protocols and one-line forwarding functions is built
entirely out of that shape.  The detector therefore also reads string literals
passed to ``import_module`` and ``getattr``, and flags a module PATH -- not only
a symbol name -- when a dynamic or static target reaches a private submodule of
the persistence-storage substrate.

No module path under that substrate is *wholly* retired today: the
``master_key`` package hosts both the retired provider family and the live
per-bucket-session substrate (``BucketSession``, the active-session seam, the
DEK wrap, the persisted profile session).  Flagging the package path outright
would condemn the surviving half, so the retired surface stays a symbol set and
the path axis catches the ownership escape instead.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_APPLICATION_LAYER = _PACKAGE_ROOT / "application"
_SCAN_ROOT = _APPLICATION_LAYER
_STORAGE_ROOT = _PACKAGE_ROOT / "adapters" / "persistence" / "storage"

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
# matched against both absolute and relative dotted paths.
_SUBSTRATE_SEGMENTS = ("adapters", "persistence", "storage")

_DYNAMIC_IMPORT_CALLS = frozenset({"import_module"})


@dataclass(frozen=True)
class _OpenViolation:
    """A reach that is known, owned, and deliberately still standing.

    ``names`` is the exact finding set the module currently produces.  The
    declaration is compared against live output, so it expires on its own: drop
    one name and the entry is stale, drop them all and the entry must go.
    """

    reason: str
    names: frozenset[str]


# Known-open reaches, each waiting on the replacement that moves it to the
# per-profile capsule.  These are NOT exemptions: every entry is re-derived from
# the tree on each run and fails the moment it stops describing reality, so an
# entry cannot outlive the violation it declares.
_DECLARED_OPEN_VIOLATIONS: dict[str, _OpenViolation] = {
    "auth/_sessions.py": _OpenViolation(
        reason=(
            "Bucket activation still resolves the process-wide provider and binds "
            "its key to the session; it must open the session from the profile "
            "capsule's password envelope instead."
        ),
        names=frozenset({"activate_master_key_provider", "get_master_key_provider"}),
    ),
    "diagnostics.py": _OpenViolation(
        reason=(
            "The storage-health probe reports custody readiness by resolving the "
            "process-wide provider; it must read the per-profile capsule's "
            "enrolment state instead."
        ),
        names=frozenset({"get_master_key_provider"}),
    ),
    "repair_integrity.py": _OpenViolation(
        reason=(
            "Integrity repair unlocks records through the process-wide provider "
            "context; it must run inside an authenticated per-profile bucket "
            "session instead."
        ),
        names=frozenset({"get_master_key_provider"}),
    ),
}


def _production_modules(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "tests" not in path.relative_to(root).parts
        and "__pycache__" not in path.parts
        and path.name != "conftest.py"
    )


def _reaches_substrate_private(dotted: str) -> bool:
    """Report whether a dotted path reaches a private submodule of the substrate."""
    segments = [segment for segment in dotted.split(".") if segment]
    for index in range(len(segments) - len(_SUBSTRATE_SEGMENTS) + 1):
        if tuple(segments[index : index + len(_SUBSTRATE_SEGMENTS)]) != _SUBSTRATE_SEGMENTS:
            continue
        tail = segments[index + len(_SUBSTRATE_SEGMENTS) :]
        return any(segment.startswith("_") for segment in tail)
    return False


def _string_argument(node: ast.Call) -> str | None:
    for argument in node.args:
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            return argument.value
    return None


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _retired_references(source: str) -> set[str]:
    """Report every retired custody reach the source imports, reads, or calls.

    Symbol reaches are reported by bare name; a module-path reach into a private
    submodule of the persistence-storage substrate is reported as
    ``private-path:<dotted>`` so the two axes stay distinguishable in a failure
    message.
    """
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found |= {alias.name for alias in node.names} & _RETIRED_CUSTODY_NAMES
            if _reaches_substrate_private(node.module or ""):
                found.add(f"private-path:{node.module}")
        elif isinstance(node, ast.Import):
            found |= {f"private-path:{alias.name}" for alias in node.names if _reaches_substrate_private(alias.name)}
        elif isinstance(node, ast.Call):
            called = _called_name(node)
            argument = _string_argument(node)
            if argument is None:
                continue
            if called in _DYNAMIC_IMPORT_CALLS and _reaches_substrate_private(argument):
                found.add(f"private-path:{argument}")
            elif called == "getattr" and argument in _RETIRED_CUSTODY_NAMES:
                found.add(argument)
        elif isinstance(node, ast.Attribute) and node.attr in _RETIRED_CUSTODY_NAMES:
            found.add(node.attr)
        elif isinstance(node, ast.Name) and node.id in _RETIRED_CUSTODY_NAMES:
            found.add(node.id)
    return found


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
    assert _retired_references(delegating) == {"get_master_key_provider", "get_master_key"}

    laundered = (
        "from importlib import import_module\n"
        "def unlock() -> object:\n"
        '    module = import_module("cadrumo.adapters.persistence.storage.master_key")\n'
        '    return getattr(module, "get_master_key_provider")()\n'
    )
    assert _retired_references(laundered) == {"get_master_key_provider"}


def test_detector_flags_a_private_substrate_module_path() -> None:
    """The path axis: a string-built target is bound by the same ownership rule."""
    dynamic = (
        "from importlib import import_module\n"
        '_M = import_module("cadrumo.adapters.persistence.storage.master_key._master_key")\n'
    )
    assert _retired_references(dynamic) == {"private-path:cadrumo.adapters.persistence.storage.master_key._master_key"}

    relative = "from ...adapters.persistence.storage.master_key._recovery import wrap_master_key\n"
    assert _retired_references(relative) == {"private-path:adapters.persistence.storage.master_key._recovery"}

    plain = "import cadrumo.adapters.persistence.storage.master_key._master_key as _mk\n"
    assert _retired_references(plain) == {"private-path:cadrumo.adapters.persistence.storage.master_key._master_key"}

    assert _retired_references('import_module("cadrumo.adapters.persistence.storage.master_key")\n') == set()
    assert _retired_references("from ._revision_persistence import build_event\n") == set()


def test_scan_root_covers_every_sibling_package_of_the_layer() -> None:
    """Prove the ROOT, not the matcher.

    A detector fired at source it was always going to reach proves only that the
    matcher works.  The defect this gate carried was scope: the root named one
    package, so every sibling was invisible and the assertion passed by never
    looking.

    The expected membership is derived from the layer directory, never from
    ``_SCAN_ROOT``, because a root that supplies its own expectation agrees with
    itself at any width -- which is exactly how the original passed.  Narrow the
    scan back to any single package and this fails naming what went dark.
    """
    scanned = {module.resolve() for module in _production_modules(_SCAN_ROOT)}
    packages = [
        child
        for child in _APPLICATION_LAYER.iterdir()
        if child.is_dir() and child.name not in {"tests", "__pycache__"} and (child / "__init__.py").exists()
    ]
    assert len(packages) > 1, "the application layer must expose sibling packages"
    uncovered = sorted(package.name for package in packages if not any(package in module.parents for module in scanned))
    assert uncovered == [], f"scan root misses sibling application packages: {uncovered}"

    top_level = {
        child.resolve()
        for child in _APPLICATION_LAYER.iterdir()
        if child.suffix == ".py" and child.name != "conftest.py"
    }
    missing = sorted(path.name for path in top_level - scanned)
    assert missing == [], f"scan root misses top-level application modules: {missing}"


def test_scan_root_reaches_reality_outside_this_package() -> None:
    """The scope proof on real material: every declared reach is found here.

    Each declared path lies outside ``user_profile/`` -- the root this gate used
    to carry -- so the declaration set is itself the evidence that the widened
    root sees material the narrow one structurally could not.
    """
    offenders = _offenders()
    for path in _DECLARED_OPEN_VIOLATIONS:
        assert not path.startswith("user_profile/"), (
            f"{path} would have been visible to the retired package-scoped root; "
            "it proves nothing about scope and must not stand in for the proof"
        )
        assert path in offenders, (
            f"declared reach {path} was not found by the scan; either the reach is "
            "gone (delete the declaration) or the scan root no longer reaches it"
        )


def test_production_application_never_reaches_shared_master_custody() -> None:
    undeclared = {path: sorted(names) for path, names in _offenders().items() if path not in _DECLARED_OPEN_VIOLATIONS}
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
    """
    offenders = _offenders()
    drift: dict[str, str] = {}
    for path, declared in _DECLARED_OPEN_VIOLATIONS.items():
        live = offenders.get(path)
        if live is None:
            drift[path] = "no longer reaches the retired surface -- delete this declaration"
        elif live != declared.names:
            drift[path] = f"declared {sorted(declared.names)}, found {sorted(live)}"
    assert drift == {}, f"declared open violations no longer describe the tree: {drift}"


def test_declared_open_violations_state_their_reason() -> None:
    """An entry without a stated replacement is an exemption wearing a reason."""
    unreasoned = {
        path
        for path, declared in _DECLARED_OPEN_VIOLATIONS.items()
        if len(declared.reason.split()) < 12 or not {"capsule", "session"} & set(declared.reason.split())
    }
    assert unreasoned == set(), f"declared open violations must state their replacement: {sorted(unreasoned)}"
    assert all(declared.names for declared in _DECLARED_OPEN_VIOLATIONS.values()), (
        "a declaration with no names asserts nothing and can never go stale"
    )


def test_retired_names_that_still_exist_belong_to_the_retired_package() -> None:
    """Anchor the forbidden names to the surface they are named for.

    Without this, renaming the retired surface would leave the gate above
    matching nothing and passing vacuously.  It is deliberately silent once the
    names are gone entirely: the absence gate still bites on reintroduction.
    """
    misplaced: dict[str, list[str]] = {}
    for path in _STORAGE_ROOT.parent.parent.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
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
