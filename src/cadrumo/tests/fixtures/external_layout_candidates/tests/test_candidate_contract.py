"""Admission gate for the unverified external-layout candidate corpus."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest
from pydantic import ValidationError

from cadrumo.tests.fixtures import RECOGNISED_FIXTURE_PROVENANCES
from cadrumo.tests.fixtures.external_layout_candidates import (
    AEAT_PUBLISHED_FACSIMILE_CLASSIFICATION,
    EXTERNAL_LAYOUT_CANDIDATE_KINDS,
    EXTERNAL_LAYOUT_MODELOS,
    EXTERNAL_LAYOUT_SOURCE_CLASSIFICATION,
    ExternalLayoutCandidate,
    external_layout_source_class_is_non_authoritative,
    load_external_layout_candidate,
    physical_candidate_mismatches,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_IDENTITIES = frozenset(
    (modelo, kind) for modelo in EXTERNAL_LAYOUT_MODELOS for kind in EXTERNAL_LAYOUT_CANDIDATE_KINDS
)
_EXPECTED_CANDIDATE_FILENAMES = frozenset(
    f"{kind}{suffix}"
    for kind in EXTERNAL_LAYOUT_CANDIDATE_KINDS
    for suffix in (".json", ".pdf")
)
_SIDECARS = tuple(
    _ROOT / modelo / f"{kind}.json"
    for modelo, kind in sorted(_EXPECTED_IDENTITIES)
)


def test_candidate_inventory_is_exactly_five_modelos_by_two_variants() -> None:
    """Reject surprise paths and either half of an orphaned JSON/PDF pair."""
    root_files = frozenset(path.name for path in _ROOT.iterdir() if path.is_file())
    candidate_directories = frozenset(
        path.name
        for path in _ROOT.iterdir()
        if path.is_dir() and path.name not in {"tests", "__pycache__"}
    )

    assert root_files == frozenset({"__init__.py"})
    assert candidate_directories == EXTERNAL_LAYOUT_MODELOS
    for modelo in sorted(EXTERNAL_LAYOUT_MODELOS):
        entries = frozenset(path.name for path in (_ROOT / modelo).iterdir())
        assert entries == _EXPECTED_CANDIDATE_FILENAMES, (
            f"modelo {modelo}: candidate directory must contain exactly the plain/fillable "
            f"JSON/PDF pairs; found {sorted(entries)}"
        )

    found = frozenset((path.parent.name, path.stem) for path in _SIDECARS)
    assert found == _EXPECTED_IDENTITIES
    assert len(_SIDECARS) == 10


@pytest.mark.parametrize("sidecar_path", _SIDECARS, ids=lambda path: f"{path.parent.name}-{path.stem}")
def test_candidate_sidecar_is_strict_frozen_and_bound_to_its_filename(sidecar_path: Path) -> None:
    """Every JSON document crosses one strict typed and path-bound boundary."""
    candidate = load_external_layout_candidate(sidecar_path)
    assert isinstance(candidate, ExternalLayoutCandidate)
    assert candidate.modelo == sidecar_path.parent.name
    assert candidate.candidate_kind == sidecar_path.stem
    with pytest.raises(ValidationError, match="frozen"):
        candidate.modelo = "130"  # type: ignore[misc]


@pytest.mark.parametrize("sidecar_path", _SIDECARS, ids=lambda path: f"{path.parent.name}-{path.stem}")
def test_candidate_sidecar_matches_readable_physical_pdf(sidecar_path: Path) -> None:
    """Digest, size, PDF structure, DocInfo and identity scans are byte-derived."""
    assert physical_candidate_mismatches(sidecar_path) == ()


def test_external_layout_class_cannot_enrol_as_recognised_or_facsimile_provenance() -> None:
    """Externality is useful parser signal, never evidence of AEAT authority."""
    assert external_layout_source_class_is_non_authoritative()
    assert EXTERNAL_LAYOUT_SOURCE_CLASSIFICATION not in RECOGNISED_FIXTURE_PROVENANCES
    assert EXTERNAL_LAYOUT_SOURCE_CLASSIFICATION != AEAT_PUBLISHED_FACSIMILE_CLASSIFICATION
    assert frozenset({"real_corpus", "synthetic_generated"}) == RECOGNISED_FIXTURE_PROVENANCES


def test_strict_contract_rejects_an_unknown_sidecar_field() -> None:
    """Schema drift fails closed rather than becoming an ignored assertion."""
    candidate = load_external_layout_candidate(_SIDECARS[0])
    payload = candidate.model_dump(mode="json")
    payload["provenance"] = "real_corpus"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ExternalLayoutCandidate.model_validate(payload)


def test_physical_gate_bites_when_candidate_bytes_change(tmp_path: Path) -> None:
    """A sidecar cannot bless bytes that no longer match its content address."""
    source_sidecar = _ROOT / "130" / "plain.json"
    source_pdf = source_sidecar.with_suffix(".pdf")
    candidate_dir = tmp_path / "130"
    candidate_dir.mkdir()
    copied_sidecar = candidate_dir / "plain.json"
    copied_pdf = candidate_dir / "plain.pdf"
    copyfile(source_sidecar, copied_sidecar)
    copyfile(source_pdf, copied_pdf)
    copied_pdf.write_bytes(copied_pdf.read_bytes() + b"\n% changed-after-inventory\n")

    assert "content digest or size" in physical_candidate_mismatches(copied_sidecar)
