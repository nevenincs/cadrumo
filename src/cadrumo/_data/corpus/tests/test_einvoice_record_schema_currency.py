"""Gate: the AEAT record-schema snapshot must stay current with the filing window.

``corpus/aeat_official/einvoice_record_schemas/`` is a SINGLE snapshot, not a
revision-indexed family. That is forced by the source: AEAT serves one live
copy of each schema at the same URL it uses as the namespace, so there is no
per-ejercicio artefact to bundle and no version attribute to record. A
year-by-year coverage obligation of the kind
``test_exact_key_corpus_year_coverage.py`` places on the exact-key corpora
would be unsatisfiable here by construction.

What IS assertable is currency, and that is what was missing: the snapshot
aged silently, with nothing anywhere relating "fetched 2026-08-07" to the
filing years the product claims to serve. This module supplies the relation.
The manifest states the filing year through which the snapshot is asserted
accurate, and that claim is measured against the one writable master window in
``registry/aeat/legal/supported-filing-years.toml`` -- read through the loader
rather than copied, so widening the master window widens this obligation
without editing anything here.

Deliberately NOT a wall-clock check. A gate that reds on a calendar rollover
fires when nobody is looking at this corpus and teaches people to bump a date;
this one fires the moment someone admits a filing year the snapshot was never
claimed to cover, which is a deliberate authoring act with an author attached.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SCHEMA_ROOT = ("corpus", "aeat_official", "einvoice_record_schemas")


def _as_mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _manifest() -> dict[str, object]:
    path = Path(bundled_path(*_SCHEMA_ROOT)) / "manifest.json"
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    return _as_mapping(loaded)


def _artefacts() -> list[dict[str, object]]:
    raw = _manifest().get("artefacts")
    assert isinstance(raw, list)
    entries = cast(list[object], raw)
    assert entries, "the manifest lists no artefacts"
    return [_as_mapping(entry) for entry in entries]


def _snapshot() -> dict[str, object]:
    snapshot = _manifest().get("snapshot")
    assert isinstance(snapshot, dict), (
        "the schema corpus declares no snapshot block, so nothing states which filing "
        "years it is claimed accurate for and the artefacts can age unobserved again"
    )
    return cast(dict[str, object], snapshot)


def _asserted_through() -> int:
    year = _snapshot().get("asserted_current_through_filing_year")
    assert isinstance(year, int), "asserted_current_through_filing_year must be a filing year"
    return year


def _master_supported_filing_years() -> tuple[int, ...]:
    """Return the years the one writable master declaration carries."""
    declaration = bundled_authority().catalogues.supported_filing_years
    assert declaration is not None, (
        "the bundled registry declares no supported_filing_years catalogue; "
        "this gate has no master window to measure against"
    )
    return tuple(declaration.years)


def test_the_snapshot_is_asserted_current_through_the_whole_filing_window() -> None:
    """No admitted filing year may sit beyond the snapshot's own currency claim.

    Property, not tally: the obligation is derived from the master declaration
    on every run, so widening that window widens this gate rather than
    silently extending an unread claim over new years.
    """
    master = _master_supported_filing_years()
    assert master, "the master declaration carries no years; an empty window makes this gate vacuous"

    uncovered = sorted(year for year in master if year > _asserted_through())

    assert uncovered == [], (
        f"registry/aeat/legal/supported-filing-years.toml admits filing year(s) {uncovered}, "
        f"but the bundled AEAT record schemas are only asserted current through "
        f"{_asserted_through()}. AEAT revises SII and VERI*FACTU between ejercicios and serves "
        "no versioned copy, so an unverified snapshot silently becomes the wrong authority for "
        "the country vocabulary it grounds and for the record families the document probe "
        "recognises. Follow the manifest's refresh_procedure: re-fetch each artefact from its "
        "source_url, re-pin the hashes, raise asserted_current_through_filing_year, and let the "
        "payload-element gates report whatever moved. Do not raise the year alone."
    )


def test_the_currency_claim_is_anchored_in_the_declared_window() -> None:
    """A claim reaching past every admitted year is unfalsifiable, not conservative.

    Asserting currency through, say, 2099 would satisfy the gate above forever
    while grounding nothing. The claim must name a year the product actually
    files for, so it stays a statement someone verified rather than a ceiling
    chosen to keep a check quiet.
    """
    master = _master_supported_filing_years()

    assert _asserted_through() in master, (
        f"the schema snapshot claims currency through filing year {_asserted_through()}, which "
        f"the master declaration does not admit (it carries {sorted(master)}). Assert a year the "
        "product files for -- normally the newest -- so the claim can be checked against real work."
    )


def test_the_snapshot_records_how_to_refresh_every_artefact() -> None:
    """A staleness gate that cannot be discharged is an obstacle, not a control.

    The gate above fires on someone who is widening the filing window and has
    no context on this corpus. The manifest must therefore carry the procedure
    AND a reachable origin for every file, since these artefacts have no
    registry source row to fall back on.
    """
    snapshot = _snapshot()
    procedure = snapshot.get("refresh_procedure")
    assert isinstance(procedure, str) and procedure.strip(), (
        "the snapshot block declares no refresh_procedure, so the currency gate names an "
        "obligation with no way to discharge it"
    )
    assert "source_url" in procedure, "the refresh procedure must point at the per-artefact origins"

    for artefact in _artefacts():
        url = artefact.get("source_url")
        assert isinstance(url, str) and url.startswith("https://"), (
            f"artefact {artefact.get('path')!r} carries no fetchable source_url, so a refresh "
            "cannot re-verify it against AEAT"
        )


def test_the_snapshot_retrieval_date_agrees_with_the_manifest_it_annotates() -> None:
    """One retrieval date, not two that can drift apart.

    The manifest already carried a top-level ``retrieved_at`` and each artefact
    now carries its own. The snapshot block restates it for the reader who
    starts at the currency claim, so this pins all three together rather than
    letting the currency story diverge from the provenance story.
    """
    manifest = _manifest()
    retrieved_at = manifest["retrieved_at"]

    assert _snapshot().get("retrieved_at") == retrieved_at

    for artefact in _artefacts():
        assert artefact.get("retrieved_at") == retrieved_at, (
            f"artefact {artefact.get('path')!r} was retrieved on a different date from the "
            "snapshot it is part of; split the manifest or re-fetch the whole set together, "
            "because a mixed-date snapshot cannot carry one currency claim"
        )
