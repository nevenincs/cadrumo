"""Guard the predecessor TUI plan's Ledger ownership dispositions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PLAN_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3] / ".vault" / "plan" / "2026-08-11-tui-architecture-plan.md"
)
_ROW_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^- \[(?P<checked>[ x])\] `(?P<display_path>W\d+\.P\d+\.S\d+)` - "
    r"(?P<action>.*); `(?P<scope>.*)`\.$",
    re.MULTILINE,
)
_DISPOSITION_PATTERN: Final[re.Pattern[str]] = re.compile(r"CLITUI_LEDGER_DISPOSITION: (?P<token>[A-Za-z0-9_]+)")
_RETAINED: Final[frozenset[str]] = frozenset(
    {
        "S169",
        "S207",
        "S259",
        "S266",
        "S267",
        "S268",
        "S269",
        "S286",
        "S291",
        "S317",
        "S321",
        "S323",
        "S344",
        "S349",
        "S365",
        "S366",
        "S375",
        "S381",
        "S384",
        "S385",
        "S391",
        "S398",
        "S405",
        "S409",
        "S410",
        "S421",
        "S426",
    }
)
_RETIRED_MARKERS: Final[frozenset[str]] = frozenset({"S73"})
_HELD: Final[frozenset[str]] = frozenset({"S390", "S395", "S396", "S411", "S424"})
_MIXED_HELD: Final[frozenset[str]] = _HELD - {"S411"}
_KNOWN_OVERLAP: Final[frozenset[str]] = _RETAINED | _RETIRED_MARKERS | _HELD
_REVIEWED_INCLUDE: Final[frozenset[str]] = _KNOWN_OVERLAP
_EXPECTED_TOKEN: Final[dict[str, str]] = {
    **dict.fromkeys(_RETAINED, "RETAINED_PREDECESSOR_EVIDENCE"),
    **dict.fromkeys(_RETIRED_MARKERS, "RETAINED_RETIRED_PREMISE_MARKER"),
    **dict.fromkeys(_HELD, "DISPLACED_AND_HELD_UNTIL_G3"),
}
_LEDGER_PATH_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[\s`'\",])(src/)?cadrumo/(?:entrypoints/tui|application|domain)/ledger"
    r"(?:/|[_.]|(?=[\s`'\",;]|$))|/ledger/",
    re.IGNORECASE,
)
_LEDGER_IDENTIFIER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])ledger_[A-Za-z0-9_]+|[A-Za-z0-9_]+_ledger(?:_[A-Za-z0-9_]+)*|"
    r"(?<![A-Za-z0-9_])ledger\.[a-z0-9_.-]+|[a-z0-9_.-]+\.ledger(?:\.[a-z0-9_.-]+)?",
    re.IGNORECASE,
)
_LEDGER_PRODUCT_SYMBOL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\bLedger(?:[A-Z][A-Za-z0-9]*)?\b|\b[A-Za-z0-9]+Ledger(?:[A-Z][A-Za-z0-9]*)?\b"
)
_LEDGER_DOMAIN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\bledger\s+(?:action|binding|capabilit|classification|entr|evidence|import|issue|module|navigation|parity|"
    r"preflight|reconciliation|review|route|selection|snapshot|summary|surface|transaction|tui|work|workspace)"
    r"[A-Za-z-]*\b|"
    r"\b(?:classification|entr|evidence|import|reconciliation|review|transaction|tui|workspace)[A-Za-z-]*\s+ledger\b",
    re.IGNORECASE,
)
_REVIEWED_PLURAL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:accounting|financial|tax|transaction)\s+ledgers\b|\bledgers\s+(?:classification|evidence|import|review)\b",
    re.IGNORECASE,
)
_REVIEWED_EXCLUDE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (re.compile(r"\baudit\s+ledgers?\b", re.IGNORECASE),)


@dataclass(frozen=True, slots=True)
class _PlanRow:
    """One parsed Vaultspec Step row."""

    display_path: str
    checked: bool
    action: str
    scope: str

    @property
    def step_id(self) -> str:
        """Return the stable Step identifier."""
        return self.display_path.rsplit(".", maxsplit=1)[-1]


def _parse_rows(plan_text: str) -> tuple[_PlanRow, ...]:
    parsed = tuple(
        _PlanRow(
            display_path=match.group("display_path"),
            checked=match.group("checked") == "x",
            action=match.group("action"),
            scope=match.group("scope"),
        )
        for match in _ROW_PATTERN.finditer(plan_text)
    )
    row_lines = tuple(line for line in plan_text.splitlines() if line.startswith("- ["))
    if len(parsed) != len(row_lines):
        raise ValueError("unsupported predecessor plan Step-row structure")
    step_ids = tuple(row.step_id for row in parsed)
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("predecessor plan Step identities are not unique")
    return parsed


def _is_ledger_overlap(row: _PlanRow) -> bool:
    base_action = row.action.split(" CLITUI_LEDGER_DISPOSITION:", maxsplit=1)[0]
    candidate = f"{base_action} {row.scope}".replace("\\", "/")
    for excluded in _REVIEWED_EXCLUDE_PATTERNS:
        candidate = excluded.sub("", candidate)
    return row.step_id in _REVIEWED_INCLUDE or any(
        pattern.search(candidate)
        for pattern in (
            _LEDGER_PATH_PATTERN,
            _LEDGER_IDENTIFIER_PATTERN,
            _LEDGER_PRODUCT_SYMBOL_PATTERN,
            _LEDGER_DOMAIN_PATTERN,
            _REVIEWED_PLURAL_PATTERN,
        )
    )


def _validate_plan_ownership(plan_text: str) -> None:
    rows = _parse_rows(plan_text)
    by_id = {row.step_id: row for row in rows}
    annotated: dict[str, str] = {}

    for row in rows:
        matches = tuple(_DISPOSITION_PATTERN.finditer(row.action))
        if len(matches) > 1:
            raise ValueError(f"duplicate Ledger disposition on {row.step_id}")
        if not matches:
            continue
        disposition = matches[0].group("token")
        if disposition not in set(_EXPECTED_TOKEN.values()):
            raise ValueError(f"unknown Ledger disposition on {row.step_id}")
        if row.step_id not in _KNOWN_OVERLAP:
            raise ValueError(f"Ledger disposition outside known overlap on {row.step_id}")
        annotated[row.step_id] = disposition

    overlaps = {row.step_id for row in rows if _is_ledger_overlap(row)}
    unannotated = overlaps - annotated.keys()
    if unannotated:
        raise ValueError(f"unannotated Ledger overlap: {sorted(unannotated)}")
    undiscovered = annotated.keys() - overlaps
    if undiscovered:
        raise ValueError(f"reviewed Ledger overlap is no longer discoverable: {sorted(undiscovered)}")
    if annotated.keys() != _KNOWN_OVERLAP:
        raise ValueError("Ledger overlap disposition identities drifted")

    for step_id, expected in _EXPECTED_TOKEN.items():
        if annotated[step_id] != expected:
            raise ValueError(f"Ledger disposition reclassified on {step_id}")
    if any(not by_id[step_id].checked for step_id in _RETAINED):
        raise ValueError("retained Ledger predecessor evidence must remain checked")
    if any(by_id[step_id].checked for step_id in _RETIRED_MARKERS | _HELD):
        raise ValueError("retired-marker and held Ledger rows must remain open")
    if len(rows) != 429 or sum(row.checked for row in rows) != 413:
        raise ValueError("predecessor plan completion drifted from 413/429")

    for step_id in _MIXED_HELD:
        if "non-Ledger scope remains owned here" not in by_id[step_id].action:
            raise ValueError(f"mixed Ledger scope retention missing on {step_id}")
    s411 = by_id["S411"].action
    if "implementation is owned by clitui-ledger W05.P21.S136" not in s411:
        raise ValueError("S411 Ledger navigation implementation target drifted")
    if "held-row disposition checkpoint remains W05.P19.S128" not in s411:
        raise ValueError("S411 held-row disposition checkpoint drifted")


def _plan_text() -> str:
    return _PLAN_PATH.read_text(encoding="utf-8")


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError(f"mutation anchor must occur once: {old!r}")
    return source.replace(old, new, 1)


def _replace_once_in_step(source: str, display_path: str, old: str, new: str) -> str:
    lines = source.splitlines(keepends=True)
    matching_indexes = [index for index, line in enumerate(lines) if f"`{display_path}`" in line]
    if len(matching_indexes) != 1:
        raise AssertionError(f"Step mutation anchor must occur once: {display_path!r}")
    index = matching_indexes[0]
    if lines[index].count(old) != 1:
        raise AssertionError(f"mutation anchor must occur once in {display_path}: {old!r}")
    lines[index] = lines[index].replace(old, new, 1)
    return "".join(lines)


def test_live_predecessor_plan_has_the_exact_ledger_ownership_dispositions() -> None:
    _validate_plan_ownership(_plan_text())


@pytest.mark.parametrize(
    "wording",
    [
        pytest.param("Retire the ledger_binding_resolution facade", id="ledger-prefix-identifier"),
        pytest.param("Retire the irnr_ledger_bindings facade", id="ledger-suffix-identifier"),
        pytest.param("Inspect src/cadrumo/application/ledger/new.py", id="ledger-path-segment"),
        pytest.param("Render LedgerWorkspaceSummary in AEAT Sync", id="ledger-product-symbol"),
        pytest.param("Export Ledger data from AEAT Sync", id="standalone-ledger-export"),
        pytest.param("Append Ledger notes in AEAT Sync", id="standalone-ledger-notes"),
        pytest.param("Edit Ledger attachments in AEAT Sync", id="standalone-ledger-attachments"),
        pytest.param("Edit Ledger fields in AEAT Sync", id="standalone-ledger-fields"),
        pytest.param("Render accounting ledgers in AEAT Sync", id="reviewed-plural-context"),
    ],
)
def test_same_row_unambiguous_ledger_signals_require_adjudication(wording: str) -> None:
    plan_text = _replace_once_in_step(
        _plan_text(),
        "W08.P30.S408",
        "Give AEAT Sync its local row readers",
        wording,
    )

    with pytest.raises(ValueError, match="unannotated Ledger overlap"):
        _validate_plan_ownership(plan_text)


@pytest.mark.parametrize("wording", ["audit ledger", "audit Ledger"])
def test_same_row_generic_audit_ledger_is_explicitly_excluded(wording: str) -> None:
    plan_text = _replace_once_in_step(
        _plan_text(),
        "W08.P30.S408",
        "Give AEAT Sync its local row readers",
        f"Record the {wording} for AEAT Sync",
    )

    _validate_plan_ownership(plan_text)


def test_same_row_lowercase_generic_ledger_is_not_a_product_signal() -> None:
    plan_text = _replace_once_in_step(
        _plan_text(),
        "W08.P30.S408",
        "Give AEAT Sync its local row readers",
        "Export ledger data from AEAT Sync",
    )

    _validate_plan_ownership(plan_text)


def test_current_overlap_row_remains_discoverable_after_nonsemantic_rewording() -> None:
    plan_text = _replace_once_in_step(
        _plan_text(),
        "W03.P20.S207",
        "Privatize the ledger_binding_resolution implementation",
        "Retire the ledger_binding_resolution implementation",
    )

    _validate_plan_ownership(plan_text)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        pytest.param("missing", "unannotated Ledger overlap", id="missing"),
        pytest.param("duplicate", "duplicate Ledger disposition", id="duplicate"),
        pytest.param("unknown", "unknown Ledger disposition", id="unknown"),
        pytest.param("reclassified", "Ledger disposition reclassified", id="reclassified"),
        pytest.param("wrong-checkbox", "retained Ledger predecessor evidence", id="wrong-checkbox"),
        pytest.param("held-checkbox", "retired-marker and held Ledger rows", id="held-checkbox"),
        pytest.param("new-overlap", "unannotated Ledger overlap", id="new-unannotated-overlap"),
        pytest.param("outside-overlap", "Ledger disposition outside known overlap", id="outside-known-overlap"),
        pytest.param("lost-mixed-scope", "mixed Ledger scope retention", id="lost-mixed-scope"),
        pytest.param("completion", "predecessor plan completion drifted", id="completion"),
        pytest.param("wrong-s411-target", "S411 Ledger navigation implementation target", id="wrong-s411-target"),
    ],
)
def test_ledger_ownership_detector_rejects_each_plan_mutation(mutation: str, expected: str) -> None:
    plan_text = _plan_text()
    if mutation == "missing":
        plan_text = _replace_once_in_step(
            plan_text,
            "W03.P20.S169",
            " CLITUI_LEDGER_DISPOSITION: RETAINED_PREDECESSOR_EVIDENCE;",
            "",
        )
    elif mutation == "duplicate":
        disposition_marker = "CLITUI_LEDGER_DISPOSITION: RETAINED_PREDECESSOR_EVIDENCE"
        plan_text = _replace_once_in_step(
            plan_text,
            "W03.P20.S169",
            disposition_marker,
            f"{disposition_marker}; {disposition_marker}",
        )
    elif mutation == "unknown":
        plan_text = _replace_once_in_step(
            plan_text,
            "W03.P20.S169",
            "CLITUI_LEDGER_DISPOSITION: RETAINED_PREDECESSOR_EVIDENCE",
            "CLITUI_LEDGER_DISPOSITION: UNKNOWN",
        )
    elif mutation == "reclassified":
        plan_text = _replace_once_in_step(
            plan_text,
            "W03.P20.S169",
            "CLITUI_LEDGER_DISPOSITION: RETAINED_PREDECESSOR_EVIDENCE",
            "CLITUI_LEDGER_DISPOSITION: DISPLACED_AND_HELD_UNTIL_G3",
        )
    elif mutation == "wrong-checkbox":
        plan_text = _replace_once(plan_text, "- [x] `W03.P20.S169`", "- [ ] `W03.P20.S169`")
    elif mutation == "held-checkbox":
        plan_text = _replace_once(plan_text, "- [ ] `W08.P30.S411`", "- [x] `W08.P30.S411`")
    elif mutation == "new-overlap":
        plan_text = _replace_once(
            plan_text,
            "\n## Parallelization\n",
            (
                "\n- [ ] `W08.P30.S999` - Add a new unresolved Ledger TUI path; "
                "`src/cadrumo/entrypoints/tui/ledger/new.py`.\n\n## Parallelization\n"
            ),
        )
    elif mutation == "outside-overlap":
        plan_text = _replace_once_in_step(
            plan_text,
            "W08.P30.S408",
            "Give AEAT Sync its local row readers",
            "Give AEAT Sync its local row readers CLITUI_LEDGER_DISPOSITION: RETAINED_PREDECESSOR_EVIDENCE",
        )
    elif mutation == "lost-mixed-scope":
        plan_text = _replace_once_in_step(
            plan_text,
            "W08.P28.S395",
            "non-Ledger scope remains owned here",
            "remaining scope is unspecified",
        )
    elif mutation == "completion":
        plan_text = _replace_once(plan_text, "- [x] `W08.P30.S408`", "- [ ] `W08.P30.S408`")
    else:
        plan_text = _replace_once(plan_text, "W05.P21.S136", "W05.P19.S128")

    with pytest.raises(ValueError, match=expected):
        _validate_plan_ownership(plan_text)
