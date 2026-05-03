"""Identifier helpers for registry schema objects."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field

_MODELO_RE = r"^\d{3}$"
_REF_RE = r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$"
_CASILLA_RE = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"

type ModeloId = Annotated[str, Field(pattern=_MODELO_RE)]
type RevisionId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type CasillaId = Annotated[str, Field(min_length=1, max_length=32, pattern=_CASILLA_RE)]
type FormulaId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ParameterId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type BindingId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type RelationId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type LegalRefId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]
type SourceRefId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]
type ExportLayoutId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type RecordId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ExportFieldId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]


def is_registry_id(value: str) -> bool:
    """Return whether ``value`` is a stable registry id."""

    return re.fullmatch(_REF_RE, value) is not None
