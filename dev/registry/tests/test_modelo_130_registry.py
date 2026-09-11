"""Compiler mutation coverage for Modelo 130's construct classifications."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.authority import compile_registry_tree
from ..compiler.validator import RegistryValidator


def test_validator_rejects_missing_relationless_direct_settlement_classification() -> None:
    """The direct same-modelo carries cannot lose their declared settlement treatment."""
    modelos, catalogues = compile_registry_tree(bundled_path("registry", "aeat"), bundled_path())
    modelo = next(item for item in modelos if item.id == "130")
    revision = modelo.revisions["2019-y-siguientes"]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "130")
    construct = next(item for item in revision.constructs if classification.id in item.dependency_classifications)
    mutated_construct = construct.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in construct.dependency_classifications if item != classification.id
            )
        }
    )
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in revision.dependency_classifications if item.id != classification.id
            ),
            "constructs": tuple(item if item.id != construct.id else mutated_construct for item in revision.constructs),
        }
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: mutated_revision}})

    with pytest.raises(
        RegistryValidationError,
        match=r"previous_filing source modelo '130' has no dependency classification",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)
