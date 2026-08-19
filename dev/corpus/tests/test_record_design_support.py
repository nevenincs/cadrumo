"""Integrity gate for the supported AEAT record-design corpus."""

from __future__ import annotations

import pytest

from dev.corpus.sync_aeat_record_design_corpus import check

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_supported_record_design_corpus_is_complete_and_current() -> None:
    """The captured official matrix and every manifested source rehash cleanly."""
    check()
