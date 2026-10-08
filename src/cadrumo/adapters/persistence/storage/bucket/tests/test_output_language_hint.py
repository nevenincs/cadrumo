"""Tests for the bucket-local output-language hint sidecar."""

from __future__ import annotations

import errno
import logging
from pathlib import Path

import pytest

from ......core.external_constants import OutputLanguage
from ..output_language_hint import (
    bucket_output_language_hint_path,
    clear_bucket_output_language_hint,
    read_bucket_output_language_hint,
    write_bucket_output_language_hint,
)
from .bucket_layout import provision_bucket_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.mark.parametrize("provisioned", (False, True), ids=("missing-parent", "missing-hint"))
def test_absent_output_language_hint_uses_the_normal_fallback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, provisioned: bool
) -> None:
    bucket_id = "11111111-1111-4111-8111-111111111111"
    if provisioned:
        provision_bucket_directory(tmp_path, bucket_id)
    logger_name = "cadrumo.adapters.persistence.storage.bucket.output_language_hint"

    with caplog.at_level(logging.DEBUG, logger=logger_name):
        assert read_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id) is None

    assert not [record for record in caplog.records if record.name == logger_name]


@pytest.mark.parametrize(
    "error",
    (
        PermissionError("synthetic denied read"),
        NotADirectoryError("synthetic invalid parent"),
        OSError(errno.ELOOP, "synthetic symlink loop"),
        RuntimeError("synthetic unexpected read failure"),
    ),
    ids=("permission", "invalid-parent", "symlink-loop", "unexpected"),
)
def test_unexpected_hint_read_error_preserves_exception_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    bucket_id = "11111111-1111-4111-8111-111111111111"
    provision_bucket_directory(tmp_path, bucket_id)
    hint = bucket_output_language_hint_path(storage_root=tmp_path, bucket_id=bucket_id)
    original_read = Path.read_text

    def denied_read(
        path: Path, encoding: str | None = None, errors: str | None = None, newline: str | None = None
    ) -> str:
        if path == hint:
            raise error
        return original_read(path, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "read_text", denied_read)
    logger_name = "cadrumo.adapters.persistence.storage.bucket.output_language_hint"

    with caplog.at_level(logging.DEBUG, logger=logger_name):
        assert read_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id) is None

    records = [record for record in caplog.records if record.name == logger_name]
    assert len(records) == 1
    assert type(error).__name__ in records[0].getMessage()
    assert records[0].exc_info is not None or records[0].exc_text is not None


def test_output_language_hint_round_trips_supported_language(tmp_path: Path) -> None:
    bucket_id = "11111111-1111-4111-8111-111111111111"
    provision_bucket_directory(tmp_path, bucket_id)

    written = write_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id, language=" CA ")

    assert written is True
    assert read_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id) == "ca"
    assert (
        bucket_output_language_hint_path(storage_root=tmp_path, bucket_id=bucket_id).read_text(
            encoding="utf-8",
        )
        == "ca\n"
    )


@pytest.mark.parametrize("language", ("", "zz", True))
def test_output_language_hint_rejects_invalid_language_without_overwriting(tmp_path: Path, language: object) -> None:
    bucket_id = "11111111-1111-4111-8111-111111111111"
    provision_bucket_directory(tmp_path, bucket_id)
    assert write_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id, language="en") is True

    written = write_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id, language=language)

    assert written is False
    assert read_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id) == "en"


def test_output_language_hint_round_trips_output_language_enum(tmp_path: Path) -> None:
    bucket_id = "11111111-1111-4111-8111-111111111111"
    provision_bucket_directory(tmp_path, bucket_id)

    written = write_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id, language=OutputLanguage.HU)

    assert written is True
    assert read_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id) == OutputLanguage.HU.value


def test_output_language_hint_invalid_file_falls_back_to_none(tmp_path: Path) -> None:
    bucket_id = "11111111-1111-4111-8111-111111111111"
    provision_bucket_directory(tmp_path, bucket_id)
    path = bucket_output_language_hint_path(storage_root=tmp_path, bucket_id=bucket_id)
    path.write_text("zz\n", encoding="utf-8")

    assert read_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id) is None


def test_clear_output_language_hint_removes_sidecar(tmp_path: Path) -> None:
    bucket_id = "11111111-1111-4111-8111-111111111111"
    provision_bucket_directory(tmp_path, bucket_id)
    assert write_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id, language="hu") is True

    clear_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id)

    assert read_bucket_output_language_hint(storage_root=tmp_path, bucket_id=bucket_id) is None
