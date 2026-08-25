"""Admission gate for the external-layout candidate corpus."""

from __future__ import annotations

import json
from copy import deepcopy
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


def _adjudicated_payload() -> dict[str, object]:
    candidate = load_external_layout_candidate(_ROOT / "130" / "plain.json")
    return candidate.model_dump(mode="python")


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


def test_three_axis_adjudication_is_required_and_rejects_the_removed_legacy_flag() -> None:
    """Every sidecar states three independent verdicts and rejects the removed flag."""
    candidate = ExternalLayoutCandidate.model_validate(_adjudicated_payload())
    adjudication = candidate.authority_adjudication
    assert adjudication is not None
    assert adjudication.artifact_authenticity.verdict == "third_party_sample"
    assert adjudication.official_base_derivation.verdict == "verified_official_base_derivative"
    assert adjudication.registry_applicability.verdict == "current_authored_revision"
    assert adjudication.registry_applicability.revision_id == "2019-y-siguientes"

    conflicting_payload = _adjudicated_payload()
    source_chain = conflicting_payload["source_chain"]
    assert isinstance(source_chain, dict)
    source_chain["authority_status"] = "unverified"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ExternalLayoutCandidate.model_validate(conflicting_payload)


@pytest.mark.parametrize(
    "comparison_method",
    ["exact_96_dpi_render_match", "normalized_96_dpi_render_similarity"],
)
def test_pair_render_contract_distinguishes_exact_and_measured_similarity(comparison_method: str) -> None:
    """Pair evidence can state exact equality or an honestly measured near-match."""
    payload = _adjudicated_payload()
    adjudication = payload["authority_adjudication"]
    assert isinstance(adjudication, dict)
    derivation = adjudication["official_base_derivation"]
    assert isinstance(derivation, dict)
    pair_render = derivation["pair_render"]
    assert isinstance(pair_render, dict)
    pair_render["comparison_method"] = comparison_method
    ExternalLayoutCandidate.model_validate(payload)


@pytest.mark.parametrize(
    ("verdict", "revision_id"),
    [
        ("current_authored_revision", None),
        ("historical_authored_revision", None),
        ("historical_layout_without_authored_revision", "2025"),
    ],
)
def test_registry_applicability_requires_a_revision_exactly_for_authored_verdicts(
    verdict: str,
    revision_id: str | None,
) -> None:
    """Historical layouts without a registry row cannot smuggle in a revision claim."""
    payload = _adjudicated_payload()
    adjudication = payload["authority_adjudication"]
    assert isinstance(adjudication, dict)
    applicability = adjudication["registry_applicability"]
    assert isinstance(applicability, dict)
    applicability.update(verdict=verdict, revision_id=revision_id)
    with pytest.raises(ValidationError, match="revision_id is required exactly"):
        ExternalLayoutCandidate.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "replacement", "message"),
    [
        (("official_source", "source_url"), "http://example.test/form.pdf", "String should match pattern"),
        (
            ("official_source", "source_url"),
            "https://www.boe.es/example.pdf",
            "official source evidence must match its reviewed coordinate",
        ),
        (("official_source", "sha256"), "not-a-digest", "String should match pattern"),
        (("pair_render", "counterpart_kind"), "plain", "counterpart_kind must be 'fillable'"),
    ],
)
def test_official_source_and_pair_evidence_fail_closed(
    path: tuple[str, str],
    replacement: str,
    message: str,
) -> None:
    """Authority evidence is typed, content-addressed, and bound to the candidate pair."""
    payload = deepcopy(_adjudicated_payload())
    adjudication = payload["authority_adjudication"]
    assert isinstance(adjudication, dict)
    derivation = adjudication["official_base_derivation"]
    assert isinstance(derivation, dict)
    record = derivation[path[0]]
    assert isinstance(record, dict)
    record[path[1]] = replacement
    with pytest.raises(ValidationError, match=message):
        ExternalLayoutCandidate.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("document_id", "BOE-A-2015-1656 Annex II"),
        ("source_url", "https://www.boe.es/boe/dias/2015/02/19/pdfs/other.pdf"),
        ("sha256", "0" * 64),
        ("page_mapping", ({"candidate_page": 1, "official_page": 7},)),
    ],
)
def test_reviewed_official_evidence_coordinate_rejects_valid_looking_drift(
    field: str,
    replacement: object,
) -> None:
    """Well-formed substitutions cannot silently replace the reviewed official anchor."""
    payload = deepcopy(_adjudicated_payload())
    adjudication = payload["authority_adjudication"]
    assert isinstance(adjudication, dict)
    derivation = adjudication["official_base_derivation"]
    assert isinstance(derivation, dict)
    official_source = derivation["official_source"]
    assert isinstance(official_source, dict)
    official_source[field] = replacement
    with pytest.raises(ValidationError, match="official source evidence must match its reviewed coordinate"):
        ExternalLayoutCandidate.model_validate(payload)


def test_reviewed_official_evidence_coordinate_rejects_valid_wrong_authority_pair() -> None:
    """A host-valid AEAT coordinate cannot replace the reviewed BOE coordinate."""
    payload = deepcopy(_adjudicated_payload())
    adjudication = payload["authority_adjudication"]
    assert isinstance(adjudication, dict)
    derivation = adjudication["official_base_derivation"]
    assert isinstance(derivation, dict)
    official_source = derivation["official_source"]
    assert isinstance(official_source, dict)
    official_source.update(
        authority="aeat",
        source_url="https://sede.agenciatributaria.gob.es/example.pdf",
    )
    with pytest.raises(ValidationError, match="official source evidence must match its reviewed coordinate"):
        ExternalLayoutCandidate.model_validate(payload)


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
    copyfile(_ROOT / "130" / "fillable.pdf", candidate_dir / "fillable.pdf")
    copied_pdf.write_bytes(copied_pdf.read_bytes() + b"\n% changed-after-inventory\n")

    assert "content digest or size" in physical_candidate_mismatches(copied_sidecar)


def test_physical_gate_bites_when_counterpart_digest_is_valid_but_wrong(tmp_path: Path) -> None:
    """Pair evidence is recomputed from the actual adjacent opposite PDF bytes."""
    source_dir = _ROOT / "130"
    candidate_dir = tmp_path / "130"
    candidate_dir.mkdir()
    for filename in _EXPECTED_CANDIDATE_FILENAMES:
        copyfile(source_dir / filename, candidate_dir / filename)

    copied_sidecar = candidate_dir / "plain.json"
    payload = json.loads(copied_sidecar.read_text(encoding="utf-8"))
    payload["authority_adjudication"]["official_base_derivation"]["pair_render"][
        "counterpart_sha256"
    ] = "0" * 64
    copied_sidecar.write_text(json.dumps(payload), encoding="utf-8")

    assert "counterpart content digest" in physical_candidate_mismatches(copied_sidecar)
