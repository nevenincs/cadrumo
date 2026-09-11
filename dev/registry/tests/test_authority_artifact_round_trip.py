"""The complete bundled registry survives publication and the runtime read.

A publication that the runtime reader cannot rebuild is not a publication: the
product refuses it, and nothing in a minimal fixture registry would show that.
This gate publishes the whole compiled bundled registry through the
publication workflow, reads it back through the same strict reader the product
runtime uses, and requires every modelo, every
catalogue and the evidence projection to come back equal as typed values.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import (
    AUTHORITY_ARTIFACT_SCHEMA_VERSION,
    AuthorityArtifact,
    AuthorityArtifactFormatError,
    read_authority_artifact,
    write_authority_artifact,
)
from cadrumo.domain.calculations.registry.facts.schema import MappingFactEntry, MappingFactPayload
from dev.registry.compiler.authority import compiled_bundled_authority

from ..pipeline.authority_publication import authority_candidate_identity
from ..pipeline.cli import publish_authority_candidate_workflow

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_full_bundled_registry_round_trips_through_a_publication(tmp_path: Path) -> None:
    registry_root = bundled_path("registry", "aeat")
    artifact_path = tmp_path / "authority.json"

    published = publish_authority_candidate_workflow(
        registry_root=registry_root,
        source_root=bundled_path(),
        artifact_path=artifact_path,
    )
    consumed = read_authority_artifact(artifact_path)

    bundled_modelos = {entry.name for entry in (registry_root / "modelos").iterdir() if entry.is_dir()}
    assert {str(modelo.id) for modelo in published.modelos} == bundled_modelos, (
        "the publication must carry every bundled modelo, or the round trip proves less than it claims"
    )
    published_by_id = {modelo.id: modelo for modelo in published.modelos}
    consumed_by_id = {modelo.id: modelo for modelo in consumed.modelos}
    assert consumed_by_id.keys() == published_by_id.keys()
    differing = sorted(
        str(modelo_id) for modelo_id, modelo in published_by_id.items() if consumed_by_id[modelo_id] != modelo
    )
    assert differing == [], f"modelos that do not round-trip as typed values: {differing}"
    assert consumed.catalogues.facts.facts, "the publication must carry governed facts, or their atoms prove nothing"
    assert consumed.catalogues == published.catalogues
    assert consumed.evidence == published.evidence
    assert consumed.identity_digest == published.identity_digest
    assert published.identity_digest == authority_candidate_identity(
        registry_root=registry_root, source_root=bundled_path()
    ), "the publication must record the identity the currency gate derives for the same inputs"


_ATOM_FACT_ID = "iva-rate-schedule"
_ATOMS: dict[str, Decimal | date | str] = {"decimal": Decimal("0.40"), "date": date(2025, 1, 1), "text": "0.40"}


def _atom_artifact() -> AuthorityArtifact:
    """A real compiled catalogue whose one mapping fact carries a decimal, a date and a look-alike string."""
    catalogues = compiled_bundled_authority().catalogues
    fact = catalogues.facts.facts[_ATOM_FACT_ID]
    variant = fact.variants[0]
    assert isinstance(variant.payload, MappingFactPayload)
    entries = tuple(MappingFactEntry(key=key, value=value) for key, value in _ATOMS.items())
    planted_variant = variant.model_copy(update={"payload": variant.payload.model_copy(update={"entries": entries})})
    planted_fact = fact.model_copy(update={"variants": (planted_variant,)})
    facts = catalogues.facts.model_copy(update={"facts": {_ATOM_FACT_ID: planted_fact}})
    return AuthorityArtifact(
        modelos=(),
        catalogues=catalogues.model_copy(update={"facts": facts}),
        identity_digest=sha256_hex(b"fact-atom-round-trip"),
    )


def _read_atoms(path: Path) -> dict[str, object]:
    consumed = read_authority_artifact(path)
    payload = consumed.catalogues.facts.facts[_ATOM_FACT_ID].variants[0].payload
    assert isinstance(payload, MappingFactPayload)
    return {str(entry.key): entry.value for entry in payload.entries}


def _redigest(path: Path, edit_payload_text: Callable[[str], str]) -> None:
    """Rewrite a published frame's payload with a matching digest, as a defective encoder would emit it."""
    frame = json.loads(path.read_bytes())
    payload_text = json.dumps(frame["payload"])
    edited = {"schema_version": frame["schema_version"], "payload": json.loads(edit_payload_text(payload_text))}
    path.write_bytes(canonical_json_bytes({**edited, "payload_sha256": sha256_hex(canonical_json_bytes(edited))}))


def _published_atoms(tmp_path: Path) -> Path:
    path = tmp_path / "authority.json"
    write_authority_artifact(path, _atom_artifact())
    return path


def test_a_decimal_and_a_date_keep_their_types_while_a_look_alike_string_stays_text(tmp_path: Path) -> None:
    path = _published_atoms(tmp_path)

    atoms = _read_atoms(path)

    assert atoms == _ATOMS
    assert {key: type(value) for key, value in atoms.items()} == {"decimal": Decimal, "date": date, "text": str}


def test_an_encoder_that_drops_the_tags_loses_the_types(tmp_path: Path) -> None:
    """The planted defect: the same frame with every atom written bare decodes to text, not to its type."""
    path = _published_atoms(tmp_path)
    _redigest(
        path,
        lambda text: text.replace('{"$decimal": "0.40"}', '"0.40"').replace('{"$date": "2025-01-01"}', '"2025-01-01"'),
    )

    atoms = _read_atoms(path)

    assert atoms != _ATOMS
    assert {key: type(value) for key, value in atoms.items()} == {"decimal": str, "date": str, "text": str}


@pytest.mark.parametrize(
    ("tagged", "replacement"),
    (
        pytest.param('{"$decimal": "0.40"}', '{"$float": "0.40"}', id="unknown-tag"),
        pytest.param('{"$decimal": "0.40"}', '{"$decimal": "+0.40"}', id="non-canonical-decimal"),
        pytest.param('{"$decimal": "0.40"}', '{"$decimal": "NaN"}', id="non-finite-decimal"),
        pytest.param('{"$date": "2025-01-01"}', '{"$date": "2025-1-1"}', id="non-canonical-date"),
        pytest.param('{"$date": "2025-01-01"}', '{"$decimal": "0.40", "$date": "2025-01-01"}', id="two-tags"),
        pytest.param('{"$date": "2025-01-01"}', "20250101", id="untagged-number"),
    ),
)
def test_a_malformed_or_untagged_non_string_atom_is_refused(tmp_path: Path, tagged: str, replacement: str) -> None:
    path = _published_atoms(tmp_path)
    _redigest(path, lambda text: text.replace(tagged, replacement))

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(path)


@pytest.mark.parametrize("superseded", ["cadrumo-authority-artifact-v1", "cadrumo-authority-artifact-v2"])
def test_a_frame_of_a_superseded_format_is_refused_by_name(tmp_path: Path, superseded: str) -> None:
    path = _published_atoms(tmp_path)
    frame = json.loads(path.read_bytes())
    document = {"schema_version": superseded, "payload": frame["payload"]}
    digest = sha256_hex(canonical_json_bytes(document))
    path.write_bytes(canonical_json_bytes({**document, "payload_sha256": digest, "signature": "00" * 64}))

    with pytest.raises(AuthorityArtifactFormatError, match=f"superseded format '{superseded}'"):
        read_authority_artifact(path)
    assert superseded != AUTHORITY_ARTIFACT_SCHEMA_VERSION
