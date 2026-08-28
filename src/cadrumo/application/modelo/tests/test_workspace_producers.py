"""Integration contracts for stamped Modelo Workspace V1 producer captures."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..workspace_models import (
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceSchemaIdentityV1,
)
from ..workspace_producers import (
    ModeloWorkspaceContributingProjectionV1,
    ModeloWorkspaceContributorKindV1,
    ModeloWorkspaceEpochV1,
    ModeloWorkspaceProducerContractInventoryV1,
    ModeloWorkspaceProducerContractV1,
    ModeloWorkspaceProducerStampV1,
    modelo_workspace_projection_schema_fingerprint,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_DIGEST = "a" * 64
_COMPARISON_DOMAIN = "b" * 64


def _projection() -> ModeloWorkspaceSchemaIdentityV1:
    return ModeloWorkspaceSchemaIdentityV1(
        schema_id="modelo-130-schema",
        schema_fingerprint=_DIGEST,
        field_manifest_digest=_DIGEST,
    )


def _contract(
    contributor_kind: ModeloWorkspaceContributorKindV1,
    *,
    projection_contract_version: int = 1,
) -> ModeloWorkspaceProducerContractV1:
    return ModeloWorkspaceProducerContractV1.declare(
        contributor_kind=contributor_kind,
        contributor=ModeloWorkspaceContributorIdentityV1(
            owner=f"{contributor_kind.value}.owner",
            producer=f"{contributor_kind.value}.projection",
        ),
        projection_discriminator=f"modelo_workspace.{contributor_kind.value}",
        projection_contract_version=projection_contract_version,
        projection_type=ModeloWorkspaceSchemaIdentityV1,
    )


def _contracts() -> tuple[ModeloWorkspaceProducerContractV1, ...]:
    return tuple(_contract(kind) for kind in ModeloWorkspaceContributorKindV1)


def _epoch(owner: str, generation: int) -> ModeloWorkspaceEpochV1:
    return ModeloWorkspaceEpochV1(
        owner=owner,
        comparison_domain=_COMPARISON_DOMAIN,
        generation=generation,
    )


def test_workspace_producer_contract_and_stamp_reproduce_the_exact_projection_schema() -> None:
    contract = _contract(ModeloWorkspaceContributorKindV1.REGISTRY)
    stamp = ModeloWorkspaceProducerStampV1.from_contract(contract)
    capture = ModeloWorkspaceContributingProjectionV1(
        projection=_projection(),
        stamp=stamp,
        epoch=_epoch(contract.contributor.owner, 1),
    )

    assert contract.projection_schema_fingerprint == modelo_workspace_projection_schema_fingerprint(
        ModeloWorkspaceSchemaIdentityV1
    )
    assert capture.require_contract(contract) is capture
    assert ModeloWorkspaceProducerContractV1.model_validate_json(contract.model_dump_json()) == contract

    mismatched_stamp = stamp.model_copy(update={"projection_contract_version": 2})
    with pytest.raises(ValueError, match="stamp does not match"):
        ModeloWorkspaceContributingProjectionV1(
            projection=_projection(),
            stamp=mismatched_stamp,
            epoch=_epoch(contract.contributor.owner, 1),
        ).require_contract(contract)


def test_fingerprint_admits_a_decimal_bearing_domain_model() -> None:
    """A bare Decimal field must no longer refuse registration.

    RegistrySnapshot, ModeloWorkReview and CalculationRevision all carry
    Decimal fields and were the real, motivating failures -- exercised here
    with an equivalent locally-defined Decimal field, since importing any of
    the three real models into this focused unit test would pull in the
    whole registry/ledger graph.
    """
    from decimal import Decimal

    from pydantic import BaseModel

    class _DecimalBearingProjection(BaseModel):
        amount: Decimal

    modelo_workspace_projection_schema_fingerprint(_DecimalBearingProjection)


def test_fingerprint_admits_the_real_motivating_calculation_revision_model() -> None:
    """The real production model that surfaced this, not just a synthetic stand-in."""
    from ....domain.modelos.calculation_revision import CalculationRevision

    modelo_workspace_projection_schema_fingerprint(CalculationRevision)


def test_fingerprint_proves_the_round_trip_it_actually_needs() -> None:
    """The corrected fingerprint's real guarantee: dump, then re-validate.

    Equality between the validation and serialization schemas was standing in
    for this property without ever testing it. A Decimal field is the
    sharpest case: it accepts int/str/Decimal on input but always emits a
    string, and that string parses straight back to the same Decimal.
    """
    from decimal import Decimal

    from pydantic import BaseModel

    class _DecimalBearingProjection(BaseModel):
        amount: Decimal

    original = _DecimalBearingProjection(amount=Decimal("42.50"))
    round_tripped = _DecimalBearingProjection.model_validate_json(original.model_dump_json())

    assert round_tripped == original
    assert isinstance(round_tripped.amount, Decimal)


def test_fingerprint_still_refuses_genuine_schema_drift() -> None:
    """Deriving from serialization alone must not turn the fingerprint into a no-op.

    Two structurally different projections -- and one projection before and
    after a real field is added -- must still fingerprint differently. A
    fingerprint that stopped discriminating shape would be a guard removed,
    not a guard fixed.
    """
    from pydantic import BaseModel

    class _NarrowProjection(BaseModel):
        value: str

    class _WiderProjection(BaseModel):
        value: str
        extra: int

    narrow_fingerprint = modelo_workspace_projection_schema_fingerprint(_NarrowProjection)
    wider_fingerprint = modelo_workspace_projection_schema_fingerprint(_WiderProjection)

    assert narrow_fingerprint != wider_fingerprint
    assert modelo_workspace_projection_schema_fingerprint(_NarrowProjection) == narrow_fingerprint


def test_workspace_contributing_capture_refuses_owner_and_projection_schema_drift() -> None:
    contract = _contract(ModeloWorkspaceContributorKindV1.REGISTRY)
    stamp = ModeloWorkspaceProducerStampV1.from_contract(contract)

    with pytest.raises(ValueError, match="scoped to its declared owner"):
        ModeloWorkspaceContributingProjectionV1(
            projection=_projection(),
            stamp=stamp,
            epoch=_epoch("other.owner", 1),
        ).require_contract(contract)

    changed_contract = ModeloWorkspaceProducerContractV1.declare(
        contributor_kind=contract.contributor_kind,
        contributor=contract.contributor,
        projection_discriminator=contract.projection_discriminator,
        projection_contract_version=contract.projection_contract_version,
        projection_type=ModeloWorkspaceLocaleSummaryV1,
    )
    mismatched_capture = ModeloWorkspaceContributingProjectionV1(
        projection=_projection(),
        stamp=ModeloWorkspaceProducerStampV1.from_contract(changed_contract),
        epoch=_epoch(contract.contributor.owner, 1),
    )

    with pytest.raises(ValueError, match="projection schema"):
        mismatched_capture.require_contract(changed_contract)


def test_workspace_epochs_make_an_aba_value_transition_observable_without_payload_identity() -> None:
    contract = _contract(ModeloWorkspaceContributorKindV1.CALCULATION)
    first_value = _projection()
    returned_value = _projection()
    first = _epoch(contract.contributor.owner, 11)
    changed = _epoch(contract.contributor.owner, 12)
    returned = _epoch(contract.contributor.owner, 13)

    assert first_value == returned_value
    assert changed.require_successor_of(first) is changed
    assert returned.require_successor_of(changed) is returned
    assert returned != first
    with pytest.raises(ValueError, match="must advance"):
        first.require_successor_of(returned)


@pytest.mark.parametrize(
    "epoch_values",
    (
        {"schema_version": 1, "comparison_domain": _COMPARISON_DOMAIN},
        {"schema_version": 2},
        {"schema_version": 3, "comparison_domain": _COMPARISON_DOMAIN},
    ),
)
def test_workspace_epoch_accepts_only_complete_current_schema_v2(
    epoch_values: dict[str, int | str],
) -> None:
    with pytest.raises(ValidationError):
        ModeloWorkspaceEpochV1.model_validate({"owner": "calculation.owner", "generation": 1, **epoch_values})


@pytest.mark.parametrize("generation", (11, 10, 9))
def test_workspace_epoch_refuses_cross_domain_coordinates_before_generation_comparison(
    generation: int,
) -> None:
    predecessor = _epoch("calculation.owner", 10)
    different_domain = ModeloWorkspaceEpochV1(
        owner="calculation.owner",
        comparison_domain="c" * 64,
        generation=generation,
    )

    with pytest.raises(ValueError, match="comparison domain"):
        different_domain.require_successor_of(predecessor)
    with pytest.raises(ValueError, match="comparison domain"):
        predecessor.require_current(different_domain)


def test_workspace_epoch_currentness_requires_an_exact_same_domain_coordinate() -> None:
    captured = _epoch("calculation.owner", 10)

    assert captured.require_current(_epoch("calculation.owner", 10)) is captured
    with pytest.raises(ValueError, match="no longer current"):
        captured.require_current(_epoch("calculation.owner", 11))


def test_workspace_producer_inventory_is_a_sorted_complete_round_trip_fixed_point() -> None:
    inventory = ModeloWorkspaceProducerContractInventoryV1.generate(_contracts())

    assert tuple(
        (contract.contributor.owner, contract.contributor.producer) for contract in inventory.contracts
    ) == tuple(sorted((contract.contributor.owner, contract.contributor.producer) for contract in inventory.contracts))
    assert set(contract.contributor_kind for contract in inventory.contracts) == set(ModeloWorkspaceContributorKindV1)
    assert {contract.epoch_schema_version for contract in inventory.contracts} == {2}
    assert ModeloWorkspaceProducerContractInventoryV1.model_validate_json(inventory.model_dump_json()) == inventory
    assert inventory.require_current(_contracts()) is inventory


def test_workspace_producer_inventory_refuses_missing_duplicate_and_unclassified_contributors() -> None:
    contracts = _contracts()
    with pytest.raises(ValidationError):
        ModeloWorkspaceProducerContractInventoryV1.generate(contracts[:-1])
    with pytest.raises(ValidationError, match="duplicate a contributor identity"):
        ModeloWorkspaceProducerContractInventoryV1.generate((*contracts[:-1], contracts[0]))
    stale_contract = contracts[0].model_copy(update={"projection_contract_version": 2})
    with pytest.raises(ValidationError, match="contract is stale"):
        ModeloWorkspaceProducerContractInventoryV1.generate((stale_contract, *contracts[1:]))

    unclassified_contract = contracts[0].model_dump(mode="json")
    unclassified_contract["contributor_kind"] = "unclassified"
    with pytest.raises(ValidationError):
        ModeloWorkspaceProducerContractInventoryV1.model_validate(
            {
                "contracts": (unclassified_contract, *(contract.model_dump(mode="json") for contract in contracts[1:])),
                "inventory_digest": _DIGEST,
            }
        )


def test_workspace_producer_inventory_refuses_a_current_contract_set_that_has_drifted() -> None:
    inventory = ModeloWorkspaceProducerContractInventoryV1.generate(_contracts())
    current_contracts = tuple(
        _contract(
            contract.contributor_kind,
            projection_contract_version=(
                2 if contract.contributor_kind is ModeloWorkspaceContributorKindV1.READINESS else 1
            ),
        )
        for contract in _contracts()
    )

    with pytest.raises(ValueError, match="inventory is stale"):
        inventory.require_current(current_contracts)


def test_the_closed_inventory_registers_all_eight_contributors_exactly() -> None:
    """The real production inventory, not a synthetic fixture."""
    from ..workspace_producers import MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1

    kinds = {contract.contributor_kind for contract in MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.contracts}
    assert kinds == set(ModeloWorkspaceContributorKindV1)
    assert len(MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.contracts) == len(ModeloWorkspaceContributorKindV1)


def test_every_contract_matches_the_governing_adrs_contributor_fixed_point() -> None:
    """The owner/producer identities reproduce the governing decision's table verbatim, not a free-form label."""
    from ..workspace_producers import MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1

    expected = {
        ModeloWorkspaceContributorKindV1.REGISTRY: ("domain.calculations.registry", "validated_registry_projection"),
        ModeloWorkspaceContributorKindV1.WORK: ("application.modelo.work_addressing", "resolved_work_target"),
        ModeloWorkspaceContributorKindV1.BOUNDED_REVIEW: ("application.modelo.work_review", "modelo_work_review"),
        ModeloWorkspaceContributorKindV1.CALCULATION: ("application.modelo.calculation", "calculation_materialization"),
        ModeloWorkspaceContributorKindV1.READINESS: ("application.state_projection", "modelo_readiness"),
        ModeloWorkspaceContributorKindV1.CLOSURE: ("application.registry", "registry_closure"),
        ModeloWorkspaceContributorKindV1.LOCALE_CATALOGUE: ("locales", "locale_catalogue"),
        ModeloWorkspaceContributorKindV1.FIELD_MANIFEST: (
            "application.modelo.workspace_manifest",
            "workspace_field_manifest",
        ),
    }
    actual = {
        contract.contributor_kind: (contract.contributor.owner, contract.contributor.producer)
        for contract in MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.contracts
    }
    assert actual == expected


def test_registry_port_captures_the_admission_specific_projection() -> None:
    """REGISTRY's port must expose exactly the admitted shape, never both at once."""
    from ....domain.calculations.registry.authority import bundled_authority
    from ..workspace_producers import ModeloWorkspaceRegistryPortV1, ModeloWorkspaceRegistryProjectionV1

    registry_authority = bundled_authority()
    port = ModeloWorkspaceRegistryPortV1(
        authority=registry_authority,
        modelo_id="130",
        filing_year=2026,
        period="1T",
    )
    captured = port.capture_projection_with_epoch()

    assert isinstance(captured.projection, ModeloWorkspaceRegistryProjectionV1)
    assert (captured.projection.inspection is None) != (captured.projection.snapshot is None)
    captured.require_contract(port.producer_contract)

    stamp, epoch = port.read_current_stamp_and_epoch()
    assert stamp == captured.stamp
    assert epoch.generation == captured.epoch.generation


def test_registry_projection_refuses_carrying_both_or_neither_admission_shape() -> None:
    from ....core import RegistryAuthorityGrade
    from ....domain.calculations.registry.authority import bundled_authority
    from ..workspace_producers import ModeloWorkspaceRegistryPortV1, ModeloWorkspaceRegistryProjectionV1

    registry_authority = bundled_authority()
    inspection_only = ModeloWorkspaceRegistryPortV1(
        authority=registry_authority,
        modelo_id="130",
        filing_year=2026,
        period="1T",
    ).capture_projection_with_epoch()
    snapshot_only = ModeloWorkspaceRegistryPortV1(
        authority=registry_authority,
        modelo_id="130",
        filing_year=2026,
        period="1T",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    ).capture_projection_with_epoch()

    assert inspection_only.projection.inspection is not None
    assert snapshot_only.projection.snapshot is not None

    with pytest.raises(ValidationError, match="exactly one admission shape"):
        ModeloWorkspaceRegistryProjectionV1()
    with pytest.raises(ValidationError, match="exactly one admission shape"):
        ModeloWorkspaceRegistryProjectionV1(
            inspection=inspection_only.projection.inspection,
            snapshot=snapshot_only.projection.snapshot,
        )


def test_workspace_producers_have_one_public_module_and_no_private_or_package_binding_remnant() -> None:
    public_module = importlib.import_module("cadrumo.application.modelo.workspace_producers")
    package = importlib.import_module("cadrumo.application.modelo")
    private_module = ".".join((*public_module.__name__.split(".")[:-1], "_workspace" + "_producers"))
    sys.modules.pop(private_module, None)

    assert public_module.ModeloWorkspaceEpochV1 is ModeloWorkspaceEpochV1
    assert ModeloWorkspaceEpochV1.__module__ == public_module.__name__
    assert package.__all__ == ()
    assert not hasattr(package, "ModeloWorkspaceEpochV1")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(private_module)


def test_workspace_producer_docs_and_active_tree_reach_the_public_module_fixed_point() -> None:
    repository = Path(__file__).resolve().parents[5]
    private_module = "_workspace" + "_producers"
    public_module = "workspace_producers"
    scanned_paths = (
        *sorted((repository / "src").rglob("*.py")),
        *sorted((repository / "docs").rglob("*.rst")),
    )
    remnants = tuple(
        path.relative_to(repository)
        for path in scanned_paths
        if path != Path(__file__).resolve() and private_module in path.read_text(encoding="utf-8")
    )

    assert not remnants
    assert (repository / "docs" / "api" / f"cadrumo.application.modelo.{public_module}.rst").is_file()
    assert public_module in (repository / "docs" / "api" / "cadrumo.application.modelo.rst").read_text(encoding="utf-8")
