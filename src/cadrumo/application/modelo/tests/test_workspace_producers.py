"""Integration contracts for stamped Modelo Workspace V1 producer captures."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._workspace_producers import (
    ModeloWorkspaceContributingProjectionV1,
    ModeloWorkspaceContributorKindV1,
    ModeloWorkspaceEpochV1,
    ModeloWorkspaceProducerContractInventoryV1,
    ModeloWorkspaceProducerContractV1,
    ModeloWorkspaceProducerStampV1,
    modelo_workspace_projection_schema_fingerprint,
)
from ..workspace_models import (
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceSchemaIdentityV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_DIGEST = "a" * 64


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


def test_workspace_producer_contract_and_stamp_reproduce_the_exact_projection_schema() -> None:
    contract = _contract(ModeloWorkspaceContributorKindV1.REGISTRY)
    stamp = ModeloWorkspaceProducerStampV1.from_contract(contract)
    capture = ModeloWorkspaceContributingProjectionV1(
        projection=_projection(),
        stamp=stamp,
        epoch=ModeloWorkspaceEpochV1(owner=contract.contributor.owner, generation=1),
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
            epoch=ModeloWorkspaceEpochV1(owner=contract.contributor.owner, generation=1),
        ).require_contract(contract)


def test_workspace_contributing_capture_refuses_owner_and_projection_schema_drift() -> None:
    contract = _contract(ModeloWorkspaceContributorKindV1.REGISTRY)
    stamp = ModeloWorkspaceProducerStampV1.from_contract(contract)

    with pytest.raises(ValueError, match="scoped to its declared owner"):
        ModeloWorkspaceContributingProjectionV1(
            projection=_projection(),
            stamp=stamp,
            epoch=ModeloWorkspaceEpochV1(owner="other.owner", generation=1),
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
        epoch=ModeloWorkspaceEpochV1(owner=contract.contributor.owner, generation=1),
    )

    with pytest.raises(ValueError, match="projection schema"):
        mismatched_capture.require_contract(changed_contract)


def test_workspace_epochs_make_an_aba_value_transition_observable_without_payload_identity() -> None:
    contract = _contract(ModeloWorkspaceContributorKindV1.CALCULATION)
    first_value = _projection()
    returned_value = _projection()
    first = ModeloWorkspaceEpochV1(owner=contract.contributor.owner, generation=11)
    changed = ModeloWorkspaceEpochV1(owner=contract.contributor.owner, generation=12)
    returned = ModeloWorkspaceEpochV1(owner=contract.contributor.owner, generation=13)

    assert first_value == returned_value
    assert changed.require_successor_of(first) is changed
    assert returned.require_successor_of(changed) is returned
    assert returned != first
    with pytest.raises(ValueError, match="must advance"):
        first.require_successor_of(returned)


def test_workspace_producer_inventory_is_a_sorted_complete_round_trip_fixed_point() -> None:
    inventory = ModeloWorkspaceProducerContractInventoryV1.generate(_contracts())

    assert tuple(
        (contract.contributor.owner, contract.contributor.producer) for contract in inventory.contracts
    ) == tuple(sorted((contract.contributor.owner, contract.contributor.producer) for contract in inventory.contracts))
    assert set(contract.contributor_kind for contract in inventory.contracts) == set(ModeloWorkspaceContributorKindV1)
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
