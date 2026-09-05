"""Guard the generator-owned Ledger campaign index contract."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from vaultspec_core.vaultcore.index import generate_feature_index_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_INDEX_PATH: Final[Path] = _ROOT / ".vault" / "index" / "clitui-ledger.index.md"
_S10_RECORD_PATH: Final[Path] = (
    _ROOT / ".vault" / "exec" / "2026-09-04-clitui-ledger" / "2026-09-04-clitui-ledger-W01-P03-S10.md"
)
_S10_NAME: Final[str] = "2026-09-04-clitui-ledger-W01-P03-S10"
_OWNER_FACT: Final[str] = "clitui-ledger sole active Ledger parity owner"
_G0_STATE: Final[str] = "G0 OPEN"
_GATE_CHAIN: Final[str] = "G0→G1→G2→G3→G4"
_TUI_HOLD: Final[str] = "Ledger TUI held until G3 closes"
_CANONICAL_LINKS: Final[tuple[str, ...]] = (
    "[[2026-09-04-clitui-ledger-adr]]",
    "[[2026-09-04-clitui-ledger-plan]]",
    "[[2026-09-04-clitui-ledger-reference]]",
    "[[2026-09-04-clitui-ledger-W01-P03-S09]]",
)
_H1_PATTERN: Final[re.Pattern[str]] = re.compile(r"^# (?P<title>.+)$", re.MULTILINE)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _record_title(record_text: str) -> str:
    match = _H1_PATTERN.search(record_text)
    assert match is not None, "S10 execution record has no level-one title"
    title = match.group("title")
    assert isinstance(title, str)
    return title


def _assert_generated_body_shape(index_text: str) -> None:
    """Reject governance prose that could only have been hand-added to the index."""
    sections = index_text.split("---\n", maxsplit=2)
    if len(sections) != 3:
        raise AssertionError("feature index does not have canonical frontmatter")
    body_lines = sections[2].splitlines()
    try:
        documents_index = body_lines.index("## Documents")
    except ValueError as exc:
        raise AssertionError("feature index has no generated Documents section") from exc

    if any(line.startswith("## ") and line != "## Documents" for line in body_lines):
        raise AssertionError("feature index contains a manual governance section")
    for line in body_lines[documents_index + 1 :]:
        if line and not (line.startswith("### ") or line.startswith("- `")):
            raise AssertionError("feature index contains manual-only body text")


def _validate_index(index_text: str, *, record_title: str) -> None:
    for fact in (_OWNER_FACT, _G0_STATE, _GATE_CHAIN, _TUI_HOLD):
        if fact not in index_text:
            raise AssertionError(f"generated index is missing governance fact: {fact}")
    for link in _CANONICAL_LINKS:
        if link not in index_text:
            raise AssertionError(f"generated index is missing canonical link: {link}")
    expected_entry = f"- `{_S10_NAME}` - {record_title}"
    if expected_entry not in index_text:
        raise AssertionError("generated index does not carry the canonical S10 title")
    _assert_generated_body_shape(index_text)


def test_live_index_is_generator_owned_and_publishes_campaign_state() -> None:
    record_title = _record_title(_read(_S10_RECORD_PATH))
    index_text = _read(_INDEX_PATH)

    result = generate_feature_index_result(_ROOT, "clitui-ledger", dry_run=True)
    assert result.changed is False
    _validate_index(index_text, record_title=record_title)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        pytest.param(
            lambda text: text.replace(_OWNER_FACT, "other-plan sole active Ledger parity owner", 1),
            "owner",
            id="wrong-owner",
        ),
        pytest.param(
            lambda text: text.replace(_G0_STATE, "G1 OPEN", 1),
            "G0 OPEN",
            id="wrong-current-gate",
        ),
        pytest.param(
            lambda text: text.replace(_GATE_CHAIN, "G0→G1→G3→G2→G4", 1),
            _GATE_CHAIN,
            id="reordered-gate-chain",
        ),
        pytest.param(
            lambda text: text.replace(_GATE_CHAIN, "G0→G1→G2→G3", 1),
            _GATE_CHAIN,
            id="missing-gate",
        ),
        pytest.param(
            lambda text: text.replace(_TUI_HOLD, "Ledger TUI held until G2 closes", 1),
            _TUI_HOLD,
            id="wrong-tui-hold-gate",
        ),
        pytest.param(
            lambda text: text.replace(_CANONICAL_LINKS[2], "", 1),
            _CANONICAL_LINKS[2],
            id="missing-reference-link",
        ),
        pytest.param(
            lambda text: text.replace(
                "## Documents\n",
                "## Governance\n\nmanual state\n\n## Documents\n",
                1,
            ),
            "manual governance section",
            id="manual-index-body",
        ),
    ],
)
def test_index_governance_detector_rejects_mutations(mutation: Callable[[str], str], expected: str) -> None:
    record_title = _record_title(_read(_S10_RECORD_PATH))
    mutated = mutation(_read(_INDEX_PATH))

    with pytest.raises(AssertionError, match=re.escape(expected)):
        _validate_index(mutated, record_title=record_title)
