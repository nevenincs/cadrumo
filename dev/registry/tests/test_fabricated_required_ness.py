"""The fabricated-required screen separates a derivation from a stand-in."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..analysis.fabricated_required_ness import (
    RequirednessBasis,
    classify_requiredness,
    shipped_requiredness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_three_official_states_are_kept_apart() -> None:
    """Silence, a stated mandate, and a stated something-else are different facts.

    The derivation folds all three into one boolean. That fold is why a field the
    design never spoke about is indistinguishable, once shipped, from one the
    design called optional.
    """
    assert classify_requiredness("OBLIGATORIO") is RequirednessBasis.STATED_MANDATORY
    assert classify_requiredness("obligatorio") is RequirednessBasis.STATED_MANDATORY
    assert classify_requiredness("Opcional") is RequirednessBasis.STATED_OTHERWISE
    assert classify_requiredness("") is RequirednessBasis.DESIGN_SILENT
    assert classify_requiredness("   ") is RequirednessBasis.DESIGN_SILENT
    assert classify_requiredness(None) is RequirednessBasis.DESIGN_SILENT


def test_an_unrecognised_token_is_not_read_as_silence() -> None:
    """A token the matcher does not know is a STATEMENT, and must not become silence.

    Reading it as silence would hide a design that speaks in a vocabulary this
    pipeline has not learned, which is the failure the uncontrolled type
    spellings already demonstrated on another axis.
    """
    assert classify_requiredness("OBLIGATORIO SI APLICA") is RequirednessBasis.STATED_OTHERWISE


def _write(root: Path, validation: str | None, *, required: bool) -> None:
    export = root / "999" / "revisions" / "2026" / "export"
    export.mkdir(parents=True, exist_ok=True)
    (export / "_generation.provenance.json").write_text(
        json.dumps(
            {
                "field_derivations": [
                    {
                        "field": {"id": "modelo-999-page-01-cuota", "required": required},
                        "parser_field": {"validation": validation},
                    },
                ],
            },
        ),
        encoding="utf-8",
    )


def test_a_silent_field_is_reported_as_fabricated(tmp_path: Path) -> None:
    """`required = false` beside a blank cell is a stand-in, not a derivation."""
    _write(tmp_path, "", required=False)

    observation = next(iter(shipped_requiredness(tmp_path)))

    assert observation.is_fabricated
    assert observation.basis is RequirednessBasis.DESIGN_SILENT


def test_a_field_the_design_spoke_about_is_not_reported_as_fabricated(tmp_path: Path) -> None:
    """The screen must not indict a value the design actually supports."""
    _write(tmp_path, "OBLIGATORIO", required=True)

    observation = next(iter(shipped_requiredness(tmp_path)))

    assert not observation.is_fabricated
    assert observation.emitted_required


def test_the_shipped_corpus_carries_a_measurable_population() -> None:
    """A screen reporting nothing across a population it never read proves nothing."""
    observations = tuple(shipped_requiredness())

    assert len(observations) > 10_000
    assert any(item.is_fabricated for item in observations), "the census contradicts a clean corpus"
    assert any(item.basis is RequirednessBasis.STATED_MANDATORY for item in observations)
