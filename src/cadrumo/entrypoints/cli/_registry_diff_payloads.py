"""Typed ``--json`` payload schemas for ``aeat app registry diff-revisions``.

Each class declared here is a strict
:class:`~core.json_contract.OutputSchema` subclass and a deferred public schema
target referenced by production-authored CommandSpec so the JSON-contract test suite can enumerate the
``registry.diff_revisions`` command surface.

Field sets mirror :class:`~application.registry.RegistryRevisionDiffReport`
and its nested projections. All sequence fields use ``list`` rather than
``tuple`` because ``model_dump(mode='json')`` serialises pydantic tuples as
JSON arrays, and the strict ``OutputSchema`` base does not coerce lists back to
tuples on re-validation. ``expression`` fields stay ``dict[str, object]``
because :class:`~domain.calculations.registry.FormulaExpression` is a
recursive tree; every other field is a concrete typed projection, not a bare
mapping.

See Also:
    :class:`~application.registry.RegistryRevisionDiffReport`
        Application report shape these JSON payloads project.
    :func:`~application.registry.diff_registry_revisions`
        Read-side service that builds the revision diff report.
    :mod:`~entrypoints.cli.registry`
        CLI command surface that emits these payload schemas.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision type whose casillas, formulas, parameters, bindings,
        and legal refs are compared.
    :class:`~core.json_contract.OutputSchema`
        Strict base class for typed CLI JSON result payloads.
    Production-authored CommandSpec deferred schema target
        Public schema target traversed by graph-derived JSON-contract tests.
"""

from __future__ import annotations

from ...core.casilla_id import CasillaId
from ...core.json_contract import OutputSchema
from ...domain.calculations.registry.ids import FormulaId, LegalRefId, ParameterId, RevisionId


class CasillaDiffPayload(OutputSchema):
    """One added or removed casilla row."""

    id: CasillaId
    number: str
    label: str


class RenumberedCasillaPayload(OutputSchema):
    """One casilla whose ``continuidad_id`` persisted but whose id/number changed."""

    continuidad_id: str
    from_id: CasillaId
    from_number: str
    to_id: CasillaId
    to_number: str


class FormulaDiffPayload(OutputSchema):
    """One formula whose expression, rounding, or legal grounding changed."""

    id: FormulaId
    target_casilla_id: CasillaId
    from_expression: dict[str, object]
    to_expression: dict[str, object]
    from_legal_refs: list[LegalRefId] = []
    to_legal_refs: list[LegalRefId] = []


class ParameterDiffPayload(OutputSchema):
    """One parameter (rate/threshold/bracket table) whose value changed."""

    id: ParameterId
    data_type: str
    from_legal_refs: list[LegalRefId] = []
    to_legal_refs: list[LegalRefId] = []


class BindingDiffPayload(OutputSchema):
    """One added or removed data binding row."""

    id: str
    source: str


class RegistryDiffRevisionsResult(OutputSchema):
    """JSON envelope for ``aeat app registry diff-revisions``.

    Mirrors :class:`~application.registry.RegistryRevisionDiffReport`
    returned by :func:`~application.registry.diff_registry_revisions`.
    ``same_revision`` is ``True`` when ``from_year`` and ``to_year`` resolve to
    the identical revision id, in which case every diff dimension is empty.
    """

    modelo: str
    from_year: int
    to_year: int
    from_revision_id: RevisionId
    to_revision_id: RevisionId
    same_revision: bool

    added_casillas: list[CasillaDiffPayload] = []
    removed_casillas: list[CasillaDiffPayload] = []
    renumbered_casillas: list[RenumberedCasillaPayload] = []
    changed_casilla_legal_refs: list[CasillaId] = []

    added_formulas: list[FormulaId] = []
    removed_formulas: list[FormulaId] = []
    changed_formulas: list[FormulaDiffPayload] = []

    added_parameters: list[ParameterId] = []
    removed_parameters: list[ParameterId] = []
    changed_parameters: list[ParameterDiffPayload] = []

    added_bindings: list[BindingDiffPayload] = []
    removed_bindings: list[BindingDiffPayload] = []

    revision_legal_refs_added: list[LegalRefId] = []
    revision_legal_refs_removed: list[LegalRefId] = []


__all__ = [
    "BindingDiffPayload",
    "CasillaDiffPayload",
    "FormulaDiffPayload",
    "ParameterDiffPayload",
    "RegistryDiffRevisionsResult",
    "RenumberedCasillaPayload",
]
