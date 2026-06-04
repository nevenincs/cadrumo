"""Typed input bundle for modelo work calculation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...domain.modelos._row_models import ModeloDetailRow


@dataclass(frozen=True, slots=True)
class WorkCalculateInputBundle:
    """Application-facing inputs for one `modelo work calculate` run."""

    casilla_inputs: Mapping[str, Decimal]
    binding_values: Mapping[str, Decimal]
    enum_binding_values: Mapping[str, str]
    relation_values: Mapping[str, Decimal]
    detail_rows: tuple[ModeloDetailRow, ...]
    borrador_snapshot_id: str | None

    @classmethod
    def build(
        cls,
        *,
        casilla_inputs: Mapping[str, Decimal],
        binding_values: Mapping[str, Decimal],
        enum_binding_values: Mapping[str, str],
        relation_values: Mapping[str, Decimal],
        detail_rows: tuple[ModeloDetailRow, ...],
        borrador_snapshot_id: str | None,
    ) -> WorkCalculateInputBundle:
        """Freeze CLI-assembled mappings before crossing into calculation services."""
        return cls(
            casilla_inputs=dict(casilla_inputs),
            binding_values=dict(binding_values),
            enum_binding_values=dict(enum_binding_values),
            relation_values=dict(relation_values),
            detail_rows=detail_rows,
            borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
        )

    def optional_binding_values(self) -> Mapping[str, Decimal] | None:
        """Return binding values using the calculation-service optional contract."""
        return self.binding_values or None

    def optional_enum_binding_values(self) -> Mapping[str, str] | None:
        """Return enum binding values using the calculation-service optional contract."""
        return self.enum_binding_values or None

    def optional_relation_values(self) -> Mapping[str, Decimal] | None:
        """Return relation values using the calculation-service optional contract."""
        return self.relation_values or None


__all__ = ["WorkCalculateInputBundle"]
