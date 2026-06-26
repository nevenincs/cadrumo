"""Identifier helpers for registry schema objects."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field

from ....core import CasillaId as CasillaId
from ....core import validated_casilla_id as validated_casilla_id
from ....core import validated_casilla_id_map as validated_casilla_id_map

_MODELO_RE = r"^\d{3}$"
_REF_RE = r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$"
# AEAT-canonical XML-dictionary field IDs (e.g. DPNIF_D, IDDeclarante)
# are uppercase + underscore. Kept separate from _REF_RE so the
# lowercase-only constraint on internal registry refs is preserved.
_EXPORT_FIELD_RE = r"^[A-Za-z0-9][A-Za-z0-9._:_-]*$"

type ModeloId = Annotated[str, Field(pattern=_MODELO_RE)]
type RevisionId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type FormulaId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ParameterId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type BindingId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type RelationId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type LegalRefId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]
type SourceRefId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]
type ExtractionProfileId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type CrossReferenceId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type WorkbookParityRefId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type VerificationExpectationId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ApplicationLinkId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type DeadlineWindowId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type SupportRemovalDecisionId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ConstructId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type DependencyClassificationId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ExportLayoutId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type RecordId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ExportFieldId = Annotated[str, Field(min_length=1, max_length=160, pattern=_EXPORT_FIELD_RE)]
type WorkbookFixtureId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]
type WorkbookOutputId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type OracleId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]


def is_registry_id(value: str) -> bool:
    """Return whether ``value`` is a stable registry id."""
    return re.fullmatch(_REF_RE, value) is not None
