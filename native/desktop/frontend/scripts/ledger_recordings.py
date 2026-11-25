"""Record what the Ledger's pure reads answer, for the browser fixtures that answer for them.

The invoice figures preview, the payment-matching rule, the duplicate rule, the rule trial and the
split check each work an answer out of the facts they are handed and read no stored record. The
browser fixtures hold none of those rules: they look an answer up in a recording of what the rule
said. This asks each rule every question in ``ledger-recording-questions`` and writes the questions
beside the answers the rule gave, so the recordings hold no answer written by hand. A new case is a
new question; run after changing a question or a rule:

    uv run --no-sync python native/desktop/frontend/scripts/ledger_recordings.py [--check]

``--check`` fails when a recording differs in meaning from what the rules answer now.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

SCRIPTS = Path(__file__).resolve().parent
QUESTIONS = SCRIPTS.parents[3] / "dev" / "fixtures" / "ledger-recording-questions"

_WIDTH = 80
_INDENT = "  "

_PREVIEW_NOTE = (
    "What the invoice figures preview answers for each synthetic draft, keyed by name, as `aeat app ledger "
    "invoice preview` serves it. A draft names no line key: the lines are keyed by their place, `line-1` "
    "first. Written by scripts/ledger_recordings.py."
)


def _inline(value: Any) -> str | None:
    """``value`` on one line as Prettier prints a JSON value that fits, or ``None`` where it breaks."""
    if isinstance(value, dict):
        return None if value else "{}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if len(value) > 1 and all(isinstance(item, list) and len(item) > 1 for item in value):
            return None
        parts: list[str] = []
        for item in value:
            part = _inline(item)
            if part is None:
                return None
            parts.append(part)
        return "[" + ", ".join(parts) + "]"
    return json.dumps(value, ensure_ascii=False)


def _render(value: Any, depth: int, room: int) -> str:
    """``value`` laid out as Prettier lays out JSON, ``room`` columns being left on its first line."""
    pad = _INDENT * depth
    inner = _INDENT * (depth + 1)
    flat = _inline(value)
    if flat is not None and len(flat) <= room:
        return flat
    if isinstance(value, dict):
        last = len(value) - 1
        lines = []
        for place, (key, item) in enumerate(value.items()):
            head = f"{json.dumps(key, ensure_ascii=False)}: "
            left = _WIDTH - len(inner) - len(head) - (0 if place == last else 1)
            lines.append(inner + head + _render(item, depth + 1, left))
        return "{\n" + ",\n".join(lines) + "\n" + pad + "}"
    if isinstance(value, list):
        last = len(value) - 1
        rows = [
            inner + _render(item, depth + 1, _WIDTH - len(inner) - (0 if place == last else 1))
            for place, item in enumerate(value)
        ]
        return "[\n" + ",\n".join(rows) + "\n" + pad + "]"
    return json.dumps(value, ensure_ascii=False)


def dump_json(value: Any) -> str:
    """``value`` as the JSON text Prettier leaves unchanged, so formatting the file changes nothing."""
    return _render(value, 0, _WIDTH) + "\n"


def _questions(name: str) -> Any:
    return json.loads((QUESTIONS / f"{name}.json").read_text(encoding="utf-8"))


def _invoice_preview(operation: PinnedAuthorityOperation) -> dict[str, Any]:
    from cadrumo.application.invoices.tests.figures_preview_support import recorded_preview_result

    drafts: Mapping[str, Mapping[str, Any]] = _questions("ledgerInvoicePreview")
    return {
        "note": _PREVIEW_NOTE,
        "recordings": {
            name: {"request": request, "result": recorded_preview_result(request, operation)}
            for name, request in drafts.items()
        },
    }


def _invoice_match(_: PinnedAuthorityOperation) -> dict[str, Any]:
    from cadrumo.domain.invoices.tests.payment_matching_support import recorded_scenario

    return {"scenarios": [recorded_scenario(scenario) for scenario in _questions("ledgerInvoiceMatch")["scenarios"]]}


def _invoice_duplicate(_: PinnedAuthorityOperation) -> dict[str, Any]:
    from cadrumo.domain.invoices.tests.duplicate_recording_support import recorded_duplicate_answer

    asked = _questions("ledgerInvoiceDuplicate")
    return {
        "invoices": asked["invoices"],
        "answers": [
            {**entry, "answer": recorded_duplicate_answer(asked["invoices"], entry["question"])}
            for entry in asked["answers"]
        ],
    }


def _rule_trial(_: PinnedAuthorityOperation) -> dict[str, Any]:
    from cadrumo.application.ledger.tests.rule_trial_support import recorded_rule_trial_answer

    asked = _questions("ledgerRuleTrial")
    return {
        "descriptions": asked["descriptions"],
        "answers": [recorded_rule_trial_answer(asked["descriptions"], pattern) for pattern in asked["patterns"]],
    }


def _split_check(_: PinnedAuthorityOperation) -> dict[str, Any]:
    from cadrumo.application.ledger.tests.split_check_support import recorded_split_answer

    return {
        "answers": [
            {**entry, "answer": recorded_split_answer(entry["parent_amount"], entry["parts"])}
            for entry in _questions("ledgerSplitCheck")["answers"]
        ]
    }


#: Each recording by fixture name, with the function that asks the rules its questions.
RECORDINGS: dict[str, Callable[[PinnedAuthorityOperation], dict[str, Any]]] = {
    "ledgerInvoicePreview": _invoice_preview,
    "ledgerInvoiceMatch": _invoice_match,
    "ledgerInvoiceDuplicate": _invoice_duplicate,
    "ledgerRuleTrial": _rule_trial,
    "ledgerSplitCheck": _split_check,
}


def render_fixtures() -> dict[str, str]:
    """Every recording's text by fixture name, each answer worked out by the rule it records."""
    with bundled_indexed_authority().operation() as operation:
        return {name: dump_json(record(operation)) for name, record in RECORDINGS.items()}


def main() -> None:
    """Write, verify or redirect the browser fixtures."""
    arguments = producer_arguments(__doc__)
    rendered = render_fixtures()
    emit(
        {family_directory("ledger-recordings") / f"{name}.json": text for name, text in rendered.items()},
        arguments,
        remedy="uv run --no-sync python native/desktop/frontend/scripts/ledger_recordings.py",
    )


if __name__ == "__main__":
    main()
