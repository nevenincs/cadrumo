"""Private interactive confirmation hook for live AEAT writes."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from aeat.filing import FilingValue
from aeat.submission._errors import AeatLiveConfirmationDeclinedError
from aeat.submission._protocols import FilingDraftLike, Portal


@dataclass(frozen=True, slots=True)
class LiveConfirmation:
    """Derived confirmation payload for one live AEAT write."""

    draft_checksum: str
    total_amount: str
    confirmation_phrase: str
    typed_phrase: str


def confirm_live_submission(
    draft: FilingDraftLike,
    *,
    portal: Portal,
    input_fn: Callable[[str], str] = input,
) -> LiveConfirmation:
    """Block on the exact confirmation phrase before a live write."""
    checksum = compute_draft_checksum(draft)
    total_amount = compute_total_amount(draft)
    confirmation_phrase = f"SUBMIT {draft.modelo} {draft.period} {draft.profile_tax_id} {total_amount} {checksum}"
    stream = sys.stderr
    stream.write("Live AEAT submission requested.\n")
    stream.write(f"  modelo: {draft.modelo}\n")
    stream.write(f"  period: {draft.period}\n")
    stream.write(f"  taxpayer NIF: {draft.profile_tax_id}\n")
    stream.write(f"  total amount: {total_amount}\n")
    stream.write(f"  submission URL: {portal.presentation_url}\n")
    stream.write(f"  draft checksum: {checksum}\n")
    stream.write("Type the exact confirmation phrase shown below to continue.\n")
    stream.write(f"  {confirmation_phrase}\n")
    stream.flush()
    typed_phrase = input_fn("> ")
    if typed_phrase != confirmation_phrase:
        raise AeatLiveConfirmationDeclinedError("live submission confirmation phrase mismatch; refusing live write")
    return LiveConfirmation(
        draft_checksum=checksum,
        total_amount=total_amount,
        confirmation_phrase=confirmation_phrase,
        typed_phrase=typed_phrase,
    )


def compute_draft_checksum(draft: FilingDraftLike) -> str:
    """Return a stable checksum of the filing draft payload."""
    encoded = json.dumps(_normalize_draft_payload(draft), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def compute_total_amount(draft: FilingDraftLike) -> str:
    """Return the operator-facing total amount string for the draft."""
    values = _extract_values_map(draft)
    if draft.modelo == "130":
        amount = values.get("07")
        return _format_amount(amount)
    return _format_amount(None)


def _normalize_draft_payload(draft: FilingDraftLike) -> dict[str, Any]:
    values = _extract_values_map(draft)
    return {
        "draft_id": draft.draft_id,
        "modelo": draft.modelo,
        "period": draft.period,
        "profile_tax_id": draft.profile_tax_id,
        "status": str(draft.status),
        "values": values,
        "findings": _normalize_findings(draft.findings),
    }


def _normalize_findings(findings: tuple[object, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for finding in findings:
        model_dump = getattr(finding, "model_dump", None)
        if callable(model_dump):
            payload = model_dump(mode="json")
            normalized.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            continue
        normalized.append(str(finding))
    return tuple(normalized)


def _extract_values_map(draft: FilingDraftLike) -> dict[str, str]:
    values = draft.values
    if isinstance(values, Mapping):
        sorted_items = sorted(values.items(), key=lambda item: str(item[0]))
        return {str(key): _stringify_scalar(value) for key, value in sorted_items}
    normalized: dict[str, str] = {}
    for item in values:
        casilla_id = _get_attr(item, "casilla_id", "id")
        value = _get_attr(item, "value")
        if casilla_id is None:
            continue
        normalized[str(casilla_id)] = _stringify_scalar(value)
    return dict(sorted(normalized.items()))


def _get_attr(item: object, *names: str) -> Any:
    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return None


def _format_amount(value: str | None) -> str:
    if value is None or value == "":
        return "unavailable"
    return value


def _stringify_scalar(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, FilingValue):
        return _stringify_scalar(value.value)
    if value is None:
        return ""
    return str(value)
