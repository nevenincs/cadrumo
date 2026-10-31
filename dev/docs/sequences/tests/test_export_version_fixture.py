"""The trusted worker receives only a finite canonical public export version."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError
from cadrumo.domain.filing import software_identity
from cadrumo.domain.filing.errors import FilingExportValidationError
from cadrumo.tests.audited_process import run_audited_process
from cadrumo.tests.authority_run_snapshot import freeze_authority_root
from dev._paths import REPO_ROOT

from ..runtime_fixture import (
    _EXPORT_VERSION_FILE,
    _export_version_authority,
    _publish_export_version,
    _recorded_export_version,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.fixture
def version_authority(tmp_path: Path) -> None:
    selected = bundled_authority_descriptor_path().resolve(strict=True)
    staged = freeze_authority_root(selected.parent, tmp_path / "publication-stage")
    assert staged is not None
    staged.rename(tmp_path / "docs-authority")


def test_fresh_isolated_fixture_receives_recorded_version_and_restores_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version_authority: None
) -> None:
    with monkeypatch.context() as changed:
        changed.setattr(software_identity, "PACKAGE_VERSION", "1.6.2")
        _publish_export_version(tmp_path)
    script = (
        f"import sys; sys.path.insert(0, {str(REPO_ROOT)!r}); "
        "from pathlib import Path; "
        "from cadrumo.domain.filing import software_identity; "
        "from dev.docs.sequences.runtime_fixture import _export_version_authority, _recorded_export_version; "
        "before = software_identity.PACKAGE_VERSION; "
        f"scope = _recorded_export_version(Path({str(tmp_path)!r})); "
        "scope.__enter__(); assert software_identity.PACKAGE_VERSION == '1.6.2'; "
        f"facts = _export_version_authority(Path({str(tmp_path)!r})); "
        "facts.__enter__(); assert software_identity.aeat_aux_version() == '162'; facts.__exit__(None, None, None); "
        "scope.__exit__(None, None, None); assert software_identity.PACKAGE_VERSION == before"
    )
    result = run_audited_process([sys.executable, "-I", "-c", script], capture_output=True, text=True, timeout=None)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "raw",
    [
        b'{"package_version":"1.2.3-dev"}',
        b'{"package_version":"10.20.30"}',
        b'{"package_version":123}',
        b'{"package_version":"1.2.3","extra":true}',
    ],
)
def test_malformed_record_refuses_without_changing_current_version(
    tmp_path: Path, raw: bytes, version_authority: None
) -> None:
    before = software_identity.PACKAGE_VERSION
    (tmp_path / _EXPORT_VERSION_FILE).write_bytes(raw)
    with pytest.raises((ValidationError, FilingExportValidationError)), _recorded_export_version(tmp_path):
        pytest.fail("malformed version was admitted")
    assert before == software_identity.PACKAGE_VERSION


def test_missing_record_refuses_and_exception_restores_selected_version(
    tmp_path: Path, version_authority: None
) -> None:
    before = software_identity.PACKAGE_VERSION
    with pytest.raises(FileNotFoundError), _recorded_export_version(tmp_path):
        pytest.fail("missing version was admitted")
    (tmp_path / _EXPORT_VERSION_FILE).write_text('{"package_version":"1.6.2"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="fixture exception"), _recorded_export_version(tmp_path):
        with pytest.raises(InternalInvariantError):
            software_identity.aeat_aux_version()
        with _export_version_authority(tmp_path):
            assert software_identity.aeat_aux_version() == "162"
        raise RuntimeError("fixture exception")
    assert before == software_identity.PACKAGE_VERSION


def test_oversized_record_refuses_before_parsing(tmp_path: Path) -> None:
    before = software_identity.PACKAGE_VERSION
    (tmp_path / _EXPORT_VERSION_FILE).write_bytes(b" " * 257)
    with pytest.raises(ValueError, match="finite limit"), _recorded_export_version(tmp_path):
        pytest.fail("oversized version was admitted")
    assert before == software_identity.PACKAGE_VERSION


def test_missing_sandbox_authority_refuses_even_with_a_valid_version(tmp_path: Path) -> None:
    with pytest.raises((AuthorityStoreError, FileNotFoundError)):
        _publish_export_version(tmp_path)
    assert not (tmp_path / _EXPORT_VERSION_FILE).exists()
