"""Typed ``--json`` payload schemas for ``aeat app registry diff-revisions``.

Each class declared here is a strict
:class:`~entrypoints.cli._schemas.OutputSchema` subclass and is decorated
with :func:`~entrypoints.cli._schemas.register_schema` so the JSON-contract test suite can enumerate the
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
    :class:`~entrypoints.cli._schemas.OutputSchema`
        Strict base class for typed CLI JSON result payloads.
    :func:`~entrypoints.cli._schemas.register_schema`
        Schema registry hook used by the JSON-contract tests.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


class CasillaDiffPayload(OutputSchema):
    """One added or removed casilla row."""

    id: str
    number: str
    label: str


class RenumberedCasillaPayload(OutputSchema):
    """One casilla whose ``continuidad_id`` persisted but whose id/number changed."""

    continuidad_id: str
    from_id: str
    from_number: str
    to_id: str
    to_number: str


class FormulaDiffPayload(OutputSchema):
    """One formula whose expression, rounding, or legal grounding changed."""

    id: str
    target_casilla_id: str
    from_expression: dict[str, object]
    to_expression: dict[str, object]
    from_legal_refs: list[str] = []
    to_legal_refs: list[str] = []


class ParameterDiffPayload(OutputSchema):
    """One parameter (rate/threshold/bracket table) whose value changed."""

    id: str
    data_type: str
    from_legal_refs: list[str] = []
    to_legal_refs: list[str] = []


class BindingDiffPayload(OutputSchema):
    """One added or removed data binding row."""

    id: str
    source: str


@register_schema("registry.diff_revisions")
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
    from_revision_id: str
    to_revision_id: str
    same_revision: bool

    added_casillas: list[CasillaDiffPayload] = []
    removed_casillas: list[CasillaDiffPayload] = []
    renumbered_casillas: list[RenumberedCasillaPayload] = []
    changed_casilla_legal_refs: list[str] = []

    added_formulas: list[str] = []
    removed_formulas: list[str] = []
    changed_formulas: list[FormulaDiffPayload] = []

    added_parameters: list[str] = []
    removed_parameters: list[str] = []
    changed_parameters: list[ParameterDiffPayload] = []

    added_bindings: list[BindingDiffPayload] = []
    removed_bindings: list[BindingDiffPayload] = []

    revision_legal_refs_added: list[str] = []
    revision_legal_refs_removed: list[str] = []


__all__ = [
    "BindingDiffPayload",
    "CasillaDiffPayload",
    "FormulaDiffPayload",
    "ParameterDiffPayload",
    "RegistryDiffRevisionsResult",
    "RenumberedCasillaPayload",
]
