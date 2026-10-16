"""Product wheels are built only after one coherent enrolled source snapshot."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import SecretStr

from dev.packaging.native import product
from dev.source_tree import normalised_content, repository_files, snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _product_tree(root: Path) -> tuple[Path, Path]:
    root.mkdir()
    declarations = ["[tool.uv.sources]"]
    for index, name in enumerate(product.PRODUCT_IDENTITY.companion_distributions):
        directory = f"packaging/companion_{index}"
        declarations.append(f'{name} = {{ path = "{directory}" }}')
        (root / directory).mkdir(parents=True)
        (root / directory / "pyproject.toml").write_text(f"name = {name!r}\n", encoding="utf-8")
    declarations.extend(
        (
            "",
            "[tool.hatch.build.targets.wheel.hooks.custom]",
            'path = "packaging/authority/hatch_build.py"',
        )
    )
    hook = root / "packaging/authority/hatch_build.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("# build hook\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("\n".join(declarations) + "\n", encoding="utf-8")
    package_file = root / "src/cadrumo_runtime/session_hold.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_text("value = 'before'\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    unrelated = root / "native/desktop/frontend/src/entry.ts"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("export const value = 1;\n", encoding="utf-8")

    inputs = root.parent / "inputs-product.txt"
    roots = product._product_source_roots(root)
    enrolled = (*repository_files(root, under=roots), "pyproject.toml", "uv.lock")
    inputs.write_text("\n".join(str(root / name) for name in enrolled) + "\n", encoding="utf-8")
    return inputs, package_file


def _capture(
    root: Path,
    inputs: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    after_snapshot: Callable[[Path], None] | None = None,
) -> Path:
    destination = root.parent / "snapshot"
    original_snapshot = snapshot

    def capture(root_arg: Path, files: tuple[str, ...], destination_arg: Path) -> None:
        original_snapshot(root_arg, files, destination_arg)
        if after_snapshot is not None:
            after_snapshot(root_arg)

    monkeypatch.setattr(product, "snapshot", capture)
    product._capture_product_source_snapshot(root, destination, inputs)
    return destination


def test_product_source_snapshot_accepts_stable_enrolled_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "checkout"
    inputs, package_file = _product_tree(root)

    captured = _capture(root, inputs, monkeypatch)

    assert (captured / package_file.relative_to(root)).read_bytes() == normalised_content(
        root, package_file.relative_to(root).as_posix()
    )


def test_product_source_snapshot_rejects_content_changed_during_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "checkout"
    inputs, package_file = _product_tree(root)
    original = package_file.read_text(encoding="utf-8")

    def transient_content_change(_root: Path) -> None:
        package_file.write_text("value = 'captured mutation'\n", encoding="utf-8")

    def restore_after_capture(root_arg: Path, files: tuple[str, ...], destination: Path) -> None:
        transient_content_change(root_arg)
        snapshot(root_arg, files, destination)
        package_file.write_text(original, encoding="utf-8")

    monkeypatch.setattr(product, "snapshot", restore_after_capture)

    with pytest.raises(RuntimeError, match="Enrolled product source content changed"):
        product._capture_product_source_snapshot(root, tmp_path / "snapshot", inputs)

    # The attempted snapshot is intentionally discarded by the caller on refusal.
    assert package_file.read_text(encoding="utf-8") == original


def test_product_source_snapshot_checks_explicit_root_uv_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "checkout"
    inputs, _ = _product_tree(root)
    lock = root / "uv.lock"
    original = lock.read_text(encoding="utf-8")

    def change_and_restore(root_arg: Path, files: tuple[str, ...], destination: Path) -> None:
        lock.write_text("version = 2\n", encoding="utf-8")
        snapshot(root_arg, files, destination)
        lock.write_text(original, encoding="utf-8")

    monkeypatch.setattr(product, "snapshot", change_and_restore)

    with pytest.raises(RuntimeError, match="Enrolled product source content changed"):
        product._capture_product_source_snapshot(root, tmp_path / "snapshot", inputs)


def test_product_source_snapshot_rejects_new_module_missing_from_cmake_census(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "checkout"
    inputs, _ = _product_tree(root)
    new_module = root / "src/cadrumo_client/transport/profile_language.py"

    def add_module(_root: Path) -> None:
        new_module.parent.mkdir(parents=True)
        new_module.write_text("language = 'en'\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"CONFIGURE_DEPENDS refreshes inputs-product.txt"):
        _capture(root, inputs, monkeypatch, after_snapshot=add_module)


def test_product_source_snapshot_allows_unrelated_frontend_churn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "checkout"
    inputs, _ = _product_tree(root)
    frontend_file = root / "native/desktop/frontend/src/entry.ts"

    def edit_frontend(_root: Path) -> None:
        frontend_file.write_text("export const value = 2;\n", encoding="utf-8")

    captured = _capture(root, inputs, monkeypatch, after_snapshot=edit_frontend)

    assert not (captured / "native").exists()


def test_product_snapshot_preserves_unchanged_files_and_removes_deleted_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "checkout"
    inputs, package_file = _product_tree(root)
    removed = package_file.with_name("removed.py")
    removed.write_text("obsolete = True\n", encoding="utf-8")
    inputs.write_text(inputs.read_text(encoding="utf-8") + str(removed) + "\n", encoding="utf-8")
    captured = _capture(root, inputs, monkeypatch)
    stable = captured / package_file.relative_to(root)
    original_mtime = stable.stat().st_mtime_ns
    removed.unlink()

    product._capture_product_source_snapshot(root, captured, inputs)

    assert stable.stat().st_mtime_ns == original_mtime
    assert not (captured / removed.relative_to(root)).exists()


def test_companion_wheel_identity_uses_its_actual_hook_owned_payload(tmp_path: Path) -> None:
    source = Path(product.__file__).resolve().parents[3]
    project = tmp_path / "packaging/cadrumo_data_official"
    shutil.copytree(source / "packaging/cadrumo_data_official", project)
    corpus = tmp_path / "src/cadrumo/_data/corpus"
    owned = corpus / "aeat_official/document.pdf"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"official corpus")
    unrelated = tmp_path / "src/cadrumo_runtime/session.py"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("value = 1\n", encoding="utf-8")

    before = product._wheel_input_digest(project, toolchain=None)
    unrelated.write_text("value = 2\n", encoding="utf-8")
    assert product._wheel_input_digest(project, toolchain=None) == before
    new_owned = owned.with_name("new.pdf")
    new_owned.write_bytes(b"new official corpus")
    assert product._wheel_input_digest(project, toolchain=None) != before


def test_product_build_reuses_companion_wheels_and_installed_files_on_python_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    declarations = [
        "[build-system]",
        'requires = ["hatchling"]',
        'build-backend = "hatchling.build"',
        "[project]",
        'name = "cadrumo"',
        'version = "0.6.0"',
        "dependencies = ["
        + ",".join(f'"{name}==0.6.0"' for name in product.PRODUCT_IDENTITY.companion_distributions)
        + "]",
        "[tool.hatch.build.targets.wheel]",
        'packages = ["src/cadrumo"]',
        "[tool.hatch.build.targets.wheel.hooks.custom]",
        'path = "packaging/authority/hatch_build.py"',
        "[tool.uv.sources]",
    ]
    repository = Path(product.__file__).resolve().parents[3]
    for name in product.PRODUCT_IDENTITY.companion_distributions:
        directory = "packaging/" + name.replace("-", "_")
        declarations.append(f'{name} = {{ path = "{directory}" }}')
        shutil.copytree(repository / directory, root / directory)
    (root / "pyproject.toml").write_text("\n".join(declarations), encoding="utf-8")
    hook = root / "packaging/authority/hatch_build.py"
    hook.parent.mkdir(parents=True)
    hook.write_text(
        "import os\nfrom pathlib import Path\n"
        "from hatchling.builders.hooks.plugin.interface import BuildHookInterface\n"
        "class CustomBuildHook(BuildHookInterface):\n"
        "    def initialize(self, version, data):\n"
        "        selected = Path(os.environ['CADRUMO_AUTHORITY_ROOT']) / 'authority.current.json'\n"
        "        data['force_include'] = {str(selected): 'cadrumo/authority.current.json'}\n",
        encoding="utf-8",
    )
    source = root / "src/cadrumo/__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text("value = 1\n", encoding="utf-8")
    for subtree in ("manuals", "aeat_official", "normatives"):
        corpus = root / "src/cadrumo/_data/corpus" / subtree / "document.pdf"
        corpus.parent.mkdir(parents=True)
        corpus.write_bytes(b"inert corpus fixture")
    pin = root / "dev/packaging/release-python-version"
    pin.parent.mkdir(parents=True)
    pin.write_text(".".join(map(str, sys.version_info[:3])), encoding="utf-8")
    authority = tmp_path / "authority.current.json"
    authority.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(product, "REPO_ROOT", root)
    monkeypatch.setattr(product, "build_client_json", lambda _: SecretStr("{}"))
    monkeypatch.setattr(product, "selected_published_authority", lambda _: (authority,))
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    output = tmp_path / "output"
    installed = tmp_path / "dependencies"
    installed.mkdir()
    uv = shutil.which("uv")
    assert uv is not None
    arguments = (output, Path(sys.executable), installed, "windows-x86-64")
    product.build_product(*arguments, uv_executable=Path(uv))
    before = {wheel.name: wheel.stat().st_mtime_ns for wheel in (output / "wheels").glob("*.whl")}
    companion = installed / "cadrumo_data/_data/corpus/manuals/document.pdf"
    installed_mtime = companion.stat().st_mtime_ns

    product.build_product(*arguments, uv_executable=Path(uv))
    assert {wheel.name: wheel.stat().st_mtime_ns for wheel in (output / "wheels").glob("*.whl")} == before
    assert companion.stat().st_mtime_ns == installed_mtime
    source.write_text("value = 2\n", encoding="utf-8")
    product.build_product(*arguments, uv_executable=Path(uv))

    after = {wheel.name: wheel.stat().st_mtime_ns for wheel in (output / "wheels").glob("*.whl")}
    assert all(after[name] == mtime for name, mtime in before.items() if name.startswith("cadrumo_data_"))
    root_wheel = next(name for name in before if name.startswith("cadrumo-"))
    assert after[root_wheel] != before[root_wheel]
    assert companion.stat().st_mtime_ns == installed_mtime
    assert (installed / "cadrumo/__init__.py").read_text(encoding="utf-8") == "value = 2\n"
    authority.write_text('{"version": 2}', encoding="utf-8")
    product.build_product(*arguments, uv_executable=Path(uv))
    assert (installed / "cadrumo/authority.current.json").read_text(encoding="utf-8") == '{"version": 2}'
    assert companion.stat().st_mtime_ns == installed_mtime


def test_product_authority_snapshot_retires_only_previous_snapshot_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authoring = tmp_path / "authoring"
    authoring.mkdir()
    descriptor = authoring / "authority.current.json"
    old = authoring / "authority-old.sqlite3"
    old.write_bytes(b"old authority")
    descriptor.write_text(old.name, encoding="utf-8")
    current = [old]
    monkeypatch.setattr(product, "selected_published_authority", lambda _: (descriptor, current[0]))
    source = tmp_path / "snapshot"
    source.mkdir()
    product._stage_product_authority(authoring, source)
    unchanged_mtime = (source / ".authority" / old.name).stat().st_mtime_ns
    product._stage_product_authority(authoring, source)
    assert (source / ".authority" / old.name).stat().st_mtime_ns == unchanged_mtime

    new = authoring / "authority-new.sqlite3"
    new.write_bytes(b"new authority")
    current[0] = new
    descriptor.write_text(new.name, encoding="utf-8")
    product._stage_product_authority(authoring, source)

    assert {path.name for path in (source / ".authority").iterdir()} == {descriptor.name, new.name}
    assert (source / ".authority" / new.name).read_bytes() == b"new authority"
    assert old.read_bytes() == b"old authority"


def test_product_authority_capture_failure_preserves_previous_selected_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authoring = tmp_path / "authoring"
    authoring.mkdir()
    descriptor = authoring / "authority.current.json"
    old = authoring / "authority-old.sqlite3"
    old.write_bytes(b"old authority")
    descriptor.write_text(old.name, encoding="utf-8")
    current = [old]
    monkeypatch.setattr(product, "selected_published_authority", lambda _: (descriptor, current[0]))
    source = tmp_path / "snapshot"
    source.mkdir()
    product._stage_product_authority(authoring, source)
    new = authoring / "authority-new.sqlite3"
    new.write_bytes(b"new authority")
    current[0] = new
    descriptor.write_text(new.name, encoding="utf-8")
    copy = shutil.copy2

    def mutate_after_capture(original: Path, destination: Path) -> Path:
        result = copy(original, destination)
        if original == new:
            new.write_bytes(b"concurrent edit")
        return Path(result)

    monkeypatch.setattr(product.shutil, "copy2", mutate_after_capture)
    with pytest.raises(RuntimeError, match="authority changed"):
        product._stage_product_authority(authoring, source)
    assert {path.name for path in (source / ".authority").iterdir()} == {descriptor.name, old.name}
    assert (source / ".authority" / descriptor.name).read_text(encoding="utf-8") == old.name
    assert not list(source.glob(".authority-capture-*"))
