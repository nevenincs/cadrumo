"""Runtime authority behavior at the published-artifact boundary."""

from __future__ import annotations

import dataclasses
from collections.abc import MutableMapping
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePath
from typing import cast

import pytest
from pydantic import BaseModel

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.frozen_mapping import FrozenMapping
from .....core.hashing import sha256_hex
from .. import authority as authority_module
from ..authority import bundled_authority, bundled_authority_artifact_path, published_authority
from ..authority_artifact import (
    AuthorityArtifact,
    AuthorityArtifactIntegrityError,
    AuthorityArtifactUnavailableError,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    read_authority_artifact,
    write_authority_artifact,
)
from ..corpus_provenance import NormativeCorpusProvenance
from ..facts.schema import GovernedFactCatalogue
from ._referential_integrity_support import _minimal_catalogues, _minimal_modelo, _minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IDENTITY_DIGEST = "e4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f"
_REPUBLISHED_IDENTITY_DIGEST = "5d41402abc4b2a76b9719d911017c592ae2d6c3f4b1b1c0e6a2d7f0f3e8a9b10"
_IMMUTABLE_SCALARS = (str, bytes, int, float, bool, type(None), Decimal, date, Enum, PurePath)


class _UnfrozenModel(BaseModel):
    """A model that would let a holder rebind its fields."""

    value: int


def _publication(*, identity_digest: str) -> AuthorityArtifact:
    """Build a real typed authority payload without requiring the authoring corpus."""
    return AuthorityArtifact(
        modelos=(_minimal_modelo(_minimal_revision()),),
        catalogues=_minimal_catalogues(),
        identity_digest=identity_digest,
    )


def _stage_runtime_publication(root: Path) -> Path:
    """Create a package-shaped publication without authoring inputs."""
    publication = root / "registry" / "authority"
    publication.mkdir(parents=True)
    artifact_path = publication / "authority.json"
    write_authority_artifact(artifact_path, _publication(identity_digest=_IDENTITY_DIGEST))
    return artifact_path


def _mutable_containers(root: object) -> list[str]:
    """Return the path of every value reachable from ``root`` that a holder could mutate.

    Anything not positively known to be immutable is reported, so a new
    container type fails the walk until it is shown to be safe to share.
    """
    findings: list[str] = []
    seen: set[int] = set()
    pending: list[tuple[object, str]] = [(root, "root")]
    while pending:
        value, where = pending.pop()
        if isinstance(value, _IMMUTABLE_SCALARS) or id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, BaseModel):
            model_type = type(value)
            if not model_type.model_config.get("frozen"):
                findings.append(f"{where}: model {model_type.__name__} is not frozen")
            if value.__pydantic_private__ or value.__pydantic_extra__:
                findings.append(f"{where}: model {model_type.__name__} carries private or extra state")
            undeclared = set(vars(value)) - set(model_type.model_fields)
            if undeclared:
                findings.append(f"{where}: model {model_type.__name__} caches {sorted(undeclared)}")
            pending.extend((getattr(value, name), f"{where}.{name}") for name in model_type.model_fields)
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            parameters = getattr(type(value), "__dataclass_params__", None)
            if parameters is None or not parameters.frozen:
                findings.append(f"{where}: dataclass {type(value).__name__} is not frozen")
            pending.extend((getattr(value, item.name), f"{where}.{item.name}") for item in dataclasses.fields(value))
        elif isinstance(value, FrozenMapping):
            for key, item in value.items():
                pending.append((key, f"{where}[key {key!r}]"))
                pending.append((item, f"{where}[{key!r}]"))
        elif isinstance(value, (tuple, frozenset)):
            pending.extend((item, f"{where}[{index}]") for index, item in enumerate(value))
        else:
            findings.append(f"{where}: {type(value).__name__}")
    return sorted(findings)


def _use_staged_package(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Point the real package-resource seam at an isolated staged package."""
    bundled_data_root = authority_module._bundled_path()

    def staged_path(*parts: str) -> Path:
        if parts[:2] == ("registry", "authority"):
            return root.joinpath(*parts)
        return bundled_data_root.joinpath(*parts)

    monkeypatch.setattr(authority_module, "_bundled_path", staged_path)


def test_the_committed_bundled_artifact_loads_and_reads_back_canonically(tmp_path: Path) -> None:
    """The package's own artifact is the runtime authority, and it re-encodes to its exact bytes.

    Read through the real package resource with no staged seam: a product process
    loads it, and a re-publication of what was read is byte-identical, so the
    committed file is a canonical encoding of the authority it decodes to.
    """
    artifact_path = bundled_authority_artifact_path()
    authority = bundled_authority()
    consumed = read_authority_artifact(artifact_path)
    republished = tmp_path / "authority.json"

    write_authority_artifact(republished, consumed)

    assert authority.modelos, "the bundled artifact must carry the registry's modelos"
    assert {modelo.id for modelo in authority.modelos} == {modelo.id for modelo in consumed.modelos}
    assert authority.catalogues == consumed.catalogues
    assert republished.read_bytes() == artifact_path.read_bytes()


def test_runtime_uses_a_published_artifact_and_isolates_later_consumers(tmp_path: Path) -> None:
    """A product authority snapshots a published model without its source tree, and no consumer reaches another's."""
    artifact_path = _stage_runtime_publication(tmp_path)

    first = published_authority(artifact_path)
    snapshot = first.snapshot("130", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY)
    capture = first.capture_law_selected_projection(
        "130",
        filing_year=2025,
        period="0A",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", first.catalogues.legal)["consumer-injected"] = object()
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", first.modelos[0].revisions)["consumer-injected"] = object()
    first.source_root = tmp_path / "consumer-chosen-root"

    later = published_authority(artifact_path)

    assert snapshot.modelo.id == "130"
    assert capture.projection.modelo.id == "130"
    capture.require_current(first.read_current_coordinate())
    assert "consumer-injected" not in later.catalogues.legal
    assert "consumer-injected" not in later.modelos[0].revisions
    assert later is not first
    assert later.source_root != first.source_root


def test_a_republished_artifact_is_decoded_afresh_rather_than_served_stale(tmp_path: Path) -> None:
    """Both an atomic republication and an in-place rewrite of the file reach the next authority."""
    artifact_path = _stage_runtime_publication(tmp_path)
    assert published_authority(artifact_path)._identity_digest == _IDENTITY_DIGEST

    write_authority_artifact(artifact_path, _publication(identity_digest=_REPUBLISHED_IDENTITY_DIGEST))
    atomically_republished = published_authority(artifact_path)

    staging = tmp_path / "staging.json"
    write_authority_artifact(staging, _publication(identity_digest=_IDENTITY_DIGEST))
    artifact_path.write_bytes(staging.read_bytes())
    rewritten_in_place = published_authority(artifact_path)

    assert atomically_republished._identity_digest == _REPUBLISHED_IDENTITY_DIGEST
    assert rewritten_in_place._identity_digest == _IDENTITY_DIGEST


def test_a_corrupt_artifact_is_refused_on_every_call_even_after_a_good_read(tmp_path: Path) -> None:
    """A valid read is never a licence to serve the file once it stops verifying."""
    artifact_path = _stage_runtime_publication(tmp_path)
    published_authority(artifact_path)
    artifact_path.write_bytes(artifact_path.read_bytes().replace(_IDENTITY_DIGEST.encode(), b"0" * 64, 1))

    for _ in range(2):
        with pytest.raises(AuthorityArtifactIntegrityError):
            published_authority(artifact_path)


def test_the_bundled_authority_graph_is_deeply_immutable() -> None:
    """Every container reachable from the shared bundled graph is immutable, so sharing it cannot leak mutation."""
    authority = bundled_authority()

    assert _mutable_containers((authority.modelos, authority.catalogues, authority.evidence)) == []


def test_the_immutability_walk_reports_each_kind_of_mutable_container() -> None:
    """The walk that guards sharing detects a plain dict, a list, a set, and a model that is not frozen."""
    unvalidated_catalogue = GovernedFactCatalogue.model_construct(facts={})

    findings = _mutable_containers(
        (unvalidated_catalogue, [1], {2}, _UnfrozenModel(value=1), FrozenMapping({"key": [3]}))
    )

    assert findings == [
        "root[0].facts: dict",
        "root[1]: list",
        "root[2]: set",
        "root[3]: model _UnfrozenModel is not frozen",
        "root[4]['key']: list",
    ]


def test_runtime_answers_a_citation_from_published_evidence_without_a_corpus_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runtime evidence API reads the artifact projection, not package corpus files."""
    artifact_path = _stage_runtime_publication(tmp_path)
    citation_text = "validated published provision"
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(_minimal_modelo(_minimal_revision()),),
            catalogues=_minimal_catalogues(),
            identity_digest=_IDENTITY_DIGEST,
            evidence=AuthorityEvidenceProjection(
                legal=(
                    PublishedLegalEvidence(
                        legal_reference_id="test:art-1",
                        anchored_text=citation_text,
                        text_sha256=sha256_hex(citation_text.encode("utf-8")),
                    ),
                )
            ),
        ),
    )
    _use_staged_package(monkeypatch, tmp_path)

    authority = bundled_authority()
    authority.source_root = tmp_path / "absent-corpus"

    assert authority.legal_quotation_is_grounded("test:art-1", "published provision")


def test_runtime_keeps_real_bundled_citation_inspection_after_artifact_loading(tmp_path: Path) -> None:
    """The artifact authority retains its package data root for real citation inspection."""
    catalogues = _minimal_catalogues()
    legal_id = next(iter(catalogues.legal))
    cited = catalogues.legal[legal_id].model_copy(
        update={"corpus_ref": "corpus/normatives/html/ley-35-2006-art-85.html#a85"}
    )
    artifact_path = tmp_path / "authority.json"
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(_minimal_modelo(_minimal_revision()),),
            catalogues=catalogues.model_copy(update={"legal": {**catalogues.legal, legal_id: cited}}),
            identity_digest=_IDENTITY_DIGEST,
        ),
    )
    authority = published_authority(artifact_path)

    provenance = authority.legal_corpus_provenance(legal_id)

    assert provenance is NormativeCorpusProvenance.BOE_ATTESTED


def test_missing_publication_refuses_before_any_authoring_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absent runtime artifact fails even when a malformed authoring tree is nearby."""
    malformed_authoring_tree = tmp_path / "registry" / "aeat"
    malformed_authoring_tree.mkdir(parents=True)
    (malformed_authoring_tree / "catalogue.toml").write_text("this is not valid registry input", encoding="utf-8")
    _use_staged_package(monkeypatch, tmp_path)

    with pytest.raises(AuthorityArtifactUnavailableError):
        bundled_authority()


def test_corrupt_publication_refuses_before_any_authoring_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tampering is refused at the artifact boundary, not repaired from nearby sources."""
    artifact_path = _stage_runtime_publication(tmp_path)
    artifact_path.write_bytes(artifact_path.read_bytes().replace(_IDENTITY_DIGEST.encode(), b"0" * 64, 1))
    malformed_authoring_tree = tmp_path / "registry" / "aeat"
    malformed_authoring_tree.mkdir(parents=True)
    (malformed_authoring_tree / "catalogue.toml").write_text("this is not valid registry input", encoding="utf-8")
    _use_staged_package(monkeypatch, tmp_path)

    with pytest.raises(AuthorityArtifactIntegrityError):
        bundled_authority()
