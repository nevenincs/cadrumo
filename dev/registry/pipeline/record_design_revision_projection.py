"""Source-pinned revision view of a multi-scheme official record design."""

from __future__ import annotations

from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import RevisionId

from .record_design_intermediate import RecordDesignIntermediate

_M369_SOURCE_SHA256: Final[str] = "b59ade58821e8e0988a1aa4e2a7f52c97b21375fc0a6720d76ca0601a7c8b1a3"
_M369_BODY_CONTENT: Final[str] = (
    "Posibles páginas presentación:\n"
    "T36900 - común siempre se envía\n"
    "Exterior: T36901 a T36903\n"
    "Union: T36904 a T36909\n"
    "Importación: T36910 a T36912"
)
_M369_SHEETS: Final[tuple[str, ...]] = (
    "T36900 Info Adicional",
    "T36901 Ext",
    "T36902 Ext",
    "T36903 Ext",
    "T36904 Un",
    "T36905 Un",
    "T36906 Un",
    "T36907 Un",
    "T36908 Un",
    "T36909 Un",
    "T36910 Imp",
    "T36911 Imp",
    "T36912 Imp",
)
_M369_REVISION_SHEETS: Final[dict[str, tuple[str, ...]]] = {
    "esquema-exterior": _M369_SHEETS[:4],
    "esquema-union": (_M369_SHEETS[0], *_M369_SHEETS[4:10]),
    "esquema-importacion": (_M369_SHEETS[0], *_M369_SHEETS[10:]),
}


def project_record_design_for_revision(
    intermediate: RecordDesignIntermediate,
    revision_id: RevisionId,
) -> RecordDesignIntermediate:
    """Retain only pages the source itself assigns to this M369 scheme."""
    if intermediate.source.source_ref != "aeat-dr-369-2021":
        return intermediate
    if (
        intermediate.source.source_sha256 != _M369_SOURCE_SHA256
        or intermediate.source.design_epoch != "2021"
        or len(intermediate.variable_envelopes) != 1
        or intermediate.variable_envelopes[0].body_content != _M369_BODY_CONTENT
    ):
        raise RegistryValidationError("M369 revision projection differs from the exact reviewed official source")
    selected = _M369_REVISION_SHEETS.get(str(revision_id))
    if selected is None:
        raise RegistryValidationError(f"M369 source declares no fixed-page range for revision {revision_id!r}")
    actual_sheets = tuple(sheet.record_identity for sheet in intermediate.sheets)
    if actual_sheets == selected:
        return intermediate
    if actual_sheets != _M369_SHEETS:
        raise RegistryValidationError(
            "M369 revision projection requires all official pages or its exact selected range"
        )
    return intermediate.model_copy(
        update={"sheets": tuple(sheet for sheet in intermediate.sheets if sheet.record_identity in selected)}
    )
