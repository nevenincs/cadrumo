"""Tests for the bucket-local output-language hint sidecar."""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.external_constants import OutputLanguage
from ......tests.bucket_layout import provision_bucket_directory
from ..output_language_hint import (
    bucket_output_language_hint_path,
    clear_bucket_output_language_hint,
    read_bucket_output_language_hint,
    write_bucket_output_language_hint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


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
