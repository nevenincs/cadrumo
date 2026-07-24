"""Per-language deploy-matrix contracts of the documentation publisher."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest
from dev.deploy.docs_static_site import (
    _DOWNLOAD_LATEST_SCHEMA,
    _DOWNLOAD_LATEST_STATIC_PATH,
    CANONICAL_DOCS_BASE_URL,
    _language_build_command,
    _language_build_environment,
    _language_site_url,
    _localized_languages,
    _refresh_download_latest,
    _validate_language_roots,
)
from dev.docs.i18n import TARGET_LANGUAGES

from cadrumo.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _materialise_language_root(html_root: Path, language: str) -> None:
    """Write a minimal valid localized site root: an index page and a Pagefind chunk."""
    root = html_root / language
    (root).mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    index_dir = root / "pagefind" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "en_abc.pf_index").write_bytes(b"substantive-index-data")


def test_localized_languages_are_the_translation_targets_not_english() -> None:
    """The deploy roots are exactly the docs translation targets; English is the default root."""
    languages = _localized_languages()
    assert languages == TARGET_LANGUAGES
    assert set(languages) == {member.value for member in OutputLanguage} - {OutputLanguage.EN.value}
    assert OutputLanguage.EN.value not in languages


def test_language_site_url_is_a_subroot_of_the_canonical_docs_url() -> None:
    """A localized root URL is the canonical docs URL plus the language segment."""
    assert _language_site_url("es") == f"{CANONICAL_DOCS_BASE_URL}/es"


def test_language_build_command_reuses_the_driver_language_and_out_dir_flags(tmp_path: Path) -> None:
    """The localized build command drives dev.docs.build with the user scope, language, and out-dir."""
    out_dir = tmp_path / "html" / "ca"
    command = _language_build_command("ca", out_dir)
    assert command[1:] == [
        "-m",
        "dev.docs.build",
        "--strict",
        "--scope",
        "user",
        "--language",
        "ca",
        "--out-dir",
        str(out_dir),
    ]


def test_language_build_environment_points_the_base_url_at_the_language_root() -> None:
    """Each localized build carries the page-only Pagefind contract and its own base URL."""
    env = _language_build_environment("hu")
    assert env["CADRUMO_DOCS_BASE_URL"] == f"{CANONICAL_DOCS_BASE_URL}/hu"
    assert env["CADRUMO_DOCS_PAGEFIND_MODE"] == "pages"
    assert env["CADRUMO_DOCS_JOBS"] == "1"


def test_validate_language_roots_accepts_a_complete_matrix(tmp_path: Path) -> None:
    """Validation passes when every localized root has its index page and Pagefind index."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    _validate_language_roots(tmp_path)


def test_validate_language_roots_refuses_a_missing_index(tmp_path: Path) -> None:
    """A localized root without its rendered index page fails validation."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    missing = _localized_languages()[0]
    (tmp_path / missing / "index.html").unlink()
    with pytest.raises(SystemExit, match="missing its rendered index page"):
        _validate_language_roots(tmp_path)


def test_validate_language_roots_refuses_an_empty_pagefind_index(tmp_path: Path) -> None:
    """A localized root whose Pagefind index has no substantive data fails validation."""
    for language in _localized_languages():
        _materialise_language_root(tmp_path, language)
    empty = _localized_languages()[0]
    for chunk in (tmp_path / empty / "pagefind" / "index").rglob("*.pf_index"):
        chunk.write_bytes(b"")
    with pytest.raises(SystemExit, match="no substantive Pagefind index data"):
        _validate_language_roots(tmp_path)


class _FakeResponse:
    """Minimal context-manager HTTP response for the download-latest fetch."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, result: object) -> None:
    """Point the module's urlopen at a canned body or exception."""

    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, bytes)
        return _FakeResponse(result)

    monkeypatch.setattr("dev.deploy.docs_static_site.urllib.request.urlopen", fake_urlopen)


def _download_latest_path(repo_root: Path) -> Path:
    return repo_root.joinpath(*_DOWNLOAD_LATEST_STATIC_PATH)


def test_refresh_download_latest_writes_a_valid_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid latest-release payload is written into docs/_static."""
    body = json.dumps({"schema_name": _DOWNLOAD_LATEST_SCHEMA, "version": "9.9.9", "assets": []}).encode("utf-8")
    _patch_urlopen(monkeypatch, body)
    _refresh_download_latest(tmp_path)
    written = _download_latest_path(tmp_path)
    assert written.is_file()
    assert json.loads(written.read_bytes())["schema_name"] == _DOWNLOAD_LATEST_SCHEMA


def test_refresh_download_latest_degrades_on_network_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No release yet / network error degrades silently: no raise, no file."""
    _patch_urlopen(monkeypatch, urllib.error.URLError("no release"))
    _refresh_download_latest(tmp_path)  # must not raise
    assert not _download_latest_path(tmp_path).exists()


def test_refresh_download_latest_degrades_on_unexpected_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A body that is not the expected schema (e.g. a 404 page) degrades silently."""
    _patch_urlopen(monkeypatch, b"<html>not found</html>")
    _refresh_download_latest(tmp_path)  # must not raise
    assert not _download_latest_path(tmp_path).exists()


def test_refresh_download_latest_degrades_on_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A local write failure (permissions/disk) degrades silently, honouring 'never raises'."""
    body = json.dumps({"schema_name": _DOWNLOAD_LATEST_SCHEMA, "version": "9.9.9", "assets": []}).encode("utf-8")
    _patch_urlopen(monkeypatch, body)

    def raise_oserror(self: Path, data: bytes) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", raise_oserror)
    _refresh_download_latest(tmp_path)  # must not raise despite the write failure
