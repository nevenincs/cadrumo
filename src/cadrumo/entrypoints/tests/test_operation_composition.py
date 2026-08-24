"""Production composition proofs for the sole operation dependency graph."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

from ...application.operations import (
    OperationCancellationService,
    OperationDetachService,
    OperationObservationService,
    OperationResponseControlService,
    OperationReviewProjectionService,
    OperationSecureResponseAuthority,
    OperationWorkspaceRefreshTargetService,
)
from ...adapters.persistence.storage import current_active_bucket_session
from ...tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from .._operation_composition import OperationProductionDependencies, compose_operation_dependencies

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_EXPECTED_DEFINITION_IDS = (
    "auth.profile.login",
    "auth.profile.passphrase-rotate",
    "auth.provider.configure",
    "auth.session.acquire",
    "auth.session.logout",
    "auth.session.reset",
    "live.filed-history.pull",
    "user-profile.bundle-export",
    "user-profile.censo-review",
    "user-profile.field-mutation",
    "user-profile.logout",
    "user-profile.repeatable-row-mutation",
)


def test_production_composition_builds_one_complete_public_registry(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies()

        assert tuple(item.definition_id for item in dependencies.registry.definitions) == _EXPECTED_DEFINITION_IDS
        assert (
            tuple(item.definition_id for item in dependencies.registry.public_contract_set.definitions)
            == _EXPECTED_DEFINITION_IDS
        )
        assert len(dependencies.registry.public_contract_set.contract_set_digest) == 64
        assert isinstance(dependencies.observation, OperationObservationService)
        assert isinstance(dependencies.review, OperationReviewProjectionService)
        assert isinstance(dependencies.refresh, OperationWorkspaceRefreshTargetService)
        assert isinstance(dependencies.cancellation, OperationCancellationService)
        assert isinstance(dependencies.detach, OperationDetachService)
        assert dependencies.observation.reader is dependencies.review.reader
        assert dependencies.observation.reader is dependencies.refresh.reader
        assert dependencies.supervisor._operands is dependencies.review.operands
        asyncio.run(dependencies.shutdown())


def test_production_composition_is_available_before_profile_login(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert current_active_bucket_session() is None
        dependencies = compose_operation_dependencies()

        assert dependencies.registry.lookup("auth.profile.login").definition_id == "auth.profile.login"
        asyncio.run(dependencies.shutdown())


def test_production_composition_requires_a_separately_held_response_authority() -> None:
    response_hints = get_type_hints(OperationProductionDependencies.response)

    assert response_hints == {
        "authority": OperationSecureResponseAuthority,
        "return": OperationResponseControlService,
    }
    assert "response" not in {item.name for item in fields(OperationProductionDependencies)}


def test_production_composition_imports_operation_definitions_only_from_owner_facades() -> None:
    source_path = Path(__file__).parents[1] / "_operation_composition.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))

    assert not any(module.endswith("_operation_definitions") for module in imported_modules)
    assert not any(module.endswith("_censal_operation") for module in imported_modules)
    assert not any(module.endswith("_filed_history_operation") for module in imported_modules)


def test_production_composition_imports_operation_contracts_only_from_the_public_facade() -> None:
    source_path = Path(__file__).parents[1] / "_operation_composition.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    operation_imports = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("application.operations")
    )

    assert len(operation_imports) == 1
    assert operation_imports[0].module == "application.operations"
    assert operation_imports[0].level == 2
