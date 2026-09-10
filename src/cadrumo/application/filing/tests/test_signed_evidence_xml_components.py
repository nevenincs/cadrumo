"""Artifact-only behavior at the XML filing and Sede parsing boundaries.

The assertions deliberately exercise real bytes through the renderer, verifier,
and submitted-file reader.  The only authoritative inputs are an artifact that
is signed and then reread by the production codec; no registry/corpus directory
is made available to either component.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import declarations_observations
from ....adapters.outbound.aeat.sede.declarations_observations import observed_casillas_from_submitted_file
from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....adapters.outbound.aeat.sede.errors import SedeParseError
from ....adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact
from ....core.declaracion_idioma import DeclaracionIdioma
from ....core.ed25519_signing import generate_ed25519_keypair_hex
from ....core.hashing import sha256_hex
from ....core.period import Period
from ....domain.calculations.registry.authority import ValidatedRegistryAuthority, _authority_from_published_artifact
from ....domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
    PublishedSourceEvidence,
    read_authority_artifact,
    write_authority_artifact,
)
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import RegistryCatalogues
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ....domain.calculations.registry.schema_references import SourceReference
from ....domain.calculations.registry.tests._referential_integrity_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
    minimal_source_ref,
    snapshot_for_revision,
)
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.schema import ModeloDraft, ModeloDraftStatus, ModeloValue, ModeloValueKind
from .._export_xml_dictionary import render_xml_dictionary_layout
from ..export_verification import DeclaracionVerifyVerdict, verify_export
from ..runtime import RegistrySchemaAccessor, _subview_from_snapshot, collection_from_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_IDENTITY_DIGEST = "e4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f"
_DICTIONARY_SOURCE_ID = "test-xml-dictionary"
_XSD_SOURCE_ID = "test-xml-schema"
_DICTIONARY = b"AMOUNT=[/Declaracion/Importe][P102][001][importe]\n"
_XSD = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">
  <xs:simpleType name=\"tipo_VersionXSD\"><xs:restriction base=\"xs:string\"><xs:enumeration value=\"1.0\"/></xs:restriction></xs:simpleType>
  <xs:element name=\"Declaracion\"><xs:complexType><xs:sequence><xs:element name=\"Aux\" minOccurs=\"0\"/><xs:element name=\"Importe\" minOccurs=\"0\"/></xs:sequence></xs:complexType></xs:element>
</xs:schema>
"""


@pytest.fixture(scope="session", autouse=True)
def compose_runtime_ports() -> Iterator[None]:
    """Keep isolated signed-artifact behavior independent of unrelated port wiring."""
    yield


@pytest.fixture(autouse=True)
def _reset_filing_store() -> Iterator[None]:
    """This pure artifact boundary test neither opens nor mutates filing storage."""
    yield


def _source(source_id: str, *, kind: str, corpus_path: str, body: bytes) -> SourceReference:
    """Build a typed source declaration whose bytes live only in the artifact."""
    return minimal_source_ref().model_copy(
        update={
            "id": source_id,
            "kind": kind,
            "corpus_path": corpus_path,
            "sha256": sha256_hex(body),
            "bytes": len(body),
        }
    )


def _layout() -> ExportLayoutDefinition:
    return ExportLayoutDefinition(
        id="test-xml-layout",
        format="xml_dictionary",
        dictionary_source_ref=_DICTIONARY_SOURCE_ID,
        source_refs=(_DICTIONARY_SOURCE_ID, _XSD_SOURCE_ID),
        legal_refs=("ley-35-2006:art-1",),
        aux_idioma=DeclaracionIdioma.CASTELLANO,
        aux_version="1.00",
    )


def _published_runtime(
    tmp_path: Path, *, include_dictionary: bool = True, include_xsd: bool = True
) -> tuple[RegistrySchemaAccessor, ValidatedRegistryAuthority]:
    """Read a signed staged authority whose corpus location does not exist."""
    layout = _layout()
    revision = minimal_revision(export_layouts=(layout,))
    modelo = minimal_modelo(revision)
    dictionary_source = _source(
        _DICTIONARY_SOURCE_ID,
        kind="dictionary",
        corpus_path="corpus/absent/authority-dictionary.txt",
        body=_DICTIONARY,
    )
    xsd_source = _source(
        _XSD_SOURCE_ID,
        kind="xsd",
        corpus_path="corpus/absent/authority-schema.xsd",
        body=_XSD,
    )
    base_catalogues = minimal_catalogues()
    catalogues = RegistryCatalogues(
        legal=base_catalogues.legal,
        sources={**base_catalogues.sources, _DICTIONARY_SOURCE_ID: dictionary_source, _XSD_SOURCE_ID: xsd_source},
    )
    artifact_path = tmp_path / "staged" / "registry" / "authority" / "authority.json"
    keys = generate_ed25519_keypair_hex()
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(modelo,),
            catalogues=catalogues,
            identity_digest=_IDENTITY_DIGEST,
            evidence=AuthorityEvidenceProjection(
                sources=(
                    *(
                        (PublishedSourceEvidence(_DICTIONARY_SOURCE_ID, _DICTIONARY, sha256_hex(_DICTIONARY)),)
                        if include_dictionary
                        else ()
                    ),
                    *((PublishedSourceEvidence(_XSD_SOURCE_ID, _XSD, sha256_hex(_XSD)),) if include_xsd else ()),
                )
            ),
        ),
        signing_private_key_hex=keys.private_key_hex,
    )
    published = read_authority_artifact(artifact_path, verification_public_key_hex=keys.public_key_hex)
    authority = _authority_from_published_artifact(published, artifact_path=artifact_path)

    # The snapshot is typed production data.  Its source map contains just the
    # references that the layout declares; the paths above are intentionally
    # absent, so a raw corpus read would fail this behavioral gate.
    snapshot = snapshot_for_revision(modelo, catalogues, revision)
    provider = RegistrySchemaAccessor(
        collections={"130": collection_from_snapshot(snapshot)},
        subviews={"130": _subview_from_snapshot(snapshot)},
        snapshots={"130": snapshot},
        sources=snapshot.sources,
        evidence=published.evidence,
    )
    return provider, authority


def _draft() -> ModeloDraft:
    period = Period.from_year_and_code(2024, "0A")
    now = datetime(2026, 9, 11, tzinfo=UTC)
    return ModeloDraft(
        draft_id="signed-evidence-xml",
        modelo="130",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref={"modelo": "130", "revision_id": "test-revision", "modelo_year": 2024, "period": "0A"},
        status=ModeloDraftStatus.APROBADO,
        values=(ModeloValue(casilla_id="001", value="12.50", kind=ModeloValueKind.LITERAL, source="test"),),
        created_at=now,
        updated_at=now,
        schema_version="registry:130:test-revision",
    )


def _declaration() -> Declaracion:
    return Declaracion(
        modelo="130",
        ejercicio=2024,
        period=Period.from_year_and_code(2024, "0A"),
        expediente_id="202410013522222A",
        estado="ALTA",
        presented_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def test_signed_projection_renders_verifies_and_parses_submitted_xml_without_corpus_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One staged publication supplies both the writer/verifier and Sede reader."""
    provider, authority = _published_runtime(tmp_path)
    corpus_root = tmp_path / "staged" / "corpus"
    assert not corpus_root.exists()
    draft = _draft()
    layout = provider.get_subview("130").export_layouts[0]
    payload = render_xml_dictionary_layout(layout, draft=draft, headers={}, schema_provider=provider)
    output_path = tmp_path / "submitted.xml"
    output_path.write_bytes(payload)

    verification = verify_export(draft, file_path=output_path, schema_provider=provider)
    assert verification.verdict is DeclaracionVerifyVerdict.MATCH

    monkeypatch.setattr(declarations_observations, "_registry_authority", lambda: authority)
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl("https://www6.aeat.es/ES13/S/IAFR"),
        content_type="application/xml",
        byte_count=len(payload),
        sha256=sha256_hex(payload),
        captured_at=datetime(2026, 9, 11, tzinfo=UTC),
    )
    observations = observed_casillas_from_submitted_file(
        snapshot=provider.get_snapshot("130"), declaration=_declaration(), body=payload, artefact=artefact
    )

    assert [(item.casilla_id, item.value) for item in observations] == [("001", "12.50")]

    output_path.write_bytes(payload.replace(b"12.50", b"13.50"))
    assert (
        verify_export(draft, file_path=output_path, schema_provider=provider).verdict is DeclaracionVerifyVerdict.DRIFT
    )


def test_missing_signed_dictionary_payload_refuses_before_xml_output_or_sede_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A signed authority without a required runtime payload cannot produce evidence."""
    provider, missing_authority = _published_runtime(tmp_path, include_dictionary=False)
    layout = provider.get_subview("130").export_layouts[0]
    missing_provider = RegistrySchemaAccessor(
        collections=provider.collections,
        subviews=provider.subviews,
        snapshots=provider.snapshots,
        sources=provider.sources,
        evidence=missing_authority.evidence,
    )
    with pytest.raises(RegistryValidationError):
        render_xml_dictionary_layout(layout, draft=_draft(), headers={}, schema_provider=missing_provider)

    monkeypatch.setattr(declarations_observations, "_registry_authority", lambda: missing_authority)
    payload = b"<?xml version='1.0'?><Declaracion><Importe>12.50</Importe></Declaracion>"
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl("https://www6.aeat.es/ES13/S/IAFR"),
        content_type="application/xml",
        byte_count=len(payload),
        sha256=sha256_hex(payload),
        captured_at=datetime(2026, 9, 11, tzinfo=UTC),
    )
    with pytest.raises(SedeParseError):
        observed_casillas_from_submitted_file(
            snapshot=provider.get_snapshot("130"), declaration=_declaration(), body=payload, artefact=artefact
        )


def test_missing_signed_xsd_payload_refuses_before_xml_output(tmp_path: Path) -> None:
    """The renderer cannot substitute a raw XSD when the signed projection omits it."""
    provider, _authority = _published_runtime(tmp_path, include_xsd=False)

    with pytest.raises(FilingExportValidationError):
        render_xml_dictionary_layout(
            provider.get_subview("130").export_layouts[0],
            draft=_draft(),
            headers={},
            schema_provider=provider,
        )
