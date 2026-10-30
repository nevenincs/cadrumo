"""The release-package scan finds development facts in product files and leaves vendored payloads alone."""

from __future__ import annotations

from pathlib import Path, PurePath

import pytest

from cadrumo.core.storage_environment import STORAGE_ROOT

from ..release_image_scan import Finding, main, scan

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
    _write(site / "cadrumo" / "core" / "config.py", b"ROOT = 'CADRUMO_LOCAL_STORAGE_ROOT'\n")
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
    default = "/".join(STORAGE_ROOT.development_default)
    _write(site / "cadrumo" / "core" / "storage.py", f"DEFAULT = {default!r}\n".encode())
    _write(package / "bin" / "aeat.exe", b"MZ" + STORAGE_ROOT.development_variable.encode("utf-16-le"))
    # A checkout path, spelled with another case and escaped as JSON, inside a distribution record.
    escaped = str(checkout).lower().replace("\\", "\\\\")
    _write(site / "cadrumo-1.0.dist-info" / "direct_url.json", f'{{"url": "{escaped}"}}'.encode())
    _write(package / "docs" / "overrides.html", f"<p>{STORAGE_ROOT.checkout_marker}</p>".encode())

    findings = scan(package, checkout)

    assert sorted(findings, key=lambda finding: finding.path.as_posix()) == [
        Finding(PurePath("bin/aeat.exe"), "development storage variable"),
        Finding(PurePath("cadrumo/site-packages/cadrumo-1.0.dist-info/direct_url.json"), "checkout path"),
        Finding(PurePath("cadrumo/site-packages/cadrumo/core/storage.py"), "development storage default"),
        Finding(PurePath("docs/overrides.html"), "checkout marker"),
    ]
    assert main(["--package", str(package), "--checkout", str(tmp_path)]) == 1
