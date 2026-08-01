"""Licence admission tests for the evidence-corpus sourcing tool."""

from __future__ import annotations

import pytest

from dev._build_evidence_corpus import _licence_is_clean

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("licence", ("Public domain", "CC0 1.0", "CC-BY 4.0", "CC BY-SA 4.0", "PD-old-100"))
def test_clean_licence_tokens_are_admitted(licence: str) -> None:
    """The production predicate admits the explicitly supported clean families."""
    assert _licence_is_clean(licence)


@pytest.mark.parametrize("licence", ("CC-BY-ND 4.0", "CC-BY-NC 4.0", "CC-BY-NC-SA 4.0", "CC-BY-SA-NC 4.0"))
def test_restricted_licence_tokens_are_refused(licence: str) -> None:
    """NC and ND variants may not enter a corpus declared licence-clean."""
    assert not _licence_is_clean(licence)
