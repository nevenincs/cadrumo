"""A selected modelo view resolves review references against its complete revision directory."""

from __future__ import annotations

import pytest

from ..errors import RegistryValidationError
from ..queries import ResolvedRegistryQueryContext
from ..revision_contracts import DeclaredPredecessor
from ..schema import ModeloDefinition
from ..temporal import ModeloDirectoryMetadata, ModeloRevisionDirectory
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
