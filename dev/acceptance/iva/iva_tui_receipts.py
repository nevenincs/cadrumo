"""Installed IVA child receipt serialization and submitted-field completeness guards."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from .iva_tui_contracts import _CLASSIFICATION_FIELDS, IvaInstalledTuiError, _CaptureChildReceipt, _ReopenChildReceipt
from .iva_tui_projection import _object


def _require_submitted_classification_fields(capture: Mapping[str, object]) -> None:
    """Require submitted classification fields."""
    submitted_fields = capture.get("classification_fields_submitted")
    if (
        not isinstance(submitted_fields, list)
        or len(submitted_fields) != len(_CLASSIFICATION_FIELDS)
        or any(not isinstance(field, str) for field in submitted_fields)
        or tuple(submitted_fields) != _CLASSIFICATION_FIELDS
    ):
        raise IvaInstalledTuiError("capture receipt did not attest all combined IVA classification fields")


def _write_success_receipt(path: Path, receipt: _CaptureChildReceipt | _ReopenChildReceipt) -> None:
    """Persist a receipt whose schema contains no source facts or credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _child_document(path: Path, *, mode: str) -> dict[str, object]:
    """Load a child receipt only after the shared runner has verified its presence."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IvaInstalledTuiError("installed TUI child receipt cannot be decoded") from exc
    result = _object(document, label="installed TUI child receipt")
    if result.get("status") != "proven" or result.get("mode") != mode:
        raise IvaInstalledTuiError("installed TUI child did not prove its requested bounded mode")
    return result


def _capture_transaction_ids(document: Mapping[str, object]) -> tuple[str, str]:
    """Take the two opaque transaction handles from a sanitized capture receipt."""
    values = document.get("transaction_ids")
    if not isinstance(values, list) or len(values) != 2:
        raise IvaInstalledTuiError("capture receipt did not retain two transaction handles")
    first, second = values
    if not isinstance(first, str) or not first or not isinstance(second, str) or not second:
        raise IvaInstalledTuiError("capture receipt did not retain two transaction handles")
    if first == second:
        raise IvaInstalledTuiError("capture receipt retained duplicate transaction handles")
    return first, second
