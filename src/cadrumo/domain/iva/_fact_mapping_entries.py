"""IVA-specific error boundary for canonical governed string mappings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedMappingFact
from ..calculations.registry.facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingPolicy,
    string_mapping_entries,
)
from .errors import IvaValidationError

IvaMappingSubject = Literal[
    "IVA classification mapping",
    "IVA component mapping",
    "IVA statutory citation mapping",
]


def iva_mapping_entries(
    resolved: ResolvedMappingFact,
    *,
    subject: IvaMappingSubject,
) -> Mapping[str, str]:
    """Project IVA mapping entries while retaining the IVA error contract."""
    try:
        entries = string_mapping_entries(
            resolved,
            policy=StringMappingPolicy(
                subject=subject,
                value_whitespace=MappingValueWhitespace.PRESERVE,
            ),
        )
    except RegistryValidationError as error:
        message = str(error)
    else:
        return entries
    raise IvaValidationError(message)
