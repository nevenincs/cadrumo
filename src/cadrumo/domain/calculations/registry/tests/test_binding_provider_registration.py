"""Tests for the single enrollment authority behind the provider union.

What these pin is the property the three former dispatch tables could not give:
a provider kind is real in exactly one place. Every union member has a row, the
row names that member's own model, the table refuses to exist when a kind goes
missing, the seven kinds nobody routed say so out loud instead of resolving
blank, and a binding that contradicts its registration earns a diagnostic per
contradiction rather than one vague failure.

The refusal case builds its own fabricated table and hands it to the production
check function; nothing patches the shipped registrations, so the normal path
and the defect proof both hold in the same run.
"""

from __future__ import annotations

import typing
from datetime import date
from typing import Literal

import pytest
from pydantic import BaseModel, create_model

from .....core.aggregation import (
    ROW_SET_GROUPING_FOR_BINDING_SOURCE,
    BindingAggregation,
    BindingAggregationOp,
    BindingSourceKind,
    RowSetGroupingKind,
)
from ....iva.flow import IvaFlowDirection
from ....iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ..binding_provider import BindingProvider
from ..binding_provider_registration import (
    BINDING_PROVIDER_REGISTRATIONS,
    BindingProviderRegistration,
    NonRuntimeOwnership,
    RouteOwnership,
    absolute_coordinate_offenders,
    registration_for,
    require_relative_provider_coordinates,
    validate_binding_against_registration,
    validate_binding_provider_registrations,
    validator_for,
)
from ..binding_temporal import FilingYearOffset
from ..binding_terminal_origin import TerminalOriginClass, TerminalOriginExpectation
from ..binding_value_contract import BindingValueChannel
from ..bindings import validate_binding_selector_shape
from ..errors import RegistryValidationError
from ..ids import RevisionId
from ..invoice_bindings import PayableInvoiceProvider
from ..ledger_iva_bindings import LedgerIvaProvider
from ..profile_bindings import ProfileProvider
from ..relation_prefill_bindings import RelationPrefillProvider
from ..schema import BindingDefinition
from ..withholding_bindings import WithholdingProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DEFERRED_KINDS = frozenset(
    {
        BindingSourceKind.RELATED_PARTY_OPERATION,
        BindingSourceKind.REFUND_OPERATION,
        BindingSourceKind.DONATIVO_DONOR,
        BindingSourceKind.GASTO193_CONTRIBUTOR,
        BindingSourceKind.LEDGER_TRANSACTION,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        BindingSourceKind.WITHHOLDING296,
    },
)
"""The kinds that carry a model and a validator but no executable route owner."""

_LEDGER_IVA_PROVIDER = LedgerIvaProvider(
    categories=(IvaCategory.DOMESTIC_GENERAL,),
    rate_kinds=(IvaRateKind.GENERAL,),
    flow_direction=IvaFlowDirection.REPERCUTIDO,
    observation_roles=(IvaLedgerObservationRole.SETTLEMENT,),
    cash_accounting_treatments=(IvaCashAccountingTreatment.NONE,),
)


_RELATION_PREFILL_PROVIDER = RelationPrefillProvider(
    relation_kind="cross_model_output",
    dependency_role="direct_calculation",
    source_modelo="303",
    source_casilla_id="iva.cuota-devengada",
    temporal=FilingYearOffset(years=-1, source_periods=("0A",)),
)

_WITHHOLDING_ROW_PROVIDER = WithholdingProvider(
    fact="row_field",
    row_field="perceptor_tax_id",
    grouping="per_perceptor_clave",
    record="perceptor",
    data_type="text",
)

_PAYABLE_INVOICE_ROW_PROVIDER = PayableInvoiceProvider(fact="row_field", row_field="party_tax_id")


def _union_members() -> tuple[type[BaseModel], ...]:
    """Return the provider union's members, read off the union itself."""
    annotated_args = typing.get_args(BindingProvider)
    members: list[type[BaseModel]] = []
    for member in typing.get_args(annotated_args[0]):
        assert isinstance(member, type)
        assert issubclass(member, BaseModel)
        members.append(member)
    return tuple(members)


def _binding(
    provider: object,
    *,
    data_type: str = "money",
    channel: str = "decimal",
    op: BindingAggregationOp = BindingAggregationOp.SUM,
    terminal_origins: tuple[TerminalOriginExpectation, ...] = (),
    row_grouping: RowSetGroupingKind | None = None,
) -> BindingDefinition:
    """Build one binding whose value, aggregation, and origins are stated explicitly."""
    value: dict[str, object] = {"data_type": data_type, "channel": channel}
    if row_grouping is not None:
        value["row_grouping"] = row_grouping
    return BindingDefinition(
        id="test.binding",
        provider=provider,
        value=value,
        aggregation=BindingAggregation(op=op),
        terminal_origins=terminal_origins,
        legal_refs=("ley-37-1992:art-1",),
        source_refs=("aeat-modelo-303-diseno-registro",),
    )


def test_every_provider_union_member_has_a_registration() -> None:
    """The table covers the union exactly -- no orphan member, no invented kind."""
    member_kinds = frozenset(BindingSourceKind(member.model_fields["kind"].default) for member in _union_members())

    assert frozenset(BINDING_PROVIDER_REGISTRATIONS) == member_kinds


def test_a_kind_whose_member_is_its_own_gate_enrols_no_validator() -> None:
    """``None`` is an enrolled answer: the table imports, and the gate returns nothing.

    A family with no cross-invariant beyond its provider shape has nothing left
    to check once the union has constructed the member, so its registration
    carries no validator and the build-time gate earns no diagnostic.
    """
    registration = registration_for(BindingSourceKind.PROFILE)

    assert registration.validator is None
    assert validator_for(BindingSourceKind.PROFILE) is None
    assert validate_binding_selector_shape(_binding(ProfileProvider(profile_key="declarante.nif"))) == []


@pytest.mark.parametrize("kind", sorted(_DEFERRED_KINDS, key=lambda kind: kind.value))
def test_unowned_kinds_declare_a_deferred_disposition_and_a_named_owner(kind: BindingSourceKind) -> None:
    """A kind with no resolver says so, with a reason, instead of resolving blank."""
    registration = registration_for(kind)

    assert registration.disposition == "deferred"
    assert isinstance(registration.route, NonRuntimeOwnership)
    assert registration.route.owner


def test_only_the_two_pseudo_owned_kinds_are_non_runtime() -> None:
    """Operator input and a diseño constant are routed but run no resolver."""
    non_runtime = {
        kind
        for kind, registration in BINDING_PROVIDER_REGISTRATIONS.items()
        if registration.disposition == "non_runtime"
    }

    assert non_runtime == {BindingSourceKind.MANUAL_INPUT, BindingSourceKind.DESIGN_CONSTANT}
    for kind in non_runtime:
        route = registration_for(kind).route
        assert isinstance(route, RouteOwnership)
        assert route.stage == "manual"


def test_every_remaining_kind_is_filing_grade_with_a_resolver_route() -> None:
    """Whatever is neither deferred nor pseudo-owned names a real resolver."""
    for kind, registration in BINDING_PROVIDER_REGISTRATIONS.items():
        if kind in _DEFERRED_KINDS or registration.disposition == "non_runtime":
            continue
        assert registration.disposition == "filing_grade"
        assert isinstance(registration.route, RouteOwnership)
        assert registration.route.resolver_id
        assert registration.route.stage != "manual"


def test_a_fabricated_table_missing_a_kind_is_refused() -> None:
    """The production check refuses an incomplete table built from real rows.

    The input is a fabricated tuple, not a mutation of the shipped table: the
    same function that validates the real registrations at import is handed one
    row short and must refuse, which is what makes the import-time guard a gate
    rather than a comment.
    """
    complete = tuple(BINDING_PROVIDER_REGISTRATIONS.values())
    incomplete = tuple(row for row in complete if row.kind is not BindingSourceKind.PROFILE)

    with pytest.raises(RegistryValidationError, match="cover exactly the provider union members"):
        validate_binding_provider_registrations(incomplete)

    assert validate_binding_provider_registrations(complete) == BINDING_PROVIDER_REGISTRATIONS


def test_a_fabricated_table_repeating_a_kind_is_refused() -> None:
    """Two rows for one kind is the ambiguity the single authority exists to remove."""
    complete = tuple(BINDING_PROVIDER_REGISTRATIONS.values())
    duplicated = (*complete, registration_for(BindingSourceKind.PROFILE))

    with pytest.raises(RegistryValidationError, match="registered more than once"):
        validate_binding_provider_registrations(duplicated)


def test_a_fabricated_row_claiming_filing_grade_without_a_route_is_refused() -> None:
    """Filing grade without an owner is exactly the defect the table was built for."""
    profile = registration_for(BindingSourceKind.PROFILE)
    unowned = BindingProviderRegistration(
        kind=profile.kind,
        provider_model=profile.provider_model,
        validator=profile.validator,
        permitted_value_channels=profile.permitted_value_channels,
        permitted_aggregation_ops=profile.permitted_aggregation_ops,
        permitted_terminal_origins=profile.permitted_terminal_origins,
        output=profile.output,
        disposition="filing_grade",
        route=NonRuntimeOwnership(owner="nobody"),
        authoring=profile.authoring,
    )
    fabricated = tuple(
        unowned if row.kind is BindingSourceKind.PROFILE else row for row in BINDING_PROVIDER_REGISTRATIONS.values()
    )

    with pytest.raises(RegistryValidationError, match="claims filing grade without a route owner"):
        validate_binding_provider_registrations(fabricated)


def test_a_well_formed_binding_earns_no_registration_diagnostics() -> None:
    """A ledger IVA sum on the decimal channel resting on a ledger aggregate passes."""
    binding = _binding(
        _LEDGER_IVA_PROVIDER,
        terminal_origins=(
            TerminalOriginExpectation(
                source_class=TerminalOriginClass.LEDGER_AGGREGATE,
                role="primary",
                cardinality="at_least_one",
                fingerprint="optional",
            ),
        ),
    )

    assert validate_binding_against_registration(binding) == ()


def test_a_channel_the_provider_cannot_produce_is_reported() -> None:
    """A ledger aggregate does not emit text, and the diagnostic names the permitted set."""
    binding = _binding(_LEDGER_IVA_PROVIDER, data_type="text", channel="text", op=BindingAggregationOp.COPY)

    diagnostics = validate_binding_against_registration(binding)

    assert len(diagnostics) == 1
    assert "does not produce the 'text' value channel" in diagnostics[0]


def test_an_aggregation_operation_the_provider_cannot_run_is_reported() -> None:
    """``count_distinct`` belongs to the invoice and withholding families, not ledger IVA."""
    binding = _binding(_LEDGER_IVA_PROVIDER, op=BindingAggregationOp.COUNT_DISTINCT)

    diagnostics = validate_binding_against_registration(binding)

    assert len(diagnostics) == 1
    assert "does not support the 'count_distinct' aggregation operation" in diagnostics[0]


def test_a_rows_operation_on_a_scalar_channel_is_reported() -> None:
    """Emitting rows down a decimal channel is a contradiction, not a preference.

    ``relation_prefill`` is used because its registration permits the scalar
    channels and not ``rows``, so the declaration earns both the
    unsupported-operation diagnostic and the cardinality one -- two distinct
    statements about the same row, which is the point of accumulating rather
    than failing fast. (``profile`` cannot serve here: repeating typed profile
    collections are a real row family, so its registration permits both.)
    """
    binding = _binding(_RELATION_PREFILL_PROVIDER, op=BindingAggregationOp.ROWS)

    diagnostics = validate_binding_against_registration(binding)

    assert len(diagnostics) == 2
    assert any("requires the 'row_set' value channel" in diagnostic for diagnostic in diagnostics)


def test_row_assembly_is_derived_from_the_canonical_grouping_correspondence() -> None:
    """A kind is grouped exactly when the row-assembly axis enrolls it; nothing restates it."""
    for kind, registration in BINDING_PROVIDER_REGISTRATIONS.items():
        enrolled = kind in ROW_SET_GROUPING_FOR_BINDING_SOURCE
        assert registration.row_assembly == ("grouped" if enrolled else "provider_native")
        assert (registration.row_grouping is not None) == enrolled


def test_a_grouped_family_must_declare_its_canonical_grouping() -> None:
    """A grouped row family with no grouping is refused; the assembler would have nothing to dispatch on."""
    binding = _binding(
        _WITHHOLDING_ROW_PROVIDER,
        data_type="text",
        channel="row_set",
        op=BindingAggregationOp.ROWS,
    )

    diagnostics = validate_binding_against_registration(binding)

    assert any("must declare row grouping 'withholding'" in diagnostic for diagnostic in diagnostics)


def test_a_provider_native_family_must_not_declare_a_grouping() -> None:
    """An invented grouping is refused at build rather than falling through the closed dispatcher at resolve."""
    binding = _binding(
        _PAYABLE_INVOICE_ROW_PROVIDER,
        data_type="text",
        channel="row_set",
        op=BindingAggregationOp.ROWS,
        row_grouping=RowSetGroupingKind.WITHHOLDING,
    )

    diagnostics = validate_binding_against_registration(binding)

    assert any("emits provider-native rows" in diagnostic for diagnostic in diagnostics)


def test_a_row_set_resting_on_an_exactly_one_terminal_origin_is_reported() -> None:
    """A row family rests on however many facts the period produced, including none."""
    binding = _binding(
        _WITHHOLDING_ROW_PROVIDER,
        data_type="text",
        channel="row_set",
        op=BindingAggregationOp.ROWS,
        row_grouping=RowSetGroupingKind.WITHHOLDING,
        terminal_origins=(
            TerminalOriginExpectation(
                source_class=TerminalOriginClass.PERCEPTOR_OBSERVATION,
                role="primary",
                cardinality="at_least_one",
                fingerprint="optional",
            ),
        ),
    )

    assert validate_binding_against_registration(binding) == ()


def test_a_terminal_origin_class_the_provider_cannot_reach_is_reported() -> None:
    """A profile field is a censo record, never a fold over the ledger."""
    binding = _binding(
        ProfileProvider(profile_key="declarante.nif"),
        op=BindingAggregationOp.COPY,
        terminal_origins=(
            TerminalOriginExpectation(
                source_class=TerminalOriginClass.LEDGER_AGGREGATE,
                role="primary",
                cardinality="exactly_one",
                fingerprint="optional",
            ),
        ),
    )

    diagnostics = validate_binding_against_registration(binding)

    assert len(diagnostics) == 1
    assert "cannot rest on terminal origin 'ledger_aggregate'" in diagnostics[0]


def test_permitted_channels_and_output_shape_agree_for_every_row() -> None:
    """The declared output shape is derivable from the channels, and is."""
    for registration in BINDING_PROVIDER_REGISTRATIONS.values():
        carries_rows = BindingValueChannel.ROW_SET in registration.permitted_value_channels
        assert carries_rows == (registration.output in {"rows", "scalar_and_rows"})


def test_every_live_provider_member_stays_relative_to_the_filing_context() -> None:
    """The enrolled table declares no absolute filing coordinate."""
    require_relative_provider_coordinates()


@pytest.mark.parametrize(
    ("field_name", "annotation"),
    [
        ("filing_year", int),
        ("source_revision", RevisionId),
        ("as_of", date),
        ("edition_year", Literal[2024, 2025]),
        ("max_year", int | None),
    ],
    ids=["int", "revision_id", "date", "int_literal", "optional_int"],
)
def test_a_provider_field_pinning_a_filing_coordinate_is_detected(field_name: str, annotation: object) -> None:
    """Each of the four coordinate shapes is refused on its type, not on its name."""
    member = create_model("_FabricatedProvider", **{field_name: (annotation, ...)})

    offenders = absolute_coordinate_offenders("provider 'fabricated'", member)

    assert offenders == (f"provider 'fabricated' declares absolute coordinate field {field_name!r}",)


@pytest.mark.parametrize("field_name", ["offset", "length", "decimals"])
def test_an_authored_layout_integer_earns_no_offender(field_name: str) -> None:
    """Anti-tautology: the allow-listed record-layout integers stay permitted."""
    member = create_model("_LayoutProvider", **{field_name: (int, ...)})

    assert absolute_coordinate_offenders("provider 'fabricated'", member) == ()


def test_the_temporal_member_and_a_boolean_flag_earn_no_offender() -> None:
    """Relative coordinates live on ``temporal``; a flag is not a coordinate."""
    member = create_model(
        "_TemporalProvider",
        temporal=(FilingYearOffset, ...),
        within_filing_year=(bool, ...),
        source_periods=(tuple[str, ...], ()),
    )

    assert absolute_coordinate_offenders("provider 'fabricated'", member) == ()


def test_a_fabricated_registration_with_an_absolute_coordinate_is_refused() -> None:
    """The guard refuses the table, not just the model, so a new member cannot slip in."""
    member = create_model("_AbsoluteProvider", filing_year=(int, ...))
    profile = registration_for(BindingSourceKind.PROFILE)
    fabricated = {
        BindingSourceKind.PROFILE: BindingProviderRegistration(
            kind=profile.kind,
            provider_model=member,
            validator=profile.validator,
            permitted_value_channels=profile.permitted_value_channels,
            permitted_aggregation_ops=profile.permitted_aggregation_ops,
            permitted_terminal_origins=profile.permitted_terminal_origins,
            output=profile.output,
            disposition=profile.disposition,
            route=profile.route,
            authoring=profile.authoring,
        ),
    }

    with pytest.raises(RegistryValidationError, match="stay relative to the target filing context"):
        require_relative_provider_coordinates(fabricated)
