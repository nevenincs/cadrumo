"""Context-sensitive Google Drive reference grammar boundaries."""

from __future__ import annotations

import pytest

from ..google_drive_reference import (
    build_google_drive_file_reference,
    parse_google_drive_file_id,
    parse_google_drive_folder_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ID_9 = "A" * 9
_ID_10 = "A" * 10
_ID_24 = "A" * 24
_ID_25 = "A" * 25


@pytest.mark.parametrize(
    ("reference", "expected"),
    (
        (f"https://drive.google.com/file/d/{_ID_9}/view", None),
        (f"https://drive.google.com/file/d/{_ID_10}/view", _ID_10),
        (f"https://drive.google.com/file/d/{_ID_24}/view", _ID_24),
        (f"https://drive.google.com/file/d/{_ID_25}/view", _ID_25),
        (f"https://drive.google.com/open?id={_ID_10}", _ID_10),
        (f"https://drive.google.com/open?id={_ID_24}&usp=sharing", _ID_24),
        (f"https://drive.google.com/open?id={_ID_25}#section", _ID_25),
        (_ID_24, None),
        (_ID_25, _ID_25),
        ("  " + _ID_25 + "  ", _ID_25),
        ("not-a-drive-reference", None),
        ("https://drive.google.com/file/d/not-a-drive!reference", None),
    ),
)
def test_file_id_grammar_preserves_contextual_length_rules(reference: str, expected: str | None) -> None:
    assert parse_google_drive_file_id(reference) == expected


@pytest.mark.parametrize(
    "reference",
    (
        f"https://drive.google.com/file/d/{_ID_10}!",
        f"https://drive.google.com/file/d/{_ID_10}.pdf",
        f"https://drive.google.com/file/d/{_ID_10}%2Fother",
        f"https://drive.google.com/open?id={_ID_10}!",
        f"https://drive.google.com/open?id={_ID_10}/tail",
        f"https://drive.google.com/file/d/{_ID_9}.",
        "https://drive.google.com/file/d/AAAAA!AAAAA",
    ),
)
def test_file_id_grammar_rejects_partial_prefixes_and_malformed_alphabet(reference: str) -> None:
    assert parse_google_drive_file_id(reference) is None


def test_folder_and_file_reference_grammars_remain_distinct() -> None:
    folder_url = f"https://drive.google.com/drive/folders/{_ID_10}?usp=sharing"
    malformed_folder_url = f"https://drive.google.com/drive/folders/{_ID_10}!"
    file_url = f"https://drive.google.com/file/d/{_ID_10}/view"

    assert parse_google_drive_folder_id(folder_url) == _ID_10
    assert parse_google_drive_file_id(folder_url) is None
    assert parse_google_drive_folder_id(malformed_folder_url) is None
    assert parse_google_drive_file_id(file_url) == _ID_10
    assert parse_google_drive_folder_id(file_url) == _ID_10
    assert parse_google_drive_folder_id(_ID_24) is None
    assert parse_google_drive_folder_id(_ID_25) == _ID_25


@pytest.mark.parametrize("file_id", (_ID_10, _ID_24, _ID_25))
def test_canonical_file_reference_builder_accepts_complete_url_context_ids(file_id: str) -> None:
    assert build_google_drive_file_reference(file_id) == f"https://drive.google.com/file/d/{file_id}"


@pytest.mark.parametrize("file_id", (_ID_9, "A" * 10 + "!", "A" * 10 + "/tail", ""))
def test_canonical_file_reference_builder_rejects_invalid_provider_ids(file_id: str) -> None:
    with pytest.raises(ValueError, match="invalid URL-context shape"):
        build_google_drive_file_reference(file_id)
