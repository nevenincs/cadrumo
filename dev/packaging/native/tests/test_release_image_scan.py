"""The release-package scan finds development facts in product files and leaves vendored payloads alone."""

from __future__ import annotations

from pathlib import Path, PurePath

import pytest

from dev.paths import REPO_ROOT

from ..application_environment import load
from ..release_image_scan import (
    BUILDER_HOME,
    RETIRED_STORAGE_VARIABLES,
    Finding,
    development_spellings,
    main,
    scan,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _clean_package(root: Path) -> Path:
    package = root / "app"
    _write(package / "cadrumo.exe", b"MZ installed default only")
    _write(package / "bin" / "aeat.exe", b"MZ" + "LOCALAPPDATA".encode("utf-16-le"))
    _write(package / "data" / "package-manifest.json", b'{"files": []}')
    site = package / "cadrumo" / "site-packages"
    # The one storage variable is not a development fact: the release resolver reads it.
    _write(site / "cadrumo" / "core" / "config.py", b"ROOT = 'CADRUMO_STORAGE_ROOT'\n")
    # Third-party payloads describe their own builds; they are not the product's to change.
    _write(site / "attrs-25.1.0.dist-info" / "METADATA", b"Built from pyproject.toml\n")
    _write(package / "cadrumo" / "node_modules" / "ajv" / "package.json", b'{"files": ["var/storage"]}')
    _write(package / "bin" / "python313.dll", b"pyproject.toml")
    _write(package / "python.zip", b"pyproject.toml")
    return package


def test_a_clean_release_package_has_no_findings(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    package = _clean_package(tmp_path)

    assert scan(package, checkout) == []
    assert main(["--package", str(package), "--checkout", str(tmp_path)]) == 0


def test_every_development_fact_in_a_product_file_is_found(tmp_path: Path) -> None:
    checkout = tmp_path / "Checkout"
    package = _clean_package(tmp_path)
    site = package / "cadrumo" / "site-packages"
    _write(site / "cadrumo" / "core" / "storage.py", b"DEFAULT = 'var/storage'\n")
    _write(package / "bin" / "aeat.exe", b"MZ" + "CADRUMO_LOCAL_STORAGE_ROOT".encode("utf-16-le"))
    # A checkout path, spelled with another case and escaped as JSON, inside a distribution record.
    escaped = str(checkout).lower().replace("\\", "\\\\")
    _write(site / "cadrumo-1.0.dist-info" / "direct_url.json", f'{{"url": "{escaped}"}}'.encode())
    _write(package / "docs" / "overrides.html", b"<p>CADRUMO_LOG_DIR</p>")

    findings = scan(package, checkout)

    assert sorted(findings, key=lambda finding: finding.path.as_posix()) == [
        Finding(PurePath("bin/aeat.exe"), "retired storage variable CADRUMO_LOCAL_STORAGE_ROOT"),
        Finding(PurePath("cadrumo/site-packages/cadrumo-1.0.dist-info/direct_url.json"), "checkout path"),
        Finding(PurePath("cadrumo/site-packages/cadrumo/core/storage.py"), "development storage default"),
        Finding(PurePath("docs/overrides.html"), "retired storage variable CADRUMO_LOG_DIR"),
    ]
    assert main(["--package", str(package), "--checkout", str(tmp_path)]) == 1


def test_the_builders_home_directory_is_found_in_an_image_and_a_manifest(tmp_path: Path) -> None:
    home = tmp_path / "Users" / "Builder Name"
    package = _clean_package(tmp_path)
    registry = home / ".cargo" / "registry" / "src" / "tokio" / "lib.rs"
    _write(package / "cadrumo.exe", b"MZ" + str(registry).encode())
    _write(package / "cadrumo-manager.exe", b"MZ" + str(registry).lower().encode("utf-16-le"))
    _write(package / "data" / "package-manifest.json", f'{{"uv": "{home.as_posix()}/uv.exe"}}'.encode())
    # A third-party payload is not the product's to change.
    _write(package / "cadrumo" / "site-packages" / "attrs" / "RECORD", str(home).encode())

    assert scan(package, tmp_path / "checkout") == []
    findings = scan(package, tmp_path / "checkout", home)

    assert sorted(findings, key=lambda finding: finding.path.as_posix()) == [
        Finding(PurePath("cadrumo-manager.exe"), BUILDER_HOME),
        Finding(PurePath("cadrumo.exe"), BUILDER_HOME),
        Finding(PurePath("data/package-manifest.json"), BUILDER_HOME),
    ]
    (tmp_path / "checkout").mkdir()
    arguments = ["--package", str(package), "--checkout", str(tmp_path / "checkout")]
    assert main([*arguments, "--home", str(home)]) == 1
    assert main([*arguments, "--home", str(tmp_path / "Users" / "Another")]) == 0


def test_a_home_directly_beneath_a_filesystem_root_is_not_looked_for(tmp_path: Path) -> None:
    home = Path(tmp_path.anchor) / "root"
    package = _clean_package(tmp_path)
    _write(package / "cadrumo.exe", b"MZ" + home.as_posix().encode())

    assert BUILDER_HOME not in development_spellings(tmp_path / "checkout", home)
    assert scan(package, tmp_path / "checkout", home) == []


@pytest.mark.parametrize("name", RETIRED_STORAGE_VARIABLES)
def test_each_retired_storage_variable_is_found_in_either_encoding(tmp_path: Path, name: str) -> None:
    package = _clean_package(tmp_path)
    _write(package / "cadrumo" / "site-packages" / "cadrumo" / "core" / "settings.py", f"X = {name!r}\n".encode())
    _write(package / "cadrumo-manager.exe", b"MZ" + name.lower().encode("utf-16-le"))

    findings = scan(package, tmp_path / "checkout")

    fact = f"retired storage variable {name}"
    assert sorted(findings, key=lambda finding: finding.path.as_posix()) == [
        Finding(PurePath("cadrumo-manager.exe"), fact),
        Finding(PurePath("cadrumo/site-packages/cadrumo/core/settings.py"), fact),
    ]


def test_the_retired_variables_are_exactly_the_names_the_package_declaration_no_longer_has() -> None:
    declared = set(load(REPO_ROOT).names)

    assert not declared & set(RETIRED_STORAGE_VARIABLES)
    assert "CADRUMO_STORAGE_ROOT" in declared
