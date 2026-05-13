"""Tests for the backend-owned operator surface contract."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from aeat.application import operator_surface
from aeat.application.operator_surface import (
    ModeloLifecycleStep,
    OperatorSurfaceContractError,
    RootSurfaceName,
    SourceKind,
    get_operator_surface_contract,
    require_accepted_root,
    resolve_source_kind_alias,
    retired_surface_suggestion,
)
from aeat.application.operator_surface._models import LifecycleContract, RootSurface
from aeat.core.errors import get_registered_error_code

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_contract_roots_are_exactly_config_and_app() -> None:
    contract = get_operator_surface_contract()

    assert tuple(root.name for root in contract.roots) == (
        RootSurfaceName.CONFIG,
        RootSurfaceName.APP,
    )
    assert contract.roots[0].owns_storage_maintenance is True
    assert contract.roots[1].owns_operational_workflow is True


def test_contract_lifecycle_forbids_live_submission() -> None:
    contract = get_operator_surface_contract()

    assert contract.lifecycle.steps == (
        ModeloLifecycleStep.CALCULATE,
        ModeloLifecycleStep.VERIFY,
        ModeloLifecycleStep.FILE,
    )
    assert contract.lifecycle.internal_filed_term == "internal filed"
    assert contract.lifecycle.live_submission_enabled is False

    with pytest.raises(ValidationError):
        LifecycleContract(
            steps=(
                ModeloLifecycleStep.CALCULATE,
                ModeloLifecycleStep.FILE,
            )
        )
    with pytest.raises(ValidationError):
        LifecycleContract(
            steps=(
                ModeloLifecycleStep.CALCULATE,
                ModeloLifecycleStep.VERIFY,
                ModeloLifecycleStep.FILE,
            ),
            live_submission_enabled=True,
        )


def test_contract_source_kind_aliases_are_parser_only() -> None:
    assert resolve_source_kind_alias("ledger_transaction") is SourceKind.LEDGER_TRANSACTION
    assert resolve_source_kind_alias("lt") is SourceKind.LEDGER_TRANSACTION
    assert resolve_source_kind_alias("pie") is SourceKind.PURCHASE_INVOICE_EVIDENCE
    assert resolve_source_kind_alias("pi") is SourceKind.PAYABLE_INVOICE
    assert resolve_source_kind_alias("ci") is SourceKind.COLLECTIBLE_INVOICE


def test_retired_surface_suggestions_capture_rejected_roots() -> None:
    setup = retired_surface_suggestion("setup")
    submit = retired_surface_suggestion("submit")

    assert setup is not None
    assert setup.replacement == "config"
    assert setup.suggestion == "aeat config init"
    assert submit is not None
    assert submit.replacement is None
    assert submit.reason == "live submission is permanently disabled"


def test_require_accepted_root_uses_registered_application_error() -> None:
    assert require_accepted_root("config").name is RootSurfaceName.CONFIG

    with pytest.raises(OperatorSurfaceContractError) as exc_info:
        require_accepted_root("setup")

    error = exc_info.value
    assert error.suggestion == "aeat config init"
    assert error.reason == "setup and config are consolidated under the config root"
    assert get_registered_error_code(error).code == "REFUSED_OPERATOR_SURFACE_CONTRACT"


def test_contract_models_are_strict_and_immutable() -> None:
    root = get_operator_surface_contract().roots[0]

    with pytest.raises(ValidationError):
        RootSurface(
            name=RootSurfaceName.CONFIG,
            purpose="duplicate children",
            owns_storage_maintenance=True,
            owns_operational_workflow=False,
            required_children=("profile", "profile"),
        )
    with pytest.raises(ValidationError):
        extra_kwargs: dict[str, object] = {"unexpected": True}
        RootSurface.model_validate(
            {
                "name": RootSurfaceName.CONFIG,
                "purpose": "extra field",
                "owns_storage_maintenance": True,
                "owns_operational_workflow": False,
                **extra_kwargs,
            }
        )
    with pytest.raises(ValidationError):
        root.purpose = "mutated"  # type: ignore[misc]


def test_operator_surface_application_package_has_no_typer_dependency() -> None:
    module_sources = [
        inspect.getsource(operator_surface),
        inspect.getsource(operator_surface._contract),  # type: ignore[attr-defined]
        inspect.getsource(operator_surface._models),  # type: ignore[attr-defined]
    ]
    joined = "\n".join(module_sources)

    assert "typer" not in joined.lower()
    assert "entrypoints.cli" not in joined


def test_log_fields_and_error_codes_are_backend_owned() -> None:
    contract = get_operator_surface_contract()

    assert contract.log_fields.as_extra() == {
        "contract_name": "operator_surface",
        "root_count": 2,
        "retired_surface_count": len(contract.retired_surfaces),
        "lifecycle": "calculate -> verify -> file",
        "source_kind_count": 4,
    }
    assert contract.error_codes == ("REFUSED_OPERATOR_SURFACE_CONTRACT",)
