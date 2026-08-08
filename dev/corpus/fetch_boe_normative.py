"""Acquire a consolidated BOE normative into the bundled corpus.

The `corpus/normatives/html/` subtree had an extractor and no acquirer: nothing
in `src/` or `dev/` could state how `ley-37-1992-art-90.html` got there. This is
the missing half, and it deliberately mirrors
`sync_aeat_record_design_corpus.py` -- maintainer-invoked, repo-relative, no CLI
surface. `test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry`
forbids an operator verb for exactly this behaviour, so a verb here would be a
defect rather than an ergonomic gain.

Reaching the corpus by repo-relative path rather than through the
``aeat_normatives_root`` setting is load-bearing, not incidental: that setting
is declared ``BUNDLED_RESOURCE`` in ``cadrumo.core`` on the grounds that the
APPLICATION only ever reads it. Maintainer tooling writing through the setting
would falsify that declaration, which is precisely what happened once already
with ``aeat_manuals_root``. Writing repo-relatively keeps the declaration true.

==========================================================
Why version selection is not positional
==========================================================

A consolidated payload carries every historical version of the norm. Choosing
the wrong one bundles repealed law under a current filename, and the resulting
file looks authoritative: it is well-formed, it comes from the right URL over a
clean 200, and it still contains the phrases a ``required_text`` gate searches
for. Only the *number* is wrong, which is the one thing a filing cares about.

Position cannot decide it. Measured against the payloads this repo already
bundles, BOE lists versions **newest first** -- ``ley-37-1992-art-90.html`` runs
``20120714, 20091224, 19951230, 19941231, 19921229``, so "take the last" takes
the 1992 original. And ``boe-a-2024-12944`` is not monotonic across the document
at all, because the selector repeats once per *bloque* and blocks amended at
different times legitimately sit at different versions.

So the served version is read from the payload rather than inferred from order:
BOE marks it ``checked``, and the invariant is asserted **per fieldset**, since
a document-wide maximum would refuse a correct multi-block payload.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx

_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(_ROOT))

_CORPUS: Final[Path] = _ROOT / "src/cadrumo/_data/corpus/normatives/html"
_ACT_URL: Final[str] = "https://www.boe.es/buscar/act.php"

#: One ``<fieldset>`` per bloque; the version radios repeat inside each.
_FIELDSET = re.compile(r"<fieldset\b.*?</fieldset>", re.DOTALL | re.IGNORECASE)
_VERSION_RADIO = re.compile(
    r"<input[^>]*\btype=\"radio\"[^>]*\bvalue=\"(?P<version>\d{8})\"[^>]*>",
    re.IGNORECASE,
)
_CHECKED = re.compile(r"\bchecked\b", re.IGNORECASE)
_DOCUMENT_ID = re.compile(
    r"<input[^>]*\bname=\"id\"[^>]*\bvalue=\"(?P<document_id>BOE-[A-Z]-\d{4}-\d+)\"|"
    r"<input[^>]*\bvalue=\"(?P<alt>BOE-[A-Z]-\d{4}-\d+)\"[^>]*\bname=\"id\"",
    re.IGNORECASE,
)


class NormativeAcquisitionError(RuntimeError):
    """The payload cannot be shown to be the consolidated text in force."""


@dataclass(frozen=True)
class VersionSelection:
    """What one bloque's selector says, and what it served."""

    checked: str
    offered: tuple[str, ...]


def version_selections(payload: str) -> tuple[VersionSelection, ...]:
    """Return the checked and offered versions for every bloque in ``payload``.

    A bloque with no version radios contributes nothing: BOE emits fieldsets for
    unrelated form controls too, and treating those as blocks with no versions
    would make the invariant below trivially unsatisfiable.
    """
    selections: list[VersionSelection] = []
    for block in _FIELDSET.findall(payload):
        offered: list[str] = []
        checked: str | None = None
        for radio in _VERSION_RADIO.finditer(block):
            version = radio.group("version")
            offered.append(version)
            if _CHECKED.search(radio.group(0)):
                checked = version
        if not offered:
            continue
        if checked is None:
            raise NormativeAcquisitionError(
                f"a bloque offers versions {offered} but marks none of them checked, so the payload "
                "does not say which text BOE served"
            )
        selections.append(VersionSelection(checked=checked, offered=tuple(offered)))
    return tuple(selections)


def assert_serves_the_text_in_force(payload: str, *, document_id: str) -> tuple[VersionSelection, ...]:
    """Refuse a payload that is not the consolidated text currently in force.

    Raises:
        NormativeAcquisitionError: If the payload names a different document, or
            offers no version selector at all, or serves a bloque at anything
            other than that bloque's own latest version.

    Returns:
        The per-bloque selections, so a caller can record what it accepted.
    """
    found = _DOCUMENT_ID.search(payload)
    served_id = (found.group("document_id") or found.group("alt")) if found else None
    if served_id != document_id:
        raise NormativeAcquisitionError(
            f"payload declares document id {served_id!r}, not the requested {document_id!r}"
        )

    selections = version_selections(payload)
    if not selections:
        raise NormativeAcquisitionError(
            "payload carries no version selector, so it cannot be shown to be the consolidated text "
            "rather than a single historical redaction"
        )

    # Per fieldset, never document-wide: blocks amended at different times sit at
    # different versions legitimately, so a global maximum refuses correct text.
    stale = [s for s in selections if s.checked != max(s.offered)]
    if stale:
        raise NormativeAcquisitionError(
            "payload serves a superseded redaction: "
            + "; ".join(f"bloque checked {s.checked} while offering up to {max(s.offered)}" for s in stale)
        )
    return selections


def fetch_normative(
    *,
    document_id: str,
    destination_name: str,
    required_text: tuple[str, ...] = (),
    client: httpx.Client | None = None,
) -> Path:
    """Fetch one consolidated BOE norm and write it under the bundled corpus.

    Requests ``act.php`` with no version parameter, so BOE serves the text in
    force rather than one this caller guessed at, then refuses the payload
    unless it can be shown to BE that text. The bytes are written binary and
    read back before the path is returned: an encoding round trip through text
    mangles the accented characters legal text is full of.

    Args:
        document_id: The BOE identifier, e.g. ``BOE-A-2012-9364``.
        destination_name: Filename under ``corpus/normatives/html/``.
        required_text: Phrases that must appear in the fetched bytes -- the
            amending norm's identifier belongs here, so a payload that parses
            cleanly but is the wrong norm still refuses.
        client: Injected for testing; a real client is created when omitted.

    Returns:
        The written path.

    Raises:
        NormativeAcquisitionError: If the payload is not the text in force, or a
            ``required_text`` phrase is absent, or the read-back does not match.
    """
    owned = client is None
    http = client or httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-hydration/1.0"},
    )
    try:
        response = http.get(_ACT_URL, params={"id": document_id})
        response.raise_for_status()
        data = response.content
    finally:
        if owned:
            http.close()

    payload = data.decode("utf-8", errors="replace")
    assert_serves_the_text_in_force(payload, document_id=document_id)

    missing = [phrase for phrase in required_text if phrase not in payload]
    if missing:
        raise NormativeAcquisitionError(f"fetched {document_id} but these required phrases are absent: {missing}")

    destination = _CORPUS / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    if destination.read_bytes() != data:
        raise NormativeAcquisitionError(f"read-back of {destination} does not match the fetched bytes")
    return destination
