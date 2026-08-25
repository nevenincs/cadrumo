"""Gate the committed tree against approving-provision mis-attribution.

``legal_attribution_screen`` was written as a screen and not a gate for a stated
reason: four filing-grade citations were known-wrong when it was authored, so a
gate would have landed red on every peer for a defect none of them created. The
screen names the condition for promotion -- an empty worklist -- and that
condition is now met, so the ratchet belongs here.

WHAT THIS GATES, and what it deliberately does not. The screen reads the
citations a modelo makes at MODELO and REVISION level, and the rule it applies is
narrow: an entry whose ``required_text`` carries an approval phrase AND names a
form is about that form, so another form citing it is claiming a provision that
is not about it.

A deeper walk -- every ``legal_refs`` on every casilla, construct, formula,
binding, relation and export layout, collected recursively -- was implemented and
measured before being rejected as the gate's surface. It returns five findings and
all five are legitimate: modelo 100 cites the ordenes approving modelos 190, 193,
130, 131 and 184 from its own dependency classifications, relations and bindings,
where naming the dependent form's approving orden is exactly correct. Gating the
deep surface would therefore red the tree on correct citations, and suppressing
those five would mean an exclusion list keyed on cross-modelo dependency, which
is judgement this rule does not carry.

The measurement still answers the question it was run to answer: below revision
level there is no approval mis-attribution to find, only dependency citations. So
the narrow surface is not a convenient scope, it is the whole of the defect.

The screen keeps its own exit-0 reporting contract for interactive use; the
enforcement lives here.
"""

from __future__ import annotations

import pytest

from ..._paths import REPO_ROOT
from ..legal_attribution_screen import _modelo_refs_from_registry, approved_modelo_numbers, find_mismatches
from ..legal_catalogue import load_legal_entries, required_text_by_entry

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def test_no_modelo_cites_a_provision_that_approves_another_form() -> None:
    """Every approving provision a modelo cites must be about that modelo."""
    entries = required_text_by_entry(load_legal_entries(REPO_ROOT))
    assert entries, "read zero legal entries; a clean result would be meaningless"

    approving = {key: value for key, value in entries.items() if approved_modelo_numbers(value)}
    assert approving, (
        "no catalogue entry carries an approval phrase, so this gate would pass "
        "vacuously; the approval vocabulary or the catalogue shape has changed"
    )

    mismatches = find_mismatches(_modelo_refs_from_registry(), entries)

    assert not mismatches, (
        "modelos citing a provision whose own approving text names a different "
        "form -- the phrase check passes because the text is genuinely present, "
        "so only attribution catches these:\n"
        + "\n".join(f"  {mismatch.render()}" for mismatch in mismatches)
        + "\nLocate the orden that approves the citing modelo and re-point the ref."
    )
