"""Unit tests for the verify pipeline and the real corpus."""

from __future__ import annotations

import pytest

from . import (
    NormativeError,
    cite,
    load_catalogue,
    raise_on_errors,
    verify_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

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
    def test_load_real_corpus(self) -> None:
        catalogue = load_catalogue()
        loaded_ids = {ref.id for ref in catalogue}
        assert _EXPECTED_IDS.issubset(loaded_ids)

    def test_verify_real_corpus_clean(self) -> None:
        report = verify_catalogue()
        assert report.clean, f"verify produced issues: {report.issues}"

    def test_raise_on_errors_noop_when_clean(self) -> None:
        report = verify_catalogue()
        raise_on_errors(report)  # must not raise

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
    def test_raises_on_dirty_report(self) -> None:
        from . import VerificationIssue, VerificationReport

        report = VerificationReport(
            issues=(
                VerificationIssue(
                    level="error",
                    code="synthetic",
                    message="test-only failure",
                ),
            )
        )
        with pytest.raises(NormativeError):
            raise_on_errors(report)
