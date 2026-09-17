"""Historical continuity evidence keeps its endpoint-specific source context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import override

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.resources.bundled_data import bundled_path

from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..authority_artifact import (
    AuthorityComponentCodecError,
    AuthorityComponentKind,
    AuthorityComponentQuery,
    AuthorityGenerationPin,
    ExportLayoutComponentQuery,
    GovernedFactComponentQuery,
    ModeloDirectoryComponentQuery,
    ModeloRevisionComponentQuery,
    ReferenceComponentQuery,
    SnapshotGlobalsComponentQuery,
    decode_authority_component,
    encode_authority_component,
)
from ..errors import RegistryValidationError
from ..governed_fact_scope import validating_governed_facts
from ..schema import ModeloDefinition, RegistryCatalogues, SnapshotGlobalCatalogues
from ..snapshot import _revision_scoped_source_window_failures, collect_snapshot_ref_ids
from ..temporal import ModeloRevisionDirectory
from .authority_fakes import FakeAuthorityComponentReader
from .registry_tree import bundled_registry_tree
from .snapshot_support import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_and_catalogues(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == modelo_id), catalogues


@pytest.mark.parametrize(
    ("modelo_id", "filing_year", "period", "revision_id", "historical_source"),
    [
        ("322", 2023, "01", "2023", "aeat-dr-322-2022"),
        ("308", 2019, "AD-HOC", "2019-y-siguientes", "aeat-dr-308-2009"),
    ],
)
def test_real_historical_continuity_sources_are_carried_from_their_valid_endpoints(
    modelo_id: str,
    filing_year: int,
    period: str,
    revision_id: str,
    historical_source: str,
) -> None:
    modelo, catalogues = _modelo_and_catalogues(modelo_id)
    if catalogues.supported_filing_years is not None and filing_year < catalogues.supported_filing_years.floor:
        catalogues = catalogues.model_copy(update={"supported_filing_years": None})

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )

    assert snapshot.revision.id == revision_id
    assert historical_source in snapshot.sources


def test_a_historical_source_reused_by_a_current_casilla_keeps_the_revision_window_check() -> None:
    modelo, catalogues = _modelo_and_catalogues("322")
    revision = modelo.revisions["2023"]
    historical_source = "aeat-dr-322-2022"
    assert historical_source not in modelo.source_refs
    assert all(historical_source not in casilla.source_refs for casilla in revision.casillas)
    changed_casilla = revision.casillas[0].model_copy(
        update={"source_refs": (*revision.casillas[0].source_refs, historical_source)},
    )
    changed_revision = revision.model_copy(update={"casillas": (changed_casilla, *revision.casillas[1:])})
    changed_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: changed_revision}},
    )

    with pytest.raises(RegistryValidationError, match=historical_source):
        build_snapshot(
            changed_modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2023,
            period="01",
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )


@pytest.mark.parametrize("defect", ["unknown-source", "unrelated-source", "unknown-endpoint"])
def test_historical_evolution_sources_must_match_a_real_declared_endpoint(defect: str) -> None:
    modelo, catalogues = _modelo_and_catalogues("322")
    revision = modelo.revisions["2023"]
    evolution = revision.casilla_continuidad_evolutions[0]
    if defect == "unknown-source":
        evolution = evolution.model_copy(update={"source_refs": ("missing-source",)})
    elif defect == "unrelated-source":
        unrelated = "aeat-dr-390-2021"
        assert unrelated in catalogues.sources
        evolution = evolution.model_copy(update={"source_refs": (unrelated,)})
    else:
        evolution = evolution.model_copy(update={"from_revision": "missing-revision"})
    changed_revision = revision.model_copy(update={"casilla_continuidad_evolutions": (evolution,)})
    changed_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: changed_revision}},
    )

    failures = _revision_scoped_source_window_failures(changed_modelo, changed_revision, catalogues)

    assert failures
    assert any(evolution.id in failure for failure in failures)


def test_structural_endpoint_sources_cannot_be_reversed() -> None:
    modelo, catalogues = _modelo_and_catalogues("309")
    revision = modelo.revisions["2016-2017"]
    reversed_relations = tuple(
        relation.model_copy(
            update={
                "from_source_refs": relation.to_source_refs,
                "to_source_refs": relation.from_source_refs,
            }
        )
        for relation in revision.casilla_structural_successions
    )
    changed_revision = revision.model_copy(update={"casilla_structural_successions": reversed_relations})
    changed_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: changed_revision}},
    )

    failures = _revision_scoped_source_window_failures(changed_modelo, changed_revision, catalogues)

    assert sum("validity window" in failure for failure in failures) == 6


def test_structural_succession_grounding_is_available_in_the_snapshot() -> None:
    modelo, catalogues = _modelo_and_catalogues("309")
    catalogues = catalogues.model_copy(update={"supported_filing_years": None})

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2016,
        period="AD-HOC",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )

    relation = snapshot.revision.casilla_structural_successions[0]
    assert set(relation.legal_refs) <= set(snapshot.legal)
    assert set((*relation.from_source_refs, *relation.to_source_refs)) <= set(snapshot.sources)


def test_directory_component_round_trip_preserves_complete_endpoint_source_enrollment() -> None:
    modelo, catalogues = _modelo_and_catalogues("322")
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=catalogues.supported_filing_years)
    query = ModeloDirectoryComponentQuery(modelo.id)

    decoded = decode_authority_component(query, encode_authority_component(query, directory))

    assert decoded == directory
    assert isinstance(decoded, ModeloRevisionDirectory)
    assert decoded.endpoint_source_ids("2008-2022")
    assert decoded.endpoint_source_ids("2023")


def test_directory_component_without_endpoint_source_enrollment_is_refused() -> None:
    modelo, catalogues = _modelo_and_catalogues("322")
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=catalogues.supported_filing_years)
    query = ModeloDirectoryComponentQuery(modelo.id)
    frame = json.loads(encode_authority_component(query, directory))
    del frame["payload"]["endpoint_source_enrollments"]

    with pytest.raises(AuthorityComponentCodecError, match="failed typed decoding"):
        decode_authority_component(query, canonical_json_bytes(frame))


def test_directory_endpoint_source_enrollment_requires_each_revision_exactly_once() -> None:
    modelo, catalogues = _modelo_and_catalogues("322")
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=catalogues.supported_filing_years)
    document = directory.model_dump(mode="python")
    document["endpoint_source_enrollments"] = directory.endpoint_source_enrollments[:-1]

    with pytest.raises(ValueError, match="cover every revision exactly once"):
        ModeloRevisionDirectory.model_validate(document)


def test_directory_refuses_duplicate_revision_metadata_even_with_one_matching_enrollment() -> None:
    modelo, catalogues = _modelo_and_catalogues("322")
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=catalogues.supported_filing_years)
    document = directory.model_dump(mode="python")
    document["revisions"] = (directory.revisions[0], directory.revisions[0])
    document["endpoint_source_enrollments"] = (directory.endpoint_source_enrollments[0],)

    with pytest.raises(ValueError, match="unique revision ids"):
        ModeloRevisionDirectory.model_validate(document)


@dataclass(slots=True)
class _PublishedFactReader(FakeAuthorityComponentReader):
    """Serve governed facts from the published generation; every other component stays fixture-owned."""

    published: PinnedAuthorityOperation | None = None

    @override
    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        if isinstance(query, GovernedFactComponentQuery) and query not in self.components:
            assert self.published is not None
            self.components[query] = self.published.governed_fact(query.fact_id)
        return FakeAuthorityComponentReader.load(self, query, pin=pin)


def test_indexed_snapshot_uses_directory_endpoint_context_without_loading_prior_revision() -> None:
    modelo, catalogues = _modelo_and_catalogues("322")
    revision = modelo.revisions["2023"]
    prior_revision = modelo.revisions["2008-2022"]
    directory = ModeloRevisionDirectory.from_modelo(modelo, support=catalogues.supported_filing_years)
    directory_query = ModeloDirectoryComponentQuery(modelo.id)
    revision_query = ModeloRevisionComponentQuery(modelo.id, str(revision.id))
    prior_query = ModeloRevisionComponentQuery(modelo.id, str(prior_revision.id))
    components: dict[AuthorityComponentQuery, object] = {
        directory_query: directory,
        revision_query: revision.model_copy(update={"export_layouts": ()}),
        prior_query: prior_revision,
        SnapshotGlobalsComponentQuery(): SnapshotGlobalCatalogues.from_catalogues(catalogues),
    }
    for layout in revision.export_layouts:
        components[ExportLayoutComponentQuery(modelo.id, str(revision.id), layout.id)] = layout
    legal_ids, source_ids = collect_snapshot_ref_ids(modelo, revision)
    for reference_id in legal_ids:
        components[ReferenceComponentQuery(reference_id, AuthorityComponentKind.LEGAL_REFERENCE)] = catalogues.legal[
            reference_id
        ]
    for reference_id in source_ids:
        components[ReferenceComponentQuery(reference_id, AuthorityComponentKind.SOURCE_REFERENCE)] = catalogues.sources[
            reference_id
        ]
    with bundled_indexed_authority().operation() as published:
        reader = _PublishedFactReader(components, published=published)
        operation = PinnedAuthorityOperation(reader, reader.pin())

        with validating_governed_facts(operation):
            snapshot = operation.snapshot(
                modelo.id,
                filing_year=2023,
                period="01",
                grade=RegistryAuthorityGrade.APPLICABILITY,
            )

    assert snapshot.revision.id == revision.id
    assert "aeat-dr-322-2022" in snapshot.sources
    assert revision_query in reader.loads
    assert prior_query not in reader.loads
