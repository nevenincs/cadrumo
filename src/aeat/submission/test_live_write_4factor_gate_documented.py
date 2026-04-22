"""Lock the 4-factor live-submit gate documentation (wave 134).

Charter #117 and ``.vault/adr/2026-04-18-live-submit-cli-excision-adr.md``
describe the 4-factor gate Kent's live submission (milestone 1.0.0)
must pass through:

1. ``AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1`` env var (opt-in flag)
2. ``AEAT_LIVE_SUBMIT_ENABLED=1`` env var (per-run enablement)
3. ``--i-understand-this-is-real`` CLI flag (conscious-action signal)
4. Per-submission interactive prompt (final human confirmation)

Live submit is excised from the default CLI today (wave 80c +
wave 133 pin that); the 4-factor gate is the architecture for its
1.0.0 reintroduction. Wave 134 locks that the ADR + project
mandates continue to document all 4 factors so no one can remove
a layer by accident when the capability is reintroduced.

This is documentation-level Stream A coverage (citation accuracy
extended to safety architecture).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ADR_PATH = _REPO_ROOT / ".vault" / "adr" / "2026-04-18-live-submit-cli-excision-adr.md"
_ROADMAP_PATH = _REPO_ROOT / "ROADMAP.md"


_REQUIRED_FACTORS: list[str] = [
    "AEAT_ALLOW_LIVE_SUBMIT_OPT_IN",
    "AEAT_LIVE_SUBMIT_ENABLED",
    "--i-understand-this-is-real",
]


class TestLiveSubmit4FactorGateDocumented:
    def test_adr_enumerates_every_factor(self) -> None:
        """The live-submit-cli-excision ADR must name every gate layer so
        a contributor reintroducing live submit in 1.0.0 lands on the full
        safety architecture, not a partial subset."""
        text = _ADR_PATH.read_text(encoding="utf-8")
        for factor in _REQUIRED_FACTORS:
            assert factor in text, (
                f"ADR at {_ADR_PATH.relative_to(_REPO_ROOT)} must name gate factor "
                f"{factor!r}. The 4-factor chain is charter #117's canonical "
                f"safety architecture; removing a factor from the ADR fails loud."
            )

    def test_adr_references_per_submission_prompt(self) -> None:
        """Factor 4 (per-submission prompt) must appear as prose even if it
        can't be spelled with a single literal token."""
        text = _ADR_PATH.read_text(encoding="utf-8").lower()
        assert "per-submission prompt" in text or "per-submission" in text, (
            "ADR must describe the 4th factor (per-submission interactive prompt) "
            "— without it the gate is a 3-factor chain and the safety architecture "
            "is incomplete."
        )

    def test_roadmap_documents_live_submit_defer_to_1_0(self) -> None:
        """The public roadmap must state live submit is deferred to 1.0.0
        so external observers know the capability isn't quietly shipped
        earlier."""
        text = _ROADMAP_PATH.read_text(encoding="utf-8")
        assert "AEAT_ALLOW_LIVE_SUBMIT_OPT_IN" in text, (
            "ROADMAP.md must reference AEAT_ALLOW_LIVE_SUBMIT_OPT_IN so readers "
            "can trace the env-gate chain from charter #117 to the public roadmap."
        )
