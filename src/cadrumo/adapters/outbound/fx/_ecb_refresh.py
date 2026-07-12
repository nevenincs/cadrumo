"""Refresh the bundled ECB euro reference-rate snapshot.

Maintenance utility (not on the runtime path) that re-acquires the European
Central Bank ``eurofxref-hist.xml`` full history and writes it to the bundled
data file the runtime reads offline. Fetch and write are separated so the
write/validate path is testable without a network round-trip.

See the ``ledger-fx-conversion`` ADR: the runtime stays offline against a
versioned bundled snapshot; this utility updates that snapshot on release.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ....core.external_constants import UTF_8_ENCODING
from ._ecb_provider import _BUNDLED_RATES, _parse_eurofxref

ECB_HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"


def refresh_bundled_ecb_rates(
    *,
    source_xml: str | None = None,
    url: str = ECB_HIST_URL,
    dest: Path | None = None,
) -> int:
    """Validate and write a fresh ECB eurofxref snapshot to the bundled file.

    When ``source_xml`` is given it is used directly (testable path); otherwise
    the history is fetched from ``url`` (must be https). The XML is parsed to
    confirm it is a usable eurofxref document before it overwrites the bundle.
    Returns the number of dated rate sets written.
    """
    xml = source_xml if source_xml is not None else _fetch(url)
    target = dest or _BUNDLED_RATES
    # Validate by parsing before persisting; a malformed download must not
    # clobber a working bundle.
    tmp = target.with_suffix(".xml.tmp")
    tmp.write_text(xml, encoding=UTF_8_ENCODING)
    parsed = _parse_eurofxref(tmp)
    if not parsed:
        tmp.unlink(missing_ok=True)
        raise ValueError("refreshed ECB document contained no dated rate sets")
    target.write_text(xml, encoding=UTF_8_ENCODING)
    tmp.unlink(missing_ok=True)
    return len(parsed)


def _fetch(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.ecb.europa.eu"
        or parsed.path != "/stats/eurofxref/eurofxref-hist.xml"
    ):
        raise ValueError(f"refusing non-https or non-ECB eurofxref URL: {url!r}")
    # URL is constrained to the canonical ECB eurofxref HTTPS endpoint above.
    with urllib.request.urlopen(url, timeout=30) as response:  # nosemgrep
        return response.read().decode(UTF_8_ENCODING)


__all__ = ["ECB_HIST_URL", "refresh_bundled_ecb_rates"]
