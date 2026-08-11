"""Anti-legacy proof for the canonical filing producer boundary."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from ....core import FilingProducerKey
from ....domain.calculations import registry
from ....domain.calculations.registry import ExportComputedKey, ExportDraftAttribute
from ...modelo import _export as modelo_export_module
from .. import _export as export_module
from .. import export_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _resolver_enum_keys() -> set[FilingProducerKey]:
    source = Path("src/cadrumo/application/filing/_export.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    resolver = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_filing_producer_values"
    )
    members: set[FilingProducerKey] = set()
    for node in ast.walk(resolver):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "FilingProducerKey"
        ):
            members.add(FilingProducerKey[node.attr])
    return members


def test_snapshot_resolver_is_exhaustive_over_the_core_producer_vocabulary() -> None:
    assert _resolver_enum_keys() == set(FilingProducerKey)


def test_legacy_header_surfaces_are_deleted_instead_of_normalised() -> None:
    assert not hasattr(registry, "ExportHeaderKey")
    assert not hasattr(export_module, "_normalise_export_headers")
    assert not hasattr(modelo_export_module, "compose_export_headers")
    assert "headers" not in inspect.signature(export_draft).parameters
    assert "producer_snapshot" in inspect.signature(export_draft).parameters


@pytest.mark.parametrize(
    "legacy_token",
    (
        "presenter_nif",
        "presenter_tax_id",
        "complementaria",
        "previous_receipt",
        "name",
        "program_version",
        "aeat_seal",
    ),
)
def test_historical_header_spellings_are_not_enum_members_or_values(legacy_token: str) -> None:
    assert legacy_token not in FilingProducerKey.__members__
    assert legacy_token not in {member.value for member in FilingProducerKey}
    with pytest.raises(ValueError):
        FilingProducerKey(legacy_token)


def test_draft_vocabulary_has_no_profile_or_taxpayer_identity_fallback() -> None:
    assert set(export_module._DRAFT_VALUE_PRODUCERS) == set(ExportDraftAttribute)
    assert set(export_module._COMPUTED_VALUE_PRODUCERS) == set(ExportComputedKey)
    assert "profile_tax_id" not in {member.value for member in ExportDraftAttribute}
