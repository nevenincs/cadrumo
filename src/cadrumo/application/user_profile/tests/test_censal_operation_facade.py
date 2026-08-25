"""Public-facade contract for the resumable censo operation."""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

from .. import (
    CENSAL_OPERATION_DEFINITION,
    CENSAL_OPERATION_DEFINITION_ID,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    CensalFieldIntent,
    CensalOperationOutcome,
    CensalOperationRequest,
    CensalOperationResult,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewResponse,
)
from .. import __all__ as public_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_censal_operation_contract_resolves_from_the_public_facade() -> None:
    """The facade exposes the typed request/result and registered definition."""

    user_profile = importlib.import_module("..", package=__package__)

    assert CENSAL_OPERATION_DEFINITION_ID == "user-profile.censo-review"
    assert CENSAL_OPERATION_DEFINITION.definition_id == CENSAL_OPERATION_DEFINITION_ID
    assert CENSAL_OPERATION_DEFINITION.request_type is CensalOperationRequest
    assert CENSAL_OPERATION_DEFINITION.result_type is CensalOperationResult
    assert CENSAL_OPERATION_DEFINITION.executor_factory.request_type is CensalOperationRequest
    assert CENSAL_OPERATION_DEFINITION.executor_factory.executor_type.__module__.endswith("._censal_operation")
    assert CENSAL_OPERATION_DEFINITION.executor_factory.build() is not None
    assert CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.model_type is CensalReviewResponse

    assert CensalFieldIntent.__module__.endswith("._censal_operation")
    assert CensalOperationOutcome.__module__.endswith("._censal_operation")
    assert CensalProfileBaseline.__module__.endswith("._censal_operation")
    assert CensalReviewedFieldIntent.__module__.endswith("._censal_operation")
    assert user_profile.CENSAL_OPERATION_DEFINITION is CENSAL_OPERATION_DEFINITION


def test_censal_operation_facade_does_not_publish_operand_or_phase_internals() -> None:
    """Secure operands and orchestration helpers remain owner-private."""

    user_profile = importlib.import_module("..", package=__package__)

    assert "CensalReviewedOperand" not in public_names
    assert "CENSAL_PHASE_APPLY" not in public_names
    assert "_pull_censal_datos" not in public_names
    assert not hasattr(user_profile, "CensalReviewedOperand")
    assert not hasattr(user_profile, "CENSAL_PHASE_APPLY")


def test_censal_operation_public_names_are_unique_and_resolvable() -> None:
    """Every promised facade member resolves to a value, never a module object."""

    user_profile = importlib.import_module("..", package=__package__)

    assert len(public_names) == len(set(public_names))
    assert all(not name.startswith("_") for name in public_names)
    assert all(hasattr(user_profile, name) for name in public_names)
    assert all(not isinstance(getattr(user_profile, name), ModuleType) for name in public_names)

    operation_names = [
        "CENSAL_OPERATION_DEFINITION",
        "CENSAL_OPERATION_DEFINITION_ID",
        "CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING",
        "CensalFieldIntent",
        "CensalOperationOutcome",
        "CensalOperationRequest",
        "CensalOperationResult",
        "CensalProfileBaseline",
        "CensalReviewResponse",
        "CensalReviewedFieldIntent",
    ]
    assert operation_names == sorted(operation_names)


def test_importing_user_profile_keeps_censal_operation_lazy() -> None:
    """Importing the package root does not load the executor module eagerly."""

    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline code under test
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import sys
                import cadrumo.application.user_profile

                assert "cadrumo.application.user_profile._censal_operation" not in sys.modules
                """,
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_censal_write_authority_is_not_redeclared_in_production() -> None:
    """Anti-redeclaration gate: reviewed live apply has one exact owner."""

    package_root = Path(__file__).resolve().parents[3]
    sources = {
        path.relative_to(package_root).as_posix(): path.read_text(encoding="utf-8")
        for path in package_root.rglob("*.py")
        if "tests" not in path.parts
    }
    trees = {relative: ast.parse(source) for relative, source in sources.items()}
    assert all(
        not any(
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "apply_censal_read"
            for node in ast.walk(tree)
        )
        for tree in trees.values()
    )

    def called_name(node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    callers = {
        relative
        for relative, tree in trees.items()
        if not relative.endswith("user_profile/_cotejo_apply.py")
        and any(isinstance(node, ast.Call) and called_name(node) == "apply_cotejo" for node in ast.walk(tree))
    }
    assert callers == {
        "application/user_profile/_censal_operation.py",
        "entrypoints/cli/_config/_censo_file.py",
    }
    canonical_calls = [
        node
        for node in ast.walk(trees["application/user_profile/_censal_operation.py"])
        if isinstance(node, ast.Call) and called_name(node) == "apply_cotejo"
    ]
    assert len(canonical_calls) == 1
    assert {keyword.arg for keyword in canonical_calls[0].keywords} == {"reviewed_proposal"}
    frontend_functions = {
        "entrypoints/_censal_review.py": "_run",
        "entrypoints/cli/_config/_censo_file.py": "censo_pull",
        "entrypoints/cli/_config/_manager_actions.py": "_run_censal_pull",
    }
    for relative, function_name in frontend_functions.items():
        function = next(
            node
            for node in ast.walk(trees[relative])
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function_name
        )
        forbidden = {called_name(node) for node in ast.walk(function) if isinstance(node, ast.Call)} & {
            "apply_censal_read",
            "apply_profile_fact_changes",
            "apply_manager_profile_field_mutation",
        }
        assert forbidden == set()
