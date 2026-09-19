"""A registered record design must carry the provenance its capture recorded.

The corpus ingest harness writes a ``manifest.json`` beside each modelo's
``files/`` directory, and every artefact row in it is a machine-written capture
record: the URL the bytes came from, the page that linked it, the digest and
length of what landed, and the date it was retrieved. The sources catalogue
then restates that same provenance by hand, in TOML, as a ``SourceReference``.

Two records of one fact, one written by a tool and one typed by a person, with
nothing comparing them. A mistyped digest would be caught downstream the first
time a hash pin was verified, but a mistyped URL or capture date would not be
caught anywhere: both are carried into the compiled registry, into calculation
provenance, and into a filing handoff as if they had been observed.

NO COUNT IS PINNED and no allowlist exists. The comparison walks whatever
designs are registered now and whatever manifests exist now, so a newly
enrolled source is compared the moment it is authored, and a source whose file
leaves the corpus surfaces as a missing capture record rather than silently
passing.

``retrieved_at`` is compared with the rest. The manifest row is written by the
ingest harness at the moment the bytes land; the catalogue row is typed
afterwards, and the disagreements this comparison first surfaced were all of
that shape -- the authoring date restated as a retrieval date, in one case
naming a day before the bytes were ever captured. A genuine re-retrieval is
not an exception to the rule: the harness rewrites the manifest when it
re-fetches, so an advanced capture date reaches this gate through the record
that observed it, not through a hand edit that outruns it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from .catalogue_verification_support import _catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN_ROOT_PARTS = ("corpus", "aeat_official", "disenos_registro")


def _capture_records() -> Mapping[Path, Mapping[str, Any]]:
    """Index every per-modelo capture row by the file it describes.

    The modelo manifests are the authority; the root manifest beside them
    describes the sweep rather than any one artefact, so it is skipped.
    """
    root = bundled_path(*_DESIGN_ROOT_PARTS)
    records: dict[Path, Mapping[str, Any]] = {}
    for manifest in root.rglob("manifest.json"):
        if manifest.parent == root:
            continue
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for artefact in payload.get("artefacts", ()):
            records[(manifest.parent / artefact["stored_path"]).resolve()] = artefact
    return records


def _registered_designs() -> tuple[Any, ...]:
    return tuple(source for source in _catalogues().sources.values() if "disenos_registro" in source.corpus_path)


def test_the_comparison_reaches_designs_across_many_modelos() -> None:
    """Anti-vacuity: a comparison that matched nothing would pass just as quietly."""
    records = _capture_records()
    assert records, "no capture record was indexed at all; the manifest layout or corpus path has moved"
    designs = _registered_designs()
    assert len(designs) > 50, f"only {len(designs)} registered design(s) reached; the catalogue walk has narrowed"
    modelos = {source.corpus_path.split("/")[3] for source in designs}
    assert len(modelos) > 10, f"only {len(modelos)} modelo director(ies) reached; the comparison has narrowed"


def test_every_registered_design_has_a_capture_record() -> None:
    """A hand-authored source row with no capture behind it asserts an unobserved retrieval."""
    base = bundled_path()
    records = _capture_records()
    orphaned = sorted(
        f"{source.id} -> {source.corpus_path}"
        for source in _registered_designs()
        if (base / source.corpus_path).resolve() not in records
    )
    assert not orphaned, (
        f"{len(orphaned)} registered record-design source(s) name a corpus file that no ingest "
        "manifest ever recorded capturing:\n  " + "\n  ".join(orphaned)
    )


def _provenance_disagreements(
    designs: Iterable[Any],
    records: Mapping[Path, Mapping[str, Any]],
    *,
    base: Path,
) -> list[str]:
    """Compare each design's declared origin with what its capture observed.

    Taken as arguments rather than read from the bundle so the detector can be
    shown to bite on a doctored capture record, without touching the corpus,
    the catalogue, or the contributor's working tree.
    """
    disagreements: list[str] = []
    for source in designs:
        captured = records.get((base / source.corpus_path).resolve())
        if captured is None:
            continue  # owned by the sibling gate above
        for field, declared, observed in (
            ("sha256", source.sha256, captured["sha256"]),
            ("bytes", source.bytes, captured["bytes"]),
            ("source_url", str(source.source_url), captured["url"]),
            ("retrieved_at", str(source.retrieved_at), captured["retrieved_at"]),
        ):
            if declared != observed:
                disagreements.append(f"{source.id} {field}: catalogue {declared!r} vs capture {observed!r}")
    return sorted(disagreements)


def test_registered_design_bytes_and_origin_match_their_capture_record() -> None:
    """Digest, length and origin URL are observations, and both records must agree on them."""
    disagreements = _provenance_disagreements(_registered_designs(), _capture_records(), base=bundled_path())
    assert not disagreements, (
        f"{len(disagreements)} registered record-design source(s) disagree with the capture record "
        "for the same bytes:\n  " + "\n  ".join(disagreements)
    )


@pytest.mark.parametrize(
    ("field", "falsified"),
    (
        ("sha256", "0" * 64),
        ("bytes", 1),
        ("url", "https://x.invalid/"),
        ("retrieved_at", "1970-01-01"),
    ),
)
def test_a_falsified_capture_record_is_detected(field: str, falsified: object) -> None:
    """Detector teeth, one representative defect per compared field.

    One capture row is doctored in a local copy of the index. Nothing on disk
    changes: corpus, manifests and catalogue are read exactly as the live gate
    reads them, and only this function's own mapping differs.
    """
    base = bundled_path()
    designs = _registered_designs()
    records = dict(_capture_records())
    target = next(source for source in designs if (base / source.corpus_path).resolve() in records)
    key = (base / target.corpus_path).resolve()
    records[key] = {**records[key], field: falsified}

    disagreements = _provenance_disagreements(designs, records, base=base)

    assert len(disagreements) == 1, f"the falsified {field} was not isolated: {disagreements}"
    assert disagreements[0].startswith(f"{target.id} ")
