"""Tripwire ports for building a registered operation's real public contract without private custody."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from ...application.auth.operator_scope_ports import (
    OperatorScopeBucketPaths,
    OperatorScopePorts,
    OperatorScopeSession,
)
from ...application.modelo.operation_definitions import (
    build_modelo_work_file_definition,
    build_modelo_work_file_registration,
)
from ...application.operations.registry import OperationPublicDefinitionContractV1


def unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract construction must not open a private profile")


class UnavailableOperatorScope:
    """Tripwire ports: constructing the real public contract needs no private custody."""

    def resolve(self, root: Path, bucket_id: str) -> NoReturn:
        return unavailable(root, bucket_id)

    def acquire_lock(self, paths: OperatorScopeBucketPaths, *, wait_seconds: float) -> NoReturn:
        return unavailable(paths, wait_seconds=wait_seconds)

    def release_lock(self, paths: OperatorScopeBucketPaths) -> NoReturn:
        return unavailable(paths)

    def current(self) -> NoReturn:
        return unavailable()

    def serves_bucket(self, session: OperatorScopeSession | None, bucket_id: str) -> NoReturn:
        return unavailable(session, bucket_id)


def unavailable_operator_scope_ports() -> OperatorScopePorts:
    scope = UnavailableOperatorScope()
    return OperatorScopePorts(storage=scope, session=scope)


def modelo_work_file_contract() -> OperationPublicDefinitionContractV1:
    definition = build_modelo_work_file_definition(
        certificate_secret_backend_factory=unavailable,
        operator_scope_ports=unavailable_operator_scope_ports(),
        filing_action_ports_factory=unavailable,
        profile_resolver=unavailable,
    )
    return build_modelo_work_file_registration(definition).contract
