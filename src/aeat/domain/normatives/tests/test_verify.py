"""Unit tests for the normative verification pipeline and the real corpus.

Loads the committed catalogue via :func:`aeat.domain.normatives.load_catalogue`,
runs :func:`aeat.domain.normatives.verify_catalogue` against it, and confirms
:func:`aeat.domain.normatives.raise_on_errors` correctly raises
:exc:`aeat.domain.normatives.NormativeError` on dirty reports while remaining a
no-op on clean ones.
"""

from __future__ import annotations

import pytest

from .. import (
    NormativeError,
    cite,
    load_catalogue,
    raise_on_errors,
    verify_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXPECTED_IDS = {
    "ley-35-2006",
    "rd-439-2007",
    "ley-37-1992",
    "rd-1624-1992",
    "ley-58-2003",
    "rd-1065-2007",
    "orden-hac-242-2025",
}


class TestRealCorpus:
    """End-to-end checks against the committed normative corpus."""

    def test_load_real_corpus(self) -> None:
        catalogue = load_catalogue()
        loaded_ids = {ref.id for ref in catalogue}
        assert _EXPECTED_IDS.issubset(loaded_ids)

    def test_verify_real_corpus_clean(self) -> None:
        report = verify_catalogue()
        assert report.clean is True, f"verify produced issues: {report.issues}"
        assert report.issues == ()

    def test_raise_on_errors_noop_when_clean(self) -> None:
        report = verify_catalogue()
        assert report.clean, f"corpus must be clean for the noop assertion to be meaningful: {report.issues}"
        result = raise_on_errors(report)
        assert result is None

    def test_every_committed_articulo_renders(self) -> None:
        catalogue = load_catalogue()
        rendered: list[str] = []
        for reference in catalogue:
            for articulo in reference.articulos:
                rendered.append(cite(reference, articulo))
        assert rendered
        for citation in rendered:
            assert "BOE-A-" in citation


class TestRaiseOnErrors:
    """Behaviour of :func:`aeat.domain.normatives.raise_on_errors`."""

    def test_raises_on_dirty_report(self) -> None:
        from .. import NormativeVerificationIssue, NormativeVerificationReport

        report = NormativeVerificationReport(
            issues=(
                NormativeVerificationIssue(
                    level="error",
                    code="synthetic",
                    message="test-only failure",
                ),
            ),
        )
        with pytest.raises(NormativeError, match=r"normative"):
            raise_on_errors(report)
