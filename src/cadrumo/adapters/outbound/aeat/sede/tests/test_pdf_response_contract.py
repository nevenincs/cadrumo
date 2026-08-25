"""One PDF-response contract across every sede capture path.

A captured PDF becomes stored filing evidence: its bytes are persisted
under a ``declaration_pdf`` / ``justificante_pdf`` artefact kind and are
what a casilla value is defended with later. So "is this response a PDF"
is an evidence question, not a formatting one, and every capture path must
answer it identically.

Three paths fetch a CSV-keyed PDF — the row-capture branch in
``_declarations_fetch``, ``_declarations.capture_declaration``, and
``_walker.capture_justificante``. They previously carried three
hand-written copies of the same status / body / content-type checks, and
the copies had drifted apart: the row-capture branch accepted any header
merely CONTAINING ``"pdf"``. This module pins the single contract and the
routing that keeps it single.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import TypedDict

import pytest

from ......core import scan_directory
from ......core.external_constants import PDF_MIME_TYPE
from .. import _declarations, _declarations_fetch, _walker
from .._adapter_utils import assert_pdf_response, response_media_type
from ..errors import JustificanteFetchError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
_SUBJECT = "CSV='FIXTURECSV1234X7'"


class _PdfResponseKwargs(TypedDict):
    status: int
    content_type: str
    body: bytes


# Header values that are NOT ``application/pdf`` but survive a substring
# test. Each one is a real historical hole rather than a hypothetical:
# the first two passed the row-capture branch, and the third passed ALL
# THREE paths, including the two the audit treated as canonical.
_NON_PDF_LOOKALIKES: tuple[str, ...] = (
    "application/notpdf",
    "text/pdf",
    "x-application/pdf-trap",
    "application/pdf-invoice",
    "multipart/pdf",
)

# Header values AEAT legitimately sends for a real PDF.
_REAL_PDF_HEADERS: tuple[str, ...] = (
    PDF_MIME_TYPE,
    f"{PDF_MIME_TYPE}; charset=binary",
    f"  {PDF_MIME_TYPE.upper()}  ",
    f"{PDF_MIME_TYPE};charset=utf-8;name=justificante.pdf",
)


class TestMediaTypeExtraction:
    """The header's parameter tail is not part of the media type."""

    @pytest.mark.parametrize("header", _REAL_PDF_HEADERS)
    def test_real_pdf_headers_reduce_to_the_canonical_media_type(self, header: str) -> None:
        """Parameters, casing and surrounding space do not change what is named."""
        assert response_media_type(header) == PDF_MIME_TYPE

    @pytest.mark.parametrize("header", _NON_PDF_LOOKALIKES)
    def test_lookalike_headers_do_not_reduce_to_the_canonical_media_type(self, header: str) -> None:
        """A type that merely contains the token is a different media type."""
        assert response_media_type(header) != PDF_MIME_TYPE


class TestPdfResponseContract:
    """``assert_pdf_response`` is the one gate every capture path runs."""

    @pytest.mark.parametrize("header", _REAL_PDF_HEADERS)
    def test_a_real_pdf_response_is_accepted(self, header: str) -> None:
        """A 2xx, non-empty, PDF-typed response passes."""
        assert_pdf_response(status=200, content_type=header, body=_PDF_BYTES, subject=_SUBJECT)

    @pytest.mark.parametrize("header", _NON_PDF_LOOKALIKES)
    def test_a_non_pdf_lookalike_is_refused(self, header: str) -> None:
        """A header containing "pdf" is not thereby a PDF.

        This is the substring hole. Every value here would have been
        stored as PDF evidence by at least one capture path before the
        contract was unified.
        """
        with pytest.raises(JustificanteFetchError) as exc_info:
            assert_pdf_response(status=200, content_type=header, body=_PDF_BYTES, subject=_SUBJECT)
        assert header in str(exc_info.value)
        assert _SUBJECT in str(exc_info.value)

    @pytest.mark.parametrize("header", ["text/html", "application/json", ""])
    def test_an_unrelated_content_type_is_refused(self, header: str) -> None:
        """An auth-gate or error page is not a PDF."""
        with pytest.raises(JustificanteFetchError):
            assert_pdf_response(status=200, content_type=header, body=_PDF_BYTES, subject=_SUBJECT)

    @pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 404, 500, 503])
    def test_a_non_2xx_status_is_refused(self, status: int) -> None:
        """Status is checked before the body, so a redirect never yields evidence."""
        with pytest.raises(JustificanteFetchError) as exc_info:
            assert_pdf_response(
                status=status,
                content_type=PDF_MIME_TYPE,
                body=_PDF_BYTES,
                subject=_SUBJECT,
            )
        assert str(status) in str(exc_info.value)

    def test_an_empty_body_is_refused(self) -> None:
        """A 200 with a PDF header and no bytes is not evidence."""
        with pytest.raises(JustificanteFetchError) as exc_info:
            assert_pdf_response(status=200, content_type=PDF_MIME_TYPE, body=b"", subject=_SUBJECT)
        assert "empty PDF body" in str(exc_info.value)

    def test_the_subject_handle_reaches_every_failure_message(self) -> None:
        """Each capture path keeps its own diagnostic handle in the message."""
        cases: tuple[_PdfResponseKwargs, ...] = (
            {"status": 500, "content_type": PDF_MIME_TYPE, "body": _PDF_BYTES},
            {"status": 200, "content_type": PDF_MIME_TYPE, "body": b""},
            {"status": 200, "content_type": "text/html", "body": _PDF_BYTES},
        )
        for kwargs in cases:
            with pytest.raises(JustificanteFetchError) as exc_info:
                assert_pdf_response(subject="CSV='DISTINCTHANDLE9'", **kwargs)
            assert "CSV='DISTINCTHANDLE9'" in str(exc_info.value)


class TestEveryLookalikeWasGenuinelyAdmittedBefore:
    """Each hostile fixture must be one the retired code actually accepted.

    A hostile value the pre-fix code ALREADY refused proves nothing while
    sitting in a discriminating set -- it inflates the proof count invisibly.
    These are the two retired predicates, reproduced verbatim, so each fixture
    is shown to have been a real hole rather than assumed to be one.
    """

    @staticmethod
    def _retired_row_capture_accepted(content_type: str) -> bool:
        """The row-capture branch: ``if "pdf" not in content_type.lower()``."""
        return "pdf" in content_type.lower()

    @staticmethod
    def _retired_sibling_accepted(content_type: str) -> bool:
        """Both siblings: ``if _PDF_MIME_TYPE not in content_type.lower()``."""
        return PDF_MIME_TYPE in content_type.lower()

    @pytest.mark.parametrize("header", _NON_PDF_LOOKALIKES)
    def test_the_lookalike_was_accepted_by_at_least_one_retired_predicate(self, header: str) -> None:
        """DISCRIMINATING fixture control: this value really was admitted before."""
        assert self._retired_row_capture_accepted(header) or self._retired_sibling_accepted(header), (
            f"{header!r} was refused by BOTH retired predicates, so it never demonstrated a hole; "
            "it belongs in SUPPORTING, not in the hostile set"
        )

    @pytest.mark.parametrize("header", _REAL_PDF_HEADERS)
    def test_the_control_would_reject_a_genuine_pdf_header(self, header: str) -> None:
        """Exercises the control itself, so its verdicts are not taken on trust.

        A control that returns "was admitted" for everything would pass the
        test above no matter what. Genuine PDF headers must also be reported
        as admitted by the retired predicates -- they were -- which confirms
        the control is reading the header rather than returning a constant.
        """
        assert self._retired_row_capture_accepted(header)
        assert self._retired_sibling_accepted(header)

    @pytest.mark.parametrize("header", ["text/html", "application/json", ""])
    def test_the_control_reports_unrelated_types_as_refused(self, header: str) -> None:
        """The other half of the control: it must be able to say "no".

        Without this, the control could be a constant-true function and the
        fixture check above would be vacuous.
        """
        assert not self._retired_row_capture_accepted(header)
        assert not self._retired_sibling_accepted(header)

    def test_the_hostile_set_spans_both_retired_predicates(self) -> None:
        """Records WHICH hole each fixture demonstrates, so the split is visible.

        Three fixtures were admitted only by the row-capture branch; two were
        admitted by ALL THREE paths, including the two the audit called
        canonical. Pinned as an exact partition so a future edit to the
        fixture list cannot silently drop either class.
        """
        row_only = {
            h
            for h in _NON_PDF_LOOKALIKES
            if self._retired_row_capture_accepted(h) and not self._retired_sibling_accepted(h)
        }
        all_three = {h for h in _NON_PDF_LOOKALIKES if self._retired_sibling_accepted(h)}
        assert row_only == {"application/notpdf", "text/pdf", "multipart/pdf"}
        assert all_three == {"x-application/pdf-trap", "application/pdf-invoice"}


class TestEveryCapturePathRoutesThroughTheContract:
    """No capture path may re-grow its own copy of the checks."""

    _CAPTURE_SITES = (
        (_declarations_fetch, "_capture_row_pdf_artefact"),
        (_declarations, "capture_declaration"),
        (_walker, "capture_justificante"),
    )

    @pytest.mark.parametrize(("module", "function"), _CAPTURE_SITES)
    def test_the_capture_path_calls_the_canonical_validator(self, module: object, function: str) -> None:
        """Each of the three paths delegates to ``assert_pdf_response``."""
        source = inspect.getsource(getattr(module, function))
        assert "_assert_pdf_response(" in source, (
            f"{function} does not route its PDF response through the canonical validator"
        )

    @pytest.mark.parametrize(("module", "function"), _CAPTURE_SITES)
    def test_the_capture_path_carries_no_inline_content_type_predicate(
        self,
        module: object,
        function: str,
    ) -> None:
        """A re-grown local MIME test is the exact drift this contract removes."""
        source = inspect.getsource(getattr(module, function))
        offenders = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("if ", "elif ")) and "content_type" in line
        ]
        assert not offenders, f"{function} re-grew an inline content-type predicate: {offenders}"

    def test_no_sede_module_tests_a_pdf_mime_type_by_substring(self) -> None:
        """Project-wide: the substring form must not reappear anywhere in sede.

        Scans production sede sources for a comparison that asks whether a
        content type CONTAINS a pdf token, which is the shape that admitted
        ``application/notpdf`` and ``x-application/pdf-trap``.
        """
        sede_root = Path(_walker.__file__).resolve().parent
        offenders: list[str] = []
        for source_path in scan_directory(sede_root, pattern="*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                if not any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                    continue
                rendered = ast.unparse(node)
                if "content_type" in rendered and "pdf" in rendered.lower():
                    offenders.append(f"{source_path.name}: {rendered}")
        assert not offenders, "sede still tests a PDF content type by substring:\n" + "\n".join(offenders)
