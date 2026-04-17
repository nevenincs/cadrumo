"""Unit tests for :mod:`aeat.schema._fetch` hardening surface.

Exercises the URL allow-list, size caps, ``boe_ref`` re-validation,
atomic-write behaviour, and override-env-var bounds introduced by
the security audit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..config import Settings
from ..models import ModeloCode
from ._errors import SchemaCacheError
from ._fetch import (
    _MAX_OVERRIDE_BYTES,
    _MAX_PDF_BYTES,
    BoeOrdenSource,
    _resolve_override,
    _validate_override_url,
    fetch_boe_pdf,
)
from .testing import build_fake_boe_pdf

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _settings_with(cache_dir: Path, override: str = "") -> Settings:
    return Settings(
        aeat_schema_cache_dir=cache_dir,
        aeat_schema_source_urls_override=override,
    )


class TestValidateOverrideUrl:
    def test_https_to_allowed_host_passes(self) -> None:
        _validate_override_url("https://www.boe.es/foo.pdf")
        _validate_override_url("https://boe.es/bar.pdf")

    def test_https_to_other_host_rejected(self) -> None:
        with pytest.raises(SchemaCacheError, match="allow-list"):
            _validate_override_url("https://evil.example.com/boe.pdf")

    def test_http_scheme_rejected(self) -> None:
        with pytest.raises(SchemaCacheError, match="https"):
            _validate_override_url("http://www.boe.es/boe.pdf")

    def test_file_url_under_tmp_allowed(self, tmp_path: Path) -> None:
        target = tmp_path / "boe.pdf"
        target.write_bytes(b"%PDF-1.4\n%EOF\n")
        _validate_override_url(target.resolve().as_uri())

    def test_file_url_outside_allowed_roots_rejected(self) -> None:
        bogus = Path.home() / "..." / "secret.pdf"
        with pytest.raises(SchemaCacheError, match="file://"):
            _validate_override_url(bogus.resolve().as_uri())


class TestBoeRefFieldValidator:
    def test_dirty_boe_ref_rejected_at_construction(self) -> None:
        from pydantic import AnyHttpUrl, TypeAdapter

        with pytest.raises(ValidationError):
            BoeOrdenSource(
                modelo_code=ModeloCode.MODELO_130,
                boe_ref="../etc/passwd",
                origin_url=TypeAdapter(AnyHttpUrl).validate_python("https://www.boe.es/x.pdf"),
            )


class TestResolveOverride:
    def test_empty_override_returns_empty_map(self, tmp_path: Path) -> None:
        assert _resolve_override(_settings_with(tmp_path, "")) == {}

    def test_invalid_json_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaCacheError, match="valid JSON"):
            _resolve_override(_settings_with(tmp_path, "{not-json"))

    def test_non_object_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaCacheError, match="object"):
            _resolve_override(_settings_with(tmp_path, '["list", "not", "object"]'))

    def test_oversized_override_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaCacheError, match="exceeds"):
            _resolve_override(_settings_with(tmp_path, "x" * (_MAX_OVERRIDE_BYTES + 1)))


class TestFetchBoePdf:
    def test_dirty_boe_ref_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaCacheError, match="invalid boe_ref"):
            fetch_boe_pdf(
                ModeloCode.MODELO_130,
                "../etc/passwd",
                settings=_settings_with(tmp_path),
            )

    def test_unregistered_source_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaCacheError, match="no BOE source registered"):
            fetch_boe_pdf(
                ModeloCode.MODELO_303,
                "BOE-A-NOPE",
                settings=_settings_with(tmp_path),
            )

    def test_file_override_happy_path(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "src.pdf"
        build_fake_boe_pdf(pdf_path, annex_lines=("01 Example",))
        override = json.dumps({"130": {"BOE-A-2023-15412": pdf_path.resolve().as_uri()}})
        result = fetch_boe_pdf(
            ModeloCode.MODELO_130,
            "BOE-A-2023-15412",
            settings=_settings_with(tmp_path / "cache", override),
        )
        assert result.pdf_path.exists()
        assert result.content_length >= 1
        assert len(result.sha256) == 64

    def test_disallowed_http_override_rejected(self, tmp_path: Path) -> None:
        override = json.dumps({"130": {"BOE-A-2023-15412": "http://evil.example.com/x.pdf"}})
        with pytest.raises(SchemaCacheError, match="https"):
            fetch_boe_pdf(
                ModeloCode.MODELO_130,
                "BOE-A-2023-15412",
                settings=_settings_with(tmp_path / "cache", override),
            )

    def test_oversized_file_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pdf_path = tmp_path / "big.pdf"
        pdf_path.write_bytes(b"\x00" * 1024)
        override = json.dumps({"130": {"BOE-A-2023-15412": pdf_path.resolve().as_uri()}})
        # Lower the cap for the test to avoid writing tens of megabytes.
        from . import _fetch as fetch_module

        monkeypatch.setattr(fetch_module, "_MAX_PDF_BYTES", 512)
        with pytest.raises(SchemaCacheError, match="exceeds"):
            fetch_boe_pdf(
                ModeloCode.MODELO_130,
                "BOE-A-2023-15412",
                settings=_settings_with(tmp_path / "cache", override),
            )
        # Partial tempfile cleaned up.
        assert not any((tmp_path / "cache").rglob("*.part"))

    def test_max_pdf_bytes_is_sane(self) -> None:
        # Guards against an accidental downgrade; 64 MiB is the ADR cap.
        assert _MAX_PDF_BYTES == 64 * 1024 * 1024
