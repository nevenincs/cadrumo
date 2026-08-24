"""Real-behavior tests for the import-hygiene facade scanner.

Guards against the regression where ``discover_facades`` only recognised the
plain ``__all__ = [...]`` assignment form and silently failed to register any
``__init__.py`` using the annotated ``__all__: list[str] = [...]`` form as a
facade -- misclassifying every symbol already exported by that package as
"needs promotion" downstream.
"""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import (
    REPO_ROOT,
    FacadeInfo,
    TuiMigrationManifestError,
    TuiMigrationRowKind,
    _require_accepted_tui_migration_identities,
    _tui_migration_identity_sha256,
    discover_facades,
    dunder_all_assignment_value,
    find_shim_modules,
    find_underscore_in_all_violations,
    generate_tui_migration_manifest,
    is_underscore_named,
    tui_migration_manifest_payload,
    walk_module_imports,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_live_tui_migration_manifest_covers_declarations_exports_consumers_and_references() -> None:
    """The generated census must join the live legacy package and its reverse consumers."""
    rows = generate_tui_migration_manifest()
    assert _tui_migration_identity_sha256(rows) == ("ec3ce967729972b09bd128616ac36acf1c199ca029c4aa8abb1579599a1b0b55")
    assert all(row.owner_lane and row.replacement and row.deletion_proof.startswith("absent:") for row in rows)

    identities = {(row.kind, row.symbol, row.consumer, row.owner_lane, row.replacement) for row in rows}
    assert (
        TuiMigrationRowKind.IMPORT,
        "ManagerAction",
        "cadrumo.entrypoints.cli._config._manager_actions",
        "operations",
        "cadrumo.application.operations",
    ) in identities
    assert (
        TuiMigrationRowKind.REFERENCE,
        "FormFieldKind",
        "cadrumo.application.user_profile._overview",
        "interface",
        "cadrumo.entrypoints.tui.components.forms",
    ) in identities


def test_tui_migration_manifest_json_is_deterministic_and_complete() -> None:
    """Rendering the same live census twice must produce byte-identical JSON."""
    first = tui_migration_manifest_payload(generate_tui_migration_manifest())
    second = tui_migration_manifest_payload(generate_tui_migration_manifest())

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["row_count"] == len(first["rows"])
    assert first["legacy_package"] == ".".join(("cadrumo", "adapters", "inbound", "tui"))


def test_tui_migration_manifest_refuses_a_new_undispositioned_legacy_module(tmp_path: Path) -> None:
    """A newly introduced legacy identity must fail closed instead of growing the census."""
    src_root = tmp_path / "src"
    package_root = src_root / "cadrumo"
    legacy_root = package_root / "adapters/inbound/tui"
    legacy_root.mkdir(parents=True)
    (legacy_root / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (legacy_root / "_unowned.py").write_text("class NewLegacyIdentity: pass\n", encoding="utf-8")

    with pytest.raises(TuiMigrationManifestError, match=r"has no accepted disposition.*_unowned"):
        generate_tui_migration_manifest(
            repo_root=tmp_path,
            src_root=src_root,
            package_root=package_root,
            legacy_root=legacy_root,
        )


def test_tui_migration_manifest_refuses_an_unreadable_consumer(tmp_path: Path) -> None:
    """An invalid scanned Python file must refuse the census, never disappear from it."""
    src_root = tmp_path / "src"
    package_root = src_root / "cadrumo"
    legacy_root = package_root / "adapters/inbound/tui"
    legacy_root.mkdir(parents=True)
    (legacy_root / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    consumer = package_root / "broken_consumer.py"
    consumer.write_text("from = broken\n", encoding="utf-8")

    with pytest.raises(TuiMigrationManifestError, match=r"cannot parse TUI migration consumer.*broken_consumer"):
        generate_tui_migration_manifest(
            repo_root=tmp_path,
            src_root=src_root,
            package_root=package_root,
            legacy_root=legacy_root,
            accepted_identity_sha256=None,
        )


def test_tui_migration_manifest_refuses_a_new_symbol_or_consumer_identity(tmp_path: Path) -> None:
    """The exact identity pin must reject either side of a new migration edge."""
    repo_root = tmp_path
    src_root = repo_root / "src"
    package_root = src_root / "cadrumo"
    legacy_root = package_root / "adapters/inbound/tui"
    legacy_root.mkdir(parents=True)
    facade = legacy_root / "__init__.py"
    facade.write_text('class Existing: pass\n__all__ = ["Existing"]\n', encoding="utf-8")
    baseline = generate_tui_migration_manifest(
        repo_root=repo_root,
        src_root=src_root,
        package_root=package_root,
        legacy_root=legacy_root,
        accepted_identity_sha256=None,
    )
    accepted = _tui_migration_identity_sha256(baseline)

    facade.write_text(
        'class Existing: pass\nclass NewLegacySymbol: pass\n__all__ = ["Existing", "NewLegacySymbol"]\n',
        encoding="utf-8",
    )
    with pytest.raises(TuiMigrationManifestError, match="identities differ from the accepted exact census"):
        generate_tui_migration_manifest(
            repo_root=repo_root,
            src_root=src_root,
            package_root=package_root,
            legacy_root=legacy_root,
            accepted_identity_sha256=accepted,
        )

    facade.write_text('class Existing: pass\n__all__ = ["Existing"]\n', encoding="utf-8")
    (package_root / "new_consumer.py").write_text(
        f"from {'.'.join(('cadrumo', 'adapters', 'inbound', 'tui'))} import Existing\n",
        encoding="utf-8",
    )
    with pytest.raises(TuiMigrationManifestError, match="identities differ from the accepted exact census"):
        generate_tui_migration_manifest(
            repo_root=repo_root,
            src_root=src_root,
            package_root=package_root,
            legacy_root=legacy_root,
            accepted_identity_sha256=accepted,
        )


@pytest.mark.parametrize(
    ("field", "changed"),
    (
        ("owner_lane", "wrong-lane"),
        ("replacement", "cadrumo.wrong.destination"),
        ("deletion_proof", "absent:wrong/path.py"),
    ),
)
def test_tui_migration_manifest_refuses_disposition_drift(field: str, changed: str) -> None:
    """Every accepted owner, destination, and deletion proof is digest-bound."""
    rows = generate_tui_migration_manifest()
    accepted = _tui_migration_identity_sha256(rows)
    changed_row = replace(rows[0], **{field: changed})

    with pytest.raises(TuiMigrationManifestError, match="identities differ from the accepted exact census"):
        _require_accepted_tui_migration_identities(
            (changed_row, *rows[1:]),
            accepted_sha256=accepted,
        )


def _parse_single_statement(src: str) -> ast.stmt:
    """Parse ``src`` (one module-level statement) and return its AST node."""
    module = ast.parse(src)
    (stmt,) = module.body
    return stmt


def test_dunder_all_assignment_value_recognises_plain_form() -> None:
    """The plain ``__all__ = [...]`` assignment must yield its list value."""
    node = _parse_single_statement('__all__ = ["Foo", "Bar"]')

    value = dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_recognises_annotated_form() -> None:
    """The annotated ``__all__: list[str] = [...]`` form must also resolve."""
    node = _parse_single_statement('__all__: list[str] = ["Foo", "Bar"]')

    value = dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_ignores_unrelated_annotated_assignment() -> None:
    """An annotated assignment to a name other than ``__all__`` is not matched."""
    node = _parse_single_statement('SOME_OTHER: list[str] = ["Foo"]')

    assert dunder_all_assignment_value(node) is None


def test_dunder_all_assignment_value_ignores_bare_annotation_with_no_value() -> None:
    """A bare annotation with no assigned value (``__all__: list[str]``) is not a binding."""
    node = _parse_single_statement("__all__: list[str]")

    assert dunder_all_assignment_value(node) is None


def test_discover_facades_registers_annotated_all_init_as_a_facade() -> None:
    """``cadrumo.core`` declares ``__all__`` in the annotated form and must be discovered.

    Exercises the real ``discover_facades`` walk over the actual ``src/cadrumo``
    tree (no fixtures, no mocks) so the regression -- ``cadrumo.core`` silently
    absent from the facade set -- is caught against the live source tree.
    """
    facades = discover_facades()

    assert "cadrumo.core" in facades
    core_facade = facades["cadrumo.core"]
    assert core_facade.has_real_all is True
    assert "Modelo" in core_facade.all_names
    assert "CasillaId" in core_facade.all_names


def test_find_shim_modules_excludes_dunder_main_entrypoint_modules() -> None:
    """A standard ``__main__.py`` entrypoint module must never be classified as a shim.

    Exercises the real classifier against ``dev/locales/__main__.py`` --
    the live module whose ``from .cli import app`` plus
    ``if __name__ == "__main__": app()`` shape previously false-positived as a
    shim (zero real defs, one import statement) before the classifier learned
    to skip ``__main__.py`` modules as the standard entry-point pattern.
    """
    main_path = REPO_ROOT / "dev" / "locales" / "__main__.py"
    assert main_path.is_file()

    shims = find_shim_modules([main_path], facades={})

    assert shims == []


def test_find_shim_modules_does_not_flag_the_real_optional_dependency_fallback() -> None:
    """``_playwright.py`` defines its fallback classes inside ``if``/``try`` branches, not a shim.

    Was misclassified as ``pure_reexport_shape`` before ``module_body_defs``
    looked inside module-level ``if TYPE_CHECKING:`` / ``try: ... except
    ImportError:`` branches: its two real class definitions
    (``PlaywrightError``, ``PlaywrightTimeoutError``) sit one level below
    ``tree.body``, where the un-widened walk could not see them. Deleting
    this module as a documented Family-2 bridge would have broken
    importability for any installation without the optional ``browser``
    extra -- a regression dressed as a dedup, so this pins the live file
    against the real classifier rather than a synthetic stand-in.
    """
    playwright_path = REPO_ROOT / "src" / "cadrumo" / "adapters" / "outbound" / "aeat" / "_playwright.py"
    assert playwright_path.is_file()

    shims = find_shim_modules([playwright_path], facades={})

    assert shims == [], f"_playwright.py must not classify as a shim: {shims}"


def test_module_body_defs_sees_a_class_defined_only_inside_a_try_except_branch(tmp_path: Path) -> None:
    """The general mechanism, isolated from the real fixture: a def inside ``try``/``except`` counts.

    Constructs the minimal synthetic shape the real ``_playwright.py`` fix
    targets -- an import-only-looking module whose sole real definition sits
    inside a ``try: import real_thing / except ImportError: class
    Fallback: ...`` branch -- so this test does not depend on
    ``_playwright.py`` continuing to exist in this exact shape.
    """
    from ..quality.import_hygiene_scan import module_body_defs

    synthetic = tmp_path / "synthetic_optional_dependency_fallback.py"
    synthetic.write_text(
        "from __future__ import annotations\n"
        "try:\n"
        "    from somewhere import RealThing as Thing\n"
        "except ImportError:\n"
        "    class Thing:\n"
        '        """Fallback used only when the optional dependency is absent."""\n'
        "\n"
        '__all__ = ["Thing"]\n',
        encoding="utf-8",
    )

    tree = ast.parse(synthetic.read_text(encoding="utf-8"))
    n_imports, n_defs, n_all = module_body_defs(tree)

    assert n_defs == 1, "a class defined only inside a try/except branch must count as a real def"
    assert n_imports == 1
    assert n_all == 1


def test_module_body_defs_still_ignores_a_bare_alias_inside_a_conditional_branch(tmp_path: Path) -> None:
    """Widening the walk into branches must not start counting bare aliases as real defs.

    ``Foo = Bar`` is a re-export alias whether it sits at the top level or
    inside an ``if``/``try`` branch; the bare-``Name``/``Attribute`` exclusion
    in :func:`module_body_defs` must apply identically in both places, or the
    branch-flattening fix would itself manufacture false negatives (a genuine
    shim built entirely from conditional aliases escaping detection).
    """
    from ..quality.import_hygiene_scan import module_body_defs

    synthetic = tmp_path / "synthetic_conditional_alias_only.py"
    synthetic.write_text(
        "from __future__ import annotations\n"
        "import sys\n"
        "from . import _windows_impl, _posix_impl\n"
        "if sys.platform == 'win32':\n"
        "    impl = _windows_impl\n"
        "else:\n"
        "    impl = _posix_impl\n"
        "\n"
        '__all__ = ["impl"]\n',
        encoding="utf-8",
    )

    tree = ast.parse(synthetic.read_text(encoding="utf-8"))
    _n_imports, n_defs, _n_all = module_body_defs(tree)

    assert n_defs == 0, "a platform-branch bare-Name alias is still an alias, not a real def"


def test_walk_module_imports_tolerates_file_removed_after_discovery(tmp_path: Path) -> None:
    """A generated module removed after discovery is not a scanner failure."""
    generated = tmp_path / "generated_test_module.py"
    generated.write_text("from pathlib import Path\n", encoding="utf-8")
    generated.unlink()

    assert walk_module_imports(generated) == []


def test_find_shim_modules_tolerates_file_removed_after_discovery(tmp_path: Path) -> None:
    """Shim classification ignores only a path that genuinely vanished."""
    generated = tmp_path / "generated_test_module.py"
    generated.write_text("from pathlib import Path\n", encoding="utf-8")
    generated.unlink()

    assert find_shim_modules([generated], facades={}) == []


def test_is_underscore_named_flags_leading_underscore_but_not_dunders() -> None:
    """A leading-underscore identifier is private-convention; a dunder is not."""
    assert is_underscore_named("_private_helper") is True
    assert is_underscore_named("__all__") is False
    assert is_underscore_named("__init__") is False
    assert is_underscore_named("public_name") is False


def test_find_underscore_in_all_violations_flags_a_private_named_export() -> None:
    """A facade whose ``__all__`` contains a leading-underscore name is flagged.

    Real-behavior fixture: a synthetic :class:`FacadeInfo` standing in for a
    parsed ``__init__.py`` (the detector operates purely on the already-parsed
    facade inventory ``discover_facades`` produces, so no file I/O is needed to
    exercise the finder's own logic).
    """
    facades = {
        "cadrumo.fixture_pkg": FacadeInfo(
            package="cadrumo.fixture_pkg",
            path=REPO_ROOT / "src" / "cadrumo" / "fixture_pkg" / "__init__.py",
            all_names=["PublicThing", "_private_helper", "__all__"],
            has_real_all=True,
        ),
        "cadrumo.clean_pkg": FacadeInfo(
            package="cadrumo.clean_pkg",
            path=REPO_ROOT / "src" / "cadrumo" / "clean_pkg" / "__init__.py",
            all_names=["PublicOnly"],
            has_real_all=True,
        ),
    }

    violations = find_underscore_in_all_violations(facades)

    assert [(v.package, v.name) for v in violations] == [("cadrumo.fixture_pkg", "_private_helper")]


def test_find_underscore_in_all_violations_ignores_facades_without_real_all() -> None:
    """A facade with no real ``__all__`` (empty / absent) yields no violations, even if named."""
    facades = {
        "cadrumo.no_all_pkg": FacadeInfo(
            package="cadrumo.no_all_pkg",
            path=REPO_ROOT / "src" / "cadrumo" / "no_all_pkg" / "__init__.py",
            all_names=["_would_be_flagged_if_real"],
            has_real_all=False,
        ),
    }

    assert find_underscore_in_all_violations(facades) == []


def test_live_tree_has_zero_underscore_in_all_violations() -> None:
    """The live ``src/cadrumo`` tree must carry zero underscore-named ``__all__`` entries.

    Real-behavior regression pinning the disposal outcome: every previously
    private-named facade export was either promoted to a public name and its
    consumers swept, or dropped from ``__all__``. This is the scanner-level
    proof that closes the underscore-in-``__all__`` finding; the pytest gate
    (``src/cadrumo/tests/test_import_hygiene_gate.py``) is the CI-wired
    counterpart.
    """
    facades = discover_facades()

    violations = find_underscore_in_all_violations(facades)

    assert violations == [], (
        f"underscore-named __all__ entries found (public facade exporting a private-named "
        f"symbol): {[(v.package, v.name) for v in violations]}"
    )


def _synthetic_package(root: Path, module: str, source: str) -> Path:
    """Write ``source`` as ``cadrumo.<module>`` inside a synthetic ``src`` tree."""
    path = root / "src" / "cadrumo"
    path.mkdir(parents=True, exist_ok=True)
    for part in module.split(".")[:-1]:
        path = path / part
        path.mkdir(exist_ok=True)
        (path / "__init__.py").touch()
    leaf = module.split(".")[-1]
    target = path / ("__init__.py" if leaf == "__init__" else f"{leaf}.py")
    target.write_text(source, encoding="utf-8")
    return target


def _wrapper_functions(tmp_path: Path, module: str, source: str) -> list[str]:
    from ..quality.import_hygiene_scan import find_delegate_wrapper_shims

    target = _synthetic_package(tmp_path, module, source)
    return [w.function for w in find_delegate_wrapper_shims([target], src_root=tmp_path / "src")]


def test_find_delegate_wrapper_shims_catches_a_forwarding_layer_written_as_defs(tmp_path: Path) -> None:
    """The wrapper syntax evades the zero-definitions test; this is what catches it.

    Every callable below has a real ``def``, so ``module_body_defs`` reports a
    module full of genuine definitions and Family 2 stays silent -- while the
    module is a forwarding layer over another package's surface and nothing
    else.
    """
    functions = _wrapper_functions(
        tmp_path,
        "application.ports",
        "from ...cadrumo.adapters.persistence import custody\n"
        "from ..adapters.persistence.storage import read_record\n"
        "\n"
        "def load_record(path, *, maximum_bytes):\n"
        '    """Load one record."""\n'
        "    return read_record(path, maximum_bytes=maximum_bytes)\n"
        "\n"
        "def clear_record(path):\n"
        "    custody.clear_record(path)\n"
        "\n"
        "class _Adapter:\n"
        "    def lock(self, path, *, wait_seconds):\n"
        "        return custody.lock(path, wait_seconds=wait_seconds)\n",
    )

    assert sorted(functions) == ["_Adapter.lock", "clear_record", "load_record"]


def test_find_delegate_wrapper_shims_ignores_a_facade_over_its_own_private_modules(tmp_path: Path) -> None:
    """A package assembling its own public surface from its own internals is not a bridge."""
    functions = _wrapper_functions(
        tmp_path,
        "application.custody.__init__",
        "from ._records import read_record\n"
        "\n"
        "def load_record(path, *, maximum_bytes):\n"
        "    return read_record(path, maximum_bytes=maximum_bytes)\n",
    )

    assert functions == []


def test_find_delegate_wrapper_shims_ignores_a_translating_adapter(tmp_path: Path) -> None:
    """Converting, re-raising, or supplying an argument is a real decision the callable owns."""
    functions = _wrapper_functions(
        tmp_path,
        "application.adapters",
        "from ..adapters.persistence.storage import crypto, read_record\n"
        "\n"
        "def load_record(path, *, maximum_bytes):\n"
        "    return Blob(read_record(path, maximum_bytes=maximum_bytes))\n"
        "\n"
        "def widen(handle, *, wait_seconds):\n"
        "    return crypto.lock(_substrate(handle), wait_seconds=wait_seconds)\n"
        "\n"
        "def pinned(path):\n"
        "    return read_record(path, maximum_bytes=4096)\n"
        "\n"
        "def guarded(path):\n"
        "    try:\n"
        "        return read_record(path)\n"
        "    except OSError as exc:\n"
        "        raise CustodyError from exc\n",
    )

    assert functions == []


def test_find_delegate_wrapper_shims_ignores_private_helpers_and_role_decorated_hooks(tmp_path: Path) -> None:
    """A module-local shorthand is not a standing bridge, and a hook is not an alias.

    A leading-underscore callable is unreachable from outside its module
    without tripping the cross-package private-import family, so it cannot be
    the standing bridge this check exists to find. A ``field_validator`` body
    that delegates to the canonical validator is what the centralisation policy
    ASKS for -- the decorator makes the callable a registration, not a second
    name for the target.
    """
    functions = _wrapper_functions(
        tmp_path,
        "application.models",
        "from pydantic import field_validator\n"
        "from ..core.time import validate_utc_aware\n"
        "\n"
        "def _utcnow(value):\n"
        "    return validate_utc_aware(value)\n"
        "\n"
        "class Record:\n"
        '    @field_validator("created_at")\n'
        "    @classmethod\n"
        "    def check_created_at(cls, value):\n"
        "        return validate_utc_aware(value)\n",
    )

    assert functions == []


def test_find_delegate_wrapper_shims_still_sees_a_wrapper_under_a_binding_only_decorator(tmp_path: Path) -> None:
    """``staticmethod``/``classmethod`` rebind the first argument; they do not add a role.

    The exclusion above is deliberately narrow. If it were "any decorator", a
    forwarding layer would only have to spell its wrappers ``@staticmethod`` to
    disappear from this scan again.
    """
    functions = _wrapper_functions(
        tmp_path,
        "application.statics",
        "from ..adapters.persistence.storage import read_record\n"
        "\n"
        "class Ports:\n"
        "    @staticmethod\n"
        "    def load_record(path, *, maximum_bytes):\n"
        "        return read_record(path, maximum_bytes=maximum_bytes)\n",
    )

    assert functions == ["Ports.load_record"]


def test_find_delegate_wrapper_shims_ignores_a_wrapper_over_a_third_party_boundary(tmp_path: Path) -> None:
    """Wrapping an external library is a boundary adapter; this check is about internal bridges."""
    functions = _wrapper_functions(
        tmp_path,
        "adapters.outbound.http",
        "import httpx\n\ndef get(url, *, timeout):\n    return httpx.get(url, timeout=timeout)\n",
    )

    assert functions == []


def test_find_delegate_wrapper_shims_tolerates_a_file_removed_after_discovery(tmp_path: Path) -> None:
    """A generated module removed after discovery is not a scanner failure."""
    from ..quality.import_hygiene_scan import find_delegate_wrapper_shims

    generated = tmp_path / "generated_test_module.py"
    generated.write_text("from pathlib import Path\n", encoding="utf-8")
    generated.unlink()

    assert find_delegate_wrapper_shims([generated]) == []


def test_find_delegate_wrapper_shims_sees_a_forward_to_a_type_checking_bound_name(tmp_path: Path) -> None:
    """Deferring an import to type-check time does not change which package owns the name.

    The same reading the cross-package private-import family already applies:
    the ownership rule governs WHERE a symbol lives, never WHEN its module
    executes. A wrapper cannot escape this scan by moving its import under the
    guard.
    """
    functions = _wrapper_functions(
        tmp_path,
        "application.deferred",
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from ..adapters.persistence.storage import read_record\n"
        "\n"
        "def load_record(path, *, maximum_bytes):\n"
        "    return read_record(path, maximum_bytes=maximum_bytes)\n",
    )

    assert functions == ["load_record"]


def test_module_import_bindings_prefer_the_runtime_binding_over_the_guarded_one() -> None:
    """A name imported for real and re-imported for typing resolves to the runtime package.

    Both bindings are real, so the map must not be left at the mercy of walk
    order: the wrapper forwards into whichever package the runtime import named.
    """
    import ast

    from ..quality.import_hygiene_scan import module_import_bindings

    tree = ast.parse(
        "from typing import TYPE_CHECKING\n"
        "from cadrumo.adapters.persistence.storage import read_record\n"
        "if TYPE_CHECKING:\n"
        "    from cadrumo.application.user_profile._ports import read_record\n"
    )

    bindings = module_import_bindings(tree, "cadrumo.application.ports", is_package=False)

    assert bindings["read_record"] == "cadrumo.adapters.persistence.storage"


def test_tui_migration_census_drift_reports_instead_of_raising() -> None:
    """One check disagreeing must not decide whether every other finding is printed.

    The refusal keeps its teeth through the caller's exit code; what it loses
    is the power to abort the report, which is what made an unrelated census
    mismatch hide every shim, boundary, and duplicate finding behind a
    traceback.
    """
    from ..quality.import_hygiene_scan import _tui_migration_identity_sha256, tui_migration_census_drift

    matching = _tui_migration_identity_sha256(())

    assert tui_migration_census_drift((), accepted_sha256=matching) is None

    drift = tui_migration_census_drift((), accepted_sha256="0" * 64)
    assert drift is not None
    assert matching in drift, "the drift message must name the found census so it can be investigated"
    assert "0" * 64 in drift, "the drift message must name the accepted census it was compared against"
