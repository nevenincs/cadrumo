"""Identifier helpers for registry schema objects."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field, TypeAdapter

_MODELO_RE = r"^\d{3}$"
_REF_RE = r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$"
_SOURCE_ID_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)+$"
# AEAT-canonical XML-dictionary field IDs (e.g. DPNIF_D, IDDeclarante)
# are uppercase + underscore. Kept separate from _REF_RE so the
# lowercase-only constraint on internal registry refs is preserved.
_EXPORT_FIELD_RE = r"^[A-Za-z0-9][A-Za-z0-9._:_-]*$"
# Live parity oracle identifiers are registry-bound adapter keys, not generic
# registry refs: current bindings are kebab-case lowercase ASCII identifiers.
_ORACLE_ID_RE = r"^[a-z](?:[a-z0-9-]{0,126}[a-z0-9])?$"

type ModeloId = Annotated[str, Field(pattern=_MODELO_RE)]
type RevisionId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type FormulaId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ParameterId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type BindingId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type RelationId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type LegalRefId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]
type SourceRefId = Annotated[str, Field(min_length=1, max_length=160, pattern=_SOURCE_ID_RE)]
type ExtractionProfileId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type CrossReferenceId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type WorkbookParityRefId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type VerificationExpectationId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ApplicationLinkId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type DeadlineWindowId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ConstructId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type DependencyClassificationId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ApplicabilityRuleId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ExportLayoutId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type RecordId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type ExportFieldId = Annotated[str, Field(min_length=1, max_length=160, pattern=_EXPORT_FIELD_RE)]
type WorkbookFixtureId = Annotated[str, Field(min_length=1, max_length=160, pattern=_REF_RE)]
type WorkbookOutputId = Annotated[str, Field(min_length=1, max_length=128, pattern=_REF_RE)]
type OracleId = Annotated[str, Field(min_length=1, max_length=128, pattern=_ORACLE_ID_RE)]


def is_registry_id(value: str) -> bool:
    """Return whether ``value`` is a stable registry id."""
    return re.fullmatch(_REF_RE, value) is not None


LEGAL_REFS_ADAPTER: TypeAdapter[tuple[LegalRefId, ...]] = TypeAdapter(tuple[LegalRefId, ...])
"""Validate a tuple of legal reference ids, beside the type it validates.

Two modules built this adapter independently. Keeping it with the type
means a change to LegalRefId cannot leave a copy validating the old shape.
"""

SOURCE_REFS_ADAPTER: TypeAdapter[tuple[SourceRefId, ...]] = TypeAdapter(tuple[SourceRefId, ...])
"""Validate a tuple of source reference ids, beside the type it validates."""
