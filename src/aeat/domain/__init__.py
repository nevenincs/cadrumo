"""Domain layer for the ``aeat`` package.

This package hosts the pure domain types and rules — modelos, registry
definitions, deadlines, attachments, categories, and other business primitives. Modules
under :mod:`aeat.domain` must remain free of I/O and infrastructure
dependencies; orchestration and persistence live in
:mod:`aeat.application` and :mod:`aeat.adapters`.
"""

from __future__ import annotations

from ._identifiers import ModeloIdentifier

__all__ = [
    "ModeloIdentifier",
]
