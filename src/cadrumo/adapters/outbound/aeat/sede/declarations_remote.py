"""Remote-read guard and CSV-extraction helpers for the declarations fetch adapter.

``extract_csv_from_url`` is shared by ``_declarations.py``, ``declarations_fetch.py``
and ``_parse.py``. External consumers import it from this defining module.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from .....core.aeat_csv import is_aeat_csv
from .....core.identity.aeat_csv import AeatCsv
from .errors import SedeParseError


def extract_csv_from_url(url: str) -> AeatCsv:
    """Extract and shape-validate the ``CSV`` query parameter from a cotejo URL.

    The return names :data:`~cadrumo.core.identity.aeat_csv.AeatCsv` to document an
    invariant this function already enforces rather than to add one: the
    :func:`~cadrumo.core.aeat_csv.is_aeat_csv` guard below is the same 8-32 uppercase
    alphanumeric shape the alias constrains toward, so every value returned
    here is already in the alias's canonical form. A plain function's
    annotation runs no validator; the guard is what refuses, and the alias is
    what names the contract the guard implements.
    """
    parsed = urlsplit(url)
    qs = parse_qs(parsed.query)
    csv_values = qs.get("CSV", [])
    if not csv_values:
        raise SedeParseError(f"cotejo URL missing CSV query: {url!r}")
    if len(csv_values) > 1:
        raise SedeParseError(
            f"cotejo URL has {len(csv_values)} CSV values; AEAT only emits one: {url!r}",
        )
    csv = csv_values[0]
    if not is_aeat_csv(csv):
        raise SedeParseError(
            f"cotejo URL CSV {csv!r} does not match AEAT shape (expected 8-32 uppercase alphanumeric chars)",
        )
    return csv


__all__ = [
    "extract_csv_from_url",
]
