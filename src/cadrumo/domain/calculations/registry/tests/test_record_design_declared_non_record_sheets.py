"""A reviewer's non-record adjudication survives into the completeness verdict.

The extractor cannot tell a lookup tab apart from a dropped record body, so the
registry carries that judgement in a ``declared-non-record-sheets.json`` beside
the design. The judgement was read only to improve a message and then discarded,
which left a completely-read workbook refusing as PARTIAL for the rest of its
life. These tests hold the two halves apart: a declared non-record tab is not a
missing record, and an undeclared skip still is.
"""

from __future__ import annotations

import pytest

from .....core.resources._boundary import bundled_path
from ..errors import RegistryValidationError
from ..loader import load_catalogue_file
from ..record_design import extract_record_design
from ..record_design_schema import (
    RecordDesignExtraction,
    RecordDesignSkippedSheet,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_232_DESIGNS = ("aeat-dr-232-2016", "aeat-dr-232-2018")


def _design_path(source_ref: str):
    """Resolve one design binary through its OWN catalogue file.

    Deliberately narrower than the whole-tree loader: this module is about the
    parser's completeness verdict, so an unrelated modelo's validation state
    must not decide whether it can run.
    """
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    return bundled_path() / catalogues.sources[source_ref].corpus_path


@pytest.mark.parametrize("source_ref", _MODELO_232_DESIGNS)
def test_modelo_232_reads_completely_despite_its_declared_lookup_tab(source_ref: str) -> None:
    """Modelo 232's every record sheet parses; only its adjudicated TABLAS tab is skipped.

    Real design, real declaration, real parser -- no constructed extraction. If
    this ever reports an undeclared skip, a record body really did go unread and
    the refusal below is correct rather than something to relax.
    """
    extraction = extract_record_design(_design_path(source_ref))

    assert extraction.skipped, "this design is expected to carry a declared non-record tab"
    assert all(item.declared_non_record for item in extraction.skipped), (
        "every skipped tab here must be reviewer-declared: "
        f"{[item.name for item in extraction.skipped if not item.declared_non_record]}"
    )
    assert extraction.unread_record_sheets == ()
    assert extraction.is_complete
    assert extraction.require_complete() == extraction.sheets


def test_an_undeclared_skip_still_makes_the_read_partial() -> None:
    """The refusal survives: only a declaration clears a skip, never its presence.

    Anti-tautology for the change above. If this passed with an undeclared skip
    admitted, the completeness contract would be decorative and a design that
    lost a record body would generate a structurally thin layout behind a valid
    digest.
    """
    real = extract_record_design(_design_path(_MODELO_232_DESIGNS[1]))

    undeclared = RecordDesignExtraction(
        source=real.source,
        sheets=real.sheets,
        skipped=(RecordDesignSkippedSheet(name="DR23203", reason="has no record-design header"),),
    )
    assert not undeclared.is_complete
    assert undeclared.unread_record_sheets != ()
    with pytest.raises(RegistryValidationError, match="PARTIAL design"):
        undeclared.require_complete()


def test_a_mixed_extraction_reports_only_the_undeclared_skip() -> None:
    """A declared tab beside a real gap must not mask the gap."""
    real = extract_record_design(_design_path(_MODELO_232_DESIGNS[1]))

    mixed = RecordDesignExtraction(
        source=real.source,
        sheets=real.sheets,
        skipped=(
            RecordDesignSkippedSheet(name="TABLAS", reason="lookup tables only", declared_non_record=True),
            RecordDesignSkippedSheet(name="DR23203", reason="has no record-design header"),
        ),
    )
    assert [item.name for item in mixed.unread_record_sheets] == ["DR23203"]
    with pytest.raises(RegistryValidationError) as excinfo:
        mixed.require_complete()
    message = str(excinfo.value)
    assert "DR23203" in message
    assert "TABLAS" not in message, "a declared non-record tab must not be reported as an unread record"


def test_the_default_is_undeclared_so_a_skip_is_partial_until_reviewed() -> None:
    """A skip constructed without the flag stays a partial read."""
    assert RecordDesignSkippedSheet(name="X", reason="y").declared_non_record is False
