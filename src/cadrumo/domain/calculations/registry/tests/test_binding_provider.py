"""Tests for the closed provider union a binding declaration names.

The union replaces the former ``source`` token plus untyped ``selector``
mapping. What these tests pin is what that replacement bought: a declaration
validates to exactly one member, serialises with its own tag and reads back to
the same member, a kind outside the authored set cannot be spelled at all, and
the two mesh-only source kinds -- which name runtime value routes no registry
row may declare -- are refused rather than tolerated.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from .....core.aggregation import (
    BindingAggregation,
    BindingAggregationOp,
    BindingSourceKind,
)
from .....core.modelo import Modelo
from .....core.toml import freeze_toml_value
from ....iva.flow import IvaFlowDirection
from ....iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ..binding_provider import BindingProvider
from ..binding_temporal import FilingYearOffset, SameTargetContext
from ..bindings_previous_filing import PreviousFilingProvider
from ..inventory_bindings import InventoryProvider
from ..ledger_iva_bindings import LedgerIvaProvider
from ..manual_input_selector import ManualInputProvider
from ..profile_bindings import ProfileProvider
from ..schema import BindingDefinition
from ..schema_base import CasillaDataType

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROVIDER_ADAPTER: TypeAdapter[object] = TypeAdapter(BindingProvider)

_LEDGER_IVA_PROVIDER = LedgerIvaProvider(
    categories=(IvaCategory.DOMESTIC_GENERAL,),
    rate_kinds=(IvaRateKind.GENERAL,),
    flow_direction=IvaFlowDirection.REPERCUTIDO,
    observation_roles=(IvaLedgerObservationRole.SETTLEMENT,),
    cash_accounting_treatments=(IvaCashAccountingTreatment.NONE,),
)

_PREVIOUS_FILING_PROVIDER = PreviousFilingProvider(
    source_modelo="303",
    temporal=FilingYearOffset(years=-1, source_periods=("4T",)),
    source_casilla_ids=("66",),
)

_INVENTORY_PROVIDER = InventoryProvider(
    modelo=Modelo.M100,
    projection_grain="taxpayer_year_activity",
    fact="row_field",
    record="inventory_activity",
    grouping="per_inventory_activity",
    row_field="complete_acquisition_cost",
    target_casilla_id="0181",
)

_MEMBERS = (
    pytest.param(_PREVIOUS_FILING_PROVIDER, BindingSourceKind.PREVIOUS_FILING, id="previous-filing"),
    pytest.param(ProfileProvider(profile_key="declarante.nif"), BindingSourceKind.PROFILE, id="profile"),
    pytest.param(
        ManualInputProvider(casilla_id="0181", data_type=CasillaDataType.MONEY),
        BindingSourceKind.MANUAL_INPUT,
        id="manual-input",
    ),
    pytest.param(_LEDGER_IVA_PROVIDER, BindingSourceKind.LEDGER_IVA_AGGREGATION, id="ledger-iva"),
    pytest.param(_INVENTORY_PROVIDER, BindingSourceKind.INVENTORY, id="inventory"),
)


def _binding(provider: object, *, data_type: str = "money", channel: str = "decimal") -> BindingDefinition:
    """Build one minimal, well-formed binding around ``provider``."""
    return BindingDefinition(
        id="test.binding",
        provider=provider,
        value={"data_type": data_type, "channel": channel},
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        legal_refs=("ley-37-1992:art-1",),
        source_refs=("aeat-modelo-303-diseno-registro",),
    )


@pytest.mark.parametrize(("provider", "expected_kind"), _MEMBERS)
def test_binding_carries_its_provider_and_projects_the_source_kind(
    provider: object,
    expected_kind: BindingSourceKind,
) -> None:
    """A well-formed provider constructs, and ``source`` projects its discriminator."""
    binding = _binding(provider)

    assert binding.provider == provider
    assert binding.source is expected_kind


@pytest.mark.parametrize(("provider", "expected_kind"), _MEMBERS)
def test_provider_round_trips_through_its_own_discriminator(
    provider: object,
    expected_kind: BindingSourceKind,
) -> None:
    """A serialised provider reads back to the same member with no sibling source key.

    The JSON payload is frozen on the way back in because registry models
    validate strictly: a tuple field dumps to a JSON array and must be handed
    back as a tuple, exactly as the published authority artifact is re-read.
    """
    payload = _binding(provider).model_dump(mode="json")

    assert "source" not in payload
    assert payload["provider"]["kind"] == expected_kind.value

    restored = BindingDefinition.model_validate(freeze_toml_value(payload))

    assert restored.provider == provider
    assert type(restored.provider) is type(provider)


def test_union_refuses_an_unknown_provider_kind() -> None:
    """A kind outside the authored set resolves to no member at all."""
    with pytest.raises(ValidationError, match=r"union_tag_invalid|does not match any of the expected tags"):
        _PROVIDER_ADAPTER.validate_python({"kind": "sheets_pull", "profile_key": "declarante.nif"})


@pytest.mark.parametrize(
    "mesh_only_kind",
    [BindingSourceKind.BORRADOR, BindingSourceKind.IVA_WALLET_DECISION],
)
def test_union_refuses_the_mesh_only_source_kinds(mesh_only_kind: BindingSourceKind) -> None:
    """The two runtime-only value routes are not declarable registry providers."""
    with pytest.raises(ValidationError, match=r"union_tag_invalid|does not match any of the expected tags"):
        _PROVIDER_ADAPTER.validate_python({"kind": mesh_only_kind.value})


def test_binding_refuses_the_legacy_source_and_selector_pair() -> None:
    """The displaced two-field spelling is refused, not quietly re-interpreted."""
    with pytest.raises(ValidationError) as failure:
        BindingDefinition.model_validate(
            {
                "id": "test.binding",
                "source": "profile",
                "selector": {"profile_key": "declarante.nif"},
                "value": {"data_type": "text", "channel": "text"},
                "legal_refs": ("ley-35-2006:art-1",),
                "source_refs": ("aeat-modelo-100-diseno-registro",),
            },
        )

    message = str(failure.value)
    assert "provider" in message
    assert "source" in message
    assert "selector" in message


def test_previous_filing_refuses_a_temporal_member_naming_no_source_window() -> None:
    """``same_target_context`` reads the target's own period and is not a carry.

    Only the per-grupo member fold means it legitimately, so every other
    previous-filing declaration must name its source window explicitly rather
    than defaulting into reading the period it is supposed to carry from.
    """
    with pytest.raises(ValidationError, match="same_target_context"):
        PreviousFilingProvider(
            source_modelo="303",
            temporal=SameTargetContext(),
            source_casilla_ids=("66",),
        )
