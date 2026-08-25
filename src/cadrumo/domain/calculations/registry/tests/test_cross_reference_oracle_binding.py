"""Tests for the optional ``oracle_id`` binding on ``LiveCrossReferenceDecision``.

The field lets a modelo cross-reference declare which oracle adapter (by
catalogue id) services its surface. The schema accepts the field as
optional, the field validator enforces a kebab-case ASCII identifier
shape, and the registry validator rejects two cross-references on the
same revision binding to the same oracle id.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .. import RegistryValidationError
from ..schema import LiveCrossReferenceDecision, ModeloDefinition, ModeloRevision
from ..validate import RegistryValidator
from ._registry_schema_support import _committed_modelo, _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_cross_reference() -> LiveCrossReferenceDecision:
    """Return a real cross-reference from the committed Modelo 130 registry."""

    modelo, _ = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    return revision.live_cross_references[0]


def test_cross_reference_without_oracle_id_round_trips() -> None:
    cross_reference = _committed_cross_reference()

    assert cross_reference.oracle_id is None
    rebuilt = LiveCrossReferenceDecision.model_validate(cross_reference.model_dump())
    assert rebuilt.oracle_id is None


def test_cross_reference_with_valid_oracle_id_round_trips() -> None:
    base = _committed_cross_reference()
    cross_reference = base.model_copy(update={"oracle_id": "aeat-nif-iva-checker"})

    assert cross_reference.oracle_id == "aeat-nif-iva-checker"
    rebuilt = LiveCrossReferenceDecision.model_validate(cross_reference.model_dump())
    assert rebuilt.oracle_id == "aeat-nif-iva-checker"


def test_cross_reference_rejects_empty_oracle_id() -> None:
    base = _committed_cross_reference()
    payload = base.model_dump()
    payload["oracle_id"] = ""

    with pytest.raises(ValidationError, match=r"oracle_id|at least 1 character"):
        LiveCrossReferenceDecision.model_validate(payload)


@pytest.mark.parametrize(
    "bad_id",
    [
        "Aeat-Nif-Iva",  # uppercase letters
        "1-leading-digit",  # leading digit
        "trailing-hyphen-",  # trailing hyphen
        "snake_case_id",  # underscore not allowed
        "with space",  # space not allowed
    ],
)
def test_cross_reference_rejects_malformed_oracle_id(bad_id: str) -> None:
    base = _committed_cross_reference()
    payload = base.model_dump()
    payload["oracle_id"] = bad_id

    with pytest.raises(ValidationError, match=r"oracle_id|pattern|String should match"):
        LiveCrossReferenceDecision.model_validate(payload)


def _revision_with_cross_references(
    revision: ModeloRevision,
    cross_references: tuple[LiveCrossReferenceDecision, ...],
) -> ModeloRevision:
    return revision.model_copy(update={"live_cross_references": cross_references})


def _modelo_with_revision(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def test_registry_rejects_duplicate_oracle_binding_within_a_revision() -> None:
    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    base_xref = revision.live_cross_references[0]

    twin_a = base_xref.model_copy(update={"id": "modelo-130-static-official", "oracle_id": "aeat-nif-iva-checker"})
    twin_b = base_xref.model_copy(
        update={"id": "modelo-130-filed-declarations-read", "oracle_id": "aeat-nif-iva-checker"},
    )
    duplicate_revision = _revision_with_cross_references(revision, (twin_a, twin_b))
    duplicate_modelo = _modelo_with_revision(modelo, duplicate_revision)

    validator = RegistryValidator(catalogues, source_root=bundled_path())
    with pytest.raises(RegistryValidationError, match="aeat-nif-iva-checker"):
        validator.validate_modelo(duplicate_modelo)


def test_registry_accepts_distinct_oracle_bindings_within_a_revision() -> None:
    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    base_xref = revision.live_cross_references[0]

    twin_a = base_xref.model_copy(update={"id": "modelo-130-static-official", "oracle_id": "aeat-nif-iva-checker"})
    twin_b = base_xref.model_copy(
        update={
            "id": "modelo-130-filed-declarations-read",
            "oracle_id": "modelo-100-renta-web-open",
        },
    )
    distinct_revision = _revision_with_cross_references(revision, (twin_a, twin_b))
    distinct_modelo = _modelo_with_revision(modelo, distinct_revision)

    assert {xref.oracle_id for xref in distinct_revision.live_cross_references} >= {
        "aeat-nif-iva-checker",
        "modelo-100-renta-web-open",
    }, "distinct revision must carry both oracle bindings"

    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validator.validate_modelo(distinct_modelo)


def test_registry_accepts_no_oracle_binding_anywhere() -> None:
    """The committed registry has no oracle bindings yet; it must still validate."""

    modelos, catalogues = _committed_registry_tree()
    assert len(modelos) >= 5, "committed registry must declare a meaningful number of modelos"
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validated = 0
    for modelo in modelos:
        validator.validate_modelo(modelo)
        validated += 1
    assert validated == len(modelos), "every modelo must be validated"
