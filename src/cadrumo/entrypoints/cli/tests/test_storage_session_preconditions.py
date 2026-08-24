"""S70 persistence-session refusals keep action policy at the CLI boundary."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import NoActiveBucketError
from ....adapters.persistence.storage.errors import (
    MasterKeyMaterialMissingError,
    MasterKeyUnavailableError,
    SessionExpiredError,
)
from ....adapters.persistence.storage.master_key import NoActiveBucketSessionError
from ....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .. import _errors
from .._common import cli_policy_refusal_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_CADRUMO_ROOT = Path(__file__).resolve().parents[3]
_PERSISTENCE_PRODUCERS = {
    "master_key/_active_session.py": _CADRUMO_ROOT
    / "adapters"
    / "persistence"
    / "storage"
    / "master_key"
    / "_active_session.py",
    "master_key/_bucket_session.py": _CADRUMO_ROOT
    / "adapters"
    / "persistence"
    / "storage"
    / "master_key"
    / "_bucket_session.py",
    "master_key/_master_key.py": _CADRUMO_ROOT
    / "adapters"
    / "persistence"
    / "storage"
    / "master_key"
    / "_master_key.py",
    "sql/secure_objects.py": _CADRUMO_ROOT / "adapters" / "persistence" / "storage" / "sql" / "secure_objects.py",
}


def _normalised_expression(source: str) -> str:
    return ast.dump(ast.parse(source, mode="eval").body, annotate_fields=False, include_attributes=False)


def _callee_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _raise_call_contracts(path: Path) -> tuple[tuple[str, Mapping[str, str]], ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    contracts: list[tuple[str, Mapping[str, str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        name = _callee_name(node.exc)
        if name not in {
            "NoActiveBucketSessionError",
            "MasterKeyUnavailableError",
            "NoActiveBucketError",
            "MasterKeyMaterialMissingError",
            "SessionExpiredError",
        }:
            continue
        contracts.append(
            (
                name,
                {
                    keyword.arg: ast.dump(keyword.value, annotate_fields=False, include_attributes=False)
                    for keyword in node.exc.keywords
                    if keyword.arg is not None
                },
            )
        )
    return tuple(contracts)


def test_s70_exactly_five_producers_keep_observed_fact_expression_polarity() -> None:
    """The five legacy command producers have one complete, mutation-sensitive census."""
    assert {
        relative: _raise_call_contracts(path)
        for relative, path in _PERSISTENCE_PRODUCERS.items()
    } == {
        "master_key/_active_session.py": (("NoActiveBucketSessionError", {}),),
        "master_key/_bucket_session.py": (
            (
                "MasterKeyUnavailableError",
                {
                    "context": _normalised_expression(
                        "{'resumed_profile_session': True, 'key_encryption_key_available': False}"
                    ),
                    "translated_message": _normalised_expression("'errors.auth.auth_storage_master_key_unavailable'"),
                },
            ),
        ),
        "master_key/_master_key.py": (
            ("NoActiveBucketError", {}),
            (
                "MasterKeyMaterialMissingError",
                {
                    "context": _normalised_expression(
                        "{'active_profile_resolved': True, 'profile_custody_unlocked': False}"
                    ),
                },
            ),
        ),
        "sql/secure_objects.py": (
            (
                "SessionExpiredError",
                {
                    "context": _normalised_expression(
                        "{'active_session_current': False, 'session_expired': True}"
                    ),
                },
            ),
        ),
    }


def test_s70_adapter_producers_cannot_author_actions_or_executable_recovery_prose() -> None:
    """Persistence records facts only; the entrypoint owns action resolution."""
    forbidden_constructors = {
        "PreconditionVerdict",
        "ConditionEvidence",
        "ActionReference",
        "no_action_precondition_verdict",
        "profile_session_failure_verdict",
    }
    for relative, path in _PERSISTENCE_PRODUCERS.items():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        imported_modules.extend(
            alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
        )
        constructed = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            if (name := _callee_name(node)) is not None
        }
        assert "application" not in ".".join(imported_modules), relative
        assert not constructed & forbidden_constructors, (relative, constructed & forbidden_constructors)
        assert "aeat config login" not in source.casefold(), relative
        assert "aeat config profile list" not in source.casefold(), relative


def test_s70_cli_boundary_delegates_all_verdict_construction_to_application_authorities() -> None:
    """The boundary selects established helpers; it does not rebuild verdict DTOs."""
    source = (_CADRUMO_ROOT / "entrypoints" / "cli" / "_errors.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    constructed = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        if (name := _callee_name(node)) is not None
    }

    assert not constructed & {"PreconditionVerdict", "ConditionEvidence", "ActionReference"}
    assert "profile_session_failure_verdict" in constructed
    assert "cli_exception_no_recovery_verdict" in constructed


def _project(error: Exception):
    projected = _errors.project_cli_boundary_error(error, lambda: None)
    projection = cli_policy_refusal_projection(projected)
    assert projection is not None
    return projection.precondition_action


@pytest.mark.parametrize(
    ("error_factory", "facts"),
    (
        (
            NoActiveBucketSessionError,
            {"active_bucket_session_available": False, "profile_login_target_available": False},
        ),
        (
            NoActiveBucketError,
            {"active_profile_resolved": False},
        ),
        (
            lambda: MasterKeyUnavailableError(
                context={"resumed_profile_session": True, "key_encryption_key_available": False}
            ),
            {"resumed_profile_session": True, "key_encryption_key_available": False},
        ),
        (
            lambda: MasterKeyMaterialMissingError(
                context={"active_profile_resolved": True, "profile_custody_unlocked": False}
            ),
            {"active_profile_resolved": True, "profile_custody_unlocked": False},
        ),
        (
            lambda: SessionExpiredError(context={"active_session_current": False, "session_expired": True}),
            {
                "active_session_current": False,
                "session_expired": True,
                "profile_login_target_available": False,
            },
        ),
    ),
    ids=("no-active-session", "no-active-profile", "resumed-kek", "missing-custody", "expired"),
)
def test_s70_boundary_projects_each_producer_without_a_resolved_profile_as_exact_no_action(
    monkeypatch: pytest.MonkeyPatch,
    error_factory: Callable[[], Exception],
    facts: Mapping[str, str | bool],
) -> None:
    """No bucket identifier is ever misrepresented as the action's public name."""
    monkeypatch.setattr(_errors, "active_profile_label_for_error", lambda: None)

    action = _project(error_factory())

    assert action.failed_condition_id == "cli.profile.login.completed"
    assert len(action.evidence) == 1
    evidence = action.evidence[0]
    assert evidence.condition_id == "cli.profile.login.completed"
    assert evidence.evidence_id == "cli.profile.login.completed.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert dict(evidence.values) == facts
    assert action.action is None
    assert action.argument_bindings == ()
    assert action.missing_argument_names == ()
    assert action.conditionality is ActionConditionality.NOT_APPLICABLE
    assert action.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


@pytest.mark.parametrize(
    ("error_factory", "condition", "reason"),
    (
        (NoActiveBucketSessionError, "profile.session.logged_in", "absent"),
        (
            lambda: SessionExpiredError(context={"active_session_current": False, "session_expired": True}),
            "profile.session.current",
            "expired_idle",
        ),
    ),
    ids=("no-active-session", "expired-session"),
)
def test_s70_boundary_reuses_canonical_login_action_only_for_a_proven_public_profile_target(
    monkeypatch: pytest.MonkeyPatch,
    error_factory: Callable[[], Exception],
    condition: str,
    reason: str,
) -> None:
    """The existing profile-session helper, not an adapter, resolves login."""
    monkeypatch.setattr(_errors, "active_profile_label_for_error", lambda: "operator-profile")

    action = _project(error_factory())

    assert action.failed_condition_id == condition
    assert action.action is not None
    assert action.action.action_id == "operator.profile.login"
    assert len(action.evidence) == 1
    evidence = action.evidence[0]
    assert evidence.condition_id == condition
    assert evidence.evidence_id == "profile.session.resume"
    assert evidence.provenance is ActionEvidenceProvenance.PERSISTED_STATE
    assert dict(evidence.values) == {
        "profile_name": "operator-profile",
        "session_resumed": False,
        "session_refusal_reason": reason,
    }
    assert action.argument_bindings[0].argument_name == "name"
    assert action.argument_bindings[0].value == "operator-profile"
    assert action.conditionality is ActionConditionality.IMMEDIATE
    assert action.no_recovery_outcome is None


def test_s70_sqlalchemy_wrapped_no_session_error_reaches_the_same_canonical_login_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real encrypted-column wrapping shape cannot bypass the boundary policy."""
    import sqlalchemy.exc as sa_exc

    monkeypatch.setattr(_errors, "active_profile_label_for_error", lambda: "operator-profile")
    wrapped = sa_exc.StatementError(
        message="bind-param processing failed",
        statement="SELECT secure_objects.payload FROM secure_objects",
        params={},
        orig=NoActiveBucketSessionError(),
    )

    action = _project(wrapped)

    assert action.failed_condition_id == "profile.session.logged_in"
    assert action.action is not None
    assert action.action.action_id == "operator.profile.login"
    assert dict(action.evidence[0].values) == {
        "profile_name": "operator-profile",
        "session_resumed": False,
        "session_refusal_reason": "absent",
    }
