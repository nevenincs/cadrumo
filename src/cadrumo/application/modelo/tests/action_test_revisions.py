"""Synthetic Modelo revisions for the modelo action tests.

Each casilla and revision carries a synthetic legal and source reference, so a
test controls exactly which semantic roles and bindings the revision declares.
"""

from __future__ import annotations

from datetime import date

from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope

SYNTHETIC_LEGAL_REF = "test-actions:legal"
SYNTHETIC_SOURCE_REF = "test-actions-source"


def synthetic_casilla_definition(
    casilla_id: CasillaId,
    *,
    semantic_role: str | None = None,
    input_kind: InputKind = InputKind.MANUAL,
    binding: BindingId | None = None,
) -> CasillaDefinition:
    """A casilla carrying the given role, input kind and binding."""
    return CasillaDefinition(
        id=casilla_id,
        number=casilla_id,
        localization_keys=(f"test.schema.casilla.{casilla_id}.label",),
        section=("test",),
        input_kind=input_kind,
        binding=binding,
        semantic_role=semantic_role,
        legal_refs=(SYNTHETIC_LEGAL_REF,),
        source_refs=(SYNTHETIC_SOURCE_REF,),
    )


def synthetic_revision(
    *,
    casillas: tuple[CasillaDefinition, ...] = (),
    bindings: tuple[BindingDefinition, ...] = (),
) -> ModeloRevision:
    """A revision of the horizon year declaring only the given casillas and bindings."""
    filing_year = filing_year_envelope().horizon
    return ModeloRevision(
        id="test-actions-revision",
        localization_key="test.schema.revision.test-actions-revision.label",
        valid_from=date(filing_year, 1, 1),
        period_selector=PeriodSelector(years=(filing_year,), periods=("0A", "1T")),
        legal_refs=(SYNTHETIC_LEGAL_REF,),
        source_refs=(SYNTHETIC_SOURCE_REF,),
        casillas=casillas,
        bindings=bindings,
    )
