"""Error-contract tests for the PDF sanitizer."""

from __future__ import annotations

import pytest

from .....core.errors import AeatError
from .._errors import AlreadySanitizedError, SanitizerSourceParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_SENSITIVE_BASENAME = "12345678Z-sanitizer-source.pdf"
_SOURCE_SHA256 = "6a84b40c8c1b6a6771598f77d5334b9af858f5fbdc8fe96c3a8b2511af0f45bc"


class TestSanitizerSourceParseError:
    """Source-parse errors expose only redacted source and parser-failure type."""

    def test_uses_aeat_error_hierarchy_and_redacted_context(self, tmp_path) -> None:
        source = tmp_path / _SENSITIVE_BASENAME

        error = SanitizerSourceParseError(
            f"pikepdf could not parse source bytes from {source}",
            failure="PdfError",
        )

        rendered = str(error)
        assert isinstance(error, AeatError)
        assert _SENSITIVE_BASENAME not in rendered
        assert str(source) not in rendered
        assert "<input-pdf>" in rendered
        assert error.context == {"source": "<input-pdf>", "failure": "PdfError"}
        assert error.failure == "PdfError"
        assert error.translated_message == "errors.fail.fail_sanitization_source_parse"


class TestAlreadySanitizedError:
    """Already-sanitized refusal keeps the full digest typed, not rendered."""

    def test_does_not_render_full_source_hash(self) -> None:
        error = AlreadySanitizedError(source_sha256=_SOURCE_SHA256)

        rendered = str(error)
        assert isinstance(error, AeatError)
        assert _SOURCE_SHA256 not in rendered
        assert "already" in rendered
        assert error.source_sha256 == _SOURCE_SHA256
        assert error.context == {"source_sha256_prefix": _SOURCE_SHA256[:16]}
        assert error.translated_message == "errors.refused.refused_sanitization_already_sanitized"
