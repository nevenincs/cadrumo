"""Cross-artifact consistency: the 303 casilla-gap story.

The "Modelo 303 2024 ruleset declares casillas that have no
schema field" gap is recorded in three places:

1. ``_EXPECTED_GAPS["303.2024"]`` in
   :mod:`.test_ruleset_schema_coverage` — the authoritative set.
2. Provenance notes at
   ``tests/fixtures/dr_specs/dr303e24.json`` ``source.notes`` —
   the fixture-level explanation a reader reaches from the
   generator output.
3. The docstring + assertion-error messages of
   :mod:`.test_integration_kent_303_e2e` — the developer-facing
   description surfaced whenever the E2E test fails.

When any one drifts (the authoritative set shrinks because a
fixture regeneration closed a gap, or expands because a new
ruleset casilla was added without schema backing), the other two
can fall out of sync silently. all three as a
single invariant so any consistent update has to touch the whole
story.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from .test_ruleset_schema_coverage import _EXPECTED_GAPS

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent
    / "tests"
    / "fixtures"
    / "dr_specs"
    / "dr303e24.json"
)


class TestGapStoryConsistency:
    def test_fixture_notes_mention_every_missing_casilla(self) -> None:
        """Every casilla in ``_EXPECTED_GAPS["303.2024"]`` must be named in
        the dr303e24.json source.notes field — the fixture is the surface
        a reader hits when tracing the generator output, so the note must
        not drift behind the test source."""
        doc = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        notes = doc["source"].get("notes", "")
        for cid in sorted(_EXPECTED_GAPS["303.2024"]):
            assert cid in notes, (
                f"fixture source.notes does not mention casilla {cid}; "
                f"_EXPECTED_GAPS was updated without a matching fixture-note update."
            )

    def test_fixture_notes_cite_sibling_tests(self) -> None:
        """The fixture notes must mention / 114 and the coverage
        test filename so a reader lands on the authoritative lock."""
        doc = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        notes = doc["source"].get("notes", "")
        # Must cite the coverage test by filename (or close match).
        assert "test_ruleset_schema_coverage" in notes, (
            "fixture source.notes should cite test_ruleset_schema_coverage.py so "
            "readers can trace the gap story to its authoritative lock."
        )

    def test_e2e_docstring_mentions_every_missing_casilla(self) -> None:
        """The E2E test's module docstring must also name every
        casilla in the gap — stale docstrings mislead developers reading
        a failing test stack."""
        from . import test_integration_kent_303_e2e

        doc = test_integration_kent_303_e2e.__doc__ or ""
        for cid in sorted(_EXPECTED_GAPS["303.2024"]):
            assert cid in doc, (
                f"test_integration_kent_303_e2e.__doc__ does not mention casilla "
                f"{cid}; the _EXPECTED_GAPS shrank/grew and the E2E "
                f"docstring is now stale."
            )

    def test_generated_module_docstring_mirrors_fixture_notes(self) -> None:
        """the generator embeds ``source.notes`` into the module
        docstring. If someone updates the fixture without regenerating, the
        module's docstring goes stale. Lock every gap casilla to also appear
        in the generated module's docstring.
        """
        from . import modelo_303_2024

        doc = modelo_303_2024.__doc__ or ""
        for cid in sorted(_EXPECTED_GAPS["303.2024"]):
            assert cid in doc, (
                f"modelo_303_2024 docstring does not mention casilla {cid}; "
                f"the fixture was updated without regenerating the module. "
                f"Run ``python -m aeat.adapters.outbound.aeat.export._formats._generate "
                f"tests/fixtures/dr_specs/dr303e24.json src/aeat/submission/"
                f"_formats/modelo_303_2024.py``."
            )

    def test_generated_module_docstring_cites_authoritative_lock(self) -> None:
        """The generator output must carry the pointer to the authoritative
        test_ruleset_schema_coverage lock. A regeneration that forgets this
        leaves readers of the .py file without a trace back."""
        from . import modelo_303_2024

        doc = modelo_303_2024.__doc__ or ""
        assert "test_ruleset_schema_coverage" in doc, (
            "modelo_303_2024 docstring lost its reference to test_ruleset_schema_coverage; regenerate from the fixture."
        )

    def test_fixture_notes_include_suspect_slot_pointers(self) -> None:
        """The fixture note's mislabeled-slot theory names three
        _2-suffix CURRENCY slots as the suspected carriers of the missing
        casillas. Lock those pointers so a future regeneration can't erase
        the closure path without replacing the theory."""
        doc = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        notes = doc["source"].get("notes", "")
        expected_pointers = re.findall(r"DP\d+_CAS\d+_2", notes)
        assert expected_pointers, (
            "fixture source.notes should name the _2-suffix slot pointers "
            "documented in the closure path survives rewrites."
        )
        # At least one pointer per 303 segment that carries mislabeled slots.
        assert any("DP30303_CAS" in p for p in expected_pointers)
        assert any("DP30304_CAS" in p for p in expected_pointers)
