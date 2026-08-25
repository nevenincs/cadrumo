"""Contract tests for the shared manual-PDF corpus-text sidecar schema.

The sidecar is written by the corpus extraction tooling and read
by the registry evidence validator. These tests pin the one contract both sides
consume: every committed sidecar satisfies it, and every field the writer
guarantees is actually required rather than optional.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..directory_scan import scan_directory
from ..manual_corpus_sidecar import (
    MANUAL_CORPUS_TEXT_SCHEMA_VERSION,
    MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX,
    ManualCorpusTextSidecar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# src/cadrumo/core/tests/ -> parents[3] is src/cadrumo.
_MANUAL_CORPUS_TEXT_ROOT = Path(__file__).resolve().parents[1].parent / "_data" / "manual_corpus_text"


def _first_committed_sidecar_payload() -> dict[str, object]:
    sidecars = scan_directory(_MANUAL_CORPUS_TEXT_ROOT, pattern=f"*{MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX}", recursive=True)
    assert sidecars, "no committed manual corpus text sidecars found"
    payload: dict[str, object] = json.loads(sidecars[0].read_text(encoding="utf-8"))
    return payload


def test_every_committed_sidecar_satisfies_the_shared_contract() -> None:
    """Each shipped sidecar validates, proving writer and reader agree on real data.

    This is the writer/reader parity gate: the extractor now constructs
    :class:`ManualCorpusTextSidecar` to serialise, and the runtime evidence
    validator admits a sidecar only through the same model. A field the writer
    stopped emitting, or a schema-version bump landed on one side only, reds
    here against the actually-committed corpus rather than degrading silently
    to on-demand PDF extraction on end-user machines.
    """
    sidecars = scan_directory(_MANUAL_CORPUS_TEXT_ROOT, pattern=f"*{MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX}", recursive=True)
    assert sidecars, "no committed manual corpus text sidecars found"

    for sidecar_path in sidecars:
        model = ManualCorpusTextSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
        assert model.schema_version == MANUAL_CORPUS_TEXT_SCHEMA_VERSION
        # The sidecar must be filed under the corpus path it claims, or the
        # runtime addressing lookup and the payload disagree.
        expected_relative = model.corpus_path[len("corpus/") :] + MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX
        assert sidecar_path.relative_to(_MANUAL_CORPUS_TEXT_ROOT).as_posix() == expected_relative


@pytest.mark.parametrize(
    "field",
    ["schema_version", "corpus_path", "source_sha256", "extraction_platform", "normalised_text"],
)
def test_every_writer_guaranteed_field_is_required(field: str) -> None:
    """Dropping any writer-guaranteed field refuses validation.

    The defect this pins: the runtime reader used to check only
    ``source_sha256`` and that ``normalised_text`` was a string, so a sidecar
    missing the schema version, corpus path, or extraction-platform stamp was
    served as if the build-time extractor had produced it.
    """
    payload = _first_committed_sidecar_payload()
    del payload[field]
    with pytest.raises(ValidationError):
        ManualCorpusTextSidecar.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 1),
        ("schema_version", MANUAL_CORPUS_TEXT_SCHEMA_VERSION + 1),
        ("corpus_path", "manuals/renta/2020/part1/source.pdf"),
        ("source_sha256", "not-a-digest"),
        ("source_sha256", "AB" * 32),
        ("extraction_platform", ""),
        ("normalised_text", ""),
    ],
)
def test_malformed_field_values_are_refused(field: str, value: object) -> None:
    """Out-of-contract values are refused rather than interpreted."""
    payload = _first_committed_sidecar_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        ManualCorpusTextSidecar.model_validate(payload)


def test_unknown_fields_are_refused() -> None:
    """An unexpected key means a writer this reader does not understand."""
    payload = _first_committed_sidecar_payload()
    payload["extraction_tool"] = "pypdfium2"
    with pytest.raises(ValidationError):
        ManualCorpusTextSidecar.model_validate(payload)


def test_serialisation_round_trip_is_stable() -> None:
    """The writer's serialisation is re-admissible by the reader unchanged."""
    payload = _first_committed_sidecar_payload()
    model = ManualCorpusTextSidecar.model_validate(payload)
    assert ManualCorpusTextSidecar.model_validate_json(model.model_dump_json()) == model
