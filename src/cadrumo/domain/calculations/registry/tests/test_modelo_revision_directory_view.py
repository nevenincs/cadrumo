"""A selected modelo view resolves review references against its complete revision directory."""

from __future__ import annotations

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.tax_domain import TaxDomain
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..authority_artifact import AuthorityComponentQuery, ModeloDirectoryComponentQuery, ModeloRevisionComponentQuery
from ..errors import RegistryValidationError
from ..queries import PinnedRegistryQueryService, ResolvedRegistryQueryContext
from ..query_reports import ModeloListRow
from ..revision_contracts import DeclaredPredecessor
from ..schema import ModeloDefinition
from ..temporal import ModeloDirectoryMetadata, ModeloRevisionDirectory
from .authority_fakes import FakeAuthorityComponentReader
from .registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "038"
_SUCCESSOR = "2025-y-siguientes"
_PREDECESSOR = "2024-desde-06"


def _modelo(modelo_id: str = _MODELO) -> ModeloDefinition:
    modelos, _catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == modelo_id)


def test_a_view_keeps_revision_references_to_a_directory_revision_it_does_not_carry() -> None:
    modelo = _modelo()
    successor = modelo.revisions[_SUCCESSOR]
    assert successor.reviewed_against == _PREDECESSOR
    assert isinstance(successor.predecessor, DeclaredPredecessor)
    assert successor.predecessor.revision_id == _PREDECESSOR

    view = ModeloRevisionDirectory.from_modelo(modelo).materialize(successor)

    assert tuple(view.revisions) == (_SUCCESSOR,)
    assert view.revisions[_SUCCESSOR].reviewed_against == _PREDECESSOR
    assert view.revisions[_SUCCESSOR].predecessor == successor.predecessor


def test_a_view_stays_valid_inside_a_consumer_model_that_revalidates_it() -> None:
    modelo = _modelo()
    successor = modelo.revisions[_SUCCESSOR]
    view = ModeloRevisionDirectory.from_modelo(modelo).materialize(successor)

    context = ResolvedRegistryQueryContext(definition=view, revision=successor)

    assert tuple(context.definition.revisions) == (_SUCCESSOR,)
    assert context.definition.revisions[_SUCCESSOR].reviewed_against == _PREDECESSOR


def _pinned_service(modelo: ModeloDefinition) -> tuple[PinnedRegistryQueryService, FakeAuthorityComponentReader]:
    components: dict[AuthorityComponentQuery, object] = {
        ModeloDirectoryComponentQuery(_MODELO): ModeloRevisionDirectory.from_modelo(modelo),
    }
    for revision in modelo.revisions.values():
        components[ModeloRevisionComponentQuery(_MODELO, str(revision.id))] = revision
    reader = FakeAuthorityComponentReader(components)
    return PinnedRegistryQueryService(PinnedAuthorityOperation(reader, reader.pin())), reader


def test_a_directory_backed_listing_counts_and_filters_by_every_directory_revision() -> None:
    modelo = _modelo()
    assert set(modelo.revisions) == {_PREDECESSOR, _SUCCESSOR}
    assert modelo.revisions[_PREDECESSOR].period_selector.includes_year(2024)
    assert not modelo.revisions[_SUCCESSOR].period_selector.includes_year(2024)
    predecessor_query = ModeloRevisionComponentQuery(_MODELO, _PREDECESSOR)
    service, reader = _pinned_service(modelo)

    (view,) = service.iter_modelo_definitions()
    (row,) = service.list_modelos().modelos
    year_rows = service.list_modelos(year=2024).modelos

    assert tuple(view.revisions) == (_SUCCESSOR,)
    assert row.revision_count == 2
    assert tuple(year_row.code for year_row in year_rows) == (_MODELO,)
    assert predecessor_query not in reader.loads


def test_a_listing_decodes_no_revision_payload() -> None:
    service, reader = _pinned_service(_modelo())

    service.list_modelos()
    service.list_modelos(year=2024, domain=TaxDomain("iva"))

    assert reader.loads
    assert not [query for query in reader.loads if isinstance(query, ModeloRevisionComponentQuery)]


def _rows_from_full_decode(
    operation: PinnedAuthorityOperation,
    *,
    year: int | None = None,
    domain: TaxDomain | None = None,
) -> tuple[ModeloListRow, ...]:
    views = [
        (operation.modelo_directory(str(definition.id)), definition)
        for definition in PinnedRegistryQueryService(operation).iter_modelo_definitions()
    ]
    rows = [
        ModeloListRow(
            code=str(definition.id),
            title=definition.title,
            cadence=definition.cadence,
            tax_domain=definition.tax_domain,
            revision_count=len(directory.revisions),
        )
        for directory, definition in views
        if (year is None or any(metadata.period_selector.includes_year(year) for metadata in directory.revisions))
        and (domain is None or definition.tax_domain == domain)
    ]
    return tuple(sorted(rows, key=lambda row: row.code))


def test_the_published_listing_equals_the_listing_built_from_full_revision_views() -> None:
    with bundled_indexed_authority().operation() as operation:
        service = PinnedRegistryQueryService(operation)
        full = _rows_from_full_decode(operation)
        listed = service.list_modelos().modelos
        domain = TaxDomain("iva")
        assert service.list_modelos(year=2024, domain=domain).modelos == _rows_from_full_decode(
            operation, year=2024, domain=domain
        )

    assert len(full) > 1
    assert any(row.revision_count > 1 for row in full)
    assert listed == full
    assert [row.model_dump() for row in listed] == [row.model_dump() for row in full]


def test_a_directory_backed_support_matrix_reports_every_declared_revision() -> None:
    modelo = _modelo()
    assert modelo.revisions[_PREDECESSOR].valid_from < modelo.revisions[_SUCCESSOR].valid_from
    service, _reader = _pinned_service(modelo)

    (view,) = service.iter_modelo_definitions()
    (entry,) = service.support_matrix().entries

    assert tuple(view.revisions) == (_SUCCESSOR,)
    assert entry.latest_revision_id == _SUCCESSOR
    assert entry.supported_revision_ids == (_PREDECESSOR, _SUCCESSOR)
    assert entry.revision_count == 2


def test_a_published_snapshot_keeps_its_cross_revision_view_valid_when_nested() -> None:
    with bundled_indexed_authority().operation() as operation:
        directory_ids = {str(metadata.id) for metadata in operation.modelo_directory(_MODELO).revisions}
        snapshot = operation.snapshot(
            _MODELO,
            filing_year=2025,
            period="01",
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )

    assert {_PREDECESSOR, _SUCCESSOR} <= directory_ids
    assert tuple(snapshot.modelo.revisions) == (_SUCCESSOR,)
    selected = snapshot.modelo.revisions[_SUCCESSOR]
    assert selected.reviewed_against == _PREDECESSOR
    assert isinstance(selected.predecessor, DeclaredPredecessor)
    assert selected.predecessor.revision_id == _PREDECESSOR


def test_a_view_refuses_a_predecessor_its_directory_does_not_declare() -> None:
    modelo = _modelo()
    dangling = modelo.revisions[_SUCCESSOR].model_copy(
        update={"predecessor": DeclaredPredecessor(revision_id="2023"), "reviewed_against": None},
    )

    with pytest.raises(RegistryValidationError, match=r"declares predecessor '2023', which is not a revision"):
        ModeloRevisionDirectory.from_modelo(modelo).materialize(dangling)


def test_a_view_keeps_structural_succession_endpoints_resolved_by_its_directory() -> None:
    modelo = _modelo("100")
    target = next(revision for revision in modelo.revisions.values() if revision.casilla_structural_successions)
    directory = ModeloRevisionDirectory.from_modelo(modelo)

    view = directory.materialize(target)

    assert view.revisions[target.id].casilla_structural_successions == target.casilla_structural_successions
    relation = target.casilla_structural_successions[0].model_copy(update={"from_revision": "1999"})
    with pytest.raises(RegistryValidationError, match=r"unknown endpoint revision"):
        directory.materialize(target.model_copy(update={"casilla_structural_successions": (relation,)}))


def test_a_view_refuses_a_review_reference_its_directory_does_not_declare() -> None:
    modelo = _modelo()
    dangling = modelo.revisions[_SUCCESSOR].model_copy(update={"reviewed_against": "2023"})

    with pytest.raises(RegistryValidationError, match=r"dangling review reference reviewed_against='2023'"):
        ModeloRevisionDirectory.from_modelo(modelo).materialize(dangling)


def test_a_view_refuses_a_revision_its_directory_does_not_declare() -> None:
    modelo = _modelo()
    foreign = modelo.revisions[_SUCCESSOR].model_copy(update={"id": "2030"})

    with pytest.raises(RegistryValidationError, match=r"view revisions \['2030'\] are not revisions of its directory"):
        ModeloRevisionDirectory.from_modelo(modelo).materialize(foreign)


def test_a_complete_modelo_missing_the_reviewed_revision_is_refused() -> None:
    modelo = _modelo()
    successor = modelo.revisions[_SUCCESSOR]

    with pytest.raises(RegistryValidationError, match=r"dangling review reference reviewed_against='2024-desde-06'"):
        ModeloDefinition(
            **ModeloDirectoryMetadata.from_modelo(modelo).model_dump(),
            revisions={successor.id: successor},
        )


def test_a_complete_modelo_missing_the_named_predecessor_is_refused() -> None:
    modelo = _modelo()
    successor = modelo.revisions[_SUCCESSOR].model_copy(update={"reviewed_against": None})

    with pytest.raises(RegistryValidationError, match=r"declares predecessor '2024-desde-06', which is not a revision"):
        ModeloDefinition(
            **ModeloDirectoryMetadata.from_modelo(modelo).model_dump(),
            revisions={successor.id: successor},
        )
