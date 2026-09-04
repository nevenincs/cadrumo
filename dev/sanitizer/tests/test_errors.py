"""Error-contract tests for the PDF sanitizer."""

from __future__ import annotations

from importlib import import_module

import pytest

from cadrumo.core.errors.hierarchy import CadrumoError

from .. import errors
from ..errors import AlreadySanitizedError, SanitizationError, SanitizerSourceParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

sanitizer_package = import_module("..", __package__)

_SENSITIVE_BASENAME = "12345678Z-sanitizer-source.pdf"
_SOURCE_SHA256 = "6a84b40c8c1b6a6771598f77d5334b9af858f5fbdc8fe96c3a8b2511af0f45bc"


def test_errors_live_in_public_defining_module_without_facade_reexports() -> None:
    """The public module owns the hierarchy and the package forwards nothing.

    The assertion used to read the package's ``__all__`` and check the two error
    names were absent from it, which assumed an ``__all__`` existed - true only
    while the initialiser forwarded twenty-three other names. The property it was
    after survives and is stated directly: the initialiser exports nothing, so no
    name can be absent from a list that no longer exists.
    """
    assert errors.__name__ == "dev.sanitizer.errors"
    assert {SanitizationError.__module__, AlreadySanitizedError.__module__} == {errors.__name__}
    assert not hasattr(sanitizer_package, "__all__"), "an inert initialiser declares no exports"
    assert not hasattr(sanitizer_package, "SanitizationError")
    assert not hasattr(sanitizer_package, "AlreadySanitizedError")
    # Nothing but submodules, which is what importing a package leaves behind
    # and the only thing an inert initialiser may carry.
    public = [name for name in vars(sanitizer_package) if not name.startswith("_")]
    assert all(getattr(sanitizer_package, name).__name__.startswith("dev.sanitizer.") for name in public), (
        f"the initialiser still forwards non-module names: {public}"
    )


def test_the_family_stays_outside_the_product_error_registry() -> None:
    """The sanitiser hierarchy must not re-enter ``CadrumoError``.

    ``CadrumoError.__init_subclass__`` binds every subclass to the shipped
    error-code registry at class-creation time and refuses one that declares
    no code, and each declared code needs a message key in all four locale
    catalogues. This package ships in neither the wheel nor the sdist, so a
    code and a translated string here would be product contract nothing
    reaches. Re-parenting the root is the single edit that would silently
    undo that, which is why it is asserted rather than left to the docstring.
    """
    assert not issubclass(SanitizationError, CadrumoError)


class TestSanitizerSourceParseError:
    """Source-parse errors expose only redacted source and parser-failure type."""

    def test_uses_sanitizer_error_hierarchy_and_redacted_context(self, tmp_path) -> None:
        source = tmp_path / _SENSITIVE_BASENAME

        error = SanitizerSourceParseError(
            f"pikepdf could not parse source bytes from {source}",
            failure="PdfError",
        )

        rendered = str(error)
        assert isinstance(error, SanitizationError)
        assert _SENSITIVE_BASENAME not in rendered
        assert str(source) not in rendered
        assert "<input-pdf>" in rendered
        assert error.context == {"source": "<input-pdf>", "failure": "PdfError"}
        assert error.failure == "PdfError"


class TestAlreadySanitizedError:
    """Already-sanitized refusal keeps the full digest typed, not rendered."""

    def test_does_not_render_full_source_hash(self) -> None:
        error = AlreadySanitizedError(source_sha256=_SOURCE_SHA256)

        rendered = str(error)
        assert isinstance(error, SanitizationError)
        assert _SOURCE_SHA256 not in rendered
        assert "already" in rendered
        assert error.source_sha256 == _SOURCE_SHA256
        assert error.context == {"source_sha256_prefix": _SOURCE_SHA256[:16]}
