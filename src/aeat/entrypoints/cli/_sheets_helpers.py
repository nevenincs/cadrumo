"""Pure helpers for Google Sheets value input handling.

Hosts the side-effect-free helpers that translate operator inputs (JSON
strings, ``--raw`` flags) into the shapes expected by the Sheets
``values`` API. Anything that requires a live Sheets service belongs in
an outbound Google adapter.
"""

from __future__ import annotations

import json
from typing import Any


def parse_values_json(payload: str) -> list[list[Any]]:
    """Parse a JSON string into a 2-D list suitable for Sheets ``values``.

    The Sheets API expects values as ``list[list[Any]]`` even when
    writing a single cell. This helper accepts three input shapes and
    normalises them:

    - A 2-D array (returned as-is).
    - A 1-D array (wrapped into a single row).
    - A scalar (wrapped into a single 1x1 row).

    Args:
        payload: JSON string containing the values to write.

    Returns:
        Normalised 2-D list of values.

    Raises:
        ValueError: If the JSON cannot be parsed or has an unsupported
            shape (e.g. dict, deeply nested).
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in values payload: {exc}"
        raise ValueError(msg) from exc

    if isinstance(data, list):
        if not data:
            return [[]]
        if all(isinstance(item, list) for item in data):
            return [list(row) for row in data]  # type: ignore[arg-type]
        return [list(data)]
    if isinstance(data, dict):
        msg = "Sheets values payload must be a list or scalar, not an object"
        raise ValueError(msg)
    return [[data]]


def coerce_value_input_option(raw: bool) -> str:
    """Map a ``--raw`` boolean flag to a Sheets ``valueInputOption``.

    Args:
        raw: True to preserve user input verbatim; False to let Google
            parse strings as numbers, dates, formulas, etc.

    Returns:
        Either ``"RAW"`` or ``"USER_ENTERED"``.
    """
    return "RAW" if raw else "USER_ENTERED"
