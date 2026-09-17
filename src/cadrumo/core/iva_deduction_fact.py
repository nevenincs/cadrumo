"""Opaque IVA-deduction authority axes projected from the facts registry."""

from __future__ import annotations

from .registry_token import StrictRegistryToken


class IvaDeductionFactKind(StrictRegistryToken):
    """Opaque deduction-kind token projected from governed fact 0085."""

    __slots__ = ()


class IvaDeductionEvidenceAuthority(StrictRegistryToken):
    """Opaque evidence-authority token projected from governed fact 0085."""

    __slots__ = ()


__all__ = [
    "IvaDeductionEvidenceAuthority",
    "IvaDeductionFactKind",
]
