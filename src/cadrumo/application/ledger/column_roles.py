"""Inward port for semantic column-role resolution.

Financial-source adapters consume the result of column-role inference, but the
inference implementation is an optional outbound capability.  This structural
port keeps the inbound provider independent of that concrete adapter while
preserving the existing role tuple as the only required contract.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol, runtime_checkable

from ...core.field_role import FieldRole
from ...core.tabular import NormalizedTable


@runtime_checkable
class ColumnRoleMappingPort(Protocol):
    """One accepted role for each normalized table column."""

    @property
    def roles(self) -> tuple[FieldRole, ...]:
        """Return roles in the same positional order as table headers."""
        ...


ColumnRoleMappingResolverPort = Callable[[NormalizedTable], ColumnRoleMappingPort | None]
"""Resolve one normalized table into a role mapping, or decline it."""


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


def resolve_column_roles(table: NormalizedTable) -> ColumnRoleMappingPort | None:
    """Resolve ``table`` through the currently composed column-role port."""
    resolver = column_role_mapping_resolver()
    return None if resolver is None else resolver(table)


__all__ = [
    "ColumnRoleMappingPort",
    "ColumnRoleMappingResolverPort",
    "bind_column_role_mapping_resolver",
    "column_role_mapping_resolver",
    "resolve_column_roles",
]
