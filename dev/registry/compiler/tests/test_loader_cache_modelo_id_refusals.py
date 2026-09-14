"""Reading ``[modelo].id`` reports its own two refusals and relabels nothing else.

A read or parse refusal is reported against the named subject, the missing-key
refusal names its path exactly once, and any other exception raised by the
reader keeps its own type and message.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..loader_cache import _read_modelo_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _UnrelatedReaderError(RuntimeError):
    """Stands in for a defect deeper than the TOML reader's own refusals."""


def test_valid_manifest_yields_the_declared_modelo_id(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text('[modelo]\nid = "303"\n', encoding="utf-8")

    assert _read_modelo_id(manifest, description="manifest") == "303"


def test_unparseable_toml_is_reported_against_the_named_subject(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text("[modelo\nid = ", encoding="utf-8")

    with pytest.raises(RegistryLoadError) as caught:
        _read_modelo_id(manifest, description="manifest")

    assert f"{manifest}: invalid manifest:" in str(caught.value)
    assert "invalid TOML" in str(caught.value)


def test_missing_modelo_id_is_reported_once_without_the_subject_prefix(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text('[otra]\nid = "303"\n', encoding="utf-8")

    with pytest.raises(RegistryLoadError) as caught:
        _read_modelo_id(manifest, description="manifest")

    assert str(caught.value) == f"{manifest}: missing [modelo].id"


def test_unrelated_reader_failure_propagates_with_its_own_type_and_message(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text('[modelo]\nid = "303"\n', encoding="utf-8")

    def broken_read(path: Path, *, error_factory: object) -> dict[str, object]:
        del path, error_factory
        raise _UnrelatedReaderError("registry toml reader symbol was removed")

    with pytest.raises(_UnrelatedReaderError) as caught:
        _read_modelo_id(manifest, description="manifest", read=broken_read)

    assert str(caught.value) == "registry toml reader symbol was removed"
    assert "invalid manifest" not in str(caught.value)
