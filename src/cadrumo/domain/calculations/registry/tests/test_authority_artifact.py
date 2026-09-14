"""Behavioral contract tests for the digest-checked authority publication."""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import MutableMapping
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from .....core.hashing import canonical_json_bytes, sha256_hex
from ..authority import bundled_authority_artifact_path
from ..authority_artifact import (
    AuthorityArtifact,
    AuthorityArtifactFormatError,
    AuthorityArtifactIntegrityError,
    AuthorityArtifactUnavailableError,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    PublishedSourceEvidence,
    read_authority_artifact,
    read_shared_authority_artifact,
    write_authority_artifact,
)
from ..errors import RegistryValidationError
from ..revision_contracts import NoPredecessor
from ..runtime_catalogues import RuntimeRegistryCatalogues
from ..schema import BindingDefinition, RegistryCatalogues
from ._artifact_runtime_support import _minimal_catalogues, _minimal_modelo, _minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUILD_IDENTITY = AuthorityBuildIdentity.from_inputs(
    source_identity_digest=sha256_hex(b"fixture authority sources"),
    compiler_identity_digest=sha256_hex(b"fixture authority compiler"),
)
_IDENTITY_DIGEST = _BUILD_IDENTITY.identity_digest
_LEGAL_ID = "ley-35-2006:art-1"
_LEGAL_TEXT = "art-1 fixture authority text"
_SOURCE_ID = "aeat-dr-130-2019-v12"


def _complete_catalogues() -> RegistryCatalogues:
    return _minimal_catalogues()


def _complete_evidence(*, source_payload: bytes | None = None) -> AuthorityEvidenceProjection:
    sources = ()
    if source_payload is not None:
        sources = (
            PublishedSourceEvidence(
                source_reference_id=_SOURCE_ID,
                payload=source_payload,
                payload_sha256=sha256_hex(source_payload),
            ),
        )
    return AuthorityEvidenceProjection(
        legal=(
            PublishedLegalEvidence(
                legal_reference_id=_LEGAL_ID,
                anchored_text=_LEGAL_TEXT,
                text_sha256=sha256_hex(_LEGAL_TEXT.encode("utf-8")),
            ),
        ),
        sources=sources,
    )


def _catalogues_with_required_source(payload: bytes) -> RegistryCatalogues:
    catalogues = _complete_catalogues()
    source = catalogues.sources[_SOURCE_ID].model_copy(
        update={"kind": "dictionary", "sha256": sha256_hex(payload), "bytes": len(payload)}
    )
    return catalogues.model_copy(update={"sources": {**catalogues.sources, _SOURCE_ID: source}})


def _validated_authority_payload(*, source_payload: bytes | None = None) -> AuthorityArtifact:
    """Build a real typed registry payload without requiring the authoring corpus."""
    catalogues = _complete_catalogues()
    if source_payload is not None:
        catalogues = _catalogues_with_required_source(source_payload)
    return AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=catalogues,
        build_identity=_BUILD_IDENTITY,
        identity_digest=_IDENTITY_DIGEST,
        evidence=_complete_evidence(source_payload=source_payload),
    )


def _publish(path: Path) -> None:
    """Publish one typed authority through the real writer."""
    write_authority_artifact(path, _validated_authority_payload())


def _write_frame(path: Path, payload: object, **extra: object) -> None:
    """Write a frame whose digest is consistent with its content, as a correct publisher would."""
    path.write_bytes(
        canonical_json_bytes(
            {
                "format": "cadrumo-authority-artifact-v5",
                "payload": payload,
                "payload_sha256": sha256_hex(canonical_json_bytes(payload)),
                **extra,
            }
        )
    )


def test_published_authority_round_trips_as_the_complete_typed_payload(tmp_path: Path) -> None:
    """A consumer receives the complete authority the writer published."""
    artifact_path = tmp_path / "authority.json"
    published = _validated_authority_payload()

    write_authority_artifact(artifact_path, published)

    consumed = read_authority_artifact(artifact_path)

    assert consumed == published
    assert consumed.build_identity == _BUILD_IDENTITY
    assert consumed.build_identity.component_dependency_digest == _BUILD_IDENTITY.component_dependency_digest
    assert consumed.identity_digest == consumed.build_identity.identity_digest
    assert consumed.modelos[0].title_localization_key == published.modelos[0].title_localization_key
    assert consumed.catalogues.legal == published.catalogues.legal
    revision = consumed.modelos[0].revisions["test-revision"]
    assert revision.valid_from == date(2024, 1, 1)
    assert revision.reviewed_at == date(2026, 7, 1)


def test_artifact_identity_must_match_its_complete_build_identity() -> None:
    with pytest.raises(ValueError, match="build receipts"):
        AuthorityArtifact(
            modelos=(_minimal_modelo(_minimal_revision()),),
            catalogues=_complete_catalogues(),
            build_identity=_BUILD_IDENTITY,
            identity_digest="0" * 64,
            evidence=_complete_evidence(),
        )


def test_build_identity_refuses_an_incoherent_component_receipt() -> None:
    other = AuthorityBuildIdentity.from_inputs(
        source_identity_digest=_BUILD_IDENTITY.source_identity_digest,
        compiler_identity_digest=sha256_hex(b"other fixture compiler"),
    )

    with pytest.raises(ValueError, match="component dependency identity"):
        AuthorityBuildIdentity(
            source_identity_digest=_BUILD_IDENTITY.source_identity_digest,
            compiler_identity_digest=other.compiler_identity_digest,
            component_dependency_digest=_BUILD_IDENTITY.component_dependency_digest,
        )


def test_current_frame_omits_schema_defaults_and_restores_the_same_typed_model(tmp_path: Path) -> None:
    """The compact frame may omit only declared defaults and restores their meaning."""
    artifact_path = tmp_path / "authority.json"
    published = AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=_complete_catalogues(),
        build_identity=_BUILD_IDENTITY,
        identity_digest=_IDENTITY_DIGEST,
        evidence=_complete_evidence(),
    )

    write_authority_artifact(artifact_path, published)

    frame = json.loads(artifact_path.read_bytes())
    wire_modelo = frame["payload"]["modelos"][0]
    assert set(frame) == {"format", "payload", "payload_sha256"}
    assert frame["format"] == "cadrumo-authority-artifact-v5"
    assert "capabilities" not in wire_modelo
    assert "calculation_class" not in wire_modelo
    assert "output_sensitivity" not in wire_modelo
    assert read_authority_artifact(artifact_path) == published


def test_published_authority_round_trips_strict_profile_selector_json(tmp_path: Path) -> None:
    """JSON arrays in a published selector rehydrate to the declared tuple shape."""
    artifact_path = tmp_path / "authority.json"
    binding = BindingDefinition.model_validate(
        {
            "id": "profile-selector",
            "provider": {"kind": "profile", "profile_key": "tax.id", "profile_keys": ()},
            "value": {"data_type": "text", "channel": "text"},
            # The explicit empty tuple becomes a JSON array in the artifact.
            # Its strict rehydration is the regression under test.
            "legal_refs": ("ley-35-2006:art-1",),
            "source_refs": ("aeat-dr-130-2019-v12",),
        }
    )
    modelo = _minimal_modelo(_minimal_revision(bindings=(binding,)))
    published = AuthorityArtifact(
        modelos=(modelo,),
        catalogues=_complete_catalogues(),
        build_identity=_BUILD_IDENTITY,
        identity_digest=_IDENTITY_DIGEST,
        evidence=_complete_evidence(),
    )

    write_authority_artifact(artifact_path, published)

    consumed = read_authority_artifact(artifact_path)
    assert consumed == published


def test_published_authority_preserves_a_grounded_no_predecessor_declaration(tmp_path: Path) -> None:
    """The complete artifact honors the predecessor field's declared JSON spelling."""
    artifact_path = tmp_path / "authority.json"
    predecessor = NoPredecessor(
        reason="The fixture has no earlier edition.",
        legal_refs=("ley-35-2006:art-1",),
        source_refs=("aeat-dr-130-2019-v12",),
    )
    revision = _minimal_revision().model_copy(update={"predecessor": predecessor})
    published = AuthorityArtifact(
        modelos=(_minimal_modelo(revision),),
        catalogues=_complete_catalogues(),
        build_identity=_BUILD_IDENTITY,
        identity_digest=_IDENTITY_DIGEST,
        evidence=_complete_evidence(),
    )

    write_authority_artifact(artifact_path, published)

    consumed = read_authority_artifact(artifact_path)
    assert consumed == published


def test_a_payload_edited_without_its_digest_is_refused_as_corrupt(tmp_path: Path) -> None:
    """A changed payload under the old recorded digest is a corrupt artifact, never a readable one."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    corrupted = json.loads(artifact_path.read_bytes())
    corrupted["payload"]["identity_digest"] = "0" * 64
    artifact_path.write_bytes(canonical_json_bytes(corrupted))

    with pytest.raises(AuthorityArtifactIntegrityError, match="content digest"):
        read_authority_artifact(artifact_path)


def test_writer_refuses_a_missing_runtime_table(tmp_path: Path) -> None:
    """A minimal authority is not publishable until every runtime table is present."""
    incomplete = _complete_catalogues().model_copy(
        update={"runtime": RuntimeRegistryCatalogues().model_copy(update={"countries": {}})}
    )
    artifact = AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=incomplete,
        build_identity=_BUILD_IDENTITY,
        identity_digest=_IDENTITY_DIGEST,
        evidence=_complete_evidence(),
    )

    with pytest.raises(RegistryValidationError, match=r"runtime authority catalogues are incomplete:.*countries"):
        write_authority_artifact(tmp_path / "authority.json", artifact)


def test_a_digest_consistent_frame_does_not_admit_an_invalid_typed_payload(tmp_path: Path) -> None:
    """A matching digest never substitutes for strict authority reconstruction."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    frame = json.loads(artifact_path.read_bytes())
    frame["payload"]["catalogues"] = {}
    _write_frame(artifact_path, frame["payload"])

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(artifact_path)


def test_a_digest_consistent_frame_missing_legal_evidence_is_refused(tmp_path: Path) -> None:
    """Artifact admission requires exact coverage of the legal catalogue."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    frame = json.loads(artifact_path.read_bytes())
    frame["payload"]["evidence"]["legal"] = []
    _write_frame(artifact_path, frame["payload"])

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(artifact_path)


def test_a_digest_consistent_frame_missing_required_source_evidence_is_refused(tmp_path: Path) -> None:
    """A runtime-required dictionary source cannot disappear behind a valid frame digest."""
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(artifact_path, _validated_authority_payload(source_payload=b"fixture dictionary"))
    frame = json.loads(artifact_path.read_bytes())
    frame["payload"]["evidence"]["sources"] = []
    _write_frame(artifact_path, frame["payload"])

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(artifact_path)


def test_a_digest_consistent_frame_with_mismatched_source_metadata_is_refused(tmp_path: Path) -> None:
    """Runtime source bytes must retain the catalogue hash and length validated by publication."""
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(artifact_path, _validated_authority_payload(source_payload=b"fixture dictionary"))
    frame = json.loads(artifact_path.read_bytes())
    frame["payload"]["catalogues"]["sources"][_SOURCE_ID]["sha256"] = "0" * 64
    _write_frame(artifact_path, frame["payload"])

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(artifact_path)


def test_a_digest_consistent_frame_with_duplicate_modelo_identity_is_refused(tmp_path: Path) -> None:
    """Artifact admission refuses two published definitions for one modelo identity."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    frame = json.loads(artifact_path.read_bytes())
    frame["payload"]["modelos"].append(frame["payload"]["modelos"][0])
    _write_frame(artifact_path, frame["payload"])

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(artifact_path)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        pytest.param("tax_id.check.nif_letters", None, id="missing-checksum-table"),
        pytest.param("tax_id.check.nif_letters", "TRWAGMYFPDXBNJZSQVHLCKT", id="duplicate-checksum-table-entry"),
        pytest.param(
            "tax_id.check.nie_prefix.X",
            "\N{ARABIC-INDIC DIGIT ZERO}",
            id="unicode-nie-substitution",
        ),
        pytest.param("tax_id.check.cif_digit_only_kinds", "AABEH", id="duplicate-cif-partition-leader"),
        pytest.param("tax_id.check.cif_letter_table", "JABCDEFGHJ", id="duplicate-cif-table-entry"),
    ),
)
def test_artifact_with_malformed_embedded_tax_id_format_fails_closed(
    tmp_path: Path, key: str, value: str | None
) -> None:
    """A valid frame digest cannot make malformed fact 0102 operative."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    frame = json.loads(artifact_path.read_bytes())
    entries = frame["payload"]["catalogues"]["facts"]["facts"]["spanish-tax-identifier-format"]["variants"][0][
        "payload"
    ]["entries"]
    if value is None:
        entries[:] = [entry for entry in entries if entry["key"] != key]
    else:
        next(entry for entry in entries if entry["key"] == key)["value"] = value
    _write_frame(artifact_path, frame["payload"])

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        read_authority_artifact(artifact_path)


def test_a_current_frame_with_an_extra_member_is_refused(tmp_path: Path) -> None:
    """The reader refuses a frame that carries an unrecognized member."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    payload = json.loads(artifact_path.read_bytes())["payload"]
    _write_frame(artifact_path, payload, unrecognized_member=True)

    with pytest.raises(AuthorityArtifactFormatError, match="unexpected members \\['unrecognized_member'\\]"):
        read_authority_artifact(artifact_path)


@pytest.mark.parametrize(
    ("format_name", "message"),
    (
        pytest.param("cadrumo-authority-artifact-v3", "superseded format", id="superseded"),
        pytest.param("cadrumo-authority-artifact-v4", "superseded format", id="previous"),
        pytest.param("cadrumo-authority-artifact-v6", "unsupported format", id="unknown-future"),
    ),
)
def test_a_noncurrent_explicit_format_is_refused(tmp_path: Path, format_name: str, message: str) -> None:
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    frame = json.loads(artifact_path.read_bytes())
    _write_frame(artifact_path, frame["payload"], format=format_name)

    with pytest.raises(AuthorityArtifactFormatError, match=message):
        read_authority_artifact(artifact_path)


def test_publication_validates_the_complete_graph_before_cutover(tmp_path: Path) -> None:
    """A fact removal that invalidates Modelo vocabulary preserves the known-good artifact."""
    artifact_path = tmp_path / "authority.json"
    shutil.copyfile(bundled_authority_artifact_path(), artifact_path)
    artifact = read_authority_artifact(artifact_path)
    facts = dict(artifact.catalogues.facts.facts)
    facts.pop("iva-statutory-schema-vocabulary")
    invalid_facts = artifact.catalogues.facts.model_copy(update={"facts": facts})
    previous_bytes = artifact_path.read_bytes()

    with pytest.raises(AuthorityArtifactFormatError, match="invalid authority payload"):
        write_authority_artifact(
            artifact_path,
            dataclasses.replace(
                artifact,
                catalogues=artifact.catalogues.model_copy(update={"facts": invalid_facts}),
            ),
        )

    assert artifact_path.read_bytes() == previous_bytes


def test_before_replace_refusal_preserves_the_previous_publication(tmp_path: Path) -> None:
    """A final publication guard can refuse cutover without changing destination bytes."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    previous_bytes = artifact_path.read_bytes()

    def refuse_cutover() -> None:
        staged = tuple(path for path in tmp_path.iterdir() if path != artifact_path)
        assert len(staged) == 1
        assert staged[0].read_bytes()
        raise RuntimeError("publication receipt changed")

    with pytest.raises(RuntimeError, match="publication receipt changed"):
        write_authority_artifact(
            artifact_path,
            _validated_authority_payload(),
            before_replace=refuse_cutover,
        )

    assert artifact_path.read_bytes() == previous_bytes


@pytest.mark.parametrize("artifact_bytes", [b"not-json", b'{"payload":{}}'])
def test_malformed_artifact_frame_is_refused(tmp_path: Path, artifact_bytes: bytes) -> None:
    """Malformed wire inputs never reach authority reconstruction."""
    artifact_path = tmp_path / "authority.json"
    artifact_path.write_bytes(artifact_bytes)

    with pytest.raises(AuthorityArtifactFormatError):
        read_authority_artifact(artifact_path)


def test_consumer_mutation_cannot_change_a_later_authority_read(tmp_path: Path) -> None:
    """A read authority graph refuses mutation, so a later read, shared or fresh, observes the publication."""
    artifact_path = tmp_path / "authority.json"
    _publish(artifact_path)
    first = read_authority_artifact(artifact_path)
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", first.catalogues.legal)["consumer-injected"] = object()

    later = read_authority_artifact(artifact_path)
    shared = read_shared_authority_artifact(artifact_path)
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", shared.catalogues.legal)["consumer-injected"] = object()

    assert "consumer-injected" not in later.catalogues.legal
    assert read_shared_authority_artifact(artifact_path) is shared
    assert "consumer-injected" not in shared.catalogues.legal
    assert shared == later == _validated_authority_payload()


def test_shared_read_refuses_a_missing_publication(tmp_path: Path) -> None:
    """The shared reader refuses an absent artifact exactly as the strict reader does."""
    with pytest.raises(AuthorityArtifactUnavailableError):
        read_shared_authority_artifact(tmp_path / "missing-authority.json")


def test_missing_publication_refuses_without_rebuilding_from_authoring_inputs(tmp_path: Path) -> None:
    """An absent artifact is a deterministic runtime refusal at the publication boundary."""
    with pytest.raises(AuthorityArtifactUnavailableError):
        read_authority_artifact(tmp_path / "missing-authority.json")
