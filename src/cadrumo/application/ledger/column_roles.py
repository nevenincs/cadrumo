"""Inward port for semantic column-role resolution.

Financial-source adapters consume the result of column-role inference, but the
inference implementation is an optional outbound capability.  This structural
port keeps the inbound provider independent of that concrete adapter while
preserving the existing role tuple as the only required contract.

A resolver answers in one of three ways, and they mean different things to the
person importing the file: a mapping; :class:`ColumnRoleReaderUnavailable`,
when the model that names columns could not be asked; or ``None``, when it was
asked and established nothing, or no resolver is composed at all.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ...core.field_role import FieldRole
from ...core.tabular import NormalizedTable
from ..operator_actions.models import PreconditionVerdict


@runtime_checkable
class ColumnRoleMappingPort(Protocol):
    """One accepted role for each normalized table column."""

    @property
    def roles(self) -> tuple[FieldRole, ...]:
        """Return roles in the same positional order as table headers."""
        ...


@dataclass(frozen=True, slots=True)
class ColumnRoleReaderUnavailable:
    """The model that names a table's columns could not be asked, so no mapping exists.

    Distinct from a decline. A decline says the model looked at the headers and
    established nothing; this says the file was never looked at, because the
    agent refused the role. The verdict carries the agent's refusal.
    """

    precondition_verdict: PreconditionVerdict


ColumnRoleMappingResolverPort = Callable[[NormalizedTable], ColumnRoleMappingPort | ColumnRoleReaderUnavailable | None]
"""Resolve one normalized table into a role mapping, report its reader unavailable, or decline it."""


_BOUND_COLUMN_ROLE_MAPPING_RESOLVER: ContextVar[ColumnRoleMappingResolverPort] = ContextVar(
    "cadrumo_column_role_mapping_resolver",
)


@contextmanager
def bind_column_role_mapping_resolver(
    resolver: ColumnRoleMappingResolverPort,
) -> Generator[ColumnRoleMappingResolverPort]:
    """Bind the outward column-role implementation for one runtime scope."""
    token = _BOUND_COLUMN_ROLE_MAPPING_RESOLVER.set(resolver)
    try:
        yield resolver
    finally:
        _BOUND_COLUMN_ROLE_MAPPING_RESOLVER.reset(token)


def column_role_mapping_resolver() -> ColumnRoleMappingResolverPort | None:
    """Return the resolver installed by an outer composition root, if any."""
    return _BOUND_COLUMN_ROLE_MAPPING_RESOLVER.get(None)


def resolve_column_roles(table: NormalizedTable) -> ColumnRoleMappingPort | ColumnRoleReaderUnavailable | None:
    """Resolve ``table`` through the currently composed column-role port."""
    resolver = column_role_mapping_resolver()
    return None if resolver is None else resolver(table)


__all__ = [
    "ColumnRoleMappingPort",
    "ColumnRoleMappingResolverPort",
    "ColumnRoleReaderUnavailable",
    "bind_column_role_mapping_resolver",
    "column_role_mapping_resolver",
    "resolve_column_roles",
]
