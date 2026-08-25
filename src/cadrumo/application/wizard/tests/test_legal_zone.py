"""Flow legal-zone projection over the real schema and validated registry.

The projection is exercised against the real singleton profile schema and
the real bundled :class:`ValidatedRegistryAuthority` the calculation
engine itself consumes — no mocks. Assertions read the derived union
shape, the presence of registry-declared citation tokens, and the
absent-not-invented discipline; they never assert invented values.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ....core import Modelo
from ....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ....core.resources import resources
from ...flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from .. import PageLegalZone, build_flow_legal_zones

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALE_TITLE = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="wizard.setup.title")


def _page(page_id: str, domain_key: str | None) -> FlowPage:
    return FlowPage(
        id=page_id,
        widget=FlowWidgetKind.TEXT,
        prompt=_LOCALE_TITLE,
        answer_type=str,
        domain_key=domain_key,
        required=False,
    )


def _definition() -> FlowDefinition:
    class _Answers(BaseModel):
        pass

    section = FlowSection(
        id="s",
        title=_LOCALE_TITLE,
        items=(
            _page("censo-status", "censo.status"),
            _page("cadastral", "contact.fiscal_address_cadastral_reference"),
            _page("ui-only", None),
            _page("ungrounded", "nonexistent.key"),
        ),
    )
    return FlowDefinition(
        id="legal-zone-test",
        title=_LOCALE_TITLE,
        description=_LOCALE_TITLE,
        sections=(section,),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


@pytest.fixture(scope="module")
def zones() -> dict[str, PageLegalZone]:
    return dict(build_flow_legal_zones(_definition(), resources().modelos.authority))


def test_binding_derived_page_unions_grounding(zones: dict[str, PageLegalZone]) -> None:
    """A page whose key a profile binding consumes carries the registry grounding."""
    zone = zones["censo-status"]
    assert zone.profile_key == "censo.status"
    assert Modelo.M036 in zone.modelos
    assert "rd-1065-2007:art-9" in zone.legal_refs
    assert zone.source_refs  # the consuming binding declares source_refs


def test_schema_only_page_has_refs_without_modelos(zones: dict[str, PageLegalZone]) -> None:
    """A schema-declared ref with no consuming binding renders refs but no modelos."""
    zone = zones["cadastral"]
    assert "rdleg-1-2004:art-6.3" in zone.legal_refs
    assert zone.modelos == ()


def test_ui_only_and_ungrounded_pages_render_no_zone(zones: dict[str, PageLegalZone]) -> None:
    """A page with no domain_key, or one absent from both sources, is omitted — never invented."""
    assert "ui-only" not in zones
    assert "ungrounded" not in zones


def test_every_zone_is_sorted_typed_union(zones: dict[str, PageLegalZone]) -> None:
    """Zones are deterministic: sorted ref unions, typed Modelo members, non-empty."""
    assert zones
    for page_id, zone in zones.items():
        assert zone.page_id == page_id
        assert list(zone.legal_refs) == sorted(set(zone.legal_refs))
        assert list(zone.source_refs) == sorted(set(zone.source_refs))
        assert all(isinstance(modelo, Modelo) for modelo in zone.modelos)
        assert zone.legal_refs or zone.source_refs
