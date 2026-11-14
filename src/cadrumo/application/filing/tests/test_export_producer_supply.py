"""An export whose layout cites a producer nothing supplies refuses, naming every missing fact.

The header producers resolve exactly the keys the shared snapshot owns, so the
headers each case hands the guard are that set, as the export builds them. The
expected missing keys are read from the published Modelo 840 export layout's own
source, apart from the guard under test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ....core.filing_producer_key import FilingProducerKey
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.export_shared_owner import canonical_export_layout
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.filing.errors import FilingExportValidationError
from ..export_producer import SHARED_SNAPSHOT_PRODUCER_KEYS
from ..export_producer_supply import require_supplied_producers, unsupplied_producer_keys
from ..producer_ownership import filing_producer_ownership

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELOS = Path(__file__).resolve().parents[3] / "_data" / "registry" / "aeat" / "modelos"
_PRODUCER_KEY = re.compile(r"""producer_key\s*=\s*['"]([^'"]+)['"]""")


def _headers() -> dict[FilingProducerKey, object]:
    """The keys the header producers resolve: exactly those the shared snapshot owns."""
    ownership = filing_producer_ownership(shared_snapshot_keys=SHARED_SNAPSHOT_PRODUCER_KEYS)
    return {key: None for key, owner in ownership.items() if owner == "shared_snapshot"}


def _layout(operation: PinnedAuthorityOperation, modelo: str, period: str) -> ExportLayoutDefinition:
    """The published export layout of the newest supported year, at the grade its revision reaches."""
    year = filing_year_envelope().years[-1]
    grade = operation.reachable_authority_grade(modelo, filing_year=year, period=period)
    snapshot = operation.snapshot(modelo, filing_year=year, period=period, grade=grade)
    layout = canonical_export_layout(snapshot.revision.export_layouts)
    if layout is None or not layout.records:
        pytest.fail(f"modelo {modelo} publishes no export layout with records")
    return layout


def _cited_outside_the_headers(modelo: str) -> set[str]:
    cited: set[str] = {
        str(key)
        for layout in _MODELOS.glob(f"{modelo}/revisions/*/export/*.toml")
        for key in _PRODUCER_KEY.findall(layout.read_text(encoding="utf-8"))
    }
    supplied = {key.value for key in _headers()}
    return cited - supplied


def test_a_layout_citing_producers_nothing_supplies_refuses_naming_each_one(
    operation: PinnedAuthorityOperation,
) -> None:
    layout, headers = _layout(operation, "840", "0A"), _headers()
    expected = _cited_outside_the_headers("840")

    missing = unsupplied_producer_keys(layout, headers)
    with pytest.raises(FilingExportValidationError) as refusal:
        require_supplied_producers(layout, headers, modelo="840")

    assert expected, "the Modelo 840 layout no longer cites an unsupplied producer, so this proves nothing"
    assert {key.value for key in missing} == expected
    assert refusal.value.translated_message == "application.filing.export.errors.producer_facts_unsupplied"
    context = refusal.value.context or {}
    facts = str(context["facts"])
    assert all(key in facts for key in expected)
    sentence = tr(refusal.value.translated_message, locale="en", modelo="840", facts=facts)
    assert "%{" not in sentence and "840" in sentence


def test_a_layout_whose_producers_are_all_supplied_passes(operation: PinnedAuthorityOperation) -> None:
    layout, headers = _layout(operation, "130", "4T"), _headers()

    assert not _cited_outside_the_headers("130")
    assert unsupplied_producer_keys(layout, headers) == ()
    require_supplied_producers(layout, headers, modelo="130")
