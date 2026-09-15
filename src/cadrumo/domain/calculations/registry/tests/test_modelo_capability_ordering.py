"""Declared modelo capabilities serialise in a process-independent order.

A set-shaped container orders its members by hash, which varies with the
interpreter's hash seed, so the same manifest produced a different capability
order -- and therefore a different serialisation and digest -- from one process
to the next. The declaration is stored sorted, which makes the authored order
irrelevant to the stored value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.classification.policies import SensitivityClass
from .....core.hashing import canonical_json_bytes
from .....core.tax_domain import TaxDomain
from ..schema import ModeloDefinition, ModeloRevision
from ._artifact_runtime_support import _LEGAL_ID, _SOURCE_ID, _minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_with(*capabilities: str, revision: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition.model_validate(
        {
            "id": "100",
            "title_localization_key": "test.schema.modelo.100.title",
            "official_name_localization_key": "test.schema.modelo.100.official_name",
            "tax_domain": TaxDomain("irpf"),
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "output_sensitivity": SensitivityClass.FINANCIAL,
            "capabilities": capabilities,
            "legal_refs": (_LEGAL_ID,),
            "source_refs": (_SOURCE_ID,),
            "revisions": {revision.id: revision},
        }
    )


def test_declared_order_does_not_reach_the_stored_capabilities() -> None:
    """Both authored orders hydrate into the same sorted tuple."""
    revision = _minimal_revision()
    forward = _modelo_with("borrador", "renta_ledger_default", revision=revision)
    reversed_declaration = _modelo_with("renta_ledger_default", "borrador", revision=revision)

    assert forward.capabilities == ("borrador", "renta_ledger_default")
    assert reversed_declaration.capabilities == forward.capabilities
    assert forward.has_capability("borrador")
    assert reversed_declaration.has_capability("renta_ledger_default")
    assert forward == reversed_declaration


def test_both_declaration_orders_serialise_and_digest_identically() -> None:
    """Serialisation, JSON dump, and canonical digest bytes all agree."""
    revision = _minimal_revision()
    forward = _modelo_with("borrador", "renta_ledger_default", revision=revision)
    reversed_declaration = _modelo_with("renta_ledger_default", "borrador", revision=revision)

    assert forward.model_dump()["capabilities"] == reversed_declaration.model_dump()["capabilities"]
    assert forward.model_dump_json() == reversed_declaration.model_dump_json()
    assert canonical_json_bytes(forward.model_dump(mode="json")) == canonical_json_bytes(
        reversed_declaration.model_dump(mode="json")
    )


def test_an_undeclared_capability_set_stays_empty_and_omittable() -> None:
    """The default is a declared-nothing tuple, not a hash-ordered empty set."""
    modelo = _modelo_with(revision=_minimal_revision())

    assert modelo.capabilities == ()
    assert "capabilities" not in modelo.model_dump(exclude_defaults=True)


def test_a_repeated_capability_is_refused_rather_than_silently_collapsed() -> None:
    """A duplicate declaration is an authoring defect, not a deduplication job."""
    with pytest.raises(ValidationError, match="at most once"):
        _modelo_with("borrador", "borrador", revision=_minimal_revision())


def test_an_unknown_capability_token_is_still_refused() -> None:
    with pytest.raises(ValidationError):
        _modelo_with("borrador", "not_a_capability", revision=_minimal_revision())
