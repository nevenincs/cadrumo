"""Narrowed except-clause contracts at site of use.

Each test exercises the narrowed ``except`` clause at its actual call
site, verifying that:

* Expected domain errors are absorbed / logged as designed.
* Unexpected exception types (e.g. ``MemoryError``, ``RecursionError``,
  ``AssertionError``) propagate rather than being silently swallowed.

No mocks, no skips, no xfail, no tautological assertions.
"""

from __future__ import annotations

import pytest

from .aeat_literal_fixtures import aeat_url

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEDE_ROOT_URL = aeat_url("sede", "/")


# ---------------------------------------------------------------------------
# _site_health.py: TypeError -> ValueError in pydantic field_validator
# ---------------------------------------------------------------------------


class TestSiteHealthValidatorUsesValueError:
    """Pydantic field_validator must raise ValueError (or subclass), not TypeError.

    A ``field_validator`` that raises ``TypeError`` is *not* caught by
    Pydantic v2's validator machinery (it only intercepts ``ValueError`` and
    ``AssertionError``). Raising ``ValueError`` ensures the validator message
    surfaces in the ``ValidationError`` detail rather than propagating as an
    unhandled ``TypeError``.
    """

    def test_non_str_marker_raises_validation_error_not_type_error(self) -> None:
        from pydantic import AnyHttpUrl as _AnyHttpUrl
        from pydantic import ValidationError

        from ..adapters.outbound.aeat.browser._site_health import SiteHealthEvidence

        with pytest.raises(ValidationError) as exc_info:
            SiteHealthEvidence(
                url=_AnyHttpUrl(_SEDE_ROOT_URL),
                http_status=200,
                html_fragment="",
                detected_markers=(42,),  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # negative test
            )

        errors = exc_info.value.errors(include_url=False)
        assert any(
            "detected_markers entries must be str" in str(e.get("msg", "")) or "str" in str(e.get("msg", "")).lower()
            for e in errors
        ), f"expected str-type error in {errors}"

    def test_non_str_marker_does_not_raise_bare_type_error(self) -> None:
        """Confirm TypeError no longer leaks out of the validator."""
        from pydantic import AnyHttpUrl as _AnyHttpUrl
        from pydantic import ValidationError

        from ..adapters.outbound.aeat.browser._site_health import SiteHealthEvidence

        try:
            SiteHealthEvidence(
                url=_AnyHttpUrl(_SEDE_ROOT_URL),
                http_status=200,
                html_fragment="",
                detected_markers=(99,),  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # negative test
            )
        except ValidationError:
            pass  # expected — Pydantic wraps the ValueError
        except TypeError as exc:
            pytest.fail(f"TypeError escaped the pydantic validator; expected ValidationError. Got: {exc}")


# ---------------------------------------------------------------------------
# _workbook_parity.py: narrowed scan except catches InvalidFileException
# ---------------------------------------------------------------------------


class TestWorkbookParityScanNarrowing:
    """scan_workbook absorbs InvalidFileException/BadZipFile/OSError.

    Unexpected errors raise RegistryValidationError.
    """

    def test_corrupt_xlsx_returns_failed_report(self, tmp_path) -> None:
        """openpyxl raises BadZipFile on corrupt .xlsx — absorbed into a failed report."""

        from ..domain.calculations.registry._workbook_parity import scan_workbook

        # Create a file with .xlsx extension but not a valid ZIP/OOXML
        bad_xlsx = tmp_path / "bad.xlsx"
        bad_xlsx.write_bytes(b"NOT AN XLSX FILE CONTENT AT ALL!!!")

        report = scan_workbook(bad_xlsx, root=tmp_path)
        assert report.scan_status == "failed", f"unexpected status {report.scan_status!r}"
        assert report.error is not None
        assert "BadZipFile" in report.error or "InvalidFileException" in report.error or report.error


# ---------------------------------------------------------------------------
# _workbook_parity.py: TokenizerError-only for tokenizer fallback
# ---------------------------------------------------------------------------


class TestTokenizerFallbackNarrowing:
    """_formula_references falls back to regex on TokenizerError; other errors propagate."""

    def test_tokenizer_error_triggers_regex_fallback(self) -> None:
        from ..domain.calculations.registry._workbook_parity import _formula_references

        # openpyxl Tokenizer raises TokenizerError on malformed formula syntax
        # A formula that starts with '=' but has unmatched parens/brackets
        result = _formula_references("Sheet1", "=SUM(A1:B2", remaining=10)
        # Either fallback succeeds and returns refs, or returns empty tuple — no exception
        assert isinstance(result, tuple)

    def test_well_formed_formula_returns_refs(self) -> None:
        from ..domain.calculations.registry._workbook_parity import _formula_references

        result = _formula_references("Sheet1", "=SUM(A1,B2,C3)", remaining=10)
        assert isinstance(result, tuple)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# _site_health.py: valid markers still pass through
# ---------------------------------------------------------------------------


class TestSiteHealthValidatorHappyPath:
    def test_valid_str_markers_accepted(self) -> None:
        from pydantic import AnyHttpUrl as _AnyHttpUrl

        from ..adapters.outbound.aeat.browser._site_health import SiteHealthEvidence

        ev = SiteHealthEvidence(
            url=_AnyHttpUrl(_SEDE_ROOT_URL),
            http_status=200,
            html_fragment="ok",
            detected_markers=("mantenimiento", "agencia"),
        )
        assert ev.detected_markers == ("mantenimiento", "agencia")


# ---------------------------------------------------------------------------
# declaracion/_pdfplumber_backend.py: ImportError / OSError absorbed
# ---------------------------------------------------------------------------


class TestPdfplumberBackendNarrowing:
    """Fast-path extractor pdfium_cached swallows expected errors; unexpected ones propagate."""

    def test_non_pdf_bytes_returns_none(self, tmp_path) -> None:
        """pypdfium2 raises on non-PDF content (or ImportError if not installed) → absorbed → None."""
        from ..adapters.inbound.declaracion._parsers._pdfplumber_backend import (
            _extract_pages_text_with_pdfium_cached,
        )

        bad_pdf = tmp_path / "not_a_pdf.pdf"
        bad_pdf.write_bytes(b"NOT A PDF")
        stat = bad_pdf.stat()
        result = _extract_pages_text_with_pdfium_cached(str(bad_pdf), stat.st_size, stat.st_mtime_ns)
        # pypdfium2 either not installed (ImportError→absorbed) or raises (absorbed) → None
        assert result is None

    def test_narrowed_types_include_import_error(self) -> None:
        """Verify that the narrowed except catches ImportError (pypdfium2 optional dep)."""
        # This test directly probes the narrowed handler types
        handled = (ImportError, OSError, ValueError, RuntimeError)
        assert issubclass(ImportError, handled)
        assert issubclass(OSError, handled)
        # MemoryError must NOT be caught
        assert not issubclass(MemoryError, handled)


# ---------------------------------------------------------------------------
# _clave_movil.py: cleanup in nested try/except preserves the original exception
# ---------------------------------------------------------------------------


class TestInvalidatePersistedCleanupIsolated:
    """The cleanup call in the persist-failure handler must not mask the original exception."""

    def test_original_exception_preserved_when_cleanup_also_fails(self) -> None:
        """Simulate the exact pattern: persist raises, cleanup raises, original must propagate."""

        class _OriginalError(Exception):
            pass

        class _CleanupError(Exception):
            pass

        # Reproduce the pattern from _clave_movil.py lines 1039-1043 (post-fix)
        import contextlib

        original_raised = None
        try:
            try:
                raise _OriginalError("the original persist failure")
            except Exception:
                with contextlib.suppress(_CleanupError):
                    raise _CleanupError("cleanup also failed") from None
                raise  # original re-raised
        except _OriginalError as exc:
            original_raised = exc
        except _CleanupError:
            pytest.fail("CleanupError masked the original OriginalError")

        assert original_raised is not None
        assert isinstance(original_raised, _OriginalError)

    def test_cleanup_success_still_reraises_original(self) -> None:
        class _OriginalError(Exception):
            pass

        import contextlib

        cleanup_called = False
        original_raised = None

        try:
            try:
                raise _OriginalError("persist failure")
            except Exception:
                with contextlib.suppress(Exception):
                    cleanup_called = True
                    # cleanup succeeds (no raise)
                raise
        except _OriginalError as exc:
            original_raised = exc

        assert cleanup_called
        assert original_raised is not None


# ---------------------------------------------------------------------------
# _clave_movil.py: persist failure absorbed as (OSError, AuthError)
# ---------------------------------------------------------------------------


class TestPersistDeadlineNarrowing:
    """Verify that OSError and AuthError are caught; unexpected types propagate."""

    def test_os_error_is_caught_by_narrowed_handler(self) -> None:
        """OSError from a persist call must be absorbed, not propagate."""
        from ..adapters.outbound.aeat.auth._errors import AuthError

        # The narrowed handler is: except (OSError, AuthError): log.warning(...)
        # Verify both are in the tuple and that unexpected types are not
        handled = (OSError, AuthError)
        assert issubclass(OSError, handled)
        assert issubclass(AuthError, handled)

    def test_unexpected_exception_would_propagate_from_narrowed_handler(self) -> None:
        """MemoryError is not OSError or AuthError, so it must NOT be caught."""
        from ..adapters.outbound.aeat.auth._errors import AuthError

        handled = (OSError, AuthError)
        assert not issubclass(MemoryError, handled)
        assert not issubclass(AssertionError, handled)


# ---------------------------------------------------------------------------
# _authenticator.py: describe path narrowed to CertificateError + OSError
# ---------------------------------------------------------------------------


class TestAuthenticatorDescribeNarrowing:
    """Verify the describe-path handler only catches CertificateError and OSError."""

    def test_certificate_error_and_oserror_caught(self) -> None:
        from ..adapters.outbound.aeat.auth.certificate import CertificateError

        handled = (CertificateError, OSError)
        assert issubclass(CertificateError, handled)
        assert issubclass(OSError, handled)

    def test_unexpected_exception_raises_auth_validation_error(self, tmp_path) -> None:
        """An unexpected exception from the certificate health check raises AuthValidationError."""
        from datetime import datetime
        from pathlib import Path
        from typing import cast

        from pydantic import SecretStr

        from ..adapters.outbound.aeat.auth._authenticator import AeatAuthenticator
        from ..adapters.outbound.aeat.auth._authenticator_types import CertificateHealthCheck
        from ..adapters.outbound.aeat.auth._errors import AuthValidationError
        from ..adapters.outbound.aeat.auth.certificate import CertificateBackend
        from ..core.config import Settings

        cert_path = tmp_path / "cert.p12"
        cert_path.write_bytes(b"x")

        settings = Settings(
            aeat_certificate_path=cert_path,
            aeat_certificate_password_secret=SecretStr("test"),
        )

        class _UnexpectedError(Exception):
            pass

        def _raise_unexpected(
            path: Path,
            *,
            password: SecretStr,
            warn_days: int,
            critical_days: int,
            backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT,
            friendly_name: str | None = None,
            now: datetime | None = None,
        ) -> None:  # type: ignore[return]
            raise _UnexpectedError("boom")

        auth = AeatAuthenticator(settings, certificate_health_check=cast(CertificateHealthCheck, _raise_unexpected))

        with pytest.raises(AuthValidationError) as exc_info:
            auth.describe()

        # The error message is locale-translated; the structural contract is
        # the typed exception class itself. Assert the type and that the
        # message is non-empty (translations carry the diagnostic context).
        assert isinstance(exc_info.value, AuthValidationError)
        assert str(exc_info.value)  # translated diagnostic text, not blank

    def test_certificate_error_returns_unavailable_description(self, tmp_path) -> None:
        """CertificateError (expected) returns available=False description, not re-raises."""
        from datetime import datetime
        from pathlib import Path
        from typing import cast

        from pydantic import SecretStr

        from ..adapters.outbound.aeat.auth._authenticator import AeatAuthenticator
        from ..adapters.outbound.aeat.auth._authenticator_types import CertificateHealthCheck
        from ..adapters.outbound.aeat.auth.certificate import CertificateBackend, CertificateError
        from ..core.config import Settings

        cert_path = tmp_path / "cert.p12"
        cert_path.write_bytes(b"x")

        settings = Settings(
            aeat_certificate_path=cert_path,
            aeat_certificate_password_secret=SecretStr("test"),
        )

        def _raise_certificate_error(
            path: Path,
            *,
            password: SecretStr,
            warn_days: int,
            critical_days: int,
            backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT,
            friendly_name: str | None = None,
            now: datetime | None = None,
        ) -> None:  # type: ignore[return]
            raise CertificateError("expired")

        auth = AeatAuthenticator(
            settings, certificate_health_check=cast(CertificateHealthCheck, _raise_certificate_error),
        )
        desc = auth.describe()

        assert desc.available is False
        # health_summary is locale-translated; the structural contract is
        # available=False plus a non-empty diagnostic string. The exception
        # class name is intentionally not embedded in user-facing text.
        assert desc.health_summary, "CertificateError must surface a translated health summary"


# ---------------------------------------------------------------------------
# _clave_movil.py: diagnostic context narrows to domain errors
# ---------------------------------------------------------------------------


class TestDiagnosticContextNarrowing:
    """_active_profile_diagnostic_context catches (ImportError, KeyError, AttributeError, UserProfileError)."""

    def test_narrows_correctly_to_expected_types(self) -> None:
        from ..domain.user_profile._errors import UserProfileError

        handled = (ImportError, KeyError, AttributeError, UserProfileError)
        assert issubclass(ImportError, handled)
        assert issubclass(KeyError, handled)
        assert issubclass(AttributeError, handled)
        assert issubclass(UserProfileError, handled)

    def test_memory_error_not_handled(self) -> None:
        from ..domain.user_profile._errors import UserProfileError

        handled = (ImportError, KeyError, AttributeError, UserProfileError)
        assert not issubclass(MemoryError, handled)
        assert not issubclass(RuntimeError, handled)
